# V12 weekly composite search — next Monday to Friday

> **Research only. No production decoder or weekly direction was changed by this run.**
> This is a leak-safe test of the user's requested combination approach, not a
> licence to optimise repeatedly against the same 2025/2026 results.

## Forecast definition and timing

- A signal is made after the **last available session of a week** (normally Friday) from information known by that close.
- It forecasts the close of the **following Monday--Friday calendar week**; weeks with fewer than three trading sessions are excluded.
- UP / FLAT / DOWN labels use a predeclared ±0.50% weekly-return FLAT band.
- Development fit: 2023--2024. Validation: 2025. Confirmation: 2026.
- Participant OI, participant volume, option-chain proxy, price-regime and v2/v3 *signal* fields were supplied to the search. Prior backtest outcomes, target OHLC values, exact-hit flags and level-hit flags were explicitly excluded.

## Dataset and gates

- Usable weekly episodes: **160** (development 73, validation 52, confirmation 35).
- Point-in-time numeric feature candidates after the leakage deny-list: **4746**.
- Single threshold rules retained after development screen: **18527**.
- Agreement pairs evaluated from a development-selected pool: **16110**.
- Promotion gate: **≥85%** on both 2025 and 2026 with at least **10** calls in each period.

| period | weeks | up | flat | down | majority_baseline_pct |
|---|---|---|---|---|---|
| dev2023_24 | 73 | 39 | 17 | 17 | 53.42 |
| val2025 | 52 | 23 | 9 | 20 | 44.23 |
| confirm2026 | 35 | 11 | 10 | 14 | 40 |

## Result

- Single rules passing the 85% **exact** gate: **0**.
- Single rules passing the 85% non-FLAT **sign** gate: **0**.
- Agreement pairs passing the 85% **exact** gate: **0**.
- Agreement pairs passing the 85% non-FLAT **sign** gate: **0**.

A result of zero means the available historical EOD combinations did **not** prove
an 85% weekly directional predictor under the declared out-of-sample guard. The
scenario playbook can remain in the report, but it must remain context/conditional
rather than an 85% weekly forecast.

## Best single-rule candidates with both holdout sample guards

| feature | mode | quantile | rho_dev | dev2023_24_n | dev2023_24_exact_pct | dev2023_24_sign_pct | val2025_n | val2025_exact_pct | val2025_sign_pct | confirm2026_n | confirm2026_exact_pct | confirm2026_sign_pct | min_holdout_exact_pct | min_holdout_sign_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DII_optheavy_lvl_chg15 | both | 0.75 | 0.2187 | 36 | 47.22 | 58.62 | 21 | 71.43 | 83.33 | 19 | 63.16 | 92.31 | 63.16 | 83.33 |
| DII_v2inst_lvl_chg15 | both | 0.9 | 0.2343 | 14 | 50 | 63.64 | 17 | 64.71 | 78.57 | 13 | 61.54 | 88.89 | 61.54 | 78.57 |
| DII_scall_qflow_sum3 | both | 0.8 | 0.2017 | 30 | 43.33 | 59.09 | 16 | 62.5 | 71.43 | 13 | 61.54 | 72.73 | 61.54 | 71.43 |
| DII_scall_rflow_sum3 | both | 0.8 | 0.2088 | 30 | 46.67 | 63.64 | 16 | 62.5 | 71.43 | 13 | 61.54 | 72.73 | 61.54 | 71.43 |
| Client_sfut_rflow_sum4 | both | 0.75 | -0.121 | 38 | 42.11 | 64 | 13 | 61.54 | 61.54 | 11 | 63.64 | 87.5 | 61.54 | 61.54 |
| Client_sfut_rflow_mean4 | both | 0.75 | -0.121 | 38 | 42.11 | 64 | 13 | 61.54 | 61.54 | 11 | 63.64 | 87.5 | 61.54 | 61.54 |
| Pro_ifut_lvl_sum21 | both | 0.85 | 0.1157 | 22 | 50 | 61.11 | 20 | 60 | 66.67 | 14 | 64.29 | 75 | 60 | 66.67 |
| Pro_ifut_lvl_mean21 | both | 0.85 | 0.1091 | 22 | 50 | 61.11 | 20 | 60 | 66.67 | 14 | 64.29 | 75 | 60 | 66.67 |
| Pro_scall_rflow_z21 | both | 0.85 | 0.1105 | 22 | 54.55 | 66.67 | 13 | 61.54 | 80 | 12 | 58.33 | 77.78 | 58.33 | 77.78 |
| Pro_scall_rflow_z21 | both | 0.9 | 0.1105 | 16 | 62.5 | 76.92 | 11 | 63.64 | 77.78 | 12 | 58.33 | 77.78 | 58.33 | 77.78 |
| Pro_scall_rflow_z63 | both | 0.85 | 0.1586 | 22 | 63.64 | 82.35 | 11 | 63.64 | 77.78 | 12 | 58.33 | 70 | 58.33 | 70 |
| DII_scall_rflow_sum3 | both | 0.85 | 0.2088 | 22 | 45.45 | 62.5 | 10 | 60 | 75 | 12 | 58.33 | 70 | 58.33 | 70 |

## Best agreement-pair candidates with both holdout sample guards

| left_feature | right_feature | dev2023_24_n | dev2023_24_exact_pct | dev2023_24_sign_pct | val2025_n | val2025_exact_pct | val2025_sign_pct | confirm2026_n | confirm2026_exact_pct | confirm2026_sign_pct | min_holdout_exact_pct | min_holdout_sign_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FII_v3inst_lvl_sum21 | DII_ifut_lvl_chg21 | 10 | 90 | 100 | 19 | 57.89 | 73.33 | 11 | 45.45 | 62.5 | 45.45 | 62.5 |
| FII_v3inst_lvl_sum21 | DII_futheavy_lvl_chg21 | 10 | 90 | 100 | 16 | 68.75 | 78.57 | 11 | 45.45 | 62.5 | 45.45 | 62.5 |
| DII_futheavy_lvl_chg21 | DII_ifut_lvl_chg21 | 13 | 92.31 | 100 | 16 | 68.75 | 78.57 | 11 | 45.45 | 62.5 | 45.45 | 62.5 |
| Pro_ifut_lvl_posdays21 | Pro_v3inst_lvl_posdays21 | 10 | 90 | 100 | 13 | 53.85 | 53.85 | 16 | 43.75 | 53.85 | 43.75 | 53.85 |
| Pro_futheavy_lvl_sum15 | Pro_futheavy_lvl_mean15 | 11 | 81.82 | 90 | 19 | 42.11 | 50 | 18 | 50 | 60 | 42.11 | 50 |
| DII_v3inst_qflow_sum21 | DII_v3inst_qflow_mean21 | 11 | 90.91 | 100 | 12 | 58.33 | 77.78 | 12 | 41.67 | 62.5 | 41.67 | 62.5 |
| DII_v3inst_qflow_sum21 | DII_futheavy_qflow_sum21 | 11 | 90.91 | 100 | 12 | 58.33 | 77.78 | 12 | 41.67 | 62.5 | 41.67 | 62.5 |
| DII_v3inst_qflow_sum21 | DII_futheavy_qflow_mean21 | 11 | 90.91 | 100 | 12 | 58.33 | 77.78 | 12 | 41.67 | 62.5 | 41.67 | 62.5 |
| DII_v3inst_qflow_sum21 | FII_v3inst_lvl_sum21 | 10 | 90 | 100 | 12 | 58.33 | 77.78 | 12 | 41.67 | 62.5 | 41.67 | 62.5 |
| DII_v3inst_qflow_mean21 | DII_futheavy_qflow_sum21 | 11 | 90.91 | 100 | 12 | 58.33 | 77.78 | 12 | 41.67 | 62.5 | 41.67 | 62.5 |
| DII_v3inst_qflow_mean21 | DII_futheavy_qflow_mean21 | 11 | 90.91 | 100 | 12 | 58.33 | 77.78 | 12 | 41.67 | 62.5 | 41.67 | 62.5 |
| DII_v3inst_qflow_mean21 | FII_v3inst_lvl_sum21 | 10 | 90 | 100 | 12 | 58.33 | 77.78 | 12 | 41.67 | 62.5 | 41.67 | 62.5 |

## Implementation consequence

No weekly direction module is promoted from V12 unless a candidate meets the
gate above and subsequently survives a fresh forward window. The report should
continue to display the Monday--Friday **playbook** (Monday range seed,
Tuesday--Wednesday expansion test, expiry/sweep caution, Friday follow-through
or mean-reversion check) with `CONTEXT_ONLY` / `NO-VALIDATED-EDGE` status.

The existing V10 small-gap previous-close-touch module remains separate: it is
an at-open, same-day level-touch event and cannot be counted as proof of a
night-before Monday--Friday direction forecast.
