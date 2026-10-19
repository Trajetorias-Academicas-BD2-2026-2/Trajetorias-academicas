# ADR-0005: Lote idempotente e CDC por outbox transacional na E2

- **Status:** aceito para a E2
- **Data:** 2026-10-19
- **Decisores:** Squad G2

## Contexto

A E2 exige dois caminhos entre a origem e o armazenamento analítico: uma
ingestão em lote da fonte pública e uma captura de mudanças no OLTP. O volume
observado é semestral e a fonte pública não oferece atualização contínua, mas
o OLTP precisa demonstrar uma mudança atravessando o fluxo.

## Opções consideradas

1. **Opção nula — somente `INSERT ... SELECT` agendado.** É suficiente para a
   fonte pública, tem baixo custo operacional e é a escolha adequada quando a
   latência de horas ou dias é aceitável. Não cobre, porém, o requisito
   pedagógico de observar uma alteração no OLTP.
2. **Debezium lendo WAL e Kafka.** É uma solução de produção válida, mas
   introduz JVM, Kafka, Connect e operação desproporcional ao volume desta
   entrega. A equipe não conseguiria reproduzir o ambiente com baixo atrito.
3. **Outbox transacional + consumidor idempotente.** A mudança é gravada na
   mesma transação do OLTP e o consumidor lê a sequência ordenada da outbox.
   Esta é a escolha da E2: demonstra CDC equivalente, é reproduzível com
   PostgreSQL e deixa a substituição por Debezium como evolução futura.

## Decisão

Usar:

- lote versionado da fonte pública;
- Parquet particionado por `ano` e `periodo`, comprimido com Zstandard,
  inclusive nos arquivos da tabela Delta;
- Delta Lake sobre Parquet para a tabela analítica;
- outbox transacional para capturar `INSERT`, `UPDATE` e `DELETE`;
- checkpoint no consumidor e reconstrução determinística por chave.

## Semântica demonstrada

O lote e o consumidor são **at-least-once**, com deduplicação determinística.
Uma falha antes do checkpoint pode fazer o consumidor ler eventos novamente,
mas a publicação em modo `overwrite` reconstrói uma linha por chave e não
duplica o estado. O checkpoint só avança depois da escrita bem-sucedida.

O lote usa `overwrite` da tabela derivada, não `append`; por isso uma
reexecução da mesma fonte também mantém os totais idênticos.

## Dado atrasado e janela

O lote usa o `event_time` da fonte para as partições `ano/periodo`. Uma
reexecução do mesmo recorte substitui as partições publicadas, portanto um
registro atrasado é aceito na partição do seu período de evento, mesmo que a
data de ingestão seja posterior. A operação é registrada no manifesto.

## Consequências

Há dois diretórios derivados: `analytical/batch/ofertas` e
`analytical/cdc/reservas`. O Delta mantém o histórico de transações e os
arquivos Parquet; o consumidor precisa de uma etapa de compactação em cargas
grandes. O fluxo não pretende ser uma implementação de Debezium e deve ser
revisitado se a latência exigida cair para segundos ou se o volume justificar
Kafka.
