# FII-DII-Decode

Decode **FII / DII / Pro / Client** positioning from official NSE data and get an
automated **daily report** — emailed every weekday at **9 PM IST** — with a
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
Historical option-chain snapshots were unavailable, so level-reaction accuracy
remains unknown.

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
2. Genuine dated **historical option-chain, exact institutional-level, intraday
   candle, and cash-flow snapshots** are still needed to test level reactions and
   the complete live pipeline. The direction-only OI/OHLC result is published
   above; bundled fixtures remain demo/test-only.

---

## What it does

1. **Fetches** (free, official NSE):
   - Participant-wise Open Interest (Client / DII / FII / Pro, futures & options)
   - FII/DII cash provisional net
   - NIFTY option chain (strike-wise OI, ΔOI, IV) + spot
2. **Decodes** it into a forced OI research lean, a separate actionability state,
   and deterministic setup strength (`src/fiidii/decode.py`).
3. Ranks **option-chain support/resistance proxies** from relevant-side total OI
   plus change in OI, keeps exact supplied institutional references separate,
   and reports confluence, max pain, and PCR (`src/fiidii/levels.py`).
4. Builds a conditional next-day plan, a decision tree at every level, and
   next-week carry context; v2 publishes no weekly direction because the
   candidate failed confirmation (`src/fiidii/predict.py`).
5. **Reports** as HTML + Markdown (`reports/`) and **emails** it
   (`src/fiidii/email_send.py`).
6. **Automates** all of the above via GitHub Actions at 9 PM IST, Mon–Fri.

## Quick start (local)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Demo run (uses bundled fixtures, no network, no email):
PYTHONPATH=src python -m fiidii.cli run --demo --no-email

# Live run (needs NSE reachability — works on GitHub runners / most home IPs):
PYTHONPATH=src python -m fiidii.cli run --no-email

# Optional: add dated exact institutional references from an external chart/file:
PYTHONPATH=src python -m fiidii.cli run --no-email \
  --institutional-levels /path/to/levels.json
```

Open `reports/latest.html` to view the result.

> Note: NSE blocks many datacenter IPs (including this build sandbox), so use
> `--demo` here. The scheduled **GitHub Actions runner can reach NSE**, so the
> live daily job works there.

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
metric definitions, no-look-ahead rules, and limitations. The published real-data
result is explicitly OI-only; no option-chain level accuracy is claimed.

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

`.github/workflows/daily-report.yml` runs at **15:30 UTC = 21:00 IST**, Mon–Fri.
You can also trigger it manually from the Actions tab (`workflow_dispatch`), with
optional `demo` / `no_email` toggles.

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
tests/                # fixtures + unit/smoke tests
.github/workflows/    # daily 9 PM IST automation
```

## Testing

```bash
PYTHONPATH=src python -m pytest tests/ -q
```
