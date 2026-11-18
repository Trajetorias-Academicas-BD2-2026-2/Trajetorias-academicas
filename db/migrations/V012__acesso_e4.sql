-- V012 (E4): privilégio mínimo com recorte de LINHA (RLS) e de COLUNA.
--
-- Papéis (senhas só de desenvolvimento; em produção viriam de um cofre):
--   painel       lê a camada de consumo inteira, nada do OLTP           (herda dashboard_reader)
--   etl_reverso  lê métricas e marts, escreve só a fila de envio da Pauta
--   coord_soft   coordenador de Software: vê só as linhas de FGA_SOFT    (herda coordenador)
--   coord_elet   coordenador de Eletrônica: vê só as linhas de FGA_ELET  (herda coordenador)
--   auditor_lgpd audita docentes por id, sem ver o nome (recorte de coluna)
--
-- As tabelas de analytics são recriadas pelo dbt a cada execução, o que apaga
-- as políticas de RLS. Por isso o recorte de linha é aplicado pela função
-- operations.aplicar_acesso_analytics(), chamada no fim de todo `dbt build`
-- (on-run-end) e por analytics/semantica.py. tests/acesso_checks.sql confere.

DO $$
DECLARE
    papel RECORD;
BEGIN
    FOR papel IN SELECT * FROM (VALUES
        ('painel', 'painel_dev_only', true),
        ('etl_reverso', 'etl_dev_only', true),
        ('coord_soft', 'coord_dev_only', true),
        ('coord_elet', 'coord_dev_only', true),
        ('auditor_lgpd', 'auditor_dev_only', true),
        ('coordenador', NULL, false)
    ) AS p(nome, senha, login)
    LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = papel.nome) THEN
            IF papel.login THEN
                EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', papel.nome, papel.senha);
            ELSE
                EXECUTE format('CREATE ROLE %I NOLOGIN', papel.nome);
            END IF;
        END IF;
    END LOOP;
END
$$;

GRANT dashboard_reader TO painel;
GRANT coordenador TO coord_soft, coord_elet;

-- Quem vê o quê, por curso (recorte de linha).
CREATE TABLE IF NOT EXISTS operations.acesso_curso (
    usuario      TEXT NOT NULL,
    -- sem FK para public.curso: as migrações rodam antes da carga (curso ainda vazio)
    curso_codigo VARCHAR(20) NOT NULL,
    PRIMARY KEY (usuario, curso_codigo)
);
COMMENT ON TABLE operations.acesso_curso IS
    'Recorte de linha: cada coordenador vê só os cursos listados aqui (RLS da E4)';
INSERT INTO operations.acesso_curso VALUES ('coord_soft', 'FGA_SOFT'), ('coord_elet', 'FGA_ELET')
ON CONFLICT DO NOTHING;

-- Esquemas: ninguém além do dono acessa o OLTP, exceto o recorte de coluna do auditor.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO auditor_lgpd;
GRANT USAGE ON SCHEMA analytics TO etl_reverso, coordenador;
GRANT USAGE ON SCHEMA operations TO etl_reverso, coordenador;
GRANT SELECT ON operations.acesso_curso TO coordenador, dashboard_reader, etl_reverso;

-- Recorte de COLUNA: o nome do docente é dado pessoal. O auditor conta e cruza
-- docentes por id, mas não lê o nome.
GRANT SELECT (id) ON public.docente TO auditor_lgpd;
GRANT SELECT ON public.turma_docente TO auditor_lgpd;

CREATE OR REPLACE FUNCTION operations.aplicar_acesso_analytics()
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    tabela TEXT;
BEGIN
    FOREACH tabela IN ARRAY ARRAY[
        'fct_reservas', 'mart_observatorio', 'mart_disciplina_semestre',
        'mart_cobertura_curriculo', 'metricas_oficiais']
    LOOP
        IF to_regclass('analytics.' || tabela) IS NULL THEN
            CONTINUE;
        END IF;
        EXECUTE format('ALTER TABLE analytics.%I ENABLE ROW LEVEL SECURITY', tabela);
        EXECUTE format('DROP POLICY IF EXISTS leitura_total ON analytics.%I', tabela);
        EXECUTE format('CREATE POLICY leitura_total ON analytics.%I FOR SELECT TO dashboard_reader, etl_reverso USING (true)', tabela);
        EXECUTE format('DROP POLICY IF EXISTS por_curso ON analytics.%I', tabela);
        EXECUTE format($p$CREATE POLICY por_curso ON analytics.%I FOR SELECT TO coordenador
                          USING (curso_codigo IN (SELECT a.curso_codigo FROM operations.acesso_curso a
                                                  WHERE a.usuario = current_user))$p$, tabela);
        EXECUTE format('GRANT SELECT ON analytics.%I TO dashboard_reader, etl_reverso, coordenador', tabela);
    END LOOP;
    IF to_regclass('analytics.metricas_definicoes') IS NOT NULL THEN
        GRANT SELECT ON analytics.metricas_definicoes TO dashboard_reader, etl_reverso, coordenador;
    END IF;
    IF to_regclass('analytics.metricas_freshness') IS NOT NULL THEN
        GRANT SELECT ON analytics.metricas_freshness TO dashboard_reader, etl_reverso;
    END IF;
    IF to_regclass('analytics.dim_curso') IS NOT NULL THEN
        GRANT SELECT ON analytics.dim_curso, analytics.dim_semestre, analytics.dim_disciplina
            TO dashboard_reader, etl_reverso, coordenador;
    END IF;
END;
$$;

COMMENT ON FUNCTION operations.aplicar_acesso_analytics() IS
    'Reaplica RLS e grants nas tabelas de consumo, que o dbt recria a cada execução';

SELECT operations.aplicar_acesso_analytics();
