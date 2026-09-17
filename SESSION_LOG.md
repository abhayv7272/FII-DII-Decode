# SESSION LOG — Running Context Backup

> **Purpose:** Permanent, in-repo backup of session context so any future
> session (human or agent) can pick up exactly where the last one stopped.
> **Update rule:** append a new entry at the top of "Log" after every work
> session/turn. Never delete older entries.

---

## Current state (as of 2026-09-18)

- **Project:** FII-DII-Decode — NIFTY FII/DII/Pro/Client participant-OI decoder
  (v2, transcript-grounded), daily 9 PM IST email automation via GitHub Actions.
- **main tip:** `9947ea5` (bot report commit) ← `8063ebd` (PR #4) ← `11bae2b`
  (PR #3, email fix) ← PR #2 ← PR #1.
- **Working branch:** `arena/01a0b0db-fii-dii-decode`, tip `36d31dd`.
  **PR #5 OPEN** (level-reaction backtest) — awaiting user merge.
- **Automation status: HEALTHY.** Scheduled live run `35263293001` = SUCCESS.
  The empty-SMTP-secret bug is confirmed fixed on a real runner.
- **Validation status:** v2 published as experimental / NO standalone edge.
  Direction: 37.91% exact vs 42.14% majority baseline (757 sessions).
  Levels (new): 685 tests, 49.20% hold — also no edge.
- **Automation:** `.github/workflows/daily-report.yml`, cron `30 15 * * 1-5`
  (21:00 IST), live mode; `workflow_dispatch` accepts `demo` / `no_email`.

## Open items / next steps

1. **[DONE]** Workflow exit-1 bug (blank SMTP secrets → `int("")`). Fixed in
   PR #3, verified GREEN by scheduled run `35263293001` on 2026-09-18.
2. **[DONE]** Live-fetch reachability from GitHub runners. The live scheduled
   run reached the Stocklyzer participant-OI fallback and completed with
   `DEGRADED_MISSING_LEVEL_INPUT` — direction inputs ready, no same-date option
   chain. NSE direct is still not reachable from the runner; the documented
   fallback chain carries it.
3. **[DONE]** Historical option-chain snapshots for level validation. Rebuilt
   from public NSE F&O bhavcopy via `research/bhavcopy_to_option_chain.py`;
   result published in `reports/backtest_v2_levels_2023-08_to_2026-09/`.
4. **Email secrets still not configured by user.** Needed (GitHub → Settings →
   Secrets → Actions): `SMTP_HOST` (smtp.gmail.com), `SMTP_PORT` (465),
   `SMTP_USER`, `SMTP_PASS` (Gmail **App Password**, not login password),
   `MAIL_FROM`, `MAIL_TO` (abhayv72727@gmail.com). Until then email is skipped
   with a clear log line and the job stays green.
5. **Merge PR #5** (or ask the agent to) so the level backtest lands on main.
6. **Only remaining data blocker: intraday 10-15 minute candles.** Daily OHLC
   cannot verify confirmation candles, sweep-then-reclaim, touch sequencing,
   stops, or slippage. Exact institutional levels and historical cash-flow
   history are still optional nice-to-haves.

## Key facts discovered (don't re-derive)

- Sandbox (Arena) cannot reach GitHub log/artifact storage
  (`results-receiver.actions.githubusercontent.com`,
  `productionresultssa*.blob.core.windows.net`) — use `gh run view` +
  committed `data/fetch_status_*.json` instead of downloading logs.
- Sandbox network access VARIES by session. Session 3 had no GitHub/NSE
  egress; session 4 had working `git clone`, `gh`, and mirror access. Always
  re-test with a quick `git ls-remote` before assuming the network is down.
- Sandbox still cannot reach NSE directly — live CLI run here fails closed;
  that is expected and documented in README.
- Python deps are NOT preinstalled in a fresh sandbox. Create a venv first:
  `python -m venv .venv && .venv/bin/pip install -r requirements.txt`, then run
  with `PYTHONPATH=src .venv/bin/python`.
- Historical option-chain rebuild recipe (session 4): sparse-checkout
  `nse_archives/{participant_oi,index_close,fo_bhavcopy}` from
  `sahilempire/groww-market-data` @ `7d481cf1fcffe44be68852892028195c4f12dddd`
  (fo_bhavcopy is ~757 MB), run `research/bhavcopy_to_option_chain.py`
  (~3.5 min for 760 files), then `backtest.py --option-chains`.
- Levels do NOT change v2 direction metrics — the locked score never consumes
  them. Identical direction numbers across chain/no-chain runs is the correct
  control result, not a bug.
- The workflow's "Commit data + reports" step runs `if: always()` and pushes
  to main even when the decode step fails — bot commits `42b527c` and
  `8e0fe52` were produced by the two FAILED demo runs (17:37 / 17:52 UTC).
- `gh secret list` AND `gh workflow run` are 403 for this token (no actions
  permissions; PR create/merge works). User must trigger workflows/secrets
  from the GitHub UI.
- Repo is a shallow clone (depth 1); use `gh api repos/.../commits` for full
  history.
- Pipeline prints `[email] SMTP_USER/SMTP_PASS not set; skipping send.` and
  exits 0 when credentials are absent/blank — email can no longer fail a run.

## Log (newest first)

### 2026-09-18 (session 4 — Arena agent, branch `arena/01a0b0db-fii-dii-decode`)
- Network was available again in this sandbox (previous session was cut off),
  so the saved level-backtest plan was executed end to end.
- Confirmed the pending verification: scheduled live run **35263293001 =
  SUCCESS** (main `9947ea5`). The empty-SMTP-secret fix from PR #3 holds; the
  workflow no longer fails. Live fetch was `DEGRADED_MISSING_LEVEL_INPUT`
  (Stocklyzer participant-OI fallback only, no same-date option chain) — that
  is the intended fail-safe behaviour, not a bug.
- Added `research/bhavcopy_to_option_chain.py`: rebuilds dated NSE-shaped
  option-chain JSON from F&O bhavcopy archives. Handles both the legacy
  `fo<DDMONYYYY>bhav.csv` and the 2024+ UDiFF `BhavCopy_NSE_FO_*` layouts,
  emits only the nearest non-expired expiry, and takes `underlyingValue` from
  the same-date index close (never a later session).
- Built 759 snapshots from the pinned mirror
  (`sahilempire/groww-market-data` @ `7d481cf1...`, 760 bhavcopy files, 1 skip).
- Re-ran the 757-session v2 replay **with** chains →
  `reports/backtest_v2_levels_2023-08_to_2026-09/`:
  exact 37.91%, directional 43.72% (identical to the chain-less run — correct
  control, v2 score does not consume levels), and the first real level numbers:
  **685 tests, 49.20% hold** (support 46.82%, resistance 51.62%). Coin flip →
  **no level edge**.
- Added `tests/test_bhavcopy_convert.py` (5 tests, both layouts + fallback +
  backtester round-trip). Full suite: **47 passed**.
- README + `docs/backtesting.md` updated with the result, reproduction steps,
  and the converter's honest limitations (EOD close not LTP, IV=0, daily proxy
  only — no 10-15 min candle / sweep / slippage verification).
- Next session: intraday (10-15 min) candles are the only remaining blocker for
  a genuine trade-level test; everything else is published.

### 2026-09-17 (session 3 — Arena agent, branch `arena/01a0b0b7-fii-dii-decode`)
- User asked to continue from previous session; no chat backup file existed,
  so state was reconstructed from repo + GitHub (this file now exists so that
  never happens again).
- Diagnosed the two failed `workflow_dispatch` demo runs (35255373444,
  35253900682): pipeline completed (reports committed by the `if: always()`
  commit step) but exited 1. Root cause: empty-string secrets →
  `int("")` ValueError in `email_send.py` before the skip-credentials check.
- Fixed `email_send.py` with blank/malformed-safe `_env_str`/`_env_int`;
  added `tests/test_email.py` (4 tests). Full suite: 37 passed.
- Verified locally: demo run with all SMTP env vars = "" now exits 0 and
  skips email cleanly.
- **PR #3 opened + MERGED (main = `11bae2b`)** — fix confirmed present on main
  via contents API.
- Could NOT trigger the verification dispatch run (token 403 on workflow
  dispatch). User was given UI steps: Actions → "Daily FII/DII Decode Report"
  → Run workflow → tick "demo" → Run. Expected: GREEN.
- Next session: check `gh run list` for the outcome of the user-triggered
  demo run and/or the next 21:00 IST scheduled live run.

### 2026-09-17 (session 2 — branch `arena/01a0af8e-fii-dii-decode`, PR #2)
- "fix: validate live data inputs and fail closed" — live CLI now records
  failures and exits non-zero instead of predicting from missing data.
- Triggered the two demo workflow_dispatch runs that failed (see above).

### 2026-09-17 (session 1 — branch `arena/01a0af6d-fii-dii-decode`, PR #1)
- Built the whole engine: PDFs decoded → methodology, NSE fetchers, v2
  decoder, levels, predictions, HTML/MD reports, email, 9 PM IST workflow.
- Later same day: backtest harness + real 757-session validation, v2
  transcript-grounded decoder, institutional-reference separation.
