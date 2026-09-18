"""V9 research: combine OI/v3 prior-day lean with 10/15m confirmation.

V5 only had a tiny recent intraday sample.  V7/V8 added long NIFTY intraday
history, so this script retests the more relevant question: does the prior-day
FII/DII/Pro/Client OI lean become executable when the next session's first
10/15/30/60-minute candle confirms (or contradicts) it?

Inputs are point-in-time:
* v3 prediction dated D, targeting session D+1;
* only the first N minutes of target session D+1 are used to trigger;
* target/stop simulation starts after the confirmation candle closes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from v8_intraday_trade_sim import _day_arrays, interval_minutes, load_bars, simulate_trade_arrays

UP = "UP"
DOWN = "DOWN"


def _safe_records(df: pd.DataFrame, n: int = 10) -> list[dict]:
    if df.empty:
        return []
    return json.loads(df.head(n).replace({np.nan: None}).to_json(orient="records"))


def _markdown_table(df: pd.DataFrame, cols: list[str], n: int = 20) -> str:
    if df.empty:
        return ""
    view = df[cols].head(n).copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else f"{x:.2f}")
        else:
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else str(x))
    header = "| " + " | ".join(view.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(str(v).replace("|", "\\|") for v in row) + " |" for row in view.to_numpy()]
    return "\n".join([header, sep, *rows])


def load_v3(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    keep = [
        "signal_date", "target_date", "predicted_class", "prediction_raw",
        "composite", "confidence", "actionability", "smart_money_conflict",
    ]
    df = df[[c for c in keep if c in df.columns]].copy()
    df["signal_date"] = pd.to_datetime(df["signal_date"]).dt.date.astype(str)
    df["target_date"] = pd.to_datetime(df["target_date"]).dt.date.astype(str)
    df["predicted_class"] = df["predicted_class"].astype(str)
    df = df[df["predicted_class"].isin([UP, DOWN])].copy()
    df["composite"] = pd.to_numeric(df.get("composite", 0), errors="coerce").fillna(0.0)
    df["confidence"] = pd.to_numeric(df.get("confidence", 0), errors="coerce").fillna(0.0)
    df["abs_composite"] = df["composite"].abs()
    return df


def build_trades_for_interval(
    bars: pd.DataFrame,
    preds: pd.DataFrame,
    target_stop_pcts: list[float],
    thresholds: list[float],
    confidence_mins: list[float],
    abs_composite_mins: list[float],
) -> pd.DataFrame:
    interval_min = interval_minutes(bars)
    windows = [1, 2, 3, 6] if interval_min == 10 else [1, 2, 4]
    bars_by_date = {d: x.sort_values("bar_index").reset_index(drop=True) for d, x in bars.groupby("date")}
    rows = []

    for _, pred in preds.iterrows():
        target_date = pred["target_date"]
        if target_date not in bars_by_date:
            continue
        day = bars_by_date[target_date]
        arr = _day_arrays(day)
        day_open = float(day.iloc[0]["open"])
        if day_open <= 0:
            continue
        v3_dir = pred["predicted_class"]
        v3_mult = 1 if v3_dir == UP else -1
        for conf_min in confidence_mins:
            if float(pred["confidence"]) < conf_min:
                continue
            for comp_min in abs_composite_mins:
                if float(pred["abs_composite"]) < comp_min:
                    continue
                filter_label = f"conf{conf_min:g}_abs{comp_min:g}"
                for n in windows:
                    if len(day) <= n:
                        continue
                    entry_bar = day.iloc[n - 1]
                    entry = float(entry_bar["close"])
                    first_ret_pct = (entry - day_open) / day_open * 100

                    candidates: list[tuple[str, str, bool]] = [
                        (f"v3_any_{filter_label}_after{n * interval_min}m", v3_dir, True),
                    ]
                    for threshold in thresholds:
                        same = first_ret_pct * v3_mult > threshold
                        opposite = first_ret_pct * v3_mult < -threshold
                        first_dir = UP if first_ret_pct > threshold else DOWN if first_ret_pct < -threshold else None
                        candidates.extend(
                            [
                                (f"v3_align_first{n * interval_min}m_gt{threshold:g}_{filter_label}", v3_dir, same),
                                (f"v3_fade_opposite_first{n * interval_min}m_gt{threshold:g}_{filter_label}", v3_dir, opposite),
                                (f"first_overrides_v3_conflict_first{n * interval_min}m_gt{threshold:g}_{filter_label}", first_dir or v3_dir, opposite and first_dir is not None),
                            ]
                        )
                    for rule, direction, ok in candidates:
                        if not ok:
                            continue
                        for pct in target_stop_pcts:
                            sim = simulate_trade_arrays(arr, n - 1, direction, entry, pct, pct)
                            if sim is None:
                                continue
                            rows.append(
                                {
                                    "family": "v3_oi_intraday_confirmation",
                                    "interval_min": interval_min,
                                    "signal_date": pred["signal_date"],
                                    "target_date": target_date,
                                    "year": int(target_date[:4]),
                                    "rule": rule,
                                    "mode": rule.split("_")[1],
                                    "direction": direction,
                                    "v3_direction": v3_dir,
                                    "entry_after_bars": n,
                                    "entry_timestamp": str(entry_bar["timestamp"]),
                                    "entry_price": entry,
                                    "first_window_ret_pct": first_ret_pct,
                                    "v3_composite": float(pred["composite"]),
                                    "v3_confidence": float(pred["confidence"]),
                                    "target_pct": pct,
                                    "stop_pct": pct,
                                    **sim,
                                }
                            )
    return pd.DataFrame(rows)


def summarize(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    rows = []
    group_cols = ["interval_min", "rule", "direction", "entry_after_bars", "target_pct", "stop_pct"]
    for key, x in trades.groupby(group_cols, sort=False):
        row = dict(zip(group_cols, key))
        train = x["year"] <= 2024
        val = x["year"] == 2025
        conf = x["year"] == 2026
        row.update(
            {
                "calls": int(len(x)),
                "win_rate": float(x["win"].mean() * 100),
                "avg_pnl_pts": float(x["pnl_pts"].mean()),
                "median_pnl_pts": float(x["pnl_pts"].median()),
                "target_rate": float((x["exit_type"] == "TARGET").mean() * 100),
                "stop_rate": float(x["exit_type"].isin(["STOP", "AMBIGUOUS_COUNTED_STOP"]).mean() * 100),
                "eod_rate": float((x["exit_type"] == "EOD").mean() * 100),
                "ambiguous_rate": float(x["ambiguous"].mean() * 100),
                "train_2023_2024_calls": int(train.sum()),
                "val_2025_calls": int(val.sum()),
                "confirm_2026_calls": int(conf.sum()),
                "train_2023_2024_win_rate": float(x.loc[train, "win"].mean() * 100) if train.any() else np.nan,
                "val_2025_win_rate": float(x.loc[val, "win"].mean() * 100) if val.any() else np.nan,
                "confirm_2026_win_rate": float(x.loc[conf, "win"].mean() * 100) if conf.any() else np.nan,
                "train_2023_2024_avg_pnl_pts": float(x.loc[train, "pnl_pts"].mean()) if train.any() else np.nan,
                "val_2025_avg_pnl_pts": float(x.loc[val, "pnl_pts"].mean()) if val.any() else np.nan,
                "confirm_2026_avg_pnl_pts": float(x.loc[conf, "pnl_pts"].mean()) if conf.any() else np.nan,
            }
        )
        rows.append(row)
    out = pd.DataFrame(rows)
    return out.sort_values(
        ["confirm_2026_win_rate", "confirm_2026_calls", "val_2025_win_rate", "train_2023_2024_win_rate", "avg_pnl_pts"],
        ascending=[False, False, False, False, False],
    )


def robust(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    return summary[
        (summary["train_2023_2024_calls"] >= 120)
        & (summary["val_2025_calls"] >= 40)
        & (summary["confirm_2026_calls"] >= 25)
        & (summary["train_2023_2024_win_rate"] >= 70)
        & (summary["val_2025_win_rate"] >= 70)
        & (summary["confirm_2026_win_rate"] >= 70)
        & (summary["avg_pnl_pts"] > 0)
    ].copy()


def write_report(out: Path, summary: pd.DataFrame, robust_df: pd.DataFrame, quality: dict) -> None:
    lines = [
        "# V9 OI + Intraday Confirmation",
        "",
        "## Objective",
        "",
        "Retest the actual FII/DII/Pro/Client idea with the new intraday history: prior-day v3 OI lean plus next-session first 10/15/30/60-minute confirmation, entered only after the candle closes and scored by symmetric target/stop simulation.",
        "",
        "## Data",
        "",
        f"- V3 OI predictions: {quality['v3_predictions']} rows from `{quality['v3_path']}`.",
        f"- 10m sessions: {quality['sessions_10m']} from `{quality['path_10m']}`.",
        f"- 15m sessions: {quality['sessions_15m']} from `{quality['path_15m']}`.",
        "- Split: train 2023-2024, validation 2025, confirmation 2026.",
        "- Ambiguous target+stop bars are counted as losses; target and stop are symmetric percentages.",
        "",
        "## Main result",
        "",
        f"- Rule summaries checked: **{len(summary):,}**.",
        f"- Rules clearing strict 70% win-rate in train, 2025 validation, and 2026 confirmation with sample guards and positive average points: **{len(robust_df)}**.",
        "- Verdict: the OI lean still does not become a production 70%+ executable edge after first-candle confirmation.",
        "",
        "## Best V9 rules by 2026 confirmation slice",
        "",
    ]
    if summary.empty:
        lines.append("No trades generated.")
    else:
        cols = [
            "interval_min", "rule", "direction", "entry_after_bars", "target_pct",
            "calls", "win_rate", "avg_pnl_pts", "train_2023_2024_calls",
            "train_2023_2024_win_rate", "val_2025_calls", "val_2025_win_rate",
            "confirm_2026_calls", "confirm_2026_win_rate", "ambiguous_rate",
        ]
        lines.append(_markdown_table(summary, cols, 25))
    lines.extend([
        "",
        "## Interpretation",
        "",
        "High 2026-only pockets are not enough. A rule must also hold in the 2023-2024 development window and 2025 validation. V9 keeps the production default unchanged and gives us a forward-test protocol: OI lean + fixed intraday confirmation + symmetric execution.",
    ])
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    payload = {
        **quality,
        "rule_summaries": int(len(summary)),
        "robust_70pct_rules": int(len(robust_df)),
        "best_rules": _safe_records(summary, 10),
        "verdict": "NO_OI_INTRADAY_PRODUCTION_70PCT_EDGE_YET",
    }
    (out / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v3", default="reports/backtest_v3_candidate_2023-08_to_2026-09/v3_predictions.csv")
    ap.add_argument("--intraday-10m", default="historical/nifty_10m.csv")
    ap.add_argument("--intraday-15m", default="historical/nifty_15m.csv")
    ap.add_argument("--out", default="reports/v9_oi_intraday_confirmation")
    ap.add_argument("--write-raw-trades", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    preds = load_v3(Path(args.v3))
    bars10 = load_bars(Path(args.intraday_10m), min_bars=30)
    bars15 = load_bars(Path(args.intraday_15m), min_bars=20)

    parts = []
    for bars in [bars10, bars15]:
        parts.append(
            build_trades_for_interval(
                bars,
                preds,
                target_stop_pcts=[0.10, 0.15, 0.20, 0.30],
                thresholds=[0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30],
                confidence_mins=[0, 15, 20, 25, 30, 35],
                abs_composite_mins=[0.00, 0.05, 0.10, 0.15],
            )
        )
    trades = pd.concat([x for x in parts if not x.empty], ignore_index=True) if any(not x.empty for x in parts) else pd.DataFrame()
    summary = summarize(trades)
    robust_df = robust(summary)

    if args.write_raw_trades:
        trades.to_csv(out / "v9_trades.csv", index=False)
    else:
        trades.head(5000).to_csv(out / "v9_trades_sample.csv", index=False)
    summary.to_csv(out / "v9_rule_summary.csv", index=False)
    robust_df.to_csv(out / "v9_robust_70pct.csv", index=False)
    quality = {
        "v3_path": args.v3,
        "path_10m": args.intraday_10m,
        "path_15m": args.intraday_15m,
        "v3_predictions": int(len(preds)),
        "trades_generated": int(len(trades)),
        "sessions_10m": int(bars10["date"].nunique()),
        "sessions_15m": int(bars15["date"].nunique()),
        "date_min_10m": str(bars10["date"].min()),
        "date_max_10m": str(bars10["date"].max()),
        "date_min_15m": str(bars15["date"].min()),
        "date_max_15m": str(bars15["date"].max()),
        "target_stop_pct_grid": [0.10, 0.15, 0.20, 0.30],
        "ambiguous_bars_policy": "counted_as_stop_loss",
    }
    (out / "data_quality.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")
    write_report(out, summary, robust_df, quality)
    print(json.dumps(json.loads((out / "summary.json").read_text()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
