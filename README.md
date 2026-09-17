# FII-DII-Decode

Decode **FII / DII / Pro / Client** positioning from official NSE data and get an
automated **daily report** — emailed every weekday at **9 PM IST** — with a
**next-day** and **next-week (Mon–Fri)** prediction, the **institutional levels**
where a reaction is expected, and exactly **what happens at each level**
(hold → bounce/continue, or reject/break → reversal).

> ⚠️ Educational analysis of publicly available data. **Not investment advice.**

## ⚠️ Validation status: experimental, not a standalone trading signal

A point-in-time OI-only replay on **757 real historical sessions** (8-Aug-2023 to
3-Sep-2026) produced:

- **36.20%** exact UP/FLAT/DOWN accuracy vs **42.14%** majority-class baseline;
- **53.96%** sign accuracy only after excluding realised FLAT moves (95% CI
  49.16–58.68%, so no reliable above-chance proof);
- **46.72%** next-session open-to-close sign accuracy on non-FLAT directional cases.

The strongest observed relationship was with the overnight gap, not the tradable
next-session open-to-close move. Higher-confidence and five-session subsets showed
some aggregate signal, but it weakened in yearly/latest-period checks. Therefore,
**do not use the displayed forecast or confidence as a standalone entry signal.**

Full result, per-date predictions, threshold sensitivity, yearly stability, and
source hashes: **[`reports/backtest_2023-08_to_2026-09/report.md`](reports/backtest_2023-08_to_2026-09/report.md)**.
Historical option-chain snapshots were unavailable, so level-reaction accuracy
remains unknown.

---

## ✅ Methodology: decoded from your PDFs

The decode engine now implements **Amit Dhamija's participant-OI methodology**,
reconstructed line-by-line from the two source PDFs (`full_transcript.pdf` and
`Market_Analysis_03_August_2026_Decoded-combined.pdf`). The full breakdown is in
**[`docs/methodology.md`](docs/methodology.md)**. Highlights:

- **Retail (Client) = contra indicator** — fade it. Smart Money = **FII + Pro**.
- **Options ranked first** (Index Options > Stock Options > Index Fut > Stock Fut).
- Reads **today's fresh action** vs **carry**, and **fresh longs vs short-covering**.
- **Pro drives the next-day view; FII drives the positional/weekly view** (Pro must
  be supportive). Detects **FII-vs-Pro conflict** → "one-sided move then reversal".
- **Institutional levels** from option-chain OI + ΔOI, with support→resistance flips
  and the **liquidity-sweep-then-reverse** confluence.
- Next-day prediction as **Gap Up / Flat / Gap Down** scenarios with expected
  reaction at each level.

### Still needed from you

1. **GitHub secrets for email** (see below) so the 9 PM job can actually send mail.
2. Genuine dated **historical option-chain and cash-flow snapshots** are still
   needed to test level reactions and the complete live pipeline. The direction-only
   OI/OHLC result is now published above; bundled fixtures remain demo/test-only.

---

## What it does

1. **Fetches** (free, official NSE):
   - Participant-wise Open Interest (Client / DII / FII / Pro, futures & options)
   - FII/DII cash provisional net
   - NIFTY option chain (strike-wise OI, ΔOI, IV) + spot
2. **Decodes** it into a composite directional bias + confidence
   (`src/fiidii/decode.py`).
3. **Derives institutional levels** from the option chain — call/put walls,
   fresh-OI levels, max pain, PCR — each with an **expected reaction**
   (`src/fiidii/levels.py`).
4. **Predicts** next-day and next-week direction with **if/then scenarios**
   (`src/fiidii/predict.py`).
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
  decode.py      # the decode engine (bias + confidence)
  levels.py      # option-chain institutional levels + reactions
  predict.py     # next-day / next-week predictions + scenarios
  backtest.py    # point-in-time replay, metrics, CSV/JSON/Markdown outputs
  report.py      # HTML + Markdown rendering
  email_send.py  # SMTP delivery
  cli.py         # daily runner + historical backtest commands
backtest.py           # convenient backtest CLI entry point
docs/methodology.md   # decoded signal methodology
docs/backtesting.md   # historical data contract + metric definitions
tests/                # fixtures + unit/smoke tests
.github/workflows/    # daily 9 PM IST automation
```

## Testing

```bash
PYTHONPATH=src python -m pytest tests/ -q
```
