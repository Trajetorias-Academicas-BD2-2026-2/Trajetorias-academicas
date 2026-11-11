\set ON_ERROR_STOP on
\set QUIET on
\pset footer off

-- P13 da camada vetorial. Diferente de analytics_checks.sql, termina com erro
-- se alguma checagem falhar, para o run_pipeline.sh repetir ou parar.

CREATE TEMP TABLE resultado (teste TEXT, ok BOOLEAN, detalhe TEXT);

INSERT INTO resultado
SELECT 'um modelo de embedding ativo', count(*) = 1, count(*)::text
FROM ml.modelo_embedding
WHERE ativo;

INSERT INTO resultado
SELECT 'staging refletido em textos ativos', count(*) = 0, count(*)::text || ' sem versão ativa'
FROM analytics.ml_stg_texto s
LEFT JOIN ml.item_texto i
  ON i.entidade = s.entidade AND i.chave_origem = s.chave_origem
 AND i.texto_sha256 = s.texto_sha256 AND i.ativo
WHERE i.id IS NULL;

INSERT INTO resultado
SELECT 'textos ativos com vetor do modelo ativo', count(*) = 0, count(*)::text || ' sem vetor'
FROM ml.item_texto i
WHERE i.ativo
  AND NOT EXISTS (
    SELECT 1 FROM ml.embedding e
    JOIN ml.modelo_embedding m ON m.id = e.modelo_id AND m.ativo
    WHERE e.item_id = i.id);

INSERT INTO resultado
SELECT 'vetores com 384 dimensões e norma 1', count(*) = 0, count(*)::text || ' fora da regra'
FROM ml.embedding
WHERE vector_dims(vetor) <> 384 OR abs(vector_norm(vetor) - 1) > 0.001;

INSERT INTO resultado
SELECT 'disciplinas do fato com vetor',
       count(*) FILTER (WHERE v.chave_origem IS NULL) = 0,
       coalesce(round(100.0 * count(v.chave_origem) / nullif(count(*), 0), 1)::text, '0') || '% de '
         || count(*)::text
FROM (SELECT DISTINCT disciplina_codigo FROM analytics.fct_reservas) f
LEFT JOIN ml.v_embedding_atual v
  ON v.entidade = 'componente' AND v.chave_origem = f.disciplina_codigo;

SELECT teste, CASE WHEN ok THEN 'ok' ELSE 'FALHOU' END status, detalhe
FROM resultado ORDER BY ok, teste;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM resultado WHERE NOT ok) THEN
    RAISE EXCEPTION 'checagens da camada vetorial falharam (veja a tabela acima)';
  END IF;
END
$$;
