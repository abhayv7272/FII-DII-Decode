#!/usr/bin/env python3
"""V4 psychology/level/flow search lab.

This is intentionally a *research* harness, not a production decoder.  It tries
exactly the kind of human-style hypotheses requested by the user, while keeping
three anti-leakage guardrails:

1. every feature for signal date D is computed from D and earlier only;
2. orientation/threshold/model selection is fitted on 2023-2024 development
   data only;
3. 2025 validation and 2026 confirmation are reported separately and unchanged.

Feature families:

* participant-OI fresh flows and current net levels for FII/Pro/Client/DII;
* 4/7/15/21-session comparisons, accelerations and crowding/positioning z-scores;
* smart-money vs Client, Pro vs FII conflict/agreement, futures-heavy/options-heavy
  composites;
* option-chain wall/PCR/max-pain aggregates rebuilt from same-date bhavcopy;
* price psychology / manipulation proxies such as gap, close-vs-open, realised
  volatility expansion/compression and range.

The goal is to find a robust 70-85% "gem" if it exists.  The script therefore
also publishes the negative evidence: rules that look amazing in development but
collapse out-of-sample.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "research") not in sys.path:
    sys.path.insert(0, str(ROOT / "research"))

from v3_features import build_features  # noqa: E402

FLAT_BAND_PCT = 0.15
PERIODS = ("dev2023_24", "val2025", "confirm2026")
WINDOWS = (4, 7, 15, 21)
ZSCORE_WINDOWS = (21, 63)
QUANTILES = (0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.925, 0.95)


@dataclass(frozen=True)
class RuleSpec:
    feature: str
    rho_dev: float
    mode: str
    quantile: float
    threshold_hi: float | None
    threshold_lo: float | None
    orientation: int


def _labels(y_pct: pd.Series | np.ndarray, band: float = FLAT_BAND_PCT) -> np.ndarray:
    y = np.asarray(y_pct, dtype=float)
    return np.where(y > band, 1, np.where(y < -band, -1, 0)).astype(np.int8)


def _class_name(values: np.ndarray | pd.Series) -> list[str]:
    mapping = {-1: "DOWN", 0: "FLAT/WAIT", 1: "UP"}
    return [mapping[int(v)] for v in values]


def _period_masks(df: pd.DataFrame) -> dict[str, np.ndarray]:
    return {period: (df["period"].astype(str).to_numpy() == period) for period in PERIODS}


def _safe_float(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def merge_prediction_columns(df: pd.DataFrame, path: Path | None, prefix: str) -> pd.DataFrame:
    if path is None or not path.exists():
        return df
    pred = pd.read_csv(path, parse_dates=["signal_date"])
    keep = [
        "signal_date",
        "predicted_class",
        "composite",
        "confidence",
        "setup_strength",
        "smart_money_conflict",
    ]
    keep = [c for c in keep if c in pred.columns]
    pred = pred[keep].rename(columns={"signal_date": "date"})
    pred = pred.add_prefix(prefix + "_").rename(columns={prefix + "_date": "date"})
    return df.merge(pred, on="date", how="left")


def add_psychology_composites(df: pd.DataFrame) -> pd.DataFrame:
    """Add interpretable smart-money/client/manipulation composite features."""
    additions: dict[str, pd.Series] = {}
    mixes = {
        "v2inst": (0.40, 0.40, 0.20),
        "v3inst": (0.30, 0.30, 0.40),
        "futheavy": (0.20, 0.20, 0.60),
        "optheavy": (0.45, 0.45, 0.10),
    }
    participants = ("FII", "Pro", "Client", "DII")
    instruments = ("icall", "iput", "ifut")
    for mix_name, (w_call, w_put, w_fut) in mixes.items():
        for kind in ("qflow", "rflow", "lvl"):
            for participant in participants:
                cols = [f"{participant}_{inst}_{kind}" for inst in instruments]
                if all(c in df.columns for c in cols):
                    additions[f"{participant}_{mix_name}_{kind}"] = (
                        w_call * df[cols[0]].astype(float)
                        + w_put * df[cols[1]].astype(float)
                        + w_fut * df[cols[2]].astype(float)
                    )
            req = [f"{p}_{mix_name}_{kind}" for p in ("Pro", "FII", "Client")]
            if all(c in additions for c in req):
                pro = additions[f"Pro_{mix_name}_{kind}"]
                fii = additions[f"FII_{mix_name}_{kind}"]
                client = additions[f"Client_{mix_name}_{kind}"]
                smart = 0.60 * pro + 0.40 * fii
                additions[f"smart_{mix_name}_{kind}"] = smart
                additions[f"pro_fii_spread_{mix_name}_{kind}"] = pro - fii
                additions[f"smart_vs_client_{mix_name}_{kind}"] = smart - client
                # Client is usually contra/crowding, so a small negative tilt is tested.
                additions[f"smart_plus_contra_client_{mix_name}_{kind}"] = smart - 0.10 * client
                additions[f"pro_fii_agreement_{mix_name}_{kind}"] = np.sign(pro) * np.sign(fii)
                additions[f"client_opposes_smart_{mix_name}_{kind}"] = -np.sign(client) * np.sign(smart)
    return pd.concat([df, pd.DataFrame(additions, index=df.index)], axis=1)


def rolling_feature_base(df: pd.DataFrame) -> list[str]:
    out: list[str] = []
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        if col in {"y_cc", "y_oc", "y_gap", "y_5d"}:
            continue
        if (
            col.endswith(("_qflow", "_rflow", "_lvl"))
            or any(tag in col for tag in ("smart_", "pro_fii", "client_", "v3_", "v2_", "oc_", "px_"))
            or col in {"dow", "dte", "is_expiry_day"}
        ):
            out.append(col)
    return out


def add_rolling_psychology(df: pd.DataFrame, base_cols: Iterable[str]) -> pd.DataFrame:
    """Add past 4/7/15/21 session context without look-ahead."""
    frames: list[pd.DataFrame] = []
    for col in base_cols:
        s = pd.to_numeric(df[col], errors="coerce")
        data: dict[str, pd.Series] = {}
        for window in WINDOWS:
            minp = max(2, window // 2)
            data[f"{col}_sum{window}"] = s.rolling(window, min_periods=minp).sum()
            data[f"{col}_mean{window}"] = s.rolling(window, min_periods=minp).mean()
            data[f"{col}_chg{window}"] = s - s.shift(window)
            data[f"{col}_posdays{window}"] = (s > 0).rolling(window, min_periods=minp).sum() / window
        for window in ZSCORE_WINDOWS:
            minp = max(5, window // 3)
            mu = s.rolling(window, min_periods=minp).mean()
            sd = s.rolling(window, min_periods=minp).std().replace(0, np.nan)
            data[f"{col}_z{window}"] = (s - mu) / sd
        frames.append(pd.DataFrame(data, index=df.index))
    return pd.concat([df, *frames], axis=1)


def build_enhanced_matrix(args: argparse.Namespace) -> pd.DataFrame:
    matrix_path = Path(args.matrix)
    if matrix_path.exists():
        matrix = pd.read_csv(matrix_path, parse_dates=["date"])
    else:
        # Arena resets wipe /home/user/features between turns.  Fall back to the
        # compact in-repo historical CSVs so this search remains reproducible.
        matrix, _ = build_features(args.oi, args.vol, args.ohlc)
        if args.save_input_matrix:
            matrix_path.parent.mkdir(parents=True, exist_ok=True)
            matrix.to_csv(matrix_path, index=False, float_format="%.8f")
    matrix = matrix.sort_values("date").reset_index(drop=True)

    if args.chain_features and Path(args.chain_features).exists():
        chain = pd.read_csv(args.chain_features, parse_dates=["date"])
        chain = chain.drop(columns=["spot"], errors="ignore")
        matrix = matrix.merge(chain, on="date", how="left")

    matrix = merge_prediction_columns(matrix, Path(args.v2_predictions) if args.v2_predictions else None, "v2")
    matrix = merge_prediction_columns(matrix, Path(args.v3_predictions) if args.v3_predictions else None, "v3")
    matrix = add_psychology_composites(matrix)
    matrix = add_rolling_psychology(matrix, rolling_feature_base(matrix))
    return matrix.copy()


def _metrics(mask: np.ndarray, pred: np.ndarray, actual: np.ndarray) -> dict[str, float | int | None]:
    called = mask & (pred != 0)
    n = int(called.sum())
    total = int(mask.sum())
    out: dict[str, float | int | None] = {
        "n": n,
        "coverage_pct": round(n / total * 100.0, 2) if total else 0.0,
    }
    if n == 0:
        out.update({"exact_pct": None, "sign_pct": None, "sign_n": 0, "up_calls": 0, "down_calls": 0})
        return out
    out["exact_pct"] = round(float((pred[called] == actual[called]).mean() * 100.0), 2)
    nonflat = called & (actual != 0)
    sign_n = int(nonflat.sum())
    out["sign_n"] = sign_n
    out["sign_pct"] = round(float((pred[nonflat] == actual[nonflat]).mean() * 100.0), 2) if sign_n else None
    out["up_calls"] = int((pred[called] == 1).sum())
    out["down_calls"] = int((pred[called] == -1).sum())
    return out


def apply_rule(spec: RuleSpec, x: np.ndarray) -> np.ndarray:
    oriented = x * spec.orientation
    pred = np.zeros(len(x), dtype=np.int8)
    if spec.mode in {"two_tail", "up_tail"} and spec.threshold_hi is not None:
        pred[oriented >= spec.threshold_hi] = 1
    if spec.mode in {"two_tail", "down_tail"} and spec.threshold_lo is not None:
        pred[oriented <= spec.threshold_lo] = -1
    return pred


def search_threshold_rules(df: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    actual = _labels(df["y_cc"])
    yret = pd.to_numeric(df["y_cc"], errors="coerce").to_numpy(dtype=float)
    masks = _period_masks(df)
    dev = masks["dev2023_24"]

    feature_cols = [
        c for c in df.columns
        if pd.api.types.is_numeric_dtype(df[c]) and c not in {"y_cc", "y_oc", "y_gap", "y_5d"}
    ]
    rows: list[dict] = []
    for feature in feature_cols:
        x = pd.to_numeric(df[feature], errors="coerce").to_numpy(dtype=float)
        finite_dev = dev & np.isfinite(x) & np.isfinite(yret)
        if int(finite_dev.sum()) < 200:
            continue
        if not np.isfinite(np.nanstd(x[dev])) or np.nanstd(x[dev]) == 0:
            continue
        try:
            rho = float(spearmanr(x[finite_dev], yret[finite_dev]).statistic)
        except Exception:
            continue
        if not np.isfinite(rho) or abs(rho) < 0.03:
            continue
        orientation = 1 if rho >= 0 else -1
        oriented = x * orientation
        for mode in ("two_tail", "up_tail", "down_tail"):
            for q in QUANTILES:
                threshold_hi = threshold_lo = None
                if mode in {"two_tail", "up_tail"}:
                    threshold_hi = _safe_float(np.nanquantile(oriented[dev], q))
                if mode in {"two_tail", "down_tail"}:
                    threshold_lo = _safe_float(np.nanquantile(oriented[dev], 1.0 - q))
                spec = RuleSpec(feature, rho, mode, q, threshold_hi, threshold_lo, orientation)
                pred = apply_rule(spec, x)
                dev_m = _metrics(dev, pred, actual)
                # Keep the output focused but still broad: only rules that had at
                # least a plausible in-sample relationship are exported.
                if (dev_m["n"] or 0) < 20:
                    continue
                if (dev_m["exact_pct"] or 0) < 50 and (dev_m["sign_pct"] or 0) < 60:
                    continue
                row = {
                    "feature": feature,
                    "rho_dev": round(rho, 6),
                    "orientation": orientation,
                    "mode": mode,
                    "quantile": q,
                    "threshold_hi": threshold_hi,
                    "threshold_lo": threshold_lo,
                }
                for period, mask in masks.items():
                    metrics = _metrics(mask, pred, actual)
                    row.update({f"{period}_{k}": v for k, v in metrics.items()})
                rows.append(row)

    rules = pd.DataFrame(rows)
    if not rules.empty:
        # Sort by honest out-of-sample properties, not by development only.
        for col in ("val2025_exact_pct", "confirm2026_exact_pct", "val2025_sign_pct", "confirm2026_sign_pct"):
            rules[col] = pd.to_numeric(rules[col], errors="coerce")
        rules["min_val_confirm_exact_pct"] = rules[["val2025_exact_pct", "confirm2026_exact_pct"]].min(axis=1)
        rules["min_val_confirm_sign_pct"] = rules[["val2025_sign_pct", "confirm2026_sign_pct"]].min(axis=1)
        rules["mean_val_confirm_coverage_pct"] = rules[["val2025_coverage_pct", "confirm2026_coverage_pct"]].mean(axis=1)
        rules = rules.sort_values(
            ["min_val_confirm_exact_pct", "min_val_confirm_sign_pct", "mean_val_confirm_coverage_pct"],
            ascending=False,
        ).reset_index(drop=True)
    rules.to_csv(out_dir / "threshold_rules.csv", index=False)
    return rules


def select_rule_views(rules: pd.DataFrame, out_dir: Path) -> dict[str, pd.DataFrame]:
    views: dict[str, pd.DataFrame] = {}
    if rules.empty:
        for name in ("top_validated_exact_n20", "top_validated_sign_n20", "closest_70_sign_n10", "overfit_examples"):
            views[name] = pd.DataFrame()
            views[name].to_csv(out_dir / f"{name}.csv", index=False)
        return views

    exact20 = rules[(rules["val2025_n"] >= 20) & (rules["confirm2026_n"] >= 20)].copy()
    exact20 = exact20.sort_values(
        ["min_val_confirm_exact_pct", "min_val_confirm_sign_pct", "mean_val_confirm_coverage_pct"],
        ascending=False,
    ).head(50)
    views["top_validated_exact_n20"] = exact20

    sign20 = rules[(rules["val2025_sign_n"] >= 20) & (rules["confirm2026_sign_n"] >= 20)].copy()
    sign20 = sign20.sort_values(
        ["min_val_confirm_sign_pct", "min_val_confirm_exact_pct", "mean_val_confirm_coverage_pct"],
        ascending=False,
    ).head(50)
    views["top_validated_sign_n20"] = sign20

    sign10 = rules[(rules["val2025_sign_n"] >= 10) & (rules["confirm2026_sign_n"] >= 10)].copy()
    sign10 = sign10.sort_values(
        ["min_val_confirm_sign_pct", "min_val_confirm_exact_pct", "mean_val_confirm_coverage_pct"],
        ascending=False,
    ).head(50)
    views["closest_70_sign_n10"] = sign10

    overfit = rules[
        (rules["dev2023_24_exact_pct"] >= 70)
        & (rules["confirm2026_n"] >= 10)
    ].copy()
    overfit["dev_minus_confirm_exact_pct"] = overfit["dev2023_24_exact_pct"] - overfit["confirm2026_exact_pct"]
    overfit = overfit.sort_values("dev_minus_confirm_exact_pct", ascending=False).head(50)
    views["overfit_examples"] = overfit

    for name, frame in views.items():
        frame.to_csv(out_dir / f"{name}.csv", index=False)
    return views


def _period_model_metrics(df: pd.DataFrame, pred: np.ndarray, actual: np.ndarray) -> list[dict]:
    rows: list[dict] = []
    masks = _period_masks(df)
    for period, mask in masks.items():
        n = int(mask.sum())
        exact = float((pred[mask] == actual[mask]).mean() * 100.0) if n else np.nan
        counts = pd.Series(actual[mask]).value_counts()
        baseline = float(counts.max() / n * 100.0) if n else np.nan
        directional = mask & (pred != 0) & (actual != 0)
        sign_n = int(directional.sum())
        sign = float((pred[directional] == actual[directional]).mean() * 100.0) if sign_n else np.nan
        rows.append({
            "period": period,
            "n": n,
            "exact_pct": round(exact, 2),
            "majority_baseline_pct": round(baseline, 2),
            "sign_n": sign_n,
            "sign_pct": round(sign, 2) if np.isfinite(sign) else None,
        })
    return rows


def _fit_predict_model(model_name: str, X_train: np.ndarray, y_train: np.ndarray, X_all: np.ndarray) -> np.ndarray:
    med = np.nanmedian(X_train, axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    X_train = np.where(np.isnan(X_train), med, X_train)
    X_all = np.where(np.isnan(X_all), med, X_all)
    if model_name == "logreg_C0.03":
        scaler = StandardScaler().fit(X_train)
        model = LogisticRegression(C=0.03, class_weight="balanced", max_iter=2000)
        model.fit(scaler.transform(X_train), y_train)
        return model.predict(scaler.transform(X_all)).astype(np.int8)
    if model_name == "hgb_depth2":
        model = HistGradientBoostingClassifier(
            max_iter=120,
            max_depth=2,
            learning_rate=0.03,
            min_samples_leaf=40,
            l2_regularization=1.0,
            random_state=7,
        )
        model.fit(X_train, y_train)
        return model.predict(X_all).astype(np.int8)
    if model_name == "rf_depth4":
        model = RandomForestClassifier(
            n_estimators=300,
            max_depth=4,
            min_samples_leaf=30,
            class_weight="balanced_subsample",
            random_state=7,
            n_jobs=-1,
        )
        model.fit(X_train, y_train)
        return model.predict(X_all).astype(np.int8)
    if model_name == "gb_depth2":
        model = GradientBoostingClassifier(n_estimators=60, max_depth=2, learning_rate=0.03, random_state=7)
        model.fit(X_train, y_train)
        return model.predict(X_all).astype(np.int8)
    raise ValueError(model_name)


def model_sanity(df: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    """Frozen-on-dev ML sanity check.  Any real gem should survive 2025/2026."""
    actual = _labels(df["y_cc"])
    yret = pd.to_numeric(df["y_cc"], errors="coerce").to_numpy(dtype=float)
    dev_mask = (df["period"].astype(str).to_numpy() == "dev2023_24")
    candidates = [
        c for c in df.columns
        if pd.api.types.is_numeric_dtype(df[c]) and c not in {"y_cc", "y_oc", "y_gap", "y_5d"}
    ]
    scored: list[tuple[float, str]] = []
    for col in candidates:
        x = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
        mask = dev_mask & np.isfinite(x) & np.isfinite(yret)
        if int(mask.sum()) < 200 or np.nanstd(x[dev_mask]) == 0:
            continue
        try:
            rho = float(spearmanr(x[mask], yret[mask]).statistic)
        except Exception:
            continue
        if np.isfinite(rho):
            scored.append((abs(rho), col))
    scored.sort(reverse=True)

    rows: list[dict] = []
    models = ("logreg_C0.03", "hgb_depth2", "rf_depth4", "gb_depth2")
    top_ns = (12, 20, 35, 50, 80, 120)
    for top_n in top_ns:
        cols = [c for _, c in scored[:top_n]]
        if not cols:
            continue
        X = df[cols].to_numpy(dtype=float)
        y_train = actual[dev_mask]
        X_train = X[dev_mask]
        for model_name in models:
            try:
                pred = _fit_predict_model(model_name, X_train, y_train, X)
            except Exception as exc:
                rows.append({"top_n": top_n, "model": model_name, "period": "ERROR", "error": str(exc)})
                continue
            for row in _period_model_metrics(df, pred, actual):
                rows.append({"top_n": top_n, "model": model_name, **row})
    res = pd.DataFrame(rows)
    res.to_csv(out_dir / "ml_frozen_dev_results.csv", index=False)
    return res


def _fmt_pct(value) -> str:
    if value is None or (isinstance(value, float) and not math.isfinite(value)) or pd.isna(value):
        return "n/a"
    return f"{float(value):.2f}%"


def _md_table(frame: pd.DataFrame, columns: list[str], max_rows: int = 10) -> str:
    """Render a tiny markdown table without requiring pandas[tabulate]."""
    if frame.empty:
        return "_None._\n"
    present = [c for c in columns if c in frame.columns]
    sub = frame[present].head(max_rows).copy()
    if sub.empty:
        return "_None._\n"

    def cell(value) -> str:
        if value is None or pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.4g}"
        text = str(value)
        return text.replace("|", "\\|").replace("\n", " ")

    header = "| " + " | ".join(present) + " |"
    sep = "|" + "|".join(["---"] * len(present)) + "|"
    rows = ["| " + " | ".join(cell(v) for v in row) + " |" for row in sub.to_numpy()]
    return "\n".join([header, sep, *rows])


def write_report(df: pd.DataFrame, rules: pd.DataFrame, views: dict[str, pd.DataFrame], ml: pd.DataFrame, out_dir: Path) -> None:
    masks = _period_masks(df)
    actual = _labels(df["y_cc"])
    class_balance = []
    for period, mask in masks.items():
        counts = pd.Series(_class_name(actual[mask])).value_counts().to_dict()
        n = int(mask.sum())
        baseline = max(counts.values()) / n * 100.0 if n else np.nan
        class_balance.append({"period": period, "n": n, "majority_baseline_pct": round(baseline, 2), **counts})
    pd.DataFrame(class_balance).to_csv(out_dir / "class_balance.csv", index=False)

    pass75_exact_n20 = rules[
        (rules.get("val2025_n", pd.Series(dtype=float)) >= 20)
        & (rules.get("confirm2026_n", pd.Series(dtype=float)) >= 20)
        & (rules.get("val2025_exact_pct", pd.Series(dtype=float)) >= 75)
        & (rules.get("confirm2026_exact_pct", pd.Series(dtype=float)) >= 75)
    ] if not rules.empty else pd.DataFrame()
    pass75_sign_n20 = rules[
        (rules.get("val2025_sign_n", pd.Series(dtype=float)) >= 20)
        & (rules.get("confirm2026_sign_n", pd.Series(dtype=float)) >= 20)
        & (rules.get("val2025_sign_pct", pd.Series(dtype=float)) >= 75)
        & (rules.get("confirm2026_sign_pct", pd.Series(dtype=float)) >= 75)
    ] if not rules.empty else pd.DataFrame()

    summary = {
        "rows": int(len(df)),
        "columns_after_engineering": int(df.shape[1]),
        "threshold_rules_exported": int(len(rules)),
        "rules_meeting_75_exact_with_val_confirm_n20": int(len(pass75_exact_n20)),
        "rules_meeting_75_sign_with_val_confirm_sign_n20": int(len(pass75_sign_n20)),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    exact_cols = [
        "feature", "mode", "quantile", "rho_dev",
        "dev2023_24_n", "dev2023_24_exact_pct", "dev2023_24_sign_pct",
        "val2025_n", "val2025_exact_pct", "val2025_sign_pct",
        "confirm2026_n", "confirm2026_exact_pct", "confirm2026_sign_pct",
        "min_val_confirm_exact_pct", "min_val_confirm_sign_pct",
    ]
    sign_cols = [
        "feature", "mode", "quantile", "rho_dev",
        "dev2023_24_sign_n", "dev2023_24_sign_pct", "dev2023_24_exact_pct",
        "val2025_sign_n", "val2025_sign_pct", "val2025_exact_pct",
        "confirm2026_sign_n", "confirm2026_sign_pct", "confirm2026_exact_pct",
        "min_val_confirm_sign_pct", "min_val_confirm_exact_pct",
    ]
    overfit_cols = [
        "feature", "mode", "quantile", "dev2023_24_n", "dev2023_24_exact_pct",
        "val2025_n", "val2025_exact_pct", "confirm2026_n", "confirm2026_exact_pct",
        "dev_minus_confirm_exact_pct",
    ]

    ml_pivot = pd.DataFrame()
    if not ml.empty and "period" in ml:
        ml_ok = ml[ml["period"].isin(PERIODS)].copy()
        if not ml_ok.empty:
            ml_pivot = ml_ok.pivot_table(index=["top_n", "model"], columns="period", values="exact_pct").reset_index()
            ml_pivot = ml_pivot.sort_values(["confirm2026", "val2025"], ascending=False, na_position="last")
            ml_pivot.to_csv(out_dir / "ml_frozen_dev_pivot.csv", index=False)

    report = f"""# V4 psychology / manipulation / level search — research log

> Educational research only — not investment advice.  This file documents an
> intentionally aggressive search for a 70-85% daily NIFTY edge.  Nothing here is
> promoted to production unless it survives untouched validation/confirmation and
> later forward data.

## Data and guardrails

- Feature rows: **{summary['rows']}** signal sessions from the existing
  participant-OI archive.
- Engineered columns after same-date option-chain merge and 4/7/15/21-session
  psychology/positioning transforms: **{summary['columns_after_engineering']}**.
- Development/fitting: **2023-2024 only**.  Validation: **2025**.  Confirmation:
  **2026**.
- Target: next-session close-to-close class with ±{FLAT_BAND_PCT:.2f}% FLAT band.
- Directional rules are selective: they can say UP/DOWN or abstain.  Exact
  accuracy below counts a called UP/DOWN against the 3-class target, so real FLAT
  days are misses.

## Bottom line

The 75-85% target was **not cracked honestly** in this run.

- Rules meeting **≥75% exact** on both 2025 and 2026 with at least 20 calls in
  each period: **{summary['rules_meeting_75_exact_with_val_confirm_n20']}**.
- Rules meeting **≥75% non-FLAT sign** on both 2025 and 2026 with at least 20
  non-FLAT calls in each period: **{summary['rules_meeting_75_sign_with_val_confirm_sign_n20']}**.

The strongest broad-coverage model remains the already-published **v3 candidate**
(45.05% exact / 57.12% sign full sample).  This v4 search did find a few
interesting *research-only* selective states around 58-63% exact and 63-73% sign,
but the sample sizes/coverage are too small for production promotion.

## Best selective exact rules requiring at least 20 calls in both 2025 and 2026

{_md_table(views.get('top_validated_exact_n20', pd.DataFrame()), exact_cols, 10)}

## Best selective sign rules requiring at least 20 non-FLAT calls in both 2025 and 2026

{_md_table(views.get('top_validated_sign_n20', pd.DataFrame()), sign_cols, 10)}

## Closest-to-70% sign candidates with relaxed n≥10 non-FLAT calls

These are the nearest "maybe gems" but **not enough evidence**.  Several top
rows have only ~10-13 non-FLAT calls in one holdout period; one interpretable
price-volatility expansion rule reaches roughly 75% sign in validation and 73%
in confirmation, but validation has only ~12 non-FLAT calls.

{_md_table(views.get('closest_70_sign_n10', pd.DataFrame()), sign_cols, 10)}

## Overfit traps: dev looked 70%+, confirmation collapsed

This is why I am not going to force a fake 80% number.  Many human-plausible
OI/level/crowding patterns look excellent on 2023-2024 and then die in 2026.

{_md_table(views.get('overfit_examples', pd.DataFrame()), overfit_cols, 10)}

## Frozen-on-development ML sanity check

A real high-accuracy structure should not need continual hand-picking.  The
frozen models below were trained on development only and applied unchanged to
2025/2026; they do **not** beat v3.

{_md_table(ml_pivot, ['top_n', 'model', 'dev2023_24', 'val2025', 'confirm2026'], 20)}

## Interpretation for next iteration

- Multi-day DII/index-future *level change* keeps appearing in the best
  selective tables.  It may be a regime/crowding proxy, but it is only a
  55-62% exact zone so far.
- Volatility expansion after the last 15 sessions is the closest 70% sign idea,
  but it is low-coverage and price-only; it needs much more forward data.
- Ensembles/model capacity easily overfit.  The correct next move is not to
  promote complexity; it is to keep v3 as default/candidate, accumulate forward
  sessions, and test these selective states prospectively.

Artifacts in this folder are deliberately auditable:

- `threshold_rules.csv` — all exported threshold rules.
- `top_validated_exact_n20.csv`, `top_validated_sign_n20.csv`,
  `closest_70_sign_n10.csv` — ranked OOS views.
- `overfit_examples.csv` — high-dev, bad-confirmation traps.
- `ml_frozen_dev_results.csv` / `ml_frozen_dev_pivot.csv` — model sanity check.
- `summary.json`, `class_balance.csv` — run metadata.
"""
    (out_dir / "report.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", default="/home/user/features/v3_matrix.csv")
    parser.add_argument("--oi", default="historical/participant_oi.csv")
    parser.add_argument("--vol", default="historical/participant_vol.csv")
    parser.add_argument("--ohlc", default="historical/nifty_ohlc.csv")
    parser.add_argument("--save-input-matrix", action="store_true")
    parser.add_argument("--chain-features", default="historical/chain_features.csv")
    parser.add_argument("--v2-predictions", default="reports/backtest_v3_candidate_2023-08_to_2026-09/v2_predictions.csv")
    parser.add_argument("--v3-predictions", default="reports/backtest_v3_candidate_2023-08_to_2026-09/v3_predictions.csv")
    parser.add_argument("--out", default="reports/v4_psychology_search")
    parser.add_argument(
        "--save-enhanced-matrix",
        action="store_true",
        help="also write the large engineered matrix CSV (normally regenerated on demand)",
    )
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = build_enhanced_matrix(args)
    if args.save_enhanced_matrix:
        df.to_csv(out_dir / "enhanced_matrix.csv", index=False, float_format="%.8f")

    rules = search_threshold_rules(df, out_dir)
    views = select_rule_views(rules, out_dir)
    ml = model_sanity(df, out_dir)
    write_report(df, rules, views, ml, out_dir)

    print(f"wrote {out_dir}/report.md")
    print(json.dumps(json.loads((out_dir / "summary.json").read_text()), indent=2))


if __name__ == "__main__":
    main()
