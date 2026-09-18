# India VIX regime audit for the prediction-maker

> Educational research, not investment advice. This tests a small, fixed
> EOD VIX range/risk-context hypothesis—not an UP/DOWN trading signal.

## Decision: **NO_VIX_RULE_PROMOTED**

No VIX rule changes the locked v2 decoder or enables a standalone trade.
The two rule gates below must independently pass in development, on 2025
validation, and on 2026 confirmation before a rule could be shown as qualified
report context.

## Protocol locked before scoring

- VIX close from the signal session is paired only with the following NIFTY
  session's absolute close-to-close return.
- Development targets through **2024-12-31** set every threshold
  (n=342); 2025 is validation and 2026 is confirmation.
- QUIET is VIX ≤ **12.1425**; ELEVATED is VIX ≥ **14.6800**. The typical absolute move is **0.4204%**.
- A claim needs at least 50 development, 25 validation, and 15 confirmation calls, plus ≥5 percentage-point hit-rate lift over the unconditional target frequency in each period.
- A prior broad descriptive VIX correlation was seen. Neither 2025 nor 2026
  fitted thresholds, but neither is described as a newly pristine blind sample.

## Fixed range-context claims

| Claim | Period | Calls | Hits | Hit rate | Unconditional target rate | Lift | Wilson 95% lower |
|---|---|---:|---:|---:|---:|---:|---:|
| ELEVATED VIX → above-typical next-session absolute move | Development through 2024 | 87 | 46 | 52.87% | 50.00% | 2.87% | 42.49% |
| ELEVATED VIX → above-typical next-session absolute move | Validation 2025 | 68 | 40 | 58.82% | 50.00% | 8.82% | 46.96% |
| ELEVATED VIX → above-typical next-session absolute move | Confirmation 2026 | 69 | 49 | 71.01% | 58.08% | 12.93% | 59.43% |
| QUIET VIX → below-typical next-session absolute move | Development through 2024 | 86 | 41 | 47.67% | 50.00% | -2.33% | 37.45% |
| QUIET VIX → below-typical next-session absolute move | Validation 2025 | 102 | 54 | 52.94% | 50.00% | 2.94% | 43.32% |
| QUIET VIX → below-typical next-session absolute move | Confirmation 2026 | 42 | 24 | 57.14% | 41.92% | 15.23% | 42.21% |

| Rule | Development checks | Validation checks | Confirmation checks | Gate state |
|---|---|---|---|---|
| ELEVATED_RANGE | no | PASS | PASS | NOT_PROMOTED |
| QUIET_RANGE | no | no | PASS | NOT_PROMOTED |

## Relationship, not direction

| Period | Observations | VIX vs next absolute return (Spearman) | VIX vs next signed return (Spearman) |
|---|---:|---:|---:|
| development | 342 | 0.099 | 0.041 |
| validation_2025 | 248 | 0.169 | 0.032 |
| confirmation_2026 | 167 | 0.39 | 0.139 |
| all | 757 | 0.194 | 0.06 |

The signed-return association is shown to prevent a common category error:
VIX is a volatility/range input here, not evidence for a next-day direction call.

## v2 accuracy segmented by frozen VIX regime — descriptive only

| Period | Regime | Observations | v2 exact 3-class | v2 directional coverage | Mean next absolute return |
|---|---|---:|---:|---:|---:|
| development | QUIET | 86 | 39.53% | 68.60% | 0.49% |
| development | NORMAL | 169 | 37.28% | 72.78% | 0.53% |
| development | ELEVATED | 87 | 37.93% | 75.86% | 0.72% |
| validation_2025 | QUIET | 102 | 39.22% | 80.39% | 0.42% |
| validation_2025 | NORMAL | 78 | 38.46% | 71.79% | 0.62% |
| validation_2025 | ELEVATED | 68 | 35.29% | 61.76% | 0.67% |
| confirmation_2026 | QUIET | 42 | 40.48% | 73.81% | 0.47% |
| confirmation_2026 | NORMAL | 56 | 41.07% | 73.21% | 0.56% |
| confirmation_2026 | ELEVATED | 69 | 33.33% | 71.01% | 0.95% |
| all | QUIET | 230 | 39.57% | 74.78% | 0.46% |
| all | NORMAL | 303 | 38.28% | 72.61% | 0.56% |
| all | ELEVATED | 224 | 35.71% | 70.09% | 0.78% |

This segmentation did **not** search for or adopt a VIX-based v2 filter/override.
Given the report-card result that v2 is below its class baseline, stratifying
the same history cannot establish a deployable directional improvement.

## Reproducibility and limits

- Matched observations: 757; VIX coverage: 2023-08-07 to 2026-09-04 (759 rows).
- Inputs: committed `historical/participant_oi.csv`, `historical/nifty_ohlc.csv`,
  and `historical/india_vix_ohlc.csv`, with hashes in `historical/manifest.json`.
- VIX does not supply pre-open, option premium/spread, event, sector, exact
  timestamped-level, execution, stop, or slippage evidence. It cannot repair
  those separate validation gaps.
- Continue prospective logging before any live report wording is changed.
