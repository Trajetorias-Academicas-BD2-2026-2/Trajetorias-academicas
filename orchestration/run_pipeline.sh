#!/usr/bin/env bash
set -euo pipefail

retries="${RETRIES:-3}"
attempt=1
run_once() {
  if [ "${TEST_FAIL_ONCE:-0}" = "1" ] && [ ! -f "${TEST_RETRY_FILE:-/tmp/g2-pipeline-retry}" ]; then
    touch "${TEST_RETRY_FILE:-/tmp/g2-pipeline-retry}"
    echo "falha controlada para demonstrar retry" >&2
    return 1
  fi
  docker compose run --rm analytics || return 1
  # Camada vetorial opcional (ML=1): P12 vetoriza só textos novos, P13 confere.
  # --no-deps: o analytics acabou de rodar; não repetir loader e dbt.
  if [ "${ML:-0}" = "1" ]; then
    docker compose --profile ml run --rm --no-deps ml || return 1
    docker compose --profile ml run --rm --no-deps ml-tests || return 1
  fi
}

while ! run_once; do
  if [ "$attempt" -ge "$retries" ]; then
    echo "pipeline analítico falhou após ${retries} tentativas" >&2
    exit 1
  fi
  echo "tentativa ${attempt} falhou; repetindo após 2s" >&2
  attempt=$((attempt + 1))
  sleep 2
done

echo "pipeline concluído; para backfill use BACKFILL_SEMESTRE=YYYY.N"
