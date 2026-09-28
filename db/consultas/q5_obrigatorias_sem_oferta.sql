-- Disciplinas obrigatórias de cada curso sem nenhuma turma no último semestre carregado.
WITH ultimo AS (
    SELECT ano, periodo FROM oferta_turma ORDER BY ano DESC, periodo DESC LIMIT 1
)
SELECT c.codigo AS curso, d.codigo AS disciplina, d.nome
FROM curso_disciplina cd
JOIN curso c      ON c.id = cd.curso_id
JOIN disciplina d ON d.id = cd.disciplina_id
CROSS JOIN ultimo u
WHERE cd.obrigatoria
  AND NOT EXISTS (
      SELECT 1 FROM oferta_turma ot
      WHERE ot.disciplina_id = cd.disciplina_id AND ot.ano = u.ano AND ot.periodo = u.periodo
  )
ORDER BY c.codigo, d.codigo;
