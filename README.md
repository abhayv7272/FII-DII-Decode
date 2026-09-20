# NIFTY Decision Lab

A VS Code-ready, leakage-safe market research app for:

- next-session **UP / FLAT / DOWN** probabilities;
- confidence-gated **WAIT / NO TRADE** behavior;
- support, resistance, pivot and ATR-based scenario zones;
- five-session (Monday–Friday style) volatility/risk map;
- optional dated FII/DII, India VIX, PCR and participant-OI context;
- chronological unseen validation and downloadable decision snapshots.

> **No model can honestly guarantee 80% live accuracy.** This app interprets “80% mode” as a *selective validation target*: it searches the unseen validation block for a confidence threshold reaching the desired precision with minimum sample size. If none exists, it uses a conservative fallback gate. The app always displays coverage and sample count.

## Run in VS Code

```bash
cd market_predictor
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open the URL printed by Streamlit (normally `http://localhost:8501`).

## Inputs

### Price CSV

```csv
Date,Open,High,Low,Close,Volume
2026-09-17,25000,25120,24880,25070,300000
```

At least **300 completed sessions** are required; 5–10 years are preferred. Yahoo Finance download is built in (`^NSEI`).

### Optional context CSV

Use `Date` plus any numeric columns. Example: `data/sample_context.csv`.

Each row must contain only information actually available at that day's close / decision time. Never put D+1 open, high, low or close on row D. Useful columns include:

- `FII_Cash_Cr`, `DII_Cash_Cr`
- `India_VIX`, `PCR_OI`
- `Pro_Index_Futures_Net`, `FII_Index_Futures_Net`
- call/put wall distances and pre-open breadth (only if correctly timestamped)

Context is exact-date joined and prefixed internally with `ctx_`.

## Model design

- Core features: lagged returns, gap, range/body, close location, RSI, moving-average distance, realized volatility, ATR, volume z-score and optional context.
- Technical research engine: SMA/EMA distance, RSI, ROC, stochastic, Williams %R, MACD, Bollinger position/width, CCI, ADX/+DI/-DI, ATR, Parkinson/upside/downside volatility, OBV, MFI, CMF, volume z-score, range location and wick/body structure.
- The same compact indicator families can be generated for Bank Nifty, NIFTY IT, Sensex, India VIX and timing-safe lagged global assets.
- Correlation pruning is fit on training data only. A 287-feature blind model scored 51.01% on the later test versus 53.44% for the compact research baseline, so the all-indicator model was correctly rejected. Indicators remain clustered decoder evidence rather than receiving duplicate votes.
- Target: D+1 close return; classes use configurable FLAT band.
- Primary direction model: strict binary next-close direction using logistic regression, random forest, extra trees and histogram gradient boosting.
- Split: earliest 60% training, middle 20% calibration, latest 20% untouched test.
- Gate: selected only on the calibration block; low-confidence latest calls become WAIT.
- Earlier compact close-to-close research result: 53.44% on all days and 66.67% on 24 selected signals. It is retained for comparison only, not promoted as a live trading model.
- Secondary three-class model supplies UP/FLAT/DOWN range context.
- Final refit: after computing untouched-test metrics, the frozen architecture refits on all labeled history for the current forecast.

## Tests

```bash
pytest -q
```

The included leakage test changes the last close and verifies that the previous row's features do not change.

## One-command 9 PM production pipeline

```bash
python run_production.py --date auto
```

This performs: source discovery → retries → primary/fallback selection → session-date validation → SHA-256 snapshotting → last-good cache → weighted quality gate → historical feature update → frozen specialist prediction → next-day and five-session professional Markdown/JSON report.

Outputs:

- `data/hub/latest_manifest.json`: selected sources, status, dates, hashes and quality score;
- `data/hub/runs/<timestamp>/`: immutable run snapshots;
- `data/hub/last_good/`: bounded stale-data fallback;
- `reports/daily/<session>_professional_report.md` and `.json`;
- `config/data_sources.json`: readable source-priority and safety policy.

Fallback priorities include Yahoo/yfinance, NSE index archive and Yahoo chart for prices; NSE contract archive and F&O bhavcopy for options/futures; nselib and direct NSE participant CSV; NSE and Yahoo VIX; NSE and Groww FII/DII; yfinance and direct Yahoo chart cross-market data. Cached data receives reduced quality credit, future-dated/mismatched payloads are rejected, and critical-data failure forces WAIT.

Schedule at 21:00 IST on weekdays:

```cron
0 21 * * 1-5 cd /path/market_predictor && .venv/bin/python run_production.py --date auto >> data/hub/production.log 2>&1
```

Windows Task Scheduler can call `scripts/run_9pm_pipeline.ps1`; Linux/macOS can call `scripts/run_9pm_pipeline.sh`.

No public fallback system can guarantee uptime or future schema compatibility. Adapters fail closed, preserve errors, and require maintenance when a provider changes its API/terms.

## Free NSE forward collection

The project now preserves raw NSE-derived files, capture timestamps, SHA-256 hashes, a manifest and one leakage-safe EOD research row.

```bash
# 09:00–09:14:59 IST only; collector rejects other times
python -m src.collector preopen --date 2026-09-21

# Run periodically during the live session (for example every 15 minutes)
python -m src.collector intraday --date 2026-09-21

# Run after reports are available, preferably around 21:00 IST
python -m src.collector eod --date 2026-09-21
```

Convenience scripts are in `scripts/`. Linux cron examples:

```cron
5 9 * * 1-5  cd /path/market_predictor && .venv/bin/python -m src.collector preopen
*/15 9-15 * * 1-5 cd /path/market_predictor && .venv/bin/python -m src.collector intraday
0 21 * * 1-5 cd /path/market_predictor && .venv/bin/python -m src.collector eod
```

Outputs:

- `data/forward/YYYY-MM-DD/HHMMSS/`: immutable-style raw snapshots and manifest;
- `data/forward/collection_log.csv`: source status and hashes;
- `data/eod_research_snapshots.csv`: one quality-gated EOD row per session;
- `data/model_feature_store.csv`: participant, breadth, cross-market and intraday option-migration features.

The EOD collector also stores timing-safe context for Bank Nifty/IT/pharma, ten NIFTY heavyweights, Asian indices, and the previous completed US/global session (SPY, QQQ, US VIX, dollar index, crude, gold and USDINR). Same-date US/global daily candles are intentionally rejected at 21:00 IST because they may still be incomplete.

The intraday collector produces PCR, OI/change-OI totals, IV medians, option walls, build walls and first-to-last wall migration. At least two captures in one session are required before migration features become ready.

The EOD collector also stores NIFTY futures expiry, close, spot-futures basis, open interest, change in OI, volume and near-expiry OI share. The decoder classifies fresh-long, fresh-short, short-covering and long-unwinding states.

## Executable and meta-label audit

`src/execution_model.py` separates two targets:

- overnight gap: D close to D+1 open;
- executable intraday move: D+1 open to D+1 close.

The intraday audit uses a strict 60/10/10/20 chronology: base-model training, meta-model training, gate calibration, and later test. It includes trend/volatility regime splits and 3/6/10-bps transaction-cost stress. Current later-test intraday directional accuracy is 55.26%, but no meta threshold met the minimum precision/sample rule, so the result remains WAIT rather than manufacturing a selective claim. The gap model scored 55.47%, approximately equal to its UP base rate, and was rejected as non-informative.

## Historical derivatives specialist

`fetch_historical_derivatives.py` reconstructs timing-safe EOD NIFTY option-chain features from official contract-wise archive data without retaining millions of raw rows. The current local dataset contains 458 option sessions and 495 futures sessions from Sep 2024–Sep 2026. `fetch_participant_history.py` added 458 complete participant-OI sessions.

A later hardening audit found that 37 sessions had been omitted when the contract API returned blank underlying values, and the final unlabeled session had been incorrectly converted to DOWN in one optimizer. The missing sessions were repaired from official bhavcopies, all three derivative stores now contain 495 unique sessions, and the optimizer was rerun with 493 genuinely labeled rows.

Corrected result: the development-selected price-plus-derivatives logistic candidate scored 54.55% accuracy and 55.51% balanced accuracy on 99 later sessions. Its frozen gate selected 35 signals at 60.00% accuracy, but returns were negative after 3/6/10-bps stress (10-bps net approximately -3.99%). It therefore fails the production promotion gate. Raw latest class probability is diagnostic only; the live production decision is WAIT. See `reports/derivative_specialist.json` and `reports/model_registry.json`.

## Systematic combination optimizer

Run `python optimize_combinations.py` to compare pre-defined feature groups and model families using expanding development folds. Feature/model selection and confidence gates are frozen from development OOF predictions before the later block is scored. `python optimize_regimes.py` then tests a small pre-defined set of bull/bear, volatility, direction and fixed-confidence policies with minimum sample and fold-stability rules.

Latest result: the multi-asset top-120 Random Forest won development selection but scored only 53.85% on the later block; the regime-filtered challenger scored 54.05%; both were below the 55.26% compact execution champion and were rejected. No OOF confidence gate reached even 60% with at least 40 signals. See `reports/model_registry.json`, `reports/combination_ranking.csv` and `reports/regime_ranking.csv`.

NSE or convenience data sources may change endpoints, revise data, or temporarily block automated access. Failed/empty inputs are recorded instead of silently fabricated. Free-source collection is appropriate for research; production should use licensed, timestamped feeds and respect source terms/rate limits.

## Production roadmap

1. Continue timestamped exchange collection and consider a licensed source for production reliability.
2. Add NSE holiday calendar and strict 9 PM IST snapshot scheduler.
3. Store pre-open and intraday option-chain snapshots with source/capture timestamps and hashes.
4. Add expanding-window walk-forward backtest, probability calibration and regime drift alarms.
5. Paper trade at least 200–260 independent sessions; report accuracy, balanced accuracy, coverage, costs, drawdown and skipped-day reasons.
6. Freeze model/rules before forward confirmation. Never tune repeatedly on the same holdout.

## Safety

This software is for education/research, not investment advice. Derivatives can cause rapid, substantial losses. Validate data and use paper trading before any capital deployment.
