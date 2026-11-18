#!/usr/bin/env python3
"""ETL reverso (E4): leva as métricas tratadas para a Pauta da coordenação.

Fluxo:
  1. monta os itens a partir das métricas oficiais (analytics/pauta.py);
  2. grava cada item na fila operations.envio_pauta (outbox):
     novo → pendente; conteúdo mudou → nova versão, pendente; igual → nada;
     item que deixou de existir → retirado;
  3. envia os pendentes para a Pauta (POST /api/itens) com Idempotency-Key,
     três tentativas com espera crescente;
  4. só marca "enviado" depois da confirmação (200/201).

Destino fora do ar: os itens continuam "pendentes" com o erro registrado,
o pipeline NÃO falha (a análise não depende da Pauta) e a próxima execução
reenvia. Reenviar a mesma versão não duplica nada no destino.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

import psycopg
from psycopg.types.json import Jsonb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pauta import montar  # noqa: E402

DESTINO = os.getenv("PAUTA_URL", "http://coordenacao:8090")
TENTATIVAS = int(os.getenv("PAUTA_TENTATIVAS", "3"))


class DestinoForaDoAr(Exception):
    pass


def conectar() -> psycopg.Connection:
    return psycopg.connect(
        host=os.getenv("PGHOST", "db"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "ofertas_unb"),
        user=os.getenv("ETL_PGUSER", os.getenv("PGUSER", "g2")),
        password=os.getenv("ETL_PGPASSWORD", os.getenv("PGPASSWORD", "g2_dev_only")),
    )


def enviar(item: dict) -> int:
    corpo = json.dumps(item, ensure_ascii=False).encode()
    pedido = urllib.request.Request(
        f"{DESTINO}/api/itens", data=corpo, method="POST",
        headers={"Content-Type": "application/json", "Idempotency-Key": item["versao"]})
    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            with urllib.request.urlopen(pedido, timeout=5) as resposta:
                return resposta.status
        except urllib.error.HTTPError as erro:
            raise RuntimeError(f"Pauta recusou o item: HTTP {erro.code}") from erro
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as erro:
            ultimo_erro = erro
            if tentativa < TENTATIVAS:
                time.sleep(0.5 * 2 ** (tentativa - 1))
    raise DestinoForaDoAr(str(getattr(ultimo_erro, "reason", ultimo_erro)))


def main() -> int:
    resumo = {"itens": 0, "novos": 0, "nova_versao": 0, "inalterados": 0, "retirados": 0,
              "enviados": 0, "criados_no_destino": 0, "ja_existiam_no_destino": 0, "pendentes": 0}
    with conectar() as conn:
        itens = montar(conn)
        resumo["itens"] = len(itens)
        with conn.cursor() as cur:
            cur.execute("SELECT chave, versao FROM operations.envio_pauta WHERE status <> 'retirado'")
            atuais = dict(cur.fetchall())
            for item in itens:
                if item["chave"] not in atuais:
                    resumo["novos"] += 1
                elif atuais[item["chave"]] != item["versao"]:
                    resumo["nova_versao"] += 1
                else:
                    resumo["inalterados"] += 1
                    continue
                cur.execute("""
                    INSERT INTO operations.envio_pauta (chave, versao, curso_codigo, tipo, payload, status)
                    VALUES (%s, %s, %s, %s, %s, 'pendente')
                    ON CONFLICT (chave) DO UPDATE SET versao = EXCLUDED.versao, payload = EXCLUDED.payload,
                        status = 'pendente', tentativas = 0, ultimo_erro = NULL, atualizado_em = now()""",
                    (item["chave"], item["versao"], item["curso_codigo"], item["tipo"], Jsonb(item)))
            vigentes = [i["chave"] for i in itens]
            cur.execute("""UPDATE operations.envio_pauta SET status = 'retirado', atualizado_em = now()
                           WHERE status <> 'retirado' AND NOT (chave = ANY(%s))""", (vigentes,))
            resumo["retirados"] = cur.rowcount
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT chave, payload FROM operations.envio_pauta WHERE status = 'pendente' ORDER BY chave")
            pendentes = cur.fetchall()
            for posicao, (chave, payload) in enumerate(pendentes):
                try:
                    status = enviar(payload)
                except DestinoForaDoAr as erro:
                    restantes = [c for c, _ in pendentes[posicao:]]
                    cur.execute("""UPDATE operations.envio_pauta SET tentativas = tentativas + 1,
                                   ultimo_erro = %s, atualizado_em = now() WHERE chave = ANY(%s)""",
                                (f"Pauta fora do ar: {erro}", restantes))
                    conn.commit()
                    print(f"AVISO: Pauta da coordenação fora do ar ({erro}). {len(restantes)} itens ficam "
                          f"pendentes e serão reenviados na próxima execução.", file=sys.stderr)
                    break
                cur.execute("""UPDATE operations.envio_pauta SET status = 'enviado', enviado_em = now(),
                               tentativas = tentativas + 1, ultimo_erro = NULL WHERE chave = %s""", (chave,))
                conn.commit()
                resumo["enviados"] += 1
                resumo["criados_no_destino" if status == 201 else "ja_existiam_no_destino"] += 1
            cur.execute("SELECT count(*) FROM operations.envio_pauta WHERE status = 'pendente'")
            resumo["pendentes"] = cur.fetchone()[0]
    print("ETL reverso → Pauta da coordenação: " + json.dumps(resumo, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
