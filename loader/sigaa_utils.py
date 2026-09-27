"""Utilitários compartilhados pelos dois scrapers."""

from playwright.sync_api import Locator


def select_by_contains(select: Locator, texto: str) -> None:
    """Seleciona a opção cujo texto contém `texto` (sem diferenciar
    maiúsculas/acentos de caixa, e sem exigir correspondência exata).

    Mais tolerante que select_option(label=...), que exige o texto
    idêntico — útil porque o mesmo rótulo (ex.: nome de unidade) pode
    aparecer com pequenas variações entre páginas do SIGAA (sufixo de
    campus presente/ausente, espaços extras, etc.).
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
    checkbox ao lado do rótulo estiver marcada — sem isso, o valor
    escolhido no <select> é ignorado silenciosamente pelo servidor.
    Marca essa checkbox se ela existir na linha e ainda não estiver
    marcada (não faz nada se a linha não tiver checkbox)."""
    checkbox = row.locator("input[type=checkbox]")
    if checkbox.count() > 0 and not checkbox.first.is_checked():
        checkbox.first.check()


def nova_pagina_disfarcada(playwright):
    """Abre um browser e uma página tentando parecer um navegador comum,
    não uma automação. Alguns sites (o SIGAA parece ser um deles)
    redirecionam para a home quando detectam `navigator.webdriver`,
    um sinalizador que o Chromium liga sozinho quando controlado por
    ferramentas como o Playwright.

    Retorna (browser, page) — quem chamar é responsável por fechar o
    browser no final.
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
