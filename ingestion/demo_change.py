#!/usr/bin/env python3
"""Gera uma alteração OLTP reproduzível para demonstrar o caminho CDC."""

from __future__ import annotations

import argparse
import os

import psycopg


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", default="E2-DEMO-001")
    parser.add_argument("--vagas", type=int, default=30)
    args = parser.parse_args()
    with psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "ofertas_unb"),
        user=os.getenv("PGUSER", "g2"),
        password=os.getenv("PGPASSWORD", "g2_dev_only"),
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO e2_oltp_reserva_demo (reserva_id, curso_codigo, disciplina_codigo, vagas)
                VALUES (%s, 'FGA_SOFT', 'FGA0242', %s)
                ON CONFLICT (reserva_id) DO UPDATE SET vagas = EXCLUDED.vagas
                """,
                (args.id, args.vagas),
            )
        connection.commit()
    print(f"alteração confirmada no OLTP: {args.id} vagas={args.vagas}")


if __name__ == "__main__":
    main()
