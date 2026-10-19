# Semana 08 (29/09 a 05/10)

## O que foi medido

- A fonte pública continua sendo adequada para carga em lote; a coleta
  versionada de 28/09 contém o recorte reproduzível usado pela E2.
- O pipeline E2 foi separado do OLTP: o lote escreve Parquet/Delta e o
  caminho de mudanças usa a outbox do PostgreSQL.

## O que surpreendeu

- Debezium/Kafka exigiria uma infraestrutura maior do que o domínio
  semestral justifica para esta entrega.

## O que foi decidido

- Comparar explicitamente CDC com a opção nula de recarga agendada no
  [ADR-0005](../adr/0005-ingestao-e2.md).

## Próxima semana

- [ ] Executar a carga Parquet/Delta e medir a reexecução.
