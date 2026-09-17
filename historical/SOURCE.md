# Compact historical research data

These CSVs are a compact, reproducible subset of the public
`sahilempire/groww-market-data` mirror pinned at commit
`7d481cf1fcffe44be68852892028195c4f12dddd`.

They are committed so Arena/session resets do not wipe the minimum data needed
for v3/v4 research gates.  The bulky raw F&O bhavcopy ZIPs and per-date option
chain snapshots are intentionally not committed.

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
- `manifest.json` — source commit and SHA-256 checksums.

Educational research only; not investment advice.
