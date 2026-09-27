-- Rodar após a carga: psql -h localhost -U g2 -d ofertas_unb -f tests/sanity_checks.sql
-- Cada bloco deve retornar 0 linhas (ou uma contagem > 0, conforme indicado).
-- Uma linha em qualquer um dos SELECTs "deve retornar 0 linhas" indica um problema de carga.

-- 1) Volume mínimo esperado (ajustar o limiar conforme o escopo real carregado)
SELECT 'oferta_turma abaixo do esperado' AS problema, count(*) AS total
FROM oferta_turma
HAVING count(*) < 50;

-- 2) Oferta de turma sem disciplina correspondente (não deve acontecer, é FK)
SELECT 'oferta sem disciplina' AS problema, ot.id
FROM oferta_turma ot
LEFT JOIN disciplina d ON d.id = ot.disciplina_id
WHERE d.id IS NULL;

-- 3) Pré-requisito apontando para disciplina inexistente
SELECT 'pre_requisito orfao' AS problema, pr.disciplina_id, pr.pre_requisito_id
FROM pre_requisito pr
LEFT JOIN disciplina d1 ON d1.id = pr.disciplina_id
LEFT JOIN disciplina d2 ON d2.id = pr.pre_requisito_id
WHERE d1.id IS NULL OR d2.id IS NULL;

-- 4) Ano fora do intervalo plausível para este projeto
SELECT 'ano implausivel' AS problema, ano, count(*)
FROM oferta_turma
WHERE ano NOT BETWEEN 2020 AND 2027
GROUP BY ano;

-- 5) Vagas ocupadas muito acima do ofertado (sinal de erro de parsing)
SELECT 'ocupacao implausivel' AS problema, id, vagas_ofertadas, vagas_ocupadas
FROM oferta_turma
WHERE vagas_ocupadas > vagas_ofertadas * 1.5;

-- 6) Toda oferta_turma deve ter fonte e carga_id preenchidos (linhagem)
SELECT 'sem linhagem' AS problema, id
FROM oferta_turma
WHERE fonte IS NULL OR carga_id IS NULL;
