# Complete Chat Handoff and Project State

This file is a comprehensive handoff summary of the build conversation. It is not a verbatim platform transcript, because the chat platform does not expose an automatic transcript-export tool to the workspace. It preserves the requirements, decisions, experiments, corrections, safety rules, and current authoritative state needed to continue in a new chat.

## User's goal

Build an advanced NIFTY market decision system that:

- runs after approximately 9 PM IST;
- fetches all available completed-session data;
- predicts the next trading day;
- gives a Monday–Friday weekly risk map;
- decodes FII/DII/Pro/Client positioning, options OI, futures, VIX, support/resistance, traps and psychology proxies;
- reports long/short/swing/investment context and what not to do;
- uses multiple/fallback sources;
- survives blocked/down providers where possible;
- produces a professional daily report;
- emails the report to `abhayv7272@gmail.com`;
- can run on GitHub Actions.

The original long FII/DII design specification is preserved in `docs/original-fii-dii-spec.txt`.

## Architecture built

### Data and source layer

- Yahoo/yfinance price adapter
- NSE index archive fallback
- Yahoo chart fallback
- NSE/nselib option and futures archive
- NSE F&O bhavcopy fallback with modern UDiFF normalization
- Participant OI via nselib and direct NSE archive fallback
- India VIX via NSE and Yahoo fallback
- FII/DII cash via NSE and Groww fallback
- Cross-market context via yfinance and direct Yahoo chart fallback
- Retry, timeouts, last-good cache, staleness policy, SHA-256 provenance
- Atomic writes and concurrent-run file lock
- Critical freshness and date matching

### Historical data

Current compact local stores contain 495 unique dates each for:

- EOD NIFTY option features
- NIFTY futures features
- FII/DII/Client/Pro participant OI features

Raw millions of option rows are aggregated into PCR, change-OI imbalance, walls, build/unwind walls, max pain, ATM straddle, concentration, futures basis/OI/volume/spread, and rolling derivatives features.

### Models and validation

Many price-only, technical, multi-asset, regime, meta-label, option/futures, participant, and full combinations were tested. Selection uses chronological development folds and a later block. Weak combinations are rejected.

A hard audit discovered missing sessions and an unlabeled-row target bug. The earlier optimistic 64.13%/91.67% derivative result is revoked.

Current corrected derivative candidate:

- 493 labeled sessions
- 99 later sessions
- 54.55% all-session accuracy
- 55.51% balanced accuracy
- 35 selected signals
- 60.00% selected accuracy
- negative after 3/6/10-bps cost stress

Therefore no model currently passes the production-promotion gate.

## Current authoritative decision policy

The production decision is **WAIT / NO TRADE** unless all gates pass:

1. fresh/date-matched price, options and futures;
2. weighted data-quality threshold;
3. specialist feature date equals session date;
4. no verified high-impact event block;
5. raw confidence passes the frozen gate;
6. at least 80 later sessions;
7. at least 58% all-session accuracy;
8. at least 30 selected signals;
9. at least 65% selected accuracy;
10. positive return after 10-bps cost stress.

A high raw UP/DOWN class probability is diagnostic, not a trade authorization.

## Ultra-hard audit corrections

See `reports/ultra_hard_audit.md`. Major fixes include:

- explicit historical-date future leakage;
- 37 omitted option sessions repaired from bhavcopies;
- final unlabeled target wrongly becoming DOWN;
- stale pivot/S1/R1 calculation;
- broken modern bhavcopy fallback;
- fallback traded-contract versus traded-quantity mismatch;
- partial participant row overwrite;
- model feature-family reconstruction mismatch;
- absent research-promotion gate;
- specialist/session mismatch;
- cached critical data permitting trades;
- historical cache poisoning;
- business-day staleness;
- non-atomic writes;
- concurrent run race;
- event gate not wired;
- understated first-trade drawdown;
- rejected model moving weekly centre;
- optimized-Python assert validation;
- corrupt manifest errors being ignored.

Automated regression tests, compile checks, critical Ruff checks, Bandit high-severity scan, real fallback parity and two-run reproducibility passed at handoff.

## Professional output

`run_production.py --date auto` creates:

- `data/hub/latest_manifest.json`
- timestamped evidence under `data/hub/runs/`
- compact history updates
- `reports/daily/<session>_professional_report.md`
- `reports/daily/<session>_professional_report.json`

The report includes:

- final gated decision;
- diagnostic class score;
- data/model/event gate status;
- corrected D+1 pivot/support/resistance;
- bull, bear and trap paths;
- neutral ATR weekly risk map when model is rejected;
- long/short/swing/investment context;
- what not to do;
- source health and hashes;
- model evidence and risk warning.

## GitHub Actions and email

Workflow: `.github/workflows/nifty-9pm-report.yml`

- Scheduled at `30 15 * * 1-5` UTC = approximately 9 PM IST.
- Manual `workflow_dispatch` supported.
- Tests run first.
- Production pipeline runs only if tests pass.
- Success or failure email is prepared.
- Report goes to `abhayv7272@gmail.com`.
- SMTP credentials must be GitHub Secrets.
- Compact state/reports are committed; raw runs are Actions artifacts.

See `GITHUB_SETUP.md` and `SECRETS_CHECKLIST.md`.

## Important financial safety position

This project is research/decision support, not personalized investment advice and not a guarantee. It must not force BUY/SELL to meet an accuracy target. Derivatives can produce rapid losses. Missing/stale/conflicting evidence must become WAIT. Long-term investment cannot be decided solely by a next-day derivatives model.

## Recommended next development

- Add a verified event-calendar provider or maintained `data/event_calendar.csv`.
- Collect forward 10/15-minute option-chain snapshots.
- Add licensed/broker bid-ask, premium and Greeks if available.
- Accumulate at least 100 selected forward signals.
- Re-run frozen promotion checks without tuning on confirmation data.
- Keep the promotion gate fail-closed.
