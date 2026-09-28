#!/usr/bin/env bash
# Carga do lote versionado. Não acessa o SIGAA: o lote em data/ já contém
# tudo e é conferido por checksum antes de entrar no banco.
set -euo pipefail

echo "[1/2] Testes unitários do parsing..."
python -m unittest discover -s tests

echo "[2/2] Carregando o lote ${DATA_DIR:-} no banco..."
python load_to_db.py

echo "Carga completa."
