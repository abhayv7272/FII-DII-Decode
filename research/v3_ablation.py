#!/usr/bin/env python3
"""Stage-2 deep dive: ablate the six locked v2 changes one at a time.

Each configuration re-runs the full point-in-time replay with exactly one
decoder change reverted to its v1 behaviour (all other v2 rules intact).
This isolates what each change contributes on each period, answering:
"if we kept everything else, was this specific rule worth it?"

The six locked changes (README/report):
 1. closures half weight            -> CLOSE_POSITION_WEIGHT = 1.0 (v1 behaviour: all equal)
 2. relative-OI normalisation       -> INDEX_FLOW_SCALE huge => ~linear raw contracts AND
                                        use v1-style fixed scales is approximated by scale=1e9 (linear, no squash)
 3. index-only next-day instruments  -> add stock instruments with v1-like weights
 4. Pro:FII 2:1 + contra-Client 20%  -> v1 participant weights (FII-led blend)
 5. stock derivatives excluded       -> covered by #3
 6. locked ±0.10 class boundary      -> scan boundaries (v1 used fixed contract rules)

Additionally the DII-exclusion and Client-contra treatments are toggled, and a
leave-one-participant-out (LOPO) table quantifies each participant's
contribution inside the v2 blend.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import fiidii.decode as d2  # noqa: E402
from fiidii.backtest import (  # noqa: E402
    BacktestConfig,
    load_ohlc,
    load_participant_oi,
    run_backtest,
)
import fiidii.backtest as bt  # noqa: E402

PERIODS = {"dev2023_24": (2023, 2024), "val2025": (2025, 2025), "confirm2026": (2026, 2099)}


def period_of(date_str: str) -> str:
    y = int(date_str[:4])
    for name, (lo, hi) in PERIODS.items():
        if lo <= y <= hi:
            return name
    return "?"


def score_predictions(pred: pd.DataFrame, flat=0.15) -> dict:
    """Exact / directional / non-FLAT sign metrics per period, matching the
    published comparison definitions."""
    out = {}
    for p in ["dev2023_24", "val2025", "confirm2026", "full"]:
        sub = pred if p == "full" else pred[pred["signal_date"].map(period_of) == p]
        n = len(sub)
        exact = sub["exact_hit"].mean() * 100
        cls_counts = sub["actual_class"].value_counts()
        majority = cls_counts.max() / n * 100
        dir_mask = sub["predicted_class"].isin(["UP", "DOWN"])
        direc = sub[dir_mask]
        hit_incl_flat = direc["direction_hit"].mean() * 100 if len(direc) else np.nan
        nonflat = direc[direc["actual_class"].isin(["UP", "DOWN"])]
        signacc = (nonflat["predicted_class"] == nonflat["actual_class"]).mean() * 100 if len(nonflat) else np.nan
        out[p] = {
            "n": n, "exact": round(exact, 2), "baseline": round(majority, 2),
            "coverage": round(len(direc) / n * 100, 2),
            "hit_incl_flat": round(hit_incl_flat, 2) if len(direc) else None,
            "signacc": round(signacc, 2) if len(nonflat) else None,
            "signacc_n": len(nonflat),
        }
    return out


def run_with_overrides(oi, ohlc, overrides: dict) -> pd.DataFrame:
    saved = {}
    for key, value in overrides.items():
        saved[key] = getattr(d2, key)
        setattr(d2, key, value)
    try:
        result = run_backtest(oi, ohlc, option_chains=None, config=BacktestConfig(decoder_version="v2"))
    finally:
        for key, value in saved.items():
            setattr(d2, key, value)
    return result.predictions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oi", default="/home/user/historical/participant_oi")
    parser.add_argument("--ohlc", default="/home/user/historical/index_close")
    parser.add_argument("--out", default="reports/v3_deep_dive")
    args = parser.parse_args()

    oi = load_participant_oi(args.oi)
    ohlc = load_ohlc(args.ohlc, symbol="NIFTY")

    variants: dict[str, dict] = {
        "v2_locked": {},
        "A1_closures_full_weight": {"CLOSE_POSITION_WEIGHT": 1.0},
        "A1b_closures_zero_weight": {"CLOSE_POSITION_WEIGHT": 0.0},
        "A1c_closures_75": {"CLOSE_POSITION_WEIGHT": 0.75},
        "A1d_closures_25": {"CLOSE_POSITION_WEIGHT": 0.25},
        "A2_linear_no_tanh": {"INDEX_FLOW_SCALE": 1e9, "STOCK_FLOW_SCALE": 1e9,
                               "CARRY_SCALE": {k: 1e9 for k in d2.CARRY_SCALE}},
        "A2b_loose_squash_5pct": {"INDEX_FLOW_SCALE": 0.05},
        "A2c_tight_squash_1pct": {"INDEX_FLOW_SCALE": 0.01},
        "A3_with_stock_fut_15": {"NEXT_DAY_INSTRUMENT_WEIGHT": {
            "index_call": 0.34, "index_put": 0.34, "index_fut": 0.17, "stock_fut": 0.15}},
        "A4_fii_led_participants": {"NEXT_DAY_PARTICIPANT_WEIGHT": {
            "Pro": 0.26, "FII": 0.54, "Client": 0.20, "DII": 0.0}},
        "A4b_fii_only": {"NEXT_DAY_PARTICIPANT_WEIGHT": {"Pro": 0.0, "FII": 1.0, "Client": 0.0, "DII": 0.0}},
        "A4c_pro_only": {"NEXT_DAY_PARTICIPANT_WEIGHT": {"Pro": 1.0, "FII": 0.0, "Client": 0.0, "DII": 0.0}},
        "A4d_equal_PF_no_client": {"NEXT_DAY_PARTICIPANT_WEIGHT": {
            "Pro": 0.5, "FII": 0.5, "Client": 0.0, "DII": 0.0}},
        "A4e_client_not_contra": {"NEXT_DAY_PARTICIPANT_WEIGHT": {
            "Pro": 0.5333, "FII": 0.2667, "Client": -0.20, "DII": 0.0}},
        "A5_dii_included": {"NEXT_DAY_PARTICIPANT_WEIGHT": {
            "Pro": 0.45, "FII": 0.22, "Client": 0.18, "DII": 0.15}},
        "A6_threshold_050": {"DIRECTION_THRESHOLD": 0.50},
        "A6b_threshold_020": {"DIRECTION_THRESHOLD": 0.20},
        "A6c_threshold_015": {"DIRECTION_THRESHOLD": 0.15},
        "A6d_threshold_005": {"DIRECTION_THRESHOLD": 0.05},
        "A7_no_conflict_rule": {"CONFLICT_THRESHOLD": 1e9},
    }

    rows = []
    store: dict[str, pd.DataFrame] = {}
    for name, overrides in variants.items():
        pred = run_with_overrides(oi, ohlc, overrides)
        store[name] = pred
        stats = score_predictions(pred)
        for period, s in stats.items():
            rows.append({"variant": name, "period": period, **s})
        print(f"done {name}: full exact={stats['full']['exact']} signacc={stats['full']['signacc']}")

    df = pd.DataFrame(rows)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "ablation_v2.csv", index=False)

    # agreement matrix: how often each variant flips the v2 class
    base = store["v2_locked"][["signal_date", "predicted_class"]].rename(
        columns={"predicted_class": "v2"})
    for name, pred in store.items():
        if name == "v2_locked":
            continue
        merged = base.merge(pred[["signal_date", "predicted_class"]], on="signal_date")
        agree = (merged["v2"] == merged["predicted_class"]).mean()
        print(f"{name}: agrees with v2 on {agree*100:.1f}% of dates")

    # focus table: exact + signacc per period vs v2
    pivot = df[df["period"] != "full"].pivot_table(
        index="variant", columns="period", values=["exact", "signacc"])
    full = df[df["period"] == "full"].set_index("variant")[["exact", "signacc", "coverage"]]
    summary = pd.concat([pivot, full], axis=1)
    summary.to_csv(out / "ablation_v2_summary.csv")
    pd.set_option("display.width", 250)
    print("\n", summary.round(2).to_string())


if __name__ == "__main__":
    main()
