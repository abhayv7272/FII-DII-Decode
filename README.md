# FII-DII-Decode

Decode **FII / DII / Pro / Client** positioning from validated, official-first market data and get a
scheduled **daily report** — configured to run every weekday at **9 PM IST** — with a
conditional **next-day OI lean**, **next-week carry context**, automatic
option-chain level proxies, and gap-up/flat/gap-down plans. Every level includes
confirmed hold/reject and break/role-flip branches with the next target. V2 can
abstain; every possible entry remains conditional on price/level confirmation.

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
2. **Intraday candles (10-15 minute)**, exact institutional levels, and
   historical cash-flow snapshots are still needed. Level reactions now have a
   published *daily* proxy (above), but confirmation-candle behaviour, sweeps,
   and slippage cannot be tested without intraday data. Bundled fixtures remain
   demo/test-only.

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
tests/                # fixtures + unit/smoke tests
.github/workflows/    # daily 9 PM IST automation
```

## Testing

```bash
PYTHONPATH=src python -m pytest tests/ -q
```
