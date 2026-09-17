#!/usr/bin/env python3
"""Stage-6: deep dive on option-chain support/resistance accuracy.

Published baseline (production v2 proxy, 60/40 OI/|+dOI| evidence, nearest of
top-3 levels, next-day OHLC proxy, +-0.05% touch band):
  685 tests, 49.20% hold — a coin flip.

Axes tested here, always fitted on dev and scrolled to val/confirm:
  L1 evidence mix w_oi in {0, .25, .5, .6, .75, 1}
  L2 expiry scope: nearest only vs all expiries summed
  L3 selection: argmax-evidence single level vs nearest-of-top3 (production)
  L4 distance band of the level from spot
Conditionals measured on the best config:
  OI-lean agreement, PCR tercile, vol tercile, days-to-expiry bucket.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

TOUCH = 0.05  # % band, matches production config
PERIODS = ("dev2023_24", "val2025", "confirm2026")
W_OI_GRID = (0.0, 0.25, 0.5, 0.6, 0.75, 1.0)


def load():
    strikes = pd.read_csv("/home/user/features/strike_table.csv.gz",
                          parse_dates=["date", "expiry"])
    mx = pd.read_csv("/home/user/features/v3_matrix2.csv", parse_dates=["date"])
    ohlc = mx[["date", "period", "y_cc"]].copy()
    # next-day OHLC from matrix is not stored; reconstruct from index_close-derived targets
    return strikes, mx


def select_level(day: pd.DataFrame, spot: float, kind: str, w_oi: float,
                 scope: str, mode: str, spot_ref: float):
    """Replicate production ranking with parameters."""
    d = day
    if scope == "nearest":
        nearest = d["expiry"].min()
        d = d[d["expiry"] == nearest]
    else:  # all expiries aggregated
        d = (d.groupby("strike", as_index=False)
             .agg(ce_oi=("ce_oi", "sum"), ce_doi=("ce_doi", "sum"),
                  pe_oi=("pe_oi", "sum"), pe_doi=("pe_doi", "sum")))
    if kind == "support":
        c = d[(d["strike"] < spot) & (d["pe_oi"] > 0)].copy()
        oi, doi = "pe_oi", "pe_doi"
    else:
        c = d[(d["strike"] > spot) & (d["ce_oi"] > 0)].copy()
        oi, doi = "ce_oi", "ce_doi"
    if c.empty:
        return None
    c["oi_c"] = c[oi] / max(c[oi].max(), 1.0)
    c["doi_c"] = c[doi].clip(lower=0) / max(c[doi].clip(lower=0).max(), 1.0)
    c["ev"] = w_oi * c["oi_c"] + (1 - w_oi) * c["doi_c"]
    top = c.nlargest(3, "ev")
    if mode == "argmax":
        return float(top.iloc[0]["strike"])
    if kind == "support":
        return float(top["strike"].max())   # nearest below spot
    return float(top["strike"].min())       # nearest above spot


def hold_test(df_days, picks, ohlc_next):
    """Score next-day hold for picks: dict[(date, kind)] -> strike."""
    rows = []
    for (d, kind), strike in picks.items():
        bar = ohlc_next.get(d)
        if bar is None:
            continue
        o, h, l, c = bar
        tested = l <= strike * (1 + TOUCH / 100) and h >= strike * (1 - TOUCH / 100)
        if not tested:
            continue
        held = (c >= strike) if kind == "support" else (c <= strike)
        rows.append({"date": d, "kind": kind, "strike": strike, "held": held})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="reports/v3_deep_dive")
    args = parser.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

    strikes = pd.read_csv("/home/user/features/strike_table.csv.gz",
                          parse_dates=["date", "expiry"])
    mx = pd.read_csv("/home/user/features/v3_matrix2.csv", parse_dates=["date"])

    # reconstruct next-day OHLC from the same consolidated source the replay uses
    import sys
    sys.path.insert(0, "src")
    from fiidii.backtest import load_ohlc
    ohlc = load_ohlc("/home/user/historical/index_close", symbol="NIFTY")
    ohlc["date"] = pd.to_datetime(ohlc["date"])
    ohlc = ohlc.sort_values("date").reset_index(drop=True)
    next_bar = {}
    dates = list(ohlc["date"])
    for i in range(len(ohlc) - 1):
        r = ohlc.iloc[i + 1]
        next_bar[ohlc.iloc[i]["date"]] = (r["open"], r["high"], r["low"], r["close"])

    period_map = mx.set_index("date")["period"].to_dict()
    comp_map = mx.set_index("date")["composite_approx"] if "composite_approx" in mx else None

    day_groups = dict(tuple(strikes.groupby("date")))
    results = []
    picks_by_config = {}
    for scope in ("nearest", "all"):
        for w_oi in W_OI_GRID:
            for mode in ("argmax", "top3nearest"):
                picks = {}
                for d, day in day_groups.items():
                    spot = float(day["spot"].iloc[0])
                    for kind in ("support", "resistance"):
                        strike = select_level(day, spot, kind, w_oi, scope, mode, spot)
                        if strike is not None:
                            picks[(d, kind)] = strike
                scored = hold_test(day_groups, picks, next_bar)
                if scored.empty:
                    continue
                scored["period"] = scored["date"].map(period_map)
                config = f"{scope}|w={w_oi}|{mode}"
                picks_by_config[config] = scored
                row = {"config": config}
                for p in PERIODS + ("full",):
                    sub = scored if p == "full" else scored[scored["period"] == p]
                    row[f"{p[:6]}_tests"] = len(sub)
                    row[f"{p[:6]}_hold"] = round(sub["held"].mean() * 100, 2) if len(sub) else np.nan
                results.append(row)
                print(config, {k: row[k] for k in ("full_tests", "full_hold")})

    res = pd.DataFrame(results)
    res.to_csv(out / "level_grid.csv", index=False)
    pd.set_option("display.width", 240)
    print("\n=== level grid sorted by dev hold ===")
    print(res.sort_values("dev202_hold", ascending=False).to_string(index=False))

    # production-baseline reconstruction sanity check
    prod = picks_by_config.get("nearest|w=0.6|top3nearest")
    if prod is not None:
        print("\n=== production-equivalent (nearest|w=0.6|top3nearest) ===")
        print(prod.groupby("kind")["held"].agg(["mean", "count"]).round(4).to_string())

    # conditionals on the dev-best config
    best = res.sort_values("dev202_hold", ascending=False).iloc[0]["config"]
    print(f"\n=== conditionals on dev-best config {best} ===")
    scored = picks_by_config[best].copy()
    mx2 = mx.set_index("date")
    scored["pcr"] = scored["date"].map(mx2["oc_pcr_oi"])
    scored["composite"] = scored["date"].map(mx2.get("v2_composite", mx2.get("composite", pd.Series(dtype=float))))
    scored["straddle"] = scored["date"].map(mx2["oc_straddle_pct"])
    scored["dte"] = scored["date"].map(mx2["oc_dte_actual"])
    scored["pcr_t"] = pd.qcut(scored["pcr"], 3, labels=["low", "mid", "high"])
    scored["vol_t"] = pd.qcut(scored["straddle"], 3, labels=["low", "mid", "high"])
    scored["dte_b"] = pd.cut(scored["dte"], [-1, 0, 2, 4, 8], labels=["expiry", "1-2", "3-4", "5+"])
    for col in ("pcr_t", "vol_t", "dte_b"):
        print(f"--- by {col} ---")
        print(scored.groupby([col, "kind"], observed=True)["held"].agg(["mean", "count"]).round(3).to_string())


if __name__ == "__main__":
    main()
