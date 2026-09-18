# FII/DII/Pro/Client Decode — NIFTY — 2026-09-18

> ⚠️ **Validation warning:** EXPERIMENTAL / NOT VALIDATED FOR TRADING: the locked v2 rules reached 37.91% exact UP/FLAT/DOWN accuracy on 757 sessions versus a 42.14% majority baseline. Its next-open-to-close sign result remained approximately chance. Treat the OI lean as conditional context, never a standalone entry signal.
> 🧪 **Demo warning:** DEMO FIXTURE: inputs are bundled synthetic/approximate sample values for pipeline testing. This report date is not a historical forecast or backtest observation.

**Next-day OI lean (Pro-led):** STRONG BULLISH  ·  score `+0.77`  ·  setup strength 100/100  ·  UP  ·  CONDITIONAL_BULLISH_SETUP
**Positional carry context (FII-led):** BULLISH  ·  score `+0.45`  ·  NO-VALIDATED-EDGE  ·  research lean SIDEWAYS-UP

## Data Fetch Health

**Overall:** `DEMO_FIXTURE`
**Run date:** 2026-09-18 · **Report session:** 2026-09-18

| Input | Status | Source | As of | Warning |
|---|---|---|---|---|
| participant oi current | available | bundled synthetic demo fixture | 2026-09-18 | Synthetic/approximate values; not live market data. |
| participant oi previous | available | bundled synthetic demo fixture | 2026-09-18 | Synthetic/approximate values; not live market data. |
| cash | available | bundled synthetic demo fixture | 2026-09-18 | Synthetic/approximate values; not live market data. |
| option chain | available | bundled synthetic demo fixture | 2026-09-18 | Synthetic/approximate values; not live market data. |
| index quote | unavailable | — | — | Demo fixture has option-chain spot but no independent index OHLC fetch. |
| participant volume | not_used | — | 2026-09-18 | Participant volume is not an input to the locked v2 score. |
| institutional references | not_provided | — | — | Optional exact references were not supplied; automatic levels remain option-chain proxies. |

A next-day OI lean requires complete current and previous participant OI. Actionable level branches additionally require a same-date option chain. Cash can alter setup strength but not the locked OI class; OHLC is an audit input.

## Institutional Data & Setup
- **Retail:** Retail fresh index positioning is bearish (contra-positive), which supports a market bounce only after price confirmation.
- **Move quality:** FII: fresh index-future longs (full-strength bullish), 17,150 contracts; Pro: fresh index-future longs (full-strength bullish), 18,500 contracts

## Full Market Possibility Map

This section is a scenario map for what can happen, not a fake sure-shot call. The validated policy is: context first, entry only after level/price confirmation.

| Market possibility | Trigger to watch | What can happen | Invalidation / wait |
|---|---|---|---|
| Base OI context | Current decoder lean: UP / STRONG BULLISH; actionability CONDITIONAL_BULLISH_SETUP. | Treat this as bias/context only. A real entry needs price confirmation at support/resistance; the all-day UP/DOWN/CONSOLIDATION model is not validated at 75-85%+. | If data health is degraded, or FII/Pro conflict appears, downgrade to WAIT / context only. |
| Consolidation / range day | Price stays between 24,600.00 (support · option_chain_proxy HIGH_RELATIVE_CONCENTRATION) and 25,150.00 (resistance · option_chain_proxy HIGH_RELATIVE_CONCENTRATION); no clean 10-15m close/retest outside the band. | Expect chop/mean reversion around option walls and max-pain 24850.0; avoid chasing mid-range candles. | A sustained break and retest beyond the band cancels range-first thinking. |
| Bullish expansion path | Support 24,600.00 (support · option_chain_proxy HIGH_RELATIVE_CONCENTRATION) holds/reclaims after a sweep, or resistance 25,150.00 (resistance · option_chain_proxy HIGH_RELATIVE_CONCENTRATION) breaks with a 10-15m close + retest. | Upside route opens toward 25150 (option chain proxy); Pro/FII alignment and put writers holding improve quality. | Failed retest, bearish engulfing back below the wall, or retail crowding against smart money = no fresh long. |
| Bearish rejection / breakdown path | Resistance 25,150.00 (resistance · option_chain_proxy HIGH_RELATIVE_CONCENTRATION) rejects after a sweep, or support 24,600.00 (support · option_chain_proxy HIGH_RELATIVE_CONCENTRATION) breaks with failed reclaim. | Downside route opens toward 24450 (option chain proxy); call writers defending resistance improve quality. | Fast reclaim above broken support/resistance means breakdown/rejection failed; do not average shorts. |
| Liquidity sweep / trap watch | Quick wick beyond support/resistance/round number, then close back inside the prior range. | Possible stop-hunt/manipulation day: first move can be false; trade only the reclaim/rejection candle break. | If price accepts outside the swept level for 10-15 minutes, treat it as breakout/role-flip, not reversal. |
| V10 tiny-gap sniper | At cash open, abs(gap) must be 0.03% to <0.12%; current status QUOTE_UNAVAILABLE_PREPARE_PLAYBOOK. | If active, expect previous-close touch intraday. Direction now: DEPENDS_ON_OPEN_GAP; target previous_close. Observed: not checked. | If open gap is outside the band, ignore this module; do not force a trade from it. |
| No-trade / protect-capital conditions | No same-date levels, no confirming candle, conflicting smart money, wide gap already beyond levels, or violent news candle. | Stand aside until the next clean level interaction. Missing a trade is better than forcing a low-quality prediction. | Conflict note: No explicit FII/Pro conflict flag. |

### Mon–Fri Weekly Playbook

| Week part | Focus | Plan |
|---|---|---|
| Monday | Opening balance / weekly range seed | Mark first reaction around 24,600.00 (support · option_chain_proxy HIGH_RELATIVE_CONCENTRATION) / 25,150.00 (resistance · option_chain_proxy HIGH_RELATIVE_CONCENTRATION). Do not assume trend until one side accepts beyond the range. |
| Tuesday-Wednesday | Expansion attempt | If the same side keeps defending levels and Pro/FII context supports it, allow continuation; otherwise expect rotation. |
| Thursday / expiry context | Premium decay, wall defence, false breaks | Expect sweeps around option walls/max pain; require stricter candle confirmation and avoid late chasing. |
| Friday | Follow-through vs mean reversion | Carry only if the week closes beyond a broken/retested level; otherwise expect mean reversion back into the range. |
| Weekly validation guard | NO-VALIDATED-EDGE | CONTEXT_ONLY_WAIT_FOR_MULTI_SESSION_CONFIRMATION: weekly direction remains context unless multi-session price + participant confirmation appears. |

## Next-Day Conditional Plan (Gap Up / Flat / Gap Down)
- Forced research class: **UP** (setup strength 100/100)
- Actionability: **CONDITIONAL_BULLISH_SETUP**
- OI-only next-day research lean +0.77 (STRONG BULLISH), Pro-led (ultra-short). OI-only bullish lean. It becomes actionable only after the relevant option-chain/price level confirms with a 10-15 minute candle; a decisive break activates the opposite backup plan. Cash flow confirms the OI lean, but was not part of historical v2 scoring. Retail fresh index positioning is bearish (contra-positive), which supports a market bounce only after price confirmation. Move quality: FII: fresh index-future longs (full-strength bullish), 17,150 contracts; Pro: fresh index-future longs (full-strength bullish), 18,500 contracts. PCR 1.027 — Put/call OI is comparatively balanced. Use confirmed support/resistance branches; PCR alone supplies no direction.
  - **PRIMARY:** Bullish OI context prefers a confirmed hold/reclaim at 24600 or a confirmed break/retest above 25150; it does not forecast that either path must occur.
  - **GAP DOWN:** Evaluate support 24600; do not buy merely because price reached it. A liquidity sweep followed by a confirmed reclaim activates the bounce branch. Independently supplied institutional/psychological confluence strengthens the setup. A sustained bearish break BELOW 24600 flips it to resistance and activates the next lower level.
  - **FLAT:** Treat 24600 to 25150 as the decision band. A confirmed support reclaim activates the bounce branch; confirmed resistance rejection activates the fade branch. Without either candle, wait. Direction changes only when a wall breaks and sustains.
  - **GAP UP:** Evaluate resistance 25150. Confirmed rejection activates a move toward 24600; a decisive 15-minute close and retest ABOVE 25150 means the call-side concentration gave way and activates the next upper level.

## V10 Opening Sniper — Previous-Close Touch

- **Status:** WAIT FOR OPEN
- **Rule:** abs(open gap) 0.03% to <0.12% → target previous close intraday.
- **Current signal:** DEPENDS_ON_OPEN_GAP toward previous_close; gap —
- **Validation:** overall 90.33% · train 89.11% · val 94.23% · 2026 confirm 87.50%
- **Observed status:** not checked
- **Warning:** This is a level-touch probability, not an unconditional close-direction call or standalone options trade. Execution needs live spread/slippage/stop checks.

## Next-Week / Positional Context (Mon–Fri)
- Forecast status: **NO-VALIDATED-EDGE**
- Unvalidated research lean: **SIDEWAYS-UP**
- Actionability: **CONTEXT_ONLY_WAIT_FOR_MULTI_SESSION_CONFIRMATION**
- Positional carry context +0.16 (research lean SIDEWAYS-UP), FII-led with Pro support required. Momentum -0.19. FII index-fut net fell -330,191 over last 2 sessions — shorts building, downside pressure. Big positional moves come only 2-3x a year; otherwise the week trades between the put wall (support) and call wall (resistance) unless a wall breaks decisively. Retail must unwind longs before a sustained up-leg. The carry/trend lean is shown as research context only: its locked five-session candidate did not survive the 2026 confirmation period.
  - **FII carry longs build over several sessions + Pro supports** → Bullish context only; require price/level confirmation.
  - **FII carry shorts build over several sessions + Pro supports** → Bearish context only; require price/level confirmation.
  - **FII and Pro oppose, or Retail remains crowded** → No positional entry; expect range/whipsaw until the conflict resolves.

## Level-by-Level Conditional Prediction

> **Level-method disclosure:** The PDFs do not disclose the proprietary institutional-level formula; they refer viewers to an advanced course. Automatically drawn values are option-chain support/resistance proxies, not reconstructed proprietary levels. Any externally supplied exact references are identified separately.
> **Option-chain input source:** bundled synthetic demo fixture

The OI-lean preferred branch is conditional, not a probability. Without a confirming candle: **WAIT / NO TRADE AT THIS LEVEL**.

| Level | Role | Source | Priority | OI-lean preferred branch | Hold/reject branch | Break/flip branch |
|---:|---|---|---|---|---|---|
| 24250 | support | option_chain_proxy | SECONDARY | HOLD_OR_RECLAIM | **BOUNCE_OR_RECLAIM_UP**: 10-15 minute bullish rejection/reclaim; enter only on the confirming candle high break → 24450 (option chain proxy) | **BREAK_DOWN_AND_ROLE_FLIP**: 10-15 minute bearish close below, failed reclaim, and candle low break → next lower level not available |
| 24450 | support | option_chain_proxy | SECONDARY | HOLD_OR_RECLAIM | **BOUNCE_OR_RECLAIM_UP**: 10-15 minute bullish rejection/reclaim; enter only on the confirming candle high break → 24600 (option chain proxy) | **BREAK_DOWN_AND_ROLE_FLIP**: 10-15 minute bearish close below, failed reclaim, and candle low break → 24250 (option chain proxy) |
| 24600 | support | option_chain_proxy | IMMEDIATE | HOLD_OR_RECLAIM | **BOUNCE_OR_RECLAIM_UP**: 10-15 minute bullish rejection/reclaim; enter only on the confirming candle high break → 25150 (option chain proxy) | **BREAK_DOWN_AND_ROLE_FLIP**: 10-15 minute bearish close below, failed reclaim, and candle low break → 24450 (option chain proxy) |
| 25150 | resistance | option_chain_proxy | IMMEDIATE | BREAK_UP_AND_ROLE_FLIP | **REJECTION_DOWN**: 10-15 minute bearish rejection; enter only on the confirming candle low break → 24600 (option chain proxy) | **BREAK_UP_AND_ROLE_FLIP**: 10-15 minute bullish close above, successful retest, and candle high break → 25300 (option chain proxy) |
| 25300 | resistance | option_chain_proxy | SECONDARY | BREAK_UP_AND_ROLE_FLIP | **REJECTION_DOWN**: 10-15 minute bearish rejection; enter only on the confirming candle low break → 25150 (option chain proxy) | **BREAK_UP_AND_ROLE_FLIP**: 10-15 minute bullish close above, successful retest, and candle high break → 25350 (option chain proxy) |
| 25350 | resistance | option_chain_proxy | SECONDARY | BREAK_UP_AND_ROLE_FLIP | **REJECTION_DOWN**: 10-15 minute bearish rejection; enter only on the confirming candle low break → 25300 (option chain proxy) | **BREAK_UP_AND_ROLE_FLIP**: 10-15 minute bullish close above, successful retest, and candle high break → next upper level not available |

Every row also uses this gap rule: if price opens and sustains beyond the level, treat that level as skipped/flipped and evaluate the next level. Once an opposite-direction break invalidates the original OI lean, later preferred branches are void; follow confirmed price action only.

## Level Evidence

| Strike | Role | Source | Basis | OI | ΔOI | Evidence score | Evidence grade | Confluence |
|---:|---|---|---|---:|---:|---:|---|---|
| 24250 | support | option_chain_proxy (put-side concentration) | put_oi_total_plus_change | 172,400 | +11,557 | 82.7 | HIGH_RELATIVE_CONCENTRATION | — |
| 24450 | support | option_chain_proxy (put-side concentration) | put_oi_total_plus_change | 207,774 | +10,044 | 87.7 | HIGH_RELATIVE_CONCENTRATION | — |
| 24600 | support | option_chain_proxy (put-side concentration) | put_oi_total_plus_change | 143,253 | +13,047 | 79.3 | HIGH_RELATIVE_CONCENTRATION | — |
| 25150 | resistance | option_chain_proxy (call-side concentration) | call_oi_total_plus_change | 197,680 | +12,944 | 93.0 | HIGH_RELATIVE_CONCENTRATION | — |
| 25300 | resistance | option_chain_proxy (call-side concentration) | call_oi_total_plus_change | 189,478 | +8,323 | 77.9 | HIGH_RELATIVE_CONCENTRATION | — |
| 25350 | resistance | option_chain_proxy (call-side concentration) | call_oi_total_plus_change | 158,275 | +13,031 | 81.8 | HIGH_RELATIVE_CONCENTRATION | — |

**Max Pain:** 24850.0 · **PCR:** 1.027 — Put/call OI is comparatively balanced. Use confirmed support/resistance branches; PCR alone supplies no direction.

## Decode Signals

| Signal | Score | Weight | Note |
|---|---|---|---|
| Pro_fresh_index | +0.74 | 0.53 | ultra-short driver; relative-OI quality score [index_fut +0.90, index_call +0.76, index_put +0.64] |
| FII_fresh_index | +0.74 | 0.27 | secondary next-day / positional participant; relative-OI quality score [index_fut +0.93, index_call +0.76, index_put +0.64] |
| Client_fresh_index | +0.86 | 0.20 | contra confirmation; relative-OI quality score [index_call +0.92, index_fut +0.85, index_put +0.81] |
| DII_fresh_index | -0.00 | 0.00 | F&O direction ignored (arbitrage contamination); relative-OI quality score [index_fut -0.01, index_call -0.00, index_put -0.00] |
| cash_confirmation | +0.57 | 0.00 | Confirmation only (not fitted in v2 backtest): FII 1,150 Cr, DII 1,350 Cr. |

## Trading Strategy & Risk Management

Never average a losing option-buy (premium decays to zero) — average at most once, only with a pre-set stop. Risk ≤10–15% capital per trade; scale in (e.g. 5%+5%) and place the stop-loss in the system immediately (~20–25 pts below support for a long). Wait for confluence.

---
_Auto-generated by FII-DII-Decode (participant-OI decode). Educational only — not investment advice._