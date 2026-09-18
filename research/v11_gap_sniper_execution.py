"""V11 research: can the V10 tiny-gap touch edge be traded safely?

V10 found a robust high-accuracy *level-touch* prediction: tiny opening gaps tend
to touch the previous close intraday.  V11 asks a stricter question: does a
simple, executable target/stop model convert that touch edge into a robust trade
without hiding risk in a huge stop?

The simulator uses raw 1-minute NIFTY candles kept outside Git.  It tests:

* gap bands around the V10 rule,
* entry at the open or after 1/2/3/5/10/15 minutes if the target was not already
  touched before entry,
* simple filters based on whether price moved toward/away from the target, and
* stop distances from 0.75x to 5x of the target distance.

Conservative rule: if the same one-minute candle touches target and stop, count
it as a loss.  This prevents a high hit-rate level event from being mistaken for
a free execution edge.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from build_intraday_candles import load_raw_files


TRAIN_END_YEAR = 2023
VAL_YEARS = {2024, 2025}
CONFIRM_YEAR = 2026

UP = "UP"
DOWN = "DOWN"


def load_one_minute(raw_root: Path) -> pd.DataFrame:
    files = sorted(raw_root.rglob("*.csv"))
    if not files:
        raise FileNotFoundError(f"no raw 1-minute CSV files found below {raw_root}")
    df = load_raw_files(files)
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["date", "timestamp", "open", "high", "low", "close"]).sort_values(
        ["date", "timestamp"]
    )


def _simulate_target_stop(
    *,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    start_pos: int,
    direction: str,
    entry: float,
    target: float,
    stop: float,
) -> tuple[bool, float, bool, str]:
    """Return (win, pnl_points, ambiguous, exit_type)."""
    if start_pos >= len(closes):
        return False, 0.0, False, "NO_BARS_AFTER_ENTRY"
    if direction == DOWN:
        target_hits = lows[start_pos:] <= target
        stop_hits = highs[start_pos:] >= stop
        mult = -1.0
    else:
        target_hits = highs[start_pos:] >= target
        stop_hits = lows[start_pos:] <= stop
        mult = 1.0
    events = target_hits | stop_hits
    if events.any():
        pos = int(np.argmax(events))
        if bool(target_hits[pos]) and bool(stop_hits[pos]):
            return False, (stop - entry) * mult, True, "AMBIGUOUS_COUNTED_STOP"
        if bool(target_hits[pos]):
            return True, (target - entry) * mult, False, "TARGET"
        return False, (stop - entry) * mult, False, "STOP"
    exit_px = float(closes[-1])
    pnl = (exit_px - entry) * mult
    return bool(pnl > 0), pnl, False, "EOD"


def build_execution_trades(
    one_minute: pd.DataFrame,
    bands: Iterable[tuple[float, float]],
    entry_minutes: Iterable[int],
    stop_multipliers: Iterable[float],
) -> pd.DataFrame:
    daily = (
        one_minute.groupby("date", sort=True)
        .agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"))
        .reset_index()
    )
    daily["year"] = pd.to_datetime(daily["date"]).dt.year.astype(int)
    daily["prev_close"] = daily["close"].shift(1)
    daily["gap_pct"] = (daily["open"] - daily["prev_close"]) / daily["prev_close"] * 100.0
    by_date = {
        date: {
            "high": g["high"].astype(float).to_numpy(),
            "low": g["low"].astype(float).to_numpy(),
            "close": g["close"].astype(float).to_numpy(),
        }
        for date, g in one_minute.groupby("date", sort=True)
    }

    rows: list[dict] = []
    for lo, hi in bands:
        candidates = daily[(daily["gap_pct"].abs() >= lo) & (daily["gap_pct"].abs() < hi)].copy()
        for _, r in candidates.iterrows():
            target = float(r["prev_close"])
            open0 = float(r["open"])
            if not np.isfinite(target) or target <= 0 or open0 <= 0:
                continue
            date = str(r["date"])
            if date not in by_date:
                continue
            direction = DOWN if float(r["gap_pct"]) > 0 else UP if float(r["gap_pct"]) < 0 else "NO_SIGNAL"
            if direction not in {UP, DOWN}:
                continue
            arr = by_date[date]
            highs, lows, closes = arr["high"], arr["low"], arr["close"]
            for entry_min in entry_minutes:
                if len(closes) <= entry_min:
                    continue
                if entry_min > 0:
                    already_touched = bool((lows[:entry_min] <= target).any()) if direction == DOWN else bool(
                        (highs[:entry_min] >= target).any()
                    )
                    if already_touched:
                        continue
                    entry = float(closes[entry_min - 1])
                    start_pos = entry_min
                else:
                    entry = open0
                    start_pos = 0
                dist = abs(entry - target)
                if dist < 1.0:
                    continue
                first_ret = (entry - open0) / open0 * 100.0
                filters = {
                    "none": True,
                    "toward_target": first_ret < 0 if direction == DOWN else first_ret > 0,
                    "not_away_more_than_0.03pct": first_ret < 0.03 if direction == DOWN else first_ret > -0.03,
                    "after_adverse_0.02pct": first_ret > 0.02 if direction == DOWN else first_ret < -0.02,
                    "after_favourable_0.02pct": first_ret < -0.02 if direction == DOWN else first_ret > 0.02,
                }
                for filter_name, active in filters.items():
                    if not active:
                        continue
                    for stop_mult in stop_multipliers:
                        stop = entry + dist * stop_mult if direction == DOWN else entry - dist * stop_mult
                        win, pnl, ambiguous, exit_type = _simulate_target_stop(
                            highs=highs,
                            lows=lows,
                            closes=closes,
                            start_pos=start_pos,
                            direction=direction,
                            entry=entry,
                            target=target,
                            stop=stop,
                        )
                        rows.append(
                            {
                                "band": f"{lo:.2f}-{hi:.2f}",
                                "date": date,
                                "year": int(r["year"]),
                                "gap_pct": float(r["gap_pct"]),
                                "direction": direction,
                                "entry_minute": int(entry_min),
                                "filter": filter_name,
                                "stop_multiplier": float(stop_mult),
                                "entry": entry,
                                "target_prev_close": target,
                                "target_distance_pts": float(dist),
                                "win": bool(win),
                                "pnl_pts": float(pnl),
                                "ambiguous_same_minute_loss": bool(ambiguous),
                                "exit_type": exit_type,
                            }
                        )
    return pd.DataFrame(rows)


def summarize_execution(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    rows: list[dict] = []
    group_cols = ["band", "entry_minute", "filter", "stop_multiplier"]
    for key, x in trades.groupby(group_cols, sort=True):
        train = x["year"] <= TRAIN_END_YEAR
        val = x["year"].isin(VAL_YEARS)
        confirm = x["year"] == CONFIRM_YEAR
        row = dict(zip(group_cols, key))
        row.update(
            {
                "calls": int(len(x)),
                "train_2017_2023_calls": int(train.sum()),
                "val_2024_2025_calls": int(val.sum()),
                "confirm_2026_calls": int(confirm.sum()),
                "win_rate": float(x["win"].mean() * 100.0),
                "train_2017_2023_win_rate": float(x.loc[train, "win"].mean() * 100.0) if train.any() else np.nan,
                "val_2024_2025_win_rate": float(x.loc[val, "win"].mean() * 100.0) if val.any() else np.nan,
                "confirm_2026_win_rate": float(x.loc[confirm, "win"].mean() * 100.0) if confirm.any() else np.nan,
                "avg_pnl_pts": float(x["pnl_pts"].mean()),
                "train_2017_2023_avg_pnl_pts": float(x.loc[train, "pnl_pts"].mean()) if train.any() else np.nan,
                "val_2024_2025_avg_pnl_pts": float(x.loc[val, "pnl_pts"].mean()) if val.any() else np.nan,
                "confirm_2026_avg_pnl_pts": float(x.loc[confirm, "pnl_pts"].mean()) if confirm.any() else np.nan,
                "mean_target_distance_pts": float(x["target_distance_pts"].mean()),
                "ambiguous_rate": float(x["ambiguous_same_minute_loss"].mean() * 100.0),
            }
        )
        rows.append(row)
    out = pd.DataFrame(rows)
    return out.sort_values(
        ["confirm_2026_win_rate", "val_2024_2025_win_rate", "train_2017_2023_win_rate", "calls"],
        ascending=[False, False, False, False],
    )


def robust_trade_rules(
    summary: pd.DataFrame,
    *,
    min_train: int,
    min_val: int,
    min_confirm: int,
    min_win_rate: float,
) -> pd.DataFrame:
    if summary.empty:
        return summary
    mask = (
        (summary["train_2017_2023_calls"] >= min_train)
        & (summary["val_2024_2025_calls"] >= min_val)
        & (summary["confirm_2026_calls"] >= min_confirm)
        & (summary["train_2017_2023_win_rate"] >= min_win_rate)
        & (summary["val_2024_2025_win_rate"] >= min_win_rate)
        & (summary["confirm_2026_win_rate"] >= min_win_rate)
        & (summary["train_2017_2023_avg_pnl_pts"] > 0)
        & (summary["val_2024_2025_avg_pnl_pts"] > 0)
        & (summary["confirm_2026_avg_pnl_pts"] > 0)
    )
    return summary.loc[mask].sort_values(
        ["confirm_2026_win_rate", "val_2024_2025_win_rate", "train_2017_2023_win_rate"],
        ascending=[False, False, False],
    )


def _fmt(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "None."
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    lines.extend("| " + " | ".join(_fmt(v) for v in row) + " |" for row in df.itertuples(index=False, name=None))
    return "\n".join(lines)


def write_report(out_dir: Path, summary: pd.DataFrame, robust: pd.DataFrame, args: argparse.Namespace) -> None:
    high_win = summary[
        (summary["train_2017_2023_calls"] >= 80)
        & (summary["val_2024_2025_calls"] >= 30)
        & (summary["confirm_2026_calls"] >= 10)
        & (summary["train_2017_2023_win_rate"] >= 65)
        & (summary["val_2024_2025_win_rate"] >= 65)
    ].sort_values(["confirm_2026_win_rate", "val_2024_2025_win_rate"], ascending=[False, False])
    positive = summary[
        (summary["train_2017_2023_calls"] >= 100)
        & (summary["val_2024_2025_calls"] >= 40)
        & (summary["confirm_2026_calls"] >= 20)
        & (summary["train_2017_2023_avg_pnl_pts"] > 0)
        & (summary["val_2024_2025_avg_pnl_pts"] > 0)
        & (summary["confirm_2026_avg_pnl_pts"] > 0)
    ].sort_values(["confirm_2026_avg_pnl_pts", "val_2024_2025_avg_pnl_pts"], ascending=[False, False])

    lines = [
        "# V11 Gap Sniper Execution Audit",
        "",
        "## Verdict",
        "",
        "**No robust production trade conversion yet.** V10's tiny-gap previous-close touch remains a high-probability level-touch prediction, but the simple target/stop execution models tested here do not clear a robust 70% + positive-P&L gate across train, validation, and 2026 confirmation.",
        "",
        f"Robust positive 70% trade rules: **{len(robust)}**",
        "",
        "Why this matters: the target is small, so wider stops can manufacture high win-rates while losing expectancy in one or more splits.  V11 therefore requires both hit-rate and positive average P&L in every split.",
        "",
        "## Top high-win pockets (research only)",
        "",
        markdown_table(high_win.head(20)),
        "",
        "## Positive-P&L pockets with sample guards (still not 70% robust)",
        "",
        markdown_table(positive.head(20)),
        "",
        "## Robust trade rules",
        "",
        markdown_table(robust),
        "",
        "## Configuration",
        "",
        f"- Raw 1m root: `{args.raw_1m_root}`",
        f"- Bands: `{args.bands}`",
        f"- Entry minutes: `{args.entry_minutes}`",
        f"- Stop multiples: `{args.stop_multipliers}`",
        f"- Robust gate: train>={args.min_train}, validation>={args.min_val}, confirmation>={args.min_confirm}, win-rate>={args.min_win_rate:.2f}%, and positive average points in each split.",
        "- Same-minute target+stop: counted as stop/loss.",
        "",
        "## Actionable interpretation",
        "",
        "Keep V10 as a level-touch sniper alert.  Do **not** promote a standalone options trade until a broker/tick-level execution model survives slippage, spread, and stop tests.  A better next data step is real option-premium/tick data around these tiny-gap days, not more daily OI curve-fitting.",
    ]
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_float_list(text: str) -> list[float]:
    return [float(x.strip()) for x in text.split(",") if x.strip()]


def parse_int_list(text: str) -> list[int]:
    return [int(x.strip()) for x in text.split(",") if x.strip()]


def parse_bands(text: str) -> list[tuple[float, float]]:
    bands = []
    for part in text.split(","):
        if not part.strip():
            continue
        lo, hi = part.split(":")
        bands.append((float(lo), float(hi)))
    return bands


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-1m-root", default="/home/user/historical/technovusin-nifty50-historical-data/1min")
    ap.add_argument("--out", default="reports/v11_gap_sniper_execution")
    ap.add_argument("--bands", default="0.02:0.10,0.03:0.12,0.05:0.15")
    ap.add_argument("--entry-minutes", default="0,1,2,3,5,10,15")
    ap.add_argument("--stop-multipliers", default="0.75,1,1.5,2,2.5,3,4,5")
    ap.add_argument("--min-train", type=int, default=100)
    ap.add_argument("--min-val", type=int, default=40)
    ap.add_argument("--min-confirm", type=int, default=20)
    ap.add_argument("--min-win-rate", type=float, default=70.0)
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    one_minute = load_one_minute(Path(args.raw_1m_root))
    trades = build_execution_trades(
        one_minute,
        bands=parse_bands(args.bands),
        entry_minutes=parse_int_list(args.entry_minutes),
        stop_multipliers=parse_float_list(args.stop_multipliers),
    )
    summary = summarize_execution(trades)
    robust = robust_trade_rules(
        summary,
        min_train=args.min_train,
        min_val=args.min_val,
        min_confirm=args.min_confirm,
        min_win_rate=args.min_win_rate,
    )

    summary.to_csv(out_dir / "execution_grid.csv", index=False)
    robust.to_csv(out_dir / "robust_trade_rules.csv", index=False)
    top_research = summary[
        (summary["train_2017_2023_calls"] >= 80)
        & (summary["val_2024_2025_calls"] >= 30)
        & (summary["confirm_2026_calls"] >= 10)
        & (summary["train_2017_2023_win_rate"] >= 65)
        & (summary["val_2024_2025_win_rate"] >= 65)
    ].head(50)
    top_research.to_csv(out_dir / "top_research_pockets.csv", index=False)

    summary_payload = {
        "raw_1m_root": args.raw_1m_root,
        "one_minute_rows": int(len(one_minute)),
        "date_min": str(one_minute["date"].min()),
        "date_max": str(one_minute["date"].max()),
        "trades_generated": int(len(trades)),
        "execution_rule_summaries": int(len(summary)),
        "robust_positive_70pct_trade_rules": int(len(robust)),
        "verdict": "NO_PRODUCTION_TRADE_CONVERSION_YET_KEEP_V10_AS_LEVEL_TOUCH_ALERT",
    }
    (out_dir / "summary.json").write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    write_report(out_dir, summary, robust, args)
    print(json.dumps(summary_payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
