-- V010: CDC sobre as tabelas reais do OLTP (substitui a tabela de demonstração da V006).
--
-- A V006 capturava mudanças só em e2_oltp_reserva_demo, uma tabela fora do
-- modelo. Aqui a mesma outbox transacional passa a receber os eventos de:
--   - reserva_vaga        (insert-only: cada carga gera INSERTs)
--   - disciplina          (upsert: renomeação ou correção de carga horária gera UPDATE)
--   - curriculo_componente (upsert: mudança de natureza/grupo gera UPDATE)
--
-- O evento é gravado na mesma transação da mudança (outbox): se a transação
-- é desfeita, o evento some junto. UPDATE que não muda nada (o upsert do
-- loader reprocessando o mesmo lote) não gera evento.

ALTER TABLE e2_cdc_outbox ADD COLUMN IF NOT EXISTS tabela TEXT;
UPDATE e2_cdc_outbox SET tabela = 'e2_oltp_reserva_demo' WHERE tabela IS NULL;
ALTER TABLE e2_cdc_outbox ALTER COLUMN tabela SET NOT NULL;

DROP TRIGGER IF EXISTS e2_reserva_cdc ON e2_oltp_reserva_demo;
DROP FUNCTION IF EXISTS e2_capture_reserva_change();
DROP TABLE IF EXISTS e2_oltp_reserva_demo;
DELETE FROM e2_cdc_outbox WHERE tabela = 'e2_oltp_reserva_demo';

-- Chave do agregado por tabela, montada a partir da chave primária.
CREATE OR REPLACE FUNCTION e2_cdc_chave(tabela TEXT, linha JSONB)
RETURNS TEXT
LANGUAGE sql IMMUTABLE
AS $$
    SELECT CASE tabela
        WHEN 'reserva_vaga'         THEN (linha->>'turma_id') || ':' || (linha->>'curso_id')
        WHEN 'disciplina'           THEN linha->>'codigo'
        WHEN 'curriculo_componente' THEN (linha->>'curriculo_id') || ':' || (linha->>'disciplina_id')
    END
$$;

CREATE OR REPLACE FUNCTION e2_cdc_captura()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    linha JSONB := CASE WHEN TG_OP = 'DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
BEGIN
    INSERT INTO e2_cdc_outbox (tabela, aggregate_key, operation, payload)
    VALUES (
        TG_TABLE_NAME,
        e2_cdc_chave(TG_TABLE_NAME, linha),
        TG_OP,
        CASE WHEN TG_OP = 'DELETE' THEN jsonb_build_object() ELSE linha END
    );
    RETURN NULL;  -- AFTER trigger: o retorno é ignorado
END;
$$;

DROP TRIGGER IF EXISTS cdc_reserva_vaga ON reserva_vaga;
CREATE TRIGGER cdc_reserva_vaga
AFTER INSERT ON reserva_vaga
FOR EACH ROW EXECUTE FUNCTION e2_cdc_captura();

DROP TRIGGER IF EXISTS cdc_disciplina_ins ON disciplina;
CREATE TRIGGER cdc_disciplina_ins
AFTER INSERT OR DELETE ON disciplina
FOR EACH ROW EXECUTE FUNCTION e2_cdc_captura();

DROP TRIGGER IF EXISTS cdc_disciplina_upd ON disciplina;
CREATE TRIGGER cdc_disciplina_upd
AFTER UPDATE ON disciplina
FOR EACH ROW WHEN (OLD.* IS DISTINCT FROM NEW.*)
EXECUTE FUNCTION e2_cdc_captura();

DROP TRIGGER IF EXISTS cdc_curriculo_componente_ins ON curriculo_componente;
CREATE TRIGGER cdc_curriculo_componente_ins
AFTER INSERT OR DELETE ON curriculo_componente
FOR EACH ROW EXECUTE FUNCTION e2_cdc_captura();

DROP TRIGGER IF EXISTS cdc_curriculo_componente_upd ON curriculo_componente;
CREATE TRIGGER cdc_curriculo_componente_upd
AFTER UPDATE ON curriculo_componente
FOR EACH ROW WHEN (OLD.* IS DISTINCT FROM NEW.*)
EXECUTE FUNCTION e2_cdc_captura();

COMMENT ON TABLE e2_cdc_outbox IS
    'Outbox CDC: um evento por INSERT/UPDATE/DELETE em reserva_vaga, disciplina e curriculo_componente (V010)';
