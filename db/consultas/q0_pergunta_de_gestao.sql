-- Pergunta de gestão: como evoluíram, entre 2022.1 e 2026.1, as vagas
-- reservadas publicadas para cada curso da FCTE nas disciplinas obrigatórias
-- do currículo de referência selecionado para 2026.1?
--
-- Análise retrospectiva de um conjunto FIXO: as obrigatórias da versão em
-- vigor em 2026.1 (view curriculo_referencia) são seguidas por toda a série,
-- inclusive em semestres em que outra versão vigorava. Vagas reservadas NÃO
-- são oferta total nem ocupação.
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
