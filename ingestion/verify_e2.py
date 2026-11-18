#!/usr/bin/env python3
"""Confere as invariantes da E2 contra o OLTP: lote completo e CDC sem duplicação."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import psycopg
from delta_io import read_delta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", default="analytical/batch/ofertas/delta")
    parser.add_argument("--cdc", default="analytical/cdc/oltp")
    parser.add_argument("--fonte", default="data/coleta_publica_2026-09-28/ofertas_por_curso.csv")
    args = parser.parse_args()

    batch = read_delta(args.batch)
    cdc = read_delta(args.cdc).to_pylist()
    linhas_fonte = sum(1 for _ in Path(args.fonte).open(encoding="utf-8")) - 1

    chaves = [(linha["tabela"], linha["aggregate_key"]) for linha in cdc]
    por_tabela: dict[str, int] = {}
    for tabela, _ in chaves:
        por_tabela[tabela] = por_tabela.get(tabela, 0) + 1

    with psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "ofertas_unb"),
        user=os.getenv("PGUSER", "g2"),
        password=os.getenv("PGPASSWORD", "g2_dev_only"),
    ) as connection, connection.cursor() as cursor:
        oltp = {}
        for tabela in ("reserva_vaga", "disciplina", "curriculo_componente"):
            cursor.execute(f"SELECT count(*) FROM {tabela}")
            oltp[tabela] = cursor.fetchone()[0]
        cursor.execute("SELECT nome, carga_horaria FROM disciplina WHERE codigo = 'FGA0137'")
        nome_oltp, carga_oltp = cursor.fetchone()

    fga0137 = next(json.loads(l["payload"]) for l in cdc if l["tabela"] == "disciplina" and l["aggregate_key"] == "FGA0137")
    checks = {
        "lote: linhas no Delta = linhas da fonte": batch.num_rows == linhas_fonte,
        "cdc: uma linha por (tabela, chave)": len(chaves) == len(set(chaves)),
        "cdc: contagem por tabela = OLTP": por_tabela == oltp,
        "cdc: FGA0137 no Delta = valor atual no OLTP": (fga0137["nome"], fga0137["carga_horaria"]) == (nome_oltp, carga_oltp),
    }
    print(json.dumps(
        {"lote_linhas": batch.num_rows, "fonte_linhas": linhas_fonte, "cdc_por_tabela": por_tabela,
         "oltp_por_tabela": oltp, "checks": checks},
        ensure_ascii=False, indent=2,
    ))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
