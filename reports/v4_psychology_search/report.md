# V4 psychology / manipulation / level search — research log

> Educational research only — not investment advice.  This file documents an
> intentionally aggressive search for a 70-85% daily NIFTY edge.  Nothing here is
> promoted to production unless it survives untouched validation/confirmation and
> later forward data.

## Data and guardrails

- Feature rows: **757** signal sessions from the existing
  participant-OI archive.
- Engineered columns after same-date option-chain merge and 4/7/15/21-session
  psychology/positioning transforms: **4764**.
- Development/fitting: **2023-2024 only**.  Validation: **2025**.  Confirmation:
  **2026**.
- Target: next-session close-to-close class with ±0.15% FLAT band.
- Directional rules are selective: they can say UP/DOWN or abstain.  Exact
  accuracy below counts a called UP/DOWN against the 3-class target, so real FLAT
  days are misses.

## Bottom line

The 75-85% target was **not cracked honestly** in this run.

- Rules meeting **≥75% exact** on both 2025 and 2026 with at least 20 calls in
  each period: **0**.
- Rules meeting **≥75% non-FLAT sign** on both 2025 and 2026 with at least 20
  non-FLAT calls in each period: **0**.

The strongest broad-coverage model remains the already-published **v3 candidate**
(45.05% exact / 57.12% sign full sample).  This v4 search did find a few
interesting *research-only* selective states around 58-63% exact and 63-73% sign,
but the sample sizes/coverage are too small for production promotion.

## Best selective exact rules requiring at least 20 calls in both 2025 and 2026

| feature | mode | quantile | rho_dev | dev2023_24_n | dev2023_24_exact_pct | dev2023_24_sign_pct | val2025_n | val2025_exact_pct | val2025_sign_pct | confirm2026_n | confirm2026_exact_pct | confirm2026_sign_pct | min_val_confirm_exact_pct | min_val_confirm_sign_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Client_sfut_lvl_z63 | up_tail | 0.9 | -0.05009 | 33 | 42.42 | 60.87 | 30 | 66.67 | 71.43 | 20 | 60 | 60 | 60 | 60 |
| DII_v2inst_lvl_chg21 | up_tail | 0.925 | 0.1291 | 25 | 60 | 75 | 37 | 59.46 | 64.71 | 31 | 61.29 | 67.86 | 59.46 | 64.71 |
| DII_v2inst_lvl_chg21 | two_tail | 0.925 | 0.1291 | 50 | 52 | 63.41 | 51 | 58.82 | 65.22 | 53 | 58.49 | 65.96 | 58.49 | 65.22 |
| DII_optheavy_lvl_chg21 | up_tail | 0.85 | 0.1093 | 49 | 65.31 | 80 | 38 | 57.89 | 62.86 | 31 | 58.06 | 64.29 | 57.89 | 62.86 |
| DII_optheavy_lvl_chg21 | up_tail | 0.9 | 0.1093 | 33 | 57.58 | 76 | 35 | 57.14 | 62.5 | 23 | 60.87 | 66.67 | 57.14 | 62.5 |
| DII_optheavy_lvl_chg21 | up_tail | 0.7 | 0.1093 | 97 | 51.55 | 62.5 | 51 | 56.86 | 60.42 | 48 | 58.33 | 66.67 | 56.86 | 60.42 |
| DII_optheavy_lvl_chg21 | two_tail | 0.925 | 0.1093 | 50 | 54 | 67.5 | 44 | 56.82 | 62.5 | 34 | 58.82 | 62.5 | 56.82 | 62.5 |
| DII_optheavy_lvl_chg21 | up_tail | 0.8 | 0.1093 | 65 | 56.92 | 71.15 | 44 | 56.82 | 60.98 | 39 | 58.97 | 65.71 | 56.82 | 60.98 |
| DII_optheavy_lvl_chg15 | two_tail | 0.95 | 0.08704 | 34 | 50 | 62.96 | 30 | 56.67 | 60.71 | 21 | 61.9 | 65 | 56.67 | 60.71 |
| DII_v2inst_lvl_chg21 | up_tail | 0.9 | 0.1291 | 33 | 60.61 | 71.43 | 39 | 56.41 | 61.11 | 32 | 62.5 | 68.97 | 56.41 | 61.11 |

## Best selective sign rules requiring at least 20 non-FLAT calls in both 2025 and 2026

| feature | mode | quantile | rho_dev | dev2023_24_sign_n | dev2023_24_sign_pct | dev2023_24_exact_pct | val2025_sign_n | val2025_sign_pct | val2025_exact_pct | confirm2026_sign_n | confirm2026_sign_pct | confirm2026_exact_pct | min_val_confirm_sign_pct | min_val_confirm_exact_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| px_atr5_sum7 | two_tail | 0.95 | 0.06224 | 28 | 60.71 | 50 | 33 | 66.67 | 51.16 | 37 | 70.27 | 57.78 | 66.67 | 51.16 |
| DII_v2inst_lvl_chg21 | two_tail | 0.925 | 0.1291 | 41 | 63.41 | 52 | 46 | 65.22 | 58.82 | 47 | 65.96 | 58.49 | 65.22 | 58.49 |
| DII_v2inst_lvl_chg21 | up_tail | 0.925 | 0.1291 | 20 | 75 | 60 | 34 | 64.71 | 59.46 | 28 | 67.86 | 61.29 | 64.71 | 59.46 |
| DII_ifut_lvl_chg21 | up_tail | 0.85 | 0.1028 | 41 | 68.29 | 57.14 | 57 | 63.16 | 56.25 | 37 | 64.86 | 58.54 | 63.16 | 56.25 |
| DII_index_rflow_sum7 | up_tail | 0.9 | 0.08087 | 30 | 60 | 51.43 | 46 | 63.04 | 48.33 | 25 | 64 | 53.33 | 63.04 | 48.33 |
| DII_index_rflow_mean7 | up_tail | 0.9 | 0.08144 | 30 | 60 | 51.43 | 46 | 63.04 | 48.33 | 25 | 64 | 53.33 | 63.04 | 48.33 |
| DII_v2inst_rflow_sum7 | up_tail | 0.9 | 0.08087 | 30 | 60 | 51.43 | 46 | 63.04 | 48.33 | 25 | 64 | 53.33 | 63.04 | 48.33 |
| DII_v2inst_rflow_mean7 | up_tail | 0.9 | 0.08144 | 30 | 60 | 51.43 | 46 | 63.04 | 48.33 | 25 | 64 | 53.33 | 63.04 | 48.33 |
| v3_smart_money_conflict | up_tail | 0.8 | 0.08271 | 64 | 67.19 | 55.84 | 33 | 63.64 | 51.22 | 27 | 62.96 | 58.62 | 62.96 | 51.22 |
| v3_smart_money_conflict | up_tail | 0.85 | 0.08271 | 64 | 67.19 | 55.84 | 33 | 63.64 | 51.22 | 27 | 62.96 | 58.62 | 62.96 | 51.22 |

## Closest-to-70% sign candidates with relaxed n≥10 non-FLAT calls

These are the nearest "maybe gems" but **not enough evidence**.  Several top
rows have only ~10-13 non-FLAT calls in one holdout period; one interpretable
price-volatility expansion rule reaches roughly 75% sign in validation and 73%
in confirmation, but validation has only ~12 non-FLAT calls.

| feature | mode | quantile | rho_dev | dev2023_24_sign_n | dev2023_24_sign_pct | dev2023_24_exact_pct | val2025_sign_n | val2025_sign_pct | val2025_exact_pct | confirm2026_sign_n | confirm2026_sign_pct | confirm2026_exact_pct | min_val_confirm_sign_pct | min_val_confirm_exact_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Client_sput_rflow_sum3 | up_tail | 0.9 | -0.05258 | 25 | 64 | 45.71 | 13 | 76.92 | 62.5 | 11 | 81.82 | 81.82 | 76.92 | 62.5 |
| px_rv20_chg15 | up_tail | 0.85 | 0.05995 | 35 | 74.29 | 55.32 | 12 | 75 | 60 | 26 | 73.08 | 63.33 | 73.08 | 60 |
| pro_fii_agreement_v3inst_lvl_sum7 | up_tail | 0.9 | 0.07095 | 28 | 64.29 | 51.43 | 31 | 74.19 | 71.88 | 10 | 70 | 63.64 | 70 | 63.64 |
| pro_fii_agreement_v3inst_lvl_sum7 | up_tail | 0.925 | 0.07095 | 28 | 64.29 | 51.43 | 31 | 74.19 | 71.88 | 10 | 70 | 63.64 | 70 | 63.64 |
| pro_fii_agreement_v3inst_lvl_sum7 | up_tail | 0.95 | 0.07095 | 28 | 64.29 | 51.43 | 31 | 74.19 | 71.88 | 10 | 70 | 63.64 | 70 | 63.64 |
| pro_fii_agreement_v3inst_lvl_mean7 | up_tail | 0.9 | 0.07567 | 28 | 64.29 | 51.43 | 31 | 74.19 | 71.88 | 10 | 70 | 63.64 | 70 | 63.64 |
| pro_fii_agreement_v3inst_lvl_mean7 | up_tail | 0.925 | 0.07567 | 28 | 64.29 | 51.43 | 31 | 74.19 | 71.88 | 10 | 70 | 63.64 | 70 | 63.64 |
| pro_fii_agreement_v3inst_lvl_mean7 | up_tail | 0.95 | 0.07567 | 28 | 64.29 | 51.43 | 31 | 74.19 | 71.88 | 10 | 70 | 63.64 | 70 | 63.64 |
| pro_fii_agreement_v3inst_lvl_posdays7 | up_tail | 0.9 | 0.07613 | 28 | 64.29 | 51.43 | 31 | 74.19 | 71.88 | 10 | 70 | 63.64 | 70 | 63.64 |
| pro_fii_agreement_v3inst_lvl_posdays7 | up_tail | 0.925 | 0.07613 | 28 | 64.29 | 51.43 | 31 | 74.19 | 71.88 | 10 | 70 | 63.64 | 70 | 63.64 |

## Overfit traps: dev looked 70%+, confirmation collapsed

This is why I am not going to force a fake 80% number.  Many human-plausible
OI/level/crowding patterns look excellent on 2023-2024 and then die in 2026.

| feature | mode | quantile | dev2023_24_n | dev2023_24_exact_pct | val2025_n | val2025_exact_pct | confirm2026_n | confirm2026_exact_pct | dev_minus_confirm_exact_pct |
|---|---|---|---|---|---|---|---|---|---|
| Pro_v3inst_rflow_chg7 | up_tail | 0.925 | 26 | 73.08 | 10 | 40 | 14 | 14.29 | 58.79 |
| Pro_optheavy_lvl | up_tail | 0.925 | 26 | 73.08 | 137 | 37.23 | 105 | 36.19 | 36.89 |
| Client_icall_qflow_mean7 | up_tail | 0.9 | 35 | 71.43 | 34 | 52.94 | 25 | 36 | 35.43 |
| Client_icall_qflow_sum7 | up_tail | 0.9 | 35 | 71.43 | 34 | 52.94 | 25 | 36 | 35.43 |
| oc_pcr_near_atm_z21 | up_tail | 0.9 | 34 | 70.59 | 31 | 38.71 | 19 | 36.84 | 33.75 |
| DII_v2inst_lvl | up_tail | 0.925 | 26 | 73.08 | 218 | 40.37 | 164 | 39.63 | 33.45 |
| Pro_v3inst_rflow | up_tail | 0.925 | 26 | 73.08 | 13 | 46.15 | 10 | 40 | 33.08 |
| pro_fii_spread_v2inst_rflow | up_tail | 0.9 | 35 | 71.43 | 13 | 46.15 | 15 | 40 | 31.43 |
| Pro_scall_lvl_z21 | up_tail | 0.925 | 26 | 73.08 | 28 | 32.14 | 16 | 43.75 | 29.33 |
| Pro_scall_lvl_z63 | up_tail | 0.925 | 25 | 72 | 21 | 38.1 | 11 | 45.45 | 26.55 |

## Frozen-on-development ML sanity check

A real high-accuracy structure should not need continual hand-picking.  The
frozen models below were trained on development only and applied unchanged to
2025/2026; they do **not** beat v3.

| top_n | model | dev2023_24 | val2025 | confirm2026 |
|---|---|---|---|---|
| 20 | gb_depth2 | 62.97 | 39.52 | 41.57 |
| 80 | hgb_depth2 | 74.34 | 43.15 | 40.96 |
| 35 | gb_depth2 | 62.39 | 41.13 | 40.96 |
| 12 | gb_depth2 | 56.56 | 42.74 | 39.76 |
| 12 | hgb_depth2 | 60.93 | 40.73 | 39.16 |
| 120 | gb_depth2 | 67.35 | 39.92 | 39.16 |
| 120 | hgb_depth2 | 74.93 | 42.74 | 38.55 |
| 12 | logreg_C0.03 | 50.73 | 36.29 | 38.55 |
| 50 | hgb_depth2 | 71.43 | 40.32 | 37.95 |
| 35 | rf_depth4 | 56.56 | 41.53 | 37.35 |
| 120 | logreg_C0.03 | 51.6 | 35.89 | 36.75 |
| 80 | gb_depth2 | 64.14 | 40.73 | 36.14 |
| 20 | hgb_depth2 | 66.47 | 37.9 | 36.14 |
| 35 | hgb_depth2 | 69.1 | 36.29 | 36.14 |
| 12 | rf_depth4 | 53.35 | 43.15 | 35.54 |
| 80 | logreg_C0.03 | 50.44 | 39.52 | 35.54 |
| 50 | logreg_C0.03 | 50.44 | 39.11 | 35.54 |
| 20 | logreg_C0.03 | 50.73 | 31.85 | 35.54 |
| 50 | gb_depth2 | 63.85 | 42.34 | 34.94 |
| 35 | logreg_C0.03 | 50.44 | 32.26 | 34.94 |

## Interpretation for next iteration

- Multi-day DII/index-future *level change* keeps appearing in the best
  selective tables.  It may be a regime/crowding proxy, but it is only a
  55-62% exact zone so far.
- Volatility expansion after the last 15 sessions is the closest 70% sign idea,
  but it is low-coverage and price-only; it needs much more forward data.
- Ensembles/model capacity easily overfit.  The correct next move is not to
  promote complexity; it is to keep v3 as default/candidate, accumulate forward
  sessions, and test these selective states prospectively.

Artifacts in this folder are deliberately auditable:

- `threshold_rules.csv` — all exported threshold rules.
- `top_validated_exact_n20.csv`, `top_validated_sign_n20.csv`,
  `closest_70_sign_n10.csv` — ranked OOS views.
- `overfit_examples.csv` — high-dev, bad-confirmation traps.
- `ml_frozen_dev_results.csv` / `ml_frozen_dev_pivot.csv` — model sanity check.
- `summary.json`, `class_balance.csv` — run metadata.
