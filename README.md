# G2 — Oferta de Disciplinas UnB (Projeto Integrado BD2, E3/E4)

Fonte transacional (OLTP) com o histórico de **vagas reservadas** pelas
turmas a cada curso de engenharia da FCTE (Campus Gama) e as **versões
curriculares** desses cursos, a partir de páginas públicas do SIGAA.

## Squad G2

Ana Joyce · Gustavo Alves · Gabriel Lima da Silva · Nathan Abreu ·
Guilherme Evangelista · Angélica Campos · Davi Araújo

## Pergunta de gestão

> Como evoluíram, entre 2022.1 e 2026.1, as vagas reservadas publicadas
> para cada curso da FCTE nas disciplinas obrigatórias do currículo de
> referência selecionado para 2026.1?

- *Vagas reservadas* = campo "Vgs Reservadas" da página de turmas do curso
  no SIGAA. **Não** é a oferta total da turma nem a ocupação.
- *Currículo de referência* = versão curricular em vigor em 2026.1 (view
  `curriculo_referencia`, fixada em 2026.1 pela migração V005). É um conjunto **fixo**, aplicado a toda a série:
  a pergunta é sobre as disciplinas que hoje são obrigatórias, não sobre o
  que era obrigatório em cada semestre.
- Consulta: [`db/consultas/q0_pergunta_de_gestao.sql`](db/consultas/q0_pergunta_de_gestao.sql).

A primeira pergunta do projeto era sobre **lotação**. Na coleta de
28/09/2026 não conseguimos obter a ocupação por turma nas fontes e
consultas testadas ([relatório da coleta](docs/COLETA_SIGAA_2026-09-28.md),
[ADR-0003](docs/adr/0003-reservas-por-curso-e-curriculo-versionado.md)).

Perguntas derivadas, em [`db/consultas/`](db/consultas/):
- Quais obrigatórias nunca tiveram reserva para o curso no recorte?
- Quanto das reservas vem de disciplinas da FCTE e quanto de outras unidades (MAT, IFD...)?
- Quantas turmas atendem mais de um curso?
- Quais obrigatórias mais perderam reservas entre 2022 e 2025?

## Domínio e persona

Coordenador de curso de graduação da FCTE, que negocia a cada semestre as
vagas reservadas ao seu curso nas turmas (as da FCTE e as de outros
institutos, como Cálculo e Física) sem ver como essas reservas evoluíram.

## Tecnologias

| Camada | Escolha |
|---|---|
| Banco de dados | PostgreSQL 16 |
| Migração | SQL versionado em `db/migrations/`, aplicado em ordem por `db/migrate.sh` com controle em `schema_migrations` |
| Dados | Lote de coleta versionado em [`data/coleta_publica_2026-09-28/`](data/coleta_publica_2026-09-28/), conferido por SHA-256 ([ADR-0004](docs/adr/0004-coleta-publica-versionada.md)) |
| Carga | Python (`loader/load_to_db.py`) |
| Coleta nova de reservas | `loader/coletar_ofertas_por_curso.py` (requests + BeautifulSoup) |
| Orquestração | Docker Compose |

## E2 — ingestão em lote e captura de mudanças

Dois caminhos levam o dado da origem ao armazenamento analítico aberto
(Parquet + Delta Lake, em `analytical/`):

- **Lote** (`ingestion/batch_to_delta.py`): lê o lote público versionado e
  grava Parquet zstd particionado por `ano/periodo` e uma tabela Delta.
  Idempotente (overwrite determinístico); `--semestre 2023.1` reprocessa só
  uma janela, que é como o dado atrasado entra.
- **Mudanças** (`ingestion/cdc_consumer.py`): a migração V010 grava, na mesma
  transação, cada INSERT/UPDATE/DELETE de `reserva_vaga`, `disciplina` e
  `curriculo_componente` numa outbox. O consumidor lê a partir do checkpoint
  e aplica MERGE por chave no Delta `analytical/cdc/oltp`.

Roteiro completo (lote duas vezes, dado atrasado, mudança real no OLTP,
queda do consumidor antes do checkpoint, reexecução e verificação), depois
do `docker compose up`:

```bash
docker compose run --rm --build e2-cdc bash ingestion/run_e2.sh
```

Passos isolados:

```bash
docker compose run --rm --build e2-batch                       # lote completo
docker compose run --rm e2-batch python ingestion/batch_to_delta.py --semestre 2024.1
docker compose run --rm e2-cdc python ingestion/demo_change.py --disciplina FGA0137 --carga-horaria 90
docker compose run --rm e2-cdc                                 # consome a outbox
docker compose run --rm e2-batch python ingestion/medir_formatos.py
```

Decisão e medições no [ADR-0005](docs/adr/0005-ingestao-e2.md); saída
executada em [`docs/evidencia-e2.md`](docs/evidencia-e2.md).

## E3 — observatório analítico

O serviço `analytics` roda o dbt sobre o OLTP:

- **Snapshot:** `snap_disciplina`, SCD tipo 2 de disciplina.
- **Staging.**
- **Estrela:** dimensões de curso, semestre, disciplina (SCD) e natureza
  curricular por versão, e o fato `fct_reservas`, com uma linha por turma
  e curso, incremental por semestre.
- **Marts:** `mart_observatorio`, `mart_disciplina_semestre`,
  `mart_cobertura_curriculo` e `metricas_freshness`.
- **Testes:** 45 testes de esquema, unicidade, integridade referencial,
  volume e distribuição.
- **ETL reverso.**

O painel, em `http://localhost:8080`, responde à pergunta por curso: série
de vagas reservadas, matriz disciplina × semestre, ganhos e perdas,
departamento de origem, obrigatórias sem reserva, fila de revisão e SLA.
`?curso=FGA_ELET&modo=indice` abre direto num curso e na escala comparada.

```bash
docker compose up --build
docker compose --profile test run --rm tests
docker compose --profile test run --rm analytics-tests
./orchestration/run_pipeline.sh                          # grafo completo com retry
BACKFILL_SEMESTRE=2024.1 ./orchestration/run_pipeline.sh # refaz só uma janela
```

Decisões no [ADR-0006](docs/adr/0006-camada-analitica-observatorio-e3.md).

Os modelos e testes estão em [`analytics/`](analytics/). A implementação,
catálogo, linhagem, SLA, LGPD e acesso mínimo estão em
[`docs/observatorio-e-governanca.md`](docs/observatorio-e-governanca.md).
Retry, backfill e o roteiro de `EXPLAIN (ANALYZE, BUFFERS)` estão em
[`docs/orquestracao-e-performance.md`](docs/orquestracao-e-performance.md).
As evidências executadas e o roteiro de defesa estão em
[`docs/evidencias/`](docs/evidencias/) e
[`docs/roteiro-apresentacao.md`](docs/roteiro-apresentacao.md).

## E4 — plataforma completa, governada e defendida

| O quê | Onde |
|---|---|
| **Camada semântica:** 8 métricas definidas uma vez (MetricFlow), lidas pelo painel, pela Pauta e pelo CSV | [`analytics/models/semantic/semantica.yml`](analytics/models/semantic/semantica.yml), `analytics/semantica.py` |
| **ETL reverso:** Pauta da coordenação em `http://localhost:8090`, com fila de envio e reenvio sem duplicar | [`coordenacao/`](coordenacao/), `analytics/etl_reverso.py`, V013 |
| **Acesso:** papéis com privilégio mínimo, RLS por curso, coluna `docente.nome` bloqueada | V012, `tests/acesso_checks.sql` |
| **Catálogo e linhagem:** dbt docs publicado em `/catalogo/`, linhagem até o SIGAA | [`docs/catalogo-e-linhagem.md`](docs/catalogo-e-linhagem.md) |
| **LGPD:** inventário, base legal, retenção, descarte (V014) | [`docs/lgpd.md`](docs/lgpd.md) |
| **Decisões:** ADR-0007 e portfólio dos 5 ADRs com os gatilhos revisados | [`docs/adr/README.md`](docs/adr/README.md) |
| **Defesa:** roteiro e banco de perguntas | [`docs/defesa/`](docs/defesa/) |

```bash
docker compose run --rm --no-deps analytics python /workspace/tests/metricas_consistentes.py   # mesmas métricas em todas as telas
docker compose --profile test run --rm --no-deps acesso-tests                                 # recorte de linha e coluna
./orchestration/demo_etl_reverso.sh                                                           # Pauta fora do ar, volta, reenvio
./orchestration/demo_descarte.sh                                                              # descarte LGPD (transação revertida)
```

Checklist com evidências: [`docs/evidencia-e4.md`](docs/evidencia-e4.md).

## Camada vetorial para ML (opcional)

A migração V009 cria o schema `ml` com pgvector; o serviço `db` usa a imagem
`pgvector/pgvector:pg16`. O dbt monta os textos em `analytics.ml_stg_texto`
(P11), o serviço `ml` vetoriza só os textos novos (P12) e `ml-tests` confere
cobertura, dimensão e norma (P13). Nada disso roda no `docker compose up`.

```bash
docker compose --profile ml run --rm ml          # P12; antes, roda loader e analytics
docker compose --profile ml run --rm ml-tests    # P13
ML=1 ./orchestration/run_pipeline.sh             # pipeline completo com a camada vetorial
```

O modelo `intfloat/multilingual-e5-small`, fixado por commit, tem cerca de
470 MB e é baixado na primeira execução para o volume `ml_modelos`. A consulta
de vizinhos está em [`ml/consultas/`](ml/consultas/).

## Painel publicado

O painel está no ar em <https://trajetorias-academicas-bd2-2026-2.github.io/Trajetorias-academicas/>, de graça, pelo GitHub Pages.

O workflow [`.github/workflows/painel.yml`](.github/workflows/painel.yml) faz cinco passos:

1. sobe o pipeline inteiro com `docker compose` numa máquina do GitHub Actions;
2. roda os testes de dados (`tests` e `analytics-tests`);
3. salva o JSON de `/api/observatorio`;
4. confere o JSON;
5. publica `index.html` + `observatorio.json`.

Se um teste falha, nada é publicado. Não há banco nem senha expostos: a página lê o arquivo JSON quando não encontra a API.

**Quando o painel atualiza:**

- a cada push na `main` que mude o pipeline;
- toda segunda às 06:00 UTC;
- à mão, em **Actions → Publicar painel → Run workflow**.

**Primeira vez:** em **Settings → Pages → Source**, escolher **GitHub Actions**.

## Como rodar

Pré-requisito: Docker e Docker Compose. Não precisa de acesso ao SIGAA.

```bash
docker compose up --build
```

Em ordem, isso:

1. sobe o Postgres;
2. aplica as migrações pendentes (`db/migrate.sh`; qualquer erro de SQL interrompe tudo);
3. roda o loader (`loader/run.sh`):
   1. testes unitários do parsing e do coletor;
   2. `load_to_db.py`: confere os checksums do lote, valida o recorte
      (5 cursos x 9 semestres, cada um encerrado segundo o calendário
      acadêmico antes de ser coletado) e carrega tudo numa única transação.

Ao final, o loader imprime um resumo (linhas inseridas, já existentes e
rejeitadas por motivo); as rejeitadas ficam em `debug/rejeitados.csv`.
No lote atual: 733 turmas e 1.776 reservas inseridas, e 10 reservas
rejeitadas (2 turmas com horário ou docente divergente entre cursos).

Recomeçar do zero:

```bash
docker compose down -v
docker compose up --build
```

## Testes

```bash
# Testes de dados pós-carga: esquema, volume, currículo, distribuição, dado faltante, histórico.
# Termina com erro se algum teste falhar.
docker compose run --rm tests

# Testes unitários (também rodam em toda carga)
docker compose run --rm loader python -m unittest discover -s tests -v
```

Reprocessamento: rodar `docker compose up` de novo com o mesmo lote não
duplica nem altera linhas; o resumo mostra `idêntica (reprocessamento)`.
Se um lote trouxer outro valor para uma turma ou reserva já carregada, a
carga é desfeita e as diferenças vão para `debug/divergencias.csv`.

## Carga de trabalho medida

```bash
docker compose run --rm -T loader python caracterizar.py > docs/carga-medida.md
```

Gera [`docs/carga-medida.md`](docs/carga-medida.md): volume por tabela,
escrita por semestre, qualidade, tempo das consultas de referência e a
medição do ADR-0003. A interpretação está em
[`docs/carga-de-trabalho.md`](docs/carga-de-trabalho.md).

Para explorar o banco sem escrever SQL, use o [DBeaver](https://dbeaver.io)
(host `localhost`, porta `5433` — ou o valor de `DB_PORT_HOST` —, banco `ofertas_unb`, usuário `g2`,
senha `g2_dev_only`).

## Limites dos dados

- Reserva não é oferta nem ocupação: não dá para dizer se uma turma lotou.
- Só aparecem turmas que reservam vagas para algum dos cinco cursos: 85
  de 254 pares curso x obrigatória têm reserva no recorte.
- A partir de 2023.2 as reservas de 50 vagas ou mais saltam de 4 para 17 a
  41 por semestre, sobretudo em Software. Isso parece mudança na forma de
  registrar a reserva e precisa ser considerado ao ler a série.
- O currículo de referência de 2026.1 é aplicado a toda a série; as
  versões em vigor em 2022–2024 não foram coletadas para 4 dos 5 cursos.
- Pré-requisitos coletados para 23 dos 585 componentes da FCTE.

## Estrutura do repositório

```
data/coleta_publica_2026-09-28/   lote versionado: CSVs, evidências, SHA256SUMS.txt, VALIDACAO.md
data/calendario_academico.csv     datas oficiais de encerramento de cada semestre, com fonte
db/
  migrations/             V001 (esquema base), V002 (correções), V003 (reservas e currículo versionado),
                          V004 (calendário acadêmico), V005 (currículo de referência fixo em 2026.1)
  migrate.sh              aplica migrações pendentes, em ordem, com ON_ERROR_STOP
  consultas/              consultas de referência (pergunta de gestão e derivadas)
docs/
  adr/                    ADR-0003 (modelagem) e ADR-0004 (coleta); 0001 e 0002 substituídos
  COLETA_SIGAA_2026-09-28.md   relatório da coleta real
  carga-de-trabalho.md    caracterização da carga (passo 1)
  carga-medida.md         números medidos, gerado por caracterizar.py
  historico.md            o que é insert-only e o que isso permite perguntar
  diario/                 diário de bordo semanal da Squad
  AI-USAGE.md             uso de IA e como cada solução foi validada
loader/
  config.py               lote, recorte e conexão
  semestres.py            regras de semestre (só semestres encerrados)
  parsing.py              horário, turno, docentes, natureza curricular
  load_to_db.py           validação do lote e carga idempotente
  coletar_ofertas_por_curso.py   coleta nova de reservas (gera lote)
  caracterizar.py         mede a carga e gera docs/carga-medida.md
  run.sh                  testes unitários + carga
  tests/                  testes unitários
ml/
  gerar_embeddings.py     P12: sincroniza textos e gera embeddings (pgvector)
  consultas/              consultas de similaridade (fora de db/consultas/)
tests/sanity_checks.sql   testes de dados pós-carga
tests/ml_checks.sql       checagens da camada vetorial (P13)
docker-compose.yml
```

## Decisões principais

- **Turma separada da reserva**: 38% das turmas reservam vagas para mais
  de um curso; numa tabela única, cada turma seria contada 2,42 vezes em
  média ([ADR-0003](docs/adr/0003-reservas-por-curso-e-curriculo-versionado.md)).
- **Currículo versionado**: entre as versões 6297/2 e 6297/3 de Automotiva,
  42 disciplinas saem, 25 entram e 4 mudam de natureza.
- **Insert-only** em turma e reserva, garantido por trigger; um lote que
  diverge do banco é recusado inteiro, com as divergências registradas.
- **Semestre encerrado pelo calendário oficial** da UnB
  ([`data/calendario_academico.csv`](data/calendario_academico.csv), com a
  fonte de cada data); o banco recusa turma coletada antes do encerramento.
- **Lote versionado com checksum**: a carga não depende do SIGAA
  ([ADR-0004](docs/adr/0004-coleta-publica-versionada.md)).
- **Uma definição por métrica, e o dado volta para quem age**: camada
  semântica, cópia por arquivo para o público e ETL reverso por API com fila
  ([ADR-0007](docs/adr/0007-disponibilizacao-e4.md)). Portfólio e gatilhos em
  [`docs/adr/README.md`](docs/adr/README.md).

## Processo da Squad

O registro semanal (o que foi medido, o que surpreendeu, o que foi
decidido) está em [`docs/diario/`](docs/diario/).

## Uso de IA

Ver [`docs/AI-USAGE.md`](docs/AI-USAGE.md).

## Antes de marcar a tag de uma entrega

1. `docker compose down -v && docker compose up --build` numa máquina limpa.
2. `docker compose run --rm tests` sem falhas.
3. `docs/carga-medida.md` gerado com os dados da tag.
4. Nenhum campo pendente na documentação; o comando abaixo não pode
   listar nada:

   ```bash
   grep -rn "⟨PREENCHER\|⟨CONFERIR" docs/
   ```
