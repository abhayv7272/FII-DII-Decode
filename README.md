# FII-DII-Decode

Decode **FII / DII / Pro / Client** positioning from official NSE data and get an
automated **daily report** — emailed every weekday at **9 PM IST** — with a
**next-day** and **next-week (Mon–Fri)** prediction, the **institutional levels**
where a reaction is expected, and exactly **what happens at each level**
(hold → bounce/continue, or reject/break → reversal).

> ⚠️ Educational analysis of publicly available data. **Not investment advice.**

---

## ⏳ Status / what's pending from you

The engine is fully built and tested end-to-end on sample data. Two things are
needed to finish:

1. **The channel transcript PDF.** It was not attached / not in the workspace.
   Drop it into the repo (or paste the text) and the decode rules in
   `docs/methodology.md` + `src/fiidii/decode.py` will be tuned to match that
   channel's exact method. Until then, a well-grounded standard methodology is used.
2. **GitHub secrets for email** (see below) so the 9 PM job can actually send mail.

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
  report.py      # HTML + Markdown rendering
  email_send.py  # SMTP delivery
  cli.py         # end-to-end runner
docs/methodology.md   # how the decode works (tuned to the PDF once provided)
tests/                # fixtures + smoke tests
.github/workflows/    # daily 9 PM IST automation
```

## Testing

```bash
PYTHONPATH=src python -m pytest tests/ -q
```
