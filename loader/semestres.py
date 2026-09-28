"""Regras de semestre letivo, sem dependência de rede nem de banco
(testadas em tests/test_parsing.py).

Só carregamos semestres ENCERRADOS: turmas e reservas de um semestre em
andamento ainda mudam, e turma/reserva_vaga guardam uma única linha por
turma e semestre (ver docs/historico.md).

"Encerrado" vem do calendário acadêmico oficial da UnB, versionado em
data/calendario_academico.csv com a fonte de cada data: o semestre está
encerrado a partir do dia seguinte à data mais tardia entre último dia de
aulas, último dia letivo e prazo de consolidação das turmas no SIGAA.
Semestre fora do calendário é recusado, nunca estimado.
"""

import csv
from datetime import date


def parse_semestre(texto: str) -> tuple[int, int]:
    """'2022.1' -> (2022, 1). Aceita só períodos regulares 1 e 2."""
    ano_txt, _, periodo_txt = texto.strip().partition(".")
    ano, periodo = int(ano_txt), int(periodo_txt)
    if periodo not in (1, 2):
        raise ValueError(f"Período inválido em '{texto}': use 1 ou 2")
    return ano, periodo


def intervalo(inicio: str, fim: str) -> list[tuple[int, int]]:
    """Todos os semestres regulares de `inicio` a `fim`, inclusive."""
    atual, ultimo = parse_semestre(inicio), parse_semestre(fim)
    if atual > ultimo:
        raise ValueError(f"Semestre inicial {inicio} é posterior ao final {fim}")
    saida = []
    while atual <= ultimo:
        saida.append(atual)
        ano, periodo = atual
        atual = (ano, 2) if periodo == 1 else (ano + 1, 1)
    return saida


def rotulo(ano: int, periodo: int) -> str:
    return f"{ano}.{periodo}"


def ler_calendario(caminho: str) -> dict[tuple[int, int], dict]:
    """Lê o calendário e calcula `encerramento` de cada semestre."""
    calendario = {}
    with open(caminho, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            datas = [
                date.fromisoformat(r[c])
                for c in ("ultimo_dia_aulas", "ultimo_dia_letivo", "consolidacao_ate")
                if r[c].strip()
            ]
            if not datas:
                raise ValueError(f"Semestre {r['ano']}.{r['periodo']} sem nenhuma data de fim no calendário")
            if not r["fonte_url"].strip():
                raise ValueError(f"Semestre {r['ano']}.{r['periodo']} sem fonte no calendário")
            calendario[(int(r["ano"]), int(r["periodo"]))] = {**r, "encerramento": max(datas)}
    return calendario


def encerrado_em(calendario: dict, ano: int, periodo: int, dia: date) -> bool:
    """True se o semestre já tinha encerrado no dia `dia`. Semestre fora do
    calendário levanta erro: não há data para sustentar a garantia."""
    if (ano, periodo) not in calendario:
        raise KeyError(f"Semestre {rotulo(ano, periodo)} ausente do calendário acadêmico")
    return dia > calendario[(ano, periodo)]["encerramento"]
