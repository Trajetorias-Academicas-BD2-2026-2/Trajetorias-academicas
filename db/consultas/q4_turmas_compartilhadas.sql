-- Turmas que reservam vagas para mais de um curso, por semestre.
SELECT t.ano, t.periodo,
       count(*)                                   AS turmas,
       count(*) FILTER (WHERE n_cursos > 1)       AS compartilhadas,
       round(avg(n_cursos), 2)                    AS cursos_por_turma
FROM (
    SELECT turma_id, count(*) AS n_cursos FROM reserva_vaga GROUP BY turma_id
) r
JOIN turma t ON t.id = r.turma_id
GROUP BY t.ano, t.periodo
ORDER BY t.ano, t.periodo;
