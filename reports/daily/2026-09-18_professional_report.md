# NIFTY Professional Decision Report — 2026-09-18

**Generated:** 2026-09-20T05:48:56.911304+05:30
**Data quality:** 60%
**Data gate:** **FAIL-CLOSED**
**Final decision:** **WAIT / NO TRADE**

**Event-calendar status:** NO_VERIFIED_CALENDAR — verified calendar unavailable; check manually
**RESEARCH PROMOTION GATE FAILED:** corrected holdout/cost metrics do not support a live directional trade.
**Diagnostic only:** raw class probability is not a calibrated profit probability and is excluded from the weekly centre.
**DATA GATE FAIL-CLOSED:** critical price/options/futures were not all fresh/date-matched, compact history failed, or overall quality was below threshold.

## Executive view

- Specialist direction: **UP**
- UP/DOWN probability: **87.94% / 12.06%**
- Model confidence: **87.94%**; frozen gate: **75%**
- Prediction/session match: **True**
- Critical fresh/date-matched data: **nifty_price=False, nifty_options_eod=False, nifty_futures_eod=False**
- Compact history update ok: **True**
- Trading stance: **NO DIRECTIONAL POSITION**
- Swing stance: Do not initiate a new swing position until the confidence/data gate and price trigger both pass.
- Investment context: Fresh long-term investment should be deferred or evaluated fundamentally; index is below its 200-day trend.

## Key levels

- Resistance trigger: **23,394.83**
- Pivot: **23,340.72**
- Support trigger: **23,292.28**
- 20-day support/resistance: **23,116.10 / 24,378.60**
- ATR(14): **195.57 points**

## Conditional playbook

### Bull path
Support/pivot hold → close above 23,394.83 → retest holds → only then long continuation is valid.
### Bear path
Resistance rejection → close below 23,292.28 → failed reclaim → only then short continuation is valid.
### Trap rule
A wick/sweep alone is not entry confirmation. Wait for a completed candle and follow-through.

## Monday–Friday risk map

| date       |   session |   expected_center |   lower_risk_band |   upper_risk_band |
|:-----------|----------:|------------------:|------------------:|------------------:|
| 2026-09-21 |         1 |          23346.40 |          23150.83 |          23541.97 |
| 2026-09-22 |         2 |          23346.40 |          23069.83 |          23622.98 |
| 2026-09-23 |         3 |          23346.40 |          23007.67 |          23685.13 |
| 2026-09-24 |         4 |          23346.40 |          22955.26 |          23737.54 |
| 2026-09-25 |         5 |          23346.40 |          22909.10 |          23783.70 |

## What not to do

- Do not trade below the confidence or data-quality gate.
- Do not chase an abnormal opening gap; wait for a new range.
- Do not treat max pain/OI wall as a guaranteed target.
- Do not average a losing leveraged position.
- Do not use this next-day model as the sole basis for long-term investment.

## Data-source health

| Dataset           | Selected source   | Status   | As-of      |   Rows |   Stale days | Error                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
|:------------------|:------------------|:---------|:-----------|-------:|-------------:|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| nifty_price       | last_good_cache   | cached   | 2026-09-18 |   2467 |              | yahoo_yfinance: nifty_price failed validation from yahoo_yfinance; nse_index_archive:  Resource not available MSG: HTTPSConnectionPool(host='www.nseindia.com', port=443): Max retries exceeded with url: /reports-indices-historical-index-data (Caused by SSLError(SSLZeroReturnError(6, 'TLS/SSL connection has been closed (EOF) (_ssl.c:992)'))); yahoo_chart: HTTPSConnectionPool(host='query1.finance.yahoo.com', port=443): Max retries exceeded with url: /v8/finance/chart/%5ENSEI?period1=1474502400&period2=1789948800&interval=1d&events=history (Caused by SSLError(SSLZeroReturnError(6, 'TLS/SSL connection has been closed (EOF) (_ssl.c:992)'))) |
| nifty_options_eod | last_good_cache   | cached   | 2026-09-18 |   1700 |            0 | nselib_contract_archive:  Invalid parameters : NSE error : HTTPSConnectionPool(host='www.nseindia.com', port=443): Max retries exceeded with url: /report-detail/fo_eq_security (Caused by SSLError(SSLZeroReturnError(6, 'TLS/SSL connection has been closed (EOF) (_ssl.c:992)'))); nse_bhavcopy: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))                                                                                                                                                                                                                                                                   |
| nifty_futures_eod | last_good_cache   | cached   | 2026-09-18 |      3 |            0 | nselib_contract_archive:  Invalid parameters : NSE error:HTTPSConnectionPool(host='www.nseindia.com', port=443): Max retries exceeded with url: /report-detail/fo_eq_security (Caused by SSLError(SSLZeroReturnError(6, 'TLS/SSL connection has been closed (EOF) (_ssl.c:992)'))); nse_bhavcopy: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))                                                                                                                                                                                                                                                                     |
| participant_oi    | last_good_cache   | cached   | 2026-09-18 |      5 |            0 | nselib_participant_archive: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')); direct_nse_archive: HTTPSConnectionPool(host='nsearchives.nseindia.com', port=443): Max retries exceeded with url: /content/nsccl/fao_participant_oi_18092026.csv (Caused by SSLError(SSLZeroReturnError(6, 'TLS/SSL connection has been closed (EOF) (_ssl.c:992)')))                                                                                                                                                                                                                                                                   |
| india_vix         | last_good_cache   | cached   | 2026-09-18 |      1 |            0 | nse_vix_archive:  Resource not available MSG: HTTPSConnectionPool(host='nsewebsite-staging.nseindia.com', port=443): Max retries exceeded with url: /report-detail/eq_security (Caused by SSLError(SSLZeroReturnError(6, 'TLS/SSL connection has been closed (EOF) (_ssl.c:992)'))); yahoo_vix_chart: HTTPSConnectionPool(host='query1.finance.yahoo.com', port=443): Max retries exceeded with url: /v8/finance/chart/%5EINDIAVIX?period1=1789084800&period2=1789776000&interval=1d&events=history (Caused by SSLError(SSLZeroReturnError(6, 'TLS/SSL connection has been closed (EOF) (_ssl.c:992)')))                                                           |
| fii_dii_cash      | last_good_cache   | cached   | 2026-09-18 |      2 |            0 | nse_fiidii_api: HTTPSConnectionPool(host='www.nseindia.com', port=443): Max retries exceeded with url: / (Caused by SSLError(SSLZeroReturnError(6, 'TLS/SSL connection has been closed (EOF) (_ssl.c:992)'))); groww_public_table: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)>                                                                                                                                                                                                                                                                                                                                                           |
| cross_market      | last_good_cache   | cached   | 2026-09-18 |     25 |            0 | yfinance_multi_asset: cross_market failed validation from yfinance_multi_asset; yahoo_chart_multi_asset: HTTPSConnectionPool(host='query1.finance.yahoo.com', port=443): Max retries exceeded with url: /v8/finance/chart/%5ENSEBANK?period1=1788393600&period2=1789776000&interval=1d&events=history (Caused by SSLError(SSLZeroReturnError(6, 'TLS/SSL connection has been closed (EOF) (_ssl.c:992)')))                                                                                                                                                                                                                                                         |

## Model evidence

- Later research test: 54.55% accuracy across 99 sessions.
- Selected research sample: 35 signals, 60.00% observed accuracy; this sample is provisional.
- Current report automatically becomes WAIT if critical data, compact-history, date, event, confidence or research-promotion gates fail.

## Risk notice

Research/decision-support only; not personalized investment advice. Futures and options can cause rapid losses. Verify exchange data, liquidity, costs and your risk capacity before any trade.