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

python /workspace/analytics/etl_reverso.py
