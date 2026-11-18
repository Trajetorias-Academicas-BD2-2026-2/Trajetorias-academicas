-- Evidência de otimização da E3: EXPLAIN (ANALYZE, BUFFERS) da consulta da
-- pergunta de gestão (q0) antes e depois da reescrita guiada pelo plano.
--   docker compose exec -T db psql -U g2 -d ofertas_unb -X -f - < db/consultas/q6_explain_reservas.sql
-- Saídas registradas em docs/evidencias/explain-antes.txt e explain-depois.txt.

\echo '=== ANTES: q0 original (CTE total agregado juntado antes do fato) ==='
EXPLAIN (ANALYZE, BUFFERS)
WITH obrigatoria AS (
    SELECT cr.curso_id, cr.codigo AS curriculo, cc.disciplina_id
    FROM curriculo_referencia cr
    JOIN curriculo_componente cc ON cc.curriculo_id = cr.id
    WHERE cc.natureza = 'OBRIGATORIA'
),
total AS (
    SELECT curso_id, curriculo, count(*) AS obrigatorias_no_curriculo
    FROM obrigatoria GROUP BY curso_id, curriculo
)
SELECT c.codigo                          AS curso,
       tot.curriculo                     AS curriculo_de_referencia,
       t.ano || '.' || t.periodo         AS semestre,
       sum(rv.vagas_reservadas)          AS vagas_reservadas,
       count(*)                          AS turmas_com_reserva,
       count(DISTINCT t.disciplina_id)   AS obrigatorias_com_reserva,
       tot.obrigatorias_no_curriculo
FROM reserva_vaga rv
JOIN turma t       ON t.id = rv.turma_id
JOIN curso c       ON c.id = rv.curso_id
JOIN obrigatoria o ON o.curso_id = rv.curso_id AND o.disciplina_id = t.disciplina_id
JOIN total tot     ON tot.curso_id = rv.curso_id
WHERE (t.ano, t.periodo) BETWEEN (2022, 1) AND (2026, 1)
GROUP BY c.codigo, tot.curriculo, t.ano, t.periodo, tot.obrigatorias_no_curriculo
ORDER BY c.codigo, t.ano, t.periodo;

\echo '=== DEPOIS: q0 atual (agrega primeiro, junta curso no fim) ==='
EXPLAIN (ANALYZE, BUFFERS)
WITH obrigatoria AS NOT MATERIALIZED (
    SELECT cr.curso_id, cr.codigo AS curriculo, cc.disciplina_id
    FROM curriculo_referencia cr
    JOIN curriculo_componente cc ON cc.curriculo_id = cr.id
    WHERE cc.natureza = 'OBRIGATORIA'
),
serie AS (
    SELECT rv.curso_id, o.curriculo, t.ano, t.periodo,
           sum(rv.vagas_reservadas)        AS vagas_reservadas,
           count(*)                        AS turmas_com_reserva,
           count(DISTINCT t.disciplina_id) AS obrigatorias_com_reserva
    FROM reserva_vaga rv
    JOIN turma t       ON t.id = rv.turma_id
    JOIN obrigatoria o ON o.curso_id = rv.curso_id AND o.disciplina_id = t.disciplina_id
    WHERE (t.ano, t.periodo) BETWEEN (2022, 1) AND (2026, 1)
    GROUP BY rv.curso_id, o.curriculo, t.ano, t.periodo
)
SELECT c.codigo AS curso, s.curriculo AS curriculo_de_referencia,
       s.ano || '.' || s.periodo AS semestre, s.vagas_reservadas, s.turmas_com_reserva,
       s.obrigatorias_com_reserva,
       (SELECT count(*) FROM obrigatoria o2 WHERE o2.curso_id = s.curso_id) AS obrigatorias_no_curriculo
FROM serie s JOIN curso c ON c.id = s.curso_id
ORDER BY c.codigo, s.ano, s.periodo;
