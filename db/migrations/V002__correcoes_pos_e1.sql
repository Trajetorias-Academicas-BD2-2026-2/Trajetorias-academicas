-- V002__correcoes_pos_e1.sql
-- Correções sobre o esquema da E1. V001 não é editada: bancos que já a
-- aplicaram recebem só esta diferença (ver db/migrate.sh).
-- Aplicada numa única transação.

-- 1) Lotação acima da oferta é dado válido, e é o sinal que a pergunta de
--    gestão procura. A V001 rejeitava ocupação > oferta + 5, o que obrigava
--    o loader a "corrigir" o dado. Mantém-se só a não negatividade; valores
--    implausíveis (erro de parsing) são apontados por tests/sanity_checks.sql.
ALTER TABLE oferta_turma DROP CONSTRAINT oferta_turma_check;
ALTER TABLE oferta_turma ADD CONSTRAINT oferta_turma_vagas_ocupadas_check CHECK (vagas_ocupadas >= 0);

-- 2) Turma sem horário (TCC, estágio) passa a ter turno explícito em vez
--    de ser classificada como DIURNO por padrão.
ALTER TABLE oferta_turma DROP CONSTRAINT oferta_turma_turno_check;
ALTER TABLE oferta_turma ADD CONSTRAINT oferta_turma_turno_check
    CHECK (turno IN ('DIURNO', 'NOTURNO', 'INTEGRAL', 'SEM_HORARIO'));

-- 3) Carimbos de tempo por papel, com fuso:
--    ano/periodo = quando o evento (a oferta) aconteceu;
--    coletado_em = quando o dado foi raspado do SIGAA (vem do CSV);
--    ingerido_em = quando a linha entrou neste banco.
ALTER TABLE oferta_turma
    ALTER COLUMN ingerido_em TYPE TIMESTAMPTZ USING ingerido_em AT TIME ZONE 'UTC';
ALTER TABLE oferta_turma ADD COLUMN coletado_em TIMESTAMPTZ;
UPDATE oferta_turma SET coletado_em = ingerido_em WHERE coletado_em IS NULL;
ALTER TABLE oferta_turma ALTER COLUMN coletado_em SET NOT NULL;
COMMENT ON COLUMN oferta_turma.coletado_em IS 'Quando a linha foi raspada do SIGAA';
COMMENT ON COLUMN oferta_turma.ingerido_em IS 'Quando a linha foi inserida neste banco';

-- 4) A expressão de pré-requisito do SIGAA tem lógica E/OU, que a tabela
--    pre_requisito (pares) não representa. A expressão original fica aqui;
--    pre_requisito guarda as disciplinas citadas, para o ranking de
--    "quais disciplinas mais travam a grade".
ALTER TABLE disciplina ADD COLUMN pre_requisito_expressao TEXT;
COMMENT ON COLUMN disciplina.pre_requisito_expressao IS
    'Expressão de pré-requisito como o SIGAA mostra, ex.: ( FGA0001 E FGA0002 ) OU ( FGA0003 )';
COMMENT ON TABLE pre_requisito IS
    'Disciplinas citadas na expressão de pré-requisito de disciplina_id (a lógica E/OU fica em disciplina.pre_requisito_expressao)';

COMMENT ON COLUMN curso.codigo IS
    'Código definido pelo projeto (loader/scrape_cursos.py); a listagem pública do SIGAA não expõe um código estável';

-- 5) Insert-only garantido pelo banco, não só por convenção do loader.
CREATE OR REPLACE FUNCTION oferta_turma_insert_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'oferta_turma é insert-only: % não é permitido (ver docs/historico.md)', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER oferta_turma_bloqueia_alteracao
    BEFORE UPDATE OR DELETE ON oferta_turma
    FOR EACH ROW EXECUTE FUNCTION oferta_turma_insert_only();

CREATE TRIGGER oferta_turma_bloqueia_truncate
    BEFORE TRUNCATE ON oferta_turma
    FOR EACH STATEMENT EXECUTE FUNCTION oferta_turma_insert_only();

-- 6) Índices para as consultas de referência (docs/carga-de-trabalho.md):
--    ranking de pré-requisitos e junção curso -> disciplina.
CREATE INDEX IF NOT EXISTS idx_pre_requisito_pre_requisito ON pre_requisito(pre_requisito_id);
CREATE INDEX IF NOT EXISTS idx_curso_disciplina_disciplina ON curso_disciplina(disciplina_id);
