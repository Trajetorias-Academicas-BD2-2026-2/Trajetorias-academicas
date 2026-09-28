# ADR-0004: A carga lê um lote de coleta versionado e conferido por checksum, e não raspa o SIGAA durante a carga

- **Status:** aceito (substitui o [ADR-0002](0002-extracao-via-navegador-real.md))
- **Data:** 2026-09-28
- **Decisores:** Squad G2 — Ana Joyce, Gustavo Alves, Gabriel Lima da Silva, Nathan Abreu, Guilherme Evangelista, Angélica Campos e Davi Araújo

## Contexto

O ADR-0002 previa raspar o SIGAA com Playwright a cada carga. Na coleta
real de 28/09/2026, os scrapers falharam em quatro pontos do site
([relatório](../COLETA_SIGAA_2026-09-28.md#falhas-do-scraper-original-observadas-no-site-real)),
e o formulário geral de turmas não devolveu o histórico da FCTE. Os dados
foram obtidos por navegação nas páginas públicas e salvos em
`data/coleta_publica_2026-09-28/`, com evidências e `SHA256SUMS.txt`. A
página da E1 aceita duas saídas para a carga reprodutível: automatizar o
download ou versionar o recorte, se couber em 5 MB.

## Alternativas consideradas

| | Alternativa | Reprodutível por terceiros? |
|---|---|---|
| A | **Opção nula:** manter os scrapers Playwright e corrigir os seletores | Só com o SIGAA no ar e sem mudança de layout |
| B | Coletor HTTP (requests) rodando a cada carga | Idem; validado em 1 das 45 consultas |
| C | Lote versionado e conferido por checksum; o coletor HTTP só gera lotes novos | Sim, offline |

## Medição

| Medida | Valor |
|---|---|
| Tamanho do lote com evidências | 903 kB (limite: 5 MB) |
| Consultas curso x semestre no lote | 45 de 45, todas com registros |
| Coletor HTTP x navegador (Software, 2022.1) | 60 registros, mesmas disciplinas, turmas, vagas, horários e docentes |
| Consultas do formulário geral com filtro FCTE (2022.1–2025.2) | 0 resultados (2023.1 e 2025.2 conferidos de novo à mão) |

## Decisão

Alternativa C. O `load_to_db.py` lê só a pasta do lote (`DATA_DIR`),
confere cada arquivo contra `SHA256SUMS.txt` e valida o recorte antes de
tocar no banco. Os scrapers Playwright foram removidos. O
`coletar_ofertas_por_curso.py` fica no repositório para gerar lotes novos
de reservas; catálogo, currículos e pré-requisitos de um lote novo ainda
são coletados por navegação e precisam de evidência e checksum.

## Consequências

- **Ganhamos:** `docker compose up` produz sempre o mesmo banco, sem rede e
  sem browser; a imagem do loader deixa de carregar o Chromium.
- **Perdemos:** coletar de novo não é um comando só: as reservas sim (o
  coletor), o resto não. O lote é um retrato de 28/09/2026 e a fonte é
  mutável.
- **Custo de reversão:** baixo. Um lote novo é uma pasta nova com o mesmo
  formato de arquivos; trocar de lote é mudar `DATA_DIR`.

## Gatilho de revisão

- Um coletor automatizado para catálogo, currículos e pré-requisitos,
  validado contra o lote atual → rodar a coleta completa no pipeline.
- O coletor HTTP falhar ao gerar um lote novo → rever se o SIGAA mudou o
  formulário ou a sessão JSF.
