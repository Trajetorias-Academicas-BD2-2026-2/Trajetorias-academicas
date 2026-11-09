-- Evidência de desempenho da consulta principal da E3.
-- Execute antes e depois de aplicar os índices da origem:
-- EXPLAIN (ANALYZE, BUFFERS) <consulta q0>;
-- A consulta q0 é mantida separada para continuar legível na defesa.
EXPLAIN (ANALYZE, BUFFERS)
SELECT curso_codigo, semestre, sum(vagas_reservadas) AS vagas_reservadas
FROM analytics.fct_reservas
WHERE obrigatoria
GROUP BY curso_codigo, semestre
ORDER BY curso_codigo, semestre;
