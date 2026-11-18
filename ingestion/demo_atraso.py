#!/usr/bin/env python3
"""Demonstra o tratamento de dado atrasado no caminho em lote.

Cenário: numa coleta posterior aparece uma reserva de 2023.1 que não estava
no lote de 28/09 (o SIGAA publicou a turma tarde). O evento é de 2023.1, a
ingestão é de hoje.

Escolha da Squad: o dado atrasado entra na partição do semestre do evento
(ano=2023/periodo=1), por reprocessamento só daquela janela. Ele não cai na
partição da data de ingestão nem é descartado. As outras partições não são
reescritas, e o Delta guarda a versão anterior (time travel) para auditoria.

O script trabalha numa cópia da fonte e, no fim, reprocessa a janela a
partir da fonte original, deixando a tabela como estava.
"""

from __future__ import annotations

import csv
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

import pyarrow.dataset as ds
from deltalake import DeltaTable

from batch_to_delta import reprocess_window
from delta_io import read_delta

FONTE = Path("data/coleta_publica_2026-09-28/ofertas_por_curso.csv")
SAIDA = Path("analytical/batch/ofertas")
COPIA = Path("analytical/tmp/ofertas_com_atraso.csv")
ATRASADA = {
    "curso_codigo": "FGA_SOFT",
    "disciplina_codigo": "FGA0137",
    "disciplina_nome": "SISTEMAS DE BANCO DE DADOS 1",
    "turma_codigo": "99",
    "ano": "2023",
    "periodo": "1",
    "docentes": "",
    "vagas_reservadas": "10",
    "horario": "",
    "fonte": "coleta_posterior_demo",
    "coletado_em": "2026-11-17T12:00:00.000Z",
}


def contagem() -> tuple[int, dict[str, int], list[str]]:
    delta = DeltaTable(str(SAIDA / "delta"))
    tabela = read_delta(SAIDA / "delta", columns=["ano", "periodo"]).to_pylist()
    por_semestre = Counter(f"{linha['ano']}.{linha['periodo']}" for linha in tabela)
    return delta.version(), dict(sorted(por_semestre.items())), sorted(delta.files())


def main() -> None:
    versao0, antes, arquivos0 = contagem()
    COPIA.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FONTE, COPIA)
    with COPIA.open("a", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=list(ATRASADA)).writerow(ATRASADA)

    reprocess_window(COPIA, SAIDA, 2023, 1)
    versao1, depois, arquivos1 = contagem()
    outras_intactas = [f for f in arquivos0 if "ano=2023/periodo=1" not in f] == [
        f for f in arquivos1 if "ano=2023/periodo=1" not in f
    ]
    atrasada = read_delta(
        SAIDA / "delta",
        columns=["ano", "periodo", "turma_codigo", "fonte", "coletado_em"],
        filter=ds.field("turma_codigo") == "99",
    ).to_pylist()

    reprocess_window(FONTE, SAIDA, 2023, 1)
    versao2, restaurado, _ = contagem()

    print(json.dumps(
        {
            "antes": {"versao_delta": versao0, "linhas_por_semestre": antes},
            "depois_do_atraso": {"versao_delta": versao1, "linhas_por_semestre": depois},
            "linha_atrasada_gravada_em": atrasada,
            "so_a_particao_2023_1_mudou": {k: (antes[k], depois[k]) for k in depois if antes.get(k) != depois[k]},
            "arquivos_das_outras_particoes_intactos": outras_intactas,
            "restaurado_da_fonte_original": {"versao_delta": versao2, "igual_ao_inicio": restaurado == antes},
        },
        ensure_ascii=False,
        indent=2,
    ))
    ok = outras_intactas and restaurado == antes and depois["2023.1"] == antes["2023.1"] + 1
    if not ok:
        print("demonstração de dado atrasado falhou", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
