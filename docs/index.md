# G2 — Observatório de Reservas UnB

Plataforma integrada de dados sobre reservas de vagas nas disciplinas da UnB,
da fonte transacional ao observatório analítico e ao ETL reverso.

## Squad G2

Este projeto foi desenvolvido por Ana Joyce, Gustavo Alves, Gabriel Lima da
Silva, Nathan Abreu, Guilherme Evangelista, Angélica Campos e Davi Araújo.

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

Para a E3, a página principal de demonstração é o
[observatório analítico](observatorio-e-governanca.md): ele usa dbt para
transformar a fato de reservas em métricas por curso e semestre, executa testes
de qualidade e disponibiliza filtros no dashboard em `http://localhost:8080`.

Para a E2, consulte a [evidência da ingestão](evidencia-e2.md), o
[ADR-0005](adr/0005-ingestao-e2.md) e o
[diário das semanas 8 a 10](diario/README.md).
