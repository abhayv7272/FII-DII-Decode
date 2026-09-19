# FII-DII-Decode

Decode **FII / DII / Pro / Client** positioning from validated, official-first market data and get a
scheduled **daily report** — configured to run every weekday at **9 PM IST** — with a
conditional **next-day OI lean**, **next-week carry context**, automatic
option-chain level proxies, a full market-possibility map (range, trend,
sweep/trap, no-trade conditions), and gap-up/flat/gap-down plans. Every level
includes confirmed hold/reject and break/role-flip branches with the next target.
V2 can abstain; every possible entry remains conditional on price/level
confirmation.

> ⚠️ Educational analysis of publicly available data. **Not investment advice.**

## ⚠️ Validation status: experimental, not a standalone trading signal

A point-in-time OI-only replay compared frozen v1 with transcript-grounded v2 on
**757 real historical sessions** (8-Aug-2023 to 3-Sep-2026):

| Full-sample diagnostic | V1 | V2 |
|---|---:|---:|
| Exact close-to-close UP/FLAT/DOWN | 36.20% | 37.91% |
| Close non-FLAT sign | 53.96% | 55.05% |
| Next-open-to-close non-FLAT sign | 46.72% | 49.41% |

The close-to-close majority-class baseline is **42.14%**, above both versions.
V2's executable next-open-to-close result remains approximately chance, and its
higher setup-strength subsets deteriorated in 2026 confirmation. A locked
five-session candidate also failed confirmation, so production v2 emits
`NO-VALIDATED-EDGE` for next week. **Do not use the OI lean or setup strength as a
standalone entry signal. Setup strength is not probability.**

Full v2 comparison, per-date predictions, chronological periods, strength
breakdown, and weekly rejection evidence:
**[`reports/backtest_v2_2023-08_to_2026-09/report.md`](reports/backtest_v2_2023-08_to_2026-09/report.md)**.
The prior v1 audit remains intact at
**[`reports/backtest_2023-08_to_2026-09/report.md`](reports/backtest_2023-08_to_2026-09/report.md)**.

### 🔬 v3 candidate: a dev-fitted structural update that now beats the majority baseline (still under forward validation)

A full deep dive (univariate null controls, six-way v2 ablation, ~840-structure
weight grids, walk-forward ML, bhavcopy-derived chain features, level and
weekly re-tests — log: **[`reports/v3_deep_dive/REPORT.md`](reports/v3_deep_dive/REPORT.md)**)
produced a small v3-candidate update, fitted on the 2023-2024 development
partition only and replayed unchanged afterwards:

| Full-sample close-to-close (757 sessions) | V1 | V2 | **V3 candidate** |
|---|---:|---:|---:|
| Exact UP/FLAT/DOWN | 36.20% | 37.91% | **45.05%** (baseline 42.14%) |
| Close non-FLAT sign | 53.96% | 55.05% | **57.12%** (95% CI 53.12–61.03) |
| Next-open-to-close non-FLAT sign | 46.72% | 49.41% | **51.30%** |

Per-period exact: dev **45.03%** (baseline 45.32%), validation **43.95%**
(baseline 39.92%), confirmation **46.71%** (baseline 42.51%) — the first
configuration in this repository to beat the period majority baselines on both
untouched partitions, with paired McNemar vs v2 p≈0.0000 pooled
(conf p=0.020, val p=0.063, dev p=0.006). The v3 delta: index futures 40% of
each participant read, Pro:FII 60:40, a -0.10 Client tilt, and a 0.00
forced-class threshold (the ~79% non-FLAT session share made v2's ±0.10 band
cost more exact-class hits than it saved). Closures remain half weight and DII
F&O still gets zero direction.

Notes that keep this honest: v3 was selected from a bounded family on
2023-2024 only; most of the close-to-close gain is the **overnight-gap
channel**, which cannot be entered at the signal close (OI is published after
it) — the **executable open-to-close basis remains ≈ chance for every
version**, so **do not treat v3 as a tradable edge**. Weekly remains
`NO-VALIDATED-EDGE`, and levels remain a coin flip. Promotion to the default
decoder requires an untouched forward window. Evidence package:
**[`reports/backtest_v3_candidate_2023-08_to_2026-09/report.md`](reports/backtest_v3_candidate_2023-08_to_2026-09/report.md)**;
opt in with `--decoder-version v3`.

**Forward-validation gate:** the daily workflow already accumulates
`data/participant_oi.csv` / `data/index_ohlc.csv` / `data/fii_dii_cash.csv`.
`python research/v3_forward_validation.py` replays v1/v2/v3 on signal dates
strictly after the fitted archive end (2026-09-04) and applies locked
promotion criteria (≥60 evaluable sessions, exact ≥ majority baseline and ≥
v2, non-FLAT sign ≥ 52% with Wilson lower bound > 50%). Current state:
**`COLLECTING_DATA`** (gate report:
[`reports/v3_forward_validation/gate_report.md`](reports/v3_forward_validation/gate_report.md)).

### 🧪 V4 psychology/manipulation search: no honest 75-85% edge yet

At the user's request, a much more aggressive v4 research pass now tests
4/7/15/21-session institutional psychology patterns, smart-money/client
crowding, Pro-vs-FII agreement/conflict, DII positioning levels, option-chain
PCR/wall/max-pain aggregates, volatility/gap manipulation proxies, and frozen ML
sanity checks. It exports **26,049** threshold rules across **4,764** engineered
columns in [`reports/v4_psychology_search/`](reports/v4_psychology_search/).

Result: **0 rules** reached ≥75% exact accuracy on both 2025 validation and 2026
confirmation with at least 20 calls in each period; **0 rules** reached ≥75%
non-FLAT sign accuracy on both holdout periods with at least 20 non-FLAT calls.
The closest research-only pockets are low-coverage (~10-30 calls) and therefore
not promotable. See
[`reports/v4_psychology_search/report.md`](reports/v4_psychology_search/report.md).

A follow-up **v5 holdout/combo/meta audit** then refit rules on 2023-2025 and
kept 2026 as the final holdout, added voting-rule combinations, a leakage-guarded
v3 meta-gate, and a recent 1-minute intraday first-candle confirmation check:
[`reports/v5_holdout_combo_meta/report.md`](reports/v5_holdout_combo_meta/report.md).
It found **0** 2026-holdout exact rules at ≥75% with ≥20 calls, **0** voting
combos at that bar, and **0** leakage-guarded meta-gates above 70% precision with
≥20 holdout calls. A few 2026-only sign pockets reached ≥75% on ~20 calls, but
were not stable enough on the training window to promote.

The **v6 real-world selective search** then tried pair/conjunction rules from the
v4 psychology pool and 10+ years of NIFTY daily price-regime history:
[`reports/v6_realworld_selective/report.md`](reports/v6_realworld_selective/report.md).
It checked **319,600** OI/psychology rule pairs and **2,562** price-only rules;
again **0** reached ≥75% robust holdout accuracy with minimum sample guards.

The **v7 intraday + exact dated-level path** now adds the next strongest data
source the EOD runs were missing: 15-minute NIFTY candles from 2017-04-03 to
2026-09-17 and 140 date-stamped NIFTY levels manually audited from the supplied
2026 market-analysis PDF:
[`reports/v7_intraday_institutional_levels/report.md`](reports/v7_intraday_institutional_levels/report.md).
The raw 1-minute archive stays outside Git; the derived 15m file and provenance
manifest are committed under `historical/`. Honest post-entry scoring still found
**0** generic 15m rules clearing a 70% train/2025/2026 gate and **0** PDF-level
confirmation variants clearing a 70% July-Aug/Sep split. Some first-candle
level branches showed 75-86% in the September slice, but July-Aug training was
near coin flip, so these are forward-watch tags only, not production signals.

The follow-up **v8 trade-level simulator** adds 10-minute candles and symmetric
target/stop execution after the confirmation candle:
[`reports/v8_intraday_trade_sim/report.md`](reports/v8_intraday_trade_sim/report.md).
It again found **0** generic 10/15m trade rules clearing a 70% train/2025/2026
win-rate gate and **0** PDF-level trade rules clearing the July-Aug/Sep gate.

Finally, **v9 OI + intraday confirmation** retests the core idea using prior-day
v3 FII/DII/Pro/Client lean plus next-session first 10/15/30/60-minute
confirmation and symmetric target/stop execution:
[`reports/v9_oi_intraday_confirmation/report.md`](reports/v9_oi_intraday_confirmation/report.md).
It checked **29,568** OI+intraday rule summaries; **0** cleared the strict 70%
train(2023-24)/validation(2025)/confirmation(2026) gate.

### V10 sniper result: supporting tiny-gap level-touch edge found

Important clarification: this is a **supporting sniper module**, not the full original next-day/weekly prediction maker. The full predictor is still not validated at 75-85%+ every-day directional accuracy. V10 found a selective **at-open level-touch prediction**:
when NIFTY opens only a tiny distance from the previous close, fade the gap and
predict that the **previous close will be touched intraday**. This uses only
values known at the open and 2017-2026 intraday highs/lows for the label.

Best robust rule:
[`reports/v10_structural_gap_pivot_sniper/report.md`](reports/v10_structural_gap_pivot_sniper/report.md)

| V10 rule | Calls | Overall | Train 2017-23 | Val 2024-25 | Confirm 2026 |
|---|---:|---:|---:|---:|---:|
| `abs_gap_0.03_0.12_both_fill_prev_close` | 393 | **90.33%** | **89.11%** | **94.23%** | **87.50%** |
| `abs_gap_0.02_0.10_both_fill_prev_close` | 351 | **91.17%** | **91.34%** | **92.47%** | **85.19%** |
| `abs_gap_0.05_0.15_both_fill_prev_close` | 428 | **87.15%** | **85.28%** | **93.44%** | **80.49%** |

The default helper `fiidii.gap_sniper.tiny_gap_fill_signal()` implements the
strongest 0.03%-0.12% band for live use as a **level-touch alert**, and the daily
report now includes a V10 opening-sniper block/playbook. You can also evaluate it
manually after the open:

```bash
PYTHONPATH=src python -m fiidii.cli sniper \
  --open 23020 --previous-close 23000 --high 23025 --low 22998
```

Important: the mean target distance is only ~13 NIFTY points, so V10 also
includes raw 1-minute execution diagnostics showing that naive tight-stop trades
are not yet a validated production strategy. A follow-up V11 execution audit
([`reports/v11_gap_sniper_execution/report.md`](reports/v11_gap_sniper_execution/report.md))
confirmed **0** simple target/stop conversions passed a strict 70% + positive-P&L
train/validation/2026 gate. Treat this as a high-probability sniper context until
tick/broker execution, spreads, option premium behavior, and stop logic are
validated. See the full goal/status clarification in [`docs/prediction_maker_status.md`](docs/prediction_maker_status.md).

### V12/V13 deep-dive status: no 85% weekly or VIX-gated daily claim

The direct Friday-to-following-Monday–Friday search (V12) tests 4,746 clean
point-in-time features, 18,527 development-fitted rules and 16,110 agreement
pairs. **Zero** cleared the predeclared 85% gate in both 2025 validation and
2026 confirmation. See
[`reports/v12_weekly_composite_search/report.md`](reports/v12_weekly_composite_search/report.md).

V13 then added a timing-correct, research-only historical India-VIX risk-state
source. It tested 1,022 VIX-direct, VIX-gated and VIX-agreement daily rules on
745 aligned signal rows: again **zero** cleared the 85% gate in both later
splits. In particular, the practical next-open-to-close lens stayed weak. VIX is
not wired into the production decoder. See
[`reports/v13_india_vix_gate/report.md`](reports/v13_india_vix_gate/report.md)
and the source/timing/data-acquisition map in
[`docs/deep-dive-research-plan.md`](docs/deep-dive-research-plan.md).

To keep future sessions reproducible after Arena wipes external directories, a
compact historical bundle is committed under [`historical/`](historical/) with
participant OI, participant volume, canonical NIFTY OHLC, long price-regime OHLC,
chain aggregate features from the pinned Groww mirror, plus the V7/V8 10- and
15-minute intraday and PDF-level datasets.

### Level reactions now measured — and they show no edge either

Historical option-chain JSON is not published anywhere, so levels were previously
untested. Dated snapshots were therefore rebuilt from public NSE **F&O bhavcopy**
archives (`research/bhavcopy_to_option_chain.py`) and the replay re-run with all
757 sessions carrying a same-date chain:
**[`reports/backtest_v2_levels_2023-08_to_2026-09/report.md`](reports/backtest_v2_levels_2023-08_to_2026-09/report.md)**.

| Daily-bar level proxy (±0.05% band) | Tests | Holds | Accuracy |
|---|---:|---:|---:|
| All levels | 685 | 337 | 49.20% |
| Support | 346 | 162 | 46.82% |
| Resistance | 339 | 175 | 51.62% |

Direction metrics are byte-identical to the chain-less run, as expected: the
locked v2 score does not consume levels. Level holds land on a coin flip, so
there is **still no validated edge**. This is a *daily* proxy — bhavcopy carries
EOD close (no LTP, no IV) and daily OHLC cannot verify 10-15 minute candle
confirmation, sweep-then-reclaim, touch order, stops, or slippage. Intraday data
is still required for a real trade-level test.

---

## ✅ Methodology: decoded from your PDFs

The v2 decoder follows a complete reread of both source PDFs
(`full_transcript.pdf` and
`Market_Analysis_03_August_2026_Decoded-combined.pdf`). See the formula in
**[`docs/methodology.md`](docs/methodology.md)** and page/timestamp evidence plus
v1 mapping errors in
**[`docs/transcript-audit-v2.md`](docs/transcript-audit-v2.md)**. The separate
[institutional-level review](docs/institutional-levels.md) documents why exact
institutional levels and automatic option-chain proxies must remain distinct.
Highlights:

- Decomposes **fresh longs, fresh shorts, short covering, and long unwinding**;
  closures receive less weight than fresh additions.
- Normalises activity by current market OI instead of fixed contract scales.
- Uses **index calls + puts first, then index futures** for the daily NIFTY lean;
  aggregate stock derivatives cannot manufacture that direction.
- Makes **Pro primary for the next session, FII primary for carry context**, and
  Client a minority contrary/crowding condition; DII F&O gets zero direction.
- FII-vs-Pro conflict produces `WAIT_FOR_REVERSAL_CONFIRMATION`; a weak score
  produces `NO_DIRECTIONAL_EDGE`.
- The PDFs do not disclose the author's exact institutional-level formula; the
  code does not fabricate it. Automatic levels are visibly labelled option-chain
  proxies, while exact externally supplied references preserve their provenance.
- Each level has both confirmed hold/reject and break/role-flip scenarios, a next
  target, a gap-skip rule, and explicit `WAIT / NO TRADE` without a 10–15 minute
  confirming candle. Gap Up / Flat / Gap Down are scenario branches, not
  guaranteed paths.

### Still needed from you

1. **GitHub secrets for email** (see below) so the 9 PM job can actually send mail.
2. **Forward exact institutional levels and post-2026-09-17 intraday candles** are
   still needed for a real untouched forward gate. V7 now includes historical
   15-minute candles and a PDF-derived dated-level seed set, but the exact level
   formula is still external and every new live level must be supplied with its
   date/provenance. Bundled fixtures remain demo/test-only.

---

## What it does

1. **Fetches and validates** each input independently, official-first:
   - Participant OI: NSE archive filename/host variants → same-date Groww GitHub
     archive → date-checked Stocklyzer and NiftyTrader complete renderings. When
     both renderings are reachable they must agree; their displayed daily changes
     may reconstruct the preceding matrix as `current − change`.
   - Previous OI: holiday-aware archive search; the runner never assumes that
     calendar yesterday was a trading session.
   - FII/DII cash: NSE provisional API → same-date MrChartist GitHub snapshot.
   - NIFTY option chain: NSE API → same-date MarketNetra strike-wise chain.
   - Index OHLC: NSE all-indices API → same-date Yahoo Finance daily bar.
   Every accepted input records source URL, as-of date, fetch time, fallback flag,
   and warnings in `data/fetch_status_<date>.json` and the report.
2. **Decodes** it into a forced OI research lean, a separate actionability state,
   and deterministic setup strength (`src/fiidii/decode.py`).
3. Ranks **option-chain support/resistance proxies** from relevant-side total OI
   plus change in OI, keeps exact supplied institutional references separate,
   and reports confluence, max pain, and PCR (`src/fiidii/levels.py`). The full
   source/validation contract is in [`docs/data-fetching.md`](docs/data-fetching.md).
4. Builds a conditional next-day plan, a decision tree at every level, and
   next-week carry context; v2 publishes no weekly direction because the
   candidate failed confirmation (`src/fiidii/predict.py`).
5. **Reports** as HTML + Markdown (`reports/`) and **emails** it
   (`src/fiidii/email_send.py`).
6. **Fails closed** if either complete current or previous participant-OI matrix
   is unavailable. Cash may degrade the setup, while a missing same-date option
   chain forces levels and gap plans to context-only instead of creating a
   normal-looking actionable report.
7. Defines GitHub Actions automation for 9 PM IST, Mon–Fri. A schedule only runs
   after this workflow is merged to the default branch and Actions is enabled.

## Quick start (local)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Demo run (uses bundled fixtures, no network, no email):
PYTHONPATH=src python -m fiidii.cli run --demo --no-email

# Live run (requires at least one validated source path per required input):
PYTHONPATH=src python -m fiidii.cli run --no-email

# Optional: add dated exact institutional references from an external chart/file:
PYTHONPATH=src python -m fiidii.cli run --no-email \
  --institutional-levels /path/to/levels.json
```

Open `reports/latest.html` to view the result.

> Note: NSE and some fallback sites block many datacenter IPs, including this
> build sandbox. The live command now records the failures and exits non-zero
> rather than generating a prediction from missing data. GitHub-runner
> reachability is not assumed: it must be demonstrated by an actual workflow run
> whose fetch manifest says `READY` or an explicitly described degraded state.

## Proper historical backtest

The harness replays each date with only that day's OI, the exact previous trading
session's OI, and a same-date option-chain snapshot. It then scores the next
trading session's NIFTY close-to-close direction:

```bash
python backtest.py \
  --participant-oi historical/participant_oi/ \
  --ohlc historical/nifty_ohlc.csv \
  --option-chains historical/option_chain/ \
  --decoder-version v2 \
  --output-dir reports/backtest
```

`--decoder-version` accepts `v1`, `v2`, or `v3` (the candidate above; the
daily workflow default remains v2 until forward validation completes).

`--participant-oi` also accepts a consolidated CSV or ZIP; `--option-chains` is
optional. Outputs include per-date predictions/skips CSVs, `metrics.json`, a
confidence-vs-accuracy CSV, and an auditable Markdown report. Definitions include
a configurable FLAT band (default ±0.15%), per-class precision/recall, directional
hit rate, majority-class baseline, and a clearly labelled **daily-OHLC proxy** for
level reactions.

See **[`docs/backtesting.md`](docs/backtesting.md)** for the data contract, exact
metric definitions, no-look-ahead rules, and limitations — including the
bhavcopy-to-option-chain rebuild steps used for the level-enabled run and its
converter limitations.

## Email setup (GitHub → Settings → Secrets and variables → Actions)

Add these repository **secrets**:

| Secret | Value |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `465` |
| `SMTP_USER` | your Gmail address |
| `SMTP_PASS` | a Gmail **App Password** (not your login password) |
| `MAIL_FROM` | your Gmail address (optional) |
| `MAIL_TO` | `abhayv72727@gmail.com` |

**Gmail App Password:** enable 2-Step Verification → Google Account → Security →
App passwords → create one for "Mail" → paste the 16-char code as `SMTP_PASS`.

## Schedule

`.github/workflows/daily-report.yml` is configured for **15:30 UTC = 21:00 IST**,
Mon–Fri. Scheduled workflows execute from the default branch, so branch-only
changes do not affect the schedule. After merging, enable Actions and either wait
for the schedule or trigger `workflow_dispatch` with optional `demo` / `no_email`
toggles. Inspect the uploaded report and `fetch_status_*.json`; a green-looking
HTML file alone is not proof that live data was complete.

## Project layout

```
src/fiidii/
  nse.py         # NSE session (cookie priming + retries)
  fetch.py       # participant OI, cash, option chain collectors
  store.py       # CSV/JSON persistence + history
  decode.py      # v2 OI lean, actionability, setup strength, carry context
  decode_v3.py   # v3-candidate decoder (dev-fitted; forward validation pending)
  legacy_v1.py   # frozen decoder used by the published v1 replay
  levels.py      # option-chain proxies + supplied institutional references
  predict.py     # next-day/weekly context + per-level decision trees
  backtest.py    # point-in-time replay, metrics, CSV/JSON/Markdown outputs
  report.py      # HTML + Markdown rendering
  email_send.py  # SMTP delivery
  cli.py         # daily runner + historical backtest commands
backtest.py           # convenient backtest CLI entry point
docs/methodology.md          # decoded signal methodology
docs/institutional-levels.md # level-source audit + conditional reaction contract
docs/backtesting.md          # historical data contract + metric definitions
docs/data-fetching.md        # provider order, validation + fail-closed policy
research/v3_*.py             # deep-dive pipeline (features, grids, ML, levels)
research/run_v3_comparison.py# official-path v1/v2/v3 replay + evidence package
tests/                # fixtures + unit/smoke tests
.github/workflows/    # daily 9 PM IST automation
```

## Testing

```bash
PYTHONPATH=src python -m pytest tests/ -q
```
