"""
Configuração central do loader.

IMPORTANTE (leia antes de rodar):
Os dois formulários do SIGAA (Consulta de Turmas e Busca de Componentes
Curriculares) são páginas JSF: os campos reais (name dos <select>, ids)
só aparecem no HTML renderizado, e mudam entre reinstalações do sistema.
Os seletores abaixo foram escritos por TEXTO VISÍVEL (rótulo/label), que é
estável entre versões do JSF — mas antes da primeira carga real, rode um
scraper em modo headed (headless=False) e confirme visualmente que cada
select_option encontrou a opção certa. Ajuste os textos aqui se algo não
bater.
"""

import os

TURMAS_URL = "https://sigaa.unb.br/sigaa/public/turmas/listar.jsf"
COMPONENTES_URL = "https://sigaa.unb.br/sigaa/public/componentes/busca_componentes.jsf"

NIVEL_ENSINO = "GRADUAÇÃO"
UNIDADE = os.getenv("SIGAA_UNIDADE", "FACULDADE DE CIÊNCIAS E TECNOLOGIAS EM ENGENHARIA - BRASÍLIA")
ANO = os.getenv("SIGAA_ANO", "2026")
PERIODO = os.getenv("SIGAA_PERIODO", "2")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "ofertas_unb")
DB_USER = os.getenv("DB_USER", "g2")
DB_PASSWORD = os.getenv("DB_PASSWORD", "g2_dev_only")

STAGING_DIR = os.getenv("STAGING_DIR", "staging")
FONTE_TURMAS = "sigaa_turmas"
FONTE_COMPONENTES = "sigaa_componentes"

TESTE_SEM_UNIDADE = os.getenv("TESTE_SEM_UNIDADE", "0") == "1"

TESTE_MINIMO = os.getenv("TESTE_MINIMO", "0") == "1"
