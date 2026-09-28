-- Pergunta de gestão: entre 2022.1 e 2026.1, quais disciplinas obrigatórias
-- dos cursos da FCTE mais ficaram lotadas, por turno?
-- Lotada = vagas_ocupadas >= vagas_ofertadas (com oferta > 0).
SELECT c.codigo                                   AS curso,
       d.codigo                                   AS disciplina,
       d.nome,
       ot.turno,
       count(*)                                   AS turmas,
       count(*) FILTER (WHERE ot.vagas_ofertadas > 0
                          AND ot.vagas_ocupadas >= ot.vagas_ofertadas) AS turmas_lotadas,
       round(sum(ot.vagas_ocupadas)::numeric / nullif(sum(ot.vagas_ofertadas), 0), 2) AS ocupacao_media,
       (SELECT count(*) FROM pre_requisito pr WHERE pr.pre_requisito_id = d.id) AS disciplinas_que_trava
FROM oferta_turma ot
JOIN disciplina d        ON d.id = ot.disciplina_id
JOIN curso_disciplina cd ON cd.disciplina_id = d.id AND cd.obrigatoria
JOIN curso c             ON c.id = cd.curso_id
WHERE (ot.ano, ot.periodo) BETWEEN (2022, 1) AND (2026, 1)
  AND ot.turno IN ('DIURNO', 'NOTURNO')
GROUP BY c.codigo, d.id, d.codigo, d.nome, ot.turno
ORDER BY turmas_lotadas DESC, ocupacao_media DESC NULLS LAST
LIMIT 30;
