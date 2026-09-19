#!/usr/bin/env python3
"""Leak-safe next-Monday-to-Friday composite search.

This is the next research pass after V4--V11.  It addresses the *weekly* part
of the prediction-maker objective directly rather than re-labelling a five-day
rolling result as a calendar-week forecast.

Signal timing
-------------
The signal is the final available trading session of a week (normally Friday,
after the EOD OI/options data has been published).  The target is the close of
the final available trading session in the following Monday--Friday week,
relative to the signal close.  Thus no data from the predicted week is used in
the signal features.

Guardrails
----------
* all candidate feature orientations and thresholds are fit only on 2023--2024;
* 2025 is validation and 2026 is separate confirmation;
* explicit outcome/target columns from prior backtest CSVs are excluded;
* a candidate needs material support in *both* later periods before it can be
  considered.  This script does not alter production predictions.

The experiment combines the available point-in-time participant OI, volume,
option-chain proxy, price-regime and existing v2/v3 *signal* fields.  It tests
single selective rules and agreement pairs.  This broad search can honestly
reject a hypothesis; it must not be used to manufacture an 85 percent claim.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT / "research", ROOT / "src"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from v4_psychology_search import build_enhanced_matrix  # noqa: E402

FLAT_BAND_PCT = 0.50
PERIODS = ("dev2023_24", "val2025", "confirm2026")
QUANTILES = (0.60, 0.70, 0.75, 0.80, 0.85, 0.90)
# These values are deliberately fixed before the experiment.  The threshold is
# intended to rule out a one-off 9/10 success rate from promotion.
MIN_CALLED_EACH_HOLDOUT = 10
TARGET_ACCURACY_PCT = 85.0

# Columns whose contents directly contain the future bar/outcome in prior
# backtest exports.  The feature source has many useful signal fields too
# (v3_composite, current OI etc.), so this is a deny-list rather than removing
# all columns originating from the prediction exports.
FORBIDDEN_EXACT = {
    "y_cc", "y_oc", "y_gap", "y_5d", "y_week",
    "exact_hit", "direction_hit", "actual_class", "actual_return_pct",
    "target_open", "target_high", "target_low", "target_close",
    "support_tested", "support_held", "resistance_tested", "resistance_held",
    "level_tests", "level_hits",
}
FORBIDDEN_TOKENS = (
    "exact_hit", "direction_hit", "actual_class", "actual_return",
    "target_open", "target_high", "target_low", "target_close",
    "support_tested", "support_held", "resistance_tested", "resistance_held",
    "level_tests", "level_hits",
)


@dataclass(frozen=True)
class Rule:
    feature: str
    orientation: int
    mode: str
    quantile: float
    hi: float | None
    lo: float | None
    rho_dev: float


def labels(values: np.ndarray | pd.Series, band: float = FLAT_BAND_PCT) -> np.ndarray:
    """Map a return to UP / FLAT / DOWN without looking at later values."""
    x = np.asarray(values, dtype=float)
    return np.where(x > band, 1, np.where(x < -band, -1, 0)).astype(np.int8)


def class_name(value: int) -> str:
    return {-1: "DOWN", 0: "FLAT", 1: "UP"}[int(value)]


def safe_pct(numerator: int, denominator: int) -> float | None:
    return round(numerator * 100.0 / denominator, 2) if denominator else None


def metrics(mask: np.ndarray, pred: np.ndarray, actual: np.ndarray) -> dict[str, int | float | None]:
    """Accuracy of selective UP/DOWN calls.

    Exact accuracy penalises a directional call on a real FLAT week.  Sign
    accuracy is reported separately on the realised non-FLAT weeks only.
    """
    called = mask & (pred != 0)
    n = int(called.sum())
    total = int(mask.sum())
    result: dict[str, int | float | None] = {
        "n": n,
        "coverage_pct": safe_pct(n, total),
        "up_calls": int((pred[called] == 1).sum()),
        "down_calls": int((pred[called] == -1).sum()),
    }
    if not n:
        result.update({"exact_pct": None, "sign_n": 0, "sign_pct": None})
        return result
    result["exact_pct"] = safe_pct(int((pred[called] == actual[called]).sum()), n)
    directional = called & (actual != 0)
    sign_n = int(directional.sum())
    result["sign_n"] = sign_n
    result["sign_pct"] = safe_pct(int((pred[directional] == actual[directional]).sum()), sign_n)
    return result


def period_masks(frame: pd.DataFrame) -> dict[str, np.ndarray]:
    period = frame["period"].astype(str).to_numpy()
    return {name: period == name for name in PERIODS}


def is_forbidden_feature(name: str) -> bool:
    lowered = name.lower()
    # Future-label columns conventionally use y_*; block the whole family so a
    # newly-added horizon cannot silently become a predictor.
    return (
        lowered.startswith("y_")
        or lowered in FORBIDDEN_EXACT
        or any(token in lowered for token in FORBIDDEN_TOKENS)
    )


def build_weekly_frame(enhanced: pd.DataFrame, ohlc_path: Path) -> pd.DataFrame:
    """Keep final-week-session signals and attach next calendar week's return."""
    ohlc = pd.read_csv(ohlc_path, parse_dates=["date"])
    ohlc = ohlc[["date", "close"]].copy()
    ohlc["date"] = pd.to_datetime(ohlc["date"]).dt.normalize()
    ohlc["close"] = pd.to_numeric(ohlc["close"], errors="coerce")
    ohlc = ohlc.dropna(subset=["date", "close"]).sort_values("date").drop_duplicates("date")

    features = enhanced.copy()
    features["date"] = pd.to_datetime(features["date"]).dt.normalize()
    features = features.merge(ohlc.rename(columns={"close": "signal_close"}), on="date", how="inner")
    features = features.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    features["signal_week"] = features["date"].dt.to_period("W-FRI")

    # A prediction is made only at the last available session in a week.  This
    # handles a holiday Friday without pretending that unavailable Friday OI was
    # known.  A target week must contain at least three sessions to be usable.
    signal_rows = features.groupby("signal_week", observed=True).tail(1).copy()
    close_by_date = ohlc.set_index("date")["close"]
    target_returns: list[float] = []
    target_dates: list[pd.Timestamp | pd.NaT] = []
    target_sessions: list[int] = []
    for date in signal_rows["date"]:
        next_week = date.to_period("W-FRI") + 1
        dates = close_by_date.index[close_by_date.index.to_period("W-FRI") == next_week]
        if len(dates) < 3:
            target_returns.append(np.nan)
            target_dates.append(pd.NaT)
            target_sessions.append(int(len(dates)))
            continue
        end = dates.max()
        start_close = float(close_by_date.loc[date])
        end_close = float(close_by_date.loc[end])
        target_returns.append((end_close / start_close - 1.0) * 100.0)
        target_dates.append(end)
        target_sessions.append(int(len(dates)))

    signal_rows["target_week_end"] = target_dates
    signal_rows["target_week_sessions"] = target_sessions
    signal_rows["y_week"] = target_returns
    signal_rows = signal_rows.dropna(subset=["y_week"]).copy()
    signal_rows["actual"] = labels(signal_rows["y_week"])
    # `period` was already derived from the signal date in the base matrix.  Do
    # not move a late-Dec signal into the following year's training partition.
    signal_rows = signal_rows[signal_rows["period"].isin(PERIODS)].reset_index(drop=True)
    return signal_rows


def apply_rule(rule: Rule, values: np.ndarray) -> np.ndarray:
    oriented = values * rule.orientation
    pred = np.zeros(len(values), dtype=np.int8)
    if rule.mode in {"upper", "both"} and rule.hi is not None:
        pred[oriented >= rule.hi] = 1
    if rule.mode in {"lower", "both"} and rule.lo is not None:
        pred[oriented <= rule.lo] = -1
    return pred


def discover_rules(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    """Fit only on development weeks, then score frozen threshold rules."""
    masks = period_masks(frame)
    dev = masks["dev2023_24"]
    actual = frame["actual"].to_numpy(dtype=np.int8)
    returns = frame["y_week"].to_numpy(dtype=float)
    feature_cols = [
        col for col in frame.columns
        if pd.api.types.is_numeric_dtype(frame[col]) and not is_forbidden_feature(col)
        and col not in {"actual", "signal_close", "target_week_sessions"}
    ]

    rows: list[dict] = []
    vectors: dict[str, np.ndarray] = {}
    for feature in feature_cols:
        values = pd.to_numeric(frame[feature], errors="coerce").to_numpy(dtype=float)
        finite_dev = dev & np.isfinite(values) & np.isfinite(returns)
        if int(finite_dev.sum()) < 30:
            continue
        if not np.isfinite(np.nanstd(values[finite_dev])) or np.nanstd(values[finite_dev]) == 0:
            continue
        rho_result = spearmanr(values[finite_dev], returns[finite_dev])
        rho = float(rho_result.statistic)
        if not np.isfinite(rho) or abs(rho) < 0.10:
            continue
        orientation = 1 if rho > 0 else -1
        oriented = values * orientation
        for mode in ("upper", "lower", "both"):
            for quantile in QUANTILES:
                hi = float(np.nanquantile(oriented[finite_dev], quantile)) if mode in {"upper", "both"} else None
                lo = float(np.nanquantile(oriented[finite_dev], 1.0 - quantile)) if mode in {"lower", "both"} else None
                rule = Rule(feature, orientation, mode, quantile, hi, lo, rho)
                pred = apply_rule(rule, values)
                dev_metrics = metrics(dev, pred, actual)
                # This is only a screen to avoid a huge CSV of zero-information
                # candidates.  The promotion decision remains entirely OOS.
                if int(dev_metrics["n"] or 0) < 10:
                    continue
                if float(dev_metrics["exact_pct"] or 0.0) < 45.0 and float(dev_metrics["sign_pct"] or 0.0) < 55.0:
                    continue
                rule_id = f"{feature}|{orientation}|{mode}|{quantile:.3f}"
                row = {
                    "rule_id": rule_id,
                    "feature": feature,
                    "orientation": orientation,
                    "mode": mode,
                    "quantile": quantile,
                    "threshold_hi": hi,
                    "threshold_lo": lo,
                    "rho_dev": round(rho, 6),
                }
                for name, mask in masks.items():
                    row.update({f"{name}_{key}": value for key, value in metrics(mask, pred, actual).items()})
                rows.append(row)
                vectors[rule_id] = pred

    rules = pd.DataFrame(rows)
    if rules.empty:
        return rules, vectors
    rules["min_holdout_exact_pct"] = rules[["val2025_exact_pct", "confirm2026_exact_pct"]].min(axis=1)
    rules["min_holdout_sign_pct"] = rules[["val2025_sign_pct", "confirm2026_sign_pct"]].min(axis=1)
    rules["mean_holdout_coverage_pct"] = rules[["val2025_coverage_pct", "confirm2026_coverage_pct"]].mean(axis=1)
    rules = rules.sort_values(
        ["min_holdout_exact_pct", "min_holdout_sign_pct", "mean_holdout_coverage_pct"],
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)
    return rules, vectors


def base_feature_name(name: str) -> str:
    """Avoid filling the pair pool with near-identical rolling transforms."""
    for marker in ("_posdays", "_mean", "_sum", "_chg", "_z"):
        if marker in name:
            return name.split(marker, 1)[0]
    return name


def select_pair_pool(rules: pd.DataFrame, max_size: int = 180) -> pd.DataFrame:
    if rules.empty:
        return rules.copy()
    # Score uses development evidence only: selecting pair members with later
    # split numbers would turn the reported holdout into a tuning set.
    ranked = rules.sort_values(
        ["dev2023_24_exact_pct", "dev2023_24_sign_pct", "dev2023_24_n"],
        ascending=False,
        na_position="last",
    )
    selected: list[dict] = []
    seen: dict[str, int] = {}
    for row in ranked.to_dict("records"):
        base = base_feature_name(str(row["feature"]))
        if seen.get(base, 0) >= 2:
            continue
        selected.append(row)
        seen[base] = seen.get(base, 0) + 1
        if len(selected) >= max_size:
            break
    return pd.DataFrame(selected)


def pair_search(frame: pd.DataFrame, rules: pd.DataFrame, vectors: dict[str, np.ndarray]) -> tuple[pd.DataFrame, int]:
    """Test pairs only when their independently-fitted rules agree."""
    pool = select_pair_pool(rules)
    if len(pool) < 2:
        return pd.DataFrame(), 0
    masks = period_masks(frame)
    actual = frame["actual"].to_numpy(dtype=np.int8)
    records: list[dict] = []
    total_pairs = 0
    pool_records = pool.to_dict("records")
    for left_index, left in enumerate(pool_records):
        left_pred = vectors[left["rule_id"]]
        for right in pool_records[left_index + 1:]:
            total_pairs += 1
            right_pred = vectors[right["rule_id"]]
            pred = np.where((left_pred != 0) & (left_pred == right_pred), left_pred, 0).astype(np.int8)
            dev_metrics = metrics(masks["dev2023_24"], pred, actual)
            if int(dev_metrics["n"] or 0) < 10:
                continue
            if float(dev_metrics["exact_pct"] or 0.0) < 50.0 and float(dev_metrics["sign_pct"] or 0.0) < 60.0:
                continue
            record = {
                "left_rule_id": left["rule_id"],
                "left_feature": left["feature"],
                "right_rule_id": right["rule_id"],
                "right_feature": right["feature"],
            }
            for name, mask in masks.items():
                record.update({f"{name}_{key}": value for key, value in metrics(mask, pred, actual).items()})
            records.append(record)
    pairs = pd.DataFrame(records)
    if pairs.empty:
        return pairs, total_pairs
    pairs["min_holdout_exact_pct"] = pairs[["val2025_exact_pct", "confirm2026_exact_pct"]].min(axis=1)
    pairs["min_holdout_sign_pct"] = pairs[["val2025_sign_pct", "confirm2026_sign_pct"]].min(axis=1)
    pairs["mean_holdout_coverage_pct"] = pairs[["val2025_coverage_pct", "confirm2026_coverage_pct"]].mean(axis=1)
    pairs = pairs.sort_values(
        ["min_holdout_exact_pct", "min_holdout_sign_pct", "mean_holdout_coverage_pct"],
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)
    return pairs, total_pairs


def overall_baselines(frame: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for period, mask in period_masks(frame).items():
        actual = frame.loc[mask, "actual"]
        counts = actual.value_counts()
        n = int(mask.sum())
        rows.append({
            "period": period,
            "weeks": n,
            "up": int((actual == 1).sum()),
            "flat": int((actual == 0).sum()),
            "down": int((actual == -1).sum()),
            "majority_baseline_pct": round(float(counts.max() * 100.0 / n), 2) if n else None,
        })
    return rows


def pass_count(frame: pd.DataFrame, *, exact: bool) -> int:
    if frame.empty:
        return 0
    metric = "exact_pct" if exact else "sign_pct"
    n_column = "n" if exact else "sign_n"
    return int((
        (frame[f"val2025_{n_column}"] >= MIN_CALLED_EACH_HOLDOUT)
        & (frame[f"confirm2026_{n_column}"] >= MIN_CALLED_EACH_HOLDOUT)
        & (frame[f"val2025_{metric}"] >= TARGET_ACCURACY_PCT)
        & (frame[f"confirm2026_{metric}"] >= TARGET_ACCURACY_PCT)
    ).sum())


def markdown_table(frame: pd.DataFrame, columns: list[str], max_rows: int = 12) -> str:
    if frame.empty:
        return "_None._\n"
    existing = [column for column in columns if column in frame.columns]
    if not existing:
        return "_None._\n"
    view = frame[existing].head(max_rows)

    def render(value: object) -> str:
        if value is None or pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.4g}"
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [
        "| " + " | ".join(existing) + " |",
        "|" + "|".join("---" for _ in existing) + "|",
    ]
    lines.extend("| " + " | ".join(render(value) for value in row) + " |" for row in view.to_numpy())
    return "\n".join(lines)


def write_report(
    frame: pd.DataFrame,
    rules: pd.DataFrame,
    pairs: pd.DataFrame,
    summary: dict,
    out_dir: Path,
) -> None:
    baseline = pd.DataFrame(overall_baselines(frame))
    baseline.to_csv(out_dir / "weekly_class_balance.csv", index=False)
    top_rules = rules[(rules["val2025_n"] >= MIN_CALLED_EACH_HOLDOUT) & (rules["confirm2026_n"] >= MIN_CALLED_EACH_HOLDOUT)].copy() if not rules.empty else rules
    top_pairs = pairs[(pairs["val2025_n"] >= MIN_CALLED_EACH_HOLDOUT) & (pairs["confirm2026_n"] >= MIN_CALLED_EACH_HOLDOUT)].copy() if not pairs.empty else pairs
    top_rules.to_csv(out_dir / "weekly_single_rules.csv", index=False)
    top_pairs.to_csv(out_dir / "weekly_agreement_pairs.csv", index=False)

    metric_columns = [
        "feature", "mode", "quantile", "rho_dev",
        "dev2023_24_n", "dev2023_24_exact_pct", "dev2023_24_sign_pct",
        "val2025_n", "val2025_exact_pct", "val2025_sign_pct",
        "confirm2026_n", "confirm2026_exact_pct", "confirm2026_sign_pct",
        "min_holdout_exact_pct", "min_holdout_sign_pct",
    ]
    pair_columns = [
        "left_feature", "right_feature",
        "dev2023_24_n", "dev2023_24_exact_pct", "dev2023_24_sign_pct",
        "val2025_n", "val2025_exact_pct", "val2025_sign_pct",
        "confirm2026_n", "confirm2026_exact_pct", "confirm2026_sign_pct",
        "min_holdout_exact_pct", "min_holdout_sign_pct",
    ]
    baseline_columns = ["period", "weeks", "up", "flat", "down", "majority_baseline_pct"]
    report = f"""# V12 weekly composite search — next Monday to Friday

> **Research only. No production decoder or weekly direction was changed by this run.**
> This is a leak-safe test of the user's requested combination approach, not a
> licence to optimise repeatedly against the same 2025/2026 results.

## Forecast definition and timing

- A signal is made after the **last available session of a week** (normally Friday) from information known by that close.
- It forecasts the close of the **following Monday--Friday calendar week**; weeks with fewer than three trading sessions are excluded.
- UP / FLAT / DOWN labels use a predeclared ±{FLAT_BAND_PCT:.2f}% weekly-return FLAT band.
- Development fit: 2023--2024. Validation: 2025. Confirmation: 2026.
- Participant OI, participant volume, option-chain proxy, price-regime and v2/v3 *signal* fields were supplied to the search. Prior backtest outcomes, target OHLC values, exact-hit flags and level-hit flags were explicitly excluded.

## Dataset and gates

- Usable weekly episodes: **{summary['weekly_rows']}** (development {summary['period_counts']['dev2023_24']}, validation {summary['period_counts']['val2025']}, confirmation {summary['period_counts']['confirm2026']}).
- Point-in-time numeric feature candidates after the leakage deny-list: **{summary['feature_candidates']}**.
- Single threshold rules retained after development screen: **{summary['single_rules']}**.
- Agreement pairs evaluated from a development-selected pool: **{summary['pairs_checked']}**.
- Promotion gate: **≥{TARGET_ACCURACY_PCT:.0f}%** on both 2025 and 2026 with at least **{MIN_CALLED_EACH_HOLDOUT}** calls in each period.

{markdown_table(baseline, baseline_columns, 10)}

## Result

- Single rules passing the {TARGET_ACCURACY_PCT:.0f}% **exact** gate: **{summary['single_pass_exact']}**.
- Single rules passing the {TARGET_ACCURACY_PCT:.0f}% non-FLAT **sign** gate: **{summary['single_pass_sign']}**.
- Agreement pairs passing the {TARGET_ACCURACY_PCT:.0f}% **exact** gate: **{summary['pair_pass_exact']}**.
- Agreement pairs passing the {TARGET_ACCURACY_PCT:.0f}% non-FLAT **sign** gate: **{summary['pair_pass_sign']}**.

A result of zero means the available historical EOD combinations did **not** prove
an 85% weekly directional predictor under the declared out-of-sample guard. The
scenario playbook can remain in the report, but it must remain context/conditional
rather than an 85% weekly forecast.

## Best single-rule candidates with both holdout sample guards

{markdown_table(top_rules, metric_columns, 12)}

## Best agreement-pair candidates with both holdout sample guards

{markdown_table(top_pairs, pair_columns, 12)}

## Implementation consequence

No weekly direction module is promoted from V12 unless a candidate meets the
gate above and subsequently survives a fresh forward window. The report should
continue to display the Monday--Friday **playbook** (Monday range seed,
Tuesday--Wednesday expansion test, expiry/sweep caution, Friday follow-through
or mean-reversion check) with `CONTEXT_ONLY` / `NO-VALIDATED-EDGE` status.

The existing V10 small-gap previous-close-touch module remains separate: it is
an at-open, same-day level-touch event and cannot be counted as proof of a
night-before Monday--Friday direction forecast.
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
    parser.add_argument("--out", default="reports/v12_weekly_composite_search")
    args = parser.parse_args()
    # build_enhanced_matrix accepts this optional attribute when it has to
    # rebuild its input matrix.
    args.save_input_matrix = False

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    enhanced = build_enhanced_matrix(args)
    weekly = build_weekly_frame(enhanced, Path(args.ohlc))
    rules, vectors = discover_rules(weekly)
    pairs, pairs_checked = pair_search(weekly, rules, vectors)

    feature_candidates = sum(
        1 for col in weekly.columns
        if pd.api.types.is_numeric_dtype(weekly[col])
        and not is_forbidden_feature(col)
        and col not in {"actual", "signal_close", "target_week_sessions"}
    )
    counts = {period: int(mask.sum()) for period, mask in period_masks(weekly).items()}
    summary = {
        "weekly_rows": int(len(weekly)),
        "period_counts": counts,
        "feature_candidates": int(feature_candidates),
        "single_rules": int(len(rules)),
        "pairs_checked": int(pairs_checked),
        "pairs_exported": int(len(pairs)),
        "single_pass_exact": pass_count(rules, exact=True),
        "single_pass_sign": pass_count(rules, exact=False),
        "pair_pass_exact": pass_count(pairs, exact=True),
        "pair_pass_sign": pass_count(pairs, exact=False),
        "flat_band_pct": FLAT_BAND_PCT,
        "min_called_each_holdout": MIN_CALLED_EACH_HOLDOUT,
        "target_accuracy_pct": TARGET_ACCURACY_PCT,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    weekly[["date", "target_week_end", "target_week_sessions", "period", "y_week", "actual"]].to_csv(
        out_dir / "weekly_episodes.csv", index=False
    )
    write_report(weekly, rules, pairs, summary, out_dir)
    print(json.dumps(summary, indent=2))
    print(f"wrote {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
