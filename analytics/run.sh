#!/usr/bin/env bash
# Transformações, testes e ETL reverso da camada analítica.
#   BACKFILL_SEMESTRE=2024.1  reprocessa só essa janela do fato
#   FULL_REFRESH=1            reconstrói o fato inteiro
set -euo pipefail

DBT=(dbt --no-use-colors)
ARGS=(--project-dir /workspace/analytics --profiles-dir /workspace/analytics)

"${DBT[@]}" source freshness "${ARGS[@]}"

if [ -n "${BACKFILL_SEMESTRE:-}" ]; then
    echo "backfill da janela ${BACKFILL_SEMESTRE}"
    "${DBT[@]}" build "${ARGS[@]}" --vars "{backfill_semestre: '${BACKFILL_SEMESTRE}'}"
elif [ "${FULL_REFRESH:-0}" = "1" ]; then
    "${DBT[@]}" build "${ARGS[@]}" --full-refresh
else
    "${DBT[@]}" build "${ARGS[@]}"
fi

# Camada semântica: grava as métricas oficiais definidas em models/semantic/semantica.yml
python /workspace/analytics/semantica.py

# ETL reverso: itens da pauta para a Pauta da coordenação (API) e, como opção nula, CSV por curso
python /workspace/analytics/etl_reverso.py
python /workspace/analytics/exportar_pauta_csv.py
