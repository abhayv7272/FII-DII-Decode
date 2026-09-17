# V7 Intraday + Date-Stamped Institutional Levels

## Objective

Move beyond EOD/OI-only curve fitting by adding longer 15-minute candles and exact date-stamped NIFTY levels extracted from the supplied dated market-analysis PDF. The score is still honest: no same-day future candles are used to choose the level list; a signal waits for a 15-minute confirmation candle before it is counted.

## Data added

- 15-minute NIFTY candles: `historical/nifty_15m.csv`; 58,397 bars across 2,336 usable sessions from 2017-04-03 to 2026-09-17.
- Raw 1-minute archive was downloaded from `technovusin/nifty50-historical-data` via GitHub API and kept outside Git; the committed 15m derived file has a manifest beside it.
- Date-stamped levels: `historical/institutional_levels_pdf_2026.csv`; 140 manually audited level rows across 28 signal days; 60 rows explicitly tagged institutional/institutional-zone from the PDF wording.

## Main result

- Long 2017-2026 generic 15m price-rule sanity check found **0** rules clearing a 70% train/2025/2026 **post-entry** hit-rate gate with large-sample guards.
- PDF-level conditional branch grid found **0** variants clearing a 70% July-Aug train and Sep confirmation gate with minimum calls. This sample is necessarily small because exact supplied levels exist only for the dated PDF window.
- Therefore V7 builds the required stronger data path, but it still does **not** justify promoting a real 70%+ production decoder yet. The useful output is a forward-testable intraday gate, not a finished accuracy claim.

## Best generic 15m price sanity rules

| rule | direction | entry_col | calls | post_entry_hit_rate | post_entry_avg_signed_ret_pct | train_2017_2024_calls | train_2017_2024_post_hit_rate | val_2025_calls | val_2025_post_hit_rate | confirm_2026_calls | confirm_2026_post_hit_rate | oc_direction_hit_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gap_up_0.1_and_first15_up_0.15 | UP | first15_close | 262 | 52.29 | 0.03 | 230 | 50.87 | 14 | 57.14 | 18 | 66.67 | 75.97 |
| gap_pct_fade_lt_-0.5 | UP | open | 193 | 52.85 | 0.07 | 153 | 49.67 | 12 | 66.67 | 28 | 64.29 | 55.11 |
| gap_up_0.2_and_first15_up_0.15 | UP | first15_close | 205 | 52.20 | 0.03 | 183 | 51.91 | 11 | 45.45 | 11 | 63.64 | 74.86 |
| gap_up_0.2_and_first15_up_0.05 | UP | first15_close | 342 | 52.05 | -0.01 | 302 | 51.32 | 22 | 54.55 | 18 | 61.11 | 69.26 |
| gap_up_0.1_and_first15_up_0.1 | UP | first15_close | 334 | 53.59 | 0.02 | 288 | 52.43 | 23 | 60.87 | 23 | 60.87 | 74.09 |
| gap_up_0.1_and_first15_up_0.05 | UP | first15_close | 439 | 51.71 | -0.01 | 381 | 50.66 | 30 | 56.67 | 28 | 60.71 | 69.29 |
| first60_ret_pct_fade_gt_0.4 | DOWN | first60_close | 229 | 44.54 | -0.03 | 180 | 42.78 | 28 | 46.43 | 21 | 57.14 | 14.35 |
| gap_up_0.2_and_first15_up_0.1 | UP | first15_close | 262 | 53.05 | 0.01 | 230 | 52.61 | 18 | 55.56 | 14 | 57.14 | 73.00 |
| gap_pct_trend_gt_0.35 | UP | open | 628 | 46.97 | -0.09 | 562 | 46.26 | 34 | 50.00 | 32 | 56.25 | 48.74 |
| first60_ret_pct_fade_gt_0.2 | DOWN | first60_close | 543 | 41.44 | -0.04 | 435 | 39.54 | 61 | 44.26 | 47 | 55.32 | 18.76 |
| first60_ret_pct_fade_gt_0.3 | DOWN | first60_close | 355 | 41.69 | -0.05 | 282 | 40.43 | 42 | 40.48 | 31 | 54.84 | 15.29 |
| gap_up_0.05_and_first15_up_0.15 | UP | first15_close | 285 | 51.93 | 0.03 | 244 | 51.23 | 17 | 58.82 | 24 | 54.17 | 75.69 |
| gap_pct_fade_lt_-0.35 | UP | open | 285 | 51.23 | 0.05 | 222 | 48.65 | 24 | 70.83 | 39 | 53.85 | 54.65 |
| gap_up_0.05_and_first15_up_0.05 | UP | first15_close | 486 | 51.23 | -0.01 | 413 | 50.36 | 39 | 58.97 | 34 | 52.94 | 69.04 |
| first60_ret_pct_fade_gt_0.15 | DOWN | first60_close | 662 | 40.79 | -0.04 | 534 | 39.70 | 69 | 39.13 | 59 | 52.54 | 20.03 |

## Best PDF-level 15m confirmation variants

| variant | calls | post_entry_hit_rate | post_entry_avg_signed_ret_pct | train_jul_aug_calls | train_jul_aug_post_hit_rate | confirm_sep_calls | confirm_sep_post_hit_rate | oc_direction_n | oc_direction_hit_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first1_bars_touch5_buf10_all | 13 | 69.23 | 0.23 | 6 | 50.00 | 7 | 85.71 | 12 | 91.67 |
| first1_bars_touch0_buf10_all | 12 | 66.67 | 0.21 | 5 | 40.00 | 7 | 85.71 | 11 | 90.91 |
| first1_bars_touch5_buf0_all | 20 | 60.00 | 0.18 | 11 | 45.45 | 9 | 77.78 | 16 | 87.50 |
| first2_bars_touch5_buf0_all | 22 | 59.09 | 0.17 | 13 | 46.15 | 9 | 77.78 | 17 | 82.35 |
| first4_bars_touch5_buf0_all | 22 | 59.09 | 0.17 | 13 | 46.15 | 9 | 77.78 | 17 | 82.35 |
| first8_bars_touch5_buf0_all | 24 | 58.33 | 0.15 | 15 | 46.67 | 9 | 77.78 | 18 | 83.33 |
| first25_bars_touch5_buf0_all | 24 | 58.33 | 0.15 | 15 | 46.67 | 9 | 77.78 | 18 | 83.33 |
| first1_bars_touch0_buf0_all | 19 | 57.89 | 0.16 | 10 | 40.00 | 9 | 77.78 | 15 | 86.67 |
| first2_bars_touch0_buf0_all | 19 | 57.89 | 0.16 | 10 | 40.00 | 9 | 77.78 | 15 | 86.67 |
| first8_bars_touch0_buf10_all | 23 | 56.52 | 0.06 | 14 | 42.86 | 9 | 77.78 | 18 | 77.78 |
| first8_bars_touch5_buf10_all | 23 | 56.52 | 0.06 | 14 | 42.86 | 9 | 77.78 | 18 | 77.78 |
| first4_bars_touch0_buf0_all | 20 | 55.00 | 0.15 | 11 | 36.36 | 9 | 77.78 | 16 | 87.50 |
| first4_bars_touch5_buf10_all | 22 | 54.55 | 0.06 | 13 | 38.46 | 9 | 77.78 | 17 | 76.47 |
| first8_bars_touch0_buf0_all | 24 | 54.17 | 0.11 | 15 | 40.00 | 9 | 77.78 | 18 | 83.33 |
| first25_bars_touch0_buf0_all | 24 | 54.17 | 0.11 | 15 | 40.00 | 9 | 77.78 | 18 | 83.33 |
| first25_bars_touch0_buf10_all | 24 | 54.17 | 0.04 | 15 | 40.00 | 9 | 77.78 | 18 | 77.78 |
| first25_bars_touch5_buf10_all | 24 | 54.17 | 0.05 | 15 | 40.00 | 9 | 77.78 | 18 | 77.78 |
| first4_bars_touch0_buf10_all | 20 | 50.00 | 0.04 | 11 | 27.27 | 9 | 77.78 | 16 | 75.00 |
| first1_bars_touch10_buf10_all | 16 | 62.50 | 0.15 | 8 | 50.00 | 8 | 75.00 | 14 | 78.57 |
| first1_bars_touch5_buf5_all | 17 | 58.82 | 0.18 | 9 | 44.44 | 8 | 75.00 | 14 | 85.71 |

## V3 OI agreement overlay

| variant | calls | post_entry_hit_rate | train_jul_aug_calls | train_jul_aug_post_hit_rate | confirm_sep_calls | confirm_sep_post_hit_rate |
| --- | --- | --- | --- | --- | --- | --- |
| first25_bars_touch10_buf0_inst | 3 | 66.67 | 2 | 100.00 | 1 | 0.00 |
| first25_bars_touch15_buf0_inst | 3 | 66.67 | 2 | 100.00 | 1 | 0.00 |
| first25_bars_touch25_buf0_inst | 3 | 66.67 | 2 | 100.00 | 1 | 0.00 |
| first25_bars_touch0_buf0_inst | 2 | 50.00 | 1 | 100.00 | 1 | 0.00 |
| first25_bars_touch0_buf5_inst | 4 | 50.00 | 3 | 66.67 | 1 | 0.00 |
| first25_bars_touch5_buf0_inst | 2 | 50.00 | 1 | 100.00 | 1 | 0.00 |
| first25_bars_touch5_buf5_inst | 4 | 50.00 | 3 | 66.67 | 1 | 0.00 |
| first25_bars_touch10_buf5_inst | 4 | 50.00 | 3 | 66.67 | 1 | 0.00 |
| first25_bars_touch15_buf5_inst | 4 | 50.00 | 3 | 66.67 | 1 | 0.00 |
| first25_bars_touch25_buf5_inst | 4 | 50.00 | 3 | 66.67 | 1 | 0.00 |
| first25_bars_touch0_buf10_inst | 5 | 40.00 | 4 | 50.00 | 1 | 0.00 |
| first25_bars_touch5_buf10_inst | 5 | 40.00 | 4 | 50.00 | 1 | 0.00 |
| first25_bars_touch10_buf10_inst | 5 | 40.00 | 4 | 50.00 | 1 | 0.00 |
| first25_bars_touch15_buf10_inst | 5 | 40.00 | 4 | 50.00 | 1 | 0.00 |
| first25_bars_touch25_buf10_inst | 5 | 40.00 | 4 | 50.00 | 1 | 0.00 |

## How to interpret this for real trading research

1. A level signal is counted only after the 15m candle range touches/overlaps a published level and its close confirms a branch above/below that level.
2. `post_entry_hit_rate` uses close after the trigger to day close, with a minimum signed move of 0.05% to avoid marking tiny/noisy drifts as wins.
3. `oc_direction_hit_rate` is the old open-to-close day direction score; it is reported separately because a conditional level trade can be right after the trigger even when the whole day's open-to-close class is misleading.
4. The PDF-level result cannot be called statistically robust until new exact levels are collected daily and walked forward. Use it as a forward-watch gate.

## Next implementation step

Add a daily `data/institutional_levels/YYYY-MM-DD.json` ingestion path for externally supplied exact levels, then append the next session's 15m bars and score this V7 gate forward without changing thresholds.