#!/usr/bin/env bash
set -e

echo "========================================================================"
echo "🚀 LAUNCHING SMART MONEY INSTITUTIONAL PREDICTION ENGINE"
echo "========================================================================"

# Check if python3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed. Please install Python 3.10+."
    exit 1
fi

# Run the master prediction script
python3 src/main.py

echo ""
echo "========================================================================"
echo "📊 Report generated! Open 'reports/latest_prediction_report.html' in your browser."
echo "========================================================================"
