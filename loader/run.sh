#!/usr/bin/env bash
# Orquestra a carga. Com RASPAR=auto (padrão), só acessa o SIGAA para
# o que ainda não está versionado em data/raw/; se o recorte já está no
# repositório, a carga roda offline e produz sempre o mesmo banco.
set -euo pipefail

echo "[1/4] Componentes curriculares e pré-requisitos..."
python scrape_componentes.py

echo "[2/4] Cursos e matrizes curriculares..."
python scrape_cursos.py

echo "[3/4] Oferta de turmas por semestre..."
python scrape_turmas.py

echo "[4/4] Carregando data/raw no banco..."
python load_to_db.py

echo "Carga completa."
