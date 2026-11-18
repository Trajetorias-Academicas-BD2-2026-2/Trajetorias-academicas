# Orquestração, backfill e performance

## Grafo e agendamento

`orchestration/run_pipeline.sh` executa, nesta ordem e com retry por etapa:

```text
db (saudável) -> migrate -> loader -> analytics -> analytics-tests [-> ml -> ml-tests]
```

`analytics` é o `analytics/run.sh`:

1. `dbt source freshness`;
2. `dbt build` (snapshot SCD, modelos, testes);
3. ETL reverso.

Cada etapa roda com `--no-deps`, então a ordem é a do script e não a do
Compose. Uma etapa é repetida até `RETRIES` vezes (padrão 3), com espera
de `BACKOFF`, 2×`BACKOFF`… segundos. Esgotadas as tentativas, o script
sai com código 1 e as etapas seguintes não rodam.

O agendamento fica em `orchestration/crontab`: todo dia às 02:00, com log
em `logs/pipeline.log`. A linha de instalação está no próprio arquivo.

## Retry demonstrado

[`evidencias/retry.txt`](evidencias/retry.txt):

- **Cenário A:** com `docker compose stop db`, a etapa `db` falha duas
  vezes. O banco volta, a 3ª tentativa passa e o resto do grafo roda.
- **Cenário B:** com o banco fora do ar o tempo todo, o pipeline desiste
  depois de `RETRIES=2`, sai com `exit=1` e não roda o loader nem o dbt.

## Backfill

`fct_reservas` é incremental por janela de semestre (`delete+insert` por `semestre_key`):

| Comando | O que refaz |
|---|---|
| `./orchestration/run_pipeline.sh` | só os semestres com linha ingerida depois da última execução (carga nova ou dado atrasado de semestre antigo) |
| `BACKFILL_SEMESTRE=2024.1 ./orchestration/run_pipeline.sh` | só a janela 2024.1 |
| `FULL_REFRESH=1 docker compose run --rm analytics` | o fato inteiro |

Em [`evidencias/backfill-2024.1.txt`](evidencias/backfill-2024.1.txt), só
2024.1 ganha `processado_em` novo. As contagens dos 9 semestres continuam
as mesmas.

## Plano de execução

```bash
docker compose exec -T db psql -U g2 -d ofertas_unb -X -f - < db/consultas/q6_explain_reservas.sql
```

| | Plano | Buffers | Tempo |
|---|---|---:|---:|
| [antes](evidencias/explain-antes.txt) | nested loop, 1.681 buscas por índice em `reserva_vaga` (o CTE agregado foi estimado em 5 linhas; eram 254) | 5.721 | 3,0 ms |
| [depois](evidencias/explain-depois.txt) | agrega primeiro, hash joins, `curso` no fim | 188 | 1,9 ms |

O resultado das duas versões é idêntico (conferido com `diff`). A V011
remove `idx_reserva_vaga_turma_curso`, que repetia a chave primária.
