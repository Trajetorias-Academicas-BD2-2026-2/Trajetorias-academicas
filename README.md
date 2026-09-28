# G2 — Oferta de Disciplinas UnB (Projeto Integrado BD2, E1)

Fonte transacional (OLTP) que apoia o coordenador de curso a decidir
quais disciplinas ofertar, a partir de três fontes públicas do SIGAA:
**Consulta de Turmas**, **Busca de Componentes Curriculares** e a
**listagem pública de cursos de graduação**.

## Pergunta de gestão

> Entre 2022.1 e 2026.1, quais disciplinas obrigatórias dos cinco cursos
> de graduação da FCTE ficaram lotadas com mais frequência, por turno?

*Lotada* = vagas ocupadas maiores ou iguais às vagas ofertadas. Os dados
públicos não mostram quem tentou se matricular e não conseguiu, então a
lotação é o indicador observável de demanda reprimida. Consulta:
[`db/consultas/q0_pergunta_de_gestao.sql`](db/consultas/q0_pergunta_de_gestao.sql).

Perguntas derivadas que o esquema também responde (em [`db/consultas/`](db/consultas/)):
- Quais dessas disciplinas mais travam a grade por serem pré-requisito de outras?
- Quantas turmas de cada disciplina abrem por semestre, e isso está crescendo ou diminuindo?
- O aluno do noturno tem o mesmo acesso às obrigatórias que o do diurno?

## Domínio e persona

Coordenador de curso de graduação da FCTE (Campus Gama), que hoje decide
quais turmas abrir sem visibilidade histórica de lotação, o que gera
turmas lotadas e atraso na formatura.

## Tecnologias

| Camada | Escolha |
|---|---|
| Banco de dados | PostgreSQL 16 |
| Migração | SQL versionado em `db/migrations/`, aplicado em ordem por `db/migrate.sh` com controle em `schema_migrations` |
| Extração | Python + Playwright, navegador real ([ADR-0002](docs/adr/0002-extracao-via-navegador-real.md)) |
| Recorte | CSVs brutos versionados em [`data/raw/`](data/raw/) |
| Orquestração | Docker Compose |

## Como rodar

Pré-requisito: Docker e Docker Compose.

```bash
docker compose up --build
```

Em ordem, isso:

1. sobe o Postgres;
2. aplica as migrações ainda não aplicadas (`db/migrate.sh`; qualquer erro de SQL interrompe tudo);
3. roda o loader (`loader/run.sh`):
   1. `scrape_componentes.py`: disciplinas, carga horária e pré-requisitos;
   2. `scrape_cursos.py`: os 5 cursos do Gama e suas matrizes curriculares;
   3. `scrape_turmas.py`: oferta de turmas de cada semestre de 2022.1 a 2026.1;
   4. `load_to_db.py`: carrega `data/raw/` no banco numa única transação.

Os scrapers só acessam o SIGAA para o que ainda **não** está em
`data/raw/`. Com o recorte versionado no repositório, a carga roda
offline e produz sempre o mesmo banco. Ao final, o loader imprime um
resumo (linhas inseridas, já existentes e rejeitadas por motivo); as
rejeitadas ficam detalhadas em `debug/rejeitados.csv`.

Recomeçar do zero (banco limpo):

```bash
docker compose down -v
docker compose up --build
```

Raspar tudo de novo no SIGAA (ex.: para ampliar o recorte), revisar o
diff de `data/raw/` e commitar:

```bash
RASPAR=1 docker compose up --build
```

O recorte (unidade e semestres) fica nas variáveis do serviço `loader`
em `docker-compose.yml`. O loader recusa semestres ainda em andamento
(ver [`docs/historico.md`](docs/historico.md)).

## Testes

```bash
# Testes de dados pós-carga: esquema, volume, distribuição, dado faltante, histórico.
# Termina com erro se algum teste falhar.
docker compose run --rm tests

# Testes unitários do parsing do SIGAA e das regras de semestre
docker compose run --rm loader python -m unittest discover -s tests -v
```

Reprocessamento: rodar `docker compose up` de novo não duplica nem altera
linhas. O resumo do loader mostra `oferta_turma: já existia
(reprocessamento)` para cada turma já carregada.

## Carga de trabalho medida

```bash
docker compose run --rm -T loader python caracterizar.py > docs/carga-medida.md
```

Gera [`docs/carga-medida.md`](docs/carga-medida.md): linhas e bytes por
tabela, crescimento por semestre, dado faltante, tempo de cada consulta
de referência e a medição do ADR-0001 (3FN x desnormalizado). A
interpretação está em [`docs/carga-de-trabalho.md`](docs/carga-de-trabalho.md).

Para explorar o banco sem escrever SQL, use o [DBeaver](https://dbeaver.io)
(host `localhost`, porta `5432`, banco `ofertas_unb`, usuário `g2`,
senha `g2_dev_only`).

## Estrutura do repositório

```
data/raw/                 recorte bruto raspado do SIGAA (versionado)
db/
  migrations/             V001 (esquema base), V002 (correções pós-E1)
  migrate.sh              aplica migrações pendentes, em ordem, com ON_ERROR_STOP
  consultas/              consultas de referência (pergunta de gestão e derivadas)
docs/
  adr/0001-modelagem-fonte-origem.md    modelagem do sistema de origem
  adr/0002-extracao-via-navegador-real.md
  carga-de-trabalho.md    caracterização da carga (passo 1)
  carga-medida.md         números medidos, gerado por caracterizar.py
  historico.md            por que oferta_turma é insert-only
  AI-USAGE.md             uso de IA e como cada solução foi validada
loader/
  config.py               URLs, recorte (unidade e semestres), caminhos
  semestres.py            regras de semestre (só semestres encerrados)
  parsing.py              interpretação do texto do SIGAA (horário, turno, vagas, pré-requisitos)
  sigaa_utils.py          navegação no SIGAA e gravação atômica dos CSVs
  scrape_componentes.py, scrape_cursos.py, scrape_turmas.py
  load_to_db.py           carga idempotente numa única transação
  caracterizar.py         mede a carga e gera docs/carga-medida.md
  run.sh                  orquestra as quatro etapas
  tests/                  testes unitários
tests/sanity_checks.sql   testes de dados pós-carga
docker-compose.yml
```

## Decisões principais

Resumo; o raciocínio completo está nos ADRs.

- **`oferta_turma` é insert-only**, uma linha por turma e semestre
  encerrado, garantido por trigger no banco. Estrutura curricular usa upsert.
- **3FN**: neste volume a tabela única desnormalizada não se paga e
  multiplicaria cada turma pelos cursos em que a disciplina aparece.
- **Carimbos por papel**: `ano`/`periodo` (evento), `coletado_em`
  (raspagem), `ingerido_em` (entrada no banco).
- **Linhagem** em toda oferta: `fonte` e `carga_id`.
- **Extração com navegador real e recorte versionado**, para que a carga
  seja reprodutível sem depender do SIGAA ([ADR-0002](docs/adr/0002-extracao-via-navegador-real.md)).

## Uso de IA

Ver [`docs/AI-USAGE.md`](docs/AI-USAGE.md).
