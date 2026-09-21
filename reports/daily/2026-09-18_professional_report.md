# NIFTY Professional Decision Report — 2026-09-18

**Generated:** 2026-09-22T01:36:06.714151+05:30
**Data quality:** 98%
**Data gate:** **PASS**
**Final decision:** **WAIT / NO TRADE**

**Event-calendar status:** NO_VERIFIED_CALENDAR — verified calendar unavailable; check manually
**RESEARCH PROMOTION GATE FAILED:** corrected holdout/cost metrics do not support a live directional trade.
**Diagnostic only:** raw class probability is not a calibrated profit probability and is excluded from the weekly centre.

## Executive view

- Specialist direction: **UP**
- UP/DOWN probability: **87.94% / 12.06%**
- Model confidence: **87.94%**; frozen gate: **75%**
- Prediction/session match: **True**
- Critical fresh/date-matched data: **nifty_price=True, nifty_options_eod=True, nifty_futures_eod=True**
- Compact history update ok: **True**
- Trading stance: **NO DIRECTIONAL POSITION**
- Swing stance: Do not initiate a new swing position until the confidence/data gate and price trigger both pass.
- Investment context: Fresh long-term investment should be deferred or evaluated fundamentally; index is below its 200-day trend.

## Key levels

- Resistance trigger: **23,394.83**
- Pivot: **23,340.72**
- Support trigger: **23,292.28**
- 20-day support/resistance: **23,116.10 / 24,378.60**
- ATR(14): **195.57 points**

## Conditional playbook

### Bull path
Support/pivot hold → close above 23,394.83 → retest holds → only then long continuation is valid.
### Bear path
Resistance rejection → close below 23,292.28 → failed reclaim → only then short continuation is valid.
### Trap rule
A wick/sweep alone is not entry confirmation. Wait for a completed candle and follow-through.

## Monday–Friday risk map

| date       |   session |   expected_center |   lower_risk_band |   upper_risk_band |
|:-----------|----------:|------------------:|------------------:|------------------:|
| 2026-09-21 |         1 |          23346.40 |          23150.83 |          23541.97 |
| 2026-09-22 |         2 |          23346.40 |          23069.83 |          23622.98 |
| 2026-09-23 |         3 |          23346.40 |          23007.67 |          23685.13 |
| 2026-09-24 |         4 |          23346.40 |          22955.26 |          23737.54 |
| 2026-09-25 |         5 |          23346.40 |          22909.10 |          23783.70 |

## What not to do

- Do not trade below the confidence or data-quality gate.
- Do not chase an abnormal opening gap; wait for a new range.
- Do not treat max pain/OI wall as a guaranteed target.
- Do not average a losing leveraged position.
- Do not use this next-day model as the sole basis for long-term investment.

## Data-source health

| Dataset           | Selected source            | Status   | As-of      |   Rows |   Stale days | Error                                                                                                                                              |
|:------------------|:---------------------------|:---------|:-----------|-------:|-------------:|:---------------------------------------------------------------------------------------------------------------------------------------------------|
| nifty_price       | yahoo_yfinance             | fresh    | 2026-09-18 |   2465 |              |                                                                                                                                                    |
| nifty_options_eod | nselib_contract_archive    | fresh    | 2026-09-18 |   1700 |              |                                                                                                                                                    |
| nifty_futures_eod | nselib_contract_archive    | fresh    | 2026-09-18 |      3 |              |                                                                                                                                                    |
| participant_oi    | nselib_participant_archive | fresh    | 2026-09-18 |      5 |              |                                                                                                                                                    |
| india_vix         | nse_vix_archive            | fresh    | 2026-09-18 |      1 |              |                                                                                                                                                    |
| fii_dii_cash      | last_good_cache            | cached   | 2026-09-18 |      2 |            0 | nse_fiidii_api: future-dated payload 2026-09-21 for session 2026-09-18; groww_public_table: future-dated payload 2026-09-21 for session 2026-09-18 |
| cross_market      | yfinance_multi_asset       | fresh    | 2026-09-18 |     25 |              |                                                                                                                                                    |

## Model evidence

- Later research test: 54.55% accuracy across 99 sessions.
- Selected research sample: 35 signals, 60.00% observed accuracy; this sample is provisional.
- Current report automatically becomes WAIT if critical data, compact-history, date, event, confidence or research-promotion gates fail.

## Risk notice

Research/decision-support only; not personalized investment advice. Futures and options can cause rapid losses. Verify exchange data, liquidity, costs and your risk capacity before any trade.