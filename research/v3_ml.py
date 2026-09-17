#!/usr/bin/env python3
"""Stage-4 deep dive: fitted models under two honest protocols.

Protocol W (walk-forward): expanding window, refit every 21 sessions, burn-in
252; predictions for date D come only from fits that saw data < D.

Protocol F (frozen-on-dev): fit once on dev2023_24; apply unchanged to 2025 and
2026 (mirrors the hand-grid protocol so capacities can be compared).

Models: multinomial logistic (L2, time-series CV on train), ridge regression on
next-day return, and a small histogram gradient boosting. All hyperparameters
are chosen inside the training window only (logistic C via blocked CV, GBT
fixed conservative config).

Feature blocks (prefix filters over the master matrix):
  F1 participants x index instruments quality flows (12 cols)
  F2 F1 + fresh-only index flows + index flow sums (sum2,3,5)
  F3 F2 + stock-instrument flows (24 more)
  F4 F3 + price context (momentum, vol, range, gap/oc)
  F5 F4 + participant volume (dvol) features

The daily option-chain features are appended by stage-5 when built.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import accuracy_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

FLAT = 0.15
PERIODS = ("dev2023_24", "val2025", "confirm2026")


def feature_blocks(df: pd.DataFrame) -> dict[str, list[str]]:
    idx_q = [f"{p}_{i}_qflow" for p in ("Pro", "FII", "Client") for i in ("icall", "iput", "ifut")]
    idx_r = [f"{p}_{i}_rflow" for p in ("Pro", "FII", "Client") for i in ("icall", "iput", "ifut")]
    idx_sums = [c for c in df.columns if c.endswith(("_sum2", "_sum3", "_sum5"))
                and any(c.startswith(f"{p}_{i}") for p in ("Pro", "FII", "Client")
                        for i in ("icall", "iput", "ifut"))]
    stk_q = [f"{p}_{i}_qflow" for p in ("Pro", "FII", "Client") for i in ("sfut", "scall", "sput")]
    stk_q += [f"{p}_{i}_qflow" for p in ("DII",) for i in ("icall", "iput", "ifut", "sfut")]
    levels = [c for c in df.columns if c.endswith("_lvl")]
    price = [c for c in df.columns if c.startswith("px_")]
    vols = [c for c in df.columns if c.endswith("_dvol")]
    misc = ["dow", "dte", "is_expiry_day"] + [c for c in df.columns if c.startswith("mkt_")]
    blocks = {
        "F1_index_q": idx_q,
        "F2_+fresh+sums": idx_q + idx_r + idx_sums,
        "F3_+stock": idx_q + idx_r + idx_sums + stk_q + levels,
        "F4_+price": idx_q + idx_r + idx_sums + stk_q + levels + price + misc,
        "F5_+vol": idx_q + idx_r + idx_sums + stk_q + levels + price + misc + vols,
    }
    return {k: [c for c in v if c in df.columns] for k, v in blocks.items()}


def labels(df: pd.DataFrame, target="y_cc") -> pd.Series:
    y = df[target]
    return y.map(lambda v: "UP" if v > FLAT else ("DOWN" if v < -FLAT else "FLAT"))


def _impute(X_tr, X_te):
    med = np.nanmedian(X_tr, axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    return (np.where(np.isnan(X_tr), med, X_tr),
            np.where(np.isnan(X_te), med, X_te))


def cv_best_C(X, y, Cs=(0.01, 0.1, 1.0)):
    tscv = TimeSeriesSplit(n_splits=4)
    best, best_score = Cs[0], -1
    for C in Cs:
        scores = []
        for tr, te in tscv.split(X):
            Xtr, Xte = _impute(X[tr], X[te])
            sc = StandardScaler().fit(Xtr)
            clf = LogisticRegression(C=C, max_iter=2000, class_weight="balanced")
            clf.fit(sc.transform(Xtr), y[tr])
            scores.append(accuracy_score(y[te], clf.predict(sc.transform(Xte))))
        if np.mean(scores) > best_score:
            best, best_score = C, np.mean(scores)
    return best


def fit_predict_logreg(X_tr, y_tr, X_te, C_mode="cv"):
    X_tr, X_te = _impute(X_tr, X_te)
    if len(np.unique(y_tr)) < 3:
        return np.repeat(np.unique(y_tr)[0], len(X_te))
    C = cv_best_C(X_tr, y_tr) if C_mode == "cv" else 0.1
    sc = StandardScaler().fit(X_tr)
    clf = LogisticRegression(C=C, max_iter=2000, class_weight="balanced")
    clf.fit(sc.transform(X_tr), y_tr)
    return clf.predict(sc.transform(X_te))


def fit_predict_gbt(X_tr, y_tr, X_te):
    if len(np.unique(y_tr)) < 3:
        return np.repeat(np.unique(y_tr)[0], len(X_te))
    clf = HistGradientBoostingClassifier(max_iter=120, max_depth=3, learning_rate=0.05,
                                         min_samples_leaf=30, l2_regularization=1.0, random_state=7)
    clf.fit(X_tr, y_tr)
    return clf.predict(X_te)


def fit_predict_ridge(X_tr, y_tr, X_te, band=FLAT):
    X_tr, X_te = _impute(X_tr, X_te)
    sc = StandardScaler().fit(X_tr)
    reg = Ridge(alpha=10.0)
    reg.fit(sc.transform(X_tr), y_tr)
    raw = reg.predict(sc.transform(X_te))
    return np.where(raw > band / 8, "UP", np.where(raw < -band / 8, "DOWN", "FLAT")), raw


def metrics_frame(df, pred_col):
    rows = []
    actual = labels(df)
    for p in PERIODS:
        mask = df["period"] == p
        sub_a, sub_p = actual[mask], df.loc[mask, pred_col]
        n = len(sub_a)
        exact = (sub_a == sub_p).mean() * 100
        base = sub_a.value_counts().max() / n * 100
        dm = sub_p.isin(["UP", "DOWN"])
        cov = dm.mean() * 100
        nf = dm & sub_a.isin(["UP", "DOWN"])
        sign = (sub_p[nf] == sub_a[nf]).mean() * 100 if nf.sum() else np.nan
        rows.append({"period": p, "n": n, "exact": round(exact, 2), "baseline": round(base, 2),
                     "cov": round(cov, 2), "sign": round(sign, 2) if nf.sum() else None,
                     "sign_n": int(nf.sum())})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", default="/home/user/features/v3_matrix.csv")
    parser.add_argument("--out", default="reports/v3_deep_dive")
    args = parser.parse_args()
    df = pd.read_csv(args.matrix, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

    blocks = feature_blocks(df)
    results = []

    # ---------------- Protocol W: walk-forward ----------------------------------
    BURN_IN, REFIT = 252, 21
    models = ("logreg", "gbt", "ridge")
    for bname, cols in blocks.items():
        X_all = df[cols].to_numpy(dtype=float)
        y_cls = labels(df).to_numpy()
        y_reg = df["y_cc"].to_numpy(dtype=float)
        preds = {m: np.full(len(df), "", dtype=object) for m in models}
        for start in range(BURN_IN, len(df), REFIT):
            tr = slice(0, start)
            te = slice(start, min(start + REFIT, len(df)))
            if not np.isfinite(X_all[tr]).all():
                pass
            for m in models:
                if m == "ridge":
                    p, _ = fit_predict_ridge(X_all[tr], y_reg[tr], X_all[te], band=FLAT)
                elif m == "logreg":
                    p = fit_predict_logreg(X_all[tr], y_cls[tr], X_all[te])
                else:
                    p = fit_predict_gbt(X_all[tr], y_cls[tr], X_all[te])
                preds[m][te] = p
        wf = df.copy()
        for m in models:
            wf[f"wf_{m}"] = preds[m]
        wf_eval = wf[wf["wf_logreg"] != ""].copy()
        for m in models:
            wf_eval[f"pred_{m}"] = wf_eval[f"wf_{m}"]
            for row in metrics_frame(wf_eval, f"pred_{m}"):
                results.append({"protocol": "walkforward", "block": bname, "model": m, **row})

    # ---------------- Protocol F: frozen on dev ----------------------------------
    dev_idx = df.index[df["period"] == "dev2023_24"]
    for bname, cols in blocks.items():
        X = df[cols].to_numpy(dtype=float)
        y_cls = labels(df).to_numpy()
        y_reg = df["y_cc"].to_numpy(dtype=float)
        fz = df.copy()
        for m in models:
            full = np.full(len(df), "", dtype=object)
            if m == "ridge":
                p, _ = fit_predict_ridge(X[dev_idx], y_reg[dev_idx], X, band=FLAT)
            elif m == "logreg":
                p = fit_predict_logreg(X[dev_idx], y_cls[dev_idx], X)
            else:
                p = fit_predict_gbt(X[dev_idx], y_cls[dev_idx], X)
            fz[f"pred_{m}"] = p
            for row in metrics_frame(fz, f"pred_{m}"):
                results.append({"protocol": "frozen_dev", "block": bname, "model": m, **row})

    res = pd.DataFrame(results)
    res.to_csv(out / "ml_results.csv", index=False)
    pd.set_option("display.width", 240)
    for protocol in ("walkforward", "frozen_dev"):
        print(f"\n===================== {protocol} =====================")
        sub = res[res.protocol == protocol].dropna(subset=["sign"])
        piv = sub.pivot_table(index=["block", "model"], columns="period",
                              values=["exact", "sign", "sign_n"])
        print(piv.round(2).to_string())


if __name__ == "__main__":
    main()
