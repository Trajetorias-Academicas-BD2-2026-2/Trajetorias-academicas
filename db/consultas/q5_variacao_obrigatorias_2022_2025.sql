-- Variação das vagas reservadas em cada obrigatória, entre 2022 e 2025
-- (anos completos: dois semestres cada).
WITH obrigatoria AS (
    SELECT cr.curso_id, cc.disciplina_id
    FROM curriculo_referencia cr
    JOIN curriculo_componente cc ON cc.curriculo_id = cr.id
    WHERE cc.natureza = 'OBRIGATORIA'
)
SELECT c.codigo AS curso, d.codigo AS disciplina, d.nome,
       coalesce(sum(rv.vagas_reservadas) FILTER (WHERE t.ano = 2022), 0) AS vagas_2022,
       coalesce(sum(rv.vagas_reservadas) FILTER (WHERE t.ano = 2025), 0) AS vagas_2025,
       coalesce(sum(rv.vagas_reservadas) FILTER (WHERE t.ano = 2025), 0)
     - coalesce(sum(rv.vagas_reservadas) FILTER (WHERE t.ano = 2022), 0) AS variacao
FROM reserva_vaga rv
JOIN turma t       ON t.id = rv.turma_id
JOIN obrigatoria o ON o.curso_id = rv.curso_id AND o.disciplina_id = t.disciplina_id
JOIN curso c       ON c.id = rv.curso_id
JOIN disciplina d  ON d.id = t.disciplina_id
GROUP BY c.codigo, d.codigo, d.nome
ORDER BY variacao, c.codigo, d.codigo;
