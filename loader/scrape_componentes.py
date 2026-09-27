"""
Extrai disciplinas (componentes curriculares) e seus pré-requisitos do
SIGAA (fonte: sigaa_componentes). Grava dois CSVs de staging:
  - componentes_raw_<carga_id>.csv   (código, nome, carga horária, unidade)
  - pre_requisitos_raw_<carga_id>.csv (disciplina_codigo, pre_requisito_codigo)

O SIGAA mostra o pré-requisito só na página de detalhe de cada componente
(um "olho"/link por linha da lista de busca) — por isso este script faz
duas passadas: lista os componentes e depois abre o detalhe de cada um.
Isso é mais lento; para a E1, rodar restrito a uma unidade/curso é
suficiente (ver config.UNIDADE).
"""

import csv
import os
import re
import sys
import uuid
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

import config
from sigaa_utils import ativar_checkbox_da_linha, nova_pagina_disfarcada, select_by_contains


def run() -> tuple[str, str]:
    carga_id = str(uuid.uuid4())
    ingerido_em = datetime.now(timezone.utc).isoformat()
    os.makedirs(config.STAGING_DIR, exist_ok=True)
    componentes_path = os.path.join(config.STAGING_DIR, f"componentes_raw_{carga_id}.csv")
    prereq_path = os.path.join(config.STAGING_DIR, f"pre_requisitos_raw_{carga_id}.csv")

    componentes = []
    pre_requisitos = []

    with sync_playwright() as p:
        browser, page = nova_pagina_disfarcada(p)


        page.goto("https://sigaa.unb.br/sigaa/public/home.jsf", wait_until="networkidle")

        page.locator("a[href*='busca_componentes.jsf?aba=p-ensino']").evaluate("node => node.click()")

        page.wait_for_load_state("networkidle")

        try:
            page.get_by_role("button", name="Ciente").click(timeout=3000)
        except Exception:
            pass

        os.makedirs(config.STAGING_DIR, exist_ok=True)
        page.screenshot(path=os.path.join(config.STAGING_DIR, "debug_componentes_antes.png"))
        print(f"[debug] URL logo após abrir: {page.url}", file=sys.stderr)

        try:
            if config.TESTE_MINIMO:
                print("[debug] TESTE_MINIMO ativo — não vou mexer em nenhum campo", file=sys.stderr)
            else:
                nivel_row = page.locator("xpath=//tr[contains(., 'Nível de Ensino')]")
                select_by_contains(nivel_row.locator("select").first, config.NIVEL_ENSINO)
                page.wait_for_load_state("networkidle")

                unidade_row = page.locator("xpath=//tr[contains(., 'Unidade Responsável')]")
                if config.TESTE_SEM_UNIDADE:
                    print("[debug] TESTE_SEM_UNIDADE ativo — pulando o filtro de unidade", file=sys.stderr)
                else:
                    ativar_checkbox_da_linha(unidade_row)
                    select_by_contains(unidade_row.locator("select").first, config.UNIDADE)
                page.wait_for_load_state("networkidle")

            print(
                f"[debug] navigator.webdriver = {page.evaluate('navigator.webdriver')}",
                file=sys.stderr,
            )
            page.screenshot(path=os.path.join(config.STAGING_DIR, "debug_componentes_antes_do_clique.png"))
            with open(
                os.path.join(config.STAGING_DIR, "debug_componentes_antes_do_clique.html"),
                "w",
                encoding="utf-8",
            ) as f:
                f.write(page.content())
            hidden_inputs = page.locator("input[type=hidden]").all()
            print(f"[debug] total de campos hidden no form: {len(hidden_inputs)}", file=sys.stderr)
            for h in hidden_inputs:
                nome = h.get_attribute("name")
                valor = h.get_attribute("value")
                valor_curto = (valor[:60] + "...") if valor and len(valor) > 60 else valor
                print(f"[debug]   hidden: name={nome!r} value={valor_curto!r}", file=sys.stderr)
            form = page.locator("form").first
            print(f"[debug] form action: {form.get_attribute('action')}", file=sys.stderr)
            botao = page.get_by_role("button", name="Buscar Componentes")
            print(f"[debug] botão Buscar Componentes — onclick: {botao.get_attribute('onclick')}", file=sys.stderr)

            respostas = []
            page.on(
                "response",
                lambda r: respostas.append((r.status, r.url))
                if r.request.is_navigation_request()
                else None,
            )

            botao.click()
            page.wait_for_load_state("networkidle")

            print("[debug] respostas de navegação durante o clique:", file=sys.stderr)
            for status, url in respostas:
                print(f"[debug]   {status} {url}", file=sys.stderr)
            print(f"[debug] cookies após o clique: {[c['name'] for c in page.context.cookies()]}", file=sys.stderr)
        except Exception:
            os.makedirs(config.STAGING_DIR, exist_ok=True)
            page.screenshot(path=os.path.join(config.STAGING_DIR, "debug_componentes.png"), full_page=True)
            with open(os.path.join(config.STAGING_DIR, "debug_componentes.html"), "w", encoding="utf-8") as f:
                f.write(page.content())
            print(
                "Falha ao preencher o formulário de componentes. Salvei "
                f"{config.STAGING_DIR}/debug_componentes.png e debug_componentes.html "
                f"para inspeção — envie esses dois arquivos. URL no momento da falha: {page.url}",
                file=sys.stderr,
            )
            raise

        linhas = page.locator("table.listagem tbody tr").all()
        if not linhas:
            os.makedirs(config.STAGING_DIR, exist_ok=True)
            page.screenshot(path=os.path.join(config.STAGING_DIR, "debug_componentes.png"), full_page=True)
            with open(os.path.join(config.STAGING_DIR, "debug_componentes.html"), "w", encoding="utf-8") as f:
                f.write(page.content())
            print(
                "A busca rodou, mas nenhuma linha de resultado bateu com o "
                f"seletor esperado. Salvei {config.STAGING_DIR}/debug_componentes.png "
                f"e debug_componentes.html — envie esses dois arquivos. URL atual: {page.url}",
                file=sys.stderr,
            )
        detalhe_links = []
        for tr in linhas:
            cells = [c.inner_text().strip() for c in tr.locator("td").all()]
            if len(cells) < 3:
                continue

            codigo = cells[0]
            nome = cells[1]

            carga_horaria = "0"
            for cell in cells[2:]:
                limpo = re.sub(r"\D", "", cell)
                if limpo.isdigit() and 1 <= int(limpo) <= 500:
                    carga_horaria = limpo
                    break

            componentes.append(
                {
                    "codigo": codigo,
                    "nome": nome,
                    "carga_horaria": carga_horaria,
                    "unidade": config.UNIDADE,
                    "fonte": config.FONTE_COMPONENTES,
                    "carga_id": carga_id,
                    "ingerido_em": ingerido_em,
                }
            )
            link = tr.locator("a[title*='Exibir']").first
            if link.count() > 0:
                detalhe_links.append((codigo, link))

        for codigo, link in detalhe_links:
            try:
                link.click()
                page.wait_for_load_state("networkidle")
                texto = page.locator("body").inner_text()
                m = re.search(r"Pré-Requisitos?:?\s*(.+)", texto)
                if m:
                    for prereq_codigo in re.findall(r"[A-Z]{2,4}\d{4}", m.group(1)):
                        pre_requisitos.append(
                            {
                                "disciplina_codigo": codigo,
                                "pre_requisito_codigo": prereq_codigo,
                                "fonte": config.FONTE_COMPONENTES,
                                "carga_id": carga_id,
                                "ingerido_em": ingerido_em,
                            }
                        )
                page.go_back()
                page.wait_for_load_state("networkidle")
            except Exception as e:
                print(f"Aviso: falha ao ler pré-requisitos de {codigo}: {e}", file=sys.stderr)

        browser.close()

    if not componentes:
        os.makedirs(config.STAGING_DIR, exist_ok=True)
        print("Nenhum componente encontrado — confira os seletores em config.py.", file=sys.stderr)
        sys.exit(1)

    with open(componentes_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(componentes[0].keys()))
        writer.writeheader()
        writer.writerows(componentes)

    with open(prereq_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["disciplina_codigo", "pre_requisito_codigo", "fonte", "carga_id", "ingerido_em"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(pre_requisitos)

    print(f"{len(componentes)} componentes em {componentes_path}")
    print(f"{len(pre_requisitos)} pré-requisitos em {prereq_path}")
    return componentes_path, prereq_path


if __name__ == "__main__":
    run()
