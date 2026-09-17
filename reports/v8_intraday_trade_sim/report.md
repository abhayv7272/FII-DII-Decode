# V8 Intraday Trade-Level Simulation

## Objective

Test the stronger real-world path after V7: enter only after a 10/15-minute confirmation candle and then simulate target/stop outcomes on the remaining intraday bars. This avoids counting a move that was already visible before entry.

## Data

- 10m bars: 88,764 rows from `historical/nifty_10m.csv`.
- 15m bars: 58,397 rows from `historical/nifty_15m.csv`.
- Dated PDF level rows: 140 from `historical/institutional_levels_pdf_2026.csv`.
- Every trade uses symmetric percentage target/stop (`target_pct == stop_pct`) and ambiguous target+stop bars are counted as losses, not wins.

## Main result

- Generic first-window rules clearing 70% win-rate on train(2017-24), validation(2025), confirmation(2026), with sample guards and positive average points: **0**.
- PDF-level reaction rules clearing 70% on July-Aug training and September confirmation with sample guards and positive average points: **0**.
- Verdict: no production-ready 70%+ executable intraday edge yet. High-looking open-to-close direction pockets from V7 do not survive honest target/stop execution.

## Best generic 10/15m first-window trade rules

| interval_min | rule | direction | entry_after_bars | target_pct | calls | win_rate | avg_pnl_pts | train_2017_2024_calls | train_2017_2024_win_rate | val_2025_calls | val_2025_win_rate | confirm_2026_calls | confirm_2026_win_rate | ambiguous_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | first30_trend_lt_-0.4 | DOWN | 3 | 0.20 | 281 | 52.31 | 2.36 | 242 | 50.00 | 18 | 61.11 | 21 | 71.43 | 4.27 |
| 15 | first30_trend_lt_-0.4 | DOWN | 2 | 0.20 | 281 | 51.60 | 1.94 | 242 | 49.17 | 18 | 61.11 | 21 | 71.43 | 5.69 |
| 10 | first10_trend_lt_-0.4 | DOWN | 1 | 0.20 | 168 | 51.79 | 0.79 | 144 | 51.39 | 10 | 30.00 | 14 | 71.43 | 8.33 |
| 10 | first10_trend_lt_-0.3 | DOWN | 1 | 0.20 | 291 | 52.58 | 1.05 | 248 | 52.82 | 23 | 34.78 | 20 | 70.00 | 4.81 |
| 10 | first10_trend_lt_-0.3 | DOWN | 1 | 0.10 | 291 | 42.27 | -2.19 | 248 | 40.73 | 23 | 34.78 | 20 | 70.00 | 21.31 |
| 10 | first10_trend_lt_-0.3 | DOWN | 1 | 0.08 | 291 | 35.40 | -3.22 | 248 | 33.06 | 23 | 30.43 | 20 | 70.00 | 33.68 |
| 10 | first10_trend_lt_-0.2 | DOWN | 1 | 0.30 | 525 | 56.76 | 6.82 | 436 | 57.11 | 47 | 42.55 | 42 | 69.05 | 1.33 |
| 10 | first10_trend_lt_-0.2 | DOWN | 1 | 0.20 | 525 | 52.76 | 1.93 | 436 | 52.29 | 47 | 42.55 | 42 | 69.05 | 3.24 |
| 10 | first30_trend_lt_-0.4 | DOWN | 3 | 0.30 | 281 | 54.09 | 4.66 | 242 | 52.48 | 18 | 61.11 | 21 | 66.67 | 1.78 |
| 15 | first30_trend_lt_-0.4 | DOWN | 2 | 0.30 | 281 | 54.09 | 4.66 | 242 | 52.48 | 18 | 61.11 | 21 | 66.67 | 1.78 |
| 10 | first30_trend_lt_-0.4 | DOWN | 3 | 0.15 | 281 | 50.53 | 0.52 | 242 | 49.17 | 18 | 50.00 | 21 | 66.67 | 7.47 |
| 15 | first30_trend_lt_-0.4 | DOWN | 2 | 0.15 | 281 | 48.40 | -0.52 | 242 | 46.69 | 18 | 50.00 | 21 | 66.67 | 10.68 |
| 10 | first30_trend_gt_0.4 | UP | 3 | 0.10 | 160 | 43.75 | -1.38 | 126 | 42.06 | 22 | 40.91 | 12 | 66.67 | 18.12 |
| 10 | first20_fade_gt_0.4 | DOWN | 2 | 0.30 | 142 | 52.11 | 1.58 | 110 | 50.00 | 20 | 55.00 | 12 | 66.67 | 2.11 |
| 10 | first20_fade_gt_0.4 | DOWN | 2 | 0.15 | 142 | 51.41 | 0.73 | 110 | 50.91 | 20 | 45.00 | 12 | 66.67 | 6.34 |
| 10 | first10_trend_lt_-0.08 | DOWN | 1 | 0.30 | 953 | 56.14 | 5.97 | 791 | 55.88 | 94 | 51.06 | 68 | 66.18 | 0.73 |
| 10 | first10_trend_lt_-0.1 | DOWN | 1 | 0.30 | 879 | 56.20 | 6.05 | 736 | 56.25 | 79 | 48.10 | 64 | 65.62 | 0.80 |
| 10 | first10_trend_lt_-0.05 | DOWN | 1 | 0.30 | 1078 | 56.03 | 5.97 | 897 | 55.85 | 106 | 50.94 | 75 | 65.33 | 0.65 |
| 10 | first10_trend_lt_-0.3 | DOWN | 1 | 0.30 | 291 | 57.39 | 5.46 | 248 | 58.06 | 23 | 43.48 | 20 | 65.00 | 2.41 |
| 10 | first10_trend_lt_-0.3 | DOWN | 1 | 0.15 | 291 | 51.20 | 0.18 | 248 | 51.61 | 23 | 34.78 | 20 | 65.00 | 9.97 |

## Best PDF-level trade rules

| interval_min | rule | direction | entry_after_bars | target_pct | calls | win_rate | avg_pnl_pts | train_jul_aug_calls | train_jul_aug_win_rate | confirm_sep_calls | confirm_sep_win_rate | ambiguous_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15 | level_first4bars_touch15_buf5_all | UP | 4 | 0.10 | 11 | 45.45 | -2.39 | 8 | 25.00 | 3 | 100.00 | 0.00 |
| 15 | level_first4bars_touch15_buf5_all | UP | 4 | 0.20 | 11 | 45.45 | -4.77 | 8 | 25.00 | 3 | 100.00 | 0.00 |
| 15 | level_first4bars_touch10_buf5_all | UP | 4 | 0.10 | 10 | 50.00 | -0.20 | 7 | 28.57 | 3 | 100.00 | 0.00 |
| 15 | level_first4bars_touch10_buf5_all | UP | 4 | 0.20 | 10 | 50.00 | -0.40 | 7 | 28.57 | 3 | 100.00 | 0.00 |
| 15 | level_first2bars_touch5_buf10_all | UP | 2 | 0.30 | 10 | 50.00 | -2.34 | 8 | 37.50 | 2 | 100.00 | 0.00 |
| 15 | level_first4bars_touch5_buf10_all | UP | 4 | 0.30 | 10 | 50.00 | -2.34 | 8 | 37.50 | 2 | 100.00 | 0.00 |
| 15 | level_first2bars_touch5_buf10_all | UP | 2 | 0.10 | 10 | 40.00 | -4.97 | 8 | 25.00 | 2 | 100.00 | 0.00 |
| 15 | level_first4bars_touch5_buf10_all | UP | 4 | 0.10 | 10 | 40.00 | -4.97 | 8 | 25.00 | 2 | 100.00 | 0.00 |
| 15 | level_first2bars_touch5_buf10_all | UP | 2 | 0.15 | 10 | 40.00 | -7.45 | 8 | 25.00 | 2 | 100.00 | 0.00 |
| 15 | level_first4bars_touch5_buf10_all | UP | 4 | 0.15 | 10 | 40.00 | -7.45 | 8 | 25.00 | 2 | 100.00 | 0.00 |
| 15 | level_first2bars_touch5_buf10_all | UP | 2 | 0.20 | 10 | 40.00 | -9.93 | 8 | 25.00 | 2 | 100.00 | 0.00 |
| 15 | level_first4bars_touch5_buf10_all | UP | 4 | 0.20 | 10 | 40.00 | -9.93 | 8 | 25.00 | 2 | 100.00 | 0.00 |
| 15 | level_first2bars_touch5_buf5_all | UP | 2 | 0.10 | 9 | 44.44 | -2.89 | 6 | 16.67 | 3 | 100.00 | 0.00 |
| 15 | level_first4bars_touch5_buf5_all | UP | 4 | 0.10 | 9 | 44.44 | -2.89 | 6 | 16.67 | 3 | 100.00 | 0.00 |
| 15 | level_first2bars_touch15_buf5_all | UP | 2 | 0.10 | 9 | 44.44 | -2.89 | 6 | 16.67 | 3 | 100.00 | 0.00 |
| 15 | level_first2bars_touch10_buf5_all | UP | 2 | 0.10 | 9 | 44.44 | -2.89 | 6 | 16.67 | 3 | 100.00 | 0.00 |
| 15 | level_first2bars_touch5_buf5_all | UP | 2 | 0.20 | 9 | 44.44 | -5.77 | 6 | 16.67 | 3 | 100.00 | 0.00 |
| 15 | level_first4bars_touch5_buf5_all | UP | 4 | 0.20 | 9 | 44.44 | -5.77 | 6 | 16.67 | 3 | 100.00 | 0.00 |
| 15 | level_first2bars_touch15_buf5_all | UP | 2 | 0.20 | 9 | 44.44 | -5.78 | 6 | 16.67 | 3 | 100.00 | 0.00 |
| 15 | level_first2bars_touch10_buf5_all | UP | 2 | 0.20 | 9 | 44.44 | -5.78 | 6 | 16.67 | 3 | 100.00 | 0.00 |

## Interpretation

- This is a conditional intraday execution test, not an overnight pre-open forecast.
- Symmetric target/stop is stricter than many discretionary scalps; that is intentional so a 70% win-rate cannot be manufactured by using a tiny target and a huge stop.
- The exact-level sample remains too small and too clustered in 2026 to promote. It is useful as a forward-testing protocol: keep collecting exact levels daily, then score them without changing the V8 rules.