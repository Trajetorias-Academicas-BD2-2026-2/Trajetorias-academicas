-- Testes de dados pós-carga.
--   docker compose run --rm tests
-- (ou: psql -v ON_ERROR_STOP=1 -h localhost -U g2 -d ofertas_unb -f tests/sanity_checks.sql)
--
-- Cada teste grava uma linha em `resultado`; no fim a tabela é impressa e,
-- se algum teste falhou, o script termina com erro (exit != 0).
-- Os limiares vêm do lote coleta_publica_2026-09-28 (docs/carga-medida.md):
-- 733 turmas, 1.776 reservas, 71 a 92 turmas por semestre. Ajuste-os quando
-- o lote mudar, com o motivo no diário, nunca para "fazer passar".

\set ON_ERROR_STOP on
\set QUIET on
\pset footer off

CREATE TEMP TABLE resultado (grupo TEXT, teste TEXT, ok BOOLEAN, detalhe TEXT);

-- ============ Esquema e linhagem ============
INSERT INTO resultado
SELECT 'esquema', 'migrações V001 a V005 aplicadas', count(*) = 5, count(*) || ' registradas'
FROM schema_migrations
WHERE versao IN ('V001__schema_base', 'V002__correcoes_pos_e1', 'V003__reservas_por_curso',
                 'V004__calendario_academico', 'V005__curriculo_referencia_fixo');

INSERT INTO resultado
SELECT 'esquema', 'turmas e reservas de um único lote', count(DISTINCT lote) = 1,
       coalesce(string_agg(DISTINCT lote, ', '), 'nenhum')
FROM (SELECT lote FROM turma UNION ALL SELECT lote FROM reserva_vaga) l;

INSERT INTO resultado
SELECT 'esquema', 'coletado_em não é posterior a ingerido_em', count(*) = 0, count(*) || ' linhas'
FROM reserva_vaga WHERE coletado_em > ingerido_em + interval '1 minute';

INSERT INTO resultado
SELECT 'esquema', 'triggers insert-only ativos (turma, turma_docente, reserva_vaga)', count(*) = 6,
       count(*) || ' triggers'
FROM pg_trigger tg
JOIN pg_proc pr ON pr.oid = tg.tgfoid AND pr.proname = 'bloqueia_alteracao'
WHERE tg.tgrelid IN ('turma'::regclass, 'turma_docente'::regclass, 'reserva_vaga'::regclass)
  AND tg.tgenabled <> 'D';

-- ============ Volume ============
INSERT INTO resultado
SELECT 'volume', 'ao menos 600 turmas', count(*) >= 600, count(*) || ' turmas' FROM turma;

INSERT INTO resultado
SELECT 'volume', 'ao menos 1500 reservas', count(*) >= 1500, count(*) || ' reservas' FROM reserva_vaga;

INSERT INTO resultado
SELECT 'volume', 'ao menos 8 semestres consecutivos (4 anos completos)',
       count(*) >= 8 AND count(*) = (max(ano * 2 + periodo) - min(ano * 2 + periodo) + 1),
       count(*) || ' semestres, ' || min(ano) || ' a ' || max(ano)
FROM (SELECT DISTINCT ano, periodo FROM turma) s;

INSERT INTO resultado
SELECT 'volume', 'os 5 cursos têm reservas em todos os semestres', count(*) = 0,
       coalesce(string_agg(codigo || ' ' || ano || '.' || periodo, ', '), 'todos ok')
FROM curso c
CROSS JOIN (SELECT DISTINCT ano, periodo FROM turma) s
WHERE NOT EXISTS (
    SELECT 1 FROM reserva_vaga rv JOIN turma t ON t.id = rv.turma_id
    WHERE rv.curso_id = c.id AND t.ano = s.ano AND t.periodo = s.periodo
);

-- ============ Currículo ============
INSERT INTO resultado
SELECT 'currículo', 'todo curso tem currículo de referência', count(*) = 0,
       coalesce(string_agg(c.codigo, ', '), 'todos ok')
FROM curso c WHERE NOT EXISTS (SELECT 1 FROM curriculo_referencia cr WHERE cr.curso_id = c.id);

-- A referência é fixa em 2026.1 (V005): nenhuma versão com vigência posterior
-- pode aparecer, mesmo que o banco tenha semestres mais novos.
INSERT INTO resultado
SELECT 'currículo', 'currículo de referência fixo em 2026.1', count(*) = 0,
       coalesce(string_agg(codigo || ' (' || inicio_vigencia_ano || '.' || inicio_vigencia_periodo || ')', ', '), 'todos ok')
FROM curriculo_referencia
WHERE (inicio_vigencia_ano, inicio_vigencia_periodo) > (2026, 1);

INSERT INTO resultado
SELECT 'currículo', 'view de referência não depende da tabela turma', count(*) = 0,
       coalesce(string_agg(DISTINCT dep.relname, ', '), 'independente')
FROM pg_depend d
JOIN pg_rewrite r   ON r.oid = d.objid
JOIN pg_class v     ON v.oid = r.ev_class AND v.relname = 'curriculo_referencia'
JOIN pg_class dep   ON dep.oid = d.refobjid AND dep.relname = 'turma';

INSERT INTO resultado
SELECT 'currículo', 'currículo de referência com ao menos 30 obrigatórias', count(*) = 0,
       coalesce(string_agg(codigo || '=' || n, ', '), 'todos ok')
FROM (
    SELECT cr.codigo, count(*) FILTER (WHERE cc.natureza = 'OBRIGATORIA') AS n
    FROM curriculo_referencia cr JOIN curriculo_componente cc ON cc.curriculo_id = cr.id
    GROUP BY cr.codigo
) x WHERE n < 30;

-- ============ Distribuição ============
INSERT INTO resultado
SELECT 'distribuição', 'nenhum semestre com menos de 50% da mediana de turmas', count(*) = 0,
       coalesce(string_agg(ano || '.' || periodo || '=' || n, ', '), 'todos ok')
FROM (SELECT ano, periodo, count(*) AS n FROM turma GROUP BY ano, periodo) s
WHERE n < 0.5 * (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY n)
                 FROM (SELECT count(*) AS n FROM turma GROUP BY ano, periodo) t);

INSERT INTO resultado
SELECT 'distribuição', 'nenhum par de semestres com turmas idênticas', count(*) = 0, count(*) || ' repetições'
FROM (
    SELECT h FROM (
        SELECT md5(string_agg(disciplina_id || ':' || codigo_turma || ':' || coalesce(horario, ''),
                              ',' ORDER BY disciplina_id, codigo_turma)) AS h
        FROM turma GROUP BY ano, periodo
    ) s GROUP BY h HAVING count(*) > 1
) repetidos;

-- Uma reserva maior que 200 vagas (o máximo observado no lote) indica erro de leitura.
INSERT INTO resultado
SELECT 'distribuição', 'nenhuma reserva acima de 200 vagas', count(*) FILTER (WHERE vagas_reservadas > 200) = 0,
       'máximo ' || coalesce(max(vagas_reservadas), 0)
FROM reserva_vaga;

-- ============ Dado faltante ============
INSERT INTO resultado
SELECT 'faltante', 'turmas SEM_HORARIO < 5%',
       coalesce(avg((turno = 'SEM_HORARIO')::int), 0) < 0.05,
       round(100 * coalesce(avg((turno = 'SEM_HORARIO')::int), 0), 1) || '%'
FROM turma;

INSERT INTO resultado
SELECT 'faltante', 'turmas sem docente < 5%',
       coalesce(avg((NOT EXISTS (SELECT 1 FROM turma_docente td WHERE td.turma_id = t.id))::int), 0) < 0.05,
       round(100 * coalesce(avg((NOT EXISTS (SELECT 1 FROM turma_docente td WHERE td.turma_id = t.id))::int), 0), 1) || '%'
FROM turma t;

-- Informativo (sempre ok): a cobertura precisa aparecer, não ser escondida.
INSERT INTO resultado
SELECT 'faltante', 'cobertura de pré-requisitos (informativo)', TRUE,
       count(*) FILTER (WHERE pre_requisito_coletado) || ' de ' || count(*) FILTER (WHERE unidade_id IS NOT NULL)
       || ' componentes da FCTE'
FROM disciplina;

INSERT INTO resultado
SELECT 'faltante', 'disciplinas de outras unidades sem carga horária (informativo)', TRUE,
       count(*) FILTER (WHERE carga_horaria IS NULL) || ' de ' || count(*)
FROM disciplina WHERE unidade_id IS NULL;

-- ============ Histórico ============
INSERT INTO resultado
SELECT 'histórico', 'toda turma tem semestre no calendário acadêmico', count(*) = 0,
       coalesce(string_agg(DISTINCT t.ano || '.' || t.periodo, ', '), 'todas ok')
FROM turma t
LEFT JOIN semestre_letivo s ON s.ano = t.ano AND s.periodo = t.periodo
WHERE s.ano IS NULL;

INSERT INTO resultado
SELECT 'histórico', 'toda turma coletada depois do encerramento oficial do semestre', count(*) = 0,
       coalesce(string_agg(DISTINCT t.ano || '.' || t.periodo, ', '), 'todas ok')
FROM turma t
JOIN semestre_letivo s ON s.ano = t.ano AND s.periodo = t.periodo
WHERE t.coletado_em::date <= s.encerramento;

INSERT INTO resultado
SELECT 'histórico', 'semestres do calendário com fonte', count(*) FILTER (WHERE fonte_url NOT LIKE 'https://%') = 0,
       count(*) || ' semestres'
FROM semestre_letivo;

INSERT INTO resultado
SELECT 'histórico', 'trigger de semestre encerrado ativo em turma', count(*) = 1, count(*) || ' trigger'
FROM pg_trigger
WHERE tgrelid = 'turma'::regclass AND tgname = 'turma_exige_semestre_encerrado' AND tgenabled <> 'D';

-- ============ Resultado ============
SELECT grupo, teste, CASE WHEN ok THEN 'ok' ELSE 'FALHOU' END AS status, detalhe
FROM resultado ORDER BY ok, grupo, teste;

DO $$
DECLARE falhas INT;
BEGIN
    SELECT count(*) INTO falhas FROM resultado WHERE NOT ok;
    IF falhas > 0 THEN
        RAISE EXCEPTION '% teste(s) de dados falharam', falhas;
    END IF;
    RAISE NOTICE 'Todos os testes de dados passaram.';
END $$;
