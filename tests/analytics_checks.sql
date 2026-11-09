\set ON_ERROR_STOP on
\set QUIET on
\pset footer off

CREATE TEMP TABLE resultado (teste TEXT, ok BOOLEAN, detalhe TEXT);

INSERT INTO resultado
SELECT 'fato analítico com linhas', count(*) > 0, count(*)::text
FROM analytics.fct_reservas;

INSERT INTO resultado
SELECT 'unicidade da granularidade turma-curso', count(*) = 0, count(*)::text
FROM (
  SELECT turma_id, curso_id, count(*) n
  FROM analytics.fct_reservas
  GROUP BY turma_id, curso_id
  HAVING count(*) > 1
) duplicadas;

INSERT INTO resultado
SELECT 'freshness registrada', count(*) > 0, coalesce(max(freshness_at)::text, 'nula')
FROM analytics.mart_observatorio;

INSERT INTO resultado
SELECT 'ETL reverso populado', count(*) > 0, count(*)::text
FROM operations.alertas_reserva;

SELECT teste, CASE WHEN ok THEN 'ok' ELSE 'FALHOU' END status, detalhe
FROM resultado ORDER BY ok, teste;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM resultado WHERE NOT ok) THEN
    RAISE EXCEPTION 'testes analíticos falharam';
  END IF;
END $$;
