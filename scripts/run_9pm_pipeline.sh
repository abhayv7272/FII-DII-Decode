#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python run_production.py --date auto >> data/hub/production.log 2>&1
