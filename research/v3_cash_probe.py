#!/usr/bin/env python3
"""Stage-8 probe: historical FII/DII cash flows (exploratory, NOT promotable).

Source: MrChartist/fii-dii-data data/history.json (2026-01-14 .. 2026-09-17).
That window never intersects the 2023-2024 development partition used to fit
v3, so nothing here can be promoted into the decoder: cash history starts too
late to fit honestly. The probe answers three questions for the record:

  Q1 do FII/DII cash nets show next-day predictive content on this window?
  Q2 does the v3 composite perform differently on cash-agree vs cash-disagree
     days (the "confirmation only" role production assigns)?
  Q3 should daily cash keep being accumulated for a future fitted decision?

Outputs reports/v3_deep_dive/cash_probe_2026.csv + console tables.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fiidii.backtest import load_ohlc  # noqa: E402

FLAT = 0.15
MRCHARTIST_URL = ("https://api.github.com/repos/MrChartist/fii-dii-data/"
                  "contents/data/history.json")


def fetch_cash_history(cache: Path | None) -> pd.DataFrame:
    if cache and cache.exists():
        raw = json.loads(cache.read_text())
    else:
        result = subprocess.run(
            ["curl", "-sf", MRCHARTIST_URL, "-H",
             "Accept: application/vnd.github.raw+json"],
            capture_output=True, timeout=60)
        if result.returncode != 0:
            raise SystemExit("cannot fetch MrChartist history.json "
                             "and no cache was supplied")
        raw = json.loads(result.stdout)
    frame = pd.DataFrame(raw)
    frame["date"] = pd.to_datetime(frame["date"], format="%d-%b-%Y")
    return frame.sort_values("date").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cash-cache", default="/home/user/historical/fii_cash_history.json")
    parser.add_argument("--ohlc", default="/home/user/historical/index_close")
    parser.add_argument("--predictions",
                        default="reports/backtest_v3_candidate_2023-08_to_2026-09/v3_predictions.csv")
    parser.add_argument("--out", default="reports/v3_deep_dive/cash_probe_2026.csv")
    args = parser.parse_args()

    cash = fetch_cash_history(Path(args.cash_cache))
    ohlc = load_ohlc(args.ohlc, symbol="NIFTY")
    ohlc["date"] = pd.to_datetime(ohlc["date"])
    ohlc = ohlc.sort_values("date").reset_index(drop=True)
    close = ohlc["close"]
    open_ = ohlc["open"]
    tgt = pd.DataFrame({
        "date": ohlc["date"],
        "y_cc": (close.shift(-1) / close - 1) * 100,
        "y_oc": (close.shift(-1) / open_.shift(-1) - 1) * 100,
        "y_gap": (open_.shift(-1) / close - 1) * 100,
    })
    df = cash.merge(tgt, on="date", how="inner").dropna(subset=["y_cc"])
    df["fii_net"] = pd.to_numeric(df["fii_net"], errors="coerce")
    df["dii_net"] = pd.to_numeric(df["dii_net"], errors="coerce")
    df["cash_combo"] = df["fii_net"] + 0.6 * df["dii_net"]
    n = len(df)
    print(f"cash rows {len(cash)} — merged with targets: {n} sessions "
          f"({df['date'].min().date()} .. {df['date'].max().date()})")

    print("\n=== Q1 univariate IC (Spearman) on the probe window ===")
    rows = []
    for feat in ("fii_net", "dii_net", "cash_combo"):
        row = {"feature": feat, "n": int(df[feat].notna().sum())}
        for t in ("y_cc", "y_gap", "y_oc"):
            sub = df[[feat, t]].dropna()
            row[f"ic_{t[2:]}"] = round(spearmanr(sub[feat], sub[t]).statistic, 4)
        # extreme-quintile sign rule: big cash net days -> next day sign
        q80 = df[feat].quantile(0.8)
        q20 = df[feat].quantile(0.2)
        hi = df[df[feat] >= q80]
        lo = df[df[feat] <= q20]
        hi_acc = (hi["y_cc"] > FLAT).mean() * 100
        lo_acc = (lo["y_cc"] < -FLAT).mean() * 100
        row["top20_up_rate"] = round(float(hi_acc), 1)
        row["bottom20_down_rate"] = round(float(lo_acc), 1)
        row["bucket_n"] = len(hi)
        rows.append(row)
    q1 = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(q1.to_string(index=False))

    print("\n=== Q2 v3 composite on cash-agree vs cash-disagree days ===")
    pred = pd.read_csv(args.predictions)
    pred["date"] = pd.to_datetime(pred["signal_date"])
    merged = pred.merge(df[["date", "cash_combo"]].dropna(), on="date", how="inner")
    merged["agree"] = np.sign(merged["cash_combo"]) == np.sign(merged["composite"])
    merged = merged[merged["predicted_class"].isin(["UP", "DOWN"])]
    q2rows = []
    for flag, sub in merged.groupby("agree"):
        nf = sub[sub["actual_class"].isin(["UP", "DOWN"])]
        exact = sub["exact_hit"].mean() * 100
        sign = (nf["predicted_class"] == nf["actual_class"]).mean() * 100 if len(nf) else np.nan
        q2rows.append({"cash_agrees_with_v3_lean": bool(flag), "signals": len(sub),
                       "exact_pct": round(exact, 2),
                       "nonflat_sign_pct": round(sign, 2) if len(nf) else None,
                       "sign_n": len(nf)})
    q2 = pd.DataFrame(q2rows)
    print(q2.to_string(index=False))

    q1.assign(block="Q1_univariate").to_json(Path(args.out).with_suffix(".q1.json"),
                                             orient="records", indent=2)
    q2.assign(block="Q2_v3_x_cash").to_json(Path(args.out).with_suffix(".q2.json"),
                                            orient="records", indent=2)
    df[["date", "fii_net", "dii_net", "cash_combo", "y_cc", "y_gap", "y_oc"]].to_csv(
        args.out, index=False, float_format="%.4f")
    print(f"\nwrote {args.out} (+ .q1.json/.q2.json)")
    print("\nQ3 note: production already accumulates FII/DII cash daily in "
          "data/fii_dii_cash.csv — keep collecting; no decoder change is justified "
          "from a probe window that post-dates the fitted period.")


if __name__ == "__main__":
    main()
