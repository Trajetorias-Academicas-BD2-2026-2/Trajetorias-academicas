-- De onde vêm as vagas reservadas a cada curso: disciplinas da FCTE ou de
-- outras unidades (MAT, IFD...), por semestre.
SELECT c.codigo AS curso, t.ano, t.periodo,
       sum(rv.vagas_reservadas) FILTER (WHERE d.unidade_id IS NOT NULL) AS vagas_fcte,
       sum(rv.vagas_reservadas) FILTER (WHERE d.unidade_id IS NULL)     AS vagas_outras_unidades
FROM reserva_vaga rv
JOIN turma t      ON t.id = rv.turma_id
JOIN disciplina d ON d.id = t.disciplina_id
JOIN curso c      ON c.id = rv.curso_id
GROUP BY c.codigo, t.ano, t.periodo
ORDER BY c.codigo, t.ano, t.periodo;
