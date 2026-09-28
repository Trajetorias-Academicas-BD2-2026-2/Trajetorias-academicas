"""Regras de semestre letivo, sem dependência de browser nem de banco
(testadas em tests/test_parsing.py).

Só carregamos semestres ENCERRADOS: a ocupação de um semestre em andamento
ainda muda (ajuste de matrícula, trancamentos), e oferta_turma guarda uma
única linha por turma e semestre (ver docs/adr/0001-...). Carregar um
semestre aberto congelaria um retrato parcial como se fosse o final.
"""

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


def semestre_corrente(hoje: date | None = None) -> tuple[int, int]:
    """Semestre que ainda pode estar em andamento na data `hoje`.

    Regra conservadora para o calendário da UnB:
      - janeiro e fevereiro: o 2º semestre do ano anterior ainda pode estar
        em fechamento de notas e matrícula;
      - março a julho: 1º semestre do ano;
      - agosto a dezembro: 2º semestre do ano.
    """
    hoje = hoje or date.today()
    if hoje.month <= 2:
        return hoje.year - 1, 2
    if hoje.month <= 7:
        return hoje.year, 1
    return hoje.year, 2


def encerrado(ano: int, periodo: int, hoje: date | None = None) -> bool:
    return (ano, periodo) < semestre_corrente(hoje)


def rotulo(ano: int, periodo: int) -> str:
    return f"{ano}.{periodo}"
