"""
Extrai a oferta de turmas do SIGAA (fonte: sigaa_turmas), um CSV por
semestre em DATA_DIR/turmas_<ano>_<periodo>.csv.

Uso:
    python scrape_turmas.py

Percorre todos os semestres de config.semestres_da_carga() (só semestres
encerrados). Com RASPAR=auto, pula semestres que já têm CSV versionado.
Qualquer semestre sem resultado interrompe a carga com erro: um semestre
vazio silencioso viraria "queda de oferta" nas análises.
"""

import sys
import uuid

from playwright.sync_api import Page, sync_playwright

import config
from parsing import extrair_horario, inferir_turno, parse_vagas
from semestres import rotulo
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

CAMPOS = [
    "disciplina_codigo", "disciplina_nome", "turma_codigo", "docente", "horario",
    "turno", "vagas_ofertadas", "vagas_ocupadas", "local", "ano", "periodo",
    "fonte", "carga_id", "coletado_em",
]


def preencher_ano_periodo(page: Page, ano: int, periodo: int) -> None:
    """O campo 'Ano - Período' pode vir como dois inputs, input + select,
    ou um input único 'AAAA.P'. Cobre os três e falha se não achar nenhum,
    para nunca buscar silenciosamente o semestre padrão do formulário."""
    linha = page.locator("xpath=//tr[contains(., 'Ano') and contains(., 'Per')]").first
    inputs = linha.locator("input[type=text]")
    selects = linha.locator("select")
    if inputs.count() >= 2:
        inputs.nth(0).fill(str(ano))
        inputs.nth(1).fill(str(periodo))
    elif inputs.count() == 1 and selects.count() >= 1:
        inputs.first.fill(str(ano))
        select_by_contains(selects.first, str(periodo))
    elif inputs.count() == 1:
        inputs.first.fill(f"{ano}.{periodo}")
    else:
        raise RuntimeError("Campo 'Ano - Período' não encontrado no formulário")


def raspar_semestre(page: Page, ano: int, periodo: int) -> list[dict]:
    carga_id = str(uuid.uuid4())
    coletado_em = agora_utc()

    abrir_pela_home(page, "turmas/listar.jsf?aba=p-ensino")
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

        preencher_ano_periodo(page, ano, periodo)
        page.get_by_role("button", name="Buscar").click()
        page.wait_for_load_state("networkidle")
    except Exception:
        salvar_debug(page, f"turmas_{ano}_{periodo}_formulario")
        raise

    linhas: list[dict] = []
    codigo_atual, nome_atual = "", ""
    for tr in page.locator("table.listagem tbody tr").all():
        cells = [c.inner_text().strip() for c in tr.locator("td").all()]
        if not cells:
            continue
        texto = " ".join(cells)

        # Linha de agrupamento: "FGA0242 - NOME DA DISCIPLINA"
        if len(cells) < 5:
            if "-" in texto:
                codigo, _, nome = texto.replace("🔍", "").strip().partition("-")
                codigo_atual, nome_atual = codigo.strip(), nome.strip()
            continue

        horario = extrair_horario(cells)
        ofertadas, ocupadas = parse_vagas(cells)
        docente = cells[2].split("(")[0].strip() if len(cells) > 2 else ""

        linhas.append({
            "disciplina_codigo": codigo_atual,
            "disciplina_nome": nome_atual,
            "turma_codigo": cells[0],
            "docente": docente,
            "horario": horario,
            "turno": inferir_turno(horario),
            "vagas_ofertadas": "" if ofertadas is None else ofertadas,
            "vagas_ocupadas": "" if ocupadas is None else ocupadas,
            "local": cells[-1][:255],
            "ano": ano,
            "periodo": periodo,
            "fonte": config.FONTE_TURMAS,
            "carga_id": carga_id,
            "coletado_em": coletado_em,
        })

    if not linhas:
        salvar_debug(page, f"turmas_{ano}_{periodo}_resultado")
        raise RuntimeError(f"Nenhuma turma encontrada em {rotulo(ano, periodo)}")
    return linhas


def run() -> None:
    pendentes = [
        (a, p) for a, p in config.semestres_da_carga()
        if precisa_raspar(config.arq_turmas(a, p))
    ]
    if not pendentes:
        print("Turmas: todos os semestres já estão em", config.DATA_DIR)
        return

    with sync_playwright() as pw:
        browser, page = nova_pagina_disfarcada(pw)
        try:
            for ano, periodo in pendentes:
                linhas = raspar_semestre(page, ano, periodo)
                destino = gravar_csv(config.arq_turmas(ano, periodo), CAMPOS, linhas)
                print(f"{rotulo(ano, periodo)}: {len(linhas)} turmas em {destino}")
        except Exception as e:
            print(f"Falha na raspagem de turmas: {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            browser.close()


if __name__ == "__main__":
    run()
