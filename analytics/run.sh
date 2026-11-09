#!/usr/bin/env bash
set -euo pipefail

dbt build --project-dir /workspace/analytics --profiles-dir /workspace/analytics

python /workspace/analytics/etl_reverso.py
