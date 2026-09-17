# Real historical backtest — FII/DII Decode

- **Run date:** 17 September 2026
- **Signal period:** 8 August 2023 to 3 September 2026
- **Evaluable next-session forecasts:** 757
- **Decoder version:** commit `85ce70a` (rules locked before this dataset was inspected)

> **Bottom line:** the current decoder has **not demonstrated reliable standalone next-day prediction accuracy**. The default three-class result is below a majority-class baseline, the open-to-close result is worse, and the apparent aggregate edges weaken materially in recent/year-by-year slices. It should remain an experimental context signal, not a trading trigger.

## 1. Headline result

The locked default evaluation defines the next-day move as next-session close versus signal-session close. Returns inside **±0.15%** are FLAT.

| Metric | Current decoder | Reference / interpretation |
|---|---:|---|
| Evaluable forecasts | 757 | 3 dates skipped with explicit reasons |
| Exact UP/FLAT/DOWN accuracy | **36.20%** | Majority-class baseline: **42.14%** |
| Directional calls | 528 (69.75%) | Remaining 229 calls were RANGE/FLAT |
| Directional hit rate, counting actual FLAT as a miss | **42.61%** | 225 / 528 |
| Sign accuracy after excluding actual FLAT moves | **53.96%** | 225 / 417; 95% CI **49.16–58.68%**, p=0.117 vs 50% |
| UP precision / recall | **43.31% / 34.48%** | Weak UP-day identification |
| DOWN precision / recall | **41.97% / 41.37%** | Weak DOWN-day identification |
| FLAT precision / recall | **21.40% / 30.63%** | RANGE calls are especially weak |

The conditional 53.96% sign number is **not** the overall accuracy. It removes 111 directional calls whose realised move was FLAT. Its confidence interval includes 50%, so this sample does not establish that it is better than chance.

### Confusion matrix

| Actual \\ Predicted | UP | FLAT | DOWN |
|---|---:|---:|---:|
| UP | 110 | 99 | 110 |
| FLAT | 62 | 49 | 49 |
| DOWN | 82 | 81 | 115 |

An actual UP session was predicted UP exactly as often as DOWN (110 each). This is not a dependable classification result.

## 2. Is it actionable after the report is published?

Participant OI is available after the signal session closes. Therefore next-session **open-to-close** is a more realistic executable-direction diagnostic than entering at the already-finished signal close.

All rows below use the same locked calls and ±0.15% threshold:

| Return basis | Exact 3-class | Majority baseline | Directional hit incl. FLAT misses | Sign accuracy on non-FLAT directional cases |
|---|---:|---:|---:|---:|
| Close-to-close | 36.20% | 42.14% | 42.61% | 53.96% (N=417) |
| **Next open-to-close** | **33.42%** | **38.71%** | **36.36%** | **46.72% (N=411)** |
| Overnight gap | 38.84% | 40.03% | 40.34% | 62.65% (N=340) |

The strongest pattern is alignment with the **overnight gap**, not the following intraday move. For non-FLAT gap cases, sign alignment is 62.65% (95% CI 57.39–67.62%). However:

1. exact gap classification still trails its majority baseline because the model is poor at deciding whether a meaningful gap will occur;
2. the normal NSE cash/F&O session is already closed when the participant report arrives;
3. next-session open-to-close sign accuracy is below 50%.

So the gap observation is useful research evidence, but **not proof of a directly executable profitable strategy**.

## 3. Stability by year

Default close-to-close scoring, ±0.15%:

| Target period | N | Exact 3-class | Baseline | Conditional non-FLAT sign accuracy | 95% CI |
|---|---:|---:|---:|---:|---:|
| 2023 partial | 96 | 39.58% | 51.04% | 60.71% (N=56) | 47.63–72.42% |
| 2024 | 246 | 34.55% | 43.09% | 51.49% (N=134) | 43.11–59.79% |
| 2025 | 248 | 37.90% | 39.92% | 55.88% (N=136) | 47.49–63.95% |
| **2026 through 4 Sep** | **167** | **34.13%** | **42.51%** | **50.55% (N=91)** | **40.46–60.59%** |

No complete year establishes a stable edge. The most recent segment is effectively coin-flip directional performance and below baseline on exact classification.

## 4. Confidence and “strong” calls

| Subset | N | Exact 3-class | Subset baseline | Conditional sign accuracy | 95% CI |
|---|---:|---:|---:|---:|---:|
| All | 757 | 36.20% | 42.14% | 53.96% | 49.16–58.68% |
| Confidence ≥40 | 266 | 47.37% | 43.61% | 58.60% | 51.93–64.98% |
| Confidence ≥45 | 154 | 46.10% | 42.21% | 58.20% | 49.33–66.57% |
| Raw strong UP/DOWN | 61 | 47.54% | 42.62% | 61.70% | 47.43–74.21% |
| Sideways-UP/DOWN only | 467 | 41.97% | 41.54% | 52.97% | 47.88–58.00% |

Confidence ≥40 is the only sizeable subset with a positive aggregate conditional result. But it degrades by target year:

- 2023 partial: 77.78% (N=27 non-FLAT directional cases)
- 2024: 56.52% (N=69)
- 2025: 57.35% (N=68)
- **2026: 52.94% (N=51; 95% CI 39.52–65.95%)**

Also, confidence ≥40 open-to-close conditional sign accuracy is only **50.97%**. Therefore “trade only high confidence” is not yet a validated fix.

## 5. Threshold sensitivity

The result was checked at FLAT bands from 0% to ±0.50%; ±0.15% was not selected after seeing performance.

| Flat band | Exact 3-class | Baseline | Directional hit incl. FLAT misses | Conditional sign accuracy |
|---|---:|---:|---:|---:|
| 0.00% | 36.72% | 52.71% | 52.65% | 52.75% |
| ±0.10% | 35.93% | 45.84% | 45.83% | 52.61% |
| **±0.15%** | **36.20%** | **42.14%** | **42.61%** | **53.96%** |
| ±0.25% | 35.27% | 37.12% | 37.31% | 54.12% |
| ±0.50% | 35.27% | 55.35% | 25.76% | 56.67% |

Larger thresholds mechanically remove smaller, harder moves from the conditional denominator; that raises conditional sign accuracy while sharply reducing scored directional observations. It does not rescue overall classification.

## 6. Five-session / positional outlook

The production positional logic was replayed chronologically using only earlier decoded history. The target is five trading sessions ahead. At a declared ±0.50% five-session FLAT band:

| Metric | Result |
|---|---:|
| Evaluable forecasts | 753 |
| Directional coverage | 39.71% |
| Exact 3-class accuracy | **29.88%** |
| Majority baseline | **43.96%** |
| Directional hit incl. realised FLAT misses | **45.48%** |
| Conditional sign accuracy | **57.14%** (136/238; 95% CI 50.79–63.27%) |

The aggregate conditional number is statistically above 50% at p=0.032, but it is not stable evidence: 2023 partial was 88.89% on only 18 cases, while 2024, 2025, and 2026 were respectively **54.02%, 54.93%, and 54.84%**, with every full-year confidence interval crossing 50%. Exact classification remains far below baseline.

Conclusion: the positional score has a weak research signal on selected non-FLAT outcomes, but not enough stable evidence for a reliable weekly forecast claim.

## 7. Fresh action vs carry ablation

The methodology says both fresh changes and carried positions matter. The current decoder uses fresh change whenever previous-day OI exists. Fixed, non-optimised fresh-only, 50/50, and carry-only variants were compared.

- No variant consistently beat the majority baseline across 2023–24 development, 2025 validation, and 2026 latest data.
- Carry-only gave better open-to-close exact accuracy in older data, but fell from 41.53% in 2025 to 37.72% in 2026, still below each period's baseline.
- A 50/50 blend did not produce stable directional improvement.

This means simply adding carry is not a validated repair. Any redesign needs a predeclared training period and a genuinely untouched forward holdout.

## 8. Data and point-in-time controls

Input came from the public GitHub mirror `sahilempire/groww-market-data`, pinned to commit:

`7d481cf1fcffe44be68852892028195c4f12dddd`

Used paths:

- `nse_archives/participant_oi/`: 760 daily raw Participant-OI files
- `nse_archives/index_close/`: 759 all-index close files; only Nifty 50 rows used

Quality checks:

- 760 OI dates, 759 OHLC dates; 759 dates overlap
- all files' embedded report dates checked against filenames: zero mismatches
- all NIFTY OHLC values present; zero invalid High/Low bars
- all named OI fields used by the decoder present
- one 22-Feb-2024 FII row contains an extra trailing unnamed aggregate value; named inputs are intact and the extra field is ignored
- raw archive directory hashes and consolidated OHLC hash are recorded in `provenance.json`

The mirror is not the primary NSE server. Direct NSE access from this sandbox failed at TLS, so source provenance is disclosed rather than represented as a direct download.

## 9. What was not tested

- Historical option-chain snapshots were unavailable, so **institutional-level reaction accuracy is unknown**.
- Historical point-in-time cash FII/DII flow was unavailable, so it was omitted rather than backfilled with current values.
- This is signal classification, not net P&L: no tradable entry rule, slippage, fees, stop, sizing, or market-impact assumptions were added.
- Gap scenarios, liquidity-sweep sequence, and 15-minute break/hold rules cannot be proven with daily bars.

## 10. Decision

### What the evidence supports

- Participant OI contains some information about the following overnight gap.
- Higher composite/confidence values contain more close-to-close information in the aggregate sample.
- The positional signal may have a small conditional edge worth forward-testing.

### What the evidence does **not** support

- A claim that the current next-day prediction is generally accurate.
- A claim that the signal can be entered at the next open and reliably predict that session's direction.
- A claim that displayed confidence is a calibrated probability.
- Any institutional-level accuracy claim without historical chains.

**Operational recommendation:** do not use the current forecast standalone with money. Keep collecting point-in-time OI, option chain, cash, and OHLC; freeze any revised rules; then evaluate on an untouched forward sample. The current implementation should be labelled **experimental / unvalidated for trading**.

## Audit files

- `next_day_predictions.csv` — every next-day call and realised bar
- `metrics.json` — locked default aggregate metrics
- `threshold_sensitivity.csv` — close/open/gap results across FLAT bands
- `return_basis_breakdown.csv` — close-to-close, open-to-close, and gap comparison
- `yearly_breakdown.csv` — year stability
- `confidence_yearly_breakdown.csv`, `subset_breakdown.csv`, and `subset_return_basis.csv` — confidence diagnostics
- `five_session_predictions.csv`, `five_session_sensitivity.csv`, `five_session_yearly_breakdown.csv` — positional replay
- `fresh_vs_carry_ablation.csv` — fixed carry/fresh variants
- `skipped.csv` — all rejected dates and reasons
- `provenance.json` — source pin, hashes, and anomalies

> Educational research only; not investment advice.
