# V9 OI + Intraday Confirmation

## Objective

Retest the actual FII/DII/Pro/Client idea with the new intraday history: prior-day v3 OI lean plus next-session first 10/15/30/60-minute confirmation, entered only after the candle closes and scored by symmetric target/stop simulation.

## Data

- V3 OI predictions: 757 rows from `reports/backtest_v3_candidate_2023-08_to_2026-09/v3_predictions.csv`.
- 10m sessions: 2336 from `historical/nifty_10m.csv`.
- 15m sessions: 2336 from `historical/nifty_15m.csv`.
- Split: train 2023-2024, validation 2025, confirmation 2026.
- Ambiguous target+stop bars are counted as losses; target and stop are symmetric percentages.

## Main result

- Rule summaries checked: **29,568**.
- Rules clearing strict 70% win-rate in train, 2025 validation, and 2026 confirmation with sample guards and positive average points: **0**.
- Verdict: the OI lean still does not become a production 70%+ executable edge after first-candle confirmation.

## Best V9 rules by 2026 confirmation slice

| interval_min | rule | direction | entry_after_bars | target_pct | calls | win_rate | avg_pnl_pts | train_2023_2024_calls | train_2023_2024_win_rate | val_2025_calls | val_2025_win_rate | confirm_2026_calls | confirm_2026_win_rate | ambiguous_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | first_overrides_v3_conflict_first10m_gt0.3_conf0_abs0.1 | DOWN | 1 | 0.15 | 25 | 56.00 | 4.36 | 12 | 41.67 | 8 | 50.00 | 5 | 100.00 | 8.00 |
| 10 | first_overrides_v3_conflict_first10m_gt0.3_conf15_abs0.1 | DOWN | 1 | 0.15 | 25 | 56.00 | 4.36 | 12 | 41.67 | 8 | 50.00 | 5 | 100.00 | 8.00 |
| 10 | first_overrides_v3_conflict_first10m_gt0.3_conf20_abs0.1 | DOWN | 1 | 0.15 | 25 | 56.00 | 4.36 | 12 | 41.67 | 8 | 50.00 | 5 | 100.00 | 8.00 |
| 10 | first_overrides_v3_conflict_first10m_gt0.3_conf20_abs0 | DOWN | 1 | 0.15 | 26 | 53.85 | 2.74 | 12 | 41.67 | 9 | 44.44 | 5 | 100.00 | 7.69 |
| 10 | first_overrides_v3_conflict_first10m_gt0.3_conf20_abs0.05 | DOWN | 1 | 0.15 | 26 | 53.85 | 2.74 | 12 | 41.67 | 9 | 44.44 | 5 | 100.00 | 7.69 |
| 10 | first_overrides_v3_conflict_first10m_gt0.3_conf35_abs0 | DOWN | 1 | 0.15 | 15 | 53.33 | 2.55 | 5 | 20.00 | 6 | 50.00 | 4 | 100.00 | 6.67 |
| 10 | first_overrides_v3_conflict_first10m_gt0.3_conf35_abs0.05 | DOWN | 1 | 0.15 | 15 | 53.33 | 2.55 | 5 | 20.00 | 6 | 50.00 | 4 | 100.00 | 6.67 |
| 10 | first_overrides_v3_conflict_first10m_gt0.3_conf35_abs0.1 | DOWN | 1 | 0.15 | 15 | 53.33 | 2.55 | 5 | 20.00 | 6 | 50.00 | 4 | 100.00 | 6.67 |
| 10 | first_overrides_v3_conflict_first10m_gt0.3_conf35_abs0.15 | DOWN | 1 | 0.15 | 15 | 53.33 | 2.55 | 5 | 20.00 | 6 | 50.00 | 4 | 100.00 | 6.67 |
| 10 | first_overrides_v3_conflict_first10m_gt0.3_conf25_abs0 | DOWN | 1 | 0.15 | 23 | 52.17 | 1.67 | 12 | 41.67 | 7 | 42.86 | 4 | 100.00 | 8.70 |
| 10 | first_overrides_v3_conflict_first10m_gt0.3_conf25_abs0.05 | DOWN | 1 | 0.15 | 23 | 52.17 | 1.67 | 12 | 41.67 | 7 | 42.86 | 4 | 100.00 | 8.70 |
| 10 | first_overrides_v3_conflict_first10m_gt0.3_conf25_abs0.1 | DOWN | 1 | 0.15 | 23 | 52.17 | 1.67 | 12 | 41.67 | 7 | 42.86 | 4 | 100.00 | 8.70 |
| 10 | first_overrides_v3_conflict_first10m_gt0.3_conf0_abs0.15 | DOWN | 1 | 0.15 | 18 | 50.00 | -0.18 | 7 | 28.57 | 7 | 42.86 | 4 | 100.00 | 5.56 |
| 10 | first_overrides_v3_conflict_first10m_gt0.3_conf15_abs0.15 | DOWN | 1 | 0.15 | 18 | 50.00 | -0.18 | 7 | 28.57 | 7 | 42.86 | 4 | 100.00 | 5.56 |
| 10 | first_overrides_v3_conflict_first10m_gt0.3_conf20_abs0.15 | DOWN | 1 | 0.15 | 18 | 50.00 | -0.18 | 7 | 28.57 | 7 | 42.86 | 4 | 100.00 | 5.56 |
| 10 | first_overrides_v3_conflict_first10m_gt0.3_conf25_abs0.15 | DOWN | 1 | 0.15 | 18 | 50.00 | -0.18 | 7 | 28.57 | 7 | 42.86 | 4 | 100.00 | 5.56 |
| 10 | first_overrides_v3_conflict_first10m_gt0.3_conf30_abs0.15 | DOWN | 1 | 0.15 | 18 | 50.00 | -0.18 | 7 | 28.57 | 7 | 42.86 | 4 | 100.00 | 5.56 |
| 10 | first_overrides_v3_conflict_first10m_gt0.3_conf30_abs0 | DOWN | 1 | 0.15 | 19 | 47.37 | -1.96 | 8 | 25.00 | 7 | 42.86 | 4 | 100.00 | 10.53 |
| 10 | first_overrides_v3_conflict_first10m_gt0.3_conf30_abs0.05 | DOWN | 1 | 0.15 | 19 | 47.37 | -1.96 | 8 | 25.00 | 7 | 42.86 | 4 | 100.00 | 10.53 |
| 10 | first_overrides_v3_conflict_first10m_gt0.3_conf30_abs0.1 | DOWN | 1 | 0.15 | 19 | 47.37 | -1.96 | 8 | 25.00 | 7 | 42.86 | 4 | 100.00 | 10.53 |
| 10 | v3_align_first20m_gt0.2_conf20_abs0 | UP | 2 | 0.10 | 35 | 57.14 | 3.89 | 12 | 41.67 | 15 | 53.33 | 8 | 87.50 | 0.00 |
| 10 | v3_align_first20m_gt0.2_conf20_abs0.05 | UP | 2 | 0.10 | 35 | 57.14 | 3.89 | 12 | 41.67 | 15 | 53.33 | 8 | 87.50 | 0.00 |
| 10 | v3_align_first20m_gt0.2_conf0_abs0.1 | UP | 2 | 0.10 | 33 | 57.58 | 4.05 | 10 | 40.00 | 15 | 53.33 | 8 | 87.50 | 0.00 |
| 10 | v3_align_first20m_gt0.2_conf15_abs0.1 | UP | 2 | 0.10 | 33 | 57.58 | 4.05 | 10 | 40.00 | 15 | 53.33 | 8 | 87.50 | 0.00 |
| 10 | v3_align_first20m_gt0.2_conf20_abs0.1 | UP | 2 | 0.10 | 33 | 57.58 | 4.05 | 10 | 40.00 | 15 | 53.33 | 8 | 87.50 | 0.00 |

## Interpretation

High 2026-only pockets are not enough. A rule must also hold in the 2023-2024 development window and 2025 validation. V9 keeps the production default unchanged and gives us a forward-test protocol: OI lean + fixed intraday confirmation + symmetric execution.