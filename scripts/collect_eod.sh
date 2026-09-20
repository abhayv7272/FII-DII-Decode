#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m src.collector eod --date "${1:-$(TZ=Asia/Kolkata date +%F)}"
