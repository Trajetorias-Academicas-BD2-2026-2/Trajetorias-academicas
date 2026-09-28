-- Ocupação média por disciplina no diurno e no noturno.
SELECT d.codigo,
       round(avg(ot.vagas_ocupadas::numeric / nullif(ot.vagas_ofertadas, 0))
             FILTER (WHERE ot.turno = 'DIURNO'), 2)  AS ocupacao_diurno,
       round(avg(ot.vagas_ocupadas::numeric / nullif(ot.vagas_ofertadas, 0))
             FILTER (WHERE ot.turno = 'NOTURNO'), 2) AS ocupacao_noturno
FROM oferta_turma ot
JOIN disciplina d ON d.id = ot.disciplina_id
WHERE ot.turno IN ('DIURNO', 'NOTURNO')
GROUP BY d.codigo
ORDER BY d.codigo;
