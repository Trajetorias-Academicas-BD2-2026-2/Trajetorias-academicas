-- Testes de dados pós-carga.
--   docker compose run --rm tests
-- (ou: psql -v ON_ERROR_STOP=1 -h localhost -U g2 -d ofertas_unb -f tests/sanity_checks.sql)
--
-- Cada teste grava uma linha em `resultado`; no fim a tabela é impressa e,
-- se algum teste falhou, o script termina com erro (exit != 0).
-- Os limiares de volume e distribuição estão comentados; ajuste-os aos
-- números de docs/carga-medida.md, nunca para "fazer passar".

\set ON_ERROR_STOP on
\set QUIET on
\pset footer off

CREATE TEMP TABLE resultado (grupo TEXT, teste TEXT, ok BOOLEAN, detalhe TEXT);

-- ============ Esquema e linhagem ============
INSERT INTO resultado
SELECT 'esquema', 'migrações V001 e V002 aplicadas', count(*) = 2, count(*) || ' registradas'
FROM schema_migrations WHERE versao IN ('V001__schema_base', 'V002__correcoes_pos_e1');

INSERT INTO resultado
SELECT 'esquema', 'toda oferta tem linhagem (fonte, carga_id, coletado_em)', count(*) = 0, count(*) || ' sem linhagem'
FROM oferta_turma WHERE fonte IS NULL OR carga_id IS NULL OR coletado_em IS NULL;

INSERT INTO resultado
SELECT 'esquema', 'fonte com valor conhecido', count(*) = 0, count(*) || ' com fonte desconhecida'
FROM oferta_turma WHERE fonte <> 'sigaa_turmas';

INSERT INTO resultado
SELECT 'esquema', 'coletado_em não é posterior a ingerido_em', count(*) = 0, count(*) || ' linhas'
FROM oferta_turma WHERE coletado_em > ingerido_em + interval '1 minute';

-- ============ Volume ============
-- Limiar: 4 anos da FCTE; ajuste ao volume medido.
INSERT INTO resultado
SELECT 'volume', 'oferta_turma com ao menos 1000 linhas', count(*) >= 1000, count(*) || ' linhas'
FROM oferta_turma;

INSERT INTO resultado
SELECT 'volume', 'ao menos 8 semestres (4 anos completos)', count(*) >= 8, count(*) || ' semestres'
FROM (SELECT DISTINCT ano, periodo FROM oferta_turma) s;

INSERT INTO resultado
SELECT 'volume', 'sem semestre faltando no meio da série',
       count(*) = (max(ano * 2 + periodo) - min(ano * 2 + periodo) + 1),
       count(*) || ' semestres entre ' || min(ano) || ' e ' || max(ano)
FROM (SELECT DISTINCT ano, periodo FROM oferta_turma) s;

INSERT INTO resultado
SELECT 'volume', 'os 5 cursos do Gama carregados', count(*) = 5, count(*) || ' cursos'
FROM curso;

INSERT INTO resultado
SELECT 'volume', 'todo curso tem ao menos 20 disciplinas obrigatórias', count(*) = 0,
       coalesce(string_agg(codigo || '=' || n, ', '), 'todos ok')
FROM (
    SELECT c.codigo, count(cd.disciplina_id) FILTER (WHERE cd.obrigatoria) AS n
    FROM curso c LEFT JOIN curso_disciplina cd ON cd.curso_id = c.id
    GROUP BY c.codigo
) x WHERE n < 20;

-- ============ Distribuição ============
-- Semestre com menos da metade da mediana indica raspagem parcial.
INSERT INTO resultado
SELECT 'distribuição', 'nenhum semestre com menos de 50% da mediana de turmas', count(*) = 0,
       coalesce(string_agg(ano || '.' || periodo || '=' || n, ', '), 'todos ok')
FROM (SELECT ano, periodo, count(*) AS n FROM oferta_turma GROUP BY ano, periodo) s
WHERE n < 0.5 * (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY n)
                 FROM (SELECT count(*) AS n FROM oferta_turma GROUP BY ano, periodo) t);

-- Semestres idênticos = filtro de ano/período ignorado na raspagem.
INSERT INTO resultado
SELECT 'distribuição', 'nenhum par de semestres com turmas idênticas', count(*) = 0, count(*) || ' repetições'
FROM (
    SELECT h FROM (
        SELECT md5(string_agg(disciplina_id || ':' || codigo_turma || ':' || vagas_ofertadas || ':' || vagas_ocupadas,
                              ',' ORDER BY disciplina_id, codigo_turma)) AS h
        FROM oferta_turma GROUP BY ano, periodo
    ) s GROUP BY h HAVING count(*) > 1
) repetidos;

INSERT INTO resultado
SELECT 'distribuição', 'turmas com 0 vagas ofertadas < 10%',
       coalesce(avg((vagas_ofertadas = 0)::int), 0) < 0.10,
       round(100 * coalesce(avg((vagas_ofertadas = 0)::int), 0), 1) || '%'
FROM oferta_turma;

-- Ocupação acima de 1,5x a oferta sugere colunas de vagas lidas trocadas.
INSERT INTO resultado
SELECT 'distribuição', 'ocupação > 1,5x a oferta em menos de 2% das turmas',
       coalesce(avg((vagas_ocupadas > 1.5 * vagas_ofertadas AND vagas_ofertadas > 0)::int), 0) < 0.02,
       round(100 * coalesce(avg((vagas_ocupadas > 1.5 * vagas_ofertadas AND vagas_ofertadas > 0)::int), 0), 1) || '%'
FROM oferta_turma;

INSERT INTO resultado
SELECT 'distribuição', 'há turnos DIURNO e NOTURNO na série', count(DISTINCT turno) FILTER (WHERE turno IN ('DIURNO', 'NOTURNO')) = 2,
       string_agg(DISTINCT turno, ', ')
FROM oferta_turma;

-- ============ Dado faltante ============
INSERT INTO resultado
SELECT 'faltante', 'turmas SEM_HORARIO < 20%',
       coalesce(avg((turno = 'SEM_HORARIO')::int), 0) < 0.20,
       round(100 * coalesce(avg((turno = 'SEM_HORARIO')::int), 0), 1) || '%'
FROM oferta_turma;

INSERT INTO resultado
SELECT 'faltante', 'turmas sem docente < 20%',
       coalesce(avg((docente_id IS NULL)::int), 0) < 0.20,
       round(100 * coalesce(avg((docente_id IS NULL)::int), 0), 1) || '%'
FROM oferta_turma;

INSERT INTO resultado
SELECT 'faltante', 'obrigatórias sem nenhuma turma em toda a série < 20%',
       coalesce(avg(sem_oferta::int), 0) < 0.20,
       round(100 * coalesce(avg(sem_oferta::int), 0), 1) || '%'
FROM (
    SELECT NOT EXISTS (SELECT 1 FROM oferta_turma ot WHERE ot.disciplina_id = cd.disciplina_id) AS sem_oferta
    FROM curso_disciplina cd WHERE cd.obrigatoria
) x;

-- ============ Histórico e reprocessamento ============
-- Mesma regra de loader/semestres.py: jan-fev -> (ano-1).2 aberto; mar-jul -> ano.1; ago-dez -> ano.2.
INSERT INTO resultado
SELECT 'histórico', 'nenhum semestre em andamento carregado', count(*) = 0,
       coalesce(string_agg(DISTINCT ano || '.' || periodo, ', '), 'nenhum')
FROM oferta_turma,
     LATERAL (SELECT CASE WHEN extract(month FROM now()) <= 2 THEN (extract(year FROM now())::int - 1) * 2 + 2
                          WHEN extract(month FROM now()) <= 7 THEN extract(year FROM now())::int * 2 + 1
                          ELSE extract(year FROM now())::int * 2 + 2 END AS corrente) c
WHERE ano * 2 + periodo >= c.corrente;

INSERT INTO resultado
SELECT 'histórico', 'trigger insert-only ativo em oferta_turma', count(*) = 2, count(*) || ' triggers'
FROM pg_trigger WHERE tgrelid = 'oferta_turma'::regclass AND NOT tgisinternal AND tgenabled <> 'D';

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
