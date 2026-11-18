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

## Revisão pós-entrega (17/11/2026)

Na revisão do checklist da E2, encontramos quatro lacunas e corrigimos:

- O CDC só observava `e2_oltp_reserva_demo`, uma tabela fora do modelo. A
  V010 passou a captura para `reserva_vaga`, `disciplina` e
  `curriculo_componente`; a tabela de demonstração foi removida.
- O consumidor relia a outbox inteira a cada execução. Agora lê a partir do
  checkpoint e faz MERGE por chave; a queda antes do checkpoint é simulada
  e a reexecução não duplica nada (`docs/evidencias/e2-roteiro.txt`).
- O dado atrasado só estava descrito. Agora o lote reprocessa uma janela
  (`--semestre`) e `demo_atraso.py` mostra o registro de 2023.1 entrando na
  partição certa.
- A escolha de zstd e da partição não tinha número: `medir_formatos.py`
  mediu. O que surpreendeu: particionar deixa a leitura da série 3× mais
  lenta neste volume; mantivemos a partição por causa da escrita por semestre (ADR-0005).
- Os comandos do README usavam `docker compose run --profile`, que não existe.
