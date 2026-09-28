"""
Configuração central do loader (tudo pode ser sobrescrito por variável de
ambiente no docker-compose.yml).
"""

import os
from datetime import date

import semestres

# Lote versionado que o loader carrega: uma pasta de coleta com
# SHA256SUMS.txt. Uma nova coleta vira uma nova pasta datada; trocar de lote
# é mudar esta variável.
DATA_DIR = os.getenv("DATA_DIR", "../data/coleta_publica_2026-09-28")
DEBUG_DIR = os.getenv("DEBUG_DIR", "debug")

# Calendário acadêmico oficial (datas de encerramento de cada semestre, com fonte).
CALENDARIO = os.getenv("CALENDARIO", "../data/calendario_academico.csv")

# Recorte esperado no lote: todos os semestres encerrados, inclusive.
SEMESTRE_INICIO = os.getenv("SEMESTRE_INICIO", "2022.1")
SEMESTRE_FIM = os.getenv("SEMESTRE_FIM", "2026.1")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "ofertas_unb")
DB_USER = os.getenv("DB_USER", "g2")
DB_PASSWORD = os.getenv("DB_PASSWORD", "g2_dev_only")

ARQ_CURSOS = "cursos.csv"
ARQ_COMPONENTES = "componentes_catalogo.csv"
ARQ_PRE_REQUISITOS = "prerequisitos_parciais.csv"
ARQ_CURRICULOS = "curriculos.csv"
ARQ_CURRICULO_COMPONENTES = "curso_disciplina_por_curriculo.csv"
ARQ_OFERTAS = "ofertas_por_curso.csv"
ARQ_CHECKSUMS = "SHA256SUMS.txt"

UNIDADE_FCTE = "FCTE"


def lote() -> str:
    """Nome do lote = nome da pasta de coleta (vai para a coluna `lote`)."""
    return os.path.basename(os.path.normpath(DATA_DIR))


def semestres_da_carga(hoje: date | None = None) -> list[tuple[int, int]]:
    """Semestres esperados no lote. Recusa semestre ausente do calendário
    acadêmico ou ainda não encerrado na data de hoje."""
    hoje = hoje or date.today()
    calendario = semestres.ler_calendario(CALENDARIO)
    lista = semestres.intervalo(SEMESTRE_INICIO, SEMESTRE_FIM)
    fora = [semestres.rotulo(a, p) for a, p in lista if (a, p) not in calendario]
    if fora:
        raise SystemExit(f"Semestre(s) sem data no calendário acadêmico ({CALENDARIO}): {', '.join(fora)}")
    abertos = [semestres.rotulo(a, p) for a, p in lista if not semestres.encerrado_em(calendario, a, p, hoje)]
    if abertos:
        raise SystemExit(
            f"Semestre(s) não encerrados em {hoje:%d/%m/%Y} segundo o calendário acadêmico: "
            f"{', '.join(abertos)}. Só carregamos semestres encerrados (ver docs/historico.md)."
        )
    return lista
