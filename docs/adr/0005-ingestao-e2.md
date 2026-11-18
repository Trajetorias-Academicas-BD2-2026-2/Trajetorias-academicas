# ADR-0005: Lote idempotente por partição e CDC por outbox transacional na E2

- **Status:** aceito para a E2 (revisado em 2026-11-17: CDC passou das tabelas de demonstração para as tabelas reais, com medições)
- **Data:** 2026-10-19
- **Decisores:** Squad G2 — Ana Joyce · Gustavo Alves · Gabriel Lima da Silva · Nathan Abreu · Guilherme Evangelista · Angélica Campos · Davi Araújo

## Contexto

A E2 exige dois caminhos entre a origem e o armazenamento analítico: uma
ingestão em lote da fonte pública e uma captura de mudanças no OLTP.

Carga (de [`docs/carga-de-trabalho.md`](../carga-de-trabalho.md)): 1.786
linhas no lote público, de +155 a +255 reservas por semestre, uma carga
nova por semestre encerrado. Leitura analítica sempre por semestre ou pela
série inteira, agregando por curso. Latência tolerada: horas, porque o
coordenador planeja o semestre seguinte com semanas de antecedência.

O OLTP tem dois tipos de tabela: `reserva_vaga`/`turma` são insert-only (só
recebem INSERT), e `disciplina`/`curriculo_componente` recebem upsert, então
uma correção no SIGAA (nome, carga horária, natureza) chega como UPDATE.

## Opções consideradas

| | Opção | Latência medida | Custo de operação | Captura UPDATE? |
|---|---|---|---|---|
| 1 | **Opção nula:** recarga periódica (`loader` + lote, agendados) | recarga completa: 2–3 s (loader) + 0,13–0,19 s (lote Delta); latência = intervalo do agendamento | nenhum serviço novo | só como novo retrato inteiro; não diz *o que* mudou |
| 2 | Debezium (decodificação lógica do WAL) + Kafka + Connect | segundos | 3 serviços JVM a mais, tópicos, offsets, `wal_level=logical`; desproporcional a ~200 linhas por semestre | sim |
| 3 | **Outbox transacional + consumidor incremental com MERGE** | consumo de 1 evento: 0,03 s; latência = intervalo do agendamento do consumidor | 1 trigger por tabela, 1 script Python | sim, com o valor novo e a ordem |

Medições: [`docs/evidencias/e2-roteiro.txt`](../evidencias/e2-roteiro.txt)
(`duracao_s` do consumidor) e as execuções do lote e do loader registradas
em [`docs/evidencia-e2.md`](../evidencia-e2.md).

**A opção nula responde a pergunta de gestão.** O dado público muda uma vez
por semestre, e a recarga inteira leva menos de 3 s. Escolhemos a 3 porque
a E2 exige ver uma mudança atravessar o fluxo. O critério para trocar a 3
pela 2 está nos gatilhos.

## Decisão

1. **Lote:** `ingestion/batch_to_delta.py` grava Parquet e uma tabela Delta a
   partir do lote versionado, com overwrite determinístico (nunca append). O
   modo `--semestre AAAA.N` sobrescreve só a partição da janela
   (`write_deltalake(mode="overwrite", predicate="ano = … AND periodo = …")`).
2. **CDC:** a migração V010 põe triggers `AFTER` em `reserva_vaga` (INSERT),
   `disciplina` e `curriculo_componente` (INSERT/UPDATE/DELETE; UPDATE só
   quando algum valor muda). Eles gravam o evento em `e2_cdc_outbox` na
   mesma transação da mudança. `ingestion/cdc_consumer.py` lê
   `id > checkpoint`, fica com o último evento de cada `(tabela, chave)`,
   faz MERGE no Delta `analytical/cdc/oltp` e só depois avança o checkpoint.
3. **Delta Lake, não Iceberg.** Critérios: (a) escrita sem catálogo:
   Iceberg exige um catálogo (REST, Hive, Glue ou SQL) para commit atômico,
   e o Delta usa só o `_delta_log` no próprio diretório, então o
   `docker compose` não ganha serviço novo; (b) MERGE e overwrite por
   predicado no cliente Python (`deltalake`), sem Spark, que é exatamente o
   que o CDC e a janela precisam; (c) leitura aberta: os arquivos são
   Parquet comum, lidos pelo pyarrow sem a biblioteca Delta (é o que
   `ingestion/delta_io.py` faz) e pelo DuckDB/Spark/Trino. A favor do Iceberg
   ficaria a evolução de partição sem reescrita (*hidden partitioning*), que
   não usamos: a partição por semestre é estável.
4. **Serialização e compressão**: Parquet zstd, particionado por `ano/periodo`.
   Medição ([`docs/evidencias/e2-formatos.txt`](../evidencias/e2-formatos.txt),
   `ingestion/medir_formatos.py`, mediana de 20 leituras):

   | Formato | Tamanho | Ler 2024.1 + agregar | Ler série + agregar |
   |---|---:|---:|---:|
   | CSV | 240 kB | ~1,0 ms | ~0,9 ms |
   | Parquet snappy, 1 arquivo | 16 kB | 0,58 ms | 0,42 ms |
   | Parquet zstd, 1 arquivo | 13 kB | 0,41 ms | 0,32 ms |
   | Parquet zstd, por `ano/periodo` | 51 kB | 0,42 ms | 0,94 ms |

   - **Colunar (Parquet)** porque toda leitura a jusante usa 2–4 das 11
     colunas e agrega. O CSV é 18× maior e o mais lento.
   - **zstd** porque o dado é escrito uma vez por semestre e lido muitas
     vezes: é o menor arquivo junto com o gzip e o mais rápido de ler. O
     snappy, padrão do pyarrow, ocupa 20% a mais e lê mais devagar.
   - **Particionar custa, neste volume:** 3,8× mais bytes (metadados de 9
     arquivos) e leitura da série 3× mais lenta. Mantemos a partição porque
     a **escrita** é por semestre: o dado atrasado e o reprocessamento de
     janela reescrevem uma partição de ~200 linhas em vez da tabela inteira,
     e cada semestre novo acrescenta uma partição sem tocar as outras. O
     custo de leitura é de décimos de milissegundo, longe da latência
     tolerada.

## Semântica de entrega (demonstrada)

**At-least-once na leitura, com escrita idempotente.** O efeito no Delta é
o de exactly-once.

- O checkpoint só avança depois do MERGE. `FAIL_BEFORE_CHECKPOINT=1` derruba
  o consumidor entre os dois. A execução seguinte relê o mesmo evento e o
  MERGE (`when_matched_update_all(predicate="s.last_event_id > t.last_event_id")`)
  não o reaplica nem duplica a linha: 3.034 linhas antes e depois (passos
  5–7 de [`e2-roteiro.txt`](../evidencias/e2-roteiro.txt)).
- Reexecutar o lote completo dá o mesmo resultado: 1.786 linhas, mesma
  versão de conteúdo (passo 1).
- `ingestion/verify_e2.py` confere, contra o OLTP, uma linha por chave e as
  contagens por tabela iguais às do banco.

## Dado atrasado e reprocessamento de janela

O semestre do **evento** (`ano`/`periodo` da turma) define a partição, não a
data de ingestão. Um registro de 2023.1 que só aparece numa coleta de
novembro entra reprocessando a janela 2023.1. Ele não cai na partição de
"hoje" nem é descartado. As outras 8 partições não são reescritas (mesmos
arquivos), e o Delta guarda a versão anterior para auditoria (time travel).
`ingestion/demo_atraso.py` demonstra isso (passo 2): 2023.1 passa de 192
para 193 linhas, nada mais muda, e a janela é depois restaurada a partir da
fonte original.

No OLTP, o dado atrasado é aceito: o trigger só exige que o semestre esteja
encerrado, e `reserva_vaga` é insert-only. O CDC o entrega como um INSERT
comum, com `occurred_at` de hoje e o semestre do evento no payload.

## Consequências

- **Ganhamos:** toda mudança real do OLTP (carga, correção de catálogo)
  chega ao Delta, com ordem e sem duplicar; o dado atrasado tem um caminho
  explícito; sem serviço novo no Compose.
- **Perdemos:** a outbox cresce sem retenção (3.059 eventos após uma carga
  e duas alterações); o trigger soma um INSERT a cada escrita no OLTP; a
  latência depende do agendamento do consumidor, não é streaming.
- **Não é Debezium:** mudanças feitas com os triggers desligados (por
  exemplo, `session_replication_role = replica`) não são capturadas, coisa
  que a leitura do WAL pegaria.

## Gatilho de revisão

- Latência exigida abaixo de 1 minuto ou mais de um consumidor da mesma
  mudança → Debezium + Kafka (opção 2).
- Outbox acima de 1 milhão de eventos → retenção (apagar até o menor
  checkpoint) e compactação do Delta (`optimize`).
- Leitura da série passar de 100 ms ou mais de 100 partições pequenas →
  rever a granularidade da partição (por ano).
