#!/usr/bin/env python3
"""Stage-3 deep dive: weight & threshold grids for the daily composite.

The grid is fitted ONLY on dev2023_24. Validation (2025) and confirmation
(2026) columns are then computed unchanged for every grid point and for the
best-on-dev configurations, so out-of-sample behaviour is visible next to the
in-sample ranking.

Composite model (vectorised replica of production v2, verified 99.87% class
agreement):  per participant p and instrument i,
  score_{p,i} = tanh(qflow_{p,i} / SCALE)
  read_p      = sum_i(w_i * score_{p,i}) / sum_i(w_i)
  composite   = clip( wPro*read_Pro + wFII*read_FII + wContra*(-read_Client) )
  class       = UP if >= strong else SIDEWAYS-UP if >= thr ... RANGE if |c|<thr

Grids:
  G1 participant weights: wPro, wFII in [0..1] step .05, wContra in [-.3,+.3] step .05
  G2 instrument weights over (call, put, fut) shares step .1
  G3 closure weight in {0, .25, .5, .75, 1}
  G4 class threshold thr in step .025 for the top composites
"""
from __future__ import annotations

import argparse
import itertools
from pathlib import Path

import numpy as np
import pandas as pd

FLAT_BAND = 0.15
PERIODS = ("dev2023_24", "val2025", "confirm2026")


def load():
    pred = pd.read_csv("reports/backtest_v2_2023-08_to_2026-09/v2_predictions.csv")
    pred["date"] = pd.to_datetime(pred["signal_date"])
    mx = pd.read_csv("/home/user/features/v3_matrix.csv", parse_dates=["date"])
    return pred.merge(mx, on="date", how="left")


def evaluate(df, composite, thr):
    """Return per-period exact / coverage / sign-acc for class mapping."""
    cls = np.where(composite >= thr, "UP", np.where(composite <= -thr, "DOWN", "FLAT"))
    actual = np.where(df["y_cc"] > FLAT_BAND, "UP", np.where(df["y_cc"] < -FLAT_BAND, "DOWN", "FLAT"))
    out = {}
    period = df["period"].to_numpy()
    for p in PERIODS:
        mask = period == p
        e = (cls[mask] == actual[mask]).mean() * 100
        dir_mask = mask & (cls != "FLAT")
        cov = dir_mask.sum() / mask.sum() * 100
        nf = dir_mask & (actual != "FLAT")
        sa = (cls[nf] == actual[nf]).mean() * 100 if nf.sum() else np.nan
        base = pd.Series(actual[mask]).value_counts().max() / mask.sum() * 100
        out[p] = (round(e, 2), round(cov, 2), round(sa, 2) if nf.sum() else None, round(base, 2), int(nf.sum()))
    return out


def scores_matrix(df, scale, close_variant):
    """Return dict[(participant, instrument)] -> np.ndarray of tanh scores."""
    suffix = {"q": "_qflow", "r": "_rflow"}[close_variant]
    per = {}
    for p in ("Pro", "FII", "Client"):
        for inst in ("icall", "iput", "ifut"):
            per[(p, inst)] = np.tanh(df[f"{p}_{inst}{suffix}"].to_numpy() / scale)
    return per


def composites(df, per, instr_w, part_w):
    (wc, wp, wf) = instr_w
    reads = {}
    for p in ("Pro", "FII", "Client"):
        num = wc * per[(p, "icall")] + wp * per[(p, "iput")] + wf * per[(p, "ifut")]
        reads[p] = num / (wc + wp + wf)
    wpro, wfii, wcon = part_w
    total = wpro + wfii + abs(wcon)
    if total == 0:
        return np.zeros(len(df))
    comp = (wpro * reads["Pro"] + wfii * reads["FII"] + wcon * (-reads["Client"])) / total
    return np.clip(comp, -1, 1)


def flat_line(label, stats):
    cells = []
    for p in PERIODS:
        e, cov, sa, base, n = stats[p]
        cells.append(f"{p}: exact {e:.2f}/base {base:.2f}, cov {cov:.0f}%, sign {sa} (n={n})")
    print(f"{label}\n   " + " | ".join(cells))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="reports/v3_deep_dive")
    args = parser.parse_args()
    df = load()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

    per_q = scores_matrix(df, 0.025, "q")
    per_r = scores_matrix(df, 0.025, "r")

    v2_stats = evaluate(df, df["composite"].to_numpy(), 0.10)
    print("=== v2 locked reference ===")
    flat_line("v2_locked", v2_stats)

    # ---- G1 participant weights (v2 instruments, q flows) ----------------------
    rows = []
    w_options = np.round(np.arange(0, 1.0001, 0.05), 2)
    contra_options = np.round(np.arange(-0.30, 0.3001, 0.05), 2)
    for wpro, wfii, wcon in itertools.product(w_options, w_options, contra_options):
        if wpro + wfii + abs(wcon) == 0:
            continue
        comp = composites(df, per_q, (0.4, 0.4, 0.2), (wpro, wfii, wcon))
        stats = evaluate(df, comp, 0.10)
        dev = stats["dev2023_24"]
        rows.append({"w_pro": wpro, "w_fii": wfii, "w_contra": wcon,
                     "dev_exact": dev[0], "dev_cov": dev[1], "dev_sign": dev[2],
                     "val_exact": stats["val2025"][0], "val_sign": stats["val2025"][2],
                     "conf_exact": stats["confirm2026"][0], "conf_sign": stats["confirm2026"][2],
                     "conf_sign_n": stats["confirm2026"][4]})
    g1 = pd.DataFrame(rows).dropna(subset=["dev_sign"])
    g1["dev_score"] = 0.6 * g1["dev_sign"] + 0.4 * g1["dev_exact"]
    g1 = g1.sort_values("dev_score", ascending=False)
    g1.to_csv(out / "grid_participant_weights.csv", index=False)
    cols = ["w_pro", "w_fii", "w_contra", "dev_sign", "dev_exact", "val_sign", "conf_sign", "conf_sign_n"]
    print("\n=== G1 top-12 by dev (0.6*sign+0.4*exact) ===")
    print(g1.head(12)[cols].to_string(index=False))
    print("\n=== G1 bottom-6 (worst on dev) ===")
    print(g1.tail(6)[cols].to_string(index=False))
    v2row = g1[(g1.w_pro.between(0.53, 0.54)) & (g1.w_fii.between(0.26, 0.27)) & (g1.w_contra == 0.20)]
    print("\n=== v2 point inside G1 ===")
    print(v2row[cols].to_string(index=False))

    # ---- G2 instrument weights (v2 participants) --------------------------------
    rows = []
    steps = np.round(np.arange(0, 1.0001, 0.1), 1)
    for wc, wp_, wf in itertools.product(steps, steps, steps):
        if wc + wp_ + wf == 0:
            continue
        comp = composites(df, per_q, (wc, wp_, wf), (0.5333, 0.2667, 0.2))
        stats = evaluate(df, comp, 0.10)
        dev = stats["dev2023_24"]
        rows.append({"w_call": wc, "w_put": wp_, "w_fut": wf,
                     "dev_exact": dev[0], "dev_sign": dev[2],
                     "val_sign": stats["val2025"][2], "conf_sign": stats["confirm2026"][2]})
    g2 = pd.DataFrame(rows).dropna(subset=["dev_sign"])
    g2["dev_score"] = 0.6 * g2["dev_sign"] + 0.4 * g2["dev_exact"]
    g2 = g2.sort_values("dev_score", ascending=False)
    g2.to_csv(out / "grid_instrument_weights.csv", index=False)
    print("\n=== G2 top-12 instrument weights by dev ===")
    print(g2.head(12)[["w_call", "w_put", "w_fut", "dev_sign", "dev_exact", "val_sign", "conf_sign"]].to_string(index=False))

    # ---- G3 closure weight -------------------------------------------------------
    rows = []
    for label, per in (("q_0.50", per_q), ("r_fresh_only", per_r)):
        comp = composites(df, per, (0.4, 0.4, 0.2), (0.5333, 0.2667, 0.2))
        stats = evaluate(df, comp, 0.10)
        print(f"\n=== G3 closure variant {label} ===")
        flat_line(label, stats)

    # ---- G4 threshold curve for chosen composites --------------------------------
    print("\n=== G4 threshold sweep (dev-fit) ===")
    cand = {
        "v2": composites(df, per_q, (0.4, 0.4, 0.2), (0.5333, 0.2667, 0.2)),
        "v2_fresh": composites(df, per_r, (0.4, 0.4, 0.2), (0.5333, 0.2667, 0.2)),
        "fii_only": composites(df, per_q, (0.4, 0.4, 0.2), (0.0, 1.0, 0.0)),
        "pro_fii_5050": composites(df, per_q, (0.4, 0.4, 0.2), (0.5, 0.5, 0.0)),
    }
    thr_rows = []
    for name, comp in cand.items():
        for thr in np.round(np.arange(0.0, 0.5001, 0.025), 3):
            stats = evaluate(df, comp, thr)
            dev = stats["dev2023_24"]
            thr_rows.append({"config": name, "thr": thr, "dev_exact": dev[0], "dev_cov": dev[1],
                             "dev_sign": dev[2], "val_exact": stats["val2025"][0],
                             "val_sign": stats["val2025"][2], "conf_exact": stats["confirm2026"][0],
                             "conf_sign": stats["confirm2026"][2]})
    g4 = pd.DataFrame(thr_rows)
    g4.to_csv(out / "grid_thresholds.csv", index=False)
    for name in cand:
        sub = g4[g4.config == name].dropna(subset=["dev_sign"])
        best = sub.sort_values(["dev_exact"], ascending=False).head(4)
        print(f"\n--- {name}: best dev_exact thresholds ---")
        print(best.to_string(index=False))
        bests = sub.sort_values(["dev_sign"], ascending=False).head(4)
        print(f"--- {name}: best dev_sign thresholds ---")
        print(bests.to_string(index=False))


if __name__ == "__main__":
    main()
