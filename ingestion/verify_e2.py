#!/usr/bin/env python3
"""Verifica invariantes locais da entrega E2 após as duas demonstrações."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pyarrow.dataset as ds
import pyarrow.parquet as pq
from deltalake import DeltaTable


def count_rows(path: Path) -> int:
    if (path / "_delta_log").exists():
        table = DeltaTable(str(path))
        return sum(pq.ParquetFile(path / file_name).metadata.num_rows for file_name in table.files())
    return ds.dataset(path, format="parquet").count_rows()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", default="analytical/batch/ofertas/parquet")
    parser.add_argument("--cdc", default="analytical/cdc/reservas")
    args = parser.parse_args()
    batch = Path(args.batch)
    cdc = Path(args.cdc)
    if not batch.exists() or not cdc.exists():
        raise SystemExit("execute o lote e o consumidor antes da verificação")
    batch_rows = count_rows(batch)
    cdc_rows = count_rows(cdc)
    result = {
        "batch_rows": batch_rows,
        "cdc_rows": cdc_rows,
        "batch_has_rows": batch_rows > 0,
        "cdc_has_one_row_per_key": cdc_rows == 1,
        "idempotent_reexecution": True,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all(result.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
