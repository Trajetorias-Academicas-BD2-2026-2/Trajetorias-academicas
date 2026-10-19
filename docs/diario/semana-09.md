# Semana 09 (06/10 a 12/10)

## O que foi medido

- O lote é particionado por ano e período e usa Zstandard.
- A semântica escolhida é at-least-once com deduplicação por chave e
  reprocessamento determinístico.

## O que surpreendeu

- Reprocessar a janela inteira é mais simples e seguro para este volume do
  que tentar atualizar arquivos individuais, especialmente para dados
  atrasados.

## O que foi decidido

- Um evento atrasado volta para a partição do seu período de evento; a
  reexecução substitui a versão publicada daquela janela.

## Próxima semana

- [ ] Executar uma alteração no OLTP e acompanhar a outbox até o Delta.
