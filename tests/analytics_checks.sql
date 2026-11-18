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
SELECT 'ETL reverso: itens entregues à Pauta', count(*) FILTER (WHERE status = 'enviado') > 0
       AND count(*) FILTER (WHERE status = 'pendente') = 0,
       count(*) FILTER (WHERE status = 'enviado') || ' enviados, ' || count(*) FILTER (WHERE status = 'pendente') || ' pendentes'
FROM operations.envio_pauta;

INSERT INTO resultado
SELECT 'camada semântica: métricas oficiais gravadas', count(DISTINCT metrica) >= 8, count(DISTINCT metrica) || ' métricas, ' || count(*) || ' valores'
FROM analytics.metricas_oficiais;

INSERT INTO resultado
SELECT 'SLA: mart até 24 h atrás da origem', bool_and(atraso_horas <= sla_horas), max(atraso_horas)::text || ' h'
FROM analytics.metricas_freshness;

INSERT INTO resultado
SELECT 'SCD: uma versão corrente por disciplina', count(*) = 0, count(*)::text || ' disciplinas com problema'
FROM (
  SELECT disciplina_id FROM analytics.dim_disciplina
  GROUP BY disciplina_id HAVING count(*) FILTER (WHERE is_current) <> 1
) d;

INSERT INTO resultado
SELECT 'integridade: fato -> dim_semestre', count(*) = 0, count(*)::text || ' órfãs'
FROM analytics.fct_reservas f
LEFT JOIN analytics.dim_semestre s USING (semestre_key)
WHERE s.semestre_key IS NULL;

SELECT teste, CASE WHEN ok THEN 'ok' ELSE 'FALHOU' END status, detalhe
FROM resultado ORDER BY ok, teste;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM resultado WHERE NOT ok) THEN
    RAISE EXCEPTION 'testes analíticos falharam';
  END IF;
END $$;
