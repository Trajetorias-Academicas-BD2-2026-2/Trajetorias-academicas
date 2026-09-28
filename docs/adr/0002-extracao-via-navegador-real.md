# ADR-0002: A extração do SIGAA usa um navegador real e o recorte raspado é versionado no repositório

- **Status:** aceito
- **Data:** 2026-09-28
- **Decisores:** Squad G2 — ⟨PREENCHER: nomes dos integrantes⟩

## Contexto

Os dados vêm de três páginas públicas do SIGAA (Consulta de Turmas, Busca
de Componentes Curriculares e listagem de cursos), que são formulários
JSF com postback, sem API. Dois comportamentos só apareceram testando
contra o site real:

- Abrir a URL de busca direto cria uma sessão inválida: o "Buscar" devolve
  HTTP 302 para a home, mesmo com o formulário correto. Chegando pelo link
  da home (`?aba=p-ensino` / `?aba=p-graduacao`), a busca funciona.
- O filtro "Unidade Responsável" só vale com a checkbox ao lado marcada.

Além disso, o SIGAA pode sair do ar ou mudar o layout, e quem corrige
precisa conseguir subir o banco igual ao da Squad.

## Alternativas consideradas

| | Alternativa | Reprodutível por terceiros? | Custo |
|---|---|---|---|
| A | **Opção nula:** baixar ou copiar os dados à mão e carregar | Não (passo manual) | Baixo agora, alto a cada semestre |
| B | `requests` + reimplementação manual do ViewState e da sessão JSF | Depende do SIGAA no ar | Reimplementar o protocolo JSF e mantê-lo |
| C | Playwright (navegador real) + CSVs brutos versionados em `data/raw/` | Sim, offline | Imagem Docker maior; raspagem lenta |

## Medição

| Acesso ao formulário de busca | Resposta ao "Buscar" |
|---|---|
| URL do formulário aberta direto | 302 para a home (observado no log de rede) |
| Clique no link da home | 200 com a listagem |

Tamanho do recorte: cerca de 150 bytes por turma em CSV. Mesmo no teto
da estimativa inicial (3 000 turmas por semestre), 9 semestres dão perto
de 4 MB, abaixo do limite de 5 MB para versionar. O tamanho real de
`data/raw/` sai em [`docs/carga-medida.md`](../carga-medida.md).

## Decisão

Alternativa C. Os scrapers (`loader/scrape_*.py`) usam Playwright,
chegam aos formulários pela home e gravam os dados brutos em
`data/raw/`, que é versionado. O `load_to_db.py` lê só de `data/raw/`.
Com `RASPAR=auto` (padrão), o SIGAA só é acessado para o que ainda não
está no repositório; `RASPAR=1` raspa tudo de novo.

## Consequências

- **Ganhamos:** qualquer pessoa sobe o mesmo banco com um comando, sem
  depender do SIGAA; o diff dos CSVs mostra o que mudou entre raspagens.
- **Perdemos:** imagem Docker maior (Chromium) e raspagem lenta (uma
  página de detalhe por componente); seletores por texto visível quebram
  se o SIGAA mudar os rótulos.
- **Custo de reversão:** baixo; os CSVs em `data/raw/` são o contrato
  entre extração e carga, então trocar o extrator não afeta o banco.

## Gatilho de revisão

- A raspagem de um semestre falhar em duas execuções seguidas por
  mudança de layout → reavaliar B ou pedir os dados à UnB.
- A UnB publicar a oferta de turmas como dado aberto ou API → trocar o
  extrator e manter o formato de `data/raw/`.
