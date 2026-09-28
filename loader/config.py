"""
Configuração central do loader (tudo pode ser sobrescrito por variável de
ambiente no docker-compose.yml).

Os formulários do SIGAA são páginas JSF: os atributos internos (name, id)
mudam entre versões, então os scrapers localizam campos pelo TEXTO VISÍVEL
dos rótulos. Se o SIGAA mudar um rótulo, é aqui e em sigaa_utils.py que se
ajusta.
"""

import os

import semestres

HOME_URL = "https://sigaa.unb.br/sigaa/public/home.jsf"
CURSOS_URL = "https://sigaa.unb.br/sigaa/public/curso/lista.jsf?nivel=G&aba=p-graduacao"

NIVEL_ENSINO = "GRADUAÇÃO"
UNIDADE = os.getenv("SIGAA_UNIDADE", "FACULDADE DE CIÊNCIAS E TECNOLOGIAS EM ENGENHARIA - BRASÍLIA")

# Recorte temporal da carga: semestres ENCERRADOS, inclusive nas pontas.
SEMESTRE_INICIO = os.getenv("SIGAA_SEMESTRE_INICIO", "2022.1")
SEMESTRE_FIM = os.getenv("SIGAA_SEMESTRE_FIM", "2026.1")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "ofertas_unb")
DB_USER = os.getenv("DB_USER", "g2")
DB_PASSWORD = os.getenv("DB_PASSWORD", "g2_dev_only")

# Recorte versionado no git (reprodutível sem acessar o SIGAA).
DATA_DIR = os.getenv("DATA_DIR", "data/raw")
# Prints e HTML salvos quando uma raspagem falha (fora do git).
DEBUG_DIR = os.getenv("DEBUG_DIR", "debug")

# auto: raspa só o que ainda não está em DATA_DIR; 1: raspa tudo de novo;
# 0: nunca acessa o SIGAA (falha se faltar arquivo).
RASPAR = os.getenv("RASPAR", "auto")

FONTE_TURMAS = "sigaa_turmas"
FONTE_COMPONENTES = "sigaa_componentes"
FONTE_CURSOS = "sigaa_cursos"

ARQ_COMPONENTES = "componentes.csv"
ARQ_PRE_REQUISITOS = "pre_requisitos.csv"
ARQ_CURSOS = "cursos.csv"
ARQ_CURSO_DISCIPLINA = "curso_disciplina.csv"


def arq_turmas(ano: int, periodo: int) -> str:
    return f"turmas_{ano}_{periodo}.csv"


def semestres_da_carga() -> list[tuple[int, int]]:
    """Semestres configurados; recusa qualquer semestre ainda em andamento."""
    lista = semestres.intervalo(SEMESTRE_INICIO, SEMESTRE_FIM)
    abertos = [semestres.rotulo(a, p) for a, p in lista if not semestres.encerrado(a, p)]
    if abertos:
        raise SystemExit(
            f"Semestre(s) em andamento no recorte: {', '.join(abertos)}. "
            "Só carregamos semestres encerrados (ver docs/historico.md). "
            "Ajuste SIGAA_SEMESTRE_FIM."
        )
    return lista
