#!/usr/bin/env bash
set -euo pipefail

python ingestion/batch_to_delta.py
python ingestion/demo_change.py --id E2-DEMO-001 --vagas 30
python ingestion/cdc_consumer.py
python ingestion/demo_change.py --id E2-DEMO-001 --vagas 35
python ingestion/cdc_consumer.py
python ingestion/cdc_consumer.py
python ingestion/verify_e2.py

echo "E2 concluída: lote reexecutado e CDC reaplicado sem duplicação."
