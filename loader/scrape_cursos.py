"""
Extrai os cursos de graduação do Campus Gama e a estrutura curricular de
cada um (fonte: sigaa_cursos). Grava em DATA_DIR:
  - cursos.csv            um curso por linha
  - curso_disciplina.csv  disciplina da matriz do curso e se é obrigatória

Falha com erro se algum curso-alvo não for encontrado ou vier sem matriz:
esses dados sustentam o filtro "disciplina obrigatória" da pergunta de
gestão, então não há valor padrão aceitável para eles.
"""

import sys
import uuid

from playwright.sync_api import sync_playwright

import config
from parsing import CODIGO_DISCIPLINA_RE
from sigaa_utils import (
    agora_utc,
    fechar_aviso,
    gravar_csv,
    nova_pagina_disfarcada,
    precisa_raspar,
    salvar_debug,
)

# O SIGAA não mostra um código público estável na listagem de cursos, então
# o projeto define o seu (curso.codigo). "termo" é como o nome aparece na lista.
CURSOS_ALVO = [
    {"codigo": "FGA_SOFT", "termo": "ENGENHARIA DE SOFTWARE"},
    {"codigo": "FGA_AERO", "termo": "ENGENHARIA AEROESPACIAL"},
    {"codigo": "FGA_AUTO", "termo": "ENGENHARIA AUTOMOTIVA"},
    {"codigo": "FGA_ENERG", "termo": "ENGENHARIA DE ENERGIA"},
    {"codigo": "FGA_ELET", "termo": "ENGENHARIA ELETRÔNICA"},
]

CAMPOS_CURSOS = ["codigo", "nome", "unidade", "fonte", "carga_id", "coletado_em"]
CAMPOS_CURRICULO = ["curso_codigo", "disciplina_codigo", "obrigatoria", "fonte", "carga_id", "coletado_em"]


def run() -> None:
    if not precisa_raspar(config.ARQ_CURSOS, config.ARQ_CURSO_DISCIPLINA):
        print("Cursos: já estão em", config.DATA_DIR)
        return

    carga_id = str(uuid.uuid4())
    coletado_em = agora_utc()
    cursos: list[dict] = []
    curriculo: list[dict] = []
    problemas: list[str] = []

    with sync_playwright() as pw:
        browser, page = nova_pagina_disfarcada(pw)
        try:
            page.goto(config.CURSOS_URL, wait_until="networkidle")
            fechar_aviso(page)

            portais: dict[str, str] = {}
            for tr in page.locator("table tr").all():
                texto = " ".join(c.inner_text().strip() for c in tr.locator("td").all()).upper()
                if "GAMA" not in texto and "FCTE" not in texto:
                    continue
                for alvo in CURSOS_ALVO:
                    if alvo["termo"] in texto and alvo["codigo"] not in portais:
                        link = tr.locator("a[href*='portal.jsf']").first
                        href = link.get_attribute("href") if link.count() > 0 else None
                        if href:
                            if not href.startswith("http"):
                                href = "https://sigaa.unb.br/sigaa/public/curso/" + href.lstrip("/")
                            portais[alvo["codigo"]] = href

            for alvo in CURSOS_ALVO:
                if alvo["codigo"] not in portais:
                    problemas.append(f"{alvo['termo']}: curso não encontrado na listagem")
                    continue
                cursos.append({
                    "codigo": alvo["codigo"],
                    "nome": alvo["termo"],
                    "unidade": config.UNIDADE,
                    "fonte": config.FONTE_CURSOS,
                    "carga_id": carga_id,
                    "coletado_em": coletado_em,
                })

                page.goto(portais[alvo["codigo"]], wait_until="networkidle")
                link_estrutura = page.locator(
                    "a:has-text('Estrutura Curricular'), a:has-text('Currículo'), a:has-text('Matriz')"
                ).first
                if link_estrutura.count() > 0:
                    link_estrutura.click()
                    page.wait_for_load_state("networkidle")

                # A matriz lista blocos "Obrigatórias" e "Optativas"; o último
                # cabeçalho visto define a natureza das disciplinas seguintes.
                obrigatoria = True
                vistos: set[str] = set()
                for tr in page.locator("table tr").all():
                    texto = tr.inner_text().upper()
                    if "OPTATIVA" in texto:
                        obrigatoria = False
                    elif "OBRIGATÓRIA" in texto or "OBRIGATORIA" in texto:
                        obrigatoria = True
                    for cel in tr.locator("td").all():
                        txt = cel.inner_text().strip()
                        if CODIGO_DISCIPLINA_RE.fullmatch(txt) and txt not in vistos:
                            vistos.add(txt)
                            curriculo.append({
                                "curso_codigo": alvo["codigo"],
                                "disciplina_codigo": txt,
                                "obrigatoria": obrigatoria,
                                "fonte": config.FONTE_CURSOS,
                                "carga_id": carga_id,
                                "coletado_em": coletado_em,
                            })
                if not vistos:
                    salvar_debug(page, f"curso_{alvo['codigo']}_matriz")
                    problemas.append(f"{alvo['termo']}: matriz curricular vazia")
        except Exception as e:
            problemas.append(f"erro inesperado: {e}")
        finally:
            browser.close()

    if problemas:
        print("Raspagem de cursos incompleta; nada foi gravado:", file=sys.stderr)
        for p in problemas:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)

    gravar_csv(config.ARQ_CURSOS, CAMPOS_CURSOS, cursos)
    gravar_csv(config.ARQ_CURSO_DISCIPLINA, CAMPOS_CURRICULO, curriculo)
    print(f"{len(cursos)} cursos e {len(curriculo)} relações curso-disciplina em {config.DATA_DIR}")


if __name__ == "__main__":
    run()
