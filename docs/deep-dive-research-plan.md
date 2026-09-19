# Exhaustive Prediction Research Map

> Last updated: 2026-09-19. Educational research only; not investment advice.
>
> This is an evidence map for pursuing the requested high-accuracy NIFTY
> prediction maker without turning repeated backtests into a false 85% claim.
> A candidate may be promoted only if its entry time, inputs, target, train
> period, validation period, confirmation period and fresh forward evidence are
> all explicit.

## 1. What has already been searched

| Layer | Point-in-time data / test | Main evidence | Honest result |
|---|---|---|---|
| EOD participant OI | FII / DII / Pro / Client index & stock derivatives; 2023-08 to 2026-09 | v2/v3 replay | v2 37.91% three-class close-to-close exact; v3 45.05%, but next-open-to-close stays near chance. |
| Participant volume, positioning and psychology | 4,764 engineered OI, volume, PCR/wall, price-regime and rolling features | V4/V5 | 0 robust 75%+ rules after validation/confirmation and leakage guards. |
| Rule pairs and long price regimes | 319,600 EOD-rule conjunctions and 2010+ price-regime conditions | V6 | 0 robust 75%+ holdout rule. |
| Intraday price confirmation | 10-/15-minute NIFTY bars, 2017-2026 | V7/V8/V9 | 0 robust 70%+ executable target/stop rule after time-of-entry and ambiguity guards. |
| At-open structural level events | NIFTY open / previous close / intraday range | V10/V11 | Tiny 0.03%-0.12% gap previous-close **touch** is 90.33%, but did not convert to a robust standalone trade. |
| Direct calendar-week prediction | Final weekly session → following Monday-Friday close, 4,746 clean EOD features | V12 | 0 of 18,527 fitted rules and 16,110 agreement pairs passed the 85% validation + confirmation gate. |
| India VIX risk state | Same-day EOD India VIX joined to v3 signals, 2023-08 to 2026-08 | V13 | 0 of 1,022 VIX-direct / VIX-gated / VIX-agreement rules passed the 85% gate. Executable open-to-close gates were no better than roughly 50-61% in both holdouts. |

## 2. Data currently available and timing reality

| Input | Coverage in repository | Known at proposed signal time? | Use status |
|---|---|---|---|
| Participant OI | 2023-08-04 to 2026-09-04 | After session close | Core EOD context; cannot capture the overnight gap at that close. |
| Participant volumes | Same period | After session close | Research feature, no validated upgrade. |
| Daily NIFTY OHLC | 2023-08 to 2026-09; longer price-only series to 1990 | EOD | Targets / price-regime only; must never leak D+1 values. |
| Rebuilt EOD option-chain aggregates | 2023-08 to 2026-09 | After session close | Walls/PCR/max-pain proxy; not a timestamped intraday chain. |
| NIFTY 10-/15-minute bars | 2017-04 to 2026-09 | Only after each candle closes | Tested as confirmation; useful for forward protocols. |
| FII/DII cash | Live store begins 2026-09; exploratory 2026 history only | EOD/provisional | Confirmation/context only; insufficient dated history for score fitting. |
| Exact institutional levels | 28 dated PDF-analysis days in 2026 | Depends on source timestamp | Too sparse and clustered for promotion. |
| India VIX | 2020-01 to 2026-08 research-only third-party copy | EOD | Added for V13; no validated daily improvement. |

## 3. Important distinction: prediction time versus label time

A result can look high accuracy but still be unusable if its input was only known
*after* the entry it implies. Every future test must declare one of these modes:

1. **Night-before / EOD plan:** only inputs known after D close; measure D+1
   open-to-close or a later confirmed entry. Do not count the D+1 overnight gap
   as a capturable trade.
2. **At-open plan:** use only the official open, D close and pre-open values
   known before/at the entry; V10 belongs here.
3. **Intraday confirmation plan:** use a completed 5/10/15-minute candle,
   timestamped option-chain/level state and an entry after that candle. Score
   target, stop, spread, slippage and ambiguous-bar outcomes conservatively.
4. **Week-ahead plan:** use final available Friday data; target the following
   Monday-Friday close/range. Never use data published during that next week.

## 4. Missing high-information inputs

The next useful step is not another unconstrained sweep over existing EOD
columns. It is collecting timestamped inputs whose economic timing can explain a
next-open or intraday move.

| Priority | Missing data | Why it matters | Required validation design |
|---:|---|---|---|
| 1 | Intraday option-chain snapshots: OI, ΔOI, volume, IV, bid/ask and premiums by strike/expiry | Lets a level break/reclaim, unwind, writing pressure and option execution be measured when it occurs rather than inferred from EOD totals. | Freeze features and thresholds on a historical train slice; run post-entry target/stop simulation with spreads/slippage; retain a new forward window. |
| 2 | Reliable pre-open GIFT/NIFTY futures, Asia/US close, USDINR, crude, yields and event calendar with timestamps | These can explain the D+1 opening path, which EOD OI cannot know. | Align each series only to values published before the Indian cash open; test separately for gap and open-to-close labels. |
| 3 | Intraday heavyweight-stock/sector leadership and breadth | NIFTY moves can be driven by a few heavyweights; aggregate stock OI cannot identify the driver. | Use only completed intraday bars; test constituent/sector confirmation after entry. |
| 4 | Full historical FII/DII cash sequence from a verifiable source | Cash may confirm/counter derivative positioning. | Use dated source snapshots, provenance hashes and a fixed pre-2026 fit / 2026 holdout. |
| 5 | Exact timestamped institutional levels | Separates externally supplied levels from reproducible option-chain proxies. | Record level time, subsequent first touch/reclaim/break and no-touch cases every day; score forward without retuning. |
| 6 | Broker/tick option-premium execution | A NIFTY level touch is not automatically an option P&L result. | Include actual available premium, bid/ask, fees, fill delay, exits and conservative same-bar ambiguity rules. |

## 5. Deep-dive protocol for each new source

1. **Provenance:** commit/record raw source URL, retrieval date, content hash,
   licence/terms, timezone and known gaps.
2. **Timing audit:** document exactly when the value was available relative to
   the intended entry. Reject any source that cannot establish this.
3. **Schema/quality checks:** non-null dates, duplicate checks, OHLC/price
   consistency, session mapping and a missing-data report.
4. **Frozen experiment:** reserve a genuine confirmation/forward period before
   selecting model thresholds; exclude all target, hit and future-price fields.
5. **Execution-first score:** report coverage, exact class, directional sign,
   confidence interval, target/stop P&L, costs and maximum adverse excursion—
   not a headline percentage alone.
6. **Promotion:** require the declared gate in validation, confirmation and
   fresh forward data. Otherwise surface it only as context / `WAIT`.

## 6. Current product policy

The email report should retain the full scenario map: OI context, range,
bullish/bearish paths, sweep/trap branches, V10 status, explicit no-trade gates
and Monday-Friday playbook. These modules are useful decision structure, but
none should be labelled an 85% all-day or all-week direction forecast until the
protocol above is passed.
