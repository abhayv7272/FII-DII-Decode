from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix

LABELS = np.array(["DOWN", "FLAT", "UP"])

@dataclass
class ModelResult:
    model: object
    columns: list[str]
    metrics: dict
    validation: pd.DataFrame
    confidence_gate: float


def _pipeline(seed=42):
    linear = Pipeline([("imp", SimpleImputer(strategy="median")), ("scale", StandardScaler()),
                       ("m", LogisticRegression(max_iter=1500, class_weight="balanced", C=.5, random_state=seed))])
    rf = Pipeline([("imp", SimpleImputer(strategy="median")),
                   ("m", RandomForestClassifier(n_estimators=350, min_samples_leaf=8, max_features=.7,
                                                class_weight="balanced_subsample", random_state=seed, n_jobs=-1))])
    hist = Pipeline([("imp", SimpleImputer(strategy="median")),
                     ("m", HistGradientBoostingClassifier(max_iter=180, learning_rate=.04,
                                                          max_leaf_nodes=12, l2_regularization=2, random_state=seed))])
    return VotingClassifier([("linear", linear), ("rf", rf), ("hist", hist)], voting="soft", weights=[1, 2, 1])


def _gate_for_target(y_true, pred, conf, target_precision=.80, min_signals=20):
    """Choose threshold only on validation. Never promises future accuracy."""
    candidates = np.arange(.40, .91, .01)
    best = None
    for g in candidates:
        mask = conf >= g
        n = int(mask.sum())
        if n < min_signals:
            continue
        precision = float((pred[mask] == y_true[mask]).mean())
        coverage = float(mask.mean())
        if precision >= target_precision:
            score = coverage
            if best is None or score > best[0]:
                best = (score, float(g), precision, n)
    return best[1] if best else .65


def train_walk_forward(features: pd.DataFrame, y: pd.Series, target_precision=.80) -> ModelResult:
    data = features.join(y).dropna(subset=["target"])
    if len(data) < 300:
        raise ValueError("At least 300 completed sessions are required.")
    cols = list(features.columns)
    n = len(data); split = int(n * .80)
    train, val = data.iloc[:split], data.iloc[split:]
    model = _pipeline(); model.fit(train[cols], train.target.astype(int))
    proba = model.predict_proba(val[cols]); pred = model.classes_[proba.argmax(axis=1)]
    conf = proba.max(axis=1)
    gate = _gate_for_target(val.target.to_numpy(int), pred, conf, target_precision,
                            min_signals=max(10, len(val)//20))
    selected = conf >= gate
    val_out = pd.DataFrame({"actual": LABELS[val.target.to_numpy(int)], "prediction": LABELS[pred],
                            "confidence": conf, "selected": selected}, index=val.index)
    metrics = {
        "validation_sessions": len(val),
        "all_accuracy": accuracy_score(val.target, pred),
        "balanced_accuracy": balanced_accuracy_score(val.target, pred),
        "selected_accuracy": accuracy_score(val.target[selected], pred[selected]) if selected.any() else np.nan,
        "coverage": float(selected.mean()),
        "selected_signals": int(selected.sum()),
        "confusion_matrix": confusion_matrix(val.target, pred, labels=[0,1,2]).tolist(),
    }
    # Refit frozen architecture on all available labeled rows after honest validation metrics.
    final = _pipeline(); final.fit(data[cols], data.target.astype(int))
    return ModelResult(final, cols, metrics, val_out, gate)


def predict_latest(result: ModelResult, feature_row: pd.DataFrame) -> dict:
    p = result.model.predict_proba(feature_row[result.columns])[0]
    aligned = np.zeros(3)
    for cls, prob in zip(result.model.classes_, p): aligned[int(cls)] = prob
    idx = int(aligned.argmax()); conf = float(aligned[idx])
    return {"label": LABELS[idx], "confidence": conf, "probabilities": dict(zip(LABELS, aligned)),
            "actionable": conf >= result.confidence_gate}


def recursive_week_scenarios(last_close: float, daily_probs: dict, atr_pct: float, days=5):
    """Probability/range scenarios, not fake recursively generated OHLC forecasts."""
    exp_sign = daily_probs["UP"] - daily_probs["DOWN"]
    rows=[]
    for i in range(1, days+1):
        center = last_close * (1 + exp_sign * atr_pct * .35 * np.sqrt(i))
        width = last_close * atr_pct * np.sqrt(i)
        rows.append({"session": i, "expected_center": center, "lower_risk_band": center-width,
                     "upper_risk_band": center+width})
    return pd.DataFrame(rows)
