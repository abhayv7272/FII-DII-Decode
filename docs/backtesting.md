# Historical backtesting

The repository includes a point-in-time replay harness for the decoder's **next-session** OI class. Frozen v1 and transcript-grounded v2 are compared on 757 real sessions in [`reports/backtest_v2_2023-08_to_2026-09/report.md`](../reports/backtest_v2_2023-08_to_2026-09/report.md). V2 improves some historical diagnostics but remains below the majority-class baseline and approximately chance on the executable next-open-to-close basis, so it remains experimental. The raw public archive is not vendored, but its compact point-in-time OI, NIFTY OHLC, and participant-volume derivatives are committed under [`historical/`](../historical/); source revision and output hashes are in [`historical/README.md`](../historical/README.md).

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
# The compact committed inputs reproduce the published direction replay.
python backtest.py \
  --participant-oi historical/participant_oi.csv \
  --ohlc historical/nifty_ohlc.csv \
  --symbol NIFTY \
  --decoder-version v2 \
  --output-dir reports/backtest
```

Raw archive directories/ZIPs and date-matched option-chain JSONs remain accepted
when a separate level-proxy study is required. Equivalent package command:

```bash
PYTHONPATH=src python -m fiidii.cli backtest \
  --participant-oi historical/participant_oi.csv \
  --ohlc historical/nifty_ohlc.csv \
  --decoder-version v2
```

Useful controls:

```text
--decoder-version v1|v2           # v2 is the production default; v1 is frozen
--flat-threshold-pct 0.15          # ±0.15% is FLAT (inclusive)
--level-touch-tolerance-pct 0.05  # range may come within ±0.05% of a level
--from-date 2025-01-01
--to-date 2025-12-31
```

Percent arguments are percentage points: `0.15` means 0.15%, not 15%.

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

The quickest reproducible direction replay uses the committed compact inputs:

```bash
PYTHONPATH=src python research/run_v3_comparison.py \
  --participant-oi historical/participant_oi.csv \
  --ohlc historical/nifty_ohlc.csv \
  --output-dir /tmp/reproduced-v3
```

It produces the same 757 per-date v1/v2/v3 predictions and daily comparison
metrics as the published candidate evidence package. `historical/README.md`
contains compact-file SHA-256 hashes and its pinned-source reference.

The published audit originally used a third-party GitHub mirror of raw
NSE archive-shaped reports, pinned to commit
`7d481cf1fcffe44be68852892028195c4f12dddd`. The raw files are intentionally
not vendored here. Fetch only the two required directories to independently
rebuild the compact inputs or to audit raw source reports:

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
