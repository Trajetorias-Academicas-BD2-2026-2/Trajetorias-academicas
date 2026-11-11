"""P12 da camada vetorial: sincroniza textos e gera embeddings no pgvector.

Lê analytics.ml_stg_texto (P11, criado pelo dbt), grava as versões de texto em
ml.item_texto e vetoriza só os itens ativos que ainda não têm vetor no modelo
configurado. Reexecutar não duplica nem recalcula nada.

Uso no compose:  docker compose --profile ml run --rm ml
Uso local:       PGHOST=localhost python ml/gerar_embeddings.py

Variáveis: PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD (como no etl_reverso),
MODELO_DIR (cache do modelo; padrão ./modelos) e MODELO_REVISAO (commit do
Hugging Face; padrão fixado abaixo).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import psycopg
from huggingface_hub import hf_hub_download
from pgvector.psycopg import register_vector
from psycopg.types.json import Jsonb
from tokenizers import Tokenizer

MODELO = "intfloat/multilingual-e5-small"
REVISAO = os.getenv("MODELO_REVISAO", "614241f622f53c4eeff9890bdc4f31cfecc418b3")
DIMENSAO = 384
PREFIXO = "query: "  # recomendado pelo model card para features e clustering
ARQUIVOS_MODELO = ("onnx/model.onnx", "onnx/tokenizer.json")


def baixar_modelo(base: Path) -> Path:
    """Baixa (uma vez) os arquivos ONNX do commit fixado e devolve a pasta."""
    pasta = base / MODELO.replace("/", "--") / REVISAO
    for arquivo in ARQUIVOS_MODELO:
        if not (pasta / arquivo).exists():
            print(f"baixando {MODELO}@{REVISAO[:8]}: {arquivo}")
            hf_hub_download(MODELO, arquivo, revision=REVISAO, local_dir=pasta)
    return pasta


class Codificador:
    def __init__(self, pasta: Path):
        self.tokenizador = Tokenizer.from_file(str(pasta / "onnx" / "tokenizer.json"))
        self.tokenizador.enable_truncation(max_length=512)
        self.tokenizador.enable_padding()
        self.sessao = ort.InferenceSession(
            str(pasta / "onnx" / "model.onnx"), providers=["CPUExecutionProvider"])
        self.entradas = {e.name for e in self.sessao.get_inputs()}

    def codificar(self, textos: list[str], lote: int = 64) -> np.ndarray:
        saida = []
        for i in range(0, len(textos), lote):
            cod = self.tokenizador.encode_batch([PREFIXO + t for t in textos[i:i + lote]])
            ids = np.array([c.ids for c in cod], dtype=np.int64)
            mascara = np.array([c.attention_mask for c in cod], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mascara}
            if "token_type_ids" in self.entradas:
                feed["token_type_ids"] = np.zeros_like(ids)
            ultimo = self.sessao.run(None, feed)[0]  # (lote, tokens, 384)
            m = mascara[..., None].astype(np.float32)
            media = (ultimo * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)  # mean pooling
            saida.append(media / np.linalg.norm(media, axis=1, keepdims=True))     # norma L2 = 1
        return np.vstack(saida).astype(np.float32)


def obter_modelo_id(con: psycopg.Connection) -> tuple[int, bool]:
    """Cadastra o modelo configurado; ativa-o se nenhum outro estiver ativo."""
    con.execute(
        "INSERT INTO ml.modelo_embedding (nome, revisao, dimensao, prefixo) "
        "VALUES (%s, %s, %s, %s) ON CONFLICT (nome, revisao) DO NOTHING",
        (MODELO, REVISAO, DIMENSAO, PREFIXO))
    con.execute(
        "UPDATE ml.modelo_embedding SET ativo = true WHERE nome = %s AND revisao = %s "
        "AND NOT EXISTS (SELECT 1 FROM ml.modelo_embedding WHERE ativo)",
        (MODELO, REVISAO))
    return con.execute(
        "SELECT id, ativo FROM ml.modelo_embedding WHERE nome = %s AND revisao = %s",
        (MODELO, REVISAO)).fetchone()


def sincronizar_textos(con: psycopg.Connection) -> tuple[int, int, int]:
    """Espelha analytics.ml_stg_texto em ml.item_texto, guardando o histórico."""
    staging = con.execute(
        "SELECT entidade, chave_origem, texto, texto_sha256, atributos "
        "FROM analytics.ml_stg_texto").fetchall()
    novos = 0
    for entidade, chave, texto, sha, atributos in staging:
        # Desativa a versão anterior antes de inserir a nova (índice item_um_ativo).
        con.execute(
            "UPDATE ml.item_texto SET ativo = false WHERE entidade = %s AND chave_origem = %s "
            "AND ativo AND texto_sha256 <> %s", (entidade, chave, sha))
        cur = con.execute(
            "INSERT INTO ml.item_texto (entidade, chave_origem, texto, texto_sha256, atributos, fonte) "
            "VALUES (%s, %s, %s, %s, %s, 'analytics.ml_stg_texto') "
            "ON CONFLICT (entidade, chave_origem, texto_sha256) DO UPDATE "
            "SET ativo = true, atributos = EXCLUDED.atributos "
            "WHERE NOT ml.item_texto.ativo OR ml.item_texto.atributos <> EXCLUDED.atributos "
            "RETURNING (xmax = 0) AS inserido",
            (entidade, chave, texto, sha, Jsonb(atributos)))
        linha = cur.fetchone()
        novos += bool(linha and linha[0])
    # Itens que saíram do staging deixam de ser ativos (o histórico fica).
    saidos = con.execute(
        "UPDATE ml.item_texto i SET ativo = false WHERE i.ativo AND NOT EXISTS ("
        "SELECT 1 FROM analytics.ml_stg_texto s WHERE s.entidade = i.entidade "
        "AND s.chave_origem = i.chave_origem)").rowcount
    return len(staging), novos, saidos


def main() -> int:
    inicio = time.time()
    with psycopg.connect(
        host=os.getenv("PGHOST", "db"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "ofertas_unb"),
        user=os.getenv("PGUSER", "g2"),
        password=os.getenv("PGPASSWORD", "g2_dev_only"),
    ) as con:
        register_vector(con)
        with con.transaction():
            modelo_id, ativo = obter_modelo_id(con)
            total, novos, saidos = sincronizar_textos(con)
            pendentes = con.execute(
                "SELECT i.id, i.entidade, i.texto FROM ml.item_texto i WHERE i.ativo "
                "AND NOT EXISTS (SELECT 1 FROM ml.embedding e WHERE e.item_id = i.id "
                "AND e.modelo_id = %s) ORDER BY i.id", (modelo_id,)).fetchall()
            print(f"P12: {total} textos no staging, {novos} versões novas, {saidos} itens desativados, "
                  f"{len(pendentes)} sem vetor no modelo {MODELO}@{REVISAO[:8]}"
                  f"{'' if ativo else ' (modelo INATIVO: vetores gerados para troca futura)'}")
            if pendentes:
                pasta = baixar_modelo(Path(os.getenv("MODELO_DIR", "modelos")))
                vetores = Codificador(pasta).codificar([p[2] for p in pendentes])
                with con.cursor() as cur:
                    cur.executemany(
                        "INSERT INTO ml.embedding (item_id, entidade, modelo_id, vetor) "
                        "VALUES (%s, %s, %s, %s)",
                        [(p[0], p[1], modelo_id, v) for p, v in zip(pendentes, vetores)])
        con.execute("ANALYZE ml.item_texto")
        con.execute("ANALYZE ml.embedding")
    print(f"P12 concluído em {time.time() - inicio:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
