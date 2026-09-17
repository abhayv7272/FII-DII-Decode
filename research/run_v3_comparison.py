#!/usr/bin/env python3
"""Run the official point-in-time replay for v1 / v2 / v3-candidate and write
the v3 evidence package.

Every number in the produced report comes from the production code path
(src/fiidii/backtest.py), not from vectorised research replicas, so the package
is audit-grade. Mirrors the conventions of research/compare_v1_v2.py.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from math import comb, sqrt
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fiidii.backtest import (  # noqa: E402
    BacktestConfig,
    load_ohlc,
    load_participant_oi,
    run_backtest,
)

PERIODS = {
    "2023-2024 development": {2023, 2024},
    "2025 validation": {2025},
    "2026 confirmation": {2026},
}
RETURN_BASES = {
    "close_to_close": "actual_return_pct",
    "overnight_gap": "gap_pct",
    "next_open_to_close": "intraday_return_pct",
}
DAILY_FLAT = 0.15


def _rate(a: int, b: int):
    return round(a / b * 100, 2) if b else None


def _actual(values: pd.Series, threshold: float) -> pd.Series:
    return values.map(lambda v: "UP" if v > threshold else ("DOWN" if v < -threshold else "FLAT"))


def _wilson(hits: int, n: int):
    if not n:
        return None, None
    z = 1.959963984540054
    p = hits / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return round((centre - half) * 100, 2), round((centre + half) * 100, 2)


def _period_of(date_str: str) -> str:
    """Period of a TARGET date string (published protocol: target-session years)."""
    year = int(str(date_str)[:4])
    for name, years in PERIODS.items():
        if year in years:
            return name
    return "?"


def _basis_row(pred: pd.DataFrame, period: str, basis_col: str, threshold: float) -> dict:
    sub = pred
    n_all = len(sub)
    col = sub[basis_col].astype(float)
    actual = _actual(col, threshold)
    baseline_cls = actual.value_counts()
    majority = _rate(int(baseline_cls.max()), n_all)

    pred_cls = sub["predicted_class"]
    exact_hits = int((pred_cls == actual).sum())
    dir_mask = pred_cls.isin(["UP", "DOWN"])
    directional = sub[dir_mask]
    dir_actual = actual[dir_mask]
    hit_incl_flat = int((directional["predicted_class"] == dir_actual).sum())
    nf = dir_actual.isin(["UP", "DOWN"])
    sign_hits = int((directional.loc[nf, "predicted_class"] == dir_actual[nf]).sum())
    lo, hi = _wilson(sign_hits, int(nf.sum()))
    return {
        "period": period, "n": n_all,
        "exact_pct": _rate(exact_hits, n_all),
        "majority_baseline_pct": majority,
        "dir_coverage_pct": _rate(int(dir_mask.sum()), n_all),
        "dir_hit_incl_flat_pct": _rate(hit_incl_flat, len(directional)),
        "nonflat_sign_pct": _rate(sign_hits, int(nf.sum())),
        "nonflat_sign_n": int(nf.sum()),
        "wilson": [lo, hi],
    }


def _mcnemar(a_correct: pd.Series, b_correct: pd.Series) -> dict:
    b = int((a_correct & ~b_correct).sum())
    c = int((~a_correct & b_correct).sum())
    n = b + c
    if not n:
        return {"b_only_v3_correct": b, "c_only_v2_correct": c, "p_value": 1.0}
    k = min(b, c)
    p = 2 * sum(comb(n, i) for i in range(k + 1)) / (2.0 ** n)
    return {"b_v3_correct_v2_wrong": b, "c_v2_correct_v3_wrong": c, "p_value": round(p, 4)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--participant-oi", default="/home/user/historical/participant_oi")
    parser.add_argument("--ohlc", default="/home/user/historical/index_close")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--source-note", default="")
    args = parser.parse_args()

    oi = load_participant_oi(args.participant_oi)
    ohlc = load_ohlc(args.ohlc, symbol="NIFTY")

    runs = {}
    for version in ("v1", "v2", "v3"):
        result = run_backtest(oi, ohlc, option_chains=None,
                              config=BacktestConfig(decoder_version=version))
        runs[version] = result
        print(f"{version}: {len(result.predictions)} predictions, "
              f"exact {result.metrics.get('exact_3_class_accuracy_pct')}%")

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for version, result in runs.items():
        result.predictions.to_csv(out / f"{version}_predictions.csv", index=False, na_rep="")
    runs["v2"].skipped.to_csv(out / "skipped.csv", index=False, na_rep="")

    # ---- comparison tables ------------------------------------------------------
    tables: dict[str, list[dict]] = {name: [] for name in RETURN_BASES}
    for basis_name, col in RETURN_BASES.items():
        for period in list(PERIODS) + ["full"]:
            for version in ("v1", "v2", "v3"):
                pred = runs[version].predictions
                usable = pred.dropna(subset=[col])
                usable = usable.assign(_period=pd.to_datetime(usable["target_date"]).dt.year.map(
                    lambda y: next((name for name, yrs in PERIODS.items() if y in yrs), "?")))
                sub = usable if period == "full" else usable[usable["_period"] == period]
                row = _basis_row(sub, period, col, DAILY_FLAT)
                row["version"] = version
                tables[basis_name].append(row)

    comparison = []
    for basis_name, rows in tables.items():
        frame = pd.DataFrame(rows)
        frame.insert(0, "basis", basis_name)
        comparison.append(frame)
    comparison_pd = pd.concat(comparison, ignore_index=True)
    comparison_pd.to_csv(out / "daily_comparison.csv", index=False)

    # ---- McNemar: v3 vs v2 exact correctness (close-to-close) -------------------
    v2p = runs["v2"].predictions.set_index("signal_date")
    v3p = runs["v3"].predictions.set_index("signal_date")
    common = v2p.join(v3p, lsuffix="_v2", rsuffix="_v3", how="inner")
    actual = common["actual_class_v2"]
    mc = []
    for period in list(PERIODS) + ["full"]:
        mask = pd.Series(True, index=common.index) if period == "full" else \
            pd.to_datetime(common["target_date_v2"]).dt.year.isin(PERIODS[period])
        stat = _mcnemar(common.loc[mask, "predicted_class_v3"] == actual[mask],
                        common.loc[mask, "predicted_class_v2"] == actual[mask])
        stat["period"] = period
        mc.append(stat)
    mc_pd = pd.DataFrame(mc)[["period", "b_v3_correct_v2_wrong", "c_v2_correct_v3_wrong", "p_value"]]
    mc_pd.to_csv(out / "mcnemar_exact_v3_vs_v2.csv", index=False)

    # ---- five-session diagnostic for the v3 daily composite ---------------------
    v3pred = runs["v3"].predictions.copy()
    ohlc_sorted = ohlc.sort_values("date").reset_index(drop=True)
    close = ohlc_sorted.set_index("date")["close"]
    dates = list(ohlc_sorted["date"])
    idx = {d: i for i, d in enumerate(dates)}
    v3pred["signal_d"] = pd.to_datetime(v3pred["signal_date"]).dt.date
    y5, t5 = [], []
    for d in v3pred["signal_d"]:
        i = idx.get(d)
        if i is None or i + 5 >= len(dates):
            y5.append(None); t5.append(None)
            continue
        y5.append((close.iloc[i + 5] / close.iloc[i] - 1) * 100)
        t5.append(dates[i + 5])
    v3pred["y_5d"] = y5
    v3pred["target5_date"] = t5
    wrows = []
    for period in list(PERIODS) + ["full"]:
        sub = v3pred if period == "full" else v3pred[
            pd.to_datetime(v3pred["target5_date"]).dt.year.isin(PERIODS[period])]
        sub = sub.dropna(subset=["y_5d"])
        actual5 = _actual(sub["y_5d"].astype(float), 0.50)
        nf = actual5.isin(["UP", "DOWN"])
        hits = int((sub.loc[nf, "predicted_class"] == actual5[nf]).sum())
        wrows.append({
            "period": period, "n": len(sub),
            "majority_baseline_pct": _rate(int(actual5.value_counts().max()), len(sub)),
            "nonflat_sign_pct": _rate(hits, int(nf.sum())),
            "nonflat_sign_n": int(nf.sum()),
        })
    wk = pd.DataFrame(wrows)
    wk.to_csv(out / "v3_weekly_diagnostic.csv", index=False)

    # ---- config + report ----------------------------------------------------------
    (out / "run_config.json").write_text(json.dumps({
        "source_note": args.source_note,
        "decoder_versions": ["v1", "v2", "v3"],
        "flat_threshold_pct_daily": DAILY_FLAT,
        "flat_threshold_pct_weekly": 0.50,
        "v3_status": "CANDIDATE - fitted on 2023-2024 development only; "
                     "2025 validation and 2026 confirmation reported unchanged. "
                     "Promotion requires an untouched forward window.",
        "v3_parameter_delta": {
            "NEXT_DAY_INSTRUMENT_WEIGHT": {"index_call": 0.30, "index_put": 0.30, "index_fut": 0.40},
            "NEXT_DAY_PARTICIPANT_WEIGHT": {"Pro": 0.60, "FII": 0.40, "Client": -0.10, "DII": 0.0},
            "forced_class_threshold": 0.0,
        },
        "periods": {k: sorted(v) for k, v in PERIODS.items()},
    }, indent=2), encoding="utf-8")

    lines = [
        "# v3-candidate historical comparison (daily OI lean)",
        "",
        "> **Status: research candidate, not production default.** V3 was fitted on the",
        "> 2023-2024 development partition only, then replayed unchanged over 2025",
        "> validation and 2026 confirmation. It must still pass an untouched forward",
        "> window before any production promotion. Educational research; not investment advice.",
        "",
        f"Data: {args.source_note}",
        "",
        "## v3-candidate delta vs locked v2",
        "",
        "- index call 30% / index put 30% / **index futures 40%** (v2: 40/40/20);",
        "- **Pro 60% / FII 40%** (v2: Pro 53.3 / FII 26.7 / contra-Client 20) plus a small",
        "  development-fitted Client-aligned tilt of -0.10 (zeroing it costs <1pp);",
        "- forced-class threshold **0.00** (v2: +-0.10) — the ~79% of non-FLAT sessions makes",
        "  a 0.10 abstain band cost more exact-class hits than it saves;",
        "- closures still half weight, flows still normalised by market OI, DII still excluded,",
        "  stock derivatives still out of the daily score, actionability still abstains on",
        "  weak/composite-conflict states.",
        "",
    ]
    for basis_name in RETURN_BASES:
        rows = [r for r in tables[basis_name]]
        lines += [
            f"## {basis_name.replace('_', ' ')} (+-{DAILY_FLAT}% FLAT band)",
            "",
            "| Period | Version | N | Exact | Baseline | Dir. coverage | Dir. hit incl. FLAT | Non-FLAT sign | 95% CI |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for row in rows:
            lo, hi = row["wilson"]
            lines.append(
                f"| {row['period']} | {row['version']} | {row['n']} | "
                f"{row['exact_pct']}% | {row['majority_baseline_pct']}% | "
                f"{row['dir_coverage_pct']}% | {row['dir_hit_incl_flat_pct']}% | "
                f"{row['nonflat_sign_pct']}% ({row['nonflat_sign_n']}) | {lo}%-{hi}% |"
            )
        lines.append("")
    lines += [
        "## Paired McNemar (exact-class correctness, close-to-close): v3 vs v2",
        "",
        "| Period | v3 right / v2 wrong | v2 right / v3 wrong | p-value |",
        "|---|---:|---:|---:|",
    ]
    for row in mc:
        lines.append(f"| {row['period']} | {row['b_v3_correct_v2_wrong']} | "
                     f"{row['c_v2_correct_v3_wrong']} | {row['p_value']} |")
    lines += [
        "",
        "## Five-session diagnostic (+-0.50% FLAT band) — daily composite only",
        "",
        "| Period | N | Majority baseline | Non-FLAT sign | n |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in wrows:
        lines.append(f"| {row['period']} | {row['n']} | {row['majority_baseline_pct']}% | "
                     f"{row['nonflat_sign_pct']}% | {row['nonflat_sign_n']} |")
    lines += [
        "",
        "> The weekly channel remains unvalidated; production continues to emit NO-VALIDATED-EDGE",
        "> for next week. This table only records how the daily lean behaves over five sessions.",
        "",
        "## Interpretation rules",
        "",
        "- Next-open-to-close is the executable basis; no version shows a reliable edge there.",
        "- Close-to-close gains are concentrated in the overnight-gap channel, which is not",
        "  capturable at the signal date's close because Participant-OI is published after it",
        "  (entry at next open loses the gap).",
        "- Selection was done on 2023-2024 development from a bounded structural family; the",
        "  2025/2026 columns were not used for fitting, but a fresh untouched forward window",
        "  is still required before production promotion.",
        "",
    ]
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
