# FII/DII/Pro/Client Decode — NIFTY — 2026-09-17

> ⚠️ **Validation warning:** EXPERIMENTAL / NOT VALIDATED FOR TRADING: the locked v2 rules reached 37.91% exact UP/FLAT/DOWN accuracy on 757 sessions versus a 42.14% majority baseline. Its next-open-to-close sign result remained approximately chance. Treat the OI lean as conditional context, never a standalone entry signal.

**Next-day OI lean (Pro-led):** BEARISH  ·  score `-0.22`  ·  setup strength 48/100  ·  SIDEWAYS-DOWN  ·  CONTEXT_ONLY_MISSING_SAME_DATE_OPTION_CHAIN
**Positional carry context (FII-led):** STRONG BEARISH  ·  score `-0.51`  ·  NO-VALIDATED-EDGE  ·  research lean RANGE

## Data Fetch Health

**Overall:** `DEGRADED_MISSING_LEVEL_INPUT`
**Run date:** 2026-09-18 · **Report session:** 2026-09-17

| Input | Status | Source | As of | Warning |
|---|---|---|---|---|
| participant oi current | available | Stocklyzer EOD participant table | 2026-09-17 | Third-party rendering of NSE data; matrix passed completeness and long/short balance checks. Previous session derived from displayed deltas. Independent corroborator unavailable: NiftyTrader participant fallback rejected: NiftyTrader participant matrix table not found |
| cash | unavailable | — | — | Latest validated participant OI is 2026-09-17, not target session 2026-09-18; current-only endpoint was deliberately not mixed in. |
| option chain | unavailable | — | — | Latest validated participant OI is 2026-09-17, not target session 2026-09-18; current-only endpoint was deliberately not mixed in. |
| index quote | unavailable | — | — | Latest validated participant OI is 2026-09-17, not target session 2026-09-18; current-only endpoint was deliberately not mixed in. |
| participant volume | unavailable | — | — | Latest validated participant OI is 2026-09-17, not target session 2026-09-18; current-only endpoint was deliberately not mixed in. |
| participant oi previous | available | Stocklyzer EOD participant table — previous session from displayed deltas | immediately preceding trading session | Third-party rendering of NSE data; matrix passed completeness and long/short balance checks. Previous session derived from displayed deltas. Independent corroborator unavailable: NiftyTrader participant fallback rejected: NiftyTrader participant matrix table not found Previous values equal current minus provider-displayed daily change; no holiday-sensitive date was guessed. |
| institutional references | not_provided | — | — | Optional exact references were not supplied; automatic levels remain option-chain proxies. |

A next-day OI lean requires complete current and previous participant OI. Actionable level branches additionally require a same-date option chain. Cash can alter setup strength but not the locked OI class; OHLC is an audit input.

## Institutional Data & Setup
- **Retail:** Retail fresh index positioning is bullish (contra-negative): upside can remain capped until those longs/short puts unwind.
- **Move quality:** FII: fresh index-future shorts (full-strength bearish), 2,040 contracts; Pro: index-future long unwinding (weaker bearish), 4,025 contracts

## Next-Day Conditional Plan (Gap Up / Flat / Gap Down)
- Forced research class: **SIDEWAYS-DOWN** (setup strength 48/100)
- Actionability: **CONTEXT_ONLY_MISSING_SAME_DATE_OPTION_CHAIN**
- OI-only next-day research lean -0.22 (BEARISH), Pro-led (ultra-short). OI-only bearish lean. It becomes actionable only after the relevant option-chain/price level confirms with a 10-15 minute candle; a decisive break activates the opposite backup plan. Same-date option-chain data is unavailable, so no level entry is actionable. Retail fresh index positioning is bullish (contra-negative): upside can remain capped until those longs/short puts unwind. Move quality: FII: fresh index-future shorts (full-strength bearish), 2,040 contracts; Pro: index-future long unwinding (weaker bearish), 4,025 contracts. PCR None — 
  - **DATA BLOCK:** No same-date support/resistance pair is available. Preserve the OI lean as context only; do not create a gap or level trade from stale data.

## Next-Week / Positional Context (Mon–Fri)
- Forecast status: **NO-VALIDATED-EDGE**
- Unvalidated research lean: **RANGE**
- Actionability: **CONTEXT_ONLY_WAIT_FOR_MULTI_SESSION_CONFIRMATION**
- Positional carry context -0.08 (research lean RANGE), FII-led with Pro support required. Momentum +0.45.  Big positional moves come only 2-3x a year; otherwise the week trades between the put wall (support) and call wall (resistance) unless a wall breaks decisively. Retail must unwind longs before a sustained up-leg. The carry/trend lean is shown as research context only: its locked five-session candidate did not survive the 2026 confirmation period.
  - **FII carry longs build over several sessions + Pro supports** → Bullish context only; require price/level confirmation.
  - **FII carry shorts build over several sessions + Pro supports** → Bearish context only; require price/level confirmation.
  - **FII and Pro oppose, or Retail remains crowded** → No positional entry; expect range/whipsaw until the conflict resolves.

## Level-by-Level Conditional Prediction

> **Level-method disclosure:** No dated option chain was available, so no automatic level proxy or level-by-level prediction was generated.
> **Option-chain input source:** unavailable

The OI-lean preferred branch is conditional, not a probability. Without a confirming candle: **WAIT / NO TRADE AT THIS LEVEL**.

| Level | Role | Source | Priority | OI-lean preferred branch | Hold/reject branch | Break/flip branch |
|---:|---|---|---|---|---|---|
| n/a | n/a | n/a | n/a | NO DATED LEVELS | Wait | Wait |

Every row also uses this gap rule: if price opens and sustains beyond the level, treat that level as skipped/flipped and evaluate the next level. Once an opposite-direction break invalidates the original OI lean, later preferred branches are void; follow confirmed price action only.

## Level Evidence

| Strike | Role | Source | Basis | OI | ΔOI | Evidence score | Evidence grade | Confluence |
|---:|---|---|---|---:|---:|---:|---|---|

**Max Pain:** None · **PCR:** None — 

## Decode Signals

| Signal | Score | Weight | Note |
|---|---|---|---|
| Pro_fresh_index | -0.22 | 0.53 | ultra-short driver; relative-OI quality score [index_put -0.48, index_fut -0.18, index_call +0.01] |
| FII_fresh_index | -0.12 | 0.27 | secondary next-day / positional participant; relative-OI quality score [index_put -0.26, index_fut -0.17, index_call +0.04] |
| Client_fresh_index | -0.34 | 0.20 | contra confirmation; relative-OI quality score [index_put -0.68, index_fut -0.45, index_call +0.06] |
| DII_fresh_index | -0.01 | 0.00 | F&O direction ignored (arbitrage contamination); relative-OI quality score [index_put -0.04, index_fut +0.02, index_call +0.01] |

## Trading Strategy & Risk Management

Never average a losing option-buy (premium decays to zero) — average at most once, only with a pre-set stop. Risk ≤10–15% capital per trade; scale in (e.g. 5%+5%) and place the stop-loss in the system immediately (~20–25 pts below support for a long). Wait for confluence.

---
_Auto-generated by FII-DII-Decode (participant-OI decode). Educational only — not investment advice._