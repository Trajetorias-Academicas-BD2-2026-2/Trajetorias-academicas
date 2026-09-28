-- Série de ocupação de cada disciplina ao longo dos semestres.
SELECT d.codigo, ot.ano, ot.periodo,
       count(*) AS turmas,
       sum(ot.vagas_ofertadas) AS vagas_ofertadas,
       sum(ot.vagas_ocupadas)  AS vagas_ocupadas,
       round(sum(ot.vagas_ocupadas)::numeric / nullif(sum(ot.vagas_ofertadas), 0), 2) AS ocupacao
FROM oferta_turma ot
JOIN disciplina d ON d.id = ot.disciplina_id
GROUP BY d.codigo, ot.ano, ot.periodo
ORDER BY d.codigo, ot.ano, ot.periodo;
