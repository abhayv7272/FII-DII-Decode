# SESSION LOG — Running Context Backup

> **Purpose:** Permanent, in-repo backup of session context so any future
> session (human or agent) can pick up exactly where the last one stopped.
> **Update rule:** append a new entry at the top of "Log" after every work
> session/turn. Never delete older entries.

---

## Current state (as of 2026-09-18, updated)

- **Project:** FII-DII-Decode — NIFTY FII/DII/Pro/Client participant-OI decoder
  (v2 production; **v3 candidate built + published as opt-in research**),
  daily 9 PM IST email automation via GitHub Actions.
- **Validation status:** v2 remains production (37.91% exact vs 42.14%
  baseline). **v3 candidate (`--decoder-version v3`): 45.05% exact full-sample,
  beats baselines on validation (43.95%) and confirmation (46.71%), McNemar
  p≈0.0000 vs v2 — but is NOT promoted**: gains are mostly the non-executable
  overnight-gap channel and it still needs an untouched forward window
  (sessions after 2026-09-04). Evidence:
  `reports/backtest_v3_candidate_2023-08_to_2026-09/` + full search log
  `reports/v3_deep_dive/REPORT.md`.
- **Forward gate:** `research/v3_forward_validation.py` + locked criteria live
  in `reports/v3_forward_validation/gate_report.md` — state
  `COLLECTING_DATA`; rerun as the daily stores/mirror accumulate. Cash probe
  (MrChartist 2026 history, exploratory): no standalone next-day content;
  mild v3-agreement premium; production's confirmation-only policy kept.
  Gate is end-to-end smoke-tested on a synthetic forward window
  (`tests/test_research_gates.py`, suite 49 passed).
- **Automation:** unchanged (v2 default), cron `30 15 * * 1-5`.
- **Sandbox caveat:** only files *inside the repo* persist across Arena turns —
  `/home/user/historical`, `/home/user/features`, and venvs are wiped between
  turns. Re-create venv with
  `pip install -r requirements.txt scipy scikit-learn`; research data must be
  re-downloaded (mirror commit `7d481cf`) or consolidated into the repo.

## Log (newest first)

### 2026-09-18 (session 9 — durable backtest foundation restarted from GitHub backup)
- User asked the agent to read the GitHub chat backup and restart the actual
  prediction-maker work. The remote continuation branch was verified at
  `1fdb66c`; the product objective in session 8 is the governing scope.
- **Durable history added:** rebuilt from the pinned
  `sahilempire/groww-market-data` commit `7d481cf1...` and committed as compact
  point-in-time CSVs under `historical/`: participant OI (3,800 rows), NIFTY
  OHLC (759 rows), and participant volume (3,795 rows), plus hashes/source
  documentation. This removes the Arena-reset blocker without committing the
  ~757 MB raw bhavcopy archive.
- Added reproducible builder `research/build_compact_history.py`; compact
  history replays all **757** published v1/v2/v3 daily predictions and the
  `daily_comparison.csv` byte-for-byte. `v3_features.py` now also accepts the
  compact dated participant-volume CSV (757×373 point-in-time matrix builds).
- The v3 forward gate now defaults to durable `historical/` files and the daily
  GitHub workflow reruns it after each decode. It still correctly reports
  `COLLECTING_DATA`: live OI ends 2026-09-17 but currently available NIFTY bars
  end 2026-09-04, so there are zero real forward evaluations.
- Added compact-history regression coverage; full suite: **50 passed**. Next
  product blocker remains a dated 10–15 minute NIFTY candle source for real
  support/resistance, break/retest, and sweep validation; weekly output remains
  `NO-VALIDATED-EDGE` until a candidate survives that evidence process.

### 2026-09-18 (session 8 — product objective clarified by user)
- User clarified the actual product aim: build an evidence-backed **prediction
  maker**, not a standalone decoder study. Each evening it should email a clear
  next-session and next Monday-to-Friday outlook: UP / DOWN / CONSOLIDATION,
  key support/resistance zones, and conditional gap, break/retest, and
  liquidity-sweep/reclaim scenarios. Backtesting is the decision process for
  whether any individual claim is safe to deploy.
- Therefore all continuation work must be judged against that deliverable:
  point-in-time historical inputs; separate, honest backtests for next-day
  direction, weekly direction, and level reaction/sweep branches; an untouched
  forward window; then calibrated e-mail wording that distinguishes a validated
  edge from research/no-trade context.
- Current honest evidence: the daily v3 candidate is promising but not yet
  promoted (45.05% exact versus 42.14% full-sample majority baseline; forward
  gate pending); the weekly directional model has **NO-VALIDATED-EDGE**; and
  option-OI proxy level holds are 49.20%, near chance. The daily email pipeline
  exists, but it must keep these caveats rather than represent unvalidated
  levels or weekly calls as reliable predictions.
- Immediate implementation sequence: make compact dated history durable in-repo
  (or otherwise reproducibly available), extend/re-run the relevant backtests,
  obtain dated 10-15 minute NIFTY bars for executable level/sweep validation,
  and only promote components that pass their locked forward evidence gate.

### 2026-09-18 (session 7 — continuation restored; persistent handoff protocol)
- User resumed work and explicitly asked that the session **not be closed**. This
  repository file remains the durable handoff: append a newest-first entry after
  every agent turn; do not delete prior entries.
- Verified the fresh Arena checkout is clean at main merge `7eeb105` / PR #6.
  Recreated the ephemeral local virtual environment with the documented research
  dependencies (`scipy`, `scikit-learn`) and ran the full suite: **49 passed**.
- Current gate status is unchanged and correctly remains `COLLECTING_DATA`: the
  committed store has participant OI through **2026-09-17**, but no committed
  index-OHLC store; the pinned historical mirror is outside the repo and absent
  in this new sandbox. Therefore there are still zero evaluable untouched
  forward sessions. The `2026-09-18` decoded/fetch artifacts are explicitly
  synthetic **DEMO_FIXTURE** outputs, not live data, and were not used.
- The prior unresolved decision remains intentionally unassumed: whether to add
  the compact (~1.5 MB) consolidated historical CSVs to the repository for
  sandbox-proof research, or keep re-downloading them per session.

### 2026-09-18 (session 6 — chat backup requested + gate smoke test)
- User asked: **"Backup chat to github"** → this entry is the backup; all
  work is committed to `arena/01a0b102-fii-dii-decode` (PR #6).
- **Discovery:** Arena sandbox wipes everything outside the repo between turns
  (venv, `/home/user/historical` mirror, `/home/user/features`, probe caches
  gone). Local branch pointer also reset to `main` while the *working tree*
  kept every file → repaired via `git fetch origin arena/01a0b102-fii-dii-decode`
  + `git reset --mixed FETCH_HEAD` (remote branch/PR #6 were never lost).
- **Gate smoke test added:** fabricated two post-2026-09-04 sessions via
  `--extra-*` dirs, ran the full gate CLI — asserts `COLLECTING_DATA`,
  per-version stats, prediction export, and that gate v3 numbers equal a
  direct `run_backtest` call. New `--repo-participant-store` /
  `--repo-ohlc-store` flags make the runner hermetic for tests (default
  unchanged: repo stores). Suite: **49 passed**.
- **Pipeline resilience:** live run now persists a close-only NIFTY bar from
  the option chain's `underlyingValue` when the index-quote fetch fails
  (`data/index_ohlc.csv` starts filling from either source).
- **Pending decision (user redirected before answering):** commit compact
  consolidated history CSVs (`historical/participant_oi.csv`,
  `nifty_ohlc.csv`, `participant_vol.csv` ≈ 1.5 MB) into the repo so the gate
  and all backtests survive sandbox wipes; a re-download was aborted mid-turn.
- Next: if user approves, do the consolidation; otherwise re-download per
  turn. Then keep accumulating daily stores and rerun the gate.
- "Continue" → executed the two documented next steps.
- **Forward-validation gate built & locked:** `research/v3_forward_validation.py`
  replays v1/v2/v3 via the production path on signal dates after 2026-09-04
  using the pinned mirror + the accumulating daily stores
  (`data/participant_oi.csv`, `data/index_ohlc.csv`). Locked promotion
  criteria: ≥60 evaluable sessions, v3 exact ≥ majority baseline, exact ≥ v2,
  sign ≥52% with Wilson lo >50%. Current state: `COLLECTING_DATA` (0 evaluable
  forward sessions — last mirror bar is 2026-09-04 and 09-17's target close
  isn't published yet). Gate artifacts committed under
  `reports/v3_forward_validation/`. Tests: `tests/test_research_gates.py`
  (suite now 48 passed).
- Verified the daily stores self-heal pairs: each live run appends the current
  matrix (dated), so consecutive appends form pairs even when the Stocklyzer
  fallback path cannot date its reconstructed previous matrix (deliberately
  conservative; not stored). `data/index_ohlc.csv` still missing (quote fetch
  failed on 09-17 live run; covered by `--extra-ohlc` refreshed mirrors).
- **Stage-8 cash probe (exploratory):** MrChartist `history.json` fetched
  (155 rows, 2026-01-14→2026-09-17). Q1: no standalone next-day content
  (|IC|≈0.03 cc on 143 merged sessions). Q2: v3 + cash agree 47.14% exact vs
  disagree 43.84% (mild, n≈70 each) — matches the existing
  "confirmation-only" policy; NOT promoted (window post-dates fitting).
  Outputs: `reports/v3_deep_dive/cash_probe_2026.csv` + .q1/.q2.json.
- Docs updated: README v3-gate paragraph, methodology forward-gate +
  cash-probe paragraphs.
- Next: let the daily workflow accumulate; rerun the gate when
  `data/index_ohlc.csv`/mirror catch up (mirror re-syncs are the OHLC supply).
  Intraday candles remain the only path to a real executable (open-to-close)
  test.

### 2026-09-17 (session 5 — Arena agent, branch `arena/01a0b102-fii-dii-decode`)
- Task: increase accuracy as much as possible; full deep dive.
- Network available; `raw.githubusercontent.com` blocked but `api.github.com`
  git-blobs (raw Accept) and `codeload` work. Re-downloaded the pinned mirror
  data to `/home/user/historical/` (outside git): participant_oi (760),
  index_close (759), participant_vol (759, NEW input), fo_bhavcopy (760 zips,
  ~757MB), meta (23).
- **Reproduced the published v2 replay byte-exactly first** (757 predictions
  match `reports/backtest_v2_2023-08_to_2026-09/`).
- Built research pipeline in `research/`: v3_features.py (757×386 point-in-time
  matrix incl. participant volumes + price context + rolling flow sums),
  v3_univariate (365-feature IC + 200-shuffle null: NO feature passes null-95
  0.183), v3_ablation (each of 6 v2 rules reverted via production code),
  v3_grids + v3_candidate_sweep (~840 structures, dev-fit, OOS scrolled),
  v3_ml (walk-forward + frozen: ML does NOT beat the hand rule; GBT 99% dev =
  36% conf overfit), v3_chain_features (759 dates of PCR/maxpain/walls/straddle
  from bhavcopy: only gap-channel ICs consistent; PCR blend rejected),
  v3_levels (selection grids ≈ coin flip, unchanged), v3_gap_weekly (gap
  channel is where the alpha is; weekly still dead), v3_robustness (bands,
  rolling windows, years, McNemar, conflict dates).
- Key mechanics discovery: forced class comes from
  `fiidii.predict._direction(composite)` with a hard-coded 0.10 (v2);
  `decode.DIRECTION_THRESHOLD` never reaches the replayed class.
- **v3 candidate locked** (dev-fit only): Pro 60/FII 40/Client −0.10; index
  call/put/fut 30/30/40; threshold 0.00; everything else = v2 (closures half,
  OI-normalised, DII/stock excluded, actionability + weekly NO-VALIDATED-EDGE
  unchanged). Implemented `src/fiidii/decode_v3.py` (delegates to v2
  machinery), wired `--decoder-version v3` into backtest.py/cli.py, tests in
  `tests/test_v3_decoder.py` (suite: 46 passed).
- Official-path evidence package: full exact 45.05% vs baseline 42.14%; per
  period exact dev 45.03/val 43.95/conf 46.71; sign 57.12 (CI 53.12-61.03);
  McNemar dev p .0056/val .0627/conf .0201; open-to-close still ≈ chance
  (51.30 sign). README + methodology v3 section added with honest caveats.
- Heavy artifacts (feature matrix / historical mirror / strike cache ~420k
  rows) live under /home/user/{historical,features} — NOT committed.
- Next session: (1) when the 21:00 IST workflow adds sessions after
  2026-09-04, replay v3 on that untouched window as the promotion gate;
  (2) intraday candles remain the only path to a real executable test
  (open-to-close is still ≈ chance for every version);
  (3) optional: historical FII/DII cash series as stage-8 feature (needs a
  date-stamped source; MrChartist mirror only has recent days).

### 2026-09-18 (session 4 — Arena agent, branch `arena/01a0b0db-fii-dii-decode`)

## Open items / next steps

1. **[FIXED & MERGED — PR #3, main `11bae2b`]** Workflow failed with exit 1 in
   demo runs: GitHub Actions renders missing secrets as EMPTY env strings, so
   `int(os.environ.get("SMTP_PORT", "465"))` got `int("")` → ValueError AFTER
   reports were written. Fixed in `src/fiidii/email_send.py`
   (`_env_str` / `_env_int` normalise blank + malformed values); regression
   tests in `tests/test_email.py`. **Still to verify on the runner:** user (or
   schedule) triggers a `workflow_dispatch` DEMO run on main → expect GREEN.
   NOTE: Arena agent token CANNOT dispatch workflows (HTTP 403) — the user
   must click "Run workflow" in the GitHub Actions UI, or wait for the
   21:00 IST schedule.
2. **Email secrets not yet configured by user.** Needed (GitHub → Settings →
   Secrets → Actions): `SMTP_HOST` (smtp.gmail.com), `SMTP_PORT` (465),
   `SMTP_USER`, `SMTP_PASS` (Gmail **App Password**, not login password),
   `MAIL_FROM`, `MAIL_TO` (abhayv72727@gmail.com). Until then email is skipped
   with a clear log line and the job stays green.
3. **Live-fetch reachability from GitHub runners still unverified.** Both
   prior dispatch runs were DEMO mode. Need one live `workflow_dispatch` run
   (no flags) — or the next 21:00 IST scheduled run — to see whether NSE +
   fallback sources are reachable from a runner. If not, the run fails CLOSED
   (exit 2) by design — then decide: alternate mirrors, self-hosted runner, or
   scheduled demo + manual data.
4. **Data for deeper validation (user-dependent):** genuine dated historical
   option-chain snapshots, exact institutional levels, intraday candles, and
   cash-flow history to test level reactions (direction-only OI result is
   already published).

## Key facts discovered (don't re-derive)

- Sandbox (Arena) cannot reach GitHub log/artifact storage
  (`results-receiver.actions.githubusercontent.com`,
  `productionresultssa*.blob.core.windows.net`) — use `gh run view` +
  committed `data/fetch_status_*.json` instead of downloading logs.
- Sandbox also cannot reach NSE etc. — live CLI run here fails closed; that is
  expected and documented in README.
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
