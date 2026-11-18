#!/usr/bin/env python3
"""Mede serialização e compressão para o padrão de acesso da E2 (ADR-0005).

Padrão de acesso a jusante: ler um semestre (ou a série inteira) e agregar
vagas por curso. Para cada formato, mede o tamanho em disco e a mediana de
20 leituras de "vagas por curso em 2024.1" e da série completa.
    docker compose run --rm e2-batch python ingestion/medir_formatos.py
"""

from __future__ import annotations

import csv
import io
import shutil
import statistics
import tempfile
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.dataset as ds

FONTE = Path("data/coleta_publica_2026-09-28/ofertas_por_curso.csv")
REPETICOES = 20


def tamanho(path: Path) -> int:
    return path.stat().st_size if path.is_file() else sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def mediana_ms(funcao) -> float:
    tempos = []
    for _ in range(REPETICOES):
        inicio = time.perf_counter()
        funcao()
        tempos.append((time.perf_counter() - inicio) * 1000)
    return round(statistics.median(tempos), 2)


def agrega(tabela: pa.Table) -> pa.Table:
    return tabela.group_by("curso_codigo").aggregate([("vagas_reservadas", "sum")])


def main() -> None:
    tabela = pacsv.read_csv(FONTE, convert_options=pacsv.ConvertOptions(column_types={"turma_codigo": pa.string()}))
    filtro = (ds.field("ano") == 2024) & (ds.field("periodo") == 1)
    linhas = []

    def csv_semestre():
        t = pacsv.read_csv(FONTE)
        return agrega(t.filter((pc.field("ano") == 2024) & (pc.field("periodo") == 1)))

    linhas.append(("CSV (fonte)", "-", "não", tamanho(FONTE), 1, mediana_ms(csv_semestre),
                   mediana_ms(lambda: agrega(pacsv.read_csv(FONTE)))))

    with tempfile.TemporaryDirectory() as tmp:
        for codec in ("none", "snappy", "gzip", "zstd"):
            for particionado in (False, True):
                destino = Path(tmp) / f"{codec}_{particionado}"
                ds.write_dataset(
                    tabela, destino, format="parquet",
                    partitioning=ds.partitioning(pa.schema([("ano", pa.int64()), ("periodo", pa.int64())]), flavor="hive") if particionado else None,
                    file_options=ds.ParquetFileFormat().make_write_options(compression=codec),
                )
                abrir = lambda: ds.dataset(destino, format="parquet", partitioning="hive" if particionado else None)
                arquivos = sum(1 for f in destino.rglob("*.parquet"))
                linhas.append((
                    "Parquet", codec, "ano/periodo" if particionado else "não", tamanho(destino), arquivos,
                    mediana_ms(lambda: agrega(abrir().to_table(filter=filtro, columns=["curso_codigo", "vagas_reservadas"]))),
                    mediana_ms(lambda: agrega(abrir().to_table(columns=["curso_codigo", "vagas_reservadas"]))),
                ))

    print(f"Fonte: {FONTE} ({tabela.num_rows} linhas). Mediana de {REPETICOES} leituras, em ms.\n")
    print("| Formato | Compressão | Partição | Tamanho (kB) | Arquivos | Ler 2024.1 + agregar | Ler série + agregar |")
    print("|---|---|---|---:|---:|---:|---:|")
    for formato, codec, particao, bytes_, arquivos, semestre, serie in linhas:
        print(f"| {formato} | {codec} | {particao} | {bytes_ / 1024:.1f} | {arquivos} | {semestre} | {serie} |")


if __name__ == "__main__":
    main()
