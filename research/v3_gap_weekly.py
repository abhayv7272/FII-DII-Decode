#!/usr/bin/env python3
"""Stage-7: gap-channel and weekly-channel deep dives.

GAP: OI positioning correlates most strongly with the overnight gap. We sweep
the same structural space as stage-3b but score on y_gap, then check whether
the dev-best *gap* classifier is also a better close-to-close classifier.

WEEKLY (y_5d): test the positional-carry features and 5-session flow sums as a
weekly composite (the published candidate failed 2026 confirmation), with
frozen-on-dev thresholds, plus the 50%-DOWN-2026 baseline context.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from v3_grids import composites, scores_matrix, load as load_merged  # noqa: E402

PERIODS = ("dev2023_24", "val2025", "confirm2026")
PART = {
    "v2": (0.5333, 0.2667, 0.20),
    "pf6040": (0.6, 0.4, 0.0),
    "pf6040c10n": (0.6, 0.4, -0.10),
    "pf5050": (0.5, 0.5, 0.0),
    "fii_only": (0.0, 1.0, 0.0),
}
INSTR = {"c4p4f2": (0.4, 0.4, 0.2), "c3p3f4": (0.3, 0.3, 0.4),
         "c2p2f6": (0.2, 0.2, 0.6), "opt": (0.5, 0.5, 0.0), "fut": (0.0, 0.0, 1.0)}


def sign_table(df, comp, target, band):
    y = df[target].to_numpy()
    cls = np.sign(comp)
    out = {}
    for p in PERIODS:
        m = (df["period"] == p).to_numpy()
        nf = m & (np.abs(y) > band)
        out[p] = (round((np.sign(y[nf]) == cls[nf]).mean() * 100, 2), int(nf.sum()))
    return out


def exact_table(df, comp, thr, band=0.15):
    y = df["y_cc"].to_numpy()
    actual = np.where(y > band, 1, np.where(y < -band, -1, 0))
    cls = np.where(comp >= thr, 1, np.where(comp <= -thr, -1, 0))
    out = {}
    for p in PERIODS:
        m = (df["period"] == p).to_numpy()
        nfm = m & (actual != 0) & (cls != 0)
        base = pd.Series(actual[m]).value_counts().max() / m.sum() * 100
        out[p] = (round((cls[m] == actual[m]).mean() * 100, 2),
                  round(base, 2),
                  round((np.sign(y[nfm]) == cls[nfm]).mean() * 100, 2) if nfm.sum() else np.nan)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="reports/v3_deep_dive")
    args = parser.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    df = load_merged()
    # refresh with chain columns
    mx2 = pd.read_csv("/home/user/features/v3_matrix2.csv", parse_dates=["date"])
    if "oc_pcr_oi" not in df:
        df = df.merge(mx2[["date", "oc_pcr_oi", "oc_pcr_near_atm", "oc_maxpain_dist_pct",
                            "oc_wall_build_pct", "oc_put_wall_dist_pct", "oc_call_wall_dist_pct"]],
                      on="date", how="left")
    per_q = scores_matrix(df, 0.025, "q")
    per_r = scores_matrix(df, 0.025, "r")

    # ---------------- GAP channel ----------------------------------------------
    rows = []
    for pn, pw in PART.items():
        for fl, per in (("q", per_q), ("r", per_r)):
            for iname, iw in INSTR.items():
                comp = composites(df, per, iw, pw)
                st = sign_table(df, comp, "y_gap", 0.15)
                cc = exact_table(df, comp, 0.0)
                rows.append({"part": pn, "flow": fl, "instr": iname,
                             "gap_dev": st["dev2023_24"][0], "gap_val": st["val2025"][0],
                             "gap_conf": st["confirm2026"][0],
                             "cc_dev": cc["dev2023_24"][0], "cc_val": cc["val2025"][0],
                             "cc_conf": cc["confirm2026"][0]})
    gap = pd.DataFrame(rows).sort_values("gap_dev", ascending=False)
    gap.to_csv(out / "gap_sweep.csv", index=False)
    pd.set_option("display.width", 200)
    print("=== gap sweep top-12 by gap_dev ===")
    print(gap.head(12).to_string(index=False))

    # PCR-enhanced gap score: z-score PCR within dev, blend with composite B
    compB = composites(df, per_q, (0.3, 0.3, 0.4), (0.6, 0.4, -0.10))
    dev_mask = (df["period"] == "dev2023_24").to_numpy()
    pcr = df["oc_pcr_oi"].to_numpy()
    mu, sd = np.nanmean(pcr[dev_mask]), np.nanstd(pcr[dev_mask])
    z = np.clip((pcr - mu) / sd, -3, 3) * 0.25  # comparable scale to composite
    for w in (0.0, 0.25, 0.5, 0.75, 1.0):
        blend = (1 - w) * compB + w * z
        st = sign_table(df, blend, "y_gap", 0.15)
        cc = exact_table(df, blend, 0.0)
        print(f"PCR blend w={w}: gap dev/val/conf = "
              f"{st['dev2023_24'][0]}/{st['val2025'][0]}/{st['confirm2026'][0]} | "
              f"cc exact dev/val/conf = {cc['dev2023_24'][0]}/{cc['val2025'][0]}/{cc['confirm2026'][0]} "
              f"| cc base {cc['confirm2026'][1]}")

    # ---------------- WEEKLY channel --------------------------------------------
    print("\n=== weekly channel (y_5d band +-0.50) ===")
    fii_carry = df["FII_ifut_lvl"].to_numpy()
    pro_carry = df["Pro_ifut_lvl"].to_numpy()
    cli_carry = -df["Client_ifut_lvl"].to_numpy()
    weekly_candidates = {
        "fii_ifut_carry": fii_carry,
        "carry_60_25_15": 0.6 * fii_carry + 0.25 * pro_carry + 0.15 * cli_carry,
        "fii_ifut_qflow_sum5": df["FII_ifut_qflow_sum5"].to_numpy(),
        "carry+flow5": 0.6 * fii_carry + 0.4 * df["FII_ifut_qflow_sum5"].to_numpy() * 10,
        "pf_carry": 0.5 * fii_carry + 0.5 * pro_carry,
    }
    rows = []
    for name, comp in weekly_candidates.items():
        comp = np.nan_to_num(comp)
        st = sign_table(df, comp, "y_5d", 0.50)
        rows.append({"candidate": name,
                     "dev": f"{st['dev2023_24'][0]} (n={st['dev2023_24'][1]})",
                     "val": f"{st['val2025'][0]} (n={st['val2025'][1]})",
                     "conf": f"{st['confirm2026'][0]} (n={st['confirm2026'][1]})"})
    print(pd.DataFrame(rows).to_string(index=False))
    # baselines
    for p in PERIODS:
        m = df[df["period"] == p]
        y = m["y_5d"]
        actual = y.map(lambda v: "UP" if v > 0.5 else ("DOWN" if v < -0.5 else "FLAT"))
        print(f"{p}: 5d baseline majority {actual.value_counts().max()/len(y)*100:.2f} "
              f"({actual.value_counts().idxmax()})")


if __name__ == "__main__":
    main()
