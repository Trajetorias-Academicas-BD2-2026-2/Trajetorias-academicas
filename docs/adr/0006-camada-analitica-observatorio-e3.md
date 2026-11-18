# ADR-0006: Esquema estrela em dbt, fato por turma e curso, orquestrado por script com cron

- **Status:** aceito (revisado em 2026-11-17: SCD, fato incremental, testes de integridade e de distribuição, medições)
- **Data:** 2026-11-08
- **Decisores:** Squad G2 — Ana Joyce · Gustavo Alves · Gabriel Lima da Silva · Nathan Abreu · Guilherme Evangelista · Angélica Campos · Davi Araújo

## Contexto

A E3 transforma o OLTP numa camada analítica que responde à pergunta da E1:

> Como evoluíram, entre 2022.1 e 2026.1, as vagas reservadas publicadas para
> cada curso da FCTE nas disciplinas obrigatórias do currículo de referência
> selecionado para 2026.1?

Evidências da E2 que pesam na decisão:

- **Uma fonte só** (o SIGAA, por lotes versionados), sem integração entre sistemas.
- **Esquema da origem estável:** em 11 migrações, nenhuma mudou o significado
  de uma coluna de reserva. O que muda são valores de catálogo (nome e carga
  horária da disciplina, chegando como UPDATE no CDC) e a natureza da
  disciplina entre versões de currículo.
- **Volume pequeno:** 1.776 reservas, de +155 a +255 por semestre.

## Decisão 1: modelagem: esquema estrela

| Alternativa | A favor | Contra, neste domínio |
|---|---|---|
| **Estrela** (fato + dimensões) | consultas da pergunta são agregações por curso, semestre e disciplina; um nível de join | — |
| Data Vault (hubs, links, satélites) | absorve várias fontes e mudança de esquema sem retrabalho | temos uma fonte e esquema estável: triplicaria os objetos (hub/link/satélite para curso, disciplina, turma) sem nenhum ganho de integração; ainda precisaria de uma estrela por cima para consumo |
| One big table | uma tabela, nenhum join | a mesma turma aparece em até 5 cursos (média 2,42): somar vagas por disciplina numa OBT sem cuidado conta a turma várias vezes; e a SCD de disciplina viraria reescrita da tabela inteira |

Ficamos com a estrela: `fct_reservas` + `dim_curso`, `dim_disciplina`,
`dim_semestre`, `dim_curriculo_componente`, e marts de consumo por cima.

## Decisão 2: granularidade do fato

**Uma linha por turma e curso:** as vagas que uma turma de um semestre
reservou para um curso. A turma já determina a disciplina e o semestre.
Unicidade testada (`test_unicidade_fato`).

| Granularidade | Linhas | Responde à pergunta? | O que perde |
|---|---:|---|---|
| reserva (turma × curso), **escolhida** | 1.776 | sim, e permite descer à disciplina e à turma | — |
| curso × disciplina × semestre (`mart_disciplina_semestre`) | 676 | sim | qual turma reservou; turmas compartilhadas entre cursos |
| curso × semestre (`mart_observatorio`) | 45 | só o total | qual disciplina ganhou ou perdeu reserva; obrigatórias sem reserva |

A fina não explode (1.776 linhas, ~330 kB). A grossa (45) responde ao
total, mas não às perguntas derivadas da E1. Por isso guardamos a fina e
materializamos as grossas como marts.

## Decisão 3: dimensões de variação lenta

- `dim_disciplina`: **SCD tipo 2 em tempo de processamento**, a partir do
  snapshot `snap_disciplina` (estratégia `check` em nome, carga horária,
  tipo e unidade). No OLTP, `disciplina` recebe upsert, então uma correção
  do SIGAA sobrescreve o valor. O snapshot preserva cada versão
  (`valid_from`, `valid_to`, `is_current`). O fato aponta para a versão
  vigente quando a reserva foi ingerida (`disciplina_sk`). Demonstração:
  [`docs/evidencias/scd.txt`](../evidencias/scd.txt).
- `dim_curriculo_componente`: **SCD tipo 2 em tempo de negócio**. A
  natureza da disciplina no curso vale do semestre de início de uma versão
  curricular até o início da seguinte. Em FGA_AUTO, 4 disciplinas trocam
  de natureza entre 6297/2 e 6297/3. O fato carrega `natureza_na_epoca`
  (nula quando a versão daquela época não foi coletada) ao lado de
  `obrigatoria`, que segue o currículo fixo de 2026.1 pedido na pergunta.

## Decisão 4: ferramenta e orquestração

- **dbt, não SQLMesh:** os dois são declarativos e versionados. O dbt tem
  adaptador Postgres estável, snapshots prontos para a SCD e testes
  genéricos (`relationships`, `accepted_values`). Os planos virtuais do
  SQLMesh (ambientes sem recomputar) não ajudam com uma recarga de menos
  de 3 segundos.
- **Script + cron como orquestrador (opção nula), não Airflow nem Dagster.**
  `orchestration/run_pipeline.sh` declara o grafo
  (db → migrate → loader → analytics → analytics-tests [→ ml]), repete cada
  etapa até 3 vezes com espera crescente e para o grafo na etapa que falha.
  O cron (`orchestration/crontab`) agenda às 02:00. O Airflow somaria
  scheduler, webserver e banco de metadados ao Compose para um pipeline
  linear de 5 etapas que roda uma vez por dia e leva cerca de 20 s.
  Demonstrado:
  - **Retry com o banco derrubado de propósito:** a etapa falha 2 vezes e
    passa na 3ª; com as tentativas esgotadas, o pipeline sai com código 1
    sem rodar as etapas seguintes ([`retry.txt`](../evidencias/retry.txt)).
  - **Backfill:** `BACKFILL_SEMESTRE=2024.1` refaz só aquela janela do fato
    incremental ([`backfill-2024.1.txt`](../evidencias/backfill-2024.1.txt)).

## Decisão 5: testes, freshness e SLA

- **Esquema:** `not_null`, `accepted_values` (natureza, tipo).
- **Unicidade:** chaves das dimensões, granularidade do fato e dos marts.
- **Integridade referencial:** `relationships` do fato para `dim_curso`,
  `dim_disciplina` (versão) e `dim_semestre`, e dos marts para `dim_curso`.
- **Volume:** fato ≥ 1.500 linhas e nenhum semestre abaixo de 50% da
  mediana, o que pega uma carga parcial de um semestre.
- **Distribuição:**
  - vagas entre 1 e 200;
  - nenhum curso some de um semestre;
  - salto de série: o curso mais que dobra ou cai pela metade de um
    semestre para o outro. Fica como `warn`, e hoje acusa 4 saltos
    conhecidos a partir de 2023.2.
- **Freshness da origem:** `dbt source freshness` em `turma` e
  `reserva_vaga`, com aviso em 200 dias e erro em 400 (cadência semestral).
- **SLA da tabela de consumo:** `mart_observatorio` reflete uma carga nova
  em até 24 h. A métrica é a view `metricas_freshness` (`atraso_horas`),
  testada em `test_sla_freshness_mart` e exibida no painel.

Resultado atual: `PASS=57 WARN=1 ERROR=0`.

## Desempenho

Consulta da pergunta (`q0`), com `EXPLAIN (ANALYZE, BUFFERS)`
([antes](../evidencias/explain-antes.txt), [depois](../evidencias/explain-depois.txt)):

- **Antes:** o CTE agregado sem estatística foi estimado em 5 linhas (eram
  254). O planner escolheu 1.681 buscas por índice em `reserva_vaga`:
  5.721 buffers, 3,0 ms.
- **Depois:** a consulta agrega primeiro e junta `curso` no fim. O plano
  passa a usar hash joins: 188 buffers (30× menos), 1,9 ms, mesmo resultado.
- **Índice duplicado:** a V011 remove `idx_reserva_vaga_turma_curso`, que
  era idêntico à chave primária.

## Consequências

- **Ganhamos:**
  - uma regra de métrica só, usada pelo painel e pelo ETL reverso;
  - histórico de catálogo e de natureza curricular preservado;
  - reprocessamento por janela sem recarga total.
- **Perdemos:**
  - a SCD de disciplina só vê mudanças a cada execução do dbt, e duas
    mudanças no mesmo dia viram uma;
  - o orquestrador não tem interface nem histórico de execuções (só o log
    do cron).
- **Fora do escopo:** ocupação real e oferta total de vagas (ver ADR-0003).

## Gatilhos de revisão

- Uma segunda fonte (ex.: matrícula) ou mudança frequente de esquema → reavaliar Data Vault.
- Mais de 10 etapas, dependências não lineares ou necessidade de histórico de execuções → Airflow ou Dagster.
- `dbt build` acima de 5 min ou consulta de consumo acima de 2 s → materialização incremental dos marts e índices nos marts.
