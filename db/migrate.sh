#!/usr/bin/env bash
# Aplica as migrações de db/migrations/ em ordem, cada uma numa transação,
# e registra as aplicadas em schema_migrations para não reaplicar.
# ON_ERROR_STOP faz qualquer erro de SQL encerrar com código != 0 (sem ele,
# o psql segue em frente e sai com 0, e o compose acharia que deu certo).
set -euo pipefail

DIR="${MIGRATIONS_DIR:-/migrations}"
PSQL=(psql -v ON_ERROR_STOP=1 -q -X)
export PGOPTIONS="${PGOPTIONS:-} -c client_min_messages=warning"

"${PSQL[@]}" -c "CREATE TABLE IF NOT EXISTS schema_migrations (
    versao      TEXT PRIMARY KEY,
    aplicado_em TIMESTAMPTZ NOT NULL DEFAULT now()
)"

for arquivo in $(ls "$DIR"/V*__*.sql | sort -V); do
    versao=$(basename "$arquivo" .sql)
    if [ "$("${PSQL[@]}" -tAc "SELECT 1 FROM schema_migrations WHERE versao = '$versao'")" = "1" ]; then
        echo "= $versao (já aplicada)"
        continue
    fi
    echo "+ aplicando $versao"
    "${PSQL[@]}" -1 -f "$arquivo" -c "INSERT INTO schema_migrations (versao) VALUES ('$versao')"
done
echo "Migrações em dia."
