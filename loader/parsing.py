"""Interpretação do texto raspado do SIGAA, separada do Playwright para
poder ser testada com exemplos fixos (tests/test_parsing.py).
"""

import re

# Notação de horário do SIGAA: dias (2=seg ... 7=sáb), turno (M, T, N) e
# aulas do turno. Ex.: "246M12", "35T23", "24N34".
HORARIO_RE = re.compile(r"\b([2-7]+)([MTN])([1-7]+)\b")

CODIGO_DISCIPLINA_RE = re.compile(r"\b[A-Z]{2,4}\d{4}\b")

# O bloco de pré-requisitos vai do rótulo até o próximo rótulo conhecido da
# página de detalhe do componente (ou o fim do texto).
_PREREQ_RE = re.compile(
    r"Pr[ée]-?\s?Requisitos?\s*:?\s*(.*?)"
    r"(?=\n\s*(?:Co-?\s?Requisitos?|Correquisitos?|Equival[êe]ncias?|Ementa|Programa)\b|\Z)",
    re.IGNORECASE | re.DOTALL,
)


def extrair_horario(celulas: list[str]) -> str:
    """Primeira célula que contém horário na notação SIGAA, só com os
    códigos (descarta datas e comentários entre parênteses).
    Ex.: ["01", "FULANO", "35T23 (09/03/2026 - 11/07/2026)"] -> "35T23".
    Retorna "" se a turma não tem horário (TCC, estágio, etc.)."""
    for celula in celulas:
        codigos = [m.group(0) for m in HORARIO_RE.finditer(celula)]
        if codigos:
            return " ".join(codigos)
    return ""


def inferir_turno(horario: str) -> str:
    """Turno a partir do horário SIGAA.
    Só M/T -> DIURNO; só N -> NOTURNO; N junto com M ou T -> INTEGRAL;
    sem horário -> SEM_HORARIO (dado faltante explícito, não um palpite)."""
    letras = {m.group(2) for m in HORARIO_RE.finditer(horario)}
    if not letras:
        return "SEM_HORARIO"
    if letras == {"N"}:
        return "NOTURNO"
    if "N" in letras:
        return "INTEGRAL"
    return "DIURNO"


def extrair_expressao_prerequisito(texto_pagina: str) -> str:
    """Expressão de pré-requisito como o SIGAA a mostra, com espaços
    normalizados. Ex.: "( FGA0001 E FGA0002 ) OU ( FGA0003 )".
    Retorna "" se a disciplina não tem pré-requisito."""
    m = _PREREQ_RE.search(texto_pagina)
    if not m:
        return ""
    expressao = " ".join(m.group(1).split())
    if not CODIGO_DISCIPLINA_RE.search(expressao):
        return ""
    return expressao[:1000]


def codigos_da_expressao(expressao: str) -> list[str]:
    """Códigos citados na expressão, sem repetição e na ordem em que aparecem.
    A lógica E/OU fica preservada na própria expressão (disciplina.pre_requisito_expressao)."""
    vistos: list[str] = []
    for codigo in CODIGO_DISCIPLINA_RE.findall(expressao):
        if codigo not in vistos:
            vistos.append(codigo)
    return vistos


def parse_vagas(celulas: list[str]) -> tuple[int | None, int | None]:
    """(vagas_ofertadas, vagas_ocupadas) a partir das duas últimas células
    puramente numéricas da linha, ignorando a primeira célula (código da
    turma, que também pode ser numérico, ex.: "01").

    NÃO troca os valores quando ocupadas > ofertadas: turma com ocupação
    acima da oferta é exatamente o sinal de lotação que a pergunta de gestão
    procura. Se a linha não tem os dois números, retorna (None, None) e o
    loader rejeita a linha de forma explícita, em vez de gravar zero."""
    numeros = [int(c) for c in celulas[1:] if c.strip().isdigit()]
    if len(numeros) >= 2:
        return numeros[-2], numeros[-1]
    return None, None
