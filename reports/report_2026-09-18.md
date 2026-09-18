# FII/DII/Pro/Client Decode — NIFTY — 2026-09-18

> ⚠️ **Validation warning:** EXPERIMENTAL / NOT VALIDATED FOR TRADING: the locked v2 rules reached 37.91% exact UP/FLAT/DOWN accuracy on 757 sessions versus a 42.14% majority baseline. Its next-open-to-close sign result remained approximately chance. Treat the OI lean as conditional context, never a standalone entry signal.

**Next-day OI lean (Pro-led):** NEUTRAL  ·  score `-0.07`  ·  setup strength 15/100  ·  RANGE  ·  NO_DIRECTIONAL_EDGE
**Positional carry context (FII-led):** STRONG BEARISH  ·  score `-0.49`  ·  NO-VALIDATED-EDGE  ·  research lean SIDEWAYS-DOWN

## Data Fetch Health

**Overall:** `DEGRADED_FALLBACK_SOURCE`
**Run date:** 2026-09-19 · **Report session:** 2026-09-18

| Input | Status | Source | As of | Warning |
|---|---|---|---|---|
| participant oi current | available | NSE archive | 2026-09-18 |  |
| cash | available | NSE FII/DII API | 2026-09-18 |  |
| option chain | available | MarketNetra EOD option chain | 2026-09-18 | Third-party rendering of NSE EOD chain; payload passed date, spot, expiry and strike/OI validation. |
| index quote | available | NSE all-indices API | 2026-09-18 |  |
| participant volume | available | NSE archive | 2026-09-18 |  |
| participant oi previous | available | NSE archive | 2026-09-17 |  |
| institutional references | not_provided | — | — | Optional exact references were not supplied; automatic levels remain option-chain proxies. |

A next-day OI lean requires complete current and previous participant OI. Actionable level branches additionally require a same-date option chain. Cash can alter setup strength but not the locked OI class; OHLC is an audit input.

## Institutional Data & Setup
- **Retail:** Retail fresh index positioning is mixed; it provides no strong contra confirmation.
- **Move quality:** FII: fresh index-future longs (full-strength bullish), 858 contracts; Pro: index-future long unwinding (weaker bearish), 3,576 contracts

## Full Market Possibility Map

This section is a scenario map for what can happen, not a fake sure-shot call. The validated policy is: context first, entry only after level/price confirmation.

| Market possibility | Trigger to watch | What can happen | Invalidation / wait |
|---|---|---|---|
| Base OI context | Current decoder lean: RANGE / NEUTRAL; actionability NO_DIRECTIONAL_EDGE. | Treat this as bias/context only. A real entry needs price confirmation at support/resistance; the all-day UP/DOWN/CONSOLIDATION model is not validated at 75-85%+. | If data health is degraded, or FII/Pro conflict appears, downgrade to WAIT / context only. |
| Consolidation / range day | Price stays between 23,300.00 (support · option_chain_proxy HIGH_RELATIVE_CONCENTRATION) and 23,400.00 (resistance · option_chain_proxy HIGH_RELATIVE_CONCENTRATION); no clean 10-15m close/retest outside the band. | Expect chop/mean reversion around option walls and max-pain 23350.0; avoid chasing mid-range candles. | A sustained break and retest beyond the band cancels range-first thinking. |
| Bullish expansion path | Support 23,300.00 (support · option_chain_proxy HIGH_RELATIVE_CONCENTRATION) holds/reclaims after a sweep, or resistance 23,400.00 (resistance · option_chain_proxy HIGH_RELATIVE_CONCENTRATION) breaks with a 10-15m close + retest. | Upside route opens toward 23400 (option chain proxy); Pro/FII alignment and put writers holding improve quality. | Failed retest, bearish engulfing back below the wall, or retail crowding against smart money = no fresh long. |
| Bearish rejection / breakdown path | Resistance 23,400.00 (resistance · option_chain_proxy HIGH_RELATIVE_CONCENTRATION) rejects after a sweep, or support 23,300.00 (support · option_chain_proxy HIGH_RELATIVE_CONCENTRATION) breaks with failed reclaim. | Downside route opens toward 23200 (option chain proxy); call writers defending resistance improve quality. | Fast reclaim above broken support/resistance means breakdown/rejection failed; do not average shorts. |
| Liquidity sweep / trap watch | Quick wick beyond support/resistance/round number, then close back inside the prior range. | Possible stop-hunt/manipulation day: first move can be false; trade only the reclaim/rejection candle break. | If price accepts outside the swept level for 10-15 minutes, treat it as breakout/role-flip, not reversal. |
| V10 tiny-gap sniper | At cash open, abs(gap) must be 0.03% to <0.12%; current status INACTIVE_OUTSIDE_BAND. | If active, expect previous-close touch intraday. Direction now: NO_SIGNAL; target —. Observed: not checked. | If open gap is outside the band, ignore this module; do not force a trade from it. |
| No-trade / protect-capital conditions | No same-date levels, no confirming candle, conflicting smart money, wide gap already beyond levels, or violent news candle. | Stand aside until the next clean level interaction. Missing a trade is better than forcing a low-quality prediction. | Conflict note: No explicit FII/Pro conflict flag. |

### Mon–Fri Weekly Playbook

| Week part | Focus | Plan |
|---|---|---|
| Monday | Opening balance / weekly range seed | Mark first reaction around 23,300.00 (support · option_chain_proxy HIGH_RELATIVE_CONCENTRATION) / 23,400.00 (resistance · option_chain_proxy HIGH_RELATIVE_CONCENTRATION). Do not assume trend until one side accepts beyond the range. |
| Tuesday-Wednesday | Expansion attempt | If the same side keeps defending levels and Pro/FII context supports it, allow continuation; otherwise expect rotation. |
| Thursday / expiry context | Premium decay, wall defence, false breaks | Expect sweeps around option walls/max pain; require stricter candle confirmation and avoid late chasing. |
| Friday | Follow-through vs mean reversion | Carry only if the week closes beyond a broken/retested level; otherwise expect mean reversion back into the range. |
| Weekly validation guard | NO-VALIDATED-EDGE | CONTEXT_ONLY_WAIT_FOR_MULTI_SESSION_CONFIRMATION: weekly direction remains context unless multi-session price + participant confirmation appears. |

## Next-Day Conditional Plan (Gap Up / Flat / Gap Down)
- Forced research class: **RANGE** (setup strength 15/100)
- Actionability: **NO_DIRECTIONAL_EDGE**
- OI-only next-day research lean -0.07 (NEUTRAL), Pro-led (ultra-short). Index participant flows do not clear the locked direction threshold; preserve capital rather than forcing an UP/DOWN call. Cash flow contradicts the OI lean; reduce conviction. Retail fresh index positioning is mixed; it provides no strong contra confirmation. Move quality: FII: fresh index-future longs (full-strength bullish), 858 contracts; Pro: index-future long unwinding (weaker bearish), 3,576 contracts. PCR 1.121 — Put/call OI is comparatively balanced. Use confirmed support/resistance branches; PCR alone supplies no direction.
  - **PRIMARY:** No OI branch is preferred. Wait for a confirmed hold/rejection or break/role-flip at the relevant level.
  - **GAP DOWN:** Evaluate support 23300; do not buy merely because price reached it. A liquidity sweep followed by a confirmed reclaim activates the bounce branch. Independently supplied institutional/psychological confluence strengthens the setup. A sustained bearish break BELOW 23300 flips it to resistance and activates the next lower level.
  - **FLAT:** Treat 23300 to 23400 as the decision band. A confirmed support reclaim activates the bounce branch; confirmed resistance rejection activates the fade branch. Without either candle, wait. Direction changes only when a wall breaks and sustains.
  - **GAP UP:** Evaluate resistance 23400. Confirmed rejection activates a move toward 23300; a decisive 15-minute close and retest ABOVE 23400 means the call-side concentration gave way and activates the next upper level.

## V10 Opening Sniper — Previous-Close Touch

- **Status:** NO SIGNAL
- **Rule:** abs(open gap) 0.03% to <0.12% → target previous close intraday.
- **Current signal:** NO_SIGNAL toward —; gap +0.2755%
- **Validation:** overall 90.33% · train 89.11% · val 94.23% · 2026 confirm 87.50%
- **Observed status:** not checked
- **Warning:** V10 validates previous-close touch probability, not a standalone high-RR trade. Use live/tick execution, slippage, option premium, and stop logic before risking capital.

## Next-Week / Positional Context (Mon–Fri)
- Forecast status: **NO-VALIDATED-EDGE**
- Unvalidated research lean: **SIDEWAYS-DOWN**
- Actionability: **CONTEXT_ONLY_WAIT_FOR_MULTI_SESSION_CONFIRMATION**
- Positional carry context -0.36 (research lean SIDEWAYS-DOWN), FII-led with Pro support required. Momentum -0.19. FII index-fut net fell -330,191 over last 2 sessions — shorts building, downside pressure. Big positional moves come only 2-3x a year; otherwise the week trades between the put wall (support) and call wall (resistance) unless a wall breaks decisively. Retail must unwind longs before a sustained up-leg. The carry/trend lean is shown as research context only: its locked five-session candidate did not survive the 2026 confirmation period.
  - **FII carry longs build over several sessions + Pro supports** → Bullish context only; require price/level confirmation.
  - **FII carry shorts build over several sessions + Pro supports** → Bearish context only; require price/level confirmation.
  - **FII and Pro oppose, or Retail remains crowded** → No positional entry; expect range/whipsaw until the conflict resolves.

## Level-by-Level Conditional Prediction

> **Level-method disclosure:** The PDFs do not disclose the proprietary institutional-level formula; they refer viewers to an advanced course. Automatically drawn values are option-chain support/resistance proxies, not reconstructed proprietary levels. Any externally supplied exact references are identified separately.
> **Option-chain input source:** MarketNetra EOD option chain

The OI-lean preferred branch is conditional, not a probability. Without a confirming candle: **WAIT / NO TRADE AT THIS LEVEL**.

| Level | Role | Source | Priority | OI-lean preferred branch | Hold/reject branch | Break/flip branch |
|---:|---|---|---|---|---|---|
| 23000 | support | option_chain_proxy | SECONDARY | WAIT_FOR_CONFIRMED_BRANCH | **BOUNCE_OR_RECLAIM_UP**: 10-15 minute bullish rejection/reclaim; enter only on the confirming candle high break → 23200 (option chain proxy) | **BREAK_DOWN_AND_ROLE_FLIP**: 10-15 minute bearish close below, failed reclaim, and candle low break → next lower level not available |
| 23200 | support | option_chain_proxy | SECONDARY | WAIT_FOR_CONFIRMED_BRANCH | **BOUNCE_OR_RECLAIM_UP**: 10-15 minute bullish rejection/reclaim; enter only on the confirming candle high break → 23300 (option chain proxy) | **BREAK_DOWN_AND_ROLE_FLIP**: 10-15 minute bearish close below, failed reclaim, and candle low break → 23000 (option chain proxy) |
| 23300 | support | option_chain_proxy | IMMEDIATE | WAIT_FOR_CONFIRMED_BRANCH | **BOUNCE_OR_RECLAIM_UP**: 10-15 minute bullish rejection/reclaim; enter only on the confirming candle high break → 23400 (option chain proxy) | **BREAK_DOWN_AND_ROLE_FLIP**: 10-15 minute bearish close below, failed reclaim, and candle low break → 23200 (option chain proxy) |
| 23400 | resistance | option_chain_proxy | IMMEDIATE | WAIT_FOR_CONFIRMED_BRANCH | **REJECTION_DOWN**: 10-15 minute bearish rejection; enter only on the confirming candle low break → 23300 (option chain proxy) | **BREAK_UP_AND_ROLE_FLIP**: 10-15 minute bullish close above, successful retest, and candle high break → 23700 (option chain proxy) |
| 23700 | resistance | option_chain_proxy | SECONDARY | WAIT_FOR_CONFIRMED_BRANCH | **REJECTION_DOWN**: 10-15 minute bearish rejection; enter only on the confirming candle low break → 23400 (option chain proxy) | **BREAK_UP_AND_ROLE_FLIP**: 10-15 minute bullish close above, successful retest, and candle high break → 24000 (option chain proxy) |
| 24000 | resistance | option_chain_proxy | SECONDARY | WAIT_FOR_CONFIRMED_BRANCH | **REJECTION_DOWN**: 10-15 minute bearish rejection; enter only on the confirming candle low break → 23700 (option chain proxy) | **BREAK_UP_AND_ROLE_FLIP**: 10-15 minute bullish close above, successful retest, and candle high break → next upper level not available |

Every row also uses this gap rule: if price opens and sustains beyond the level, treat that level as skipped/flipped and evaluate the next level. Once an opposite-direction break invalidates the original OI lean, later preferred branches are void; follow confirmed price action only.

## Level Evidence

| Strike | Role | Source | Basis | OI | ΔOI | Evidence score | Evidence grade | Confluence |
|---:|---|---|---|---:|---:|---:|---|---|
| 23000 | support | option_chain_proxy (put-side concentration) | put_oi_total_plus_change | 11,000,000 | +1,340,000 | 61.1 | MEDIUM_RELATIVE_CONCENTRATION | — |
| 23200 | support | option_chain_proxy (put-side concentration) | put_oi_total_plus_change | 9,600,000 | +900,000 | 51.5 | MEDIUM_RELATIVE_CONCENTRATION | — |
| 23300 | support | option_chain_proxy (put-side concentration) | put_oi_total_plus_change | 12,700,000 | +5,890,000 | 100.0 | HIGH_RELATIVE_CONCENTRATION | — |
| 23400 | resistance | option_chain_proxy (call-side concentration) | call_oi_total_plus_change | 8,770,000 | +2,250,000 | 85.4 | HIGH_RELATIVE_CONCENTRATION | — |
| 23700 | resistance | option_chain_proxy (call-side concentration) | call_oi_total_plus_change | 9,500,000 | +1,930,000 | 83.4 | HIGH_RELATIVE_CONCENTRATION | — |
| 24000 | resistance | option_chain_proxy (call-side concentration) | call_oi_total_plus_change | 11,600,000 | +1,250,000 | 82.2 | HIGH_RELATIVE_CONCENTRATION | — |

**Max Pain:** 23350.0 · **PCR:** 1.121 — Put/call OI is comparatively balanced. Use confirmed support/resistance branches; PCR alone supplies no direction.

## Decode Signals

| Signal | Score | Weight | Note |
|---|---|---|---|
| Pro_fresh_index | -0.09 | 0.53 | ultra-short driver; relative-OI quality score [index_put -0.43, index_call +0.30, index_fut -0.21] |
| FII_fresh_index | +0.01 | 0.27 | secondary next-day / positional participant; relative-OI quality score [index_put -0.12, index_fut +0.11, index_call +0.11] |
| Client_fresh_index | -0.10 | 0.20 | contra confirmation; relative-OI quality score [index_put -0.54, index_call +0.40, index_fut -0.21] |
| DII_fresh_index | -0.00 | 0.00 | F&O direction ignored (arbitrage contamination); relative-OI quality score [index_put -0.02, index_fut +0.01, index_call +0.01] |
| cash_confirmation | +0.38 | 0.00 | Confirmation only (not fitted in v2 backtest): FII 600 Cr, DII 1,020 Cr. |

## Trading Strategy & Risk Management

Never average a losing option-buy (premium decays to zero) — average at most once, only with a pre-set stop. Risk ≤10–15% capital per trade; scale in (e.g. 5%+5%) and place the stop-loss in the system immediately (~20–25 pts below support for a long). Wait for confluence.

---
_Auto-generated by FII-DII-Decode (participant-OI decode). Educational only — not investment advice._