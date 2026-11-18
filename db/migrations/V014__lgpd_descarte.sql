-- V014 (E4): descarte de dado pessoal ao fim da retenção (docs/lgpd.md).
--
-- O único dado pessoal no banco é o nome do docente (public.docente.nome).
-- Retenção: até 30/06/2027 (fim da disciplina + 6 meses para revisão de nota).
-- Descarte = pseudonimização: o nome vira DOCENTE-<id>. Os vínculos
-- turma_docente continuam (contagem de docentes por turma), sem identificar
-- ninguém. Cada execução fica registrada em operations.descartes.
--
-- Uso (só o dono do banco):
--   SELECT * FROM operations.descartar_dados_pessoais('fim da retenção', true);
-- Com confirmado = false, só informa o que seria descartado.

CREATE TABLE IF NOT EXISTS operations.descartes (
    id            BIGSERIAL PRIMARY KEY,
    executado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    executado_por TEXT NOT NULL DEFAULT current_user,
    motivo        TEXT NOT NULL,
    tabela        TEXT NOT NULL,
    coluna        TEXT NOT NULL,
    linhas        INTEGER NOT NULL
);
COMMENT ON TABLE operations.descartes IS 'Registro de cada descarte de dado pessoal (LGPD, E4)';

CREATE OR REPLACE FUNCTION operations.descartar_dados_pessoais(motivo TEXT, confirmado BOOLEAN DEFAULT false)
RETURNS TABLE (tabela TEXT, coluna TEXT, linhas_afetadas INTEGER, executado BOOLEAN)
LANGUAGE plpgsql
AS $$
DECLARE
    n INTEGER;
BEGIN
    SELECT count(*) INTO n FROM public.docente WHERE nome NOT LIKE 'DOCENTE-%';
    IF confirmado THEN
        UPDATE public.docente SET nome = 'DOCENTE-' || lpad(id::text, 4, '0') WHERE nome NOT LIKE 'DOCENTE-%';
        INSERT INTO operations.descartes (motivo, tabela, coluna, linhas)
        VALUES (motivo, 'public.docente', 'nome', n);
    END IF;
    RETURN QUERY SELECT 'public.docente'::TEXT, 'nome'::TEXT, n, confirmado;
END;
$$;
REVOKE ALL ON FUNCTION operations.descartar_dados_pessoais(TEXT, BOOLEAN) FROM PUBLIC;
