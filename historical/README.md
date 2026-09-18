# Historical research bundle

This directory is the durable, point-in-time data bundle used by the NIFTY
prediction-maker research and forward validation. It is intentionally committed
so Arena resets cannot erase the evidence required to evaluate a prediction
claim.

## Provenance and integrity

- Canonical source and construction notes: [`SOURCE.md`](SOURCE.md)
- Pinned input sources and SHA-256 manifest: [`manifest.json`](manifest.json)
- The original raw NSE / bhavcopy / one-minute archives are **not** committed;
  only compact derivatives required by reproducible V3–V11 analysis are kept.

## Contents

| Inputs | Purpose |
|---|---|
| `participant_oi.csv`, `participant_vol.csv`, `nifty_ohlc.csv` | Canonical OI-direction replay and V3 forward-validation base history. |
| `nifty_ohlc_long.csv`, `chain_features.csv` | Price-regime and EOD option-chain feature research. |
| `nifty_10m.csv`, `nifty_15m.csv` | Intraday level, confirmation, sweep, and execution studies. |
| `institutional_levels_pdf_2026.csv` | Manually audited, dated PDF-level research inputs. |

## Rebuild helpers

`research/build_compact_history.py` can rebuild the first three compact CSVs
from a checkout of the pinned Groww source. It is a source-audit/rebuild helper;
run it into a temporary directory first, compare output hashes and schemas with
`manifest.json`, then deliberately replace canonical files only when refreshing
the entire provenance manifest.

```bash
PYTHONPATH=src python research/build_compact_history.py \
  --source-root /path/to/groww-market-data \
  --output-dir /tmp/rebuilt-compact-history
```

`research/build_intraday_candles.py` rebuilds the 10- and 15-minute files from
the documented raw source. The data supports historical analysis, not a promise
of a profitable or stand-alone trading system.
