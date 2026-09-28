"""
Extrai disciplinas (componentes curriculares) da unidade e seus
pré-requisitos (fonte: sigaa_componentes). Grava em DATA_DIR:
  - componentes.csv     código, nome, carga horária, unidade e a expressão
                        de pré-requisito exatamente como o SIGAA mostra
  - pre_requisitos.csv  um par (disciplina, código citado na expressão) por linha

O pré-requisito só aparece na página de detalhe de cada componente, por
isso o script faz duas passadas: lista os componentes e depois abre o
detalhe de cada um.
"""

import re
import sys
import uuid

from playwright.sync_api import sync_playwright

import config
from parsing import codigos_da_expressao, extrair_expressao_prerequisito
from sigaa_utils import (
    abrir_pela_home,
    agora_utc,
    ativar_checkbox_da_linha,
    gravar_csv,
    nova_pagina_disfarcada,
    precisa_raspar,
    salvar_debug,
    select_by_contains,
)

CAMPOS_COMPONENTES = [
    "codigo", "nome", "carga_horaria", "unidade", "pre_requisito_expressao",
    "fonte", "carga_id", "coletado_em",
]
CAMPOS_PREREQ = ["disciplina_codigo", "pre_requisito_codigo", "fonte", "carga_id", "coletado_em"]


def run() -> None:
    if not precisa_raspar(config.ARQ_COMPONENTES, config.ARQ_PRE_REQUISITOS):
        print("Componentes: já estão em", config.DATA_DIR)
        return

    carga_id = str(uuid.uuid4())
    coletado_em = agora_utc()
    componentes: list[dict] = []
    pre_requisitos: list[dict] = []
    falhas_detalhe: list[str] = []

    with sync_playwright() as pw:
        browser, page = nova_pagina_disfarcada(pw)
        try:
            abrir_pela_home(page, "busca_componentes.jsf?aba=p-ensino")
            try:
                nivel_row = page.locator("xpath=//tr[contains(., 'Nível de Ensino')]")
                select_by_contains(nivel_row.locator("select").first, config.NIVEL_ENSINO)
                page.wait_for_load_state("networkidle")

                unidade_row = page.locator("xpath=//tr[contains(., 'Unidade Responsável')]")
                ativar_checkbox_da_linha(unidade_row)
                select_by_contains(unidade_row.locator("select").first, config.UNIDADE)
                page.wait_for_load_state("networkidle")

                page.get_by_role("button", name="Buscar Componentes").click()
                page.wait_for_load_state("networkidle")
            except Exception:
                salvar_debug(page, "componentes_formulario")
                raise

            detalhes = []
            for tr in page.locator("table.listagem tbody tr").all():
                cells = [c.inner_text().strip() for c in tr.locator("td").all()]
                if len(cells) < 3:
                    continue
                carga_horaria = ""
                for cell in cells[2:]:
                    digitos = re.sub(r"\D", "", cell)
                    if digitos and 1 <= int(digitos) <= 500:
                        carga_horaria = digitos
                        break
                componentes.append({
                    "codigo": cells[0],
                    "nome": cells[1],
                    "carga_horaria": carga_horaria,
                    "unidade": config.UNIDADE,
                    "pre_requisito_expressao": "",
                    "fonte": config.FONTE_COMPONENTES,
                    "carga_id": carga_id,
                    "coletado_em": coletado_em,
                })
                link = tr.locator("a[title*='Exibir']").first
                if link.count() > 0:
                    detalhes.append((len(componentes) - 1, link))

            if not componentes:
                salvar_debug(page, "componentes_resultado")
                raise RuntimeError("Nenhum componente encontrado")

            for indice, link in detalhes:
                codigo = componentes[indice]["codigo"]
                try:
                    link.click()
                    page.wait_for_load_state("networkidle")
                    expressao = extrair_expressao_prerequisito(page.locator("body").inner_text())
                    componentes[indice]["pre_requisito_expressao"] = expressao
                    for citado in codigos_da_expressao(expressao):
                        if citado != codigo:
                            pre_requisitos.append({
                                "disciplina_codigo": codigo,
                                "pre_requisito_codigo": citado,
                                "fonte": config.FONTE_COMPONENTES,
                                "carga_id": carga_id,
                                "coletado_em": coletado_em,
                            })
                    page.go_back()
                    page.wait_for_load_state("networkidle")
                except Exception as e:
                    falhas_detalhe.append(codigo)
                    print(f"Aviso: falha ao ler o detalhe de {codigo}: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Falha na raspagem de componentes: {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            browser.close()

    # Pré-requisito faltando em muitas disciplinas distorce o ranking de
    # "disciplinas que mais travam a grade": melhor falhar do que gravar.
    if detalhes and len(falhas_detalhe) > 0.05 * len(detalhes):
        print(
            f"{len(falhas_detalhe)} de {len(detalhes)} detalhes falharam (> 5%); "
            "nada foi gravado. Rode de novo.",
            file=sys.stderr,
        )
        sys.exit(1)

    gravar_csv(config.ARQ_COMPONENTES, CAMPOS_COMPONENTES, componentes)
    gravar_csv(config.ARQ_PRE_REQUISITOS, CAMPOS_PREREQ, pre_requisitos)
    print(f"{len(componentes)} componentes e {len(pre_requisitos)} pré-requisitos em {config.DATA_DIR}")
    if falhas_detalhe:
        print(f"Aviso: detalhe não lido para {falhas_detalhe}", file=sys.stderr)


if __name__ == "__main__":
    run()
