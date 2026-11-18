-- Pergunta de gestão: como evoluíram, entre 2022.1 e 2026.1, as vagas
-- reservadas publicadas para cada curso da FCTE nas disciplinas obrigatórias
-- do currículo de referência selecionado para 2026.1?
--
-- Análise retrospectiva de um conjunto FIXO: as obrigatórias da versão em
-- vigor em 2026.1 (view curriculo_referencia) são seguidas por toda a série,
-- inclusive em semestres em que outra versão vigorava. Vagas reservadas NÃO
-- são oferta total nem ocupação.
--
-- Versão otimizada a partir do plano (E3, docs/evidencias/explain-*.txt):
-- agrega primeiro e só depois junta com curso. A versão anterior juntava o
-- CTE agregado "total" antes do fato; sem estatística no CTE, o planner
-- estimava 5 linhas (eram 254) e escolhia 1.681 buscas por índice em
-- reserva_vaga (5.721 buffers). Agora: hash joins e 197 buffers.
-- O resultado é idêntico (conferido com diff das duas saídas).
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
