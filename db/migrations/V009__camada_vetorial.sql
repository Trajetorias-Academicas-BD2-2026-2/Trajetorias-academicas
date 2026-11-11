-- Camada vetorial para treinos de ML (plano da camada vetorial, nov/2026).
-- O migrate.sh já envolve cada migração numa transação (psql -1): sem BEGIN/COMMIT aqui.
-- Requer o serviço db com pgvector (imagem pgvector/pgvector:pg16).
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS ml;

-- Modelo de embedding usado em cada vetor (permite trocar de modelo sem perder histórico).
CREATE TABLE IF NOT EXISTS ml.modelo_embedding (
  id smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nome text NOT NULL,                       -- ex.: intfloat/multilingual-e5-small
  revisao text NOT NULL,                    -- commit fixado no Hugging Face
  dimensao integer NOT NULL CHECK (dimensao > 0),
  prefixo text NOT NULL DEFAULT 'query: ',
  ativo boolean NOT NULL DEFAULT false,
  criado_em timestamptz NOT NULL DEFAULT now(),
  UNIQUE (nome, revisao)
);
CREATE UNIQUE INDEX IF NOT EXISTS modelo_um_ativo
  ON ml.modelo_embedding (ativo) WHERE ativo;

-- Texto que vira vetor. Uma linha por versão do texto; só uma versão ativa por item.
CREATE TABLE IF NOT EXISTS ml.item_texto (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entidade text NOT NULL CHECK (entidade IN ('componente', 'curso_unb', 'curso_inep')),
  chave_origem text NOT NULL,               -- id_componente, id_curso ou codigo_ies:codigo_curso
  texto text NOT NULL CHECK (length(trim(texto)) > 0),   -- só o conteúdo semântico (ex.: nome)
  texto_sha256 char(64) NOT NULL,
  atributos jsonb NOT NULL DEFAULT '{}'::jsonb,          -- filtros fora do texto: unidade, campus, grau, turno
  fonte text NOT NULL,                      -- recurso de origem e data da coleta
  ativo boolean NOT NULL DEFAULT true,
  carregado_em timestamptz NOT NULL DEFAULT now(),
  UNIQUE (entidade, chave_origem, texto_sha256),
  UNIQUE (id, entidade)                     -- alvo da FK composta abaixo
);
CREATE UNIQUE INDEX IF NOT EXISTS item_um_ativo
  ON ml.item_texto (entidade, chave_origem) WHERE ativo;

-- Vetores. A entidade é repetida para permitir índices parciais por tipo de item;
-- a FK composta impede divergência com ml.item_texto.
CREATE TABLE IF NOT EXISTS ml.embedding (
  item_id bigint NOT NULL,
  entidade text NOT NULL,
  modelo_id smallint NOT NULL REFERENCES ml.modelo_embedding,
  vetor vector(384) NOT NULL,               -- trocar de dimensão = nova coluna ou tabela
  gerado_em timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (item_id, modelo_id),
  FOREIGN KEY (item_id, entidade) REFERENCES ml.item_texto (id, entidade) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS embedding_curso_inep_hnsw
  ON ml.embedding USING hnsw (vetor vector_cosine_ops) WHERE entidade = 'curso_inep';
CREATE INDEX IF NOT EXISTS embedding_componente_hnsw
  ON ml.embedding USING hnsw (vetor vector_cosine_ops) WHERE entidade = 'componente';

-- Vetores do modelo ativo para os textos ativos: ponto de entrada de consultas e exportações.
CREATE OR REPLACE VIEW ml.v_embedding_atual AS
SELECT i.entidade, i.chave_origem, i.texto, i.atributos, e.vetor, m.nome AS modelo, m.revisao
FROM ml.embedding e
JOIN ml.item_texto i ON i.id = e.item_id AND i.ativo
JOIN ml.modelo_embedding m ON m.id = e.modelo_id AND m.ativo;

-- Leitura para treino; o papel do dashboard não recebe acesso a este schema.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ml_reader') THEN
    CREATE ROLE ml_reader NOLOGIN;
  END IF;
END $$;
GRANT USAGE ON SCHEMA ml TO ml_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA ml TO ml_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA ml
    GRANT SELECT ON TABLES TO ml_reader;
