# v3 forward-validation gate

Forward window: signal dates **2026-09-05** onward (fitted archive ended 2026-09-04).
Data available: OI through 2026-09-17, NIFTY bars through 2026-09-04.

## Gate state: **COLLECTING_DATA**

| Check | Result |
|---|---|
| enough_signals | no |
| v3_beats_baseline | no |
| v3_beats_v2 | no |
| v3_sign_target | no |

| Version | Signals | Exact | Baseline | Coverage | Non-FLAT sign | Wilson lo | Open-Close sign |
|---|---:|---:|---:|---:|---:|---:|---:|
| v1 | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| v2 | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| v3 | 0 | n/a | n/a | n/a | n/a | n/a | n/a |

`COLLECTING_DATA` until at least 60 evaluable forward sessions accumulate via the daily 9 PM IST workflow stores (data/participant_oi.csv + data/index_ohlc.csv), optionally augmented by --extra-* refreshed mirrors. Rerun: `PYTHONPATH=src python research/v3_forward_validation.py`.
