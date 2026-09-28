-- Disciplinas que mais aparecem como pré-requisito (as que mais "travam a grade").
SELECT d.codigo, d.nome, count(*) AS disciplinas_dependentes
FROM pre_requisito pr
JOIN disciplina d ON d.id = pr.pre_requisito_id
GROUP BY d.codigo, d.nome
ORDER BY disciplinas_dependentes DESC
LIMIT 20;
