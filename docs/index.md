# G2 — Entrega E2

Documentação da Entrega E2 do projeto de oferta de disciplinas da UnB.

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
