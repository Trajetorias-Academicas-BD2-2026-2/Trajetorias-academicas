#!/usr/bin/env bash
# Demonstração do ETL reverso da E4 (saída em docs/evidencias/e4-etl-reverso.txt):
# a Pauta da coordenação fora do ar, a volta, o reenvio sem duplicar e o
# coordenador agindo sobre o item.
#   ./orchestration/demo_etl_reverso.sh
# Pré-requisito: docker compose up (banco, dbt e métricas oficiais prontos).
set -euo pipefail
cd "$(dirname "$0")/.."

passo() { printf '\n===== %s =====\n' "$*"; }
etl() { docker compose run --rm --no-deps analytics python /workspace/analytics/etl_reverso.py 2>&1 | grep -v Container; }
no_destino() { curl -fsS localhost:8090/api/itens | python3 -c 'import json,sys; d=json.load(sys.stdin); r=sum(1 for i in d if i["revisado_em"]); print("itens na Pauta:", len(d), "| revisados:", r)'; }
fila() { docker compose exec -T db psql -U g2 -d ofertas_unb -X -qAt -F ' | ' -c "select 'fila de envio: ' || status, count(*), max(tentativas) || ' tentativas', coalesce(max(ultimo_erro), '') from operations.envio_pauta group by status order by status"; }

passo "0. Começo limpo: fila de envio vazia e Pauta sem itens"
docker compose exec -T db psql -U g2 -d ofertas_unb -X -qc "truncate operations.envio_pauta"
docker compose rm -sf coordenacao >/dev/null 2>&1
docker volume rm -f "$(basename "$PWD" | tr '[:upper:]' '[:lower:]')_pauta_dados" >/dev/null 2>&1 || true

passo "1. A Pauta da coordenação está fora do ar e o pipeline roda"
etl
fila

passo "2. A Pauta volta e o pipeline roda de novo: os pendentes são entregues"
docker compose up -d coordenacao >/dev/null 2>&1
for _ in $(seq 1 20); do curl -fsS localhost:8090/saude >/dev/null 2>&1 && break; sleep 1; done
etl
fila
no_destino

passo "3. Nova execução, nada mudou: nada é reenviado"
etl
no_destino

passo "4. Reenvio forçado da mesma versão (como após uma queda no meio do envio): o destino não duplica"
docker compose exec -T db psql -U g2 -d ofertas_unb -X -qc "update operations.envio_pauta set status = 'pendente' where status = 'enviado'"
etl
no_destino

passo "5. O coordenador de Eletrônica abre a pauta e marca um item como revisado"
CHAVE=$(curl -fsS "localhost:8090/api/itens?curso=FGA_ELET" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["chave"])')
curl -fsS -o /dev/null -X POST "localhost:8090/api/itens/$CHAVE/revisar"
curl -fsS "localhost:8090/api/itens?curso=FGA_ELET" | python3 -c 'import json,sys; d=json.load(sys.stdin); i=[x for x in d if x["revisado_em"]][0]; print("revisado:", i["titulo"], "em", i["revisado_em"])'
no_destino

passo "6. Opção nula: o mesmo conteúdo como CSV por curso"
docker compose run --rm --no-deps analytics python /workspace/analytics/exportar_pauta_csv.py 2>&1 | grep -v Container
wc -l saida/pauta_*.csv

echo
echo "ETL reverso demonstrado: destino fora do ar não derruba o pipeline nem perde item; reenvio não duplica."
