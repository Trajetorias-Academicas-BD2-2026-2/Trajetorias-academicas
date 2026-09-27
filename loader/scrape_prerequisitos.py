
import csv
import os
import sys
import uuid
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

import config
from sigaa_utils import nova_pagina_disfarcada


def run() -> str:
    carga_id = str(uuid.uuid4())
    ingerido_em = datetime.now(timezone.utc).isoformat()
    os.makedirs(config.STAGING_DIR, exist_ok=True)
    out_path = os.path.join(config.STAGING_DIR, f"pre_requisitos_raw_{carga_id}.csv")

    rows = []

    with sync_playwright() as p:
        browser, page = nova_pagina_disfarcada(p)

        url_alvo = "https://sigaa.unb.br/sigaa/public/matriz_curricular/lista.jsf?nivel=G&aba=p-graduacao"
        page.goto(url_alvo, wait_until="networkidle")

        try:
            page.get_by_role("button", name="Ciente").click(timeout=3000)
        except Exception:
            pass

        print(f"[debug] Página de pré-requisitos aberta: {page.url}", file=sys.stderr)

        try:
            radio_todos = page.locator("input[type='radio'][value='todos'], input[type='radio']").last
            if radio_todos.count() > 0:
                radio_todos.click()
            page.get_by_role("button", name="Buscar").click()
            page.wait_for_load_state("networkidle")
        except Exception:
            print("[debug] Falha ao submeter busca para pré-requisitos.", file=sys.stderr)

        table_rows = page.locator("table.listagem tr, table.tabelaRelatorio tr, table tr").all()

        current_disc = ""
        for tr in table_rows:
            cells = [c.inner_text().strip() for c in tr.locator("td").all()]
            full_text = " ".join(cells)

            for c in cells:
                if len(c) >= 6 and c[:3].isalpha() and c[3:].isdigit():
                    if not current_disc:
                        current_disc = c
                    else:

                        pre_req = c
                        if current_disc != pre_req:
                            if not any(r["disciplina_codigo"] == current_disc and r["pre_requisito_codigo"] == pre_req for r in rows):
                                rows.append({
                                    "disciplina_codigo": current_disc,
                                    "pre_requisito_codigo": pre_req,
                                    "carga_id": carga_id,
                                    "ingerido_em": ingerido_em
                                })
            
            if len(cells) == 0:
                current_disc = ""

        browser.close()

    if rows:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["disciplina_codigo", "pre_requisito_codigo", "carga_id", "ingerido_em"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"{len(rows)} pré-requisitos gravados em {out_path}")
    else:
        print("Nenhum pré-requisito detetado nesta passagem.")

    return out_path


if __name__ == "__main__":
    run()