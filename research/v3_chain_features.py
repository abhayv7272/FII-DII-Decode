#!/usr/bin/env python3
"""Stage-5a: same-date EOD option-chain aggregate features from F&O bhavcopy.

Point-in-time contract: every feature for trade date D comes only from D's
bhavcopy rows and D's index close — identical timing discipline to the daily
production pipeline (which fetches the same-date chain after close).

Features (prefix oc_):
  pcr_oi / pcr_doi          total & change-in-OI put/call ratios (nearest expiry)
  pcr_near_atm              PCR using strikes within +-2% of spot
  maxpain_dist_pct          (spot - max pain) / spot, %
  put_wall_dist_pct         distance spot->highest-PE-OI strike below spot, %
  call_wall_dist_pct        distance spot->highest-CE-OI strike above spot, %
  wall_build_pct            dOI at immediate support minus dOI at immediate
                            resistance, as % of total chain dOI (signed)
  near_put_doi_pct          dOI of puts within +-2% of spot as % of |total dOI|
  near_call_doi_pct         same for calls
  straddle_pct              ATM CE close + PE close, % of spot (implied move)
  dte_actual                calendar days to nearest expiry
  is_weekly_expiry          nearest expiry is the standard weekly expiry
  oi_total                  total call+put OI nearest expiry
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from bhavcopy_to_option_chain import _extract, _rows, load_index_closes  # noqa: E402


def chain_features(zip_path: Path, symbol: str, closes: dict) -> dict | None:
    """Aggregate one bhavcopy file for the nearest non-expired expiry."""
    by_expiry: dict[date, dict[float, dict]] = {}
    trade_dates: set[date] = set()
    for row in _rows(zip_path):
        parsed = _extract(row, symbol)
        if parsed is None:
            continue
        trade_date, expiry, strike, option_type, leg = parsed
        trade_dates.add(trade_date)
        by_expiry.setdefault(expiry, {}).setdefault(strike, {})[option_type] = leg
    if not by_expiry or len(trade_dates) != 1:
        return None
    trade_date = trade_dates.pop()
    spot = closes.get(trade_date)
    if spot is None:
        return None
    future = sorted(e for e in by_expiry if e > trade_date)
    # near expiry == smallest expiry strictly after today? NSE chain includes
    # expiry==today snapshots intraday; EOD convention: include today if present
    today = sorted(e for e in by_expiry if e == trade_date)
    nearest = today[0] if today else (future[0] if future else None)
    if nearest is None:
        return None
    chain = by_expiry[nearest]

    strikes = sorted(chain)
    ce_oi = {s: chain[s].get("CE", {}).get("openInterest", 0.0) for s in strikes}
    pe_oi = {s: chain[s].get("PE", {}).get("openInterest", 0.0) for s in strikes}
    ce_doi = {s: chain[s].get("CE", {}).get("changeinOpenInterest", 0.0) for s in strikes}
    pe_doi = {s: chain[s].get("PE", {}).get("changeinOpenInterest", 0.0) for s in strikes}
    ce_px = {s: chain[s].get("CE", {}).get("lastPrice", 0.0) for s in strikes}
    pe_px = {s: chain[s].get("PE", {}).get("lastPrice", 0.0) for s in strikes}

    tot_ce, tot_pe = sum(ce_oi.values()), sum(pe_oi.values())
    tot_dce, tot_dpe = sum(ce_doi.values()), sum(pe_doi.values())
    if tot_ce <= 0 or tot_pe <= 0:
        return None

    near = [s for s in strikes if abs(s - spot) / spot <= 0.02]
    near_ce, near_pe = sum(ce_oi[s] for s in near), sum(pe_oi[s] for s in near)
    near_dce, near_dpe = sum(ce_doi[s] for s in near), sum(pe_doi[s] for s in near)

    below = [s for s in strikes if s < spot and pe_oi[s] > 0]
    above = [s for s in strikes if s > spot and ce_oi[s] > 0]
    put_wall = max(below, key=lambda s: pe_oi[s]) if below else None
    call_wall = min(above, key=lambda s: -ce_oi[s]) if above else None
    call_wall = max(above, key=lambda s: ce_oi[s]) if above else None

    # max pain: strike minimising total intrinsic payout to option holders
    def pain(k):
        return sum(ce_oi[s] * max(k - s, 0) for s in strikes) + \
            sum(pe_oi[s] * max(s - k, 0) for s in strikes)
    max_pain = min(strikes, key=pain) if strikes else None

    atm = min(strikes, key=lambda s: abs(s - spot)) if strikes else None
    straddle = (ce_px.get(atm, 0.0) + pe_px.get(atm, 0.0)) if atm else 0.0

    total_abs_doi = abs(tot_dce) + abs(tot_dpe)
    wall_build = (
        (pe_doi.get(put_wall, 0.0) - ce_doi.get(call_wall, 0.0)) / total_abs_doi * 100
        if put_wall and call_wall and total_abs_doi else np.nan
    )

    return {
        "date": pd.Timestamp(trade_date),
        "oc_pcr_oi": tot_pe / tot_ce,
        "oc_pcr_doi": (tot_dpe / tot_dce) if tot_dce else np.nan,
        "oc_pcr_near_atm": (near_pe / near_ce) if near_ce else np.nan,
        "oc_maxpain_dist_pct": (spot - max_pain) / spot * 100 if max_pain else np.nan,
        "oc_put_wall_dist_pct": (spot - put_wall) / spot * 100 if put_wall else np.nan,
        "oc_call_wall_dist_pct": (call_wall - spot) / spot * 100 if call_wall else np.nan,
        "oc_wall_build_pct": wall_build,
        "oc_near_put_doi_pct": (near_dpe / total_abs_doi * 100) if total_abs_doi else np.nan,
        "oc_near_call_doi_pct": (near_dce / total_abs_doi * 100) if total_abs_doi else np.nan,
        "oc_straddle_pct": straddle / spot * 100 if spot else np.nan,
        "oc_dte_actual": (nearest - trade_date).days,
        "oc_is_expiry": float(nearest == trade_date),
        "oc_oi_total": tot_ce + tot_pe,
        "spot": spot,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bhavcopy-dir", default="/home/user/historical/fo_bhavcopy")
    parser.add_argument("--index-close-dir", default="/home/user/historical/index_close")
    parser.add_argument("--out", default="/home/user/features/chain_features.csv")
    args = parser.parse_args()

    closes = load_index_closes(Path(args.index_close_dir), "Nifty 50")
    rows = []
    files = sorted(Path(args.bhavcopy_dir).glob("*.zip"))
    for path in files:
        try:
            feats = chain_features(path, "NIFTY", closes)
        except Exception as exc:  # keep going; count failures
            print(f"skip {path.name}: {exc}", file=sys.stderr)
            feats = None
        if feats:
            rows.append(feats)

    out = pd.DataFrame(rows).drop_duplicates("date").sort_values("date")
    out.to_csv(args.out, index=False, float_format="%.6f")
    print(f"wrote {args.out}: {len(out)} dates from {len(files)} files")
    print(out.head(3).to_string())
    print(out.describe().loc[["mean", "std", "min", "max"]].T.round(3).to_string())


if __name__ == "__main__":
    main()
