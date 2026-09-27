"""
Extrai a oferta de turmas de um semestre do SIGAA (fonte: sigaa_turmas)
e grava um CSV de staging em STAGING_DIR/turmas_raw_<carga_id>.csv.

Uso:
    python scrape_turmas.py

O formulário é JSF (postback com ViewState) — por isso usamos um browser
real via Playwright em vez de requests/BeautifulSoup puro. Selecionamos
os campos por texto visível, não por atributos internos, porque esses
atributos mudam entre versões do JSF.
"""

import csv
import os
import sys
import uuid
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

import config
from sigaa_utils import ativar_checkbox_da_linha, nova_pagina_disfarcada, select_by_contains


def infer_turno(horario: str) -> str:
    """Deriva o turno a partir da notação SIGAA de horário (ex.: '246M34').
    M = matutino, T = vespertino -> tratamos ambos como DIURNO; N = NOTURNO.
    Se o mesmo horário combinar letras de turnos diferentes, é INTEGRAL."""
    letras = {c for c in horario.upper() if c in ("M", "T", "N")}
    if letras == {"N"}:
        return "NOTURNO"
    if letras and "N" not in letras:
        return "DIURNO"
    if len(letras) > 1:
        return "INTEGRAL"
    return "DIURNO"


def run() -> str:
    carga_id = str(uuid.uuid4())
    ingerido_em = datetime.now(timezone.utc).isoformat()
    os.makedirs(config.STAGING_DIR, exist_ok=True)
    out_path = os.path.join(config.STAGING_DIR, f"turmas_raw_{carga_id}.csv")

    rows = []
    with sync_playwright() as p:
        browser, page = nova_pagina_disfarcada(p)

        page.goto("https://sigaa.unb.br/sigaa/public/home.jsf", wait_until="networkidle")

        page.locator("a[href*='turmas/listar.jsf?aba=p-ensino']").evaluate("node => node.click()")

        page.wait_for_load_state("networkidle")

        try:
            page.get_by_role("button", name="Ciente").click(timeout=3000)
        except Exception:
            pass

        page.screenshot(path=os.path.join(config.STAGING_DIR, "debug_turmas_antes.png"))
        print(f"[debug] URL logo após abrir: {page.url}", file=sys.stderr)

        try:
            select_by_contains(
                page.locator("xpath=//tr[contains(., 'Nível de Ensino')]//select").first,
                config.NIVEL_ENSINO,
            )
            page.wait_for_load_state("networkidle")

            unidade_row = page.locator("xpath=//tr[contains(., 'Unidade')]")
            ativar_checkbox_da_linha(unidade_row)
            select_by_contains(unidade_row.locator("select").first, config.UNIDADE)
            page.wait_for_load_state("networkidle")
            ano_periodo_row = page.locator("xpath=//tr[contains(., 'Ano - Período')]")
            texto_input = ano_periodo_row.locator("input[type=text]")
            if texto_input.count() > 0:
                texto_input.first.fill(f"{config.ANO}.{config.PERIODO}")
            periodo_select = ano_periodo_row.locator("select")
            if periodo_select.count() > 0:
                select_by_contains(periodo_select.first, config.PERIODO)

            page.get_by_role("button", name="Buscar").click()
            page.wait_for_load_state("networkidle")
        except Exception:
            os.makedirs(config.STAGING_DIR, exist_ok=True)
            page.screenshot(path=os.path.join(config.STAGING_DIR, "debug_turmas.png"), full_page=True)
            with open(os.path.join(config.STAGING_DIR, "debug_turmas.html"), "w", encoding="utf-8") as f:
                f.write(page.content())
            print(
                "Falha ao preencher o formulário de turmas. Salvei "
                f"{config.STAGING_DIR}/debug_turmas.png e debug_turmas.html "
                f"para inspeção — envie esses dois arquivos. URL no momento da falha: {page.url}",
                file=sys.stderr,
            )
            raise

        table_rows = page.locator("table.listagem tbody tr").all()
        if not table_rows:
            page.screenshot(path=os.path.join(config.STAGING_DIR, "debug_turmas_resultado.png"), full_page=True)
            with open(os.path.join(config.STAGING_DIR, "debug_turmas_resultado.html"), "w", encoding="utf-8") as f:
                f.write(page.content())
            print(
                "A busca rodou, mas nenhuma linha de resultado bateu com o "
                f"seletor esperado. Salvei {config.STAGING_DIR}/debug_turmas_resultado.png "
                f"e debug_turmas_resultado.html — envie esses dois arquivos. URL atual: {page.url}",
                file=sys.stderr,
            )

        current_codigo = ""
        current_nome = ""

        for tr in table_rows:
            cells = [c.inner_text().strip() for c in tr.locator("td").all()]
            if not cells:
                continue

            full_text = " ".join(cells)

            if len(cells) < 5 or ("-" in full_text and len(cells) <= 3):
                if "-" in full_text:
                    limpo = full_text.replace("🔍", "").strip()
                    parts = limpo.split("-", 1)
                    current_codigo = parts[0].strip()
                    current_nome = parts[1].strip()
                continue

            if len(cells) >= 5:
                local = cells[-1] if len(cells) > 0 else ""

                digitos_indices = [i for i, c in enumerate(cells) if c.isdigit()]
                vagas_ofertadas = 0
                vagas_ocupadas = 0

                if len(digitos_indices) >= 2:
                    vagas_ofertadas = int(cells[digitos_indices[-2]])
                    vagas_ocupadas = int(cells[digitos_indices[-1]])
                elif len(digitos_indices) == 1:
                    vagas_ofertadas = int(cells[digitos_indices[0]])

                if vagas_ofertadas < vagas_ocupadas:
                    vagas_ofertadas, vagas_ocupadas = vagas_ocupadas, vagas_ofertadas

                horario_raw = ""
                for c in cells:
                    if any(turno_letra in c.upper() for turno_letra in ["M", "T", "N"]) and len(c) <= 30:
                        horario_raw = c
                        break
                if not horario_raw and len(cells) >= 4:
                    horario_raw = cells[3]

                horario_limpo = horario_raw.split("(")[0].strip()[:10]

                docente_raw = cells[2] if len(cells) > 2 else ""
                docente = docente_raw.split("(")[0].strip() if docente_raw else ""

                turma_codigo = cells[0] if len(cells) > 0 else "01"

                rows.append(
                    {
                        "disciplina_codigo": current_codigo,
                        "disciplina_nome": current_nome,
                        "turma_codigo": turma_codigo[:10],
                        "docente": docente,
                        "horario": horario_limpo,
                        "vagas_ofertadas": vagas_ofertadas,
                        "vagas_ocupadas": vagas_ocupadas,
                        "local": local[:50],
                        "turno": infer_turno(horario_limpo),
                        "ano": config.ANO,
                        "periodo": config.PERIODO,
                        "fonte": config.FONTE_TURMAS,
                        "carga_id": carga_id,
                        "ingerido_em": ingerido_em,
                    }
                )

        browser.close()

    if not rows:
        print("Nenhuma turma encontrada — confira os seletores em config.py e a página.", file=sys.stderr)
        sys.exit(1)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(rows)} turmas gravadas em {out_path}")
    return out_path


if __name__ == "__main__":
    run()
