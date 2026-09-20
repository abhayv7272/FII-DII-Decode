Set-Location (Join-Path $PSScriptRoot "..")
python run_production.py --date auto *>> data/hub/production.log
