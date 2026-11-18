#!/usr/bin/env python3
"""Opção nula do ETL reverso (E4): um CSV por curso, gerado a cada execução.

Mesmos itens do envio por API (analytics/pauta.py), entregues como arquivo
em saida/pauta_<curso>.csv. O ADR-0007 compara as duas formas.
"""

from __future__ import annotations

import csv
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from etl_reverso import conectar  # noqa: E402
from pauta import montar  # noqa: E402

SAIDA = Path(os.getenv("SAIDA_PAUTA", "/workspace/saida"))
COLUNAS = ["curso", "tipo", "titulo", "detalhe", "disciplina_codigo", "semestre", "metrica", "versao_metrica", "valor"]


def main() -> None:
    inicio = time.perf_counter()
    with conectar() as conn:
        itens = montar(conn)
    por_curso = defaultdict(list)
    for item in itens:
        por_curso[item["curso_codigo"]].append(item)
    SAIDA.mkdir(parents=True, exist_ok=True)
    for curso, lista in sorted(por_curso.items()):
        with (SAIDA / f"pauta_{curso}.csv").open("w", newline="", encoding="utf-8") as handle:
            escritor = csv.DictWriter(handle, fieldnames=COLUNAS, extrasaction="ignore")
            escritor.writeheader()
            escritor.writerows(lista)
    print(f"CSV da pauta: {len(itens)} itens em {len(por_curso)} arquivos ({SAIDA}), "
          f"{(time.perf_counter() - inicio) * 1000:.0f} ms")


if __name__ == "__main__":
    main()
