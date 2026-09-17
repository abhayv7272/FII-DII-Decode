# Compact historical research data

These CSVs are a compact, reproducible subset of the public
`sahilempire/groww-market-data` mirror pinned at commit
`7d481cf1fcffe44be68852892028195c4f12dddd`, plus the V7 intraday and
PDF-level seed data described below.

They are committed so Arena/session resets do not wipe the minimum data needed
for v3/v4/v5/v6/v7 research gates.  The bulky raw F&O bhavcopy ZIPs, per-date
option-chain snapshots, and raw 1-minute intraday files are intentionally not
committed.

Files:

- `participant_oi.csv` — NSE participant-wise open interest, 2023-08-04 to
  2026-09-04, with all participant rows plus TOTAL.
- `participant_vol.csv` — NSE participant-wise volume history on the same basis.
- `nifty_ohlc.csv` — canonical NIFTY 50 OHLC consolidated from NSE
  `ind_close_all_YYYYMMDD.csv` files in the pinned mirror; this is the target
  source used by the published OI backtests.
- `nifty_ohlc_long.csv` — long OpenChart/Groww NIFTY 50 daily OHLC history
  through 2026-09-04 for price-regime research only (not the canonical target
  source for published OI backtests).
- `chain_features.csv` — same-date EOD option-chain aggregate features rebuilt
  from F&O bhavcopy via `research/v3_chain_features.py`.
- `nifty_10m.csv` / `nifty_15m.csv` — 10-minute and 15-minute NIFTY 50
  intraday OHLCV bars from 2017-04-03 to 2026-09-17, derived from the public
  `technovusin/nifty50-historical-data` 1-minute archive via
  `research/build_intraday_candles.py`. Raw 1-minute CSVs are kept outside Git;
  each intraday CSV has a `.manifest.json` file with raw-file hashes.
- `institutional_levels_pdf_2026.csv` — 140 manually audited, date-stamped
  NIFTY levels from the supplied `Market_Analysis_03_August_2026_Decoded-
  combined.pdf`; 60 rows are tagged as explicit institutional/institutional-zone
  references from the PDF wording.
- `manifest.json` — source commit and SHA-256 checksums.

Educational research only; not investment advice.
