"""Utilitários compartilhados pelos scrapers."""

import csv
import os
import sys
from datetime import datetime, timezone

from playwright.sync_api import Locator, Page

import config


def agora_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def select_by_contains(select: Locator, texto: str) -> None:
    """Seleciona a opção com texto igual a `texto` (sem diferenciar
    maiúsculas); se não houver, a primeira que CONTÉM `texto`.

    Tenta a correspondência exata primeiro porque a por substring pode
    errar: "GRADUAÇÃO" está contido em "PÓS-GRADUAÇÃO".
    """
    opcoes = select.locator("option").all_text_contents()
    alvo = texto.strip().upper()
    for i, opcao in enumerate(opcoes):
        if opcao.strip().upper() == alvo:
            select.select_option(index=i)
            return
    for i, opcao in enumerate(opcoes):
        if alvo in opcao.strip().upper():
            select.select_option(index=i)
            return
    raise ValueError(
        f"Nenhuma opção contendo '{texto}' encontrada. "
        f"Opções disponíveis (primeiras 15): {opcoes[:15]}"
    )


def ativar_checkbox_da_linha(row: Locator) -> None:
    """Alguns critérios do formulário do SIGAA só são aplicados se a
    checkbox ao lado do rótulo estiver marcada; sem isso, o valor
    escolhido no <select> é ignorado silenciosamente pelo servidor."""
    checkbox = row.locator("input[type=checkbox]")
    if checkbox.count() > 0 and not checkbox.first.is_checked():
        checkbox.first.check()


def nova_pagina_disfarcada(playwright):
    """Abre um browser e uma página com cara de navegador comum. O SIGAA
    redireciona para a home quando detecta `navigator.webdriver`, que o
    Chromium liga sozinho quando controlado pelo Playwright.

    Retorna (browser, page); quem chamar fecha o browser.
    """
    browser = playwright.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1366, "height": 768},
        locale="pt-BR",
    )
    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    )
    page = context.new_page()
    return browser, page


def abrir_pela_home(page: Page, trecho_href: str) -> None:
    """Chega ao formulário clicando no link da home, como um usuário faria.
    Abrir a URL do formulário direto cria uma sessão JSF inválida: o
    'Buscar' devolve 302 para a home (ver docs/adr/0002-...)."""
    page.goto(config.HOME_URL, wait_until="networkidle")
    page.locator(f"a[href*='{trecho_href}']").first.evaluate("node => node.click()")
    page.wait_for_load_state("networkidle")
    fechar_aviso(page)


def fechar_aviso(page: Page) -> None:
    try:
        page.get_by_role("button", name="Ciente").click(timeout=3000)
    except Exception:
        pass


def salvar_debug(page: Page, nome: str) -> None:
    """Salva print e HTML da página em DEBUG_DIR para investigar falhas."""
    os.makedirs(config.DEBUG_DIR, exist_ok=True)
    base = os.path.join(config.DEBUG_DIR, nome)
    page.screenshot(path=f"{base}.png", full_page=True)
    with open(f"{base}.html", "w", encoding="utf-8") as f:
        f.write(page.content())
    print(f"[debug] {base}.png e {base}.html salvos (URL: {page.url})", file=sys.stderr)


def gravar_csv(nome_arquivo: str, campos: list[str], linhas: list[dict]) -> str:
    """Grava em DATA_DIR de forma atômica: escreve num .tmp e renomeia, para
    que uma raspagem interrompida não deixe um CSV pela metade versionado."""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    destino = os.path.join(config.DATA_DIR, nome_arquivo)
    tmp = destino + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(linhas)
    os.replace(tmp, destino)
    return destino


def precisa_raspar(*nomes_arquivo: str) -> bool:
    """Decide se o recorte precisa ser (re)raspado, conforme config.RASPAR."""
    faltando = [n for n in nomes_arquivo if not os.path.exists(os.path.join(config.DATA_DIR, n))]
    if config.RASPAR == "1":
        return True
    if config.RASPAR == "0":
        if faltando:
            raise SystemExit(f"RASPAR=0, mas faltam arquivos em {config.DATA_DIR}: {faltando}")
        return False
    return bool(faltando)
