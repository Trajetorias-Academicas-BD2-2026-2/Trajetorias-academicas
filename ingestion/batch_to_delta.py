#!/usr/bin/env python3
"""Materializa a coleta pública em Parquet e em uma tabela Delta idempotente."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq
from deltalake import WriterProperties, write_deltalake


COLUMNS = (
    "curso_codigo",
    "disciplina_codigo",
    "disciplina_nome",
    "turma_codigo",
    "ano",
    "periodo",
    "docentes",
    "vagas_reservadas",
    "horario",
    "fonte",
    "coletado_em",
)


def read_rows(source: Path) -> list[dict[str, object]]:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = set(COLUMNS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"colunas obrigatórias ausentes: {sorted(missing)}")
        rows: list[dict[str, object]] = []
        for row in reader:
            rows.append(
                {
                    **{column: row[column] for column in COLUMNS if column not in {"ano", "periodo", "vagas_reservadas"}},
                    "ano": int(row["ano"]),
                    "periodo": int(row["periodo"]),
                    "vagas_reservadas": int(row["vagas_reservadas"]),
                }
            )
    if not rows:
        raise ValueError("a fonte pública está vazia")
    return rows


def source_checksum(source: Path) -> str:
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def materialize(source: Path, output: Path) -> dict[str, object]:
    rows = read_rows(source)
    checksum = source_checksum(source)
    table = pa.Table.from_pylist(rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        temporary_path = Path(temporary)
        parquet_path = temporary_path / "parquet"
        delta_path = temporary_path / "delta"
        ds.write_dataset(
            table,
            parquet_path,
            format="parquet",
            partitioning=["ano", "periodo"],
            existing_data_behavior="delete_matching",
            file_options=ds.ParquetFileFormat().make_write_options(compression="zstd"),
        )
        write_deltalake(
            str(delta_path),
            table,
            mode="overwrite",
            partition_by=["ano", "periodo"],
            configuration={"delta.appendOnly": "false"},
            writer_properties=WriterProperties(compression="ZSTD"),
        )
        manifest = {
            "source": str(source),
            "source_sha256": checksum,
            "rows": len(rows),
            "compression": "zstd",
            "partitioning": ["ano", "periodo"],
            "delivery_semantics": "at-least-once with deterministic overwrite and key deduplication",
        }
        (temporary_path / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if output.exists():
            shutil.rmtree(output)
        output.mkdir(parents=True)
        shutil.copytree(parquet_path, output / "parquet")
        shutil.copytree(delta_path, output / "delta")
        shutil.copy2(temporary_path / "manifest.json", output / "manifest.json")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="data/coleta_publica_2026-09-28/ofertas_por_curso.csv")
    parser.add_argument("--output", default="analytical/batch/ofertas")
    args = parser.parse_args()
    print(json.dumps(materialize(Path(args.source), Path(args.output)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
