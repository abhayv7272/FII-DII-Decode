# V5 holdout combo/meta/intraday audit

> Research only; no production decoder change.  This is a continuation of the
> 70-85% accuracy hunt after v4, with a stronger leakage guard and a 2026 final
> holdout.

## What changed vs v4

- Rules are refit on **2023-2025** and scored on **2026** as the untouched
  holdout.
- A rule-combo/voting layer tests whether many weak psychology rules combine
  into a high-precision state.
- A v3 meta-gate tries to predict when v3 will be right, but explicitly excludes
  target/outcome columns (`exact_hit`, `direction_hit`, `actual_class`, target
  returns).  This prevents a fake 100% result.
- A recent intraday check uses available NIFTY 1-minute data to test whether a
  first 15/30/60-minute candle confirming the OI view creates an executable edge.

## Summary

- Rows: **757**
- Clean numeric features after leakage guard: **4746**
- Train-2023/25 threshold rules exported: **13944**
- 2026-holdout rules with ≥75% exact and ≥20 calls: **0**
- 2026-holdout rules with ≥75% sign and ≥20 non-FLAT calls: **7**
- Voting combos with ≥75% exact and ≥20 holdout calls: **0**
- Meta-gates with ≥70% v3-hit precision and ≥20 holdout calls: **0**

## Best 2026 holdout exact rules (diagnostic, not selected blindly)

| feature | mode | quantile | rho_train2023_25 | train2023_25_n | train2023_25_exact_pct | train2023_25_sign_pct | val2025_n | val2025_exact_pct | val2025_sign_pct | confirm2026_n | confirm2026_exact_pct | confirm2026_sign_pct | confirm2026_sign_n |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Client_scall_rflow_chg21 | two_tail | 0.925 | -0.04691 | 86 | 48.84 | 61.76 | 36 | 47.22 | 54.84 | 22 | 72.73 | 84.21 | 19 |
| DII_scall_qflow_chg21 | two_tail | 0.925 | 0.03943 | 86 | 48.84 | 60 | 36 | 50 | 60 | 20 | 70 | 77.78 | 18 |
| Client_scall_rflow_chg21 | two_tail | 0.9 | -0.04691 | 114 | 47.37 | 61.36 | 50 | 46 | 56.1 | 25 | 68 | 77.27 | 22 |
| Pro_v2inst_lvl_chg7 | up_tail | 0.85 | 0.1126 | 88 | 52.27 | 61.33 | 40 | 42.5 | 50 | 25 | 68 | 77.27 | 22 |
| DII_scall_rflow_chg21 | two_tail | 0.925 | 0.04111 | 86 | 48.84 | 60 | 35 | 51.43 | 60 | 21 | 66.67 | 73.68 | 19 |
| DII_v2inst_lvl_chg21 | up_tail | 0.85 | 0.119 | 86 | 56.98 | 64.47 | 44 | 54.55 | 60 | 36 | 66.67 | 72.73 | 33 |
| px_rv5_chg21 | up_tail | 0.925 | 0.04274 | 43 | 53.49 | 65.71 | 10 | 70 | 77.78 | 27 | 66.67 | 72 | 25 |
| DII_v3inst_qflow_posdays21 | up_tail | 0.925 | 0.04184 | 57 | 54.39 | 62 | 39 | 48.72 | 55.88 | 27 | 66.67 | 72 | 25 |
| DII_v3inst_qflow_posdays21 | up_tail | 0.95 | 0.04184 | 57 | 54.39 | 62 | 39 | 48.72 | 55.88 | 27 | 66.67 | 72 | 25 |
| DII_v3inst_rflow_posdays21 | up_tail | 0.9 | 0.03738 | 66 | 51.52 | 60.71 | 45 | 46.67 | 55.26 | 27 | 66.67 | 72 | 25 |
| DII_v3inst_rflow_posdays21 | up_tail | 0.925 | 0.03738 | 66 | 51.52 | 60.71 | 45 | 46.67 | 55.26 | 27 | 66.67 | 72 | 25 |
| Pro_icall_lvl_posdays15 | up_tail | 0.7 | -0.05308 | 195 | 50.26 | 60.12 | 35 | 54.29 | 57.58 | 24 | 66.67 | 69.57 | 23 |

## Best 2026 holdout sign rules

| feature | mode | quantile | rho_train2023_25 | train2023_25_n | train2023_25_exact_pct | train2023_25_sign_pct | val2025_n | val2025_exact_pct | val2025_sign_pct | confirm2026_n | confirm2026_exact_pct | confirm2026_sign_pct | confirm2026_sign_n |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Client_scall_rflow_chg21 | two_tail | 0.9 | -0.04691 | 114 | 47.37 | 61.36 | 50 | 46 | 56.1 | 25 | 68 | 77.27 | 22 |
| Pro_v2inst_lvl_chg7 | up_tail | 0.85 | 0.1126 | 88 | 52.27 | 61.33 | 40 | 42.5 | 50 | 25 | 68 | 77.27 | 22 |
| DII_futheavy_rflow_chg4 | two_tail | 0.925 | -0.02588 | 88 | 46.59 | 62.12 | 65 | 50.77 | 64.71 | 30 | 60 | 75 | 24 |
| DII_index_rflow_sum21 | two_tail | 0.95 | 0.03361 | 60 | 50 | 57.69 | 29 | 55.17 | 64 | 29 | 51.72 | 75 | 20 |
| DII_index_rflow_mean21 | two_tail | 0.95 | 0.0343 | 60 | 50 | 57.69 | 29 | 55.17 | 64 | 29 | 51.72 | 75 | 20 |
| DII_v2inst_rflow_sum21 | two_tail | 0.95 | 0.03361 | 60 | 50 | 57.69 | 29 | 55.17 | 64 | 29 | 51.72 | 75 | 20 |
| DII_v2inst_rflow_mean21 | two_tail | 0.95 | 0.0343 | 60 | 50 | 57.69 | 29 | 55.17 | 64 | 29 | 51.72 | 75 | 20 |
| oc_oi_total_chg7 | up_tail | 0.85 | 0.0367 | 88 | 44.32 | 61.9 | 24 | 37.5 | 56.25 | 26 | 65.38 | 73.91 | 23 |
| px_oc1_sum21 | two_tail | 0.9 | -0.05586 | 118 | 50.85 | 58.82 | 69 | 52.17 | 58.06 | 27 | 62.96 | 73.91 | 23 |
| px_oc1_mean21 | two_tail | 0.9 | -0.05486 | 118 | 50.85 | 58.82 | 69 | 52.17 | 58.06 | 27 | 62.96 | 73.91 | 23 |
| DII_v2inst_lvl_chg21 | up_tail | 0.85 | 0.119 | 86 | 56.98 | 64.47 | 44 | 54.55 | 60 | 36 | 66.67 | 72.73 | 33 |
| DII_scall_lvl_z21 | two_tail | 0.9 | 0.05621 | 118 | 51.69 | 60.4 | 55 | 47.27 | 54.17 | 26 | 61.54 | 72.73 | 22 |

## Rules that looked strong on train only, then hit 2026

This is the fairer view: train exact ≥60%, train sign ≥70%, train calls ≥40,
then observe 2026 without re-picking.

| feature | mode | quantile | rho_train2023_25 | train2023_25_n | train2023_25_exact_pct | train2023_25_sign_pct | val2025_n | val2025_exact_pct | val2025_sign_pct | confirm2026_n | confirm2026_exact_pct | confirm2026_sign_pct | confirm2026_sign_n |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| px_rv20_z63 | up_tail | 0.925 | 0.07902 | 42 | 61.9 | 72.22 | 13 | 69.23 | 75 | 36 | 63.89 | 69.7 | 33 |
| DII_v2inst_lvl_chg21 | up_tail | 0.9 | 0.119 | 57 | 61.4 | 70 | 36 | 61.11 | 66.67 | 30 | 60 | 66.67 | 27 |
| DII_optheavy_lvl_chg21 | up_tail | 0.85 | 0.1149 | 86 | 61.63 | 71.62 | 38 | 57.89 | 62.86 | 29 | 58.62 | 65.38 | 26 |
| DII_v2inst_lvl_chg21 | up_tail | 0.925 | 0.119 | 43 | 65.12 | 70 | 30 | 56.67 | 62.96 | 28 | 57.14 | 64 | 25 |
| Client_sfut_lvl_chg7 | up_tail | 0.925 | 0.02937 | 44 | 63.64 | 70 | 9 | 66.67 | 75 | 22 | 54.55 | 60 | 20 |
| px_rv5_sum7 | up_tail | 0.925 | 0.04638 | 44 | 61.36 | 72.97 | 17 | 64.71 | 64.71 | 28 | 53.57 | 60 | 25 |
| px_rv5_mean7 | up_tail | 0.925 | 0.04643 | 44 | 61.36 | 72.97 | 17 | 64.71 | 64.71 | 28 | 53.57 | 60 | 25 |
| px_rv20_z63 | up_tail | 0.85 | 0.07902 | 83 | 61.45 | 73.91 | 18 | 55.56 | 71.43 | 55 | 52.73 | 58 | 50 |
| px_rv20 | up_tail | 0.925 | 0.03808 | 43 | 60.47 | 74.29 | 23 | 52.17 | 63.16 | 30 | 50 | 57.69 | 26 |
| px_atr5_sum15 | up_tail | 0.9 | 0.03401 | 59 | 61.02 | 75 | 12 | 58.33 | 77.78 | 26 | 50 | 56.52 | 23 |
| px_atr5_sum15 | up_tail | 0.925 | 0.03401 | 44 | 63.64 | 75.68 | 4 | 50 | 50 | 26 | 50 | 56.52 | 23 |
| px_atr5_mean15 | up_tail | 0.9 | 0.03129 | 59 | 61.02 | 75 | 12 | 58.33 | 77.78 | 26 | 50 | 56.52 | 23 |

## Voting-combo results

| top_n | min_votes | agree_ratio | train2023_25_n | train2023_25_exact_pct | train2023_25_sign_pct | confirm2026_n | confirm2026_exact_pct | confirm2026_sign_pct | confirm2026_sign_n |
|---|---|---|---|---|---|---|---|---|---|
| 500 | 30 | 1 | 199 | 58.79 | 76.97 | 59 | 47.46 | 56 | 50 |
| 500 | 30 | 0.9 | 238 | 56.72 | 75 | 64 | 45.31 | 54.72 | 53 |
| 200 | 15 | 0.5 | 168 | 58.93 | 79.2 | 53 | 45.28 | 55.81 | 43 |
| 200 | 15 | 0.6 | 168 | 58.93 | 79.2 | 53 | 45.28 | 55.81 | 43 |
| 200 | 15 | 0.67 | 168 | 58.93 | 79.2 | 53 | 45.28 | 55.81 | 43 |
| 200 | 15 | 0.75 | 168 | 58.93 | 79.2 | 53 | 45.28 | 55.81 | 43 |
| 200 | 15 | 0.8 | 168 | 58.93 | 79.2 | 53 | 45.28 | 55.81 | 43 |
| 200 | 15 | 0.9 | 168 | 58.93 | 79.2 | 53 | 45.28 | 55.81 | 43 |
| 200 | 15 | 1 | 164 | 58.54 | 78.69 | 53 | 45.28 | 55.81 | 43 |
| 500 | 50 | 1 | 140 | 56.43 | 76.7 | 40 | 45 | 52.94 | 34 |
| 500 | 40 | 1 | 165 | 58.18 | 78.05 | 49 | 44.9 | 53.66 | 41 |
| 500 | 30 | 0.5 | 242 | 56.2 | 74.32 | 65 | 44.62 | 53.7 | 54 |

## V3 meta-gate results after leakage guard

The model can look strong on 2023-2025, but holdout precision remains near
chance.  The fake 100% path is blocked by excluding all target/outcome columns.

| model | top_n | threshold_name | train2023_25_n | train2023_25_v3_hit_precision_pct | val2025_n | val2025_v3_hit_precision_pct | confirm2026_n | confirm2026_v3_hit_precision_pct | confirm2026_coverage_pct |
|---|---|---|---|---|---|---|---|---|---|
| gb_depth2 | 10 | train_prob_q0.85 | 89 | 67.42 | 49 | 71.43 | 43 | 51.16 | 25.9 |
| logreg_C0.1 | 50 | train_prob_q0.8 | 119 | 68.91 | 45 | 73.33 | 45 | 51.11 | 27.11 |
| logreg_C0.1 | 120 | train_prob_q0.5 | 296 | 64.53 | 127 | 64.57 | 87 | 50.57 | 52.41 |
| logreg_C0.1 | 200 | train_prob_q0.5 | 296 | 67.57 | 120 | 68.33 | 122 | 50 | 73.49 |
| hgb_depth2 | 10 | train_prob_q0.6 | 243 | 58.85 | 103 | 62.14 | 74 | 50 | 44.58 |
| logreg_C0.1 | 80 | train_prob_q0.7 | 178 | 70.79 | 76 | 72.37 | 50 | 50 | 30.12 |
| logreg_C0.1 | 80 | train_prob_q0.8 | 119 | 71.43 | 49 | 69.39 | 34 | 50 | 20.48 |
| hgb_depth2 | 10 | train_prob_q0.5 | 350 | 53.71 | 147 | 53.74 | 93 | 49.46 | 56.02 |
| logreg_C0.1 | 400 | train_prob_q0.5 | 296 | 74.66 | 121 | 74.38 | 146 | 49.32 | 87.95 |
| logreg_C0.1 | 400 | train_prob_q0.7 | 178 | 82.58 | 72 | 84.72 | 129 | 48.84 | 77.71 |
| gb_depth2 | 400 | train_prob_q0.7 | 178 | 89.89 | 61 | 91.8 | 37 | 48.65 | 22.29 |
| logreg_C0.1 | 200 | train_prob_q0.6 | 237 | 74.26 | 98 | 72.45 | 109 | 48.62 | 65.66 |

## Recent 1-minute intraday confirmation check

Only the mirror's recent 1-minute NIFTY window is available, so this is a tiny
sample.  In this sample, first-window confirmation does **not** create a stable
executable edge.

| strategy | minutes | threshold_pct | samples | calls | sign_n | sign_hit_pct |
|---|---|---|---|---|---|---|
| v3_agrees_with_first_window | 15 | 0.02 | 24 | 13 | 13 | 53.85 |
| v3_agrees_with_first_window | 15 | 0.03 | 24 | 13 | 13 | 53.85 |
| v3_agrees_with_first_window | 15 | 0.05 | 24 | 12 | 12 | 50 |
| v3_agrees_with_first_window | 15 | 0.08 | 24 | 10 | 10 | 50 |
| v3_agrees_with_first_window | 15 | 0.1 | 24 | 10 | 10 | 50 |
| v3_agrees_with_first_window | 15 | 0 | 24 | 15 | 15 | 46.67 |
| first_window_trend_continuation | 15 | 0.02 | 24 | 21 | 21 | 42.86 |
| first_window_trend_continuation | 15 | 0.03 | 24 | 21 | 21 | 42.86 |
| first_window_trend_continuation | 15 | 0.05 | 24 | 19 | 19 | 42.11 |
| first_window_trend_continuation | 15 | 0 | 24 | 24 | 24 | 41.67 |
| first_window_trend_continuation | 15 | 0.08 | 24 | 15 | 15 | 33.33 |
| first_window_trend_continuation | 15 | 0.1 | 24 | 15 | 15 | 33.33 |

## Verdict

This second cycle still does **not** honestly promote a 70-85% production edge.
The only way to print 80-100% here is either low-sample selection or target
leakage.  The useful discoveries remain research-only:

- Some 2026 pockets (e.g. stock-call flow changes / DII level-volatility states)
  can score 70%+ on ~20 calls, but they were not strong/stable enough in
  2023-2025 to trust.
- Rule voting amplifies overfit instead of improving the 2026 holdout.
- A v3 meta-gate cannot reliably identify the winning v3 days once leakage is
  removed.
- Recent 15-minute confirmation is roughly coin-flip on the available intraday
  sample.

Next best route: collect/procure a longer 10-15 minute intraday history with
same-date option levels/exact institutional levels, then evaluate executable
rules prospectively instead of adding more EOD curve fitting.
