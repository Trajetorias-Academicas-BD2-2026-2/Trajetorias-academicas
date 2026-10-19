# G2 — Oferta de Disciplinas UnB (Projeto Integrado BD2, E1)

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

A branch `feat/e2-ingestao-cdc-parquet` adiciona os dois caminhos exigidos:

- `ingestion/batch_to_delta.py` lê o lote público, gera Parquet particionado
  por `ano/periodo` com Zstandard e publica uma tabela Delta;
- `db/migrations/V006__e2_ingestao.sql` cria uma outbox transacional no OLTP;
- `ingestion/demo_change.py` altera uma linha no OLTP e
  `ingestion/cdc_consumer.py` consome `INSERT`, `UPDATE` e `DELETE` para a
  tabela Delta de mudanças.

Para executar depois da carga normal:

```bash
docker compose run --rm --build e2-batch
docker compose run --rm --build e2-cdc
```

Para demonstrar reexecução e mudança no OLTP:

```bash
docker compose run --rm --build e2-batch
docker compose run --rm --build e2-batch
docker compose run --rm --build e2-cdc
docker compose run --rm --build e2-cdc
```

O segundo lote substitui a mesma tabela Delta sem duplicar linhas. O segundo
consumo não reaplica eventos já confirmados pelo checkpoint. O [ADR-0005](docs/adr/0005-ingestao-e2.md)
registra a comparação com a opção nula e a política para dados atrasados.

O roteiro com contagens, checksum, atualização do OLTP e caso de dado atrasado
está em [`docs/evidencia-e2.md`](docs/evidencia-e2.md).

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
(host `localhost`, porta `5432`, banco `ofertas_unb`, usuário `g2`,
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
tests/sanity_checks.sql   testes de dados pós-carga
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
