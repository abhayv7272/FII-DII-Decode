# Start Here

## What this folder contains

A complete hardened NIFTY research/decision-support project with:

- resilient multi-source 9 PM data hub;
- options, futures, participant OI, VIX, cash and global context;
- chronological backtesting and model promotion gates;
- next-day professional report and Monday–Friday ATR risk map;
- fail-closed WAIT behavior;
- GitHub Actions weekday schedule;
- email delivery to `abhayv7272@gmail.com`;
- source-health manifest, hashes, cache and artifacts;
- comprehensive handoff and ultra-hard bug audit.

## Read in this order

1. `GITHUB_SETUP.md`
2. `SECRETS_CHECKLIST.md`
3. `docs/CHAT_HANDOFF.md`
4. `reports/ultra_hard_audit.md`
5. `README.md`
6. `NEW_CHAT_PROMPT.txt`

## Local smoke test

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q tests
python run_production.py --date auto
```

## GitHub setup summary

- Upload the contents of this folder to the repository root.
- Enable Actions read/write permissions.
- Add the five SMTP GitHub Secrets.
- Manually run the workflow once.
- Never commit an email password or App Password.

## Current model truth

The earlier optimistic derivative accuracy was revoked after hardening. The corrected candidate fails the profitability/promotion gate. The authoritative production policy is **WAIT / NO TRADE** until a model passes all forward-validation gates.
