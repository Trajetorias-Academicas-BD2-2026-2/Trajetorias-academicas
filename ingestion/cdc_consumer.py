#!/usr/bin/env python3
"""Consome a outbox CDC do PostgreSQL e publica um snapshot Delta deduplicado."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pyarrow as pa
from deltalake import WriterProperties, write_deltalake
import psycopg


def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "ofertas_unb"),
        user=os.getenv("PGUSER", "g2"),
        password=os.getenv("PGPASSWORD", "g2_dev_only"),
    )


def consume(output: Path) -> dict[str, int]:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, aggregate_key, operation, payload, occurred_at
                FROM e2_cdc_outbox
                ORDER BY id
                """
            )
            events = cursor.fetchall()
            cursor.execute("SELECT last_event_id FROM e2_cdc_checkpoint WHERE consumer = 'delta'")
            checkpoint_row = cursor.fetchone()
            checkpoint = checkpoint_row[0] if checkpoint_row else 0

    state: dict[str, dict[str, object]] = {}
    for event_id, key, operation, payload, occurred_at in events:
        if operation == "DELETE":
            state.pop(key, None)
        else:
            state[key] = {
                "aggregate_key": key,
                **payload,
                "last_event_id": event_id,
                "last_occurred_at": occurred_at.isoformat(),
            }

    if state:
        table = pa.Table.from_pylist(list(state.values()))
        output.mkdir(parents=True, exist_ok=True)
        write_deltalake(
            str(output),
            table,
            mode="overwrite",
            configuration={"delta.appendOnly": "false"},
            writer_properties=WriterProperties(compression="ZSTD"),
        )

    latest = events[-1][0] if events else checkpoint
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO e2_cdc_checkpoint (consumer, last_event_id)
                VALUES ('delta', %s)
                ON CONFLICT (consumer) DO UPDATE
                SET last_event_id = EXCLUDED.last_event_id, updated_at = now()
                """,
                (latest,),
            )
        connection.commit()
    return {"events_seen": len(events), "events_applied": max(0, len(events) - checkpoint), "checkpoint": latest, "rows_published": len(state)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="analytical/cdc/reservas")
    args = parser.parse_args()
    print(json.dumps(consume(Path(args.output)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
