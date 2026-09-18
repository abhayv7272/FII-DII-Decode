# Prediction Maker Status — Original Goal vs Current Evidence

## Original goal

Build a real NIFTY prediction maker that can be emailed daily and answer:

1. **Next day:** UP / DOWN / CONSOLIDATION.
2. **Coming week (Mon-Fri):** likely UP / DOWN / CONSOLIDATION or range context.
3. **Levels:** from which level price may go up/down, reject, break, role-flip, or sweep.
4. **Actionability:** whether the setup is tradable or should be skipped.
5. **Validation:** backtest honestly before deployment so the user can decide whether it is reliable enough to use.

## What is already built

The repository already has an email/report pipeline that produces:

- FII/DII/Pro/Client participant-OI decode.
- Option-chain proxy support/resistance levels when same-date option chain is available.
- Gap-up / flat / gap-down scenario plan.
- Level-by-level hold/reject and break/role-flip branches.
- Weekly positional carry context.
- GitHub Actions schedule for weekday reports.
- Research harnesses V2-V11 and saved reports.

## Current validation result for the full goal

The **full original predictor** — every-day next-session/next-week UP/DOWN/CONSOLIDATION with level/sweep actionability — is **not production validated yet** at 75-85%+ accuracy.

Key evidence:

- V2 production OI decoder: 37.91% exact UP/FLAT/DOWN on 757 sessions, below 42.14% majority baseline.
- V3 candidate: 45.05% exact, better than V2/baseline in untouched splits, but not tradable because most gain comes from overnight gap channel and open-to-close remains near chance.
- V4-V9 aggressive psychology/OI/intraday searches: **0** robust 70-85% directional/trade rules after holdout, sample, leakage, and post-entry guards.
- V11 execution audit: **0** simple target/stop conversions for V10 passed robust 70% + positive-P&L gates.

Therefore the honest deployment status for the full original aim is:

> **Prediction maker can generate an educational conditional report, but it is not yet proven reliable enough to be used as a standalone trading system.**

## What V10 actually means

V10 is a **supporting sniper module**, not the full predictor.

It found this narrow at-open level-touch rule:

- If NIFTY opens with an absolute gap between **0.03% and 0.12%** from previous close,
- predict that **previous close will be touched intraday**.

Backtest for that narrow event:

| Rule | Calls | Overall | Train 2017-23 | Validation 2024-25 | Confirmation 2026 |
|---|---:|---:|---:|---:|---:|
| `abs_gap_0.03_0.12_both_fill_prev_close` | 393 | 90.33% | 89.11% | 94.23% | 87.50% |

This does **not** mean:

- every day prediction is 90% correct;
- next-day UP/DOWN/CONSOLIDATION is 90% correct;
- next-week prediction is 90% correct;
- a standalone options trade is ready.

It means only:

> On the subset of days where the tiny-gap condition occurs after market open, the previous close was touched intraday about 90% of the time historically.

## Correct product interpretation

The prediction maker should be treated as a **multi-module decision report**:

1. **Night-before / 9 PM report:** OI, participant positioning, option-chain walls, next-day scenarios, weekly context.
2. **At-open sniper add-on:** if the V10 tiny-gap condition triggers, show previous-close touch alert.
3. **Level plan:** support/resistance hold, rejection, break, role-flip, sweep/reclaim branches.
4. **Risk gate:** if evidence is not robust, say `NO TRADE / CONTEXT ONLY` instead of forcing a fake confident call.

## What data is still needed to chase the full aim honestly

To make the full original prediction maker stronger, the missing data is:

- Historical intraday option-chain snapshots: OI, change in OI, volume, IV, premiums by strike through the day.
- Tick or broker option-premium execution data for actual entries/exits/slippage.
- GIFT Nifty / pre-open / global-market inputs available before Indian open.
- Intraday heavyweight stock/sector leadership (Reliance, HDFC Bank, ICICI Bank, Infosys, TCS, etc.).
- India VIX, straddle premium, expiry/event calendar, and exact timestamped institutional levels.

Without these, the current public EOD/OI/intraday-index data has not proven a full 75-85% next-day/weekly directional predictor.
