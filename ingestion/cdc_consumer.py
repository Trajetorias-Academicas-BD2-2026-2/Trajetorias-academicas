#!/usr/bin/env python3
"""Consome a outbox CDC do PostgreSQL de forma incremental e aplica num Delta por MERGE.

Semântica: at-least-once na leitura, com escrita idempotente.
  1. lê só os eventos depois do checkpoint (id > last_event_id);
  2. reduz para o último evento de cada (tabela, chave);
  3. faz MERGE no Delta: só substitui a linha se o evento for mais novo
     (last_event_id maior). Reaplicar o mesmo evento não muda nada;
  4. só então avança o checkpoint.
Se o processo cair entre 3 e 4, a próxima execução relê os mesmos eventos
e o MERGE os ignora: nenhuma linha duplicada e nenhum estado regredido.

FAIL_BEFORE_CHECKPOINT=1 simula essa queda, para a demonstração.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pyarrow as pa
from deltalake import DeltaTable, WriterProperties, write_deltalake

from delta_io import read_delta

CONSUMER = "delta"

SCHEMA = pa.schema(
    [
        ("tabela", pa.string()),
        ("aggregate_key", pa.string()),
        ("operation", pa.string()),
        ("deleted", pa.bool_()),
        ("payload", pa.string()),
        ("last_event_id", pa.int64()),
        ("last_occurred_at", pa.timestamp("us", tz="UTC")),
        ("published_at", pa.timestamp("us", tz="UTC")),
    ]
)


def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "ofertas_unb"),
        user=os.getenv("PGUSER", "g2"),
        password=os.getenv("PGPASSWORD", "g2_dev_only"),
    )


def read_checkpoint(cursor: psycopg.Cursor) -> int:
    cursor.execute("SELECT last_event_id FROM e2_cdc_checkpoint WHERE consumer = %s", (CONSUMER,))
    row = cursor.fetchone()
    return row[0] if row else 0


def latest_per_key(events: list[tuple]) -> pa.Table:
    """Último evento de cada (tabela, chave); DELETE vira marca de remoção."""
    latest: dict[tuple[str, str], dict[str, object]] = {}
    now = datetime.now(timezone.utc)
    for event_id, tabela, key, operation, payload, occurred_at in events:
        latest[(tabela, key)] = {
            "tabela": tabela,
            "aggregate_key": key,
            "operation": operation,
            "deleted": operation == "DELETE",
            "payload": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            "last_event_id": event_id,
            "last_occurred_at": occurred_at,
            "published_at": now,
        }
    return pa.Table.from_pylist(list(latest.values()), schema=SCHEMA)


def apply(output: Path, batch: pa.Table) -> None:
    properties = WriterProperties(compression="ZSTD")
    if not (output / "_delta_log").exists():
        output.mkdir(parents=True, exist_ok=True)
        write_deltalake(str(output), batch, mode="append", partition_by=["tabela"],
                        writer_properties=properties)
        return
    (
        DeltaTable(str(output))
        .merge(
            source=batch,
            predicate="t.tabela = s.tabela AND t.aggregate_key = s.aggregate_key",
            source_alias="s",
            target_alias="t",
            writer_properties=properties,
        )
        .when_matched_update_all(predicate="s.last_event_id > t.last_event_id")
        .when_not_matched_insert_all()
        .execute()
    )


def consume(output: Path) -> dict[str, object]:
    started = time.perf_counter()
    with connect() as connection, connection.cursor() as cursor:
        checkpoint = read_checkpoint(cursor)
        cursor.execute(
            """
            SELECT id, tabela, aggregate_key, operation, payload, occurred_at
            FROM e2_cdc_outbox
            WHERE id > %s
            ORDER BY id
            """,
            (checkpoint,),
        )
        events = cursor.fetchall()

    if events:
        apply(output, latest_per_key(events))

    if os.getenv("FAIL_BEFORE_CHECKPOINT") == "1":
        raise SystemExit(
            f"falha simulada: {len(events)} eventos escritos no Delta, checkpoint NÃO avançado ({checkpoint})"
        )

    new_checkpoint = events[-1][0] if events else checkpoint
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO e2_cdc_checkpoint (consumer, last_event_id)
            VALUES (%s, %s)
            ON CONFLICT (consumer) DO UPDATE
            SET last_event_id = EXCLUDED.last_event_id, updated_at = now()
            """,
            (CONSUMER, new_checkpoint),
        )

    by_operation: dict[str, int] = {}
    for event in events:
        by_operation[event[3]] = by_operation.get(event[3], 0) + 1
    rows = read_delta(output).num_rows if (output / "_delta_log").exists() else 0
    return {
        "checkpoint_antes": checkpoint,
        "checkpoint_depois": new_checkpoint,
        "eventos_lidos": len(events),
        "eventos_por_operacao": by_operation,
        "linhas_no_delta": rows,
        "duracao_s": round(time.perf_counter() - started, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="analytical/cdc/oltp")
    args = parser.parse_args()
    print(json.dumps(consume(Path(args.output)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
