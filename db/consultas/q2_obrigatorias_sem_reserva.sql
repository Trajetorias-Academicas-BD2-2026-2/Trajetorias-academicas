-- Obrigatórias do currículo de referência sem NENHUMA reserva para o curso no
-- recorte. Não significa que a disciplina não foi ofertada: a página do curso
-- só lista turmas que reservam vagas para ele.
SELECT c.codigo AS curso, cr.codigo AS curriculo, d.codigo AS disciplina, d.nome, cc.grupo,
       (d.unidade_id IS NULL) AS de_outra_unidade
FROM curriculo_referencia cr
JOIN curso c                 ON c.id = cr.curso_id
JOIN curriculo_componente cc ON cc.curriculo_id = cr.id AND cc.natureza = 'OBRIGATORIA'
JOIN disciplina d            ON d.id = cc.disciplina_id
WHERE NOT EXISTS (
    SELECT 1 FROM reserva_vaga rv JOIN turma t ON t.id = rv.turma_id
    WHERE rv.curso_id = cr.curso_id AND t.disciplina_id = cc.disciplina_id
)
ORDER BY c.codigo, cc.grupo, d.codigo;
