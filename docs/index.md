# G2 — Observatório de Reservas UnB

Plataforma integrada de dados sobre reservas de vagas nas disciplinas da UnB,
da fonte transacional ao observatório analítico e ao ETL reverso.

## Pergunta de gestão

> Como evoluíram, entre 2022.1 e 2026.1, as vagas reservadas publicadas para
> cada curso da FCTE nas disciplinas obrigatórias do currículo de referência
> selecionado para 2026.1?

## Camadas implementadas

- **E1:** PostgreSQL, migrações, carga reproduzível e histórico insert-only.
- **E2:** ingestão em lote, Parquet/Delta e outbox transacional.
- **E3:** dbt, modelo dimensional, testes, freshness, retry, backfill e painel.
- **E4:** camada semântica, ETL reverso, catálogo, linhagem, LGPD e acesso mínimo.

Comece pelo README do projeto na raiz do repositório, depois consulte o
[observatório e governança](observatorio-e-governanca.md) e o
[roteiro de apresentação](roteiro-apresentacao.md).

Esta entrega implementa:

- ingestão em lote idempotente da coleta pública;
- Parquet particionado por ano e período, com compressão Zstandard;
- tabela Delta sobre Parquet;
- captura de mudanças do OLTP por outbox transacional;
- consumidor CDC idempotente;
- tratamento documentado de reprocessamento e dados atrasados.

Consulte a [evidência da E2](evidencia-e2.md), o
[ADR-0005](adr/0005-ingestao-e2.md) e o
[diário das semanas 8 a 10](diario/README.md).
