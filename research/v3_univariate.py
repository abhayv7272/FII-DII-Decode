#!/usr/bin/env python3
"""Stage-1 deep dive: univariate predictive power of every feature.

Outputs (under --out, default reports/v3_deep_dive):
  class_balance.csv        actual class shares per period & basis
  univariate_ic.csv        Spearman IC of every feature vs every basis, per period
  univariate_null.csv      permutation-null reference distribution (dev period)
  top_features.csv         features passing the dev null filter, with OOS columns

Protocol: rank on dev2023_24; validation (2025) and confirmation (2026) columns
are reported unchanged for the same features. The permutation null estimates the
max-|IC| distribution under 'no signal' on dev so we know what rank-1 looks like
even when nothing works (multiple-testing control).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

TARGETS = ("y_cc", "y_oc", "y_gap", "y_5d")
FLAT = {"y_cc": 0.15, "y_oc": 0.15, "y_gap": 0.15, "y_5d": 0.50}
SKIP_COLS = {"date", "period", "target_date", "target5_date"} | set(TARGETS)


def actual_class(series: pd.Series, band: float) -> pd.Series:
    return series.map(lambda v: "UP" if v > band else ("DOWN" if v < -band else "FLAT"))


def sign_accuracy(feat: pd.Series, target: pd.Series, band: float, thr: float) -> tuple[float, int]:
    """Predict sign(feat) when |feat| >= thr; score on realised non-FLAT moves."""
    mask = (feat.abs() >= thr) & (target.abs() > band)
    mask &= feat.notna() & target.notna()
    n = int(mask.sum())
    if n < 10:
        return np.nan, n
    hits = (np.sign(feat[mask]) == np.sign(target[mask])).sum()
    return round(hits / n * 100, 2), n


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", default="/home/user/features/v3_matrix.csv")
    parser.add_argument("--out", default="reports/v3_deep_dive")
    parser.add_argument("--shuffles", type=int, default=200)
    args = parser.parse_args()

    df = pd.read_csv(args.matrix, parse_dates=["date"])
    features = [c for c in df.columns if c not in SKIP_COLS and df[c].notna().mean() > 0.95]
    periods = ["dev2023_24", "val2025", "confirm2026"]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # ---- class balance ---------------------------------------------------------
    rows = []
    for t in TARGETS:
        for p in ["full"] + periods:
            sub = df if p == "full" else df[df["period"] == p]
            cls = actual_class(sub[t], FLAT[t])
            counts = cls.value_counts()
            n = len(sub)
            rows.append({
                "basis": t, "period": p, "n": n,
                "up_pct": round(counts.get("UP", 0) / n * 100, 2),
                "flat_pct": round(counts.get("FLAT", 0) / n * 100, 2),
                "down_pct": round(counts.get("DOWN", 0) / n * 100, 2),
                "majority_baseline_pct": round(counts.max() / n * 100, 2),
                "majority_class": counts.idxmax(),
                "nonflat_up_share_pct": round(
                    counts.get("UP", 0) / max(counts.get("UP", 0) + counts.get("DOWN", 0), 1) * 100, 2),
            })
    balance = pd.DataFrame(rows)
    balance.to_csv(out / "class_balance.csv", index=False)

    # ---- univariate IC + simple sign rule --------------------------------------
    recs = []
    dev = df[df["period"] == "dev2023_24"]
    for feat in features:
        rec = {"feature": feat}
        for p in periods:
            sub = df if p == "full" else df[df["period"] == p]
            x, y = sub[feat], sub["y_cc"]
            mask = x.notna() & y.notna()
            rec[f"ic_cc_{p.split('2')[0]}"] = round(spearmanr(x[mask], y[mask]).statistic, 4)
            xo, yo = sub[feat], sub["y_oc"]
            mo = xo.notna() & yo.notna()
            rec[f"ic_oc_{p.split('2')[0]}"] = round(spearmanr(xo[mo], yo[mo]).statistic, 4)
        # dev-fitted threshold sign rule -> carried unchanged to val/confirm
        thr = float(dev[feat].abs().median())
        for p in periods:
            sub = df[df["period"] == p]
            acc, n = sign_accuracy(sub[feat], sub["y_cc"], FLAT["y_cc"], thr)
            rec[f"signacc_p50_{p.split('2')[0]}"] = acc
            rec[f"signacc_n_{p.split('2')[0]}"] = n
        recs.append(rec)
    ic = pd.DataFrame(recs)
    ic["abs_ic_dev"] = ic["ic_cc_dev"].abs()
    ic = ic.sort_values("abs_ic_dev", ascending=False)
    ic.to_csv(out / "univariate_ic.csv", index=False)

    # ---- permutation null on dev ------------------------------------------------
    rng = np.random.default_rng(42)
    y = dev["y_cc"].to_numpy()
    max_null = []
    for _ in range(args.shuffles):
        ys = rng.permutation(y)
        best = 0.0
        for feat in features:
            x = dev[feat].to_numpy()
            if np.isnan(x).any():
                continue
            r = spearmanr(x, ys).statistic
            best = max(best, abs(r))
        max_null.append(best)
    null = pd.Series(max_null)
    null_stats = pd.DataFrame({
        "metric": ["null_max_abs_ic_p50", "null_max_abs_ic_p95", "null_max_abs_ic_p99",
                    "n_features", "n_shuffles"],
        "value": [round(float(null.quantile(0.5)), 4), round(float(null.quantile(0.95)), 4),
                  round(float(null.quantile(0.99)), 4), len(features), args.shuffles],
    })
    null_stats.to_csv(out / "univariate_null.csv", index=False)

    gate = float(null.quantile(0.95))
    ic["passes_null95"] = ic["abs_ic_dev"] > gate
    top = ic[ic["passes_null95"]].copy()
    top.to_csv(out / "top_features.csv", index=False)

    pd.set_option("display.width", 220)
    print("=== class balance (y_cc ±0.15 / y_5d ±0.50) ===")
    print(balance[balance["basis"].isin(["y_cc", "y_5d"])].to_string(index=False))
    print(f"\n=== null: 95th pct of max |IC| on dev = {gate:.4f} "
          f"({len(features)} features, {args.shuffles} shuffles) ===")
    print(f"features passing: {len(top)}")
    cols = ["feature", "ic_cc_dev", "ic_cc_val", "ic_cc_confirm",
            "ic_oc_dev", "ic_oc_confirm",
            "signacc_p50_dev", "signacc_n_dev", "signacc_p50_val", "signacc_p50_confirm"]
    print(ic.head(40)[cols].to_string(index=False))


if __name__ == "__main__":
    main()
