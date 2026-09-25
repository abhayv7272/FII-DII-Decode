# NIFTY Professional Decision Report — 2026-09-24

**Generated:** 2026-09-26T00:56:16.967846+05:30
**Data quality:** 95%
**Data gate:** **PASS**
**Final decision:** **WAIT / NO TRADE**

**Event-calendar status:** NO_VERIFIED_CALENDAR — verified calendar unavailable; check manually
**RESEARCH PROMOTION GATE FAILED:** corrected holdout/cost metrics do not support a live directional trade.
**Diagnostic only:** raw class probability is not a calibrated profit probability and is excluded from the weekly centre.

## Executive view

- Specialist direction: **DOWN**
- UP/DOWN probability: **22.99% / 77.01%**
- Model confidence: **77.01%**; frozen gate: **75%**
- Prediction/session match: **True**
- Critical fresh/date-matched data: **nifty_price=True, nifty_options_eod=True, nifty_futures_eod=True**
- Compact history update ok: **True**
- Trading stance: **NO DIRECTIONAL POSITION**
- Swing stance: Do not initiate a new swing position until the confidence/data gate and price trigger both pass.
- Investment context: Fresh long-term investment should be deferred or evaluated fundamentally; index is below its 200-day trend.

## Key levels

- Resistance trigger: **23,214.65**
- Pivot: **23,130.40**
- Support trigger: **22,978.85**
- 20-day support/resistance: **23,046.15 / 24,297.45**
- ATR(14): **202.73 points**

## Conditional playbook

### Bull path
Support/pivot hold → close above 23,214.65 → retest holds → only then long continuation is valid.
### Bear path
Resistance rejection → close below 22,978.85 → failed reclaim → only then short continuation is valid.
### Trap rule
A wick/sweep alone is not entry confirmation. Wait for a completed candle and follow-through.

## Monday–Friday risk map

| date       |   session |   expected_center |   lower_risk_band |   upper_risk_band |
|:-----------|----------:|------------------:|------------------:|------------------:|
| 2026-09-25 |         1 |          23063.10 |          22860.37 |          23265.82 |
| 2026-09-28 |         2 |          23063.10 |          22776.40 |          23349.80 |
| 2026-09-29 |         3 |          23063.10 |          22711.97 |          23414.23 |
| 2026-09-30 |         4 |          23063.10 |          22657.65 |          23468.55 |
| 2026-10-01 |         5 |          23063.10 |          22609.79 |          23516.41 |

## What not to do

- Do not trade below the confidence or data-quality gate.
- Do not chase an abnormal opening gap; wait for a new range.
- Do not treat max pain/OI wall as a guaranteed target.
- Do not average a losing leveraged position.
- Do not use this next-day model as the sole basis for long-term investment.

## Data-source health

| Dataset           | Selected source            | Status   | As-of      |   Rows | Stale days   | Error                                                                                                                                              |
|:------------------|:---------------------------|:---------|:-----------|-------:|:-------------|:---------------------------------------------------------------------------------------------------------------------------------------------------|
| nifty_price       | yahoo_yfinance             | fresh    | 2026-09-24 |   2466 |              |                                                                                                                                                    |
| nifty_options_eod | nse_bhavcopy               | fresh    | 2026-09-24 |   1824 |              |                                                                                                                                                    |
| nifty_futures_eod | nse_bhavcopy               | fresh    | 2026-09-24 |      3 |              |                                                                                                                                                    |
| participant_oi    | nselib_participant_archive | fresh    | 2026-09-24 |      5 |              |                                                                                                                                                    |
| india_vix         | yahoo_vix_chart            | fresh    | 2026-09-24 |      6 |              |                                                                                                                                                    |
| fii_dii_cash      | none                       | failed   |            |      0 |              | nse_fiidii_api: future-dated payload 2026-09-25 for session 2026-09-24; groww_public_table: future-dated payload 2026-09-25 for session 2026-09-24 |
| cross_market      | yfinance_multi_asset       | fresh    | 2026-09-24 |     25 |              |                                                                                                                                                    |

## Model evidence

- Later research test: 54.55% accuracy across 99 sessions.
- Selected research sample: 35 signals, 60.00% observed accuracy; this sample is provisional.
- Current report automatically becomes WAIT if critical data, compact-history, date, event, confidence or research-promotion gates fail.

## Risk notice

Research/decision-support only; not personalized investment advice. Futures and options can cause rapid losses. Verify exchange data, liquidity, costs and your risk capacity before any trade.