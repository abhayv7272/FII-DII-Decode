#!/usr/bin/env python3
"""V6 real-world selective search.

Third continuation loop for the 70-85% accuracy goal.  This script focuses on
practical next-day use cases:

1. Can two independent OI/psychology rules agree and create a high-precision
   *selective* signal?
2. Can long price/regime history (2010-2026) add a robust filter beyond the
   short participant-OI archive?

Guardrails:

* v4 rule orientations and thresholds are fit on 2023-2024 only;
* pair candidates are evaluated on 2025 and 2026 separately;
* price-only rules are fit on 2010-2022, validated on 2023-2024, confirmed on
  2025-2026;
* target/outcome columns are excluded from features;
* no production decoder change is made by this research script.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "research") not in sys.path:
    sys.path.insert(0, str(ROOT / "research"))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from v4_psychology_search import build_enhanced_matrix  # noqa: E402

FLAT_BAND_PCT = 0.15
LEAKAGE_NAMES = {"y_cc", "y_oc", "y_gap", "y_5d", "actual", "actual_class", "actual_return_pct", "exact_hit", "direction_hit"}


def labels(y_pct: pd.Series | np.ndarray, band: float = FLAT_BAND_PCT) -> np.ndarray:
    y = np.asarray(y_pct, dtype=float)
    return np.where(y > band, 1, np.where(y < -band, -1, 0)).astype(np.int8)


def safe_rate(num: int, den: int) -> float | None:
    return round(num / den * 100.0, 2) if den else None


def metrics(mask: np.ndarray, pred: np.ndarray, actual: np.ndarray) -> dict[str, int | float | None]:
    called = mask & (pred != 0)
    n = int(called.sum())
    total = int(mask.sum())
    out: dict[str, int | float | None] = {
        "n": n,
        "coverage_pct": safe_rate(n, total),
        "up_calls": int((pred[called] == 1).sum()),
        "down_calls": int((pred[called] == -1).sum()),
    }
    if not n:
        out.update({"exact_pct": None, "sign_pct": None, "sign_n": 0})
        return out
    out["exact_pct"] = safe_rate(int((pred[called] == actual[called]).sum()), n)
    nonflat = called & (actual != 0)
    sign_n = int(nonflat.sum())
    out["sign_n"] = sign_n
    out["sign_pct"] = safe_rate(int((pred[nonflat] == actual[nonflat]).sum()), sign_n)
    return out


def period_masks(df: pd.DataFrame) -> dict[str, np.ndarray]:
    period = df["period"].astype(str).to_numpy()
    return {
        "dev2023_24": period == "dev2023_24",
        "val2025": period == "val2025",
        "confirm2026": period == "confirm2026",
    }


def rule_base_name(feature: str) -> str:
    base = feature
    for token in ("_posdays", "_mean", "_sum", "_chg", "_z"):
        base = base.split(token)[0]
    return base


def apply_rule_to_df(row, df: pd.DataFrame) -> np.ndarray:
    x = pd.to_numeric(df[row.feature], errors="coerce").to_numpy(dtype=float)
    z = x * int(row.orientation)
    pred = np.zeros(len(df), dtype=np.int8)
    if row.mode in {"two_tail", "up_tail"} and pd.notna(row.threshold_hi):
        pred[z >= float(row.threshold_hi)] = 1
    if row.mode in {"two_tail", "down_tail"} and pd.notna(row.threshold_lo):
        pred[z <= float(row.threshold_lo)] = -1
    return pred


def pair_search(df: pd.DataFrame, rules_path: Path, out_dir: Path, pool_size: int = 800) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    rules = pd.read_csv(rules_path)
    rules = rules[~rules["feature"].isin(LEAKAGE_NAMES)].copy()
    dev_strong = rules[
        (rules["dev2023_24_n"] >= 25)
        & ((rules["dev2023_24_exact_pct"] >= 52) | (rules["dev2023_24_sign_pct"] >= 65))
    ].copy()
    dev_strong = dev_strong.sort_values(
        ["dev2023_24_sign_pct", "dev2023_24_exact_pct", "dev2023_24_n"],
        ascending=False,
    )
    selected_rows = []
    base_counts: dict[str, int] = {}
    for row in dev_strong.itertuples(index=False):
        base = rule_base_name(str(row.feature))
        if base_counts.get(base, 0) >= 3:
            continue
        selected_rows.append(row)
        base_counts[base] = base_counts.get(base, 0) + 1
        if len(selected_rows) >= pool_size:
            break

    vectors = [apply_rule_to_df(row, df) for row in selected_rows]
    V = np.vstack(vectors) if vectors else np.zeros((0, len(df)), dtype=np.int8)
    actual = labels(df["y_cc"])
    masks = period_masks(df)

    rows: list[dict] = []
    total_pairs = 0
    for i in range(len(selected_rows)):
        left = V[i]
        for j in range(i + 1, len(selected_rows)):
            total_pairs += 1
            right = V[j]
            pred = np.where((left != 0) & (left == right), left, 0).astype(np.int8)
            dev_m = metrics(masks["dev2023_24"], pred, actual)
            if (dev_m["n"] or 0) < 15:
                continue
            if (dev_m["exact_pct"] or 0) < 58 and (dev_m["sign_pct"] or 0) < 70:
                continue
            row = {
                "left_feature": selected_rows[i].feature,
                "left_mode": selected_rows[i].mode,
                "left_quantile": selected_rows[i].quantile,
                "right_feature": selected_rows[j].feature,
                "right_mode": selected_rows[j].mode,
                "right_quantile": selected_rows[j].quantile,
            }
            for period, mask in masks.items():
                row.update({f"{period}_{k}": v for k, v in metrics(mask, pred, actual).items()})
            if (row["val2025_n"] or 0) >= 10 or (row["confirm2026_n"] or 0) >= 10:
                rows.append(row)

    pairs = pd.DataFrame(rows)
    if pairs.empty:
        top_both = pd.DataFrame()
        devval = pd.DataFrame()
    else:
        pairs["min_val_confirm_exact_pct"] = pairs[["val2025_exact_pct", "confirm2026_exact_pct"]].min(axis=1)
        pairs["min_val_confirm_sign_pct"] = pairs[["val2025_sign_pct", "confirm2026_sign_pct"]].min(axis=1)
        top_both = pairs[(pairs["val2025_n"] >= 10) & (pairs["confirm2026_n"] >= 10)].copy()
        top_both = top_both.sort_values(
            ["min_val_confirm_exact_pct", "min_val_confirm_sign_pct", "dev2023_24_exact_pct"],
            ascending=False,
            na_position="last",
        ).head(300)
        devval = pairs[
            (pairs["val2025_n"] >= 10)
            & ((pairs["val2025_exact_pct"] >= 70) | (pairs["val2025_sign_pct"] >= 75))
        ].copy()
        devval = devval.sort_values(
            ["confirm2026_exact_pct", "confirm2026_sign_pct", "val2025_exact_pct"],
            ascending=False,
            na_position="last",
        ).head(300)
    top_both.to_csv(out_dir / "pair_top_both_holdouts.csv", index=False)
    devval.to_csv(out_dir / "pair_devval_selected_confirm.csv", index=False)
    summary = {
        "rule_pool_size": len(selected_rows),
        "total_pairs_checked": total_pairs,
        "qualified_pairs_exported": int(len(pairs)),
        "pairs_ge_75_exact_both_holdouts_n10": int(((top_both.get("val2025_exact_pct", pd.Series(dtype=float)) >= 75) & (top_both.get("confirm2026_exact_pct", pd.Series(dtype=float)) >= 75)).sum()) if not top_both.empty else 0,
        "pairs_ge_75_sign_both_holdouts_sign_n10": int(((top_both.get("val2025_sign_pct", pd.Series(dtype=float)) >= 75) & (top_both.get("confirm2026_sign_pct", pd.Series(dtype=float)) >= 75) & (top_both.get("val2025_sign_n", pd.Series(dtype=float)) >= 10) & (top_both.get("confirm2026_sign_n", pd.Series(dtype=float)) >= 10)).sum()) if not top_both.empty else 0,
    }
    return top_both, devval, summary


def build_price_features(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, parse_dates=["date"]).sort_values("date")
    raw = raw[raw["date"] >= pd.Timestamp("2010-01-01")].reset_index(drop=True)
    for col in ("open", "high", "low", "close", "volume"):
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
    close, open_, high, low = raw["close"], raw["open"], raw["high"], raw["low"]
    ret = close.pct_change() * 100.0
    out = pd.DataFrame({"date": raw["date"]})
    out["dow"] = raw["date"].dt.dayofweek
    out["month"] = raw["date"].dt.month
    out["dom"] = raw["date"].dt.day
    data: dict[str, pd.Series] = {}
    for window in (1, 2, 3, 4, 5, 7, 10, 15, 20, 30, 40, 60, 90, 120, 180, 252):
        minp = max(1, min(window, window // 2))
        data[f"ret{window}"] = close.pct_change(window) * 100.0
        data[f"ma_dev{window}"] = (close / close.rolling(window, min_periods=minp).mean() - 1.0) * 100.0
        span = (high - low) / close * 100.0
        data[f"range_mean{window}"] = span.rolling(window, min_periods=minp).mean()
        data[f"rv{window}"] = ret.rolling(window, min_periods=minp).std()
        data[f"updays{window}"] = (ret > 0).rolling(window, min_periods=minp).sum() / window
        data[f"high_break{window}"] = (close / high.shift(1).rolling(window, min_periods=minp).max() - 1.0) * 100.0
        data[f"low_break{window}"] = (close / low.shift(1).rolling(window, min_periods=minp).min() - 1.0) * 100.0
        if window >= 5:
            r = ret.rolling(window, min_periods=minp)
            data[f"ret_z{window}"] = (ret - r.mean()) / r.std().replace(0, np.nan)
    one_day_oc = (close / open_ - 1.0) * 100.0
    one_day_gap = (open_ / close.shift(1) - 1.0) * 100.0
    for window in (1, 2, 3, 5, 7, 10, 15, 20):
        data[f"oc_sum{window}"] = one_day_oc.rolling(window, min_periods=1).sum()
        data[f"gap_sum{window}"] = one_day_gap.rolling(window, min_periods=1).sum()
    span = (high - low) / close * 100.0
    for window in (5, 10, 20, 60):
        minp = max(3, window // 2)
        data[f"range_z{window}"] = (span - span.rolling(window, min_periods=minp).mean()) / span.rolling(window, min_periods=minp).std().replace(0, np.nan)
    out = pd.concat([out, pd.DataFrame(data)], axis=1)
    out["y_next_pct"] = (close.shift(-1) / close - 1.0) * 100.0
    out["period"] = np.where(out["date"] < pd.Timestamp("2023-01-01"), "train2010_22", np.where(out["date"] < pd.Timestamp("2025-01-01"), "val2023_24", "confirm2025_26"))
    return out.iloc[:-1].copy()


def price_rule_search(price_df: pd.DataFrame, out_dir: Path) -> tuple[pd.DataFrame, dict]:
    actual = labels(price_df["y_next_pct"])
    yret = price_df["y_next_pct"].to_numpy(dtype=float)
    period = price_df["period"].astype(str).to_numpy()
    masks = {
        "train2010_22": period == "train2010_22",
        "val2023_24": period == "val2023_24",
        "confirm2025_26": period == "confirm2025_26",
    }
    train = masks["train2010_22"]
    rows: list[dict] = []
    features = [c for c in price_df.columns if c not in {"date", "period", "y_next_pct"}]
    for feature in features:
        x = pd.to_numeric(price_df[feature], errors="coerce").to_numpy(dtype=float)
        finite = train & np.isfinite(x) & np.isfinite(yret)
        if int(finite.sum()) < 1000 or not np.isfinite(np.nanstd(x[train])) or np.nanstd(x[train]) == 0:
            continue
        try:
            rho = float(spearmanr(x[finite], yret[finite]).statistic)
        except Exception:
            continue
        if not np.isfinite(rho) or abs(rho) < 0.015:
            continue
        z = x if rho >= 0 else -x
        for mode in ("two_tail", "up_tail", "down_tail"):
            for q in (0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.925, 0.95, 0.975):
                pred = np.zeros(len(price_df), dtype=np.int8)
                if mode in {"two_tail", "up_tail"}:
                    hi = np.nanquantile(z[train], q)
                    pred[z >= hi] = 1
                if mode in {"two_tail", "down_tail"}:
                    lo = np.nanquantile(z[train], 1.0 - q)
                    pred[z <= lo] = -1
                train_m = metrics(masks["train2010_22"], pred, actual)
                if (train_m["n"] or 0) < 100:
                    continue
                if (train_m["exact_pct"] or 0) < 42 and (train_m["sign_pct"] or 0) < 52:
                    continue
                row = {"feature": feature, "mode": mode, "quantile": q, "rho_train2010_22": round(rho, 6)}
                for name, mask in masks.items():
                    row.update({f"{name}_{k}": v for k, v in metrics(mask, pred, actual).items()})
                rows.append(row)
    res = pd.DataFrame(rows)
    if not res.empty:
        res["min_val_confirm_exact_pct"] = res[["val2023_24_exact_pct", "confirm2025_26_exact_pct"]].min(axis=1)
        res["min_val_confirm_sign_pct"] = res[["val2023_24_sign_pct", "confirm2025_26_sign_pct"]].min(axis=1)
        res = res.sort_values(
            ["min_val_confirm_exact_pct", "min_val_confirm_sign_pct", "val2023_24_n"],
            ascending=False,
            na_position="last",
        )
    top = res[(res.get("val2023_24_n", pd.Series(dtype=float)) >= 20) & (res.get("confirm2025_26_n", pd.Series(dtype=float)) >= 20)].head(300) if not res.empty else pd.DataFrame()
    top.to_csv(out_dir / "price_only_2010_2026_top_rules.csv", index=False)
    summary = {
        "price_rows": int(len(price_df)),
        "price_rules_exported": int(len(res)),
        "price_rules_ge_75_exact_both_holdouts_n20": int(((top.get("val2023_24_exact_pct", pd.Series(dtype=float)) >= 75) & (top.get("confirm2025_26_exact_pct", pd.Series(dtype=float)) >= 75)).sum()) if not top.empty else 0,
        "price_rules_ge_75_sign_both_holdouts_sign_n20": int(((top.get("val2023_24_sign_pct", pd.Series(dtype=float)) >= 75) & (top.get("confirm2025_26_sign_pct", pd.Series(dtype=float)) >= 75) & (top.get("val2023_24_sign_n", pd.Series(dtype=float)) >= 20) & (top.get("confirm2025_26_sign_n", pd.Series(dtype=float)) >= 20)).sum()) if not top.empty else 0,
    }
    return top, summary


def md_table(frame: pd.DataFrame, columns: list[str], max_rows: int = 12) -> str:
    if frame.empty:
        return "_None._\n"
    present = [c for c in columns if c in frame]
    sub = frame[present].head(max_rows)
    if sub.empty:
        return "_None._\n"

    def cell(value) -> str:
        if value is None or pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.4g}"
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(present) + " |", "|" + "|".join(["---"] * len(present)) + "|"]
    for row in sub.to_numpy():
        lines.append("| " + " | ".join(cell(v) for v in row) + " |")
    return "\n".join(lines)


def write_report(pair_top: pd.DataFrame, pair_devval: pd.DataFrame, price_top: pd.DataFrame, summary: dict, out_dir: Path) -> None:
    pair_cols = [
        "left_feature", "left_mode", "left_quantile", "right_feature", "right_mode", "right_quantile",
        "dev2023_24_n", "dev2023_24_exact_pct", "dev2023_24_sign_pct",
        "val2025_n", "val2025_exact_pct", "val2025_sign_pct",
        "confirm2026_n", "confirm2026_exact_pct", "confirm2026_sign_pct", "confirm2026_sign_n",
        "min_val_confirm_exact_pct", "min_val_confirm_sign_pct",
    ]
    price_cols = [
        "feature", "mode", "quantile", "rho_train2010_22",
        "train2010_22_n", "train2010_22_exact_pct", "train2010_22_sign_pct",
        "val2023_24_n", "val2023_24_exact_pct", "val2023_24_sign_pct",
        "confirm2025_26_n", "confirm2025_26_exact_pct", "confirm2025_26_sign_pct", "confirm2025_26_sign_n",
        "min_val_confirm_exact_pct", "min_val_confirm_sign_pct",
    ]
    report = f"""# V6 real-world selective search

> Research only; no production change.  This pass specifically asked: can we
> make a next-day signal usable in the real world by requiring multiple
> institutional/psychology conditions or by adding 10+ years of price-regime
> context?

## Summary

- V4 dev-fitted rule pool used for pair search: **{summary['pair']['rule_pool_size']}** rules.
- Pair/conjunctions checked: **{summary['pair']['total_pairs_checked']}**.
- Pair/conjunctions passing the dev screen and exported internally: **{summary['pair']['qualified_pairs_exported']}**.
- Pairs with ≥75% exact on both 2025 and 2026 holdouts, n≥10 each: **{summary['pair']['pairs_ge_75_exact_both_holdouts_n10']}**.
- Pairs with ≥75% sign on both 2025 and 2026 holdouts, sign-n≥10 each: **{summary['pair']['pairs_ge_75_sign_both_holdouts_sign_n10']}**.
- Long price-history rows tested: **{summary['price']['price_rows']}**.
- Price-only rules exported: **{summary['price']['price_rules_exported']}**.
- Price-only rules with ≥75% exact on both 2023-2024 and 2025-2026 holdouts, n≥20 each: **{summary['price']['price_rules_ge_75_exact_both_holdouts_n20']}**.
- Price-only rules with ≥75% sign on both holdouts, sign-n≥20 each: **{summary['price']['price_rules_ge_75_sign_both_holdouts_sign_n20']}**.

## Bottom line

The real-world selective search still does **not** produce an honest 75-85%
production signal.  Pairing OI/psychology rules improves some tiny pockets, but
the best pair that has at least 10 calls in both holdouts reaches only the
low-60s exact / low-70s sign zone.  Long price history also fails to create a
stable 75% filter.

## Best pair/conjunction rules requiring at least 10 calls in both holdouts

{md_table(pair_top, pair_cols, 12)}

## Pairs that looked good on dev+2025, then hit 2026

This table is useful for forward-watch ideas, but several rows have tiny 2026
sample sizes.  Do not promote them without fresh forward evidence.

{md_table(pair_devval, pair_cols, 12)}

## Best long price-only rules

These use NIFTY daily history from 2010 onward.  Train = 2010-2022, validation =
2023-2024, confirmation = 2025-2026.  They also do not reach 75% robustly.

{md_table(price_top, price_cols, 12)}

## Practical consequence for next-day use

- Keep v2/v3 reports as **context**, not a standalone trade.
- If a v4/v5/v6 pocket triggers, treat it as a **forward-watch tag**, not as a
  proved edge.
- The next realistic route to 70%+ is not more EOD curve-fitting; it is a longer
  10-15 minute intraday candle/level dataset with exact date-stamped
  institutional levels, then an executable backtest with costs/slippage.
- Until that exists, the honest production action remains: emit next-day lean +
  conditional level plan, and require live price confirmation before acting.
"""
    (out_dir / "report.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", default="/home/user/features/v3_matrix.csv")
    parser.add_argument("--oi", default="historical/participant_oi.csv")
    parser.add_argument("--vol", default="historical/participant_vol.csv")
    parser.add_argument("--ohlc", default="historical/nifty_ohlc.csv")
    parser.add_argument("--chain-features", default="historical/chain_features.csv")
    parser.add_argument("--v2-predictions", default="reports/backtest_v3_candidate_2023-08_to_2026-09/v2_predictions.csv")
    parser.add_argument("--v3-predictions", default="reports/backtest_v3_candidate_2023-08_to_2026-09/v3_predictions.csv")
    parser.add_argument("--rules", default="reports/v4_psychology_search/threshold_rules.csv")
    parser.add_argument("--price-ohlc", default="historical/nifty_ohlc_long.csv")
    parser.add_argument("--save-input-matrix", action="store_true")
    parser.add_argument("--out", default="reports/v6_realworld_selective")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = build_enhanced_matrix(args)
    pair_top, pair_devval, pair_summary = pair_search(df, Path(args.rules), out_dir)
    price_df = build_price_features(Path(args.price_ohlc))
    price_top, price_summary = price_rule_search(price_df, out_dir)
    summary = {"pair": pair_summary, "price": price_summary}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_report(pair_top, pair_devval, price_top, summary, out_dir)
    print(f"wrote {out_dir}/report.md")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
