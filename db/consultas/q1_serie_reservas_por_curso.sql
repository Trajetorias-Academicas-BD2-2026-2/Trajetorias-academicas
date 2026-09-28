-- Série de vagas reservadas a cada curso, por semestre (todas as disciplinas).
SELECT c.codigo AS curso, t.ano, t.periodo,
       count(*)                 AS turmas_com_reserva,
       sum(rv.vagas_reservadas) AS vagas_reservadas
FROM reserva_vaga rv
JOIN turma t ON t.id = rv.turma_id
JOIN curso c ON c.id = rv.curso_id
GROUP BY c.codigo, t.ano, t.periodo
ORDER BY c.codigo, t.ano, t.periodo;
