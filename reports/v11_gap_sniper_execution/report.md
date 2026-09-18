# V11 Gap Sniper Execution Audit

## Verdict

**No robust production trade conversion yet.** V10's tiny-gap previous-close touch remains a high-probability level-touch prediction, but the simple target/stop execution models tested here do not clear a robust 70% + positive-P&L gate across train, validation, and 2026 confirmation.

Robust positive 70% trade rules: **0**

Why this matters: the target is small, so wider stops can manufacture high win-rates while losing expectancy in one or more splits.  V11 therefore requires both hit-rate and positive average P&L in every split.

## Top high-win pockets (research only)

| band | entry_minute | filter | stop_multiplier | calls | train_2017_2023_calls | val_2024_2025_calls | confirm_2026_calls | win_rate | train_2017_2023_win_rate | val_2024_2025_win_rate | confirm_2026_win_rate | avg_pnl_pts | train_2017_2023_avg_pnl_pts | val_2024_2025_avg_pnl_pts | confirm_2026_avg_pnl_pts | mean_target_distance_pts | ambiguous_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.03-0.12 | 0 | none | 5.00 | 393 | 257 | 104 | 32 | 82.70 | 80.16 | 90.38 | 78.12 | 1.94 | -0.47 | 10.71 | -7.26 | 12.99 | 2.29 |
| 0.03-0.12 | 0 | not_away_more_than_0.03pct | 5.00 | 393 | 257 | 104 | 32 | 82.70 | 80.16 | 90.38 | 78.12 | 1.94 | -0.47 | 10.71 | -7.26 | 12.99 | 2.29 |
| 0.03-0.12 | 0 | none | 4.00 | 393 | 257 | 104 | 32 | 77.61 | 73.54 | 87.50 | 78.12 | 1.24 | -1.82 | 10.11 | -2.96 | 12.99 | 3.56 |
| 0.03-0.12 | 0 | not_away_more_than_0.03pct | 4.00 | 393 | 257 | 104 | 32 | 77.61 | 73.54 | 87.50 | 78.12 | 1.24 | -1.82 | 10.11 | -2.96 | 12.99 | 3.56 |
| 0.02-0.10 | 0 | none | 5.00 | 351 | 231 | 93 | 27 | 79.20 | 78.35 | 81.72 | 77.78 | 0.54 | 0.06 | 4.08 | -7.52 | 10.22 | 4.27 |
| 0.02-0.10 | 0 | not_away_more_than_0.03pct | 5.00 | 351 | 231 | 93 | 27 | 79.20 | 78.35 | 81.72 | 77.78 | 0.54 | 0.06 | 4.08 | -7.52 | 10.22 | 4.27 |
| 0.02-0.10 | 0 | none | 4.00 | 351 | 231 | 93 | 27 | 72.93 | 70.56 | 77.42 | 77.78 | -0.67 | -1.95 | 3.31 | -3.42 | 10.22 | 6.55 |
| 0.02-0.10 | 0 | not_away_more_than_0.03pct | 4.00 | 351 | 231 | 93 | 27 | 72.93 | 70.56 | 77.42 | 77.78 | -0.67 | -1.95 | 3.31 | -3.42 | 10.22 | 6.55 |
| 0.05-0.15 | 0 | none | 5.00 | 428 | 265 | 122 | 41 | 84.58 | 82.64 | 93.44 | 70.73 | 3.11 | 0.48 | 16.63 | -20.08 | 18.25 | 0.00 |
| 0.05-0.15 | 0 | not_away_more_than_0.03pct | 5.00 | 428 | 265 | 122 | 41 | 84.58 | 82.64 | 93.44 | 70.73 | 3.11 | 0.48 | 16.63 | -20.08 | 18.25 | 0.00 |
| 0.05-0.15 | 0 | none | 4.00 | 428 | 265 | 122 | 41 | 80.61 | 76.60 | 92.62 | 70.73 | 2.53 | -1.59 | 17.08 | -14.20 | 18.25 | 0.47 |
| 0.05-0.15 | 0 | not_away_more_than_0.03pct | 4.00 | 428 | 265 | 122 | 41 | 80.61 | 76.60 | 92.62 | 70.73 | 2.53 | -1.59 | 17.08 | -14.20 | 18.25 | 0.47 |
| 0.03-0.12 | 0 | none | 3.00 | 393 | 257 | 104 | 32 | 71.25 | 67.70 | 80.77 | 68.75 | 0.27 | -1.56 | 6.26 | -4.47 | 12.99 | 6.11 |
| 0.03-0.12 | 0 | not_away_more_than_0.03pct | 3.00 | 393 | 257 | 104 | 32 | 71.25 | 67.70 | 80.77 | 68.75 | 0.27 | -1.56 | 6.26 | -4.47 | 12.99 | 6.11 |
| 0.05-0.15 | 5 | none | 5.00 | 180 | 109 | 51 | 20 | 71.11 | 66.06 | 84.31 | 65.00 | 2.73 | -3.02 | 11.05 | 12.89 | 38.47 | 0.56 |
| 0.05-0.15 | 5 | none | 4.00 | 180 | 109 | 51 | 20 | 70.56 | 65.14 | 84.31 | 65.00 | 2.85 | -3.60 | 12.31 | 13.87 | 38.47 | 0.56 |
| 0.05-0.15 | 1 | none | 5.00 | 230 | 144 | 64 | 22 | 76.96 | 73.61 | 89.06 | 63.64 | 5.50 | 0.08 | 18.82 | 2.25 | 33.54 | 0.00 |
| 0.05-0.15 | 3 | after_adverse_0.02pct | 4.00 | 150 | 97 | 37 | 16 | 68.67 | 65.98 | 78.38 | 62.50 | 3.36 | -2.44 | 13.32 | 15.44 | 43.61 | 0.00 |
| 0.05-0.15 | 3 | after_adverse_0.02pct | 5.00 | 150 | 97 | 37 | 16 | 68.67 | 65.98 | 78.38 | 62.50 | 3.29 | -3.07 | 14.71 | 15.44 | 43.61 | 0.00 |
| 0.05-0.15 | 1 | after_adverse_0.02pct | 5.00 | 158 | 100 | 40 | 18 | 69.62 | 66.00 | 82.50 | 61.11 | 4.43 | -1.75 | 18.02 | 8.55 | 41.65 | 0.00 |

## Positive-P&L pockets with sample guards (still not 70% robust)

| band | entry_minute | filter | stop_multiplier | calls | train_2017_2023_calls | val_2024_2025_calls | confirm_2026_calls | win_rate | train_2017_2023_win_rate | val_2024_2025_win_rate | confirm_2026_win_rate | avg_pnl_pts | train_2017_2023_avg_pnl_pts | val_2024_2025_avg_pnl_pts | confirm_2026_avg_pnl_pts | mean_target_distance_pts | ambiguous_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.05-0.15 | 1 | none | 5.00 | 230 | 144 | 64 | 22 | 76.96 | 73.61 | 89.06 | 63.64 | 5.50 | 0.08 | 18.82 | 2.25 | 33.54 | 0.00 |
| 0.05-0.15 | 2 | none | 4.00 | 203 | 126 | 56 | 21 | 73.89 | 71.43 | 85.71 | 57.14 | 5.58 | 0.50 | 18.75 | 0.94 | 37.16 | 0.00 |
| 0.05-0.15 | 2 | none | 1.00 | 203 | 126 | 56 | 21 | 55.67 | 55.56 | 60.71 | 42.86 | 3.10 | 0.37 | 10.35 | 0.17 | 37.16 | 0.49 |

## Robust trade rules

None.

## Configuration

- Raw 1m root: `/home/user/historical/technovusin-nifty50-historical-data/1min`
- Bands: `0.02:0.10,0.03:0.12,0.05:0.15`
- Entry minutes: `0,1,2,3,5,10,15`
- Stop multiples: `0.75,1,1.5,2,2.5,3,4,5`
- Robust gate: train>=100, validation>=40, confirmation>=20, win-rate>=70.00%, and positive average points in each split.
- Same-minute target+stop: counted as stop/loss.

## Actionable interpretation

Keep V10 as a level-touch sniper alert.  Do **not** promote a standalone options trade until a broker/tick-level execution model survives slippage, spread, and stop tests.  A better next data step is real option-premium/tick data around these tiny-gap days, not more daily OI curve-fitting.
