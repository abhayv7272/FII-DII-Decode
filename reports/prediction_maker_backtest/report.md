# Prediction-Maker Backtest Report Card

> Educational research, not investment advice. This report scores each precise
> forecast claim in the email separately. It does not invent one misleading
> accuracy number for conditional scenario branches.

## Overall verdict: **NOT_READY_AS_A_STANDALONE_TRADING_PREDICTOR**

The complete daily next-day + Mon–Fri + level/sweep system is **not** yet
validated as a standalone trading predictor. The tables below show exactly
what is and is not supported by the historical evidence.

## 1. Next-day UP / DOWN / CONSOLIDATION

| Model used in report | Samples | Exact 3-class accuracy | Majority baseline | Executable next-open-to-close sign | Result |
|---|---:|---:|---:|---:|---|
| v2 (current default) | 757 | 37.91% | 42.14% | 49.41% (n=425) | Below baseline / not standalone |
| v3 (research candidate) | 757 | 45.05% | 42.14% | 51.30% (n=579) | Not promoted: executable basis is near chance |

**Meaning:** v2 is the current emailed OI context. Its exact next-day
UP/FLAT/DOWN result is below the naive majority baseline. V3 has a stronger
close-to-close research number, but the usable entry-at-next-open result does
not establish a trade edge, so it remains opt-in research only.

## 2. Weekly Monday–Friday prediction

| Status | Samples | Exact 3-class accuracy | Majority baseline | 2026 confirmation exact | 2026 baseline |
|---|---:|---:|---:|---:|---:|
| Rejected weekly candidate; production abstains | 753 | 32.14% | 43.96% | 29.34% | 49.70% |

**Meaning:** the report correctly provides a Mon–Fri scenario playbook, but
must not claim a validated weekly UP/DOWN direction prediction yet.

## 3. Support, resistance, break and sweep claims

| Claim tested | Tests | Hold / reject accuracy | Support | Resistance | Result |
|---|---:|---:|---:|---:|---|
| Option-chain level daily-bar proxy | 685 | 49.20% | 46.82% | 51.62% | Near coin-flip; no generic edge |

V7/V8/V9 reran intraday candle confirmation and target/stop simulations. None
produced a robust 70%+ production rule across train, validation, and 2026
confirmation. Therefore level rows in the email remain conditional plans, not
promised trades.

## 4. India VIX EOD range context

| Fixed range claim | Development lift | 2025 validation lift | 2026 confirmation lift | Result |
|---|---:|---:|---:|---|
| ELEVATED VIX → above-typical absolute move | 2.87% | 8.82% | 12.93% | NOT_PROMOTED |
| QUIET VIX → below-typical absolute move | -2.33% | 2.94% | 15.23% | NOT_PROMOTED |

Both pre-specified range-context rules failed at least one locked partition
gate, so the report does **not** add VIX-based range wording or a direction
override. This is not an UP/DOWN test; it does not alter locked v2.

## 5. V10 at-open tiny-gap alert

| Event prediction | Calls | Overall | Train 2017–23 | Validation 2024–25 | Confirmation 2026 |
|---|---:|---:|---:|---:|---:|
| abs gap 0.03% to <0.12% → previous close touched intraday | 393 | 90.33% | 89.11% | 94.23% | 87.50% |

Mean target distance: **12.99 NIFTY points**.
This high statistic applies only after the opening price is known and only to
a previous-close **touch**. It is not a next-day close direction forecast.
The raw-1-minute V11 execution audit found **0** robust positive-P&L 70%
target/stop conversions, so V10 is an alert/context module, not a trade bot.

## Deployment decision

- **Keep:** daily OI context, conditional range/break/reclaim map, and V10
  at-open level-touch alert with its warning.
- **Do not claim yet:** reliable every-day next-day direction, weekly direction,
  generic sweep/break trade, or automated target/stop profitability.
- **Next validation:** continue untouched live forward tracking and collect
  timestamped option-chain, option-premium/spread, GIFT/pre-open, live VIX, sector
  leadership, and exact institutional-level data before changing any rule.

## Method and audit sources

- v2/v3 and weekly rows are recalculated by this run from committed point-in-time
  participant-OI and NIFTY OHLC history.
- India VIX audit: `recomputed from historical/india_vix_ohlc.csv via research/india_vix_regime_audit.py`.
- Level proxy: `reports/backtest_v2_levels_2023-08_to_2026-09/metrics.json`.
- V10: `recomputed from historical/nifty_15m.csv`.
- V7 intraday level confirmation: `reports/v7_intraday_institutional_levels/summary.json` → NO_VALIDATED_EDGE.
- V8 intraday target/stop simulation: `reports/v8_intraday_trade_sim/summary.json` → NO_VALIDATED_EDGE.
- V9 OI + intraday confirmation: `reports/v9_oi_intraday_confirmation/summary.json` → NO_VALIDATED_EDGE.
- V11 V10 execution audit: `reports/v11_gap_sniper_execution/summary.json` → NO_VALIDATED_EDGE.
