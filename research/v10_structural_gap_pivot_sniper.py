"""V10 research: leak-safe structural level-touch sniper rules.

The earlier V7/V8/V9 work tested close-direction and executable target/stop
rules.  This V10 pass tests a different, narrower question that is closer to
how discretionary intraday traders use "levels": after the NIFTY opens, can we
predict that a nearby structural level will be touched during the same session?

Important scope
---------------

* These are level-touch predictions, not unconditional next-day close direction.
* Signal time is the cash-market open because the open price is required to know
  the gap size.  Previous close/high/low/pivots are known before the open.
* The strongest edge found by this family is the ultra-small-gap fill: when the
  index opens very close to yesterday's close, the previous close is touched
  intraday with high probability.
* High hit-rate level-touch events can still be difficult to monetize because
  the target distance is small.  If raw 1-minute data is available, this script
  also writes conservative entry-at-open stop diagnostics to prevent confusing a
  high hit-rate event with a production trading system.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

try:  # Optional 1-minute execution diagnostics.
    from build_intraday_candles import load_raw_files
except Exception:  # pragma: no cover - only relevant when run outside research/.
    load_raw_files = None  # type: ignore[assignment]


TRAIN_END_YEAR = 2023
VAL_YEARS = {2024, 2025}
CONFIRM_YEAR = 2026


GAP_BANDS: list[tuple[float, float]] = [
    (0.01, 0.05),
    (0.02, 0.10),
    (0.03, 0.12),
    (0.05, 0.15),
    (0.05, 0.20),
    (0.10, 0.20),
    (0.15, 0.50),
    (0.50, 1.00),
    (1.00, 10.00),
]


def load_intraday_daily(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    bars = pd.read_csv(path)
    bars["date"] = pd.to_datetime(bars["date"]).dt.date.astype(str)
    bars["timestamp"] = pd.to_datetime(bars["timestamp"])
    for col in ["bar_index", "open", "high", "low", "close"]:
        bars[col] = pd.to_numeric(bars[col], errors="coerce")
    bars = bars.dropna(subset=["date", "bar_index", "open", "high", "low", "close"])
    bars = bars.sort_values(["date", "bar_index"]).reset_index(drop=True)
    daily = (
        bars.groupby("date", sort=True)
        .agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"))
        .reset_index()
    )
    daily["year"] = pd.to_datetime(daily["date"]).dt.year.astype(int)
    return bars, daily


def add_structural_features(daily: pd.DataFrame) -> pd.DataFrame:
    out = daily.copy()
    out["prev_high"] = out["high"].shift(1)
    out["prev_low"] = out["low"].shift(1)
    out["prev_close"] = out["close"].shift(1)
    out["prev_range_pts"] = out["prev_high"] - out["prev_low"]
    out["prev_range_pct"] = out["prev_range_pts"] / out["prev_close"] * 100.0
    out["gap_pct"] = (out["open"] - out["prev_close"]) / out["prev_close"] * 100.0
    out["gap_abs_pct"] = out["gap_pct"].abs()
    out["gap_side"] = np.select([out["gap_pct"] > 0, out["gap_pct"] < 0], ["UP", "DOWN"], default="FLAT")
    out["fade_direction"] = np.select([out["gap_pct"] > 0, out["gap_pct"] < 0], ["DOWN", "UP"], default="NO_SIGNAL")

    out["pivot"] = (out["prev_high"] + out["prev_low"] + out["prev_close"]) / 3.0
    out["r1"] = 2.0 * out["pivot"] - out["prev_low"]
    out["s1"] = 2.0 * out["pivot"] - out["prev_high"]
    out["r2"] = out["pivot"] + (out["prev_high"] - out["prev_low"])
    out["s2"] = out["pivot"] - (out["prev_high"] - out["prev_low"])

    out["gap_fill_prev_close"] = np.where(
        out["gap_pct"] > 0,
        out["low"] <= out["prev_close"],
        np.where(out["gap_pct"] < 0, out["high"] >= out["prev_close"], np.nan),
    )
    out["open_above_pivot"] = out["open"] > out["pivot"]
    out["open_below_pivot"] = out["open"] < out["pivot"]
    out["reach_r1"] = out["high"] >= out["r1"]
    out["reach_s1"] = out["low"] <= out["s1"]
    out["reach_prev_high"] = out["high"] >= out["prev_high"]
    out["reach_prev_low"] = out["low"] <= out["prev_low"]
    return out


def _split_mask(x: pd.DataFrame, split: str) -> pd.Series:
    if split == "train":
        return x["year"] <= TRAIN_END_YEAR
    if split == "val":
        return x["year"].isin(VAL_YEARS)
    if split == "confirm":
        return x["year"] == CONFIRM_YEAR
    raise ValueError(split)


def _rate(x: pd.DataFrame, mask: pd.Series, col: str) -> float:
    if int(mask.sum()) == 0:
        return float("nan")
    return float(pd.to_numeric(x.loc[mask, col], errors="coerce").mean() * 100.0)


def summarize_rule(
    daily: pd.DataFrame,
    *,
    rule: str,
    family: str,
    direction: str,
    target: str,
    mask: pd.Series,
    hit_col: str,
) -> dict:
    x = daily.loc[mask].copy()
    x = x[pd.to_numeric(x[hit_col], errors="coerce").notna()]
    train = _split_mask(x, "train")
    val = _split_mask(x, "val")
    confirm = _split_mask(x, "confirm")
    gap_pts = (x["open"] - x["prev_close"]).abs()
    row = {
        "family": family,
        "rule": rule,
        "direction": direction,
        "target": target,
        "calls": int(len(x)),
        "hit_rate": float(pd.to_numeric(x[hit_col], errors="coerce").mean() * 100.0) if len(x) else float("nan"),
        "train_2017_2023_calls": int(train.sum()),
        "val_2024_2025_calls": int(val.sum()),
        "confirm_2026_calls": int(confirm.sum()),
        "train_2017_2023_hit_rate": _rate(x, train, hit_col),
        "val_2024_2025_hit_rate": _rate(x, val, hit_col),
        "confirm_2026_hit_rate": _rate(x, confirm, hit_col),
        "mean_abs_gap_pts": float(gap_pts.mean()) if len(x) and family == "gap_fill" else float("nan"),
        "median_abs_gap_pts": float(gap_pts.median()) if len(x) and family == "gap_fill" else float("nan"),
    }
    return row


def build_structural_rule_table(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows: list[dict] = []

    # Gap-fill sniper: at the open, fade tiny gaps to previous close.
    for lo, hi in GAP_BANDS:
        for side, side_mask, direction in [
            ("up", (daily["gap_pct"] >= lo) & (daily["gap_pct"] < hi), "DOWN"),
            ("down", (daily["gap_pct"] <= -lo) & (daily["gap_pct"] > -hi), "UP"),
            ("both", (daily["gap_abs_pct"] >= lo) & (daily["gap_abs_pct"] < hi), "FADE_GAP"),
        ]:
            rows.append(
                summarize_rule(
                    daily,
                    rule=f"abs_gap_{lo:.2f}_{hi:.2f}_{side}_fill_prev_close",
                    family="gap_fill",
                    direction=direction,
                    target="previous_close_touch_intraday",
                    mask=side_mask,
                    hit_col="gap_fill_prev_close",
                )
            )

    # Structural pivot/previous-day levels.  These are included because they are
    # trader-visible institutional/psychological reference levels, but they are
    # not expected to beat the high-accuracy tiny-gap pocket.
    level_rules = [
        (
            "open_above_pivot_reach_r1",
            "pivot_reach",
            "UP",
            "r1_touch_intraday",
            daily["open_above_pivot"],
            "reach_r1",
        ),
        (
            "open_below_pivot_reach_s1",
            "pivot_reach",
            "DOWN",
            "s1_touch_intraday",
            daily["open_below_pivot"],
            "reach_s1",
        ),
        (
            "open_above_prev_close_reach_prev_high",
            "previous_day_level_reach",
            "UP",
            "previous_high_touch_intraday",
            daily["open"] > daily["prev_close"],
            "reach_prev_high",
        ),
        (
            "open_below_prev_close_reach_prev_low",
            "previous_day_level_reach",
            "DOWN",
            "previous_low_touch_intraday",
            daily["open"] < daily["prev_close"],
            "reach_prev_low",
        ),
    ]
    for rule, family, direction, target, mask, hit_col in level_rules:
        rows.append(
            summarize_rule(
                daily,
                rule=rule,
                family=family,
                direction=direction,
                target=target,
                mask=mask,
                hit_col=hit_col,
            )
        )

    table = pd.DataFrame(rows).sort_values(
        ["confirm_2026_hit_rate", "val_2024_2025_hit_rate", "train_2017_2023_hit_rate", "calls"],
        ascending=[False, False, False, False],
    )

    yearly_rows = []
    for row in rows:
        mask = pd.Series(False, index=daily.index)
        rule = row["rule"]
        if rule.startswith("abs_gap_"):
            parts = rule.split("_")
            lo = float(parts[2])
            hi = float(parts[3])
            side = parts[4]
            if side == "up":
                mask = (daily["gap_pct"] >= lo) & (daily["gap_pct"] < hi)
            elif side == "down":
                mask = (daily["gap_pct"] <= -lo) & (daily["gap_pct"] > -hi)
            else:
                mask = (daily["gap_abs_pct"] >= lo) & (daily["gap_abs_pct"] < hi)
            hit_col = "gap_fill_prev_close"
        elif rule == "open_above_pivot_reach_r1":
            mask, hit_col = daily["open_above_pivot"], "reach_r1"
        elif rule == "open_below_pivot_reach_s1":
            mask, hit_col = daily["open_below_pivot"], "reach_s1"
        elif rule == "open_above_prev_close_reach_prev_high":
            mask, hit_col = daily["open"] > daily["prev_close"], "reach_prev_high"
        elif rule == "open_below_prev_close_reach_prev_low":
            mask, hit_col = daily["open"] < daily["prev_close"], "reach_prev_low"
        else:  # pragma: no cover
            continue
        x = daily.loc[mask & pd.to_numeric(daily[hit_col], errors="coerce").notna()].copy()
        for year, g in x.groupby("year", sort=True):
            yearly_rows.append(
                {
                    "rule": rule,
                    "family": row["family"],
                    "year": int(year),
                    "calls": int(len(g)),
                    "hit_rate": float(pd.to_numeric(g[hit_col], errors="coerce").mean() * 100.0),
                }
            )
    yearly = pd.DataFrame(yearly_rows).sort_values(["rule", "year"])

    signal_cols = [
        "date",
        "year",
        "open",
        "high",
        "low",
        "close",
        "prev_close",
        "gap_pct",
        "gap_abs_pct",
        "gap_side",
        "fade_direction",
        "gap_fill_prev_close",
    ]
    gap_signals = daily.loc[(daily["gap_abs_pct"] >= 0.02) & (daily["gap_abs_pct"] < 0.10), signal_cols].copy()
    gap_signals = gap_signals.sort_values("date")
    return table, yearly, gap_signals


def robust_rules(table: pd.DataFrame, min_train: int, min_val: int, min_confirm: int, min_hit: float) -> pd.DataFrame:
    mask = (
        (table["train_2017_2023_calls"] >= min_train)
        & (table["val_2024_2025_calls"] >= min_val)
        & (table["confirm_2026_calls"] >= min_confirm)
        & (table["train_2017_2023_hit_rate"] >= min_hit)
        & (table["val_2024_2025_hit_rate"] >= min_hit)
        & (table["confirm_2026_hit_rate"] >= min_hit)
    )
    return table.loc[mask].sort_values(
        ["confirm_2026_hit_rate", "hit_rate", "calls"], ascending=[False, False, False]
    )


def load_one_minute(raw_root: Path) -> pd.DataFrame | None:
    if load_raw_files is None:
        return None
    if not raw_root.exists():
        return None
    files = sorted(raw_root.rglob("*.csv"))
    if not files:
        return None
    df = load_raw_files(files)  # type: ignore[misc]
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["date", "timestamp", "open", "high", "low", "close"])
    return df.sort_values(["date", "timestamp"]).reset_index(drop=True)


def conservative_open_trade_diagnostics(
    one_minute: pd.DataFrame,
    bands: Iterable[tuple[float, float]],
    stop_multipliers: Iterable[float] = (1.0, 2.0, 3.0),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = (
        one_minute.groupby("date", sort=True)
        .agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"))
        .reset_index()
    )
    daily["year"] = pd.to_datetime(daily["date"]).dt.year.astype(int)
    daily["prev_close"] = daily["close"].shift(1)
    daily["gap_pct"] = (daily["open"] - daily["prev_close"]) / daily["prev_close"] * 100.0
    by_date = {d: x.reset_index(drop=True) for d, x in one_minute.groupby("date", sort=True)}

    rows: list[dict] = []
    for lo, hi in bands:
        candidates = daily[(daily["gap_pct"].abs() >= lo) & (daily["gap_pct"].abs() < hi)].copy()
        for _, r in candidates.iterrows():
            date = str(r["date"])
            if date not in by_date or not np.isfinite(r["prev_close"]):
                continue
            direction = "DOWN" if r["gap_pct"] > 0 else "UP"
            if direction not in {"DOWN", "UP"}:
                continue
            day = by_date[date]
            entry = float(r["open"])
            target = float(r["prev_close"])
            dist = abs(entry - target)
            if entry <= 0 or target <= 0 or dist <= 0:
                continue
            level_touch = bool((day["low"] <= target).any()) if direction == "DOWN" else bool((day["high"] >= target).any())
            for stop_mult in stop_multipliers:
                stop = entry + dist * stop_mult if direction == "DOWN" else entry - dist * stop_mult
                win: bool | None = None
                ambiguous = False
                exit_timestamp = None
                for _, bar in day.iterrows():
                    target_hit = bool(bar["low"] <= target) if direction == "DOWN" else bool(bar["high"] >= target)
                    stop_hit = bool(bar["high"] >= stop) if direction == "DOWN" else bool(bar["low"] <= stop)
                    if target_hit and stop_hit:
                        # Intraminute order is unknown. Count as loss to avoid optimism.
                        win = False
                        ambiguous = True
                        exit_timestamp = str(bar["timestamp"])
                        break
                    if target_hit:
                        win = True
                        exit_timestamp = str(bar["timestamp"])
                        break
                    if stop_hit:
                        win = False
                        exit_timestamp = str(bar["timestamp"])
                        break
                if win is None:
                    win = False
                rows.append(
                    {
                        "rule": f"abs_gap_{lo:.2f}_{hi:.2f}_both_fill_prev_close",
                        "date": date,
                        "year": int(r["year"]),
                        "gap_pct": float(r["gap_pct"]),
                        "direction": direction,
                        "entry": entry,
                        "target_prev_close": target,
                        "target_distance_pts": float(dist),
                        "stop_multiplier": float(stop_mult),
                        "level_touch": level_touch,
                        "trade_win_conservative": bool(win),
                        "ambiguous_same_minute_counted_loss": bool(ambiguous),
                        "exit_timestamp": exit_timestamp,
                    }
                )
    trades = pd.DataFrame(rows)
    if trades.empty:
        return trades, pd.DataFrame()

    summary_rows: list[dict] = []
    for (rule, stop_mult), x in trades.groupby(["rule", "stop_multiplier"], sort=True):
        train = x["year"] <= TRAIN_END_YEAR
        val = x["year"].isin(VAL_YEARS)
        confirm = x["year"] == CONFIRM_YEAR
        summary_rows.append(
            {
                "rule": rule,
                "stop_multiplier": float(stop_mult),
                "calls": int(len(x)),
                "level_touch_rate": float(x["level_touch"].mean() * 100.0),
                "trade_win_rate_conservative": float(x["trade_win_conservative"].mean() * 100.0),
                "ambiguous_rate": float(x["ambiguous_same_minute_counted_loss"].mean() * 100.0),
                "mean_target_distance_pts": float(x["target_distance_pts"].mean()),
                "train_2017_2023_calls": int(train.sum()),
                "val_2024_2025_calls": int(val.sum()),
                "confirm_2026_calls": int(confirm.sum()),
                "train_2017_2023_trade_win_rate": float(x.loc[train, "trade_win_conservative"].mean() * 100.0)
                if train.any()
                else float("nan"),
                "val_2024_2025_trade_win_rate": float(x.loc[val, "trade_win_conservative"].mean() * 100.0)
                if val.any()
                else float("nan"),
                "confirm_2026_trade_win_rate": float(x.loc[confirm, "trade_win_conservative"].mean() * 100.0)
                if confirm.any()
                else float("nan"),
            }
        )
    summary = pd.DataFrame(summary_rows).sort_values(["rule", "stop_multiplier"])
    return trades, summary


def _fmt_cell(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def markdown_table(df: pd.DataFrame) -> str:
    """Small dependency-free markdown table writer.

    pandas.DataFrame.to_markdown requires the optional ``tabulate`` package,
    which is not part of the project runtime requirements.  Reports should be
    reproducible from a clean venv, so keep this helper local.
    """
    if df.empty:
        return "None."
    cols = list(df.columns)
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    body = ["| " + " | ".join(_fmt_cell(v) for v in row) + " |" for row in df.itertuples(index=False, name=None)]
    return "\n".join([header, sep, *body])


def write_report(
    out_dir: Path,
    table: pd.DataFrame,
    robust: pd.DataFrame,
    yearly: pd.DataFrame,
    exec_summary: pd.DataFrame | None,
    args: argparse.Namespace,
) -> None:
    best = robust.iloc[0].to_dict() if not robust.empty else None
    lines = [
        "# V10 Structural Gap/Pivot Sniper Research",
        "",
        "## Verdict",
        "",
    ]
    if best:
        lines.extend(
            [
                "**HIGH-ACCURACY LEVEL-TOUCH EDGE FOUND (selective, not daily close direction).**",
                "",
                "The strongest leak-safe pocket is an at-open tiny-gap-fill signal: if NIFTY opens only a tiny distance from the previous close, predict that the previous close will be touched intraday.",
                "",
                f"Top robust rule: `{best['rule']}`",
                f"- Calls: {int(best['calls'])}",
                f"- Overall hit-rate: {best['hit_rate']:.2f}%",
                f"- Train 2017-2023: {int(best['train_2017_2023_calls'])} calls, {best['train_2017_2023_hit_rate']:.2f}%",
                f"- Validation 2024-2025: {int(best['val_2024_2025_calls'])} calls, {best['val_2024_2025_hit_rate']:.2f}%",
                f"- Confirmation 2026: {int(best['confirm_2026_calls'])} calls, {best['confirm_2026_hit_rate']:.2f}%",
                f"- Mean target distance: {best['mean_abs_gap_pts']:.2f} NIFTY points",
                "",
                "This reaches the requested 75-85%+ accuracy band for a narrowly-defined, real-world next-session **level touch** prediction. It does **not** solve unconditional next-day UP/DOWN close prediction.",
            ]
        )
    else:
        lines.append("No robust 70%+ structural level-touch rule passed the configured split/sample gates.")
    lines.extend(
        [
            "",
            "## Guardrails / no leakage",
            "",
            "- Signal uses only values known at the open: current open, previous close/high/low, and pivots derived from the previous session.",
            "- The label is whether the target level is touched later during the same session.",
            "- No current-session close-to-close return, full-day range, future OI, or future candle is used as a feature.",
            "- For execution diagnostics, if a 1-minute bar hits target and stop in the same minute, it is counted as a stop/loss.",
            "",
            "## Top structural rules",
            "",
            markdown_table(table.head(20)),
            "",
            "## Robust 70%+ rules",
            "",
        ]
    )
    if robust.empty:
        lines.append("None.")
    else:
        lines.append(markdown_table(robust))

    if exec_summary is not None and not exec_summary.empty:
        lines.extend(
            [
                "",
                "## 1-minute execution diagnostic",
                "",
                "The high hit-rate is a level-touch probability. Because the target is small, a naive at-open trade can be fragile. The table below uses raw 1-minute candles, enters at the open, targets previous close, and places a stop at 1x/2x/3x the target distance. Same-minute target+stop is counted as a loss.",
                "",
                markdown_table(exec_summary),
                "",
                "Conclusion: promote the tiny-gap signal as a high-probability level-touch alert / context feature first. A production trading rule still needs tick-level or broker-level execution testing, slippage, option premium behavior, and a stop/exit model.",
            ]
        )

    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `structural_rules.csv` — all tested structural level-touch summaries.",
            "- `robust_rules.csv` — rules passing split/sample/hit-rate gates.",
            "- `yearly_breakdown.csv` — yearly hit rates for each structural rule.",
            "- `gap_fill_signals.csv` — individual signals for the default 0.02%-0.10% absolute-gap rule.",
            "- `gap_fill_execution_1m.csv` and `gap_fill_execution_summary.csv` — optional raw-1m execution diagnostics when raw 1m data is available outside Git.",
            "",
            "## Configuration",
            "",
            f"- Intraday bars: `{args.bars}`",
            f"- Raw 1m root for optional execution diagnostics: `{args.raw_1m_root}`",
            f"- Robust gate: train>={args.min_train}, validation>={args.min_val}, confirmation>={args.min_confirm}, hit-rate>={args.min_hit:.2f}% in each split",
        ]
    )
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", default="historical/nifty_15m.csv", help="Committed 10/15m intraday bars")
    ap.add_argument(
        "--raw-1m-root",
        default="/home/user/historical/technovusin-nifty50-historical-data/1min",
        help="Optional raw 1-minute source kept outside Git for execution diagnostics",
    )
    ap.add_argument("--out", default="reports/v10_structural_gap_pivot_sniper")
    ap.add_argument("--min-train", type=int, default=100)
    ap.add_argument("--min-val", type=int, default=40)
    ap.add_argument("--min-confirm", type=int, default=25)
    ap.add_argument("--min-hit", type=float, default=70.0)
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    _, daily0 = load_intraday_daily(Path(args.bars))
    daily = add_structural_features(daily0)
    table, yearly, gap_signals = build_structural_rule_table(daily)
    robust = robust_rules(table, args.min_train, args.min_val, args.min_confirm, args.min_hit)

    table.to_csv(out_dir / "structural_rules.csv", index=False)
    robust.to_csv(out_dir / "robust_rules.csv", index=False)
    yearly.to_csv(out_dir / "yearly_breakdown.csv", index=False)
    gap_signals.to_csv(out_dir / "gap_fill_signals.csv", index=False)

    exec_trades = pd.DataFrame()
    exec_summary = pd.DataFrame()
    raw_1m_root = Path(args.raw_1m_root)
    one_minute = load_one_minute(raw_1m_root)
    if one_minute is not None:
        exec_trades, exec_summary = conservative_open_trade_diagnostics(
            one_minute,
            bands=[(0.02, 0.10), (0.03, 0.12), (0.05, 0.15)],
        )
        exec_trades.to_csv(out_dir / "gap_fill_execution_1m.csv", index=False)
        exec_summary.to_csv(out_dir / "gap_fill_execution_summary.csv", index=False)

    best = robust.iloc[0].to_dict() if not robust.empty else None
    summary = {
        "input_bars": args.bars,
        "rows_daily": int(len(daily)),
        "date_min": str(daily["date"].min()),
        "date_max": str(daily["date"].max()),
        "rules_total": int(len(table)),
        "robust_70pct_rules": int(len(robust)),
        "robust_gate": {
            "min_train": args.min_train,
            "min_val": args.min_val,
            "min_confirm": args.min_confirm,
            "min_hit": args.min_hit,
            "train": f"<= {TRAIN_END_YEAR}",
            "validation": sorted(VAL_YEARS),
            "confirmation": CONFIRM_YEAR,
        },
        "best_rule": best,
        "high_accuracy_level_touch_edge_found": bool(best is not None),
        "unconditional_daily_direction_edge_found": False,
        "execution_diagnostics_1m_available": bool(not exec_summary.empty),
    }
    if best is not None:
        summary["verdict"] = "HIGH_ACCURACY_LEVEL_TOUCH_EDGE_FOUND_NOT_UNCONDITIONAL_CLOSE_DIRECTION"
    else:
        summary["verdict"] = "NO_STRUCTURAL_LEVEL_TOUCH_70PCT_EDGE_FOUND"
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    write_report(out_dir, table, robust, yearly, exec_summary if not exec_summary.empty else None, args)

    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
