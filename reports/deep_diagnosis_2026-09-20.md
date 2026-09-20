# Ultra-Hard Deep Diagnosis — 2026-09-20 IST

## Scope

Deep bug/security/safety pass across the root production project after expanding the uploaded GitHub package. Focus areas:

- fail-closed financial safety;
- stale/future/date-mismatched market data;
- persisted compact state versus raw Actions artifacts;
- GitHub Actions report/email sequence;
- cache corruption and atomic writes;
- model/session matching and research-promotion gate;
- dependency/security scan;
- UI/report language that could overstate production readiness.

## Diagnostics run

- `python -m pytest -q tests` → **19 passed**
- `python -m compileall -q .` → **passed**
- `ruff check --select E9,F63,F7,F82,B,S` excluding tests/run artifacts → **passed**
- `bandit -r . -lll` excluding tests/run artifacts → **passed**
- `pip-audit -r requirements.txt` → **No known vulnerabilities found**
- `python run_production.py --date auto` → completed, **WAIT / NO TRADE**
- `python verify_reproducibility.py --runs 2 --date auto` → **PASS**

Local provider access to NSE/Yahoo/Groww remained blocked by TLS/provider errors, so the pipeline used last-good cache and correctly kept the data gate fail-closed.

## Bugs fixed in this pass

1. **Committed manifest pointed only to ignored raw run paths**
   - Problem: `latest_manifest.json` could reference `data/hub/runs/...` files, which are intentionally not committed. A fresh clone could not rebuild the latest report from compact state.
   - Fix: `SourceResult` now includes `cache_path`; professional report reconstruction falls back to committed compact `data/hub/last_good/*` and truncates price history at the manifest session to avoid future leakage.

2. **Corrupt cache metadata could crash production**
   - Problem: corrupt `data/hub/last_good/*.json` metadata was parsed directly.
   - Fix: safe JSON metadata loader records the corrupt metadata as a failed source reason and fails closed instead of crashing or silently using bad metadata.

3. **Critical raw payload validation was too shallow**
   - Problem: options/futures validators only checked row counts, so malformed schemas or missing underlying values could be marked fresh before summary failure.
   - Fix: strict validators now require critical schema columns, CE/PE option presence, numeric OHLC/OI/volume/underlying fields, participant client coverage, VIX/cash/cross-market structure.

4. **History-update failure was not an explicit production gate input**
   - Problem: a fresh source plus compact feature-store write failure could still show the raw data gate as passed until model date mismatch caught it later.
   - Fix: manifest now records `history_update_ok`; `prediction_allowed` requires it; report exposes this gate.

5. **Price evidence fallback could leak later bars if compact cache was reused naively**
   - Fix: report price loading always re-truncates compact cache at `manifest.session_date` and verifies the final candle date equals the session.

6. **Dependency vulnerability in test stack**
   - Problem: `pytest>=8,<9` resolved to a version flagged by `pip-audit`.
   - Fix: upgraded requirement to `pytest>=9.0.3,<10`; tests pass with pytest 9.1.1.

7. **Silent participant repair failure**
   - Problem: `repair_historical_gaps.py` swallowed participant repair exceptions with `except: pass`.
   - Fix: participant repair failures are now logged and written to `reports/participant_repair_failures.csv` when present.

8. **Probability serialization and static bug warnings**
   - Problem: `zip()` calls in probability mapping did not enforce strict class/probability length matching, and numpy scalar keys/values could leak to JSON/UI.
   - Fix: strict zips and explicit Python `str`/`float` conversions.

9. **App wording could imply a production champion exists**
   - Problem: Streamlit displayed “Production champion retained” even when registry says no production model is approved.
   - Fix: UI now explicitly says production champion is **none** and authoritative policy remains **WAIT / NO TRADE**.

10. **Rejected/non-actionable research probabilities could still move the app weekly centre**
    - Problem: app risk-map centre used research probabilities even when gates were not actionable.
    - Fix: app uses a neutral weekly risk map unless both binary and three-class research gates pass.

11. **Workflow compact-state push ambiguity**
    - Problem: generic `git push` could be ambiguous in detached/branch contexts.
    - Fix: workflow pushes compact report commits explicitly to `HEAD:${GITHUB_REF_NAME}`.

## Current authoritative production result from this pass

- Session: **2026-09-18**
- Data quality: **60%**
- Critical fresh/date-matched data: **false** locally because live providers were blocked and cache was used
- Compact history update: **true**
- Research promotion gate: **failed**
- Final decision: **WAIT / NO TRADE**

The raw latest class score remains diagnostic only and is not a calibrated profit probability.

## Remaining operational/manual items

1. Merge the PR so the workflow exists on the default branch and can be run from GitHub Actions.
2. Add GitHub Actions secrets: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`.
3. Run `workflow_dispatch` after merge.
4. If GitHub-hosted runners remain blocked by NSE/Yahoo, use a self-hosted Indian runner or a licensed market-data adapter; do not relax freshness gates.
