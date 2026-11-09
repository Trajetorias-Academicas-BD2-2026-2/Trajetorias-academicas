# Roteiro de apresentação

## 1. Problema e pergunta (2 min)

O usuário é o coordenador de curso da FCTE. A pergunta é:

> Como evoluíram, entre 2022.1 e 2026.1, as vagas reservadas publicadas
> para cada curso da FCTE nas disciplinas obrigatórias do currículo de
> referência selecionado para 2026.1?

A métrica não é ocupação nem oferta total. Essa limitação veio da coleta real
do SIGAA e é parte da decisão de modelagem.

## 2. Origem e OLTP (3 min)

Mostrar o lote com checksum, as migrações e a carga Docker. Explicar:

- 733 turmas, 1.776 reservas e 9 semestres;
- `turma` e `reserva_vaga` são insert-only;
- o currículo de referência é fixo em 2026.1;
- divergência de lote é recusada, não sobrescrita silenciosamente.

## 3. Ingestão (3 min)

Mostrar Parquet/Delta e a outbox da E2. Executar, se necessário:

```bash
docker compose --profile e2 run --rm --build e2-batch
docker compose --profile e2 run --rm --build e2-cdc
```

Explicar at-least-once, checkpoint, deduplicação e dado atrasado.

## 4. E3 e painel (5 min)

Mostrar o fluxo `staging -> fct_reservas -> mart_observatorio` e abrir
`http://localhost:8080`. Filtrar `FGA_SOFT` e `2024.1`, comparando curso e
semestre.

Executar:

```bash
docker compose run --rm analytics
docker compose --profile test run --rm analytics-tests
```

O resultado esperado é `PASS=18 WARN=0 ERROR=0`.

## 5. E4 e governança (4 min)

Mostrar `operations.alertas_reserva` como ETL reverso, o catálogo/linhagem e a
análise LGPD em `docs/observatorio-e-governanca.md`. Mostrar o papel
`dashboard_reader`: ele lê o mart, não lê `public.turma` e não pode fazer login.

## 6. Evidências técnicas e limites (3 min)

Mostrar:

- `docs/evidencias/explain-antes.txt` e `explain-depois.txt`;
- `docs/evidencias/backfill-2024.1.txt`;
- `docs/evidencias/retry.txt`;
- `docs/evidencias/controle-acesso.txt`.

O `EXPLAIN` mostra que o volume atual é pequeno: os índices não produziram
ganho significativo, e essa é a conclusão correta. O backfill recuperou 174
linhas de 2024.1 sem alterar as 1.776 linhas históricas. O retry teve uma
falha controlada e concluiu na segunda tentativa.

Fechar com as limitações: não há ocupação, a oferta total não está completa e
as versões históricas de currículo são incompletas.
