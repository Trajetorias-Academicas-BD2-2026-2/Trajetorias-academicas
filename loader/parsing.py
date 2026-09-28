"""Interpretação dos campos textuais do SIGAA, sem dependência de rede ou
banco (testada em tests/test_parsing.py).
"""

import re
import unicodedata

# Notação de horário do SIGAA: dias (2=seg ... 7=sáb), turno (M, T, N) e
# aulas do turno. Ex.: "246M12", "35T23", "24N34".
HORARIO_RE = re.compile(r"\b([2-7]+)([MTN])([1-7]+)\b")


def extrair_horario(celulas: list[str]) -> str:
    """Primeira célula com horário na notação SIGAA, só com os códigos
    (descarta datas e comentários entre parênteses). "" se não houver."""
    for celula in celulas:
        codigos = [m.group(0) for m in HORARIO_RE.finditer(celula)]
        if codigos:
            return " ".join(codigos)
    return ""


def inferir_turno(horario: str) -> str:
    """Só M/T -> DIURNO; só N -> NOTURNO; N junto com M ou T -> INTEGRAL;
    sem horário -> SEM_HORARIO (dado faltante explícito, não um palpite)."""
    letras = {m.group(2) for m in HORARIO_RE.finditer(horario)}
    if not letras:
        return "SEM_HORARIO"
    if letras == {"N"}:
        return "NOTURNO"
    if "N" in letras:
        return "INTEGRAL"
    return "DIURNO"


def parse_docentes(texto: str) -> list[str]:
    """"FULANO , BELTRANO" -> ["FULANO", "BELTRANO"]. Remove a carga horária
    entre parênteses que o SIGAA às vezes acrescenta, e repetições."""
    nomes: list[str] = []
    for parte in texto.split(","):
        nome = " ".join(re.sub(r"\(.*?\)", "", parte).split())
        if nome and nome not in nomes:
            nomes.append(nome)
    return nomes


def normalizar_natureza(texto: str) -> str:
    """"Obrigatória" -> "OBRIGATORIA"; "Optativa" -> "OPTATIVA"."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    valor = sem_acento.strip().upper()
    if valor not in ("OBRIGATORIA", "OPTATIVA"):
        raise ValueError(f"Natureza curricular desconhecida: {texto!r}")
    return valor
