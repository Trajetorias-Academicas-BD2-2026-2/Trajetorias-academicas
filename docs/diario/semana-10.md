# Semana 10 (13/10 a 19/10)

## O que foi medido

- A migração V006 cria o OLTP demonstrativo, a outbox, o checkpoint e o
  trigger de captura.
- A execução de `demo_change.py` gera um evento; `cdc_consumer.py` publica
  uma linha por chave no Delta.

## O que surpreendeu

- O consumidor pode reler eventos sem duplicar o estado, pois a publicação
  é uma reconstrução idempotente por chave.

## O que foi decidido

- A branch da E2 manterá scripts e comandos reproduzíveis, além de um ADR
  específico sobre ingestão. A criação da tag `e2` fica para depois da
  validação da Squad.

## Próxima semana

- [ ] Validar o roteiro completo com os colegas e abrir o PR.
