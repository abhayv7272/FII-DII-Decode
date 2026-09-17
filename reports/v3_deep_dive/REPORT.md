# V3 deep dive — full research log

> **Purpose:** document the complete accuracy investigation behind the
> v3-candidate decoder: every search, every null control, and every negative
> result, so the v3 numbers in
> [`../backtest_v3_candidate_2023-08_to_2026-09/`](../backtest_v3_candidate_2023-08_to_2026-09/)
> can be judged with full context. Educational research; not investment advice.

**Data:** public `sahilempire/groww-market-data` mirror pinned at commit
`7d481cf1fcffe44be68852892028195c4f12dddd` (760 participant-OI files,
759 index-close files, 759 participant-*volume* files, 760 F&O bhavcopy
files — the same participant-OI/index-close basis as the published v1/v2
replays). 757 evaluable sessions; periods (target-session years):
**development 2023-2024**, **validation 2025**, **confirmation 2026**.

All fitting was done on development only; validation/confirmation columns
were then computed unchanged. Reproduction scripts are `research/v3_*.py`
(extra deps: `scipy`, `scikit-learn`); the master feature matrix is rebuilt by
`research/v3_features.py` into `/home/user/features/` (kept out of git).

---

## 0. What was reproduced first

The published v2 replay was re-run **before any change**:
per-date predictions and every reported percentage are byte-identical to
`reports/backtest_v2_2023-08_to_2026-09/`. All v3 work starts from a verified
baseline, and v3's final evidence package is produced by the same production
code path (`src/fiidii/backtest.py`), not by the vectorised research replica
(the replica was used only for fast grid search and agrees with the production
classes on 756/757 dates; the one flip is an exact-zero composite).

## 1. Class balance and baselines (`class_balance.csv`)

| Basis | Dev | Val | Confirm |
|---|---|---|---|
| UP share (±0.15% FLAT) | 45.48% | 39.52% | 39.16% |
| FLAT share | 22.74% | 20.97% | 18.07% |
| DOWN share | 31.78% | 39.52% | 42.77% |
| Majority baseline | 45.48% (UP) | 39.52% (UP) | 42.77% (DOWN) |

FLAT is only ~19-23% of sessions — a wide no-call band (v2: ±0.10) therefore
costs more exact-class hits than it saves. This motivated the v3 grid to
include threshold ≈ 0.

## 2. Univariate power: no single feature is reliable (`univariate_ic.csv`, `univariate_null.csv`)

365 features × Spearman IC vs next-day return, per period. **Null control:**
200 target shuffles put the 95th percentile of the dev max |IC| at **0.183**;
the best real dev |IC| was 0.163 (Pro index-call 3-day fresh flow). **Zero
features pass the multiple-testing gate**, and the top dev features decay to
~zero IC in 2026 (`top_features.csv` is intentionally the empty gate result).
Conclusion: any accuracy gain must come from combinations/structure, not a
single magic variable. Participant-*volume* files (new input, unused by v2)
show the same pattern — no standalone signal.

## 3. Six v2 changes under the microscope (`ablation_v2.csv` / `ablation_v2_summary.csv`)

Each locked v2 rule was reverted alone and the full replay re-run (production
code, per-period metrics). Outcome (full-sample sign accuracy / exact):

| Variant | Full sign | Full exact | Reading |
|---|---:|---:|---|
| v2 locked | 55.05% | 37.91% | reference |
| closures full weight (revert) | 54.79% | 38.57% | half-weight is a wash |
| closures 0.25 weight | 56.28% | 35.93% | fresh-heavy slightly better sign |
| no tanh (linear) | n/a | 21.14% | squashing to a bounded scale is essential |
| tight squash 1% | 54.07% | 39.89% | saturation scale shifts exact, not sign |
| + stock futures 15% | 55.47% | 36.20% | confirms v2's exclusion decision |
| FII-led participants (revert) | 54.85% | 36.86% | v2's Pro-FII mix direction is right |
| FII only | 54.09% | 38.44% | single-participant is weaker |
| Pro only | 55.14% | 37.91% | single-participant is weaker |
| Client not contra | 53.58% | 34.61% | heavy contra-Client or heavy Client-aligned both hurt |
| DII included 15% | 55.26% | 36.72% | v2's DII exclusion confirmed |

Discovered mechanics note: the forced class is produced by
`fiidii.predict._direction(composite)` with a hard-coded per-version
threshold; `fiidii.decode.DIRECTION_THRESHOLD` only feeds `bias` and
`actionability`. Ablating it therefore cannot change the replayed class —
explained in code comments and fixed terminology in the v3 work.

## 4. Structural grids (`grid_participant_weights.csv`, `grid_instrument_weights.csv`, `grid_thresholds.csv`, `candidate_sweep.csv`)

~840 composite structures (participant weights × contra weight in [-0.3,+0.3]
× instrument mixes × thresholds), dev-scored with untouched OOS columns:

- Low-n artefacts eliminated (early top rows had 3-10 observation sign
  "accuracy"; coverage floor of 50% applied).
- The robust dev plateau is: **participant mix ≈ Pro 55-65 / FII 35-45, tiny
  Client tilt (either sign, ~0.1), index futures 30-60% in the instrument
  mix, threshold ≈ 0-0.05.** Every plateau point beats v2 on validation and
  confirmation exact accuracy.
- High thresholds recreate the published trap: dev sign-accuracy 60-65% on
  12-21% coverage collapses to ~50% in 2026. Threshold selection cannot
  manufacture precision.

Final candidate = plateau centre: **Pro 60 / FII 40 / Client-tilt −0.10;
index call 30 / index put 30 / index futures 40; threshold 0.00.**

## 5. Honest machine learning (`ml_results.csv`)

Two protocols: expanding-window walk-forward (252-day burn-in, refit every 21
sessions) and frozen-on-deviation; logreg (C via blocked TS CV), ridge on
returns, small gradient boosting; feature blocks F1 index flows → F5
+ price context + participant volumes.

- Frozen GBT: 99-100% dev accuracy → 35-41% confirmation. Total overfit;
  capacity is punished, exactly as feared.
- Best walk-forward rows (ridge, richer blocks) reach confirmation exact
  ~43-44%, sign ~54-58% — the *same zone* as the hand candidate but with
  model churn, refit cost, and worse interpretability. **No ML config beats
  the hand candidate honestly**, so v3 stays a small, auditable rule.

## 6. Option-chain aggregates from bhavcopy (`chain_feature_ic.csv`)

759 same-date EOD chain aggregate rows extracted from the pinned bhavcopy
files (`research/v3_chain_features.py`): PCR variants, max-pain distance,
wall distances, wall-build %, ATM straddle %, true days-to-expiry.

- The only consistent relationship is the **overnight-gap channel**: PCR-OI
  gap IC ≈ +0.13/+0.11/+0.13 (dev/val/confirm). Blending PCR into the daily
  composite was tested (weights 0.25-1.0): it *reduces* close-to-close
  accuracy — rejected.
- FLAT/size channel is dead: no feature separates the |next-day move| < 0.15%
  tail well enough to call FLAT profitably (P(FLAT) stays 14-30% across all
  buckets; expiry days are *less* flat).

## 7. Level accuracy re-examined (`level_grid.csv`)

Level selection re-gridded over evidence mix (OI vs ΔOI weight), nearest vs
all-expiry aggregation, argmax vs nearest-of-top-3, on next-day OHLC proxy
(published contract): best dev variants reach 52-55% hold but validation dips
to 45-47% in nearly every variant; full sample best ≈ 51.8-52.6% vs
production 49.20%. Conditioning by PCR tercile / vol tercile / DTE bucket
shows 60-74% cells on n=8-40 — underpowered, not promotable. **Verdict
unchanged: daily-bar level holds are a coin flip; the report stays honest.**

## 8. Gap and weekly channels (`gap_sweep.csv`, `v3_weekly_diagnostic.csv`)

- Gap: the v3 composite is also the best gap classifier of the family
  (dev 61.2 / val 57.0 / confirm 60.5 sign, full coverage). The close-to-close
  improvement is *mostly* the overnight gap; intraday open-to-close stays
  ~48-51% for every candidate. Executable edge: not established (unchanged).
- Weekly: carry composites hit 60% in confirmation only because 2026 was
  DOWN-majority and 2026 carry was bearish; dev/val sit at 46-48%.
  The v3 daily composite's 5-day diagnostic is dev 54.8 / val 58.4 /
  confirm 49.7 — **weekly stays NO-VALIDATED-EDGE.**

## 9. Robustness battery for the chosen candidate (`robust_*.csv`)

- FLAT-band sensitivity ±0.10/±0.15/±0.20: v3 wins every period × band cell
  (exact +6 to +12pp vs v2).
- Rolling 126-session sign accuracy: v3 > v2 in **85.6%** of windows
  (mean 57.2% vs 53.9%).
- Per-year exact: 2023 52.6, 2024 42.3, 2025 43.6, 2026 47.6 — v3 beats v2
  every year; 2024 remains ~1.2pp under its yearly majority baseline.
- McNemar vs v2 (exact class): dev p=0.0056, val p=0.063, confirm p=0.020,
  pooled p<10⁻⁶ (production package aligned to target-date years:
  `../backtest_v3_candidate_2023-08_to_2026-09/mcnemar_exact_v3_vs_v2.csv`).
- Conflict dates (v2's WAIT_FOR_REVERSAL_CONFIRMATION): v2 sign 21-26%,
  v3 50-62.5% over 27/14/8 dates — v2's conflict abstention was catching a
  genuinely difficult state, which v3 handles slightly better but remains
  flagged for actionability caution.

## 10. Promotion criteria (unchanged, enforced)

V3 is a **candidate**. Production promotion requires an untouched forward
window (sessions after 2026-09-04, the pinned archive end) replayed with this
exact configuration still showing gains. Until then the daily workflow keeps
emitting v2 as the default decoder; v3 is opt-in via
`--decoder-version v3`.
