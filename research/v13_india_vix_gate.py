#!/usr/bin/env python3
"""V13 — India-VIX timing-correct gate for the daily OI lean.

V4--V6 exhaustively searched the existing EOD OI/options/price matrix.  This
pass adds one genuinely new, explicitly provisional, data family: India VIX.
The experiment asks a narrow and deployable question:

    At the close of signal day D, can the then-known India VIX state improve
    the next session's V3 OI direction, especially the executable
    next-open-to-close direction?

It does *not* treat a VIX number published during D+1 as a D feature.  The
third-party VIX source is pinned and marked research-only in historical/manifest
and is not wired into the production decoder regardless of this experiment.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
FLAT_BAND_PCT = 0.15
PERIODS = ("dev2023_24", "val2025", "confirm2026")
QUANTILES = (0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.925, 0.95)
MIN_HOLDOUT_CALLS = 20
TARGET_ACCURACY_PCT = 85.0


@dataclass(frozen=True)
class Threshold:
    feature: str
    orientation: int
    mode: str
    quantile: float
    high: float | None
    low: float | None
    rho_dev: float


def labels(values: np.ndarray | pd.Series, band: float = FLAT_BAND_PCT) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    return np.where(values > band, 1, np.where(values < -band, -1, 0)).astype(np.int8)


def pct(n: int, d: int) -> float | None:
    return round(n * 100.0 / d, 2) if d else None


def metric(mask: np.ndarray, pred: np.ndarray, actual: np.ndarray) -> dict[str, int | float | None]:
    called = mask & (pred != 0)
    n = int(called.sum())
    output: dict[str, int | float | None] = {
        "n": n,
        "coverage_pct": pct(n, int(mask.sum())),
        "up_calls": int((pred[called] == 1).sum()),
        "down_calls": int((pred[called] == -1).sum()),
    }
    if not n:
        output.update({"exact_pct": None, "sign_n": 0, "sign_pct": None})
        return output
    output["exact_pct"] = pct(int((pred[called] == actual[called]).sum()), n)
    sign_mask = called & (actual != 0)
    sign_n = int(sign_mask.sum())
    output["sign_n"] = sign_n
    output["sign_pct"] = pct(int((pred[sign_mask] == actual[sign_mask]).sum()), sign_n)
    return output


def masks(frame: pd.DataFrame) -> dict[str, np.ndarray]:
    period = frame["period"].to_numpy(dtype=str)
    return {name: period == name for name in PERIODS}


def load_vix(path: Path) -> pd.DataFrame:
    """Validate source dates/columns and create values available by D close."""
    raw = pd.read_csv(path)
    required = {"Date", "Sum of Open", "Sum of High", "Sum of Low", "Sum of Close"}
    missing = sorted(required - set(raw.columns))
    if missing:
        raise ValueError(f"India VIX source missing columns: {missing}")
    out = pd.DataFrame({
        "signal_date": pd.to_datetime(raw["Date"], format="%Y-%m-%d %H:%M:%S", errors="coerce"),
        "vix_open": pd.to_numeric(raw["Sum of Open"], errors="coerce"),
        "vix_high": pd.to_numeric(raw["Sum of High"], errors="coerce"),
        "vix_low": pd.to_numeric(raw["Sum of Low"], errors="coerce"),
        "vix_close": pd.to_numeric(raw["Sum of Close"], errors="coerce"),
    })
    out = out.dropna().sort_values("signal_date").drop_duplicates("signal_date").reset_index(drop=True)
    if out.empty or (out[["vix_open", "vix_high", "vix_low", "vix_close"]] <= 0).any().any():
        raise ValueError("India VIX source has no usable positive OHLC rows")
    if (out["vix_high"] < out[["vix_open", "vix_close"]].max(axis=1)).any() or (
        out["vix_low"] > out[["vix_open", "vix_close"]].min(axis=1)
    ).any():
        raise ValueError("India VIX source has internally inconsistent OHLC rows")

    close = out["vix_close"]
    daily_change = close.pct_change() * 100.0
    out["vix_oc_pct"] = (close / out["vix_open"] - 1.0) * 100.0
    out["vix_range_pct"] = (out["vix_high"] - out["vix_low"]) / close * 100.0
    for window in (1, 2, 3, 5, 10, 20):
        out[f"vix_ret{window}"] = close.pct_change(window) * 100.0
    for window in (5, 10, 20):
        avg = close.rolling(window, min_periods=max(3, window // 2)).mean()
        std = close.rolling(window, min_periods=max(3, window // 2)).std().replace(0, np.nan)
        out[f"vix_z{window}"] = (close - avg) / std
        out[f"vix_range_mean{window}"] = out["vix_range_pct"].rolling(window, min_periods=max(3, window // 2)).mean()
    # No forward fill: a missing same-date VIX is never silently replaced.
    return out


def load_frame(predictions_path: Path, vix_path: Path) -> tuple[pd.DataFrame, dict]:
    pred = pd.read_csv(predictions_path, parse_dates=["signal_date", "target_date"])
    required = {"signal_date", "target_date", "predicted_class", "actual_return_pct", "intraday_return_pct"}
    missing = sorted(required - set(pred.columns))
    if missing:
        raise ValueError(f"v3 predictions missing columns: {missing}")
    direction = pred["predicted_class"].map({"UP": 1, "DOWN": -1}).fillna(0).astype(np.int8)
    frame = pred[["signal_date", "target_date", "actual_return_pct", "intraday_return_pct"]].copy()
    frame["v3_pred"] = direction
    frame["signal_date"] = pd.to_datetime(frame["signal_date"]).dt.normalize()
    frame = frame.merge(load_vix(vix_path), on="signal_date", how="inner", validate="one_to_one")
    frame["period"] = np.where(
        frame["signal_date"] < pd.Timestamp("2025-01-01"), "dev2023_24",
        np.where(frame["signal_date"] < pd.Timestamp("2026-01-01"), "val2025", "confirm2026"),
    )
    # Source coverage ends 2026-08-24, deliberately leaving later rows out of
    # this VIX experiment rather than fabricating a current value.
    frame = frame.dropna(subset=["actual_return_pct", "intraday_return_pct"]).sort_values("signal_date").reset_index(drop=True)
    metadata = {
        "signal_rows_after_vix_merge": int(len(frame)),
        "vix_first_signal_date": frame["signal_date"].min().date().isoformat() if not frame.empty else None,
        "vix_last_signal_date": frame["signal_date"].max().date().isoformat() if not frame.empty else None,
        "vix_missing_v3_signal_dates": int(len(pred) - len(frame)),
    }
    return frame, metadata


def apply_direct(threshold: Threshold, values: np.ndarray) -> np.ndarray:
    oriented = values * threshold.orientation
    pred = np.zeros(len(values), dtype=np.int8)
    if threshold.mode in {"upper", "both"} and threshold.high is not None:
        pred[oriented >= threshold.high] = 1
    if threshold.mode in {"lower", "both"} and threshold.low is not None:
        pred[oriented <= threshold.low] = -1
    return pred


def search(frame: pd.DataFrame, *, outcome: str) -> pd.DataFrame:
    """Fit VIX thresholds on development, then score frozen gates on later data."""
    if outcome not in {"close_to_close", "open_to_close"}:
        raise ValueError(outcome)
    target_col = "actual_return_pct" if outcome == "close_to_close" else "intraday_return_pct"
    y_return = frame[target_col].to_numpy(dtype=float)
    actual = labels(y_return)
    split = masks(frame)
    dev = split["dev2023_24"]
    vix_cols = [column for column in frame.columns if column.startswith("vix_")]
    rows: list[dict] = []
    for feature in vix_cols:
        values = frame[feature].to_numpy(dtype=float)
        finite_dev = dev & np.isfinite(values) & np.isfinite(y_return)
        if int(finite_dev.sum()) < 150 or np.nanstd(values[finite_dev]) == 0:
            continue
        rho = float(spearmanr(values[finite_dev], y_return[finite_dev]).statistic)
        if not math.isfinite(rho) or abs(rho) < 0.015:
            continue
        orientation = 1 if rho >= 0 else -1
        oriented = values * orientation
        for mode in ("upper", "lower", "both"):
            for q in QUANTILES:
                high = float(np.nanquantile(oriented[finite_dev], q)) if mode in {"upper", "both"} else None
                low = float(np.nanquantile(oriented[finite_dev], 1.0 - q)) if mode in {"lower", "both"} else None
                threshold = Threshold(feature, orientation, mode, q, high, low, rho)
                vix_pred = apply_direct(threshold, values)
                # Three strategies test whether VIX has standalone directional
                # content, gates v3 into a more precise subset, or agrees with v3.
                candidates = {
                    "vix_direct": vix_pred,
                    "v3_vix_gate": np.where(vix_pred != 0, frame["v3_pred"].to_numpy(dtype=np.int8), 0),
                    "v3_vix_agree": np.where(
                        (vix_pred != 0) & (vix_pred == frame["v3_pred"].to_numpy(dtype=np.int8)),
                        frame["v3_pred"].to_numpy(dtype=np.int8), 0,
                    ),
                }
                for strategy, prediction in candidates.items():
                    dev_metric = metric(dev, prediction, actual)
                    if int(dev_metric["n"] or 0) < 20:
                        continue
                    # Development-only storage screen.  It does not inspect
                    # 2025/2026 before a rule is created.
                    if float(dev_metric["exact_pct"] or 0.0) < 42.0 and float(dev_metric["sign_pct"] or 0.0) < 52.0:
                        continue
                    row = {
                        "outcome": outcome,
                        "strategy": strategy,
                        "feature": feature,
                        "orientation": orientation,
                        "mode": mode,
                        "quantile": q,
                        "threshold_high": high,
                        "threshold_low": low,
                        "rho_dev": round(rho, 6),
                    }
                    for name, mask in split.items():
                        row.update({f"{name}_{key}": value for key, value in metric(mask, prediction, actual).items()})
                    rows.append(row)
    rules = pd.DataFrame(rows)
    if rules.empty:
        return rules
    rules["min_holdout_exact_pct"] = rules[["val2025_exact_pct", "confirm2026_exact_pct"]].min(axis=1)
    rules["min_holdout_sign_pct"] = rules[["val2025_sign_pct", "confirm2026_sign_pct"]].min(axis=1)
    rules["mean_holdout_coverage_pct"] = rules[["val2025_coverage_pct", "confirm2026_coverage_pct"]].mean(axis=1)
    return rules.sort_values(
        ["outcome", "min_holdout_exact_pct", "min_holdout_sign_pct", "mean_holdout_coverage_pct"],
        ascending=[True, False, False, False],
        na_position="last",
    ).reset_index(drop=True)


def baseline_rows(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    split = masks(frame)
    v3_pred = frame["v3_pred"].to_numpy(dtype=np.int8)
    for outcome, col in (("close_to_close", "actual_return_pct"), ("open_to_close", "intraday_return_pct")):
        actual = labels(frame[col])
        for period, mask in split.items():
            result = metric(mask, v3_pred, actual)
            rows.append({"outcome": outcome, "strategy": "v3_ungated", "period": period, **result})
    return pd.DataFrame(rows)


def pass_count(rules: pd.DataFrame, *, exact: bool) -> int:
    if rules.empty:
        return 0
    measure = "exact_pct" if exact else "sign_pct"
    calls = "n" if exact else "sign_n"
    return int((
        (rules[f"val2025_{calls}"] >= MIN_HOLDOUT_CALLS)
        & (rules[f"confirm2026_{calls}"] >= MIN_HOLDOUT_CALLS)
        & (rules[f"val2025_{measure}"] >= TARGET_ACCURACY_PCT)
        & (rules[f"confirm2026_{measure}"] >= TARGET_ACCURACY_PCT)
    ).sum())


def table(frame: pd.DataFrame, columns: list[str], max_rows: int = 12) -> str:
    if frame.empty:
        return "_None._\n"
    columns = [column for column in columns if column in frame.columns]
    if not columns:
        return "_None._\n"
    view = frame[columns].head(max_rows)

    def cell(value: object) -> str:
        if value is None or pd.isna(value):
            return ""
        return f"{value:.4g}" if isinstance(value, float) else str(value).replace("|", "\\|")

    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    lines.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in view.to_numpy())
    return "\n".join(lines)


def write_report(frame: pd.DataFrame, baseline: pd.DataFrame, rules: pd.DataFrame, summary: dict, out: Path) -> None:
    baseline.to_csv(out / "baseline.csv", index=False)
    guarded = rules[(rules["val2025_n"] >= MIN_HOLDOUT_CALLS) & (rules["confirm2026_n"] >= MIN_HOLDOUT_CALLS)].copy() if not rules.empty else rules
    guarded.to_csv(out / "vix_gate_rules.csv", index=False)
    columns = [
        "outcome", "strategy", "feature", "mode", "quantile", "rho_dev",
        "dev2023_24_n", "dev2023_24_exact_pct", "dev2023_24_sign_pct",
        "val2025_n", "val2025_exact_pct", "val2025_sign_pct",
        "confirm2026_n", "confirm2026_exact_pct", "confirm2026_sign_pct",
        "min_holdout_exact_pct", "min_holdout_sign_pct",
    ]
    report = f"""# V13 India-VIX gate — daily next-session combination test

> **Research only; production decoder unchanged.** The India VIX source is a
> third-party derived historical dataset pinned in `historical/manifest.json`.
> It must not be treated as independently verified production data.

## Question and timing

Can the India VIX state known at the close of OI signal day **D** add a robust
gate to the v3 OI lean for D+1?  Every VIX feature here is calculated only from
D and earlier.  No D+1 VIX, D+1 high/low, outcome/hit field, or forward-filled
missing value is used.

- VIX-aligned signal rows: **{summary['signal_rows_after_vix_merge']}**
  ({summary['vix_first_signal_date']} to {summary['vix_last_signal_date']}).
- VIX source coverage excludes {summary['vix_missing_v3_signal_dates']} v3 rows;
  those are not imputed.
- Development: 2023--24; validation: 2025; confirmation: 2026 through the
  available VIX cutoff. Flat band: ±{FLAT_BAND_PCT:.2f}%.
- Strategies: VIX standalone direction; v3 only in a VIX state; and v3/VIX
  directional agreement. Threshold orientation and quantile are fitted on the
  development split only.
- Promotion gate: **{TARGET_ACCURACY_PCT:.0f}%** in *both* later splits with at
  least **{MIN_HOLDOUT_CALLS}** calls each.

## Ungated v3 reference

{table(baseline, ['outcome', 'strategy', 'period', 'n', 'coverage_pct', 'exact_pct', 'sign_n', 'sign_pct'], 10)}

## Result

- Rules passing the 85% exact gate: **{summary['pass_exact']}**.
- Rules passing the 85% non-FLAT sign gate: **{summary['pass_sign']}**.

The open-to-close section is the executable diagnostic because D's OI/VIX data
is only known after D's market close. Close-to-close includes the overnight gap,
so it cannot by itself prove a tradeable night-before edge.

## Best candidates with sample guards

{table(guarded, columns, 24)}

## Decision

No VIX feature is wired into the production score unless it clears the stated
gate and then survives a new forward period from an independently verified VIX
source. In all other cases VIX may be displayed as qualitative risk context
only, never as a claimed 85% direction signal.
"""
    (out / "report.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v3-predictions", default="reports/backtest_v3_candidate_2023-08_to_2026-09/v3_predictions.csv")
    parser.add_argument("--india-vix", default="historical/india_vix.csv")
    parser.add_argument("--out", default="reports/v13_india_vix_gate")
    args = parser.parse_args()

    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    frame, metadata = load_frame(Path(args.v3_predictions), Path(args.india_vix))
    rules = pd.concat([search(frame, outcome="close_to_close"), search(frame, outcome="open_to_close")], ignore_index=True)
    baseline = baseline_rows(frame)
    summary = {
        **metadata,
        "vix_feature_count": int(len([c for c in frame if c.startswith("vix_")])),
        "rules_exported": int(len(rules)),
        "pass_exact": pass_count(rules, exact=True),
        "pass_sign": pass_count(rules, exact=False),
        "target_accuracy_pct": TARGET_ACCURACY_PCT,
        "min_holdout_calls": MIN_HOLDOUT_CALLS,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    frame.to_csv(output / "vix_aligned_signals.csv", index=False)
    write_report(frame, baseline, rules, summary, output)
    print(json.dumps(summary, indent=2))
    print(f"wrote {output / 'report.md'}")


if __name__ == "__main__":
    main()
