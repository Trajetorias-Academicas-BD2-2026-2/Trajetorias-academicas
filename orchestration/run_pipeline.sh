#!/usr/bin/env bash
# Orquestração do pipeline: um grafo linear de dependências, com retry por etapa.
#
#   db (saudável) -> migrate -> loader -> analytics (dbt: freshness, snapshot,
#   modelos, testes; ETL reverso) -> analytics-tests [-> ml -> ml-tests]
#
# Cada etapa roda com --no-deps: a ordem é a deste script, não a do Compose,
# para que uma falha pare o grafo na etapa que falhou e só ela seja repetida.
# Uma etapa é repetida até RETRIES vezes, com espera crescente (BACKOFF, 2*BACKOFF...).
#
#   ./orchestration/run_pipeline.sh                         execução normal
#   BACKFILL_SEMESTRE=2024.1 ./orchestration/run_pipeline.sh reprocessa uma janela
#   ML=1 ./orchestration/run_pipeline.sh                     inclui a camada vetorial
set -euo pipefail
cd "$(dirname "$0")/.."

RETRIES="${RETRIES:-3}"
BACKOFF="${BACKOFF:-5}"
export BACKFILL_SEMESTRE="${BACKFILL_SEMESTRE:-}"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }

etapa() {
    local nome="$1"; shift
    local tentativa=1
    while true; do
        log "[$nome] tentativa $tentativa/$RETRIES"
        if "$@"; then
            log "[$nome] ok"
            return 0
        fi
        if [ "$tentativa" -ge "$RETRIES" ]; then
            log "[$nome] FALHOU após $RETRIES tentativas; etapas seguintes não executadas" >&2
            exit 1
        fi
        local espera=$((BACKOFF * tentativa))
        log "[$nome] falhou; nova tentativa em ${espera}s" >&2
        sleep "$espera"
        tentativa=$((tentativa + 1))
    done
}

db_saudavel() {
    local id
    id="$(docker compose ps -q db)"
    [ -n "$id" ] && [ "$(docker inspect -f '{{.State.Health.Status}}' "$id")" = "healthy" ]
}

etapa db               db_saudavel
etapa migrate          docker compose run --rm --no-deps migrate
etapa loader           docker compose run --rm --no-deps loader
etapa analytics        docker compose run --rm --no-deps analytics
etapa analytics-tests  docker compose --profile test run --rm --no-deps analytics-tests
if [ "${ML:-0}" = "1" ]; then
    etapa ml           docker compose --profile ml run --rm --no-deps ml
    etapa ml-tests     docker compose --profile ml run --rm --no-deps ml-tests
fi
log "pipeline concluído${BACKFILL_SEMESTRE:+ (backfill $BACKFILL_SEMESTRE)}"
