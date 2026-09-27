#!/usr/bin/env bash
set -euo pipefail

echo "[1/5] Raspando componentes curriculares..."
python scrape_componentes.py

echo "[2/5] Raspando cursos e currículos..."
python scrape_cursos.py

echo "[3/5] Raspando pré-requisitos..."
python scrape_prerequisitos.py

echo "[4/5] Raspando oferta de turmas..."
python scrape_turmas.py

echo "[5/5] Carregando staging no banco..."
python load_to_db.py

echo "Carga completa."