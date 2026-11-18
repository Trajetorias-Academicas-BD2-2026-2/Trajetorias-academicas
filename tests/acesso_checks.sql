-- Controle de acesso da E4: privilégio mínimo com recorte de LINHA e de COLUNA.
--   docker compose --profile test run --rm --no-deps acesso-tests
-- Cada verificação troca de papel (SET ROLE), tenta ler ou escrever, volta ao
-- papel do dono e registra o resultado. Termina com erro se alguma falhar.

\set ON_ERROR_STOP on
\set QUIET on
\pset footer off

CREATE TEMP TABLE resultado (papel TEXT, verificacao TEXT, ok BOOLEAN, detalhe TEXT);
GRANT INSERT ON resultado TO PUBLIC;

-- recorte de LINHA (RLS): cada coordenador só vê o próprio curso
DO $$
DECLARE cursos TEXT; linhas INT; esperado INT;
BEGIN
    SELECT count(*) INTO esperado FROM analytics.fct_reservas WHERE curso_codigo = 'FGA_SOFT';
    SET ROLE coord_soft;
    SELECT string_agg(DISTINCT curso_codigo, ','), count(*) INTO cursos, linhas FROM analytics.fct_reservas;
    RESET ROLE;
    INSERT INTO resultado VALUES ('coord_soft', 'linha: fct_reservas só de FGA_SOFT', cursos = 'FGA_SOFT' AND linhas = esperado,
        format('vê %s linhas de %s (esperado %s)', linhas, cursos, esperado));

    SET ROLE coord_soft;
    SELECT string_agg(DISTINCT curso_codigo, ','), count(*) INTO cursos, linhas FROM analytics.metricas_oficiais;
    RESET ROLE;
    INSERT INTO resultado VALUES ('coord_soft', 'linha: métricas oficiais só de FGA_SOFT', cursos = 'FGA_SOFT', format('%s valores de %s', linhas, cursos));

    SET ROLE coord_elet;
    SELECT string_agg(DISTINCT curso_codigo, ','), count(*) INTO cursos, linhas FROM analytics.mart_observatorio;
    RESET ROLE;
    INSERT INTO resultado VALUES ('coord_elet', 'linha: mart_observatorio só de FGA_ELET', cursos = 'FGA_ELET' AND linhas = 9,
        format('%s linhas de %s', linhas, cursos));
END $$;

-- o painel vê todos os cursos, mas nada do OLTP
DO $$
DECLARE n INT; bloqueado BOOLEAN := false;
BEGIN
    SET ROLE painel;
    SELECT count(DISTINCT curso_codigo) INTO n FROM analytics.mart_observatorio;
    BEGIN
        PERFORM 1 FROM public.turma LIMIT 1;
    EXCEPTION WHEN insufficient_privilege THEN bloqueado := true;
    END;
    RESET ROLE;
    INSERT INTO resultado VALUES ('painel', 'lê a camada de consumo inteira', n = 5, format('%s cursos', n));
    INSERT INTO resultado VALUES ('painel', 'não lê o OLTP (public.turma)', bloqueado, CASE WHEN bloqueado THEN 'permission denied' ELSE 'LEU' END);
END $$;

-- coordenador também não lê o OLTP
DO $$
DECLARE bloqueado BOOLEAN := false;
BEGIN
    SET ROLE coord_soft;
    BEGIN
        PERFORM 1 FROM public.reserva_vaga LIMIT 1;
    EXCEPTION WHEN insufficient_privilege THEN bloqueado := true;
    END;
    RESET ROLE;
    INSERT INTO resultado VALUES ('coord_soft', 'não lê o OLTP (public.reserva_vaga)', bloqueado, CASE WHEN bloqueado THEN 'permission denied' ELSE 'LEU' END);
END $$;

-- recorte de COLUNA: o auditor conta docentes por id, mas não lê o nome
DO $$
DECLARE n INT; bloqueado BOOLEAN := false;
BEGIN
    SET ROLE auditor_lgpd;
    SELECT count(id) INTO n FROM public.docente;
    BEGIN
        PERFORM nome FROM public.docente LIMIT 1;
    EXCEPTION WHEN insufficient_privilege THEN bloqueado := true;
    END;
    RESET ROLE;
    INSERT INTO resultado VALUES ('auditor_lgpd', 'coluna: lê docente.id', n > 0, format('%s docentes', n));
    INSERT INTO resultado VALUES ('auditor_lgpd', 'coluna: NÃO lê docente.nome (dado pessoal)', bloqueado, CASE WHEN bloqueado THEN 'permission denied for column' ELSE 'LEU' END);
END $$;

-- o ETL reverso lê métricas e escreve só a fila de envio
DO $$
DECLARE bloqueado BOOLEAN := false; n INT;
BEGIN
    SET ROLE etl_reverso;
    SELECT count(*) INTO n FROM analytics.metricas_oficiais;
    BEGIN
        DELETE FROM analytics.mart_observatorio;
    EXCEPTION WHEN insufficient_privilege THEN bloqueado := true;
    END;
    RESET ROLE;
    INSERT INTO resultado VALUES ('etl_reverso', 'lê as métricas oficiais', n > 0, format('%s valores', n));
    INSERT INTO resultado VALUES ('etl_reverso', 'não altera a camada analítica', bloqueado, CASE WHEN bloqueado THEN 'permission denied' ELSE 'APAGOU' END);
    INSERT INTO resultado VALUES ('etl_reverso', 'escreve na fila de envio',
        has_table_privilege('etl_reverso', 'operations.envio_pauta', 'UPDATE'), 'UPDATE em operations.envio_pauta');
END $$;

-- o RLS sobrevive ao dbt, que recria as tabelas a cada execução
INSERT INTO resultado
SELECT 'dbt', 'RLS ativo depois do build: ' || c.relname, c.relrowsecurity AND count(p.polname) = 2,
       count(p.polname) || ' políticas'
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'analytics'
LEFT JOIN pg_policy p ON p.polrelid = c.oid
WHERE c.relname IN ('fct_reservas', 'mart_observatorio', 'mart_disciplina_semestre', 'mart_cobertura_curriculo', 'metricas_oficiais')
GROUP BY c.relname, c.relrowsecurity;

SELECT papel, verificacao, CASE WHEN ok THEN 'ok' ELSE 'FALHOU' END AS status, detalhe
FROM resultado ORDER BY ok, papel, verificacao;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM resultado WHERE NOT ok) THEN
        RAISE EXCEPTION 'controle de acesso falhou';
    END IF;
    RAISE NOTICE 'Controle de acesso: todas as verificações passaram.';
END $$;
