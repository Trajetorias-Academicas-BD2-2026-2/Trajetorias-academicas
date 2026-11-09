# Orquestração, backfill e performance

## Execução agendada

O arquivo `orchestration/crontab` agenda o pipeline diariamente às 02:00.
`orchestration/run_pipeline.sh` executa o dbt e repete a execução até três
vezes quando o serviço falha. A carga inteira é determinística porque parte do
lote versionado.

## Backfill

O backfill recalcula o histórico completo ou uma janela de semestre:

```bash
docker compose run --rm analytics
psql -h localhost -U g2 -d ofertas_unb \
  -v semestre=2024.1 -f orchestration/backfill.sql
```

O resultado é comparado com a série do mart antes de ser publicado. Como o
domínio tem apenas 1.776 reservas, recomputar o recorte é mais seguro do que
alterar arquivos individuais.

## Plano de execução

Para registrar a medição exigida na E3, execute
`db/consultas/q6_explain_reservas.sql` antes e depois da migração
`V008__indices_consumo_analitico.sql`, salvando as saídas como evidência da
tag da entrega. A consulta mede a agregação usada pelo observatório e inclui
`ANALYZE` e buffers, não apenas o tempo aparente.
