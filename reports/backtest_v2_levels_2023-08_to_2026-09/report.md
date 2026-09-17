# NIFTY FII/DII Decode Backtest

> **Run provenance (level-enabled run, 2026-09-18).** This is the first audit run
> with dated option-chain input, so the level-reaction proxy is populated. The
> 757 option-chain snapshots were rebuilt from public NSE **F&O bhavcopy**
> archives by `research/bhavcopy_to_option_chain.py`, using the mirror
> `sahilempire/groww-market-data` pinned at
> `7d481cf1fcffe44be68852892028195c4f12dddd`. `underlyingValue` is the same-date
> Nifty 50 **close** from `nse_archives/index_close`; no later session's data was
> used on any date.
>
> **What these reconstructions are not:** bhavcopy publishes EOD
> settlement/close, not a 15:30 LTP, and no implied volatility (emitted as 0).
> Only the nearest non-expired expiry is emitted, matching the live fetcher.
> Level metrics below are therefore a **daily-bar proxy**: they cannot confirm
> 10-15 minute candle reactions, intraday sweep-then-reclaim, touch sequencing,
> or stops/slippage. Read them as "did the daily close respect the level", not
> as trade accuracy.

> Point-in-time replay of the participant-OI decoder. This is classification evaluation, not a trading-P&L claim and not investment advice.

## Evaluation contract

- Decoder rule set: **v2**.
- Signal date **D** uses D participant OI and the exact previous trading session's OI.
- Target is the **next trading session close-to-close return**.
- Actual FLAT band: **±0.150%** (inclusive).
- `SIDEWAYS-UP` → UP, `SIDEWAYS-DOWN` → DOWN, `RANGE` → FLAT.
- Historical cash flow is not used; a current API response is never applied to old dates.

## Summary

| Metric | Result |
|---|---:|
| Evaluable signals | 757 |
| Signal period | 2023-08-08 to 2026-09-03 |
| Exact 3-class accuracy | 37.91% |
| Directional hit rate | 43.72% |
| Directional coverage | 72.52% |
| Trigger-eligible calls | 517 (68.30%) |
| Trigger-eligible hit rate incl. FLAT misses | 43.91% |
| Trigger-eligible non-FLAT sign | 55.23% (411 samples) |
| Majority-class baseline | 42.14% |

Directional hit rate scores UP/DOWN calls; a directional call followed by a FLAT day is a miss. V2 trigger-eligible means `CONDITIONAL_*`; conflict/wait and no-edge states abstain.

## Per-class precision / recall

| Class | Actual | Calls | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| UP | 319 | 267 | 44.19% | 36.99% | 40.27% |
| FLAT | 160 | 208 | 22.60% | 29.38% | 25.55% |
| DOWN | 278 | 282 | 43.26% | 43.88% | 43.57% |

## Confusion matrix (actual rows)

| Actual \ Predicted | UP | FLAT | DOWN |
|---|---:|---:|---:|
| UP | 118 | 94 | 107 |
| FLAT | 60 | 47 | 53 |
| DOWN | 89 | 67 | 122 |

## Setup strength vs accuracy

| Setup strength bucket | N | Mean setup strength | Exact accuracy | Directional hit rate |
|---|---:|---:|---:|---:|
| 0-20 | 190 | 10.05% | 23.68% | n/a |
| 20<x<=40 | 192 | 30.71% | 39.06% | 41.95% |
| 40<x<=60 | 119 | 50.08% | 42.86% | 42.86% |
| 60<x<=80 | 106 | 69.90% | 42.45% | 42.45% |
| 80<x<=100 | 150 | 95.65% | 47.33% | 47.33% |

## Institutional-level reaction (daily-bar proxy)

Tolerance band: **±0.050%** around the level.
A support test succeeds when the next daily close is at/above support; a resistance test succeeds when it closes at/below resistance.

| Observation | Tests | Holds | Accuracy |
|---|---:|---:|---:|
| All levels | 685 | 337 | 49.20% |
| Support | 346 | 162 | 46.82% |
| Resistance | 339 | 175 | 51.62% |

> This is not 15-minute reaction accuracy: daily OHLC cannot prove sequence, volume, liquidity sweeps, or an intraday hold-and-retest.

## Data quality

- Skipped signal dates: **3**
- Option-chain snapshots matched to evaluated dates: **757**
- `missing_signal_ohlc`: 1
- `no_previous_market_session`: 1
- `no_next_market_session`: 1

## Limitations

- Accuracy is sensitive to the declared FLAT threshold; compare thresholds before drawing conclusions.
- The stored confidence/setup-strength value is heuristic, not a calibrated probability; the buckets test whether it is empirically monotonic.
- The report does not include transaction costs, slippage, tradable entry timing, or position sizing.
- Option-chain level metrics require genuine end-of-day snapshots from each signal date; a current snapshot must not be copied backward.
- Expiry-regime, volatility-regime, and sample-size breakdowns become meaningful only with enough real history.
