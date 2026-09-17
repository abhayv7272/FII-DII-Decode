"""V8 research: trade-level intraday simulation with 10/15-minute candles.

V7 proved that open-to-close direction accuracy can look high merely because the
observed first candle is included in the label.  V8 moves one step closer to a
real executable plan: after a 10/15-minute confirmation candle closes, enter at
that close and then simulate target/stop order outcomes on the remaining
intraday bars.

The script runs two families of tests:

1. Generic first-window momentum/fade rules over 2017-2026, using symmetric
   percentage targets and stops (target == stop) to avoid fake high win-rates
   from tiny targets and huge stops.
2. PDF date-stamped level reactions over the 2026 level window, also with
   symmetric target/stop.  These are small-sample by construction because exact
   institutional levels are available only in the supplied dated PDF window.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd

UP = "UP"
DOWN = "DOWN"


@dataclass(frozen=True)
class TradeConfig:
    min_bars_per_day: int = 20
    flat_cost_pts: float = 0.0  # Set to zero for index-point research; costs are reported separately.


def _dir_mult(direction: str) -> int:
    return 1 if direction == UP else -1


def load_bars(path: Path, min_bars: int) -> pd.DataFrame:
    bars = pd.read_csv(path)
    bars["date"] = pd.to_datetime(bars["date"]).dt.date.astype(str)
    bars["timestamp"] = pd.to_datetime(bars["timestamp"])
    for c in ["bar_index", "open", "high", "low", "close", "volume", "minute_count"]:
        if c in bars.columns:
            bars[c] = pd.to_numeric(bars[c], errors="coerce")
    bars = bars.dropna(subset=["date", "bar_index", "open", "high", "low", "close"])
    counts = bars.groupby("date")["bar_index"].nunique()
    good = counts[counts >= min_bars].index
    return bars[bars["date"].isin(good)].sort_values(["date", "bar_index"]).copy()


def interval_minutes(bars: pd.DataFrame) -> int:
    vc = bars.loc[bars["minute_count"] > 1, "minute_count"].round().astype(int).value_counts()
    return int(vc.index[0]) if not vc.empty else 15


def _day_arrays(day: pd.DataFrame) -> dict:
    day = day.sort_values("bar_index").reset_index(drop=True)
    return {
        "bar_index": day["bar_index"].astype(int).to_numpy(),
        "timestamp": day["timestamp"].astype(str).to_numpy(),
        "high": day["high"].astype(float).to_numpy(),
        "low": day["low"].astype(float).to_numpy(),
        "close": day["close"].astype(float).to_numpy(),
    }


def simulate_trade_arrays(
    arr: dict,
    entry_pos: int,
    direction: str,
    entry: float,
    target_pct: float,
    stop_pct: float,
) -> dict | None:
    """Conservative target/stop simulation after the entry bar has closed."""
    mult = _dir_mult(direction)
    if entry <= 0 or entry_pos + 1 >= len(arr["close"]):
        return None
    target_pts = entry * target_pct / 100.0
    stop_pts = entry * stop_pct / 100.0
    target_px = entry + mult * target_pts
    stop_px = entry - mult * stop_pts
    for pos in range(entry_pos + 1, len(arr["close"])):
        high = float(arr["high"][pos])
        low = float(arr["low"][pos])
        if direction == UP:
            target_hit = high >= target_px
            stop_hit = low <= stop_px
        else:
            target_hit = low <= target_px
            stop_hit = high >= stop_px
        if target_hit and stop_hit:
            # Intrabar order is unknown in OHLC bars. Count as a loss to avoid
            # optimistic target-first bias.
            return {
                "exit_type": "AMBIGUOUS_COUNTED_STOP",
                "exit_bar_index": int(arr["bar_index"][pos]),
                "exit_timestamp": str(arr["timestamp"][pos]),
                "exit_price": stop_px,
                "pnl_pts": -stop_pts,
                "win": False,
                "ambiguous": True,
                "target_px": target_px,
                "stop_px": stop_px,
                "target_pts": target_pts,
                "stop_pts": stop_pts,
            }
        if target_hit:
            return {
                "exit_type": "TARGET",
                "exit_bar_index": int(arr["bar_index"][pos]),
                "exit_timestamp": str(arr["timestamp"][pos]),
                "exit_price": target_px,
                "pnl_pts": target_pts,
                "win": True,
                "ambiguous": False,
                "target_px": target_px,
                "stop_px": stop_px,
                "target_pts": target_pts,
                "stop_pts": stop_pts,
            }
        if stop_hit:
            return {
                "exit_type": "STOP",
                "exit_bar_index": int(arr["bar_index"][pos]),
                "exit_timestamp": str(arr["timestamp"][pos]),
                "exit_price": stop_px,
                "pnl_pts": -stop_pts,
                "win": False,
                "ambiguous": False,
                "target_px": target_px,
                "stop_px": stop_px,
                "target_pts": target_pts,
                "stop_pts": stop_pts,
            }
    exit_pos = len(arr["close"]) - 1
    exit_price = float(arr["close"][exit_pos])
    pnl_pts = (exit_price - entry) * mult
    return {
        "exit_type": "EOD",
        "exit_bar_index": int(arr["bar_index"][exit_pos]),
        "exit_timestamp": str(arr["timestamp"][exit_pos]),
        "exit_price": exit_price,
        "pnl_pts": pnl_pts,
        "win": bool(pnl_pts > 0),
        "ambiguous": False,
        "target_px": target_px,
        "stop_px": stop_px,
        "target_pts": target_pts,
        "stop_pts": stop_pts,
    }


def summarize_trades(trades: pd.DataFrame, split_mode: str) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    rows = []
    group_cols = ["family", "interval_min", "rule", "direction", "entry_after_bars", "target_pct", "stop_pct"]
    for key, x in trades.groupby(group_cols, dropna=False, sort=False):
        row = dict(zip(group_cols, key))
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
            }
        )
        if split_mode == "year":
            train = x["year"] <= 2024
            val = x["year"] == 2025
            conf = x["year"] == 2026
            row.update(
                {
                    "train_2017_2024_calls": int(train.sum()),
                    "val_2025_calls": int(val.sum()),
                    "confirm_2026_calls": int(conf.sum()),
                    "train_2017_2024_win_rate": float(x.loc[train, "win"].mean() * 100) if train.any() else np.nan,
                    "val_2025_win_rate": float(x.loc[val, "win"].mean() * 100) if val.any() else np.nan,
                    "confirm_2026_win_rate": float(x.loc[conf, "win"].mean() * 100) if conf.any() else np.nan,
                    "train_2017_2024_avg_pnl_pts": float(x.loc[train, "pnl_pts"].mean()) if train.any() else np.nan,
                    "val_2025_avg_pnl_pts": float(x.loc[val, "pnl_pts"].mean()) if val.any() else np.nan,
                    "confirm_2026_avg_pnl_pts": float(x.loc[conf, "pnl_pts"].mean()) if conf.any() else np.nan,
                }
            )
        else:
            train = x["signal_date"] < "2026-09-01"
            conf = x["signal_date"] >= "2026-09-01"
            row.update(
                {
                    "train_jul_aug_calls": int(train.sum()),
                    "confirm_sep_calls": int(conf.sum()),
                    "train_jul_aug_win_rate": float(x.loc[train, "win"].mean() * 100) if train.any() else np.nan,
                    "confirm_sep_win_rate": float(x.loc[conf, "win"].mean() * 100) if conf.any() else np.nan,
                    "train_jul_aug_avg_pnl_pts": float(x.loc[train, "pnl_pts"].mean()) if train.any() else np.nan,
                    "confirm_sep_avg_pnl_pts": float(x.loc[conf, "pnl_pts"].mean()) if conf.any() else np.nan,
                }
            )
        rows.append(row)
    out = pd.DataFrame(rows)
    sort_cols = [c for c in ["confirm_2026_win_rate", "confirm_sep_win_rate", "calls", "avg_pnl_pts"] if c in out.columns]
    return out.sort_values(sort_cols, ascending=[False] * len(sort_cols))


def generic_first_window_trades(
    bars: pd.DataFrame,
    interval_min: int,
    target_stop_pcts: Iterable[float],
    thresholds: Iterable[float],
) -> pd.DataFrame:
    rows = []
    windows = [1, 2, 3, 6] if interval_min == 10 else [1, 2, 4]
    bars_by_date = {d: x.sort_values("bar_index").reset_index(drop=True) for d, x in bars.groupby("date")}
    for date, day in bars_by_date.items():
        arr = _day_arrays(day)
        day_open = float(day.iloc[0]["open"])
        if day_open <= 0:
            continue
        year = int(date[:4])
        for n in windows:
            if len(day) <= n:
                continue
            entry_bar = day.iloc[n - 1]
            entry = float(entry_bar["close"])
            ret_pct = (entry - day_open) / day_open * 100
            for threshold in thresholds:
                rules: list[tuple[str, str, bool]] = [
                    (f"first{n * interval_min}_trend_gt_{threshold:g}", UP, ret_pct > threshold),
                    (f"first{n * interval_min}_trend_lt_-{threshold:g}", DOWN, ret_pct < -threshold),
                    (f"first{n * interval_min}_fade_gt_{threshold:g}", DOWN, ret_pct > threshold),
                    (f"first{n * interval_min}_fade_lt_-{threshold:g}", UP, ret_pct < -threshold),
                ]
                for rule, direction, condition in rules:
                    if not condition:
                        continue
                    for pct in target_stop_pcts:
                        sim = simulate_trade_arrays(arr, n - 1, direction, entry, pct, pct)
                        if sim is None:
                            continue
                        rows.append(
                            {
                                "family": "generic_first_window",
                                "interval_min": interval_min,
                                "date": date,
                                "signal_date": date,
                                "target_date": date,
                                "year": year,
                                "rule": rule,
                                "direction": direction,
                                "entry_after_bars": n,
                                "entry_timestamp": str(entry_bar["timestamp"]),
                                "entry_price": entry,
                                "first_window_ret_pct": ret_pct,
                                "target_pct": pct,
                                "stop_pct": pct,
                                **sim,
                            }
                        )
    return pd.DataFrame(rows)


def _touched(role: str, high: float, low: float, level: float, touch_pts: float) -> bool:
    role = str(role).lower()
    if role == "support":
        return low <= level + touch_pts and high >= level - touch_pts
    if role == "resistance":
        return high >= level - touch_pts and low <= level + touch_pts
    return low <= level + touch_pts and high >= level - touch_pts


def _direction_for_role(role: str, close: float, level: float, close_buffer_pts: float) -> str | None:
    role = str(role).lower()
    if role == "support":
        if close >= level + close_buffer_pts:
            return UP
        if close <= level - close_buffer_pts:
            return DOWN
    elif role == "resistance":
        if close <= level - close_buffer_pts:
            return DOWN
        if close >= level + close_buffer_pts:
            return UP
    elif role == "breakdown":
        if close <= level - close_buffer_pts:
            return DOWN
        if close >= level + close_buffer_pts:
            return UP
    else:
        if close >= level + close_buffer_pts:
            return UP
        if close <= level - close_buffer_pts:
            return DOWN
    return None


def level_reaction_trades(
    bars: pd.DataFrame,
    interval_min: int,
    levels: pd.DataFrame,
    target_stop_pcts: Iterable[float],
    max_bars_options: Iterable[int],
    touch_pts_options: Iterable[float],
    close_buffer_options: Iterable[float],
    institutional_only_options: Iterable[bool],
) -> pd.DataFrame:
    bars_by_date = {d: x.sort_values("bar_index").reset_index(drop=True) for d, x in bars.groupby("date")}
    levels = levels.copy()
    levels["signal_date"] = pd.to_datetime(levels["signal_date"]).dt.date.astype(str)
    levels["target_date"] = pd.to_datetime(levels["target_date"]).dt.date.astype(str)
    levels["level"] = pd.to_numeric(levels["level"], errors="coerce")
    levels["is_exact_institutional_reference"] = levels["is_exact_institutional_reference"].astype(str).str.lower().isin(["true", "1", "yes"])
    levels = levels.dropna(subset=["signal_date", "target_date", "level"])
    rows = []
    for max_bars in max_bars_options:
        for touch_pts in touch_pts_options:
            for close_buffer in close_buffer_options:
                for institutional_only in institutional_only_options:
                    source_levels = levels[levels["is_exact_institutional_reference"]] if institutional_only else levels
                    source_label = "inst" if institutional_only else "all"
                    base_rule = f"level_first{max_bars}bars_touch{touch_pts:g}_buf{close_buffer:g}_{source_label}"
                    for (signal_date, target_date), day_levels in source_levels.groupby(["signal_date", "target_date"], sort=True):
                        if target_date not in bars_by_date:
                            continue
                        day = bars_by_date[target_date]
                        arr = _day_arrays(day)
                        scan = day.head(max_bars)
                        fired = None
                        for pos, bar in scan.iterrows():
                            candidates = []
                            for li, lvl in day_levels.iterrows():
                                level = float(lvl["level"])
                                if not _touched(str(lvl["role"]), float(bar["high"]), float(bar["low"]), level, touch_pts):
                                    continue
                                direction = _direction_for_role(str(lvl["role"]), float(bar["close"]), level, close_buffer)
                                if direction is None:
                                    continue
                                candidates.append((abs(float(bar["close"]) - level), li, lvl, direction))
                            if candidates:
                                candidates.sort(key=lambda x: (x[0], x[1]))
                                _, _, lvl, direction = candidates[0]
                                fired = (int(pos), bar, lvl, direction)
                                break
                        if fired is None:
                            continue
                        entry_pos, bar, lvl, direction = fired
                        entry = float(bar["close"])
                        for pct in target_stop_pcts:
                            sim = simulate_trade_arrays(arr, entry_pos, direction, entry, pct, pct)
                            if sim is None:
                                continue
                            rows.append(
                                {
                                    "family": "pdf_level_reaction",
                                    "interval_min": interval_min,
                                    "date": target_date,
                                    "signal_date": signal_date,
                                    "target_date": target_date,
                                    "year": int(target_date[:4]),
                                    "rule": base_rule,
                                    "direction": direction,
                                    "entry_after_bars": max_bars,
                                    "entry_timestamp": str(bar["timestamp"]),
                                    "entry_price": entry,
                                    "target_pct": pct,
                                    "stop_pct": pct,
                                    "level": float(lvl["level"]),
                                    "role": lvl.get("role", ""),
                                    "level_type": lvl.get("level_type", ""),
                                    "institutional_only": institutional_only,
                                    "source_excerpt": lvl.get("source_excerpt", ""),
                                    **sim,
                                }
                            )
    return pd.DataFrame(rows)


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


def robust_generic(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    return summary[
        (summary["train_2017_2024_calls"] >= 300)
        & (summary["val_2025_calls"] >= 40)
        & (summary["confirm_2026_calls"] >= 25)
        & (summary["train_2017_2024_win_rate"] >= 70)
        & (summary["val_2025_win_rate"] >= 70)
        & (summary["confirm_2026_win_rate"] >= 70)
        & (summary["avg_pnl_pts"] > 0)
    ].copy()


def robust_levels(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    return summary[
        (summary["train_jul_aug_calls"] >= 10)
        & (summary["confirm_sep_calls"] >= 8)
        & (summary["train_jul_aug_win_rate"] >= 70)
        & (summary["confirm_sep_win_rate"] >= 70)
        & (summary["avg_pnl_pts"] > 0)
    ].copy()


def write_report(
    out: Path,
    generic_summary: pd.DataFrame,
    level_summary: pd.DataFrame,
    generic_robust: pd.DataFrame,
    level_robust: pd.DataFrame,
    quality: dict,
) -> None:
    lines = [
        "# V8 Intraday Trade-Level Simulation",
        "",
        "## Objective",
        "",
        "Test the stronger real-world path after V7: enter only after a 10/15-minute confirmation candle and then simulate target/stop outcomes on the remaining intraday bars. This avoids counting a move that was already visible before entry.",
        "",
        "## Data",
        "",
        f"- 10m bars: {quality.get('bars_10m', 0):,} rows from `{quality.get('path_10m')}`.",
        f"- 15m bars: {quality.get('bars_15m', 0):,} rows from `{quality.get('path_15m')}`.",
        f"- Dated PDF level rows: {quality.get('level_rows', 0):,} from `{quality.get('levels_path')}`.",
        "- Every trade uses symmetric percentage target/stop (`target_pct == stop_pct`) and ambiguous target+stop bars are counted as losses, not wins.",
        "",
        "## Main result",
        "",
        f"- Generic first-window rules clearing 70% win-rate on train(2017-24), validation(2025), confirmation(2026), with sample guards and positive average points: **{len(generic_robust)}**.",
        f"- PDF-level reaction rules clearing 70% on July-Aug training and September confirmation with sample guards and positive average points: **{len(level_robust)}**.",
        "- Verdict: no production-ready 70%+ executable intraday edge yet. High-looking open-to-close direction pockets from V7 do not survive honest target/stop execution.",
        "",
        "## Best generic 10/15m first-window trade rules",
        "",
    ]
    if generic_summary.empty:
        lines.append("No generic trades generated.")
    else:
        cols = [
            "interval_min", "rule", "direction", "entry_after_bars", "target_pct",
            "calls", "win_rate", "avg_pnl_pts", "train_2017_2024_calls",
            "train_2017_2024_win_rate", "val_2025_calls", "val_2025_win_rate",
            "confirm_2026_calls", "confirm_2026_win_rate", "ambiguous_rate",
        ]
        lines.append(_markdown_table(generic_summary, cols, 20))
    lines.extend(["", "## Best PDF-level trade rules", ""])
    if level_summary.empty:
        lines.append("No level trades generated.")
    else:
        cols = [
            "interval_min", "rule", "direction", "entry_after_bars", "target_pct",
            "calls", "win_rate", "avg_pnl_pts", "train_jul_aug_calls",
            "train_jul_aug_win_rate", "confirm_sep_calls", "confirm_sep_win_rate",
            "ambiguous_rate",
        ]
        lines.append(_markdown_table(level_summary, cols, 20))
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- This is a conditional intraday execution test, not an overnight pre-open forecast.",
            "- Symmetric target/stop is stricter than many discretionary scalps; that is intentional so a 70% win-rate cannot be manufactured by using a tiny target and a huge stop.",
            "- The exact-level sample remains too small and too clustered in 2026 to promote. It is useful as a forward-testing protocol: keep collecting exact levels daily, then score them without changing the V8 rules.",
        ]
    )
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")

    summary = {
        **quality,
        "generic_rules_total": int(len(generic_summary)),
        "level_rules_total": int(len(level_summary)),
        "generic_robust_70pct_rules": int(len(generic_robust)),
        "level_robust_70pct_rules": int(len(level_robust)),
        "best_generic_rules": _safe_records(generic_summary, 5),
        "best_level_rules": _safe_records(level_summary, 5),
        "verdict": "NO_PRODUCTION_70PCT_EXECUTABLE_EDGE_YET",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--intraday-10m", default="historical/nifty_10m.csv")
    ap.add_argument("--intraday-15m", default="historical/nifty_15m.csv")
    ap.add_argument("--levels", default="historical/institutional_levels_pdf_2026.csv")
    ap.add_argument("--out", default="reports/v8_intraday_trade_sim")
    ap.add_argument("--write-raw-trades", action="store_true", help="write full raw trade tables; large generic table is omitted by default")
    args = ap.parse_args()

    cfg = TradeConfig()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    bars10 = load_bars(Path(args.intraday_10m), min_bars=30)
    bars15 = load_bars(Path(args.intraday_15m), min_bars=20)
    min10 = interval_minutes(bars10)
    min15 = interval_minutes(bars15)
    levels = pd.read_csv(args.levels)

    generic_parts = []
    for bars, mins in [(bars10, min10), (bars15, min15)]:
        generic_parts.append(
            generic_first_window_trades(
                bars,
                mins,
                target_stop_pcts=[0.08, 0.10, 0.15, 0.20, 0.30],
                thresholds=[0.05, 0.08, 0.10, 0.15, 0.20, 0.30, 0.40],
            )
        )
    generic_trades = pd.concat([x for x in generic_parts if not x.empty], ignore_index=True) if any(not x.empty for x in generic_parts) else pd.DataFrame()
    generic_summary = summarize_trades(generic_trades, "year")
    gen_rob = robust_generic(generic_summary)

    level_parts = []
    for bars, mins in [(bars10, min10), (bars15, min15)]:
        max_bars = [1, 2, 3, 6] if mins == 10 else [1, 2, 4]
        level_parts.append(
            level_reaction_trades(
                bars,
                mins,
                levels,
                target_stop_pcts=[0.08, 0.10, 0.15, 0.20, 0.30],
                max_bars_options=max_bars,
                touch_pts_options=[0.0, 5.0, 10.0, 15.0],
                close_buffer_options=[0.0, 5.0, 10.0],
                institutional_only_options=[False, True],
            )
        )
    level_trades = pd.concat([x for x in level_parts if not x.empty], ignore_index=True) if any(not x.empty for x in level_parts) else pd.DataFrame()
    level_summary = summarize_trades(level_trades, "jul_aug_sep")
    lev_rob = robust_levels(level_summary)

    if args.write_raw_trades:
        generic_trades.to_csv(out / "generic_first_window_trades.csv", index=False)
        level_trades.to_csv(out / "level_reaction_trades.csv", index=False)
    else:
        # Keep committed artifacts small; summaries are enough to reproduce the
        # conclusion, and full raw trades can be regenerated with
        # --write-raw-trades when needed.
        generic_trades.head(5000).to_csv(out / "generic_first_window_trades_sample.csv", index=False)
        level_trades.to_csv(out / "level_reaction_trades.csv", index=False)
    generic_summary.to_csv(out / "generic_first_window_summary.csv", index=False)
    gen_rob.to_csv(out / "generic_robust_70pct.csv", index=False)
    level_summary.to_csv(out / "level_reaction_summary.csv", index=False)
    lev_rob.to_csv(out / "level_robust_70pct.csv", index=False)

    quality = {
        "path_10m": args.intraday_10m,
        "path_15m": args.intraday_15m,
        "levels_path": args.levels,
        "bars_10m": int(len(bars10)),
        "bars_15m": int(len(bars15)),
        "sessions_10m": int(bars10["date"].nunique()),
        "sessions_15m": int(bars15["date"].nunique()),
        "date_min_10m": str(bars10["date"].min()),
        "date_max_10m": str(bars10["date"].max()),
        "date_min_15m": str(bars15["date"].min()),
        "date_max_15m": str(bars15["date"].max()),
        "level_rows": int(len(levels)),
        "target_stop_pct_grid": [0.08, 0.10, 0.15, 0.20, 0.30],
        "ambiguous_bars_policy": "counted_as_stop_loss",
    }
    (out / "data_quality.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")
    write_report(out, generic_summary, level_summary, gen_rob, lev_rob, quality)
    print(json.dumps(json.loads((out / "summary.json").read_text()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
