"""V7 research: 10-15 minute intraday candles + dated institutional levels.

This is the next step after V4/V5/V6 failed to find a robust EOD/OI-only edge.
It deliberately changes the target from an unconditional close-to-close forecast
into a *conditional next-day execution plan*:

* use the prior evening's published/date-stamped levels only;
* wait for a 15-minute candle around those levels;
* score only the post-confirmation move, while separately reporting the old
  open-to-close / close-to-close direction hit rates.

The script also runs a long 2017-2026 intraday price-rule sanity check so that
any high score from the small PDF-level sample is not mistaken for a robust
market-wide edge.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

UP = "UP"
DOWN = "DOWN"
FLAT = "FLAT"


@dataclass(frozen=True)
class EvalConfig:
    flat_threshold_pct: float = 0.10
    post_entry_min_move_pct: float = 0.05
    min_complete_bars_per_day: int = 20


def _sign_from_return(ret_pct: float, flat_threshold_pct: float = 0.10) -> str:
    if pd.isna(ret_pct):
        return FLAT
    if ret_pct > flat_threshold_pct:
        return UP
    if ret_pct < -flat_threshold_pct:
        return DOWN
    return FLAT


def _dir_mult(direction: str) -> int:
    if direction == UP:
        return 1
    if direction == DOWN:
        return -1
    return 0


def load_intraday(path: Path, min_complete_bars: int = 20) -> pd.DataFrame:
    bars = pd.read_csv(path)
    bars["date"] = pd.to_datetime(bars["date"]).dt.date.astype(str)
    bars["timestamp"] = pd.to_datetime(bars["timestamp"])
    for c in ["bar_index", "open", "high", "low", "close", "volume", "minute_count"]:
        if c in bars.columns:
            bars[c] = pd.to_numeric(bars[c], errors="coerce")
    counts = bars.groupby("date")["bar_index"].nunique()
    good_dates = counts[counts >= min_complete_bars].index
    return bars[bars["date"].isin(good_dates)].copy()


def make_daily_from_intraday(bars: pd.DataFrame, cfg: EvalConfig) -> pd.DataFrame:
    g = bars.sort_values(["date", "bar_index"]).groupby("date", sort=True)
    daily = g.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        bars=("bar_index", "nunique"),
        first15_open=("open", "first"),
        first15_close=("close", "first"),
        first15_high=("high", "first"),
        first15_low=("low", "first"),
    ).reset_index()
    # First 30/60m features.
    def agg_first(day: pd.DataFrame, n: int) -> pd.Series:
        sub = day.sort_values("bar_index").head(n)
        return pd.Series(
            {
                f"first{n*15}_close": sub["close"].iloc[-1],
                f"first{n*15}_high": sub["high"].max(),
                f"first{n*15}_low": sub["low"].min(),
            }
        )

    firsts = []
    for d, day in bars.groupby("date", sort=True):
        row = {"date": d}
        for n in (2, 4):
            row.update(agg_first(day, n).to_dict())
        firsts.append(row)
    firsts_df = pd.DataFrame(firsts)
    daily = daily.merge(firsts_df, on="date", how="left")
    daily["prev_close"] = daily["close"].shift(1)
    daily["gap_pct"] = (daily["open"] - daily["prev_close"]) / daily["prev_close"] * 100
    daily["oc_ret_pct"] = (daily["close"] - daily["open"]) / daily["open"] * 100
    daily["cc_ret_pct"] = (daily["close"] - daily["prev_close"]) / daily["prev_close"] * 100
    daily["first15_ret_pct"] = (daily["first15_close"] - daily["open"]) / daily["open"] * 100
    daily["first30_ret_pct"] = (daily["first30_close"] - daily["open"]) / daily["open"] * 100
    daily["first60_ret_pct"] = (daily["first60_close"] - daily["open"]) / daily["open"] * 100
    daily["first15_range_pct"] = (daily["first15_high"] - daily["first15_low"]) / daily["open"] * 100
    daily["day_range_pct"] = (daily["high"] - daily["low"]) / daily["open"] * 100
    for col in ["oc_ret_pct", "cc_ret_pct", "first15_ret_pct", "first30_ret_pct", "first60_ret_pct"]:
        daily[col.replace("_pct", "_sign")] = daily[col].map(
            lambda x: _sign_from_return(x, cfg.flat_threshold_pct)
        )
    return daily


def _rate(num: int, den: int) -> float:
    return float(num / den * 100) if den else float("nan")


def _hit(direction: str, actual: str) -> bool | None:
    if direction not in (UP, DOWN) or actual not in (UP, DOWN):
        return None
    return direction == actual


def load_v3_predictions(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["signal_date", "target_date", "predicted_class", "composite", "confidence"])
    df = pd.read_csv(path)
    keep = [c for c in ["signal_date", "target_date", "predicted_class", "composite", "confidence", "actionability"] if c in df.columns]
    df = df[keep].copy()
    df["signal_date"] = pd.to_datetime(df["signal_date"]).dt.date.astype(str)
    df["target_date"] = pd.to_datetime(df["target_date"]).dt.date.astype(str)
    return df.rename(columns={"predicted_class": "v3_predicted_class", "composite": "v3_composite", "confidence": "v3_confidence"})


def _direction_for_role(role: str, close: float, level: float, buffer_pts: float) -> str | None:
    role = str(role).lower()
    if role == "support":
        if close >= level + buffer_pts:
            return UP
        if close <= level - buffer_pts:
            return DOWN
    elif role == "resistance":
        if close <= level - buffer_pts:
            return DOWN
        if close >= level + buffer_pts:
            return UP
    elif role == "breakdown":
        if close <= level - buffer_pts:
            return DOWN
        if close >= level + buffer_pts:
            return UP
    else:  # pivot/target/unknown: pure close-side branch.
        if close >= level + buffer_pts:
            return UP
        if close <= level - buffer_pts:
            return DOWN
    return None


def _touched(role: str, high: float, low: float, level: float, touch_pts: float) -> bool:
    role = str(role).lower()
    if role == "support":
        return low <= level + touch_pts and high >= level - touch_pts
    if role == "resistance":
        return high >= level - touch_pts and low <= level + touch_pts
    # Pivot / target / breakdown: require the candle range to overlap the level.
    return low <= level + touch_pts and high >= level - touch_pts


def evaluate_level_triggers(
    bars: pd.DataFrame,
    daily: pd.DataFrame,
    levels: pd.DataFrame,
    cfg: EvalConfig,
    max_bars_options: Iterable[int] = (1, 2, 4, 8, 25),
    touch_pts_options: Iterable[float] = (0.0, 5.0, 10.0, 15.0, 25.0),
    close_buffer_options: Iterable[float] = (0.0, 5.0, 10.0),
    institutional_only_options: Iterable[bool] = (False, True),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    bars_by_date = {d: x.sort_values("bar_index").copy() for d, x in bars.groupby("date")}
    daily_by_date = daily.set_index("date").to_dict("index")
    triggers: list[dict] = []

    levels = levels.copy()
    levels["signal_date"] = pd.to_datetime(levels["signal_date"]).dt.date.astype(str)
    levels["target_date"] = pd.to_datetime(levels["target_date"], errors="coerce").dt.date.astype(str)
    levels["is_exact_institutional_reference"] = levels["is_exact_institutional_reference"].astype(str).str.lower().isin(["true", "1", "yes"])

    for max_bars in max_bars_options:
        for touch_pts in touch_pts_options:
            for close_buffer_pts in close_buffer_options:
                for institutional_only in institutional_only_options:
                    source_levels = levels[levels["is_exact_institutional_reference"]].copy() if institutional_only else levels.copy()
                    variant = f"first{max_bars}_bars_touch{touch_pts:g}_buf{close_buffer_pts:g}_{'inst' if institutional_only else 'all'}"
                    for (signal_date, target_date), day_levels in source_levels.groupby(["signal_date", "target_date"], sort=True):
                        if not target_date or target_date == "NaT" or target_date not in bars_by_date or target_date not in daily_by_date:
                            continue
                        day = bars_by_date[target_date].head(max_bars)
                        if day.empty:
                            continue
                        dd = daily_by_date[target_date]
                        # Use the level closest to the current candle once it triggers;
                        # sort by candle-close distance then original CSV order.
                        fired: dict | None = None
                        for _, bar in day.iterrows():
                            candidates = []
                            for li, lvl in day_levels.iterrows():
                                level = float(lvl["level"])
                                if not _touched(lvl["role"], float(bar["high"]), float(bar["low"]), level, touch_pts):
                                    continue
                                direction = _direction_for_role(lvl["role"], float(bar["close"]), level, close_buffer_pts)
                                if direction is None:
                                    continue
                                candidates.append((abs(float(bar["close"]) - level), li, lvl, direction))
                            if candidates:
                                candidates.sort(key=lambda x: (x[0], x[1]))
                                _, _, lvl, direction = candidates[0]
                                entry = float(bar["close"])
                                post_ret_pct = (float(dd["close"]) - entry) / entry * 100 * _dir_mult(direction)
                                oc_hit = _hit(direction, str(dd["oc_ret_sign"]))
                                cc_hit = _hit(direction, str(dd["cc_ret_sign"]))
                                first15_hit = _hit(direction, str(dd["first15_ret_sign"]))
                                post_hit = bool(post_ret_pct >= cfg.post_entry_min_move_pct)
                                fired = {
                                    "variant": variant,
                                    "max_bars": max_bars,
                                    "touch_pts": touch_pts,
                                    "close_buffer_pts": close_buffer_pts,
                                    "institutional_only": institutional_only,
                                    "signal_date": signal_date,
                                    "target_date": target_date,
                                    "trigger_bar_index": int(bar["bar_index"]),
                                    "trigger_timestamp": str(bar["timestamp"]),
                                    "level": float(lvl["level"]),
                                    "role": lvl["role"],
                                    "level_type": lvl.get("level_type", ""),
                                    "direction": direction,
                                    "entry_close": entry,
                                    "day_open": float(dd["open"]),
                                    "day_close": float(dd["close"]),
                                    "post_entry_signed_ret_pct": post_ret_pct,
                                    "post_entry_hit": post_hit,
                                    "oc_ret_pct": float(dd["oc_ret_pct"]),
                                    "cc_ret_pct": float(dd["cc_ret_pct"]),
                                    "first15_ret_pct": float(dd["first15_ret_pct"]),
                                    "oc_direction_hit": oc_hit,
                                    "cc_direction_hit": cc_hit,
                                    "first15_direction_hit": first15_hit,
                                    "source_excerpt": lvl.get("source_excerpt", ""),
                                }
                                break
                        if fired:
                            triggers.append(fired)

    trig = pd.DataFrame(triggers)
    if trig.empty:
        return trig, pd.DataFrame()

    summaries = []
    for variant, x in trig.groupby("variant", sort=False):
        oc_nonflat = x["oc_direction_hit"].dropna()
        cc_nonflat = x["cc_direction_hit"].dropna()
        first15_nonflat = x["first15_direction_hit"].dropna()
        summaries.append(
            {
                "variant": variant,
                "max_bars": int(x["max_bars"].iloc[0]),
                "touch_pts": float(x["touch_pts"].iloc[0]),
                "close_buffer_pts": float(x["close_buffer_pts"].iloc[0]),
                "institutional_only": bool(x["institutional_only"].iloc[0]),
                "calls": int(len(x)),
                "unique_signal_days": int(x["signal_date"].nunique()),
                "post_entry_hit_rate": _rate(int(x["post_entry_hit"].sum()), len(x)),
                "post_entry_avg_signed_ret_pct": float(x["post_entry_signed_ret_pct"].mean()),
                "post_entry_median_signed_ret_pct": float(x["post_entry_signed_ret_pct"].median()),
                "oc_direction_n": int(len(oc_nonflat)),
                "oc_direction_hit_rate": _rate(int(oc_nonflat.sum()), len(oc_nonflat)),
                "cc_direction_n": int(len(cc_nonflat)),
                "cc_direction_hit_rate": _rate(int(cc_nonflat.sum()), len(cc_nonflat)),
                "first15_direction_n": int(len(first15_nonflat)),
                "first15_direction_hit_rate": _rate(int(first15_nonflat.sum()), len(first15_nonflat)),
                "train_jul_aug_calls": int((x["signal_date"] < "2026-09-01").sum()),
                "confirm_sep_calls": int((x["signal_date"] >= "2026-09-01").sum()),
                "train_jul_aug_post_hit_rate": _rate(int(x.loc[x["signal_date"] < "2026-09-01", "post_entry_hit"].sum()), int((x["signal_date"] < "2026-09-01").sum())),
                "confirm_sep_post_hit_rate": _rate(int(x.loc[x["signal_date"] >= "2026-09-01", "post_entry_hit"].sum()), int((x["signal_date"] >= "2026-09-01").sum())),
            }
        )
    summ = pd.DataFrame(summaries).sort_values(
        ["confirm_sep_post_hit_rate", "confirm_sep_calls", "post_entry_hit_rate", "calls"],
        ascending=[False, False, False, False],
    )
    return trig, summ


def evaluate_v3_agreement(level_triggers: pd.DataFrame, v3: pd.DataFrame) -> pd.DataFrame:
    if level_triggers.empty or v3.empty:
        return pd.DataFrame()
    merged = level_triggers.merge(v3, on=["signal_date", "target_date"], how="left")
    merged = merged[merged["v3_predicted_class"].isin([UP, DOWN])].copy()
    merged = merged[merged["direction"] == merged["v3_predicted_class"]].copy()
    if merged.empty:
        return pd.DataFrame()
    rows = []
    for variant, x in merged.groupby("variant", sort=False):
        rows.append(
            {
                "variant": variant,
                "calls": int(len(x)),
                "unique_signal_days": int(x["signal_date"].nunique()),
                "post_entry_hit_rate": _rate(int(x["post_entry_hit"].sum()), len(x)),
                "post_entry_avg_signed_ret_pct": float(x["post_entry_signed_ret_pct"].mean()),
                "train_jul_aug_calls": int((x["signal_date"] < "2026-09-01").sum()),
                "confirm_sep_calls": int((x["signal_date"] >= "2026-09-01").sum()),
                "train_jul_aug_post_hit_rate": _rate(int(x.loc[x["signal_date"] < "2026-09-01", "post_entry_hit"].sum()), int((x["signal_date"] < "2026-09-01").sum())),
                "confirm_sep_post_hit_rate": _rate(int(x.loc[x["signal_date"] >= "2026-09-01", "post_entry_hit"].sum()), int((x["signal_date"] >= "2026-09-01").sum())),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["confirm_sep_post_hit_rate", "confirm_sep_calls", "post_entry_hit_rate"],
        ascending=[False, False, False],
    )


def intraday_price_rule_sanity(daily: pd.DataFrame, cfg: EvalConfig) -> pd.DataFrame:
    """Check generic 15m rules over 2017-2026 with fixed OOS windows.

    This does not use institutional levels. It answers whether plain longer
    intraday candles alone contain a persistent 70% *post-entry* edge.  A rule
    based on the first 15/30/60 minutes is entered only after that window closes;
    the main hit-rate is therefore signal-close-to-day-close, not the easier
    open-to-close label that includes the already-observed move.
    """
    df = daily.dropna(
        subset=[
            "prev_close", "gap_pct", "first15_ret_pct", "first30_ret_pct",
            "first60_ret_pct", "oc_ret_pct", "first15_close", "first30_close",
            "first60_close",
        ]
    ).copy()
    df["year"] = pd.to_datetime(df["date"]).dt.year
    rules = []
    specs = []
    thresholds = {
        "gap_pct": ([0.05, 0.10, 0.20, 0.35, 0.50], "open"),
        "first15_ret_pct": ([0.03, 0.05, 0.08, 0.10, 0.15, 0.20], "first15_close"),
        "first30_ret_pct": ([0.05, 0.08, 0.10, 0.15, 0.20, 0.30], "first30_close"),
        "first60_ret_pct": ([0.08, 0.10, 0.15, 0.20, 0.30, 0.40], "first60_close"),
    }
    for feature, (vals, entry_col) in thresholds.items():
        for t in vals:
            specs.append((f"{feature}_trend_gt_{t:g}", feature, ">", t, UP, entry_col))
            specs.append((f"{feature}_trend_lt_-{t:g}", feature, "<", -t, DOWN, entry_col))
            # Fade variants are included because opening/gap overreaction is common.
            specs.append((f"{feature}_fade_gt_{t:g}", feature, ">", t, DOWN, entry_col))
            specs.append((f"{feature}_fade_lt_-{t:g}", feature, "<", -t, UP, entry_col))
    # A few combined early momentum/gap agreement rules.  They are entered after
    # the first 15-minute candle closes because first15 information is used.
    combo_specs = []
    for t1 in [0.05, 0.10, 0.20]:
        for t2 in [0.05, 0.10, 0.15]:
            combo_specs.append((f"gap_up_{t1:g}_and_first15_up_{t2:g}", lambda x, a=t1, b=t2: (x["gap_pct"] > a) & (x["first15_ret_pct"] > b), UP, "first15_close"))
            combo_specs.append((f"gap_down_{t1:g}_and_first15_down_{t2:g}", lambda x, a=t1, b=t2: (x["gap_pct"] < -a) & (x["first15_ret_pct"] < -b), DOWN, "first15_close"))
            combo_specs.append((f"gap_up_{t1:g}_but_first15_down_{t2:g}_fade", lambda x, a=t1, b=t2: (x["gap_pct"] > a) & (x["first15_ret_pct"] < -b), DOWN, "first15_close"))
            combo_specs.append((f"gap_down_{t1:g}_but_first15_up_{t2:g}_fade", lambda x, a=t1, b=t2: (x["gap_pct"] < -a) & (x["first15_ret_pct"] > b), UP, "first15_close"))

    def score_mask(mask: pd.Series, direction: str, name: str, entry_col: str) -> dict:
        x = df[mask].copy()
        if x.empty:
            return {
                "rule": name,
                "direction": direction,
                "entry_col": entry_col,
                "calls": 0,
                "post_entry_hit_rate": np.nan,
                "oc_direction_hit_rate": np.nan,
                "train_2017_2024_calls": 0,
                "val_2025_calls": 0,
                "confirm_2026_calls": 0,
                "train_2017_2024_post_hit_rate": np.nan,
                "val_2025_post_hit_rate": np.nan,
                "confirm_2026_post_hit_rate": np.nan,
            }
        mult = _dir_mult(direction)
        x["post_entry_signed_ret_pct"] = (x["close"] - x[entry_col]) / x[entry_col] * 100 * mult
        x["post_entry_hit"] = x["post_entry_signed_ret_pct"] >= cfg.post_entry_min_move_pct
        oc_nonflat = x["oc_ret_sign"].isin([UP, DOWN])
        oc_hit = x.loc[oc_nonflat, "oc_ret_sign"].eq(direction)
        cc_nonflat = x["cc_ret_sign"].isin([UP, DOWN])
        cc_hit = x.loc[cc_nonflat, "cc_ret_sign"].eq(direction)
        year = x["year"]
        train = year <= 2024
        val = year == 2025
        conf = year == 2026

        def sub_rate(mask_: pd.Series) -> float:
            sub = x.loc[mask_, "post_entry_hit"]
            return _rate(int(sub.sum()), int(len(sub)))

        return {
            "rule": name,
            "direction": direction,
            "entry_col": entry_col,
            "calls": int(len(x)),
            "post_entry_hit_rate": _rate(int(x["post_entry_hit"].sum()), len(x)),
            "post_entry_avg_signed_ret_pct": float(x["post_entry_signed_ret_pct"].mean()),
            "post_entry_median_signed_ret_pct": float(x["post_entry_signed_ret_pct"].median()),
            "oc_direction_n": int(oc_nonflat.sum()),
            "oc_direction_hit_rate": _rate(int(oc_hit.sum()), int(oc_nonflat.sum())),
            "cc_direction_n": int(cc_nonflat.sum()),
            "cc_direction_hit_rate": _rate(int(cc_hit.sum()), int(cc_nonflat.sum())),
            "avg_oc_signed_ret_pct": float((x["oc_ret_pct"] * mult).mean()),
            "train_2017_2024_calls": int(train.sum()),
            "val_2025_calls": int(val.sum()),
            "confirm_2026_calls": int(conf.sum()),
            "train_2017_2024_post_hit_rate": sub_rate(train),
            "val_2025_post_hit_rate": sub_rate(val),
            "confirm_2026_post_hit_rate": sub_rate(conf),
            "train_2017_2024_oc_hit_rate": _rate(int(x.loc[train & oc_nonflat, "oc_ret_sign"].eq(direction).sum()), int((train & oc_nonflat).sum())),
            "val_2025_oc_hit_rate": _rate(int(x.loc[val & oc_nonflat, "oc_ret_sign"].eq(direction).sum()), int((val & oc_nonflat).sum())),
            "confirm_2026_oc_hit_rate": _rate(int(x.loc[conf & oc_nonflat, "oc_ret_sign"].eq(direction).sum()), int((conf & oc_nonflat).sum())),
        }

    for name, feature, op, threshold, direction, entry_col in specs:
        mask = df[feature] > threshold if op == ">" else df[feature] < threshold
        rules.append(score_mask(mask, direction, name, entry_col))
    for name, fn, direction, entry_col in combo_specs:
        rules.append(score_mask(fn(df), direction, name, entry_col))
    out = pd.DataFrame(rules)
    return out.sort_values(
        ["confirm_2026_post_hit_rate", "confirm_2026_calls", "val_2025_post_hit_rate", "post_entry_hit_rate", "calls"],
        ascending=[False, False, False, False, False],
    )


def make_day_level_overview(levels: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    dd = daily.set_index("date")
    rows = []
    for (signal_date, target_date), x in levels.groupby(["signal_date", "target_date"], sort=True):
        if target_date not in dd.index:
            continue
        d = dd.loc[target_date]
        supports = sorted(x[x["role"].isin(["support", "breakdown"])] ["level"].astype(float).tolist())
        resistances = sorted(x[x["role"].isin(["resistance", "pivot", "target"])] ["level"].astype(float).tolist())
        open_px = float(d["open"])
        nearest_support = max([v for v in supports if v <= open_px], default=np.nan)
        nearest_resistance = min([v for v in resistances if v >= open_px], default=np.nan)
        all_levels = x["level"].astype(float).tolist()
        nearest_any = min(all_levels, key=lambda v: abs(v - open_px)) if all_levels else np.nan
        rows.append(
            {
                "signal_date": signal_date,
                "target_date": target_date,
                "levels_total": int(len(x)),
                "institutional_levels": int(x["is_exact_institutional_reference"].astype(bool).sum()),
                "day_open": open_px,
                "day_high": float(d["high"]),
                "day_low": float(d["low"]),
                "day_close": float(d["close"]),
                "oc_ret_pct": float(d["oc_ret_pct"]),
                "cc_ret_pct": float(d["cc_ret_pct"]),
                "first15_ret_pct": float(d["first15_ret_pct"]),
                "nearest_support_below_open": nearest_support,
                "nearest_resistance_above_open": nearest_resistance,
                "nearest_any_level_to_open": nearest_any,
                "nearest_any_distance_pts": abs(open_px - nearest_any) if pd.notna(nearest_any) else np.nan,
                "open_inside_published_range": bool((len(supports) == 0 or open_px >= min(supports)) and (len(resistances) == 0 or open_px <= max(resistances))),
            }
        )
    return pd.DataFrame(rows)


def _safe_top(df: pd.DataFrame, n: int = 10) -> list[dict]:
    if df.empty:
        return []
    return json.loads(df.head(n).replace({np.nan: None}).to_json(orient="records"))


def _markdown_table(df: pd.DataFrame, cols: list[str], n: int = 20) -> str:
    """Small dependency-free markdown table writer."""
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


def write_report(
    out_dir: Path,
    intraday_path: Path,
    levels_path: Path,
    bars: pd.DataFrame,
    daily: pd.DataFrame,
    levels: pd.DataFrame,
    price_rules: pd.DataFrame,
    level_summary: pd.DataFrame,
    v3_agree: pd.DataFrame,
    cfg: EvalConfig,
) -> None:
    complete_days = daily["date"].nunique()
    level_days = levels[["signal_date", "target_date"]].drop_duplicates().shape[0]
    inst_rows = int(levels["is_exact_institutional_reference"].astype(bool).sum())
    robust_price = price_rules[
        (price_rules["train_2017_2024_calls"] >= 300)
        & (price_rules["val_2025_calls"] >= 40)
        & (price_rules["confirm_2026_calls"] >= 25)
        & (price_rules["train_2017_2024_post_hit_rate"] >= 70)
        & (price_rules["val_2025_post_hit_rate"] >= 70)
        & (price_rules["confirm_2026_post_hit_rate"] >= 70)
    ]
    robust_levels = level_summary[
        (level_summary["train_jul_aug_calls"] >= 10)
        & (level_summary["confirm_sep_calls"] >= 8)
        & (level_summary["train_jul_aug_post_hit_rate"] >= 70)
        & (level_summary["confirm_sep_post_hit_rate"] >= 70)
    ] if not level_summary.empty else pd.DataFrame()
    best_level = level_summary.head(1).to_dict("records") if not level_summary.empty else []
    best_price = price_rules.head(1).to_dict("records") if not price_rules.empty else []

    lines = [
        "# V7 Intraday + Date-Stamped Institutional Levels",
        "",
        "## Objective",
        "",
        "Move beyond EOD/OI-only curve fitting by adding longer 15-minute candles and exact date-stamped NIFTY levels extracted from the supplied dated market-analysis PDF. The score is still honest: no same-day future candles are used to choose the level list; a signal waits for a 15-minute confirmation candle before it is counted.",
        "",
        "## Data added",
        "",
        f"- 15-minute NIFTY candles: `{intraday_path}`; {len(bars):,} bars across {complete_days:,} usable sessions from {daily['date'].min()} to {daily['date'].max()}.",
        "- Raw 1-minute archive was downloaded from `technovusin/nifty50-historical-data` via GitHub API and kept outside Git; the committed 15m derived file has a manifest beside it.",
        f"- Date-stamped levels: `{levels_path}`; {len(levels):,} manually audited level rows across {level_days:,} signal days; {inst_rows:,} rows explicitly tagged institutional/institutional-zone from the PDF wording.",
        "",
        "## Main result",
        "",
        f"- Long 2017-2026 generic 15m price-rule sanity check found **{len(robust_price)}** rules clearing a 70% train/2025/2026 **post-entry** hit-rate gate with large-sample guards.",
        f"- PDF-level conditional branch grid found **{len(robust_levels)}** variants clearing a 70% July-Aug train and Sep confirmation gate with minimum calls. This sample is necessarily small because exact supplied levels exist only for the dated PDF window.",
        "- Therefore V7 builds the required stronger data path, but it still does **not** justify promoting a real 70%+ production decoder yet. The useful output is a forward-testable intraday gate, not a finished accuracy claim.",
        "",
        "## Best generic 15m price sanity rules",
        "",
    ]
    if price_rules.empty:
        lines.append("No price rules generated.")
    else:
        cols = ["rule", "direction", "entry_col", "calls", "post_entry_hit_rate", "post_entry_avg_signed_ret_pct", "train_2017_2024_calls", "train_2017_2024_post_hit_rate", "val_2025_calls", "val_2025_post_hit_rate", "confirm_2026_calls", "confirm_2026_post_hit_rate", "oc_direction_hit_rate"]
        lines.append(_markdown_table(price_rules, cols, 15))
    lines.extend(["", "## Best PDF-level 15m confirmation variants", ""])
    if level_summary.empty:
        lines.append("No level-trigger variants fired.")
    else:
        cols = ["variant", "calls", "post_entry_hit_rate", "post_entry_avg_signed_ret_pct", "train_jul_aug_calls", "train_jul_aug_post_hit_rate", "confirm_sep_calls", "confirm_sep_post_hit_rate", "oc_direction_n", "oc_direction_hit_rate"]
        lines.append(_markdown_table(level_summary, cols, 20))
    lines.extend(["", "## V3 OI agreement overlay", ""])
    if v3_agree.empty:
        lines.append("No sufficient V3-agreement overlay rows. V3 historical predictions in this repo end before most September PDF-level dates, so this cannot yet be a reliable filter.")
    else:
        cols = ["variant", "calls", "post_entry_hit_rate", "train_jul_aug_calls", "train_jul_aug_post_hit_rate", "confirm_sep_calls", "confirm_sep_post_hit_rate"]
        lines.append(_markdown_table(v3_agree, cols, 15))
    lines.extend([
        "",
        "## How to interpret this for real trading research",
        "",
        "1. A level signal is counted only after the 15m candle range touches/overlaps a published level and its close confirms a branch above/below that level.",
        f"2. `post_entry_hit_rate` uses close after the trigger to day close, with a minimum signed move of {cfg.post_entry_min_move_pct:.2f}% to avoid marking tiny/noisy drifts as wins.",
        "3. `oc_direction_hit_rate` is the old open-to-close day direction score; it is reported separately because a conditional level trade can be right after the trigger even when the whole day's open-to-close class is misleading.",
        "4. The PDF-level result cannot be called statistically robust until new exact levels are collected daily and walked forward. Use it as a forward-watch gate.",
        "",
        "## Next implementation step",
        "",
        "Add a daily `data/institutional_levels/YYYY-MM-DD.json` ingestion path for externally supplied exact levels, then append the next session's 15m bars and score this V7 gate forward without changing thresholds.",
    ])
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")

    summary = {
        "intraday_bars": int(len(bars)),
        "intraday_usable_sessions": int(complete_days),
        "intraday_start": str(daily["date"].min()),
        "intraday_end": str(daily["date"].max()),
        "level_rows": int(len(levels)),
        "level_signal_days": int(level_days),
        "institutional_level_rows": inst_rows,
        "generic_15m_robust_70pct_rules": int(len(robust_price)),
        "pdf_level_robust_70pct_variants": int(len(robust_levels)),
        "best_generic_price_rules": _safe_top(price_rules, 5),
        "best_level_variants": _safe_top(level_summary, 5),
        "best_v3_agreement_variants": _safe_top(v3_agree, 5),
        "verdict": "DATA_PATH_BUILT_NO_PRODUCTION_70PCT_EDGE_YET",
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--intraday", default="historical/nifty_15m.csv")
    ap.add_argument("--levels", default="historical/institutional_levels_pdf_2026.csv")
    ap.add_argument("--v3-predictions", default="reports/backtest_v3_candidate_2023-08_to_2026-09/v3_predictions.csv")
    ap.add_argument("--out", default="reports/v7_intraday_institutional_levels")
    ap.add_argument("--flat-threshold-pct", type=float, default=0.10)
    ap.add_argument("--post-entry-min-move-pct", type=float, default=0.05)
    args = ap.parse_args()

    cfg = EvalConfig(flat_threshold_pct=args.flat_threshold_pct, post_entry_min_move_pct=args.post_entry_min_move_pct)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    intraday_path = Path(args.intraday)
    levels_path = Path(args.levels)
    bars = load_intraday(intraday_path, cfg.min_complete_bars_per_day)
    daily = make_daily_from_intraday(bars, cfg)
    levels = pd.read_csv(levels_path)
    levels["signal_date"] = pd.to_datetime(levels["signal_date"]).dt.date.astype(str)
    levels["target_date"] = pd.to_datetime(levels["target_date"]).dt.date.astype(str)
    levels["level"] = pd.to_numeric(levels["level"], errors="coerce")
    levels = levels.dropna(subset=["signal_date", "target_date", "level"])
    levels["is_exact_institutional_reference"] = levels["is_exact_institutional_reference"].astype(str).str.lower().isin(["true", "1", "yes"])

    day_level_overview = make_day_level_overview(levels, daily)
    price_rules = intraday_price_rule_sanity(daily, cfg)
    triggers, level_summary = evaluate_level_triggers(bars, daily, levels, cfg)
    v3 = load_v3_predictions(Path(args.v3_predictions))
    v3_agree = evaluate_v3_agreement(triggers, v3)

    daily.to_csv(out_dir / "daily_from_15m.csv", index=False)
    day_level_overview.to_csv(out_dir / "day_level_overview.csv", index=False)
    price_rules.to_csv(out_dir / "generic_15m_price_rules.csv", index=False)
    triggers.to_csv(out_dir / "level_event_triggers.csv", index=False)
    level_summary.to_csv(out_dir / "level_rule_grid.csv", index=False)
    v3_agree.to_csv(out_dir / "v3_agreement_level_grid.csv", index=False)

    quality = {
        "source_intraday": str(intraday_path),
        "source_levels": str(levels_path),
        "bars_loaded": int(len(bars)),
        "usable_sessions": int(daily["date"].nunique()),
        "date_min": str(daily["date"].min()),
        "date_max": str(daily["date"].max()),
        "sessions_by_bar_count": {str(k): int(v) for k, v in bars.groupby("date")["bar_index"].nunique().value_counts().sort_index().items()},
        "level_rows": int(len(levels)),
        "level_signal_days": int(levels[["signal_date", "target_date"]].drop_duplicates().shape[0]),
    }
    (out_dir / "data_quality.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")

    write_report(out_dir, intraday_path, levels_path, bars, daily, levels, price_rules, level_summary, v3_agree, cfg)
    print(json.dumps(json.loads((out_dir / "summary.json").read_text()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
