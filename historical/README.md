# Compact historical research inputs

This directory contains consolidated **point-in-time historical inputs** for
reproducible model research and the v3 forward-validation gate. They are not
live stores and are never overwritten by the scheduled workflow.

- Source mirror: `https://github.com/sahilempire/groww-market-data`
- Pinned source commit: `7d481cf1fcffe44be68852892028195c4f12dddd`
- Source format: archive-shaped public NSE reports; source provenance and the
  raw-archive hashes are in `reports/backtest_2023-08_to_2026-09/provenance.json`.
- Built at UTC: `2026-09-18T01:14:45.356026+00:00`
- Raw file counts: participant OI 760, index close 759, participant volume 759

| File | Rows | Date range | SHA-256 |
|---|---:|---|---|
| `participant_oi.csv` | 3,800 | 2023-08-04 to 2026-09-04 | `c25424cd63779a4a259a757b59dcefb64b979969986adce98bbb19de3bfce94b` |
| `nifty_ohlc.csv` | 759 | 2023-08-07 to 2026-09-04 | `636b1bfeadf7259da04975b9045a46f9d706d20c986cdace95154bfee82d336e` |
| `participant_vol.csv` | 3,795 | 2023-08-04 to 2026-09-04 | `4defbac58ced33c8cb5ceb22bdeeaec902035a333dc9728ef8a1f09932dc6404` |

## Intended use

```bash
python backtest.py \
  --participant-oi historical/participant_oi.csv \
  --ohlc historical/nifty_ohlc.csv \
  --decoder-version v3 \
  --output-dir /tmp/v3-replay

PYTHONPATH=src python research/v3_forward_validation.py
```

Participant volumes are research-only; they are not consumed by the locked
v2 or candidate-v3 production score. Daily OHLC is sufficient for historical
close-to-close and gap diagnostics, but not for validating 10–15 minute
level-reclaim, sweep, stop, or slippage claims.
