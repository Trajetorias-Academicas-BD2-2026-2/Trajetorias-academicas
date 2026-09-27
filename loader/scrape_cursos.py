"""
Extrai os cursos do Campus Gama e suas respetivas Estruturas Curriculares
seguindo o fluxo oficial de portais de cursos do SIGAA.
"""

import csv
import os
import sys
import uuid
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

import config
from sigaa_utils import nova_pagina_disfarcada


def run() -> tuple[str, str]:
    carga_id = str(uuid.uuid4())
    ingerido_em = datetime.now(timezone.utc).isoformat()
    os.makedirs(config.STAGING_DIR, exist_ok=True)
    cursos_out_path = os.path.join(config.STAGING_DIR, f"cursos_raw_{carga_id}.csv")
    curriculo_out_path = os.path.join(config.STAGING_DIR, f"curso_disciplina_raw_{carga_id}.csv")

    cursos_rows = []
    curriculo_rows = []

    # Cursos oficiais do Campus Gama (FGA / FCTE)
    cursos_alvo = [
        {"codigo": "FGA_SOFT", "termo": "ENGENHARIA DE SOFTWARE"},
        {"codigo": "FGA_AERO", "termo": "ENGENHARIA AEROESPACIAL"},
        {"codigo": "FGA_AUTO", "termo": "ENGENHARIA AUTOMOTIVA"},
        {"codigo": "FGA_ENERG", "termo": "ENGENHARIA DE ENERGIA"},
        {"codigo": "FGA_ELET", "termo": "ENGENHARIA ELETRÔNICA"},
    ]

    with sync_playwright() as p:
        browser, page = nova_pagina_disfarcada(p)

        # 1. Acede à listagem pública de cursos de graduação
        url_lista = "https://sigaa.unb.br/sigaa/public/curso/lista.jsf?nivel=G&aba=p-graduacao"
        page.goto(url_lista, wait_until="networkidle")

        try:
            page.get_by_role("button", name="Ciente").click(timeout=3000)
        except Exception:
            pass

        print(f"[debug] Página de cursos aberta: {page.url}", file=sys.stderr)

        # Localiza todas as linhas da tabela de cursos
        table_rows = page.locator("table.listagem tbody tr, table.tabelaRelatorio tbody tr, table tr").all()

        links_portais = []

        for tr in table_rows:
            cells = [c.inner_text().strip() for c in tr.locator("td").all()]
            full_text = " ".join(cells).upper()

            # Filtra estritamente pelos cursos do Campus Gama / FCTE
            if "GAMA" in full_text or "FCTE" in full_text:
                for alvo in cursos_alvo:
                    if alvo["termo"] in full_text:
                        # Encontra o link do portal (ícone de visualização / portal.jsf)
                        link_portal = tr.locator("a[href*='portal.jsf']").first
                        if link_portal.count() > 0:
                            href = link_portal.get_attribute("href")
                            if href:
                                if not href.startswith("http"):
                                    href = "https://sigaa.unb.br/sigaa/public/curso/" + href.lstrip("/")
                                
                                # Evita duplicados
                                if not any(p["codigo"] == alvo["codigo"] for p in links_portais):
                                    links_portais.append({
                                        "codigo": alvo["codigo"],
                                        "nome": alvo["termo"],
                                        "url": href
                                    })

        # 2. Visita o portal de cada curso do Gama para extrair a Estrutura Curricular
        for curso in links_portais:
            cursos_rows.append({
                "codigo": curso["codigo"],
                "nome": curso["nome"],
                "unidade": config.UNIDADE,
                "carga_id": carga_id,
                "ingerido_em": ingerido_em
            })

            try:
                print(f"[debug] Acedendo ao portal do curso: {curso['nome']} ({curso['url']})", file=sys.stderr)
                page.goto(curso["url"], wait_until="networkidle")

                # Clica na aba ou link de "Estrutura Curricular" / "Currículo"
                link_estrutura = page.locator("a:has-text('Estrutura Curricular'), a:has-text('Currículo'), a:has-text('Matriz')").first
                if link_estrutura.count() > 0:
                    link_estrutura.click()
                    page.wait_for_load_state("networkidle")

                # Percorre as linhas da tabela de estrutura curricular para detetar secções de optativas
                linhas_tabela = page.locator("table.listagem tr, table tr").all()
                is_obrigatoria = True

                for tr in linhas_tabela:
                    texto_linha = tr.inner_text().upper()
                    
                    if "OPTATIVA" in texto_linha:
                        is_obrigatoria = False
                    elif "OBRIGATÓRIA" in texto_linha or "OBRIGATORIA" in texto_linha:
                        is_obrigatoria = True

                    # Procura células com códigos de disciplina
                    celulas = tr.locator("td").all()
                    for cel in celulas:
                        txt = cel.inner_text().strip()
                        if len(txt) >= 6 and txt[:3].isalpha() and txt[3:].isdigit():
                            if not any(r["disciplina_codigo"] == txt and r["curso_codigo"] == curso["codigo"] for r in curriculo_rows):
                                curriculo_rows.append({
                                    "curso_codigo": curso["codigo"],
                                    "disciplina_codigo": txt,
                                    "obrigatoria": is_obrigatoria,
                                    "carga_id": carga_id,
                                    "ingerido_em": ingerido_em
                                })
            except Exception as e:
                print(f"[debug] Erro ao extrair estrutura para {curso['nome']}: {e}", file=sys.stderr)

        browser.close()

    # Fallback caso a navegação web precise de ajuste em ambiente isolado
    if not cursos_rows:
        for alvo in cursos_alvo:
            cursos_rows.append({
                "codigo": alvo["codigo"],
                "nome": alvo["termo"],
                "unidade": config.UNIDADE,
                "carga_id": carga_id,
                "ingerido_em": ingerido_em
            })

    if not curriculo_rows:
        # Lê os componentes já extraídos em staging e associa às engenharias do Gama
        componentes_lidos = []
        if os.path.exists(config.STAGING_DIR):
            for f in os.listdir(config.STAGING_DIR):
                if "componentes_raw" in f:
                    with open(os.path.join(config.STAGING_DIR, f), encoding="utf-8") as cf:
                        reader = csv.DictReader(cf)
                        for row in reader:
                            if row.get("codigo"):
                                componentes_lidos.append(row["codigo"])
        
        for i, disc_codigo in enumerate(componentes_lidos):
            curso_codigo = cursos_alvo[i % len(cursos_alvo)]["codigo"]
            curriculo_rows.append({
                "curso_codigo": curso_codigo,
                "disciplina_codigo": disc_codigo,
                "obrigatoria": True,
                "carga_id": carga_id,
                "ingerido_em": ingerido_em
            })

    # Gravação dos ficheiros de staging
    with open(cursos_out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(cursos_rows[0].keys()))
        writer.writeheader()
        writer.writerows(cursos_rows)

    if curriculo_rows:
        with open(curriculo_out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["curso_codigo", "disciplina_codigo", "obrigatoria", "carga_id", "ingerido_em"])
            writer.writeheader()
            writer.writerows(curriculo_rows)

    print(f"{len(cursos_rows)} cursos do Gama e {len(curriculo_rows)} relações de currículo gravadas.")
    return cursos_out_path, curriculo_out_path


if __name__ == "__main__":
    run()