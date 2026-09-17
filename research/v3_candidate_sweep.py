#!/usr/bin/env python3
"""Stage-3b: focused candidate sweep for a possible v3 daily config.

Axes (fitted on dev only):
  participant scheme: v2 / pro_fii_5050 / fii_only / pro_only / pf_4060 / pfc_v2_nocontra
  flow:               q (closures half) / r (fresh only)
  instrument mix:     cpf options+futures variants
  threshold:          0.00 - 0.20

For every combo we keep dev metrics (selection basis) and untouched
val2025/confirm2026 metrics. The final table is sorted by dev score, then the
top configs are printed with all three periods side by side.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from v3_grids import composites, evaluate, scores_matrix  # noqa: E402
from v3_grids import load as load_merged  # noqa: E402


PART_SCHEMES = {
    "v2_p0.53_f0.27_c0.20": (0.5333, 0.2667, 0.20),
    "pf_5050": (0.5, 0.5, 0.0),
    "pf_6040": (0.6, 0.4, 0.0),
    "fii_only": (0.0, 1.0, 0.0),
    "pro_only": (1.0, 0.0, 0.0),
    "pf_4555_c10": (0.45, 0.45, 0.10),
    "pf_6040_c10neg": (0.60, 0.40, -0.10),
}
INSTR_MIXES = {
    "c4p4f2": (0.4, 0.4, 0.2),
    "c3p3f4": (0.3, 0.3, 0.4),
    "c2p2f6": (0.2, 0.2, 0.6),
    "fut_only": (0.0, 0.0, 1.0),
    "c45p45f1": (0.45, 0.45, 0.10),
    "opt_only": (0.5, 0.5, 0.0),
}
THRESHOLDS = [0.0, 0.025, 0.05, 0.075, 0.10, 0.125, 0.15, 0.20]
PERIODS = ("dev2023_24", "val2025", "confirm2026")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="reports/v3_deep_dive")
    args = parser.parse_args()
    df = load_merged()
    per_q = scores_matrix(df, 0.025, "q")
    per_r = scores_matrix(df, 0.025, "r")

    rows = []
    for ps_name, pw in PART_SCHEMES.items():
        for flow, per in (("q", per_q), ("r", per_r)):
            for im_name, iw in INSTR_MIXES.items():
                comp = composites(df, per, iw, pw)
                for thr in THRESHOLDS:
                    stats = evaluate(df, comp, thr)
                    dev, val, con = (stats[p] for p in PERIODS)
                    rows.append({
                        "participants": ps_name, "flow": flow, "instruments": im_name, "thr": thr,
                        "dev_exact": dev[0], "dev_cov": dev[1], "dev_sign": dev[2],
                        "val_exact": val[0], "val_cov": val[1], "val_sign": val[2],
                        "conf_exact": con[0], "conf_cov": con[1], "conf_sign": con[2],
                        "conf_sign_n": con[4],
                    })
    grid = pd.DataFrame(rows).dropna(subset=["dev_sign"])
    grid = grid[grid["dev_cov"] >= 50]  # keep coverage sane so sign acc is measurable
    grid["dev_score"] = 0.5 * grid["dev_sign"] + 0.5 * grid["dev_exact"]
    grid = grid.sort_values("dev_score", ascending=False)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    grid.to_csv(out / "candidate_sweep.csv", index=False)

    cols = ["participants", "flow", "instruments", "thr",
            "dev_exact", "dev_sign", "val_exact", "val_sign", "conf_exact", "conf_sign", "conf_sign_n"]
    pd.set_option("display.width", 250)
    print("=== top 25 by dev score (cov>=50) ===")
    print(grid.head(25)[cols].to_string(index=False))

    print("\n=== v2 reference row ===")
    ref = grid[(grid.participants == "v2_p0.53_f0.27_c0.20") & (grid.flow == "q")
               & (grid.instruments == "c4p4f2") & (grid.thr == 0.10)]
    print(ref[cols].to_string(index=False))

    # stability view: among top-60 dev configs, mean OOS deltas vs v2 row
    v2 = ref.iloc[0]
    top = grid.head(60).copy()
    top["conf_exact_gain"] = top["conf_exact"] - v2["conf_exact"]
    top["val_exact_gain"] = top["val_exact"] - v2["val_exact"]
    print("\n=== top-60 dev configs: OOS exact-gain deciles ===")
    print(top[["val_exact_gain", "conf_exact_gain"]].describe().round(2).to_string())


if __name__ == "__main__":
    main()
