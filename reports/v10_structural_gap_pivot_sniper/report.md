# V10 Structural Gap/Pivot Sniper Research

## Verdict

**HIGH-ACCURACY LEVEL-TOUCH EDGE FOUND (selective, not daily close direction).**

The strongest leak-safe pocket is an at-open tiny-gap-fill signal: if NIFTY opens only a tiny distance from the previous close, predict that the previous close will be touched intraday.

Top robust rule: `abs_gap_0.03_0.12_both_fill_prev_close`
- Calls: 393
- Overall hit-rate: 90.33%
- Train 2017-2023: 257 calls, 89.11%
- Validation 2024-2025: 104 calls, 94.23%
- Confirmation 2026: 32 calls, 87.50%
- Mean target distance: 12.99 NIFTY points

This reaches the requested 75-85%+ accuracy band for a narrowly-defined, real-world next-session **level touch** prediction. It does **not** solve unconditional next-day UP/DOWN close prediction.

## Guardrails / no leakage

- Signal uses only values known at the open: current open, previous close/high/low, and pivots derived from the previous session.
- The label is whether the target level is touched later during the same session.
- No current-session close-to-close return, full-day range, future OI, or future candle is used as a feature.
- For execution diagnostics, if a 1-minute bar hits target and stop in the same minute, it is counted as a stop/loss.

## Top structural rules

| family | rule | direction | target | calls | hit_rate | train_2017_2023_calls | val_2024_2025_calls | confirm_2026_calls | train_2017_2023_hit_rate | val_2024_2025_hit_rate | confirm_2026_hit_rate | mean_abs_gap_pts | median_abs_gap_pts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gap_fill | abs_gap_0.01_0.05_up_fill_prev_close | DOWN | previous_close_touch_intraday | 104 | 96.15 | 80 | 20 | 4 | 97.50 | 90.00 | 100.00 | 5.02 | 4.20 |
| gap_fill | abs_gap_0.03_0.12_up_fill_prev_close | DOWN | previous_close_touch_intraday | 238 | 94.12 | 164 | 55 | 19 | 94.51 | 92.73 | 94.74 | 12.96 | 11.65 |
| gap_fill | abs_gap_0.02_0.10_up_fill_prev_close | DOWN | previous_close_touch_intraday | 203 | 95.07 | 143 | 44 | 16 | 97.20 | 88.64 | 93.75 | 10.27 | 8.60 |
| gap_fill | abs_gap_0.03_0.12_both_fill_prev_close | FADE_GAP | previous_close_touch_intraday | 393 | 90.33 | 257 | 104 | 32 | 89.11 | 94.23 | 87.50 | 12.99 | 11.60 |
| gap_fill | abs_gap_0.05_0.15_up_fill_prev_close | DOWN | previous_close_touch_intraday | 262 | 90.08 | 177 | 63 | 22 | 90.40 | 90.48 | 86.36 | 17.68 | 16.25 |
| gap_fill | abs_gap_0.02_0.10_both_fill_prev_close | FADE_GAP | previous_close_touch_intraday | 351 | 91.17 | 231 | 93 | 27 | 91.34 | 92.47 | 85.19 | 10.22 | 8.30 |
| previous_day_level_reach | open_below_prev_close_reach_prev_low | DOWN | previous_low_touch_intraday | 788 | 72.84 | 500 | 199 | 89 | 72.20 | 69.85 | 83.15 |  |  |
| gap_fill | abs_gap_0.01_0.05_both_fill_prev_close | FADE_GAP | previous_close_touch_intraday | 204 | 90.20 | 146 | 47 | 11 | 89.73 | 93.62 | 81.82 | 4.92 | 4.38 |
| pivot_reach | open_below_pivot_reach_s1 | DOWN | s1_touch_intraday | 855 | 71.93 | 565 | 201 | 89 | 72.74 | 65.67 | 80.90 |  |  |
| gap_fill | abs_gap_0.05_0.15_both_fill_prev_close | FADE_GAP | previous_close_touch_intraday | 428 | 87.15 | 265 | 122 | 41 | 85.28 | 93.44 | 80.49 | 18.25 | 16.85 |
| gap_fill | abs_gap_0.03_0.12_down_fill_prev_close | UP | previous_close_touch_intraday | 155 | 84.52 | 93 | 49 | 13 | 79.57 | 95.92 | 76.92 | 13.04 | 11.50 |
| gap_fill | abs_gap_0.05_0.20_up_fill_prev_close | DOWN | previous_close_touch_intraday | 407 | 86.98 | 276 | 102 | 29 | 87.68 | 88.24 | 75.86 | 21.91 | 20.20 |
| gap_fill | abs_gap_0.05_0.15_down_fill_prev_close | UP | previous_close_touch_intraday | 166 | 82.53 | 88 | 59 | 19 | 75.00 | 96.61 | 73.68 | 19.15 | 18.10 |
| gap_fill | abs_gap_0.02_0.10_down_fill_prev_close | UP | previous_close_touch_intraday | 148 | 85.81 | 88 | 49 | 11 | 81.82 | 95.92 | 72.73 | 10.15 | 8.15 |
| gap_fill | abs_gap_0.05_0.20_both_fill_prev_close | FADE_GAP | previous_close_touch_intraday | 631 | 84.47 | 407 | 169 | 55 | 83.29 | 91.12 | 72.73 | 21.84 | 20.25 |
| pivot_reach | open_above_pivot_reach_r1 | UP | r1_touch_intraday | 1490 | 72.21 | 1107 | 296 | 87 | 73.53 | 67.23 | 72.41 |  |  |
| previous_day_level_reach | open_above_prev_close_reach_prev_high | UP | previous_high_touch_intraday | 1555 | 70.10 | 1171 | 297 | 87 | 70.88 | 66.33 | 72.41 |  |  |
| gap_fill | abs_gap_0.01_0.05_down_fill_prev_close | UP | previous_close_touch_intraday | 100 | 84.00 | 66 | 27 | 7 | 80.30 | 96.30 | 71.43 | 4.82 | 4.41 |
| gap_fill | abs_gap_0.05_0.20_down_fill_prev_close | UP | previous_close_touch_intraday | 224 | 79.91 | 131 | 67 | 26 | 74.05 | 95.52 | 69.23 | 21.72 | 20.30 |
| gap_fill | abs_gap_0.10_0.20_down_fill_prev_close | UP | previous_close_touch_intraday | 147 | 76.19 | 90 | 39 | 18 | 70.00 | 94.87 | 66.67 | 25.67 | 25.25 |

## Robust 70%+ rules

| family | rule | direction | target | calls | hit_rate | train_2017_2023_calls | val_2024_2025_calls | confirm_2026_calls | train_2017_2023_hit_rate | val_2024_2025_hit_rate | confirm_2026_hit_rate | mean_abs_gap_pts | median_abs_gap_pts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gap_fill | abs_gap_0.03_0.12_both_fill_prev_close | FADE_GAP | previous_close_touch_intraday | 393 | 90.33 | 257 | 104 | 32 | 89.11 | 94.23 | 87.50 | 12.99 | 11.60 |
| gap_fill | abs_gap_0.02_0.10_both_fill_prev_close | FADE_GAP | previous_close_touch_intraday | 351 | 91.17 | 231 | 93 | 27 | 91.34 | 92.47 | 85.19 | 10.22 | 8.30 |
| gap_fill | abs_gap_0.05_0.15_both_fill_prev_close | FADE_GAP | previous_close_touch_intraday | 428 | 87.15 | 265 | 122 | 41 | 85.28 | 93.44 | 80.49 | 18.25 | 16.85 |
| gap_fill | abs_gap_0.05_0.20_up_fill_prev_close | DOWN | previous_close_touch_intraday | 407 | 86.98 | 276 | 102 | 29 | 87.68 | 88.24 | 75.86 | 21.91 | 20.20 |
| gap_fill | abs_gap_0.05_0.20_both_fill_prev_close | FADE_GAP | previous_close_touch_intraday | 631 | 84.47 | 407 | 169 | 55 | 83.29 | 91.12 | 72.73 | 21.84 | 20.25 |

## 1-minute execution diagnostic

The high hit-rate is a level-touch probability. Because the target is small, a naive at-open trade can be fragile. The table below uses raw 1-minute candles, enters at the open, targets previous close, and places a stop at 1x/2x/3x the target distance. Same-minute target+stop is counted as a loss.

| rule | stop_multiplier | calls | level_touch_rate | trade_win_rate_conservative | ambiguous_rate | mean_target_distance_pts | train_2017_2023_calls | val_2024_2025_calls | confirm_2026_calls | train_2017_2023_trade_win_rate | val_2024_2025_trade_win_rate | confirm_2026_trade_win_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| abs_gap_0.02_0.10_both_fill_prev_close | 1.00 | 351 | 91.17 | 37.89 | 25.93 | 10.22 | 231 | 93 | 27 | 39.83 | 32.26 | 40.74 |
| abs_gap_0.02_0.10_both_fill_prev_close | 2.00 | 351 | 91.17 | 54.70 | 15.38 | 10.22 | 231 | 93 | 27 | 55.41 | 54.84 | 48.15 |
| abs_gap_0.02_0.10_both_fill_prev_close | 3.00 | 351 | 91.17 | 65.81 | 9.97 | 10.22 | 231 | 93 | 27 | 63.64 | 70.97 | 66.67 |
| abs_gap_0.03_0.12_both_fill_prev_close | 1.00 | 393 | 90.33 | 43.26 | 17.56 | 12.99 | 257 | 104 | 32 | 45.53 | 37.50 | 43.75 |
| abs_gap_0.03_0.12_both_fill_prev_close | 2.00 | 393 | 90.33 | 61.32 | 9.41 | 12.99 | 257 | 104 | 32 | 60.31 | 66.35 | 53.12 |
| abs_gap_0.03_0.12_both_fill_prev_close | 3.00 | 393 | 90.33 | 71.25 | 6.11 | 12.99 | 257 | 104 | 32 | 67.70 | 80.77 | 68.75 |
| abs_gap_0.05_0.15_both_fill_prev_close | 1.00 | 428 | 87.15 | 48.83 | 7.48 | 18.25 | 265 | 122 | 41 | 51.32 | 46.72 | 39.02 |
| abs_gap_0.05_0.15_both_fill_prev_close | 2.00 | 428 | 87.15 | 66.36 | 3.04 | 18.25 | 265 | 122 | 41 | 64.91 | 74.59 | 51.22 |
| abs_gap_0.05_0.15_both_fill_prev_close | 3.00 | 428 | 87.15 | 75.23 | 1.40 | 18.25 | 265 | 122 | 41 | 71.70 | 87.70 | 60.98 |

Conclusion: promote the tiny-gap signal as a high-probability level-touch alert / context feature first. A production trading rule still needs tick-level or broker-level execution testing, slippage, option premium behavior, and a stop/exit model.

## Files

- `structural_rules.csv` — all tested structural level-touch summaries.
- `robust_rules.csv` — rules passing split/sample/hit-rate gates.
- `yearly_breakdown.csv` — yearly hit rates for each structural rule.
- `gap_fill_signals.csv` — individual signals for the default 0.02%-0.10% absolute-gap rule.
- `gap_fill_execution_1m.csv` and `gap_fill_execution_summary.csv` — optional raw-1m execution diagnostics when raw 1m data is available outside Git.

## Configuration

- Intraday bars: `historical/nifty_15m.csv`
- Raw 1m root for optional execution diagnostics: `/home/user/historical/technovusin-nifty50-historical-data/1min`
- Robust gate: train>=100, validation>=40, confirmation>=25, hit-rate>=70.00% in each split
