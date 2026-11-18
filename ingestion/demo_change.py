#!/usr/bin/env python3
"""Altera uma linha real do OLTP para demonstrar o caminho CDC (e a SCD da E3).

Exemplos:
    python ingestion/demo_change.py --disciplina FGA0137 --nome "SISTEMAS DE BANCO DE DADOS 1 (REVISADA)"
    python ingestion/demo_change.py --disciplina FGA0137 --carga-horaria 90
    python ingestion/demo_change.py --disciplina FGA0137 --reverter

`disciplina` é tabela de catálogo com upsert (não é insert-only): uma
correção de nome ou de carga horária no SIGAA chega como UPDATE. O trigger da
V010 grava o evento na outbox na mesma transação. --reverter volta aos
valores do lote versionado (componentes_catalogo.csv), gerando outro UPDATE.
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import psycopg

CATALOGO = Path("data/coleta_publica_2026-09-28/componentes_catalogo.csv")


def original(codigo: str) -> tuple[str, int | None]:
    with CATALOGO.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["codigo"] == codigo:
                return row["nome"], int(row["carga_horaria"]) if row["carga_horaria"] else None
    raise SystemExit(f"{codigo} não está no catálogo versionado")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--disciplina", default="FGA0137")
    parser.add_argument("--nome")
    parser.add_argument("--carga-horaria", type=int)
    parser.add_argument("--reverter", action="store_true")
    args = parser.parse_args()

    with psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "ofertas_unb"),
        user=os.getenv("PGUSER", "g2"),
        password=os.getenv("PGPASSWORD", "g2_dev_only"),
    ) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT nome, carga_horaria FROM disciplina WHERE codigo = %s", (args.disciplina,))
        antes = cursor.fetchone()
        if antes is None:
            raise SystemExit(f"disciplina {args.disciplina} não existe no OLTP")
        nome, carga = antes
        if args.reverter:
            nome, carga = original(args.disciplina)
        if args.nome:
            nome = args.nome
        if args.carga_horaria:
            carga = args.carga_horaria
        cursor.execute(
            "UPDATE disciplina SET nome = %s, carga_horaria = %s WHERE codigo = %s",
            (nome, carga, args.disciplina),
        )
        cursor.execute(
            "SELECT id, operation FROM e2_cdc_outbox WHERE tabela = 'disciplina' AND aggregate_key = %s "
            "ORDER BY id DESC LIMIT 1",
            (args.disciplina,),
        )
        evento = cursor.fetchone()
    print(f"OLTP disciplina {args.disciplina}: {antes[0]!r}/{antes[1]}h -> {nome!r}/{carga}h")
    print(f"último evento na outbox para a chave: {evento}")


if __name__ == "__main__":
    main()
