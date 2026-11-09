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
  docker compose run --rm analytics
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
