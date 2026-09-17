#!/usr/bin/env python3
"""Stage-8: robustness battery for the v3-candidate daily composite.

Candidate B (dev-fitted on 2023-2024):
  participants Pro 60 / FII 40 / Client-aligned 10 (contra weight -0.10)
  instruments index call 30 / index put 30 / index futures 40
  quality flows (closures half weight), tanh scale 2.5% of market OI
  forced-class threshold 0.00 (always directional)

Checks:
  R1 exact/sign under FLAT bands +-0.10 / +-0.15 / +-0.20
  R2 rolling 126-session sign accuracy path (v2 vs candidate)
  R3 per-year and per-quarter breakdown
  R4 McNemar paired test vs v2 (val+confirm pooled and per period)
  R5 conflict-date behaviour (v2 WAIT dates)
  R6 executable basis (open-to-close) and basis decomposition:
       cc = gap + oc  -> how much of the gain is the gap channel
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from v3_grids import composites, scores_matrix, load as load_merged  # noqa: E402

PERIODS = ("dev2023_24", "val2025", "confirm2026")


def mcnamar(correct_a: np.ndarray, correct_b: np.ndarray):
    """Two-sided exact binomial on discordant pairs."""
    from math import comb
    b = int(np.sum(correct_a & ~correct_b))
    c = int(np.sum(~correct_a & correct_b))
    n = b + c
    if n == 0:
        return {"b": b, "c": c, "p_value": 1.0}
    k = min(b, c)
    p = 2 * sum(comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return {"b": b, "c": c, "p_value": round(p, 4)}


def class_from(comp, thr):
    return np.where(comp >= thr, "UP", np.where(comp <= -thr, "DOWN", "FLAT"))


def eval_band(df, comp, thr, band):
    y = df["y_cc"].to_numpy()
    actual = np.where(y > band, "UP", np.where(y < -band, "DOWN", "FLAT"))
    cls = class_from(comp, thr)
    out = {}
    for p in PERIODS:
        m = (df["period"] == p).to_numpy()
        exact = (cls[m] == actual[m]).mean() * 100
        nf = m & (cls != "FLAT") & (actual != "FLAT")
        sign = (cls[nf] == actual[nf]).mean() * 100 if nf.sum() else np.nan
        out[p] = (round(exact, 2), round(sign, 2) if nf.sum() else None, int(nf.sum()))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="reports/v3_deep_dive")
    args = parser.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    df = load_merged()
    per_q = scores_matrix(df, 0.025, "q")

    comp_v2 = df["composite"].to_numpy()
    comp_v3 = composites(df, per_q, (0.3, 0.3, 0.4), (0.6, 0.4, -0.10))

    print("=== R1 band sensitivity ===")
    rows = []
    for band in (0.10, 0.15, 0.20):
        for name, comp, thr in (("v2", comp_v2, 0.10), ("v3c", comp_v3, 0.0)):
            ev = eval_band(df, comp, thr, band)
            for p in PERIODS:
                rows.append({"band": band, "model": name, "period": p,
                             "exact": ev[p][0], "sign": ev[p][1], "sign_n": ev[p][2]})
    r1 = pd.DataFrame(rows)
    r1.to_csv(out / "robust_band_sensitivity.csv", index=False)
    print(r1.pivot_table(index=["band", "model"], columns="period",
                         values=["exact", "sign"]).round(2).to_string())

    print("\n=== R2 rolling 126d sign accuracy (full-coverage models) ===")
    y = df["y_cc"].to_numpy()
    nonflat = np.abs(y) > 0.15
    hits_v2 = (np.sign(comp_v2) == np.sign(y)) & nonflat
    hits_v3 = (np.sign(comp_v3) == np.sign(y)) & nonflat
    roll = pd.DataFrame({"date": df["date"], "v2c": hits_v2.astype(float),
                         "v3c": hits_v3.astype(float), "nf": nonflat.astype(float)})
    roll["v2_sign"] = roll["v2c"].rolling(126, min_periods=63).sum() / roll["nf"].rolling(126, min_periods=63).sum()
    roll["v3_sign"] = roll["v3c"].rolling(126, min_periods=63).sum() / roll["nf"].rolling(126, min_periods=63).sum()
    roll.dropna().to_csv(out / "rolling_sign.csv", index=False)
    sub = roll.dropna()
    print(f"rolling-126d sign: v3>v2 on {(sub['v3_sign'] > sub['v2_sign']).mean()*100:.1f}% of windows; "
          f"mean v3 {sub['v3_sign'].mean()*100:.1f}% vs v2 {sub['v2_sign'].mean()*100:.1f}%")

    print("\n=== R3 per-year breakdown (thr: v2 0.10 / v3c 0.00, band 0.15) ===")
    df["year"] = df["date"].dt.year
    rows = []
    for yr, g in df.groupby("year"):
        yv = g["y_cc"].to_numpy()
        actual = np.where(yv > 0.15, "UP", np.where(yv < -0.15, "DOWN", "FLAT"))
        base = pd.Series(actual).value_counts().max() / len(g) * 100
        for name, comp_all, thr in (("v2", comp_v2, 0.10), ("v3c", comp_v3, 0.0)):
            comp = comp_all[df["year"] == yr]
            cls = class_from(comp, thr)
            exact = (cls == actual).mean() * 100
            nf = (cls != "FLAT") & (actual != "FLAT")
            sign = (cls[nf] == actual[nf]).mean() * 100 if nf.sum() else np.nan
            rows.append({"year": yr, "model": name, "n": len(g), "exact": round(exact, 2),
                         "baseline": round(base, 2),
                         "sign": round(sign, 2) if nf.sum() else None, "sign_n": int(nf.sum())})
    r3 = pd.DataFrame(rows)
    r3.to_csv(out / "robust_yearly.csv", index=False)
    print(r3.pivot_table(index="year", columns="model", values=["exact", "sign", "baseline"]).round(2).to_string())

    print("\n=== R4 McNemar v3c vs v2 (exact-class correctness, band 0.15) ===")
    actual = np.where(y > 0.15, "UP", np.where(y < -0.15, "DOWN", "FLAT"))
    cls2 = class_from(comp_v2, 0.10)
    cls3 = class_from(comp_v3, 0.0)
    rows = []
    for p in PERIODS:
        m = (df["period"] == p).to_numpy()
        stat = mcnamar(cls3[m] == actual[m], cls2[m] == actual[m])
        rows.append({"period": p, **stat})
        # non-FLAT sign correctness among dates both called correctly directional
        m2 = m & (actual != "FLAT")
        stat2 = mcnamar(cls3[m2] == actual[m2], cls2[m2] == actual[m2])
        rows.append({"period": f"{p} (nonflat sign)", **stat2})
    r4 = pd.DataFrame(rows)
    r4.to_csv(out / "robust_mcnemar.csv", index=False)
    print(r4.to_string(index=False))

    print("\n=== R5 v2 conflict dates (smart_money_conflict) ===")
    conf_mask = df["smart_money_conflict"].fillna(False).astype(bool).to_numpy()
    for p in PERIODS:
        m = (df["period"] == p).to_numpy() & conf_mask & (actual != "FLAT")
        n = m.sum()
        if n:
            acc2 = (cls2[m] == actual[m]).mean() * 100
            acc3 = (cls3[m] == actual[m]).mean() * 100
            print(f"{p}: {n} conflict non-FLAT dates; v2 sign {acc2:.1f}% | v3c {acc3:.1f}%")

    print("\n=== R6 basis decomposition ===")
    for basis, band in (("y_gap", 0.15), ("y_oc", 0.15)):
        yb = df[basis].to_numpy()
        for name, comp in (("v2", comp_v2), ("v3c", comp_v3)):
            cells = []
            for p in PERIODS:
                m = (df["period"] == p).to_numpy() & (np.abs(yb) > band)
                acc = (np.sign(yb[m]) == np.sign(comp[m])).mean() * 100 if m.sum() else np.nan
                cells.append(f"{p.split('2')[0]} {acc:.1f}% (n={int(m.sum())})")
            print(f"{basis} {name}: " + " | ".join(cells))


if __name__ == "__main__":
    main()
