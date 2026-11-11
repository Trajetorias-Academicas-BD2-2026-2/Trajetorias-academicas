-- Disciplinas mais parecidas com uma disciplina, pelo nome, no modelo ativo.
-- Uso: docker compose exec -T db psql -U g2 -d ofertas_unb -v codigo=FGA0060 \
--        < ml/consultas/consulta_vizinhos.sql
-- Fica fora de db/consultas/ porque o loader executa todo q*.sql daquela pasta.
-- Com pgvector >= 0.8, troque o ef_search por: SET hnsw.iterative_scan = relaxed_order;
SET hnsw.ef_search = 200;

WITH alvo AS (
  SELECT vetor FROM ml.v_embedding_atual
  WHERE entidade = 'componente' AND chave_origem = :'codigo'
)
SELECT v.chave_origem AS codigo,
       v.texto AS nome,
       round((v.vetor <=> alvo.vetor)::numeric, 3) AS distancia
FROM ml.v_embedding_atual v, alvo
WHERE v.entidade = 'componente'
  AND v.chave_origem <> :'codigo'
ORDER BY v.vetor <=> alvo.vetor
LIMIT 10;
