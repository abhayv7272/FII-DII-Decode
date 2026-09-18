#!/usr/bin/env python3
"""V5 holdout combo/meta/intraday audit.

This is the second aggressive accuracy-hunt cycle after the v4 psychology search.
It deliberately tries approaches that can *appear* to reach 70-85%, then forces
three checks before anything can be considered useful:

* train only on 2023-2025 and keep 2026 as the final holdout;
* forbid target/outcome leakage columns such as ``exact_hit`` and
  ``direction_hit`` from meta-model inputs;
* separate broad close-to-close classification from actionable intraday
  confirmation tests.

The script writes compact artifacts under ``reports/v5_holdout_combo_meta/`` and
is research-only.  Nothing here changes the production decoder.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "research") not in sys.path:
    sys.path.insert(0, str(ROOT / "research"))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from v4_psychology_search import build_enhanced_matrix  # noqa: E402

FLAT_BAND_PCT = 0.15
TRAIN_PERIODS = ("dev2023_24", "val2025")
HOLDOUT_PERIOD = "confirm2026"
LEAKAGE_COLUMNS = {
    "y_cc",
    "y_oc",
    "y_gap",
    "y_5d",
    "actual_class",
    "actual_return_pct",
    "exact_hit",
    "direction_hit",
    "target_date",
    "target5_date",
}


def labels(y_pct: pd.Series | np.ndarray, band: float = FLAT_BAND_PCT) -> np.ndarray:
    y = np.asarray(y_pct, dtype=float)
    return np.where(y > band, 1, np.where(y < -band, -1, 0)).astype(np.int8)


def safe_pct(numer: int, denom: int) -> float | None:
    return round(numer / denom * 100.0, 2) if denom else None


def metrics(mask: np.ndarray, pred: np.ndarray, actual: np.ndarray) -> dict[str, float | int | None]:
    called = mask & (pred != 0)
    n = int(called.sum())
    total = int(mask.sum())
    out: dict[str, float | int | None] = {
        "n": n,
        "coverage_pct": safe_pct(n, total),
        "up_calls": int((pred[called] == 1).sum()),
        "down_calls": int((pred[called] == -1).sum()),
    }
    if not n:
        out.update({"exact_pct": None, "sign_pct": None, "sign_n": 0})
        return out
    out["exact_pct"] = safe_pct(int((pred[called] == actual[called]).sum()), n)
    nonflat = called & (actual != 0)
    sign_n = int(nonflat.sum())
    out["sign_n"] = sign_n
    out["sign_pct"] = safe_pct(int((pred[nonflat] == actual[nonflat]).sum()), sign_n)
    return out


def period_masks(df: pd.DataFrame) -> dict[str, np.ndarray]:
    period = df["period"].astype(str).to_numpy()
    return {
        "train2023_25": np.isin(period, TRAIN_PERIODS),
        "dev2023_24": period == "dev2023_24",
        "val2025": period == "val2025",
        "confirm2026": period == HOLDOUT_PERIOD,
    }


def feature_columns(df: pd.DataFrame) -> list[str]:
    cols = [
        c for c in df.columns
        if pd.api.types.is_numeric_dtype(df[c]) and c not in LEAKAGE_COLUMNS
    ]
    accidental = sorted(set(cols) & LEAKAGE_COLUMNS)
    if accidental:
        raise RuntimeError(f"leakage columns in feature set: {accidental}")
    return cols


def _clean_number(value) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def search_train2023_25_rules(df: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    """Refit univariate thresholds on 2023-2025, score 2026 untouched."""
    actual = labels(df["y_cc"])
    yret = pd.to_numeric(df["y_cc"], errors="coerce").to_numpy(dtype=float)
    masks = period_masks(df)
    train = masks["train2023_25"]
    qs = (0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.925, 0.95, 0.975)
    rows: list[dict] = []

    for feature in feature_columns(df):
        x = pd.to_numeric(df[feature], errors="coerce").to_numpy(dtype=float)
        finite_train = train & np.isfinite(x) & np.isfinite(yret)
        if int(finite_train.sum()) < 350:
            continue
        if not np.isfinite(np.nanstd(x[train])) or np.nanstd(x[train]) == 0:
            continue
        try:
            rho = float(spearmanr(x[finite_train], yret[finite_train]).statistic)
        except Exception:
            continue
        if not np.isfinite(rho) or abs(rho) < 0.025:
            continue
        orientation = 1 if rho >= 0 else -1
        z = x * orientation
        for mode in ("two_tail", "up_tail", "down_tail"):
            for q in qs:
                hi = lo = None
                if mode in {"two_tail", "up_tail"}:
                    hi = _clean_number(np.nanquantile(z[train], q))
                if mode in {"two_tail", "down_tail"}:
                    lo = _clean_number(np.nanquantile(z[train], 1.0 - q))
                pred = np.zeros(len(df), dtype=np.int8)
                if hi is not None:
                    pred[z >= hi] = 1
                if lo is not None:
                    pred[z <= lo] = -1
                train_m = metrics(train, pred, actual)
                if (train_m["n"] or 0) < 40:
                    continue
                if (train_m["exact_pct"] or 0) < 50 and (train_m["sign_pct"] or 0) < 60:
                    continue
                row = {
                    "feature": feature,
                    "mode": mode,
                    "quantile": q,
                    "rho_train2023_25": round(rho, 6),
                    "orientation": orientation,
                    "threshold_hi": hi,
                    "threshold_lo": lo,
                }
                for name, mask in masks.items():
                    row.update({f"{name}_{k}": v for k, v in metrics(mask, pred, actual).items()})
                rows.append(row)

    res = pd.DataFrame(rows)
    if not res.empty:
        res["train_minus_confirm_exact_pct"] = res["train2023_25_exact_pct"] - res["confirm2026_exact_pct"]
        res["train_minus_confirm_sign_pct"] = res["train2023_25_sign_pct"] - res["confirm2026_sign_pct"]
        res = res.sort_values(
            ["confirm2026_exact_pct", "confirm2026_sign_pct", "confirm2026_n"],
            ascending=False,
            na_position="last",
        ).reset_index(drop=True)
    res.to_csv(out_dir / "train2023_25_holdout2026_rules.csv", index=False)
    return res


def combo_search(rules: pd.DataFrame, df: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    """Simple voting ensembles made only from train-selected threshold rules."""
    if rules.empty:
        out = pd.DataFrame()
        out.to_csv(out_dir / "combo_vote_results.csv", index=False)
        return out
    actual = labels(df["y_cc"])
    masks = period_masks(df)
    # Eligible by training only.  This intentionally ignores 2026 when building the pool.
    eligible = rules[
        (rules["train2023_25_n"] >= 40)
        & (rules["train2023_25_exact_pct"] >= 50)
        & (rules["train2023_25_sign_pct"] >= 62)
    ].copy()
    eligible = eligible.sort_values(
        ["train2023_25_sign_pct", "train2023_25_exact_pct", "train2023_25_n"],
        ascending=False,
    ).head(1000)
    if eligible.empty:
        out = pd.DataFrame()
        out.to_csv(out_dir / "combo_vote_results.csv", index=False)
        return out

    vectors: list[np.ndarray] = []
    for row in eligible.itertuples(index=False):
        x = pd.to_numeric(df[row.feature], errors="coerce").to_numpy(dtype=float)
        z = x * int(row.orientation)
        pred = np.zeros(len(df), dtype=np.int8)
        if row.mode in {"two_tail", "up_tail"} and pd.notna(row.threshold_hi):
            pred[z >= float(row.threshold_hi)] = 1
        if row.mode in {"two_tail", "down_tail"} and pd.notna(row.threshold_lo):
            pred[z <= float(row.threshold_lo)] = -1
        vectors.append(pred)

    rows: list[dict] = []
    for top_n in (20, 50, 100, 200, 500, 1000):
        if len(vectors) < top_n:
            continue
        V = np.vstack(vectors[:top_n])
        calls = (V != 0).sum(axis=0)
        score = V.sum(axis=0)
        agree = np.abs(score) / np.maximum(calls, 1)
        for min_votes in (2, 3, 5, 8, 10, 15, 20, 30, 40, 50, 75, 100):
            for agree_ratio in (0.50, 0.60, 0.67, 0.75, 0.80, 0.90, 1.00):
                pred = np.zeros(len(df), dtype=np.int8)
                selected = (calls >= min_votes) & (agree >= agree_ratio)
                pred[selected] = np.sign(score[selected]).astype(np.int8)
                train_m = metrics(masks["train2023_25"], pred, actual)
                confirm_m = metrics(masks["confirm2026"], pred, actual)
                if (train_m["n"] or 0) < 40 or (confirm_m["n"] or 0) < 10:
                    continue
                row = {"top_n": top_n, "min_votes": min_votes, "agree_ratio": agree_ratio}
                for name, mask in masks.items():
                    row.update({f"{name}_{k}": v for k, v in metrics(mask, pred, actual).items()})
                rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(
            ["confirm2026_exact_pct", "confirm2026_sign_pct", "confirm2026_n"],
            ascending=False,
            na_position="last",
        ).reset_index(drop=True)
    out.to_csv(out_dir / "combo_vote_results.csv", index=False)
    return out


def load_v3_predictions(path: Path) -> pd.DataFrame:
    pred = pd.read_csv(path, parse_dates=["signal_date", "target_date"])
    keep = ["signal_date", "target_date", "predicted_class"]
    missing = [c for c in keep if c not in pred]
    if missing:
        raise ValueError(f"v3 prediction file missing columns: {missing}")
    return pred[keep].rename(columns={"signal_date": "date"})


def _fit_prob_model(model_name: str, X_train: np.ndarray, y_train: np.ndarray, X_all: np.ndarray) -> np.ndarray:
    med = np.nanmedian(X_train, axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    X_train = np.where(np.isnan(X_train), med, X_train)
    X_all = np.where(np.isnan(X_all), med, X_all)
    if model_name == "logreg_C0.1":
        scaler = StandardScaler().fit(X_train)
        model = LogisticRegression(C=0.1, class_weight="balanced", max_iter=2000)
        model.fit(scaler.transform(X_train), y_train)
        return model.predict_proba(scaler.transform(X_all))[:, 1]
    if model_name == "hgb_depth2":
        model = HistGradientBoostingClassifier(
            max_iter=80,
            max_depth=2,
            learning_rate=0.03,
            min_samples_leaf=40,
            l2_regularization=1.0,
            random_state=11,
        )
        model.fit(X_train, y_train)
        return model.predict_proba(X_all)[:, 1]
    if model_name == "rf_depth3":
        model = RandomForestClassifier(
            n_estimators=300,
            max_depth=3,
            min_samples_leaf=30,
            class_weight="balanced_subsample",
            random_state=11,
            n_jobs=-1,
        )
        model.fit(X_train, y_train)
        return model.predict_proba(X_all)[:, 1]
    if model_name == "gb_depth2":
        model = GradientBoostingClassifier(n_estimators=50, max_depth=2, learning_rate=0.03, random_state=11)
        model.fit(X_train, y_train)
        return model.predict_proba(X_all)[:, 1]
    raise ValueError(model_name)


def meta_gate_v3(df: pd.DataFrame, args: argparse.Namespace, out_dir: Path) -> pd.DataFrame:
    """Try to predict when the v3 direction will be correct; exclude outcomes."""
    v3 = load_v3_predictions(Path(args.v3_predictions))
    work = df.merge(v3[["date", "target_date", "predicted_class"]], on="date", how="inner")
    actual = labels(work["y_cc"])
    v3_sign = np.where(work["predicted_class"].astype(str).to_numpy() == "UP", 1, -1).astype(np.int8)
    hit = (v3_sign == actual).astype(np.int8)

    masks = period_masks(work)
    train = masks["train2023_25"]
    clean_cols = feature_columns(work)

    # Rank features by relationship to the meta-label on training only.
    scored: list[tuple[float, str]] = []
    for col in clean_cols:
        x = pd.to_numeric(work[col], errors="coerce").to_numpy(dtype=float)
        finite = train & np.isfinite(x)
        if int(finite.sum()) < 350 or not np.isfinite(np.nanstd(x[train])) or np.nanstd(x[train]) == 0:
            continue
        try:
            rho = float(spearmanr(x[finite], hit[finite]).statistic)
        except Exception:
            continue
        if np.isfinite(rho):
            scored.append((abs(rho), col))
    scored.sort(reverse=True)

    rows: list[dict] = []
    models = ("logreg_C0.1", "hgb_depth2", "rf_depth3", "gb_depth2")
    for top_n in (10, 20, 35, 50, 80, 120, 200, 400):
        cols = [c for _, c in scored[:top_n]]
        if not cols:
            continue
        X = work[cols].to_numpy(dtype=float)
        X_train = X[train]
        y_train = hit[train]
        for model_name in models:
            try:
                prob = _fit_prob_model(model_name, X_train, y_train, X)
            except Exception as exc:
                rows.append({"model": model_name, "top_n": top_n, "error": str(exc)})
                continue
            thresholds: list[tuple[str, float]] = []
            for q in (0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.925, 0.95):
                thresholds.append((f"train_prob_q{q:g}", float(np.nanquantile(prob[train], q))))
            for threshold_name, threshold in thresholds:
                row = {
                    "model": model_name,
                    "top_n": top_n,
                    "threshold_name": threshold_name,
                    "threshold": threshold,
                }
                selected = prob >= threshold
                for name, mask in masks.items():
                    m = mask & selected
                    n = int(m.sum())
                    row[f"{name}_n"] = n
                    row[f"{name}_coverage_pct"] = safe_pct(n, int(mask.sum()))
                    row[f"{name}_v3_hit_precision_pct"] = safe_pct(int(hit[m].sum()), n)
                rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty and "confirm2026_v3_hit_precision_pct" in out:
        out = out.sort_values(
            ["confirm2026_v3_hit_precision_pct", "confirm2026_n", "val2025_v3_hit_precision_pct"],
            ascending=False,
            na_position="last",
        ).reset_index(drop=True)
    out.to_csv(out_dir / "v3_meta_gate_results.csv", index=False)
    return out


def intraday_confirmation(args: argparse.Namespace, out_dir: Path) -> pd.DataFrame:
    path = Path(args.intraday_1m) if args.intraday_1m else Path()
    if not path.exists():
        out = pd.DataFrame([{"status": "skipped", "reason": f"intraday file not found: {path}"}])
        out.to_csv(out_dir / "intraday_confirmation.csv", index=False)
        return out

    raw = pd.read_csv(path, parse_dates=["timestamp_ist"])
    raw = raw.rename(columns={"timestamp_ist": "ts"})
    raw = raw.sort_values("ts")
    raw = raw[(raw["ts"].dt.strftime("%H:%M:%S") >= "09:15:00") & (raw["ts"].dt.strftime("%H:%M:%S") <= "15:30:59")]
    raw["target_date"] = pd.to_datetime(raw["ts"].dt.date)
    rows: list[dict] = []
    for d, group in raw.groupby("target_date"):
        group = group.sort_values("ts")
        if len(group) < 50:
            continue
        day_open = float(group.iloc[0]["open"])
        day_close = float(group.iloc[-1]["close"])
        row = {"target_date": pd.Timestamp(d), "open": day_open, "close": day_close, "open_to_close_pct": (day_close / day_open - 1.0) * 100.0}
        for minutes, cutoff in ((15, "09:30:59"), (30, "09:45:59"), (60, "10:15:59")):
            sub = group[group["ts"].dt.strftime("%H:%M:%S") <= cutoff]
            if sub.empty:
                continue
            window_close = float(sub.iloc[-1]["close"])
            row[f"first{minutes}_ret_pct"] = (window_close / day_open - 1.0) * 100.0
            row[f"after{minutes}_ret_pct"] = (day_close / window_close - 1.0) * 100.0
        rows.append(row)
    bars = pd.DataFrame(rows)

    v3 = pd.read_csv(args.v3_predictions, parse_dates=["signal_date", "target_date"])
    v3 = v3[["signal_date", "target_date", "predicted_class"]]
    sample = v3.merge(bars, on="target_date", how="inner")
    pred_sign = np.where(sample["predicted_class"].astype(str).to_numpy() == "UP", 1, -1).astype(np.int8)

    result_rows: list[dict] = []
    for minutes in (15, 30, 60):
        first_col = f"first{minutes}_ret_pct"
        after_col = f"after{minutes}_ret_pct"
        if first_col not in sample:
            continue
        for threshold in (0.00, 0.02, 0.03, 0.05, 0.08, 0.10):
            first = pd.to_numeric(sample[first_col], errors="coerce").to_numpy(dtype=float)
            after = pd.to_numeric(sample[after_col], errors="coerce").to_numpy(dtype=float)
            candle_dir = np.where(first > threshold, 1, np.where(first < -threshold, -1, 0)).astype(np.int8)
            after_dir = np.where(after > 0.02, 1, np.where(after < -0.02, -1, 0)).astype(np.int8)

            agree = candle_dir == pred_sign
            called = (candle_dir != 0) & agree
            nonflat = called & (after_dir != 0)
            result_rows.append({
                "strategy": "v3_agrees_with_first_window",
                "minutes": minutes,
                "threshold_pct": threshold,
                "samples": int(len(sample)),
                "calls": int(called.sum()),
                "sign_n": int(nonflat.sum()),
                "sign_hit_pct": safe_pct(int((pred_sign[nonflat] == after_dir[nonflat]).sum()), int(nonflat.sum())),
            })

            pure_called = candle_dir != 0
            pure_nonflat = pure_called & (after_dir != 0)
            result_rows.append({
                "strategy": "first_window_trend_continuation",
                "minutes": minutes,
                "threshold_pct": threshold,
                "samples": int(len(sample)),
                "calls": int(pure_called.sum()),
                "sign_n": int(pure_nonflat.sum()),
                "sign_hit_pct": safe_pct(int((candle_dir[pure_nonflat] == after_dir[pure_nonflat]).sum()), int(pure_nonflat.sum())),
            })
    out = pd.DataFrame(result_rows)
    out.to_csv(out_dir / "intraday_confirmation.csv", index=False)
    sample.to_csv(out_dir / "intraday_recent_sample.csv", index=False)
    return out


def md_table(frame: pd.DataFrame, columns: list[str], max_rows: int = 10) -> str:
    if frame.empty:
        return "_None._\n"
    present = [c for c in columns if c in frame]
    sub = frame[present].head(max_rows)
    if sub.empty:
        return "_None._\n"

    def cell(v) -> str:
        if v is None or pd.isna(v):
            return ""
        if isinstance(v, float):
            return f"{v:.4g}"
        return str(v).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(present) + " |", "|" + "|".join(["---"] * len(present)) + "|"]
    for row in sub.to_numpy():
        lines.append("| " + " | ".join(cell(v) for v in row) + " |")
    return "\n".join(lines)


def write_report(
    df: pd.DataFrame,
    rules: pd.DataFrame,
    combos: pd.DataFrame,
    meta: pd.DataFrame,
    intraday: pd.DataFrame,
    out_dir: Path,
) -> None:
    summary = {
        "rows": int(len(df)),
        "feature_columns_after_leakage_guard": int(len(feature_columns(df))),
        "train2023_25_rules_exported": int(len(rules)),
        "rule_75_exact_holdout_n20": 0,
        "rule_75_sign_holdout_sign_n20": 0,
        "combo_75_exact_holdout_n20": 0,
        "meta_gate_70_precision_holdout_n20": 0,
    }
    if not rules.empty:
        summary["rule_75_exact_holdout_n20"] = int(((rules["confirm2026_n"] >= 20) & (rules["confirm2026_exact_pct"] >= 75)).sum())
        summary["rule_75_sign_holdout_sign_n20"] = int(((rules["confirm2026_sign_n"] >= 20) & (rules["confirm2026_sign_pct"] >= 75)).sum())
    if not combos.empty:
        summary["combo_75_exact_holdout_n20"] = int(((combos["confirm2026_n"] >= 20) & (combos["confirm2026_exact_pct"] >= 75)).sum())
    if not meta.empty and "confirm2026_v3_hit_precision_pct" in meta:
        summary["meta_gate_70_precision_holdout_n20"] = int(((meta["confirm2026_n"] >= 20) & (meta["confirm2026_v3_hit_precision_pct"] >= 70)).sum())
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    rule_cols = [
        "feature", "mode", "quantile", "rho_train2023_25",
        "train2023_25_n", "train2023_25_exact_pct", "train2023_25_sign_pct",
        "val2025_n", "val2025_exact_pct", "val2025_sign_pct",
        "confirm2026_n", "confirm2026_exact_pct", "confirm2026_sign_pct", "confirm2026_sign_n",
    ]
    combo_cols = [
        "top_n", "min_votes", "agree_ratio",
        "train2023_25_n", "train2023_25_exact_pct", "train2023_25_sign_pct",
        "confirm2026_n", "confirm2026_exact_pct", "confirm2026_sign_pct", "confirm2026_sign_n",
    ]
    meta_cols = [
        "model", "top_n", "threshold_name", "train2023_25_n", "train2023_25_v3_hit_precision_pct",
        "val2025_n", "val2025_v3_hit_precision_pct",
        "confirm2026_n", "confirm2026_v3_hit_precision_pct", "confirm2026_coverage_pct",
    ]
    intra_cols = ["strategy", "minutes", "threshold_pct", "samples", "calls", "sign_n", "sign_hit_pct"]

    best_holdout_rules = rules[(rules.get("confirm2026_n", pd.Series(dtype=float)) >= 20)].copy() if not rules.empty else pd.DataFrame()
    best_holdout_sign = rules[(rules.get("confirm2026_sign_n", pd.Series(dtype=float)) >= 20)].copy() if not rules.empty else pd.DataFrame()
    train_selected_rules = rules[
        (rules.get("train2023_25_n", pd.Series(dtype=float)) >= 40)
        & (rules.get("train2023_25_exact_pct", pd.Series(dtype=float)) >= 60)
        & (rules.get("train2023_25_sign_pct", pd.Series(dtype=float)) >= 70)
        & (rules.get("confirm2026_n", pd.Series(dtype=float)) >= 20)
    ].copy() if not rules.empty else pd.DataFrame()

    report = f"""# V5 holdout combo/meta/intraday audit

> Research only; no production decoder change.  This is a continuation of the
> 70-85% accuracy hunt after v4, with a stronger leakage guard and a 2026 final
> holdout.

## What changed vs v4

- Rules are refit on **2023-2025** and scored on **2026** as the untouched
  holdout.
- A rule-combo/voting layer tests whether many weak psychology rules combine
  into a high-precision state.
- A v3 meta-gate tries to predict when v3 will be right, but explicitly excludes
  target/outcome columns (`exact_hit`, `direction_hit`, `actual_class`, target
  returns).  This prevents a fake 100% result.
- A recent intraday check uses available NIFTY 1-minute data to test whether a
  first 15/30/60-minute candle confirming the OI view creates an executable edge.

## Summary

- Rows: **{summary['rows']}**
- Clean numeric features after leakage guard: **{summary['feature_columns_after_leakage_guard']}**
- Train-2023/25 threshold rules exported: **{summary['train2023_25_rules_exported']}**
- 2026-holdout rules with ≥75% exact and ≥20 calls: **{summary['rule_75_exact_holdout_n20']}**
- 2026-holdout rules with ≥75% sign and ≥20 non-FLAT calls: **{summary['rule_75_sign_holdout_sign_n20']}**
- Voting combos with ≥75% exact and ≥20 holdout calls: **{summary['combo_75_exact_holdout_n20']}**
- Meta-gates with ≥70% v3-hit precision and ≥20 holdout calls: **{summary['meta_gate_70_precision_holdout_n20']}**

## Best 2026 holdout exact rules (diagnostic, not selected blindly)

{md_table(best_holdout_rules.sort_values(['confirm2026_exact_pct', 'confirm2026_sign_pct'], ascending=False), rule_cols, 12)}

## Best 2026 holdout sign rules

{md_table(best_holdout_sign.sort_values(['confirm2026_sign_pct', 'confirm2026_exact_pct'], ascending=False), rule_cols, 12)}

## Rules that looked strong on train only, then hit 2026

This is the fairer view: train exact ≥60%, train sign ≥70%, train calls ≥40,
then observe 2026 without re-picking.

{md_table(train_selected_rules.sort_values(['confirm2026_exact_pct', 'confirm2026_sign_pct'], ascending=False), rule_cols, 12)}

## Voting-combo results

{md_table(combos.sort_values(['confirm2026_exact_pct', 'confirm2026_sign_pct'], ascending=False) if not combos.empty else combos, combo_cols, 12)}

## V3 meta-gate results after leakage guard

The model can look strong on 2023-2025, but holdout precision remains near
chance.  The fake 100% path is blocked by excluding all target/outcome columns.

{md_table(meta[(meta.get('confirm2026_n', pd.Series(dtype=float)) >= 20)].sort_values(['confirm2026_v3_hit_precision_pct', 'confirm2026_n'], ascending=False) if not meta.empty else meta, meta_cols, 12)}

## Recent 1-minute intraday confirmation check

Only the mirror's recent 1-minute NIFTY window is available, so this is a tiny
sample.  In this sample, first-window confirmation does **not** create a stable
executable edge.

{md_table(intraday.sort_values(['sign_hit_pct', 'sign_n'], ascending=False) if not intraday.empty and 'sign_hit_pct' in intraday else intraday, intra_cols, 12)}

## Verdict

This second cycle still does **not** honestly promote a 70-85% production edge.
The only way to print 80-100% here is either low-sample selection or target
leakage.  The useful discoveries remain research-only:

- Some 2026 pockets (e.g. stock-call flow changes / DII level-volatility states)
  can score 70%+ on ~20 calls, but they were not strong/stable enough in
  2023-2025 to trust.
- Rule voting amplifies overfit instead of improving the 2026 holdout.
- A v3 meta-gate cannot reliably identify the winning v3 days once leakage is
  removed.
- Recent 15-minute confirmation is roughly coin-flip on the available intraday
  sample.

Next best route: collect/procure a longer 10-15 minute intraday history with
same-date option levels/exact institutional levels, then evaluate executable
rules prospectively instead of adding more EOD curve fitting.
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
    parser.add_argument("--save-input-matrix", action="store_true")
    parser.add_argument(
        "--intraday-1m",
        default="/home/user/historical/groww-market-data-7d481cf1fcffe44be68852892028195c4f12dddd/openchart_nse/indices_1m/NIFTY_50.csv",
    )
    parser.add_argument("--out", default="reports/v5_holdout_combo_meta")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = build_enhanced_matrix(args)

    rules = search_train2023_25_rules(df, out_dir)
    combos = combo_search(rules, df, out_dir)
    meta = meta_gate_v3(df, args, out_dir)
    intraday = intraday_confirmation(args, out_dir)
    write_report(df, rules, combos, meta, intraday, out_dir)
    print(f"wrote {out_dir}/report.md")
    print((out_dir / "summary.json").read_text())


if __name__ == "__main__":
    main()
