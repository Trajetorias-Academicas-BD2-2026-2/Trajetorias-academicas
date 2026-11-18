#!/usr/bin/env python3
"""Materializa a coleta pública em Parquet e numa tabela Delta, de forma idempotente.

Dois modos:
  - completo (padrão): reconstrói tudo a partir da fonte. Rodar duas vezes
    dá o mesmo resultado (overwrite determinístico, nunca append);
  - janela (--semestre 2023.1): reprocessa só a partição ano=2023/periodo=1.
    A Delta recebe overwrite com predicado, e as outras partições não são
    reescritas. É assim que um dado atrasado entra: chega numa coleta
    posterior, mas é gravado na partição do semestre do evento (ano/periodo
    da turma), não na data de ingestão.

Particionamento por ano/periodo porque todas as leituras a jusante filtram
ou agrupam por semestre; zstd porque o dado é lido muitas vezes e escrito
uma vez por semestre (ver medição no ADR-0005).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.dataset as ds
from deltalake import DeltaTable, WriterProperties, write_deltalake

from delta_io import read_delta

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
INTEGER_COLUMNS = {"ano", "periodo", "vagas_reservadas"}
PROPERTIES = WriterProperties(compression="ZSTD")


def read_rows(source: Path, janela: tuple[int, int] | None = None) -> list[dict[str, object]]:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = set(COLUMNS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"colunas obrigatórias ausentes: {sorted(missing)}")
        rows = [
            {column: int(row[column]) if column in INTEGER_COLUMNS else row[column] for column in COLUMNS}
            for row in reader
        ]
    if not rows:
        raise ValueError("a fonte pública está vazia")
    if janela:
        rows = [row for row in rows if (row["ano"], row["periodo"]) == janela]
        if not rows:
            raise ValueError(f"a fonte não tem linhas do semestre {janela[0]}.{janela[1]}")
    return rows


def source_checksum(source: Path) -> str:
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_parquet(table: pa.Table, path: Path) -> None:
    ds.write_dataset(
        table,
        path,
        format="parquet",
        partitioning=ds.partitioning(pa.schema([("ano", pa.int64()), ("periodo", pa.int64())]), flavor="hive"),
        existing_data_behavior="delete_matching",
        file_options=ds.ParquetFileFormat().make_write_options(compression="zstd"),
        basename_template="part-{i}.parquet",
    )


def update_manifest(output: Path, run: dict[str, object]) -> dict[str, object]:
    path = output / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"runs": []}
    delta = DeltaTable(str(output / "delta"))
    manifest.update(
        {
            "compression": "zstd",
            "partitioning": ["ano", "periodo"],
            "delivery_semantics": "at-least-once com overwrite determinístico por partição",
            "delta_version": delta.version(),
            "rows": read_delta(output / "delta").num_rows,
        }
    )
    manifest["runs"].append(run)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def materialize(source: Path, output: Path) -> dict[str, object]:
    rows = read_rows(source)
    table = pa.Table.from_pylist(rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        staging = Path(temporary)
        write_parquet(table, staging / "parquet")
        write_deltalake(str(staging / "delta"), table, mode="overwrite", partition_by=["ano", "periodo"],
                        engine="rust", writer_properties=PROPERTIES)
        if output.exists():
            shutil.rmtree(output)
        shutil.copytree(staging, output)
    return update_manifest(output, run_info(source, "completo", None, len(rows)))


def reprocess_window(source: Path, output: Path, ano: int, periodo: int) -> dict[str, object]:
    if not (output / "delta" / "_delta_log").exists():
        raise SystemExit("rode o modo completo antes de reprocessar uma janela")
    rows = read_rows(source, (ano, periodo))
    table = pa.Table.from_pylist(rows)
    write_parquet(table, output / "parquet")
    write_deltalake(
        str(output / "delta"),
        table,
        mode="overwrite",
        predicate=f"ano = {ano} AND periodo = {periodo}",
        partition_by=["ano", "periodo"],
        engine="rust",
        writer_properties=PROPERTIES,
    )
    return update_manifest(output, run_info(source, "janela", f"{ano}.{periodo}", len(rows)))


def run_info(source: Path, mode: str, janela: str | None, rows: int) -> dict[str, object]:
    return {
        "modo": mode,
        "janela": janela,
        "source": str(source),
        "source_sha256": source_checksum(source),
        "linhas_escritas": rows,
        "executado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="data/coleta_publica_2026-09-28/ofertas_por_curso.csv")
    parser.add_argument("--output", default="analytical/batch/ofertas")
    parser.add_argument("--semestre", help="reprocessa só esta janela, ex.: 2023.1")
    args = parser.parse_args()
    if args.semestre:
        ano, periodo = (int(parte) for parte in args.semestre.split("."))
        manifest = reprocess_window(Path(args.source), Path(args.output), ano, periodo)
    else:
        manifest = materialize(Path(args.source), Path(args.output))
    resumo = {key: value for key, value in manifest.items() if key != "runs"}
    resumo["ultima_execucao"] = manifest["runs"][-1]
    print(json.dumps(resumo, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
