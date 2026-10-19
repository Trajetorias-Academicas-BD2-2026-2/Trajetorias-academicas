# Evidência da E2

## Lote público

Com a branch na raiz do projeto:

```bash
docker compose run --rm --build --profile e2 e2-batch
```

O comando lê `data/coleta_publica_2026-09-28/ofertas_por_curso.csv`,
calcula o SHA-256, grava Parquet com Zstandard em partições
`ano/periodo` e cria a tabela Delta em `analytical/batch/ofertas`.

Na validação local desta branch, o manifesto registrou:

| Medição | Resultado |
|---|---:|
| Linhas de entrada/saída | 1.786 |
| Partições | `ano`, `periodo` |
| Compressão | Zstandard |
| Arquivos Parquet no Delta | 9 |
| SHA-256 da fonte | `3bba2352d8c08ffc59b308bc3f5169003de43aa061a90037387d1c59d2a321df` |

Executar o mesmo comando novamente substitui a tabela derivada de forma
determinística. O número de linhas permanece 1.786; não há `append` cego.

## Mudança no OLTP

Depois de `docker compose up --build`, a migração V006 já está aplicada.
A alteração abaixo ocorre no mesmo container com as dependências da E2:

```bash
docker compose run --rm --build --profile e2 e2-cdc \
  python ingestion/demo_change.py --id E2-DEMO-001 --vagas 30
docker compose run --rm --build --profile e2 e2-cdc
```

O `AFTER INSERT/UPDATE/DELETE` grava a mudança em
`e2_cdc_outbox`. O consumidor lê a sequência, publica o estado por
`aggregate_key` em `analytical/cdc/reservas` e só avança
`e2_cdc_checkpoint` depois da escrita.

Para demonstrar atualização, reprocessamento e ausência de duplicação:

```bash
docker compose run --rm --build --profile e2 e2-cdc \
  python ingestion/demo_change.py --id E2-DEMO-001 --vagas 35
docker compose run --rm --build --profile e2 e2-cdc
docker compose run --rm --build --profile e2 e2-cdc
```

O estado final contém uma linha para `E2-DEMO-001`, com `vagas=35`; a terceira
execução não acrescenta outra linha. `ingestion/verify_e2.py` automatiza essa
conferência.

## Dado atrasado

O período do evento, e não o horário em que o consumidor o processa, define a
partição do lote. Uma coleta posterior que contenha um evento de período antigo
reprocessa a janela `ano/periodo` e substitui a versão daquela partição. Isso
evita que o registro atrasado caia na partição da data de ingestão ou seja
perdido.

## Limitação da validação nesta máquina

Os testes Python de materialização foram executados localmente. A execução
integral da migração e do CDC depende do Docker Desktop, que estava desligado
no momento da validação; o roteiro acima é a reprodução a executar pelos
colegas antes do PR.
