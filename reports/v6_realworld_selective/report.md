# V6 real-world selective search

> Research only; no production change.  This pass specifically asked: can we
> make a next-day signal usable in the real world by requiring multiple
> institutional/psychology conditions or by adding 10+ years of price-regime
> context?

## Summary

- V4 dev-fitted rule pool used for pair search: **800** rules.
- Pair/conjunctions checked: **319600**.
- Pair/conjunctions passing the dev screen and exported internally: **13213**.
- Pairs with ≥75% exact on both 2025 and 2026 holdouts, n≥10 each: **0**.
- Pairs with ≥75% sign on both 2025 and 2026 holdouts, sign-n≥10 each: **0**.
- Long price-history rows tested: **4136**.
- Price-only rules exported: **2562**.
- Price-only rules with ≥75% exact on both 2023-2024 and 2025-2026 holdouts, n≥20 each: **0**.
- Price-only rules with ≥75% sign on both holdouts, sign-n≥20 each: **0**.

## Bottom line

The real-world selective search still does **not** produce an honest 75-85%
production signal.  Pairing OI/psychology rules improves some tiny pockets, but
the best pair that has at least 10 calls in both holdouts reaches only the
low-60s exact / low-70s sign zone.  Long price history also fails to create a
stable 75% filter.

## Best pair/conjunction rules requiring at least 10 calls in both holdouts

| left_feature | left_mode | left_quantile | right_feature | right_mode | right_quantile | dev2023_24_n | dev2023_24_exact_pct | dev2023_24_sign_pct | val2025_n | val2025_exact_pct | val2025_sign_pct | confirm2026_n | confirm2026_exact_pct | confirm2026_sign_pct | confirm2026_sign_n | min_val_confirm_exact_pct | min_val_confirm_sign_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FII_ifut_volshare | up_tail | 0.75 | Pro_ifut_ds | up_tail | 0.85 | 20 | 65 | 86.67 | 14 | 64.29 | 69.23 | 11 | 63.64 | 70 | 10 | 63.64 | 69.23 |
| FII_scall_volshare | up_tail | 0.8 | FII_iput_dl | up_tail | 0.9 | 17 | 82.35 | 93.33 | 10 | 70 | 70 | 13 | 61.54 | 80 | 10 | 61.54 | 70 |
| pro_fii_agreement_optheavy_qflow_z63 | up_tail | 0.75 | DII_sfut_ds | up_tail | 0.85 | 16 | 81.25 | 100 | 13 | 61.54 | 66.67 | 10 | 70 | 70 | 10 | 61.54 | 66.67 |
| pro_fii_agreement_optheavy_qflow_z63 | up_tail | 0.8 | DII_sfut_ds | up_tail | 0.85 | 16 | 81.25 | 100 | 13 | 61.54 | 66.67 | 10 | 70 | 70 | 10 | 61.54 | 66.67 |
| DII_sput_qflow_z63 | up_tail | 0.75 | Pro_scall_dvol | up_tail | 0.8 | 17 | 52.94 | 81.82 | 18 | 61.11 | 73.33 | 11 | 72.73 | 72.73 | 11 | 61.11 | 72.73 |
| DII_sput_qflow_z63 | up_tail | 0.7 | Pro_scall_dvol | up_tail | 0.8 | 19 | 52.63 | 83.33 | 18 | 61.11 | 73.33 | 11 | 72.73 | 72.73 | 11 | 61.11 | 72.73 |
| Pro_scall_volshare | up_tail | 0.8 | Pro_ifut_ds | up_tail | 0.85 | 17 | 76.47 | 81.25 | 16 | 62.5 | 71.43 | 15 | 60 | 69.23 | 13 | 60 | 69.23 |
| px_rv20 | up_tail | 0.925 | DII_sput_qflow_z63 | up_tail | 0.7 | 18 | 72.22 | 92.86 | 13 | 69.23 | 69.23 | 15 | 60 | 69.23 | 13 | 60 | 69.23 |
| px_rv20 | up_tail | 0.925 | DII_sput_rflow_z63 | up_tail | 0.7 | 18 | 72.22 | 92.86 | 15 | 73.33 | 73.33 | 15 | 60 | 69.23 | 13 | 60 | 69.23 |
| px_rv20 | up_tail | 0.925 | DII_sput_qflow_z63 | up_tail | 0.75 | 18 | 72.22 | 92.86 | 13 | 69.23 | 69.23 | 15 | 60 | 69.23 | 13 | 60 | 69.23 |
| px_rv20_sum4 | up_tail | 0.925 | DII_sput_rflow_z63 | up_tail | 0.7 | 20 | 65 | 92.86 | 14 | 71.43 | 71.43 | 15 | 60 | 69.23 | 13 | 60 | 69.23 |
| px_rv20_sum4 | up_tail | 0.925 | DII_sput_qflow_z63 | up_tail | 0.75 | 20 | 65 | 92.86 | 13 | 69.23 | 69.23 | 15 | 60 | 69.23 | 13 | 60 | 69.23 |

## Pairs that looked good on dev+2025, then hit 2026

This table is useful for forward-watch ideas, but several rows have tiny 2026
sample sizes.  Do not promote them without fresh forward evidence.

| left_feature | left_mode | left_quantile | right_feature | right_mode | right_quantile | dev2023_24_n | dev2023_24_exact_pct | dev2023_24_sign_pct | val2025_n | val2025_exact_pct | val2025_sign_pct | confirm2026_n | confirm2026_exact_pct | confirm2026_sign_pct | confirm2026_sign_n | min_val_confirm_exact_pct | min_val_confirm_sign_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Pro_futheavy_qflow_z21 | up_tail | 0.85 | Pro_ifut_ds | up_tail | 0.85 | 21 | 80.95 | 94.44 | 10 | 70 | 77.78 | 1 | 100 | 100 | 1 | 70 | 77.78 |
| Pro_sput_lvl_chg7 | up_tail | 0.9 | Pro_sput_lvl_chg7 | up_tail | 0.925 | 26 | 69.23 | 75 | 10 | 60 | 75 | 1 | 100 | 100 | 1 | 60 | 75 |
| DII_scall_lvl_z21 | up_tail | 0.925 | Pro_scall_volshare | up_tail | 0.8 | 19 | 78.95 | 88.24 | 10 | 70 | 70 | 8 | 75 | 85.71 | 7 | 70 | 70 |
| Client_v3inst_rflow_sum4 | up_tail | 0.75 | DII_ifut_ds | up_tail | 0.85 | 16 | 62.5 | 90.91 | 10 | 70 | 77.78 | 4 | 75 | 75 | 4 | 70 | 75 |
| Client_v3inst_rflow_mean4 | up_tail | 0.75 | DII_ifut_ds | up_tail | 0.85 | 16 | 62.5 | 90.91 | 10 | 70 | 77.78 | 4 | 75 | 75 | 4 | 70 | 75 |
| Client_v3inst_rflow_sum4 | up_tail | 0.75 | pro_fii_agreement_v2inst_rflow_z63 | up_tail | 0.8 | 17 | 70.59 | 100 | 10 | 60 | 75 | 8 | 75 | 75 | 8 | 60 | 75 |
| Client_v3inst_rflow_mean4 | up_tail | 0.75 | pro_fii_agreement_v2inst_rflow_z63 | up_tail | 0.8 | 17 | 70.59 | 100 | 10 | 60 | 75 | 8 | 75 | 75 | 8 | 60 | 75 |
| Client_index_qflow_sum4 | up_tail | 0.9 | oc_near_call_doi_pct_sum15 | up_tail | 0.75 | 15 | 80 | 85.71 | 10 | 40 | 80 | 4 | 75 | 75 | 4 | 40 | 75 |
| Client_v2inst_qflow_sum4 | up_tail | 0.9 | oc_near_call_doi_pct_sum15 | up_tail | 0.75 | 15 | 80 | 85.71 | 10 | 40 | 80 | 4 | 75 | 75 | 4 | 40 | 75 |
| smart_vs_client_v2inst_qflow_sum4 | up_tail | 0.9 | oc_near_call_doi_pct_sum15 | up_tail | 0.75 | 15 | 73.33 | 84.62 | 10 | 40 | 80 | 4 | 75 | 75 | 4 | 40 | 75 |
| smart_vs_client_v2inst_qflow_mean4 | up_tail | 0.9 | oc_near_call_doi_pct_sum15 | up_tail | 0.75 | 15 | 73.33 | 84.62 | 10 | 40 | 80 | 4 | 75 | 75 | 4 | 40 | 75 |
| DII_sput_qflow_z63 | up_tail | 0.7 | Pro_ifut_ds | up_tail | 0.85 | 15 | 66.67 | 83.33 | 10 | 70 | 70 | 7 | 71.43 | 71.43 | 7 | 70 | 70 |

## Best long price-only rules

These use NIFTY daily history from 2010 onward.  Train = 2010-2022, validation =
2023-2024, confirmation = 2025-2026.  They also do not reach 75% robustly.

| feature | mode | quantile | rho_train2010_22 | train2010_22_n | train2010_22_exact_pct | train2010_22_sign_pct | val2023_24_n | val2023_24_exact_pct | val2023_24_sign_pct | confirm2025_26_n | confirm2025_26_exact_pct | confirm2025_26_sign_pct | confirm2025_26_sign_n | min_val_confirm_exact_pct | min_val_confirm_sign_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| range_mean15 | up_tail | 0.6 | 0.0292 | 1288 | 48.45 | 54.55 | 34 | 61.76 | 77.78 | 32 | 59.38 | 67.86 | 28 | 59.38 | 67.86 |
| ret_z60 | up_tail | 0.95 | 0.0823 | 160 | 56.88 | 67.41 | 24 | 58.33 | 73.68 | 23 | 56.52 | 61.9 | 21 | 56.52 | 61.9 |
| gap_sum3 | up_tail | 0.85 | 0.06048 | 484 | 48.76 | 57.14 | 39 | 61.54 | 75 | 36 | 55.56 | 66.67 | 30 | 55.56 | 66.67 |
| gap_sum2 | up_tail | 0.9 | 0.07081 | 323 | 52.94 | 61.51 | 20 | 55 | 64.71 | 20 | 65 | 76.47 | 17 | 55 | 64.71 |
| range_mean20 | up_tail | 0.55 | 0.02566 | 1448 | 47.72 | 53.73 | 42 | 57.14 | 72.73 | 40 | 55 | 61.11 | 36 | 55 | 61.11 |
| range_mean20 | up_tail | 0.6 | 0.02566 | 1287 | 47.94 | 54.03 | 29 | 65.52 | 86.36 | 31 | 54.84 | 60.71 | 28 | 54.84 | 60.71 |
| ret4 | up_tail | 0.85 | 0.02999 | 484 | 47.31 | 56.27 | 37 | 62.16 | 79.31 | 33 | 54.55 | 64.29 | 28 | 54.55 | 64.29 |
| ret_z40 | up_tail | 0.95 | 0.08048 | 161 | 59.01 | 68.35 | 22 | 54.55 | 70.59 | 21 | 57.14 | 63.16 | 19 | 54.55 | 63.16 |
| rv15 | up_tail | 0.7 | 0.03013 | 966 | 48.65 | 54.65 | 27 | 62.96 | 85 | 66 | 54.55 | 61.02 | 59 | 54.55 | 61.02 |
| range_mean2 | up_tail | 0.8 | 0.0237 | 646 | 49.85 | 55.33 | 24 | 54.17 | 72.22 | 24 | 62.5 | 71.43 | 21 | 54.17 | 71.43 |
| rv10 | up_tail | 0.7 | 0.03961 | 967 | 49.64 | 56.07 | 37 | 54.05 | 68.97 | 57 | 56.14 | 60.38 | 53 | 54.05 | 60.38 |
| gap_sum5 | up_tail | 0.9 | 0.04294 | 323 | 45.51 | 54.04 | 26 | 53.85 | 66.67 | 21 | 57.14 | 70.59 | 17 | 53.85 | 66.67 |

## Practical consequence for next-day use

- Keep v2/v3 reports as **context**, not a standalone trade.
- If a v4/v5/v6 pocket triggers, treat it as a **forward-watch tag**, not as a
  proved edge.
- The next realistic route to 70%+ is not more EOD curve-fitting; it is a longer
  10-15 minute intraday candle/level dataset with exact date-stamped
  institutional levels, then an executable backtest with costs/slippage.
- Until that exists, the honest production action remains: emit next-day lean +
  conditional level plan, and require live price confirmation before acting.
