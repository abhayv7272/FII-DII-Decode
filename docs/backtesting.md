# Historical backtesting

The repository includes a point-in-time replay harness for the decoder's **next-session** OI class. Frozen v1 and transcript-grounded v2 are compared on 757 real sessions in [`reports/backtest_v2_2023-08_to_2026-09/report.md`](../reports/backtest_v2_2023-08_to_2026-09/report.md). V2 improves some historical diagnostics but remains below the majority-class baseline and approximately chance on the executable next-open-to-close basis, so it remains experimental. The bulky raw archive is not vendored; a compact research bundle is now committed under [`historical/`](../historical/) and the pinned source revision/checksums are retained with the reports.

## What is scored

For every eligible signal date **D**:

1. Load participant OI from D.
2. Load participant OI from the **exact previous session in the supplied OHLC calendar**.
3. Load the option-chain snapshot dated D, if one exists.
4. Run the normal `decode()` and `build_predictions()` pipeline.
5. Compare the call with the next market session's close-to-close index return.

This avoids two common sources of look-ahead bias:

- a missing OI file is not replaced silently by a file from several sessions ago;
- a current option chain or cash API response is never applied to an old date.

Historical cash flow is not part of replay because the project does not collect dated cash snapshots. V2 may display live current-session cash as confirmation, but it gives that input zero score weight so live behavior cannot silently become an unvalidated variant.

## Inputs

### 1. Participant OI

`--participant-oi` accepts any one of:

- a directory containing raw NSE files named `fao_participant_oi_DDMMYYYY.csv`;
- a ZIP containing those files;
- a consolidated CSV such as `data/participant_oi.csv`, with a `date` column and one row per date/participant.

The required participants are Client, FII, and Pro. DII is optional for direction because its configured weight is zero.

### 2. Index OHLC

`--ohlc` accepts a consolidated daily CSV, a ZIP, or a directory of raw NSE `ind_close_all_YYYYMMDD.csv` files. For a consolidated file, `Date` and `Close` are required; `Open`, `High`, and `Low` are strongly recommended. Common NSE headings such as `Index Date`, `Open Index Value`, `TIMESTAMP`, `OPEN`, `HIGH`, `LOW`, and `CLOSE` are recognised case-insensitively. When all-index archive files are supplied, the requested `--symbol` row is selected from every date automatically.

A minimal file is:

```csv
date,symbol,open,high,low,close
2026-08-03,NIFTY,24780,24960,24690,24890
2026-08-04,NIFTY,24910,25040,24750,24980
```

Close-only data can produce direction metrics, but gap and institutional-level reaction observations will remain unscored.

### 3. Option-chain snapshots (optional)

`--option-chains` accepts a directory or ZIP of raw NSE option-chain JSON. Every filename must contain its snapshot date in one of these forms:

- `NIFTY_2026-08-03.json`
- `option_chain_NIFTY_20260803.json`
- `option_chain_NIFTY_03082026.json`

A timestamp inside `records.timestamp` is also accepted when the filename has no date. The JSON must retain the raw `records.data` structure. A current snapshot must **never** be renamed and reused for historical dates.

## Run

From a virtual environment with the requirements installed:

```bash
python backtest.py \
  --participant-oi historical/participant_oi/ \
  --ohlc historical/nifty_ohlc.csv \
  --option-chains historical/option_chain/ \
  --symbol NIFTY \
  --decoder-version v2 \
  --output-dir reports/backtest
```

Equivalent package command:

```bash
PYTHONPATH=src python -m fiidii.cli backtest \
  --participant-oi historical/participant_oi.zip \
  --ohlc historical/nifty_ohlc.csv \
  --option-chains historical/option_chains.zip \
  --decoder-version v2
```

Useful controls:

```text
--decoder-version v1|v2|v3        # v2 is production default; v3 is opt-in candidate
--flat-threshold-pct 0.15          # ±0.15% is FLAT (inclusive)
--level-touch-tolerance-pct 0.05  # range may come within ±0.05% of a level
--from-date 2025-01-01
--to-date 2025-12-31
```

Percent arguments are percentage points: `0.15` means 0.15%, not 15%.

## V4 psychology search harness

`research/v4_psychology_search.py` is a research-only harness for aggressive
accuracy hunting. It builds on `research/v3_features.py` and the compact
`historical/` bundle, then tests 4/7/15/21-session participant psychology,
Pro/FII/Client/DII positioning levels, option-chain aggregate levels, gap and
volatility proxies, and frozen-on-development ML. The search is deliberately
strict: thresholds and orientations come from 2023-2024 only, while 2025 and
2026 remain holdouts.

```bash
# Requires optional research deps: scipy and scikit-learn
python research/v4_psychology_search.py --out reports/v4_psychology_search
```

The published run exports `threshold_rules.csv` and ranked holdout views in
[`reports/v4_psychology_search/`](../reports/v4_psychology_search/). It did not
find any rule that honestly reached the requested 75-85% zone on both holdouts
with minimum sample guards.

`research/v5_holdout_combo_meta.py` continues the hunt by fitting rules on
2023-2025 and reserving 2026 as the final holdout. It also tests voting-rule
combinations, a leakage-guarded v3 meta-gate, and whatever recent NIFTY 1-minute
intraday file is available:

```bash
python research/v5_holdout_combo_meta.py --out reports/v5_holdout_combo_meta
```

The published v5 run again rejects promotion: no ≥75% exact rule/combination
survived 2026 with ≥20 calls, and no leakage-guarded v3 meta-gate exceeded 70%
precision with ≥20 holdout calls.

`research/v6_realworld_selective_search.py` adds pair/conjunction tests and a
long price-only regime search:

```bash
python research/v6_realworld_selective_search.py --out reports/v6_realworld_selective
```

It checks whether two independent OI/psychology rules agreeing, or 10+ years of
NIFTY price history, can create a practical high-precision next-day filter. The
published run rejects that too: 319,600 pairs and 2,562 price-only rules produced
no robust ≥75% holdout result with minimum sample guards.

## Direction labels and metrics

Prediction classes are normalised as follows:

| Engine output | Backtest class |
|---|---|
| UP, SIDEWAYS-UP | UP |
| RANGE | FLAT |
| DOWN, SIDEWAYS-DOWN | DOWN |

Actual class for next-session return `r` and flat threshold `t`:

- UP when `r > t`;
- DOWN when `r < -t`;
- FLAT otherwise (boundaries included).

The report provides:

- exact three-class accuracy;
- UP/DOWN directional hit rate and directional coverage;
- UP, FLAT, and DOWN precision, recall, and F1;
- actual-vs-predicted confusion matrix;
- majority-class baseline;
- fixed setup-strength buckets with mean displayed strength and realised accuracy (v2 retains the `confidence` field only for API compatibility; it is not a calibrated probability);
- decoder method version, actionability state, and trigger-eligible subset diagnostics;
- mean/median next-session return by predicted class;
- institutional support/resistance reaction accuracy using a clearly labelled daily-bar proxy.

A directional UP/DOWN call followed by a FLAT actual session is counted as a directional miss. This prevents the hit rate from being inflated by dropping inconvenient low-movement outcomes.

### Level-reaction proxy

For the immediate support and resistance generated from date-D option chain:

- a test occurs when next-session daily range intersects the configured tolerance band;
- support succeeds if that session closes at or above support;
- resistance succeeds if it closes at or below resistance.

Daily OHLC cannot reveal whether the touch happened before or after a gap, whether volume confirmed it, or whether a 15-minute close/retest occurred. Therefore this is **not** presented as intraday level-reaction accuracy.

## Outputs

The output directory contains:

| File | Contents |
|---|---|
| `report.md` | human-readable methodology, metrics, data quality, and limitations |
| `predictions.csv` | one auditable row per signal and target session |
| `metrics.json` | machine-readable configuration and all aggregate metrics |
| `confidence_curve.csv` | confidence-vs-accuracy buckets |
| `skipped.csv` | every rejected signal date and the exact reason |

If there are no evaluable signals, the command still writes artifacts but explicitly reports **no accuracy**.

## Forward-test collection

Live weekday runs already save participant OI and dated option-chain snapshots. They now also append the current NIFTY session bar to `data/index_ohlc.csv` when NSE's all-indices response provides it. The runner refuses to stamp current cash/option-chain/quote data onto an older fallback OI date.

After enough genuine sessions have accumulated:

```bash
python backtest.py \
  --participant-oi data/participant_oi.csv \
  --ohlc data/index_ohlc.csv \
  --option-chains data/option_chain
```

Do not draw conclusions from a handful of observations. Report the sample size, date range, flat threshold, missing-date counts, and baseline alongside every accuracy figure.

## Reproduce the published 757-session run

The published audit used a third-party GitHub mirror of raw NSE archive-shaped reports, pinned to commit `7d481cf1fcffe44be68852892028195c4f12dddd`. The raw files are intentionally not vendored here. Fetch only the two required directories:

```bash
git clone --filter=blob:none --no-checkout --depth=1 \
  https://github.com/sahilempire/groww-market-data.git /tmp/groww-market-data
cd /tmp/groww-market-data
git sparse-checkout init --cone
git sparse-checkout set nse_archives/participant_oi nse_archives/index_close
git fetch --depth=1 origin 7d481cf1fcffe44be68852892028195c4f12dddd
git checkout 7d481cf1fcffe44be68852892028195c4f12dddd
```

Then, from this repository, reproduce the frozen v1 audit:

```bash
python backtest.py \
  --participant-oi /tmp/groww-market-data/nse_archives/participant_oi \
  --ohlc /tmp/groww-market-data/nse_archives/index_close \
  --decoder-version v1 \
  --flat-threshold-pct 0.15 \
  --output-dir /tmp/reproduced-v1
```

Its primary close-to-close metrics are 757 signals, 36.20% exact three-class accuracy, and 42.61% directional-call hit rate with realised FLAT outcomes counted as misses.

Reproduce the complete chronological v1/v2 and five-session comparison:

```bash
PYTHONPATH=src python research/compare_v1_v2.py \
  --participant-oi /tmp/groww-market-data/nse_archives/participant_oi \
  --ohlc /tmp/groww-market-data/nse_archives/index_close \
  --output-dir /tmp/reproduced-v2-comparison \
  --source-note "Public mirror pinned at 7d481cf1fcffe44be68852892028195c4f12dddd"
```

The v2 full close-to-close exact result should be 37.91%, versus v1's 36.20% and the 42.14% majority baseline. Compare aggregate source hashes in the published v1 `provenance.json` before treating a mismatch as a code regression. Direct NSE TLS was unavailable in the build sandbox, so the mirror limitation is part of the disclosed result.

## Reproduce the level-enabled 757-session run (bhavcopy-derived option chains)

Public archives do not publish historical option-chain JSON, so the level proxy
was blank in the earlier audits. `research/bhavcopy_to_option_chain.py` rebuilds
an EOD-equivalent snapshot per trading date from the NSE F&O bhavcopy archive.

Fetch the three required directories from the same pinned mirror:

```bash
git clone --filter=blob:none --no-checkout --depth=1 \
  https://github.com/sahilempire/groww-market-data.git /tmp/groww-market-data
cd /tmp/groww-market-data
git sparse-checkout init --cone
git sparse-checkout set nse_archives/participant_oi nse_archives/index_close nse_archives/fo_bhavcopy
git fetch --depth=1 origin 7d481cf1fcffe44be68852892028195c4f12dddd
git checkout 7d481cf1fcffe44be68852892028195c4f12dddd
```

Build the snapshots (about 760 files, ~3.5 minutes), then replay:

```bash
python research/bhavcopy_to_option_chain.py \
  --bhavcopy-dir /tmp/groww-market-data/nse_archives/fo_bhavcopy \
  --index-close-dir /tmp/groww-market-data/nse_archives/index_close \
  --output-dir /tmp/option_chain_hist

python backtest.py \
  --participant-oi /tmp/groww-market-data/nse_archives/participant_oi \
  --ohlc /tmp/groww-market-data/nse_archives/index_close \
  --option-chains /tmp/option_chain_hist \
  --output-dir reports/backtest_v2_levels_2023-08_to_2026-09
```

Published result (`reports/backtest_v2_levels_2023-08_to_2026-09/`):

| Metric | Result |
|---|---:|
| Evaluable signals | 757 (option chain matched on all 757) |
| Exact 3-class accuracy | 37.91% (baseline 42.14%) |
| Directional hit rate | 43.72% |
| Level tests (±0.05% band) | 685, 49.20% hold |
| Support | 346 tests, 46.82% hold |
| Resistance | 339 tests, 51.62% hold |

Direction metrics are unchanged from the chain-less run, which is the expected
control: the locked v2 score does not consume levels. The new information is the
level-reaction proxy — and at roughly a coin flip it provides **no evidence of a
tradable level edge**.

### Converter limitations (must be quoted with any level number)

* Bhavcopy carries EOD close/settlement, not a 15:30 LTP; implied volatility is
  absent and emitted as `0`.
* `underlyingValue` is the same-date Nifty 50 close, not the snapshot-time spot.
* Only the nearest non-expired expiry is emitted, mirroring the live fetcher's
  `records.expiryDates[0]` behaviour.
* Daily OHLC cannot verify 10-15 minute candle confirmation, sweep-then-reclaim,
  touch sequencing, stops, or slippage. These are **daily proxy** numbers, not
  trade simulation results.

## V7 intraday + exact dated-level gate

After V4/V5/V6 failed to produce a robust EOD/OI-only 75%+ edge, the next path
adds the missing execution-time data:

- `historical/nifty_15m.csv` — 15-minute NIFTY candles derived from the public
  `technovusin/nifty50-historical-data` 1-minute archive. Raw 1-minute files are
  kept outside Git; `historical/nifty_15m.csv.manifest.json` records upstream
  files, hashes, and the builder script.
- `historical/institutional_levels_pdf_2026.csv` — 140 manually audited,
  date-stamped NIFTY levels from the supplied 2026 market-analysis PDF. Rows are
  tagged as institutional when the PDF wording calls them institutional or
  institutional-zone levels; otherwise they remain technical/psychological/
  option-chain levels.
- `research/v7_intraday_institutional_levels.py` — scores generic 15m rules over
  2017-2026 and scores PDF-level 15m confirmation branches over the dated level
  window.

Run:

```bash
.venv/bin/python research/build_intraday_candles.py \
  --raw-root /home/user/historical/technovusin-nifty50-historical-data/1min \
  --interval 15 \
  --out historical/nifty_15m.csv

.venv/bin/python research/v7_intraday_institutional_levels.py \
  --out reports/v7_intraday_institutional_levels
```

Published V7 result:

| Check | Result |
|---|---:|
| 15m bars loaded | 58,397 |
| Usable sessions | 2,336 (2017-04-03 to 2026-09-17) |
| PDF level rows | 140 across 28 signal days |
| Explicit institutional-level rows | 60 |
| Generic 15m rules clearing 70% train/2025/2026 **post-entry** gate | 0 |
| PDF-level variants clearing 70% July-Aug/Sep **post-entry** gate | 0 |

Important scoring distinction: many first-15/30/60-minute momentum filters show
70%+ **open-to-close** direction because the measured day already includes the
first move. V7 therefore treats the candle close as the earliest entry and uses
signal-close-to-day-close `post_entry_hit_rate` as the main honest metric. That
post-entry edge did **not** clear the 70% gate. The best PDF-level first-candle
branches reached high September-only rates on small samples, but failed the
July-Aug training split, so they are forward-watch tags only.

## V8 10/15-minute trade-level simulator

V8 tests whether the intraday confirmation idea becomes useful when measured as
an executable trade instead of a day-label prediction. It enters only after the
confirmation window has closed and simulates symmetric percentage target/stop
orders on the remaining bars. Ambiguous OHLC bars that touch target and stop in
the same candle are counted as losses.

Run:

```bash
.venv/bin/python research/build_intraday_candles.py \
  --raw-root /home/user/historical/technovusin-nifty50-historical-data/1min \
  --interval 10 \
  --out historical/nifty_10m.csv

.venv/bin/python research/v8_intraday_trade_sim.py \
  --out reports/v8_intraday_trade_sim
```

Published V8 result:

| Check | Result |
|---|---:|
| 10m bars loaded | 88,764 |
| 15m bars loaded | 58,397 |
| Usable sessions | 2,336 |
| Generic first-window rule grid summaries | 980 |
| PDF-level trade rule grid summaries | 1,680 |
| Generic trade rules clearing 70% train/2025/2026 gate | 0 |
| PDF-level trade rules clearing 70% July-Aug/Sep gate | 0 |

The best 2026-looking generic pockets were downside first-window continuation
rules around 70-71% in the 2026 slice, but their 2017-2024 and/or 2025 win rates
were near 50-61%, so they are regime-specific, not robust. The best PDF-level
pockets again showed 100% on only 2-3 September trades while losing in the
July-Aug training split; they are not promotable.

## V9 OI + intraday confirmation

V9 retests the core FII/DII/Pro/Client idea after adding long intraday data. It
combines the prior-day v3 OI lean with next-session first 10/15/30/60-minute
confirmation and enters only after that candle closes. Execution again uses
symmetric target/stop percentages and counts ambiguous target+stop candles as
losses.

Run:

```bash
PYTHONPATH=research .venv/bin/python research/v9_oi_intraday_confirmation.py \
  --out reports/v9_oi_intraday_confirmation
```

Published V9 result:

| Check | Result |
|---|---:|
| V3 OI predictions tested | 757 |
| Trade candidates generated | 2,274,684 |
| Rule summaries checked | 29,568 |
| Split | train 2023-2024 / validation 2025 / confirmation 2026 |
| Rules clearing strict 70% win-rate gate | 0 |

The best 2026-only OI+intraday pockets were tiny (often 4-8 confirmation calls)
and failed the older train/validation windows. Therefore first-candle
confirmation does not currently convert the OI lean into a robust executable
70%+ edge.

## V10 Structural gap/pivot sniper

V10 switches from unconditional daily direction to a narrower, trader-style
level-touch question: after the NIFTY cash open is known, will a nearby structural
level be touched intraday?  The high-accuracy pocket is the ultra-small-gap fill:
if the open is only a tiny distance from the previous close, predict that the
previous close will be touched in the same session.

Run:

```bash
PYTHONPATH=research .venv/bin/python research/v10_structural_gap_pivot_sniper.py \
  --out reports/v10_structural_gap_pivot_sniper
```

Published V10 result:

| Check | Result |
|---|---:|
| Daily intraday sessions | 2,346 |
| Date range | 2017-04-03 to 2026-09-17 |
| Structural rules tested | 31 |
| Rules clearing 70% train/validation/confirmation gate | 5 |
| Best rule | `abs_gap_0.03_0.12_both_fill_prev_close` |
| Best rule calls / overall hit-rate | 393 / **90.33%** |
| Train 2017-2023 | 257 calls / **89.11%** |
| Validation 2024-2025 | 104 calls / **94.23%** |
| Confirmation 2026 | 32 calls / **87.50%** |

Interpretation: this finally reaches the requested 75-85%+ accuracy range, but
only for a selective **previous-close level-touch** prediction available after the
open, not for an every-day next-close UP/DOWN forecast.  The rule says:

- if the gap is up by 0.03%-0.12%, target a touch of previous close downward;
- if the gap is down by 0.03%-0.12%, target a touch of previous close upward;
- otherwise no V10 tiny-gap sniper signal.

`src/fiidii/gap_sniper.py` exposes this as
`tiny_gap_fill_signal(open_price, previous_close)`.  The normal report now carries
a V10 opening-sniper playbook/status block, and the manual CLI can evaluate a
live open directly:

```bash
PYTHONPATH=src python -m fiidii.cli sniper \
  --open 23020 --previous-close 23000 --high 23025 --low 22998
```

V10 also writes optional raw-1m execution diagnostics when the raw Technovusin
archive is available outside Git.  Those diagnostics are deliberately
conservative: entry at open, target previous close, stop at 1x/2x/3x target
distance, and same-minute target+stop counted as a loss.  The high level-touch
hit-rate does **not** by itself validate a production options trade because the
average target is only ~13 NIFTY points and execution/slippage dominate.

## V11 Gap-sniper execution audit

V11 asks whether the V10 tiny-gap level-touch edge can be converted into a simple
production trade.  It uses raw 1-minute candles, enters at the open or after
1/2/3/5/10/15 minutes if the previous-close target has not already touched, and
tests stops from 0.75x to 5x of the remaining target distance.  If a one-minute
candle touches both target and stop, it is counted as a loss.

Run:

```bash
PYTHONPATH=research .venv/bin/python research/v11_gap_sniper_execution.py \
  --out reports/v11_gap_sniper_execution
```

Published V11 result:

| Check | Result |
|---|---:|
| Raw 1m rows | 877,729 |
| Date range | 2017-04-03 to 2026-09-17 |
| Trade candidates generated | 64,776 |
| Execution rule summaries | 768 |
| Robust 70% + positive-P&L trade rules | **0** |

The highest win-rate pockets use very wide stops (4x-5x the tiny target).  They
can show 77-83% win-rate, but lose average points in one or more splits.  Example:
0.03%-0.12% gap, entry at open, 5x stop had 82.70% overall win-rate but negative
average points in train and 2026 confirmation.  Therefore V10 remains a
high-probability **level-touch alert**, not a standalone options trade.
