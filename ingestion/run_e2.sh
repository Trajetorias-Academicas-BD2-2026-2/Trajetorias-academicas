#!/usr/bin/env bash
# Roteiro completo da E2, com saída usada como evidência (docs/evidencias/e2-roteiro.txt).
#   docker compose run --rm --build e2-cdc bash ingestion/run_e2.sh
# Pré-requisito: docker compose up (banco carregado; a V010 já capturou os INSERTs da carga).
set -euo pipefail

passo() { printf '\n===== %s =====\n' "$*"; }

passo "1. Lote completo, duas vezes (idempotência)"
python ingestion/batch_to_delta.py
python ingestion/batch_to_delta.py

passo "2. Dado atrasado: reserva de 2023.1 numa coleta posterior, reprocessando só a janela"
python ingestion/demo_atraso.py

passo "3. CDC: primeiro consumo (eventos da carga do OLTP)"
python ingestion/cdc_consumer.py

passo "4. Mudança real no OLTP: renomear FGA0137 e mudar a carga horária"
python ingestion/demo_change.py --disciplina FGA0137 --nome "SISTEMAS DE BANCO DE DADOS 1 (REVISADA)" --carga-horaria 90

passo "5. Consumidor cai depois de escrever no Delta e antes do checkpoint"
FAIL_BEFORE_CHECKPOINT=1 python ingestion/cdc_consumer.py || echo "(falha esperada)"

passo "6. Reexecução: relê os mesmos eventos (at-least-once), o MERGE não duplica"
python ingestion/cdc_consumer.py

passo "7. Terceira execução: nada novo"
python ingestion/cdc_consumer.py

passo "8. Reverter a disciplina (outro UPDATE) e consumir"
python ingestion/demo_change.py --disciplina FGA0137 --reverter
python ingestion/cdc_consumer.py

passo "9. Verificação contra o OLTP"
python ingestion/verify_e2.py

echo
echo "E2 concluída: lote idempotente, janela reprocessada com dado atrasado, CDC reexecutado sem duplicação."
