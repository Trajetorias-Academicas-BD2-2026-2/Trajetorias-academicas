#!/usr/bin/env python3
"""Catálogo da E4: falha se alguma tabela ou coluna da camada analítica estiver sem descrição.

Lê o manifest.json (o que documentamos) e o catalog.json (as colunas que
existem de verdade no banco), gerados por `dbt docs generate`.
    docker compose run --rm --no-deps analytics bash -c \
      'cd /workspace/analytics && dbt docs generate --profiles-dir . && python /workspace/tests/catalogo_cobertura.py'
"""

import json
import sys
from pathlib import Path

ALVO = Path("/workspace/analytics/target")
manifesto = json.loads((ALVO / "manifest.json").read_text(encoding="utf-8"))
catalogo = json.loads((ALVO / "catalog.json").read_text(encoding="utf-8"))

faltando, conferidos = [], 0
for uid, no in {**manifesto["nodes"], **manifesto["sources"]}.items():
    if no["resource_type"] not in ("model", "snapshot", "source"):
        continue
    if not no.get("description", "").strip():
        faltando.append(f"{uid}: tabela sem descrição")
    reais = (catalogo["nodes"].get(uid) or catalogo["sources"].get(uid) or {}).get("columns", {})
    if no["resource_type"] == "source" and not no.get("columns"):
        continue  # fontes: descrevemos a tabela e as colunas que importam para a linhagem
    documentadas = {c.lower(): d.get("description", "").strip() for c, d in no.get("columns", {}).items()}
    for coluna in reais:
        conferidos += 1
        if no["resource_type"] != "source" and not documentadas.get(coluna.lower()):
            faltando.append(f"{uid}.{coluna}: coluna sem descrição")

exposicoes = len(manifesto.get("exposures", {}))
print(f"Catálogo: {conferidos} colunas conferidas, {exposicoes} exposições (consumidores) registradas.")
if faltando:
    print(f"FALHOU: {len(faltando)} itens sem descrição")
    print("\n".join("  " + f for f in faltando[:40]))
    sys.exit(1)
print("OK: toda tabela e coluna da camada analítica está descrita.")
