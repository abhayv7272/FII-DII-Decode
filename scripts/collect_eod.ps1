param([string]$Date = (Get-Date -Format "yyyy-MM-dd"))
Set-Location (Join-Path $PSScriptRoot "..")
python -m src.collector eod --date $Date
