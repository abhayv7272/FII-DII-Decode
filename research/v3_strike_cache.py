#!/usr/bin/env python3
"""One-time cache: per-(date, expiry, strike) NIFTY option OI table from bhavcopy.

Keeps strikes within +-8% of same-day spot to stay compact. Used by the
level-selection grid (stage 6) and any future chain-derived features.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from bhavcopy_to_option_chain import _extract, _rows, load_index_closes  # noqa: E402


def extract_strikes(zip_path: Path, symbol: str, closes: dict, band=0.08) -> list[dict]:
    per_key: dict[tuple, dict] = {}
    trade_dates: set[date] = set()
    for row in _rows(zip_path):
        parsed = _extract(row, symbol)
        if parsed is None:
            continue
        trade_date, expiry, strike, option_type, leg = parsed
        trade_dates.add(trade_date)
        rec = per_key.setdefault((expiry, strike), {
            "expiry": expiry, "strike": strike,
            "ce_oi": 0.0, "ce_doi": 0.0, "pe_oi": 0.0, "pe_doi": 0.0,
            "ce_close": 0.0, "pe_close": 0.0,
        })
        side = "ce" if option_type == "CE" else "pe"
        rec[f"{side}_oi"] = leg.get("openInterest", 0.0)
        rec[f"{side}_doi"] = leg.get("changeinOpenInterest", 0.0)
        rec[f"{side}_close"] = leg.get("lastPrice", 0.0)
    if len(trade_dates) != 1:
        return []
    trade_date = trade_dates.pop()
    spot = closes.get(trade_date)
    if spot is None:
        return []
    rows = []
    for rec in per_key.values():
        s = rec["strike"]
        if abs(s - spot) / spot > band:
            continue
        rows.append({
            "date": trade_date.isoformat(),
            "expiry": rec["expiry"].isoformat(),
            "strike": s,
            "ce_oi": rec["ce_oi"], "ce_doi": rec["ce_doi"],
            "pe_oi": rec["pe_oi"], "pe_doi": rec["pe_doi"],
            "ce_close": rec["ce_close"], "pe_close": rec["pe_close"],
            "spot": spot,
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bhavcopy-dir", default="/home/user/historical/fo_bhavcopy")
    parser.add_argument("--index-close-dir", default="/home/user/historical/index_close")
    parser.add_argument("--out", default="/home/user/features/strike_table.csv.gz")
    args = parser.parse_args()

    closes = load_index_closes(Path(args.index_close_dir), "Nifty 50")
    frames = []
    files = sorted(Path(args.bhavcopy_dir).glob("*.zip"))
    for i, path in enumerate(files):
        try:
            rows = extract_strikes(path, "NIFTY", closes)
            if rows:
                frames.append(pd.DataFrame(rows))
        except Exception as exc:
            print(f"skip {path.name}: {exc}", file=sys.stderr)
        if i % 100 == 0:
            print(f"{i}/{len(files)}", flush=True)
    table = pd.concat(frames, ignore_index=True)
    table["date"] = pd.to_datetime(table["date"])
    table["expiry"] = pd.to_datetime(table["expiry"])
    table.to_csv(args.out, index=False, compression="gzip")
    print(f"wrote {args.out}: {len(table)} rows, {table['date'].nunique()} dates")


if __name__ == "__main__":
    main()
