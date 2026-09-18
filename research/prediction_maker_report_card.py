#!/usr/bin/env python3
"""Backtest the *actual components* of the daily prediction-maker report.

The daily email is a multi-part scenario report, not one atomic forecast. It is
therefore statistically wrong to assign one invented “overall accuracy” to the
whole email. This command instead produces an auditable report card for each
claim the user sees:

* default v2 next-session UP/FLAT/DOWN call;
* research-only v3 next-session candidate;
* the rejected weekly candidate (the production weekly section intentionally
  emits NO-VALIDATED-EDGE, so it has no directional accuracy to claim);
* option-chain level hold proxy;
* V7–V9 intraday confirmation/execution searches;
* V10 at-open tiny-gap previous-close touch alert; and
* the V11 V10 trade-execution audit.

Point-in-time daily and weekly figures are recalculated from the committed
historical inputs every run. The level/execution studies cite their dedicated
saved audit outputs because their raw dated option-chain/one-minute inputs are
intentionally not committed.  This report is a deployment-readiness scorecard,
not investment advice.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
RESEARCH = ROOT / "research"
for path in (SRC, RESEARCH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from fiidii.backtest import BacktestConfig, load_ohlc, load_participant_oi, run_backtest  # noqa: E402
from compare_v1_v2 import weekly_comparison  # noqa: E402
from v10_structural_gap_pivot_sniper import (  # noqa: E402
    add_structural_features,
    build_structural_rule_table,
    load_intraday_daily,
    robust_rules,
)

DEFAULT_V10_RULE = "abs_gap_0.03_0.12_both_fill_prev_close"


def _pct(value: Any) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.2f}%"


def _int(value: Any) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{int(value):,}"


def _period(frame: pd.DataFrame, version: str, period: str) -> pd.Series:
    matched = frame[(frame["version"] == version) & (frame["period"] == period)]
    if len(matched) != 1:
        raise ValueError(f"expected one {version}/{period} row, found {len(matched)}")
    return matched.iloc[0]


def _open_to_close_sign(predictions: pd.DataFrame, flat_band_pct: float = 0.15) -> tuple[float | None, int]:
    """Score the direction call on the executable next-open-to-close return.

    Close-to-close includes an overnight move that cannot be entered after
    participant-OI is published. The report card therefore shows this separately
    and counts only non-FLAT intraday returns, following the published audit.
    """
    frame = predictions.copy()
    intraday = pd.to_numeric(frame["intraday_return_pct"], errors="coerce")
    actual = intraday.map(
        lambda value: "UP" if value > flat_band_pct else "DOWN"
        if value < -flat_band_pct else "FLAT"
    )
    mask = frame["predicted_class"].isin(["UP", "DOWN"]) & actual.isin(["UP", "DOWN"])
    n = int(mask.sum())
    if not n:
        return None, 0
    hits = int((frame.loc[mask, "predicted_class"] == actual.loc[mask]).sum())
    return round(hits / n * 100.0, 2), n


def _daily_component(result, version: str) -> dict[str, Any]:
    metrics = result.metrics
    executable_accuracy, executable_samples = _open_to_close_sign(result.predictions)
    return {
        "component": f"{version} next-session direction",
        "status": "PRODUCTION_DEFAULT" if version == "v2" else "RESEARCH_CANDIDATE_NOT_PROMOTED",
        "target": "next trading-session close-to-close UP / FLAT / DOWN",
        "samples": metrics["signals_evaluated"],
        "full_accuracy_pct": metrics["exact_3_class_accuracy_pct"],
        "baseline_pct": metrics["majority_class_baseline_accuracy_pct"],
        "executable_metric": "next-open-to-close non-FLAT sign",
        "executable_accuracy_pct": executable_accuracy,
        "executable_samples": executable_samples,
        "evidence": (
            "v2 is the currently emailed decoder; v3 is not the default because its "
            "close-to-close uplift is mostly overnight-gap behaviour."
        ),
        "source": "recomputed from historical/participant_oi.csv + historical/nifty_ohlc.csv",
    }


def _weekly_component(weekly: pd.DataFrame) -> dict[str, Any]:
    full = _period(weekly, "v2_candidate", "full")
    confirmation = _period(weekly, "v2_candidate", "2026 confirmation")
    return {
        "component": "Mon–Fri weekly direction",
        "status": "NO_VALIDATED_EDGE__PRODUCTION_ABSTAINS",
        "target": "five-session close-to-close UP / FLAT / DOWN",
        "samples": int(full["samples"]),
        "full_accuracy_pct": float(full["exact_accuracy_pct"]),
        "baseline_pct": float(full["majority_baseline_pct"]),
        "confirmation_accuracy_pct": float(confirmation["exact_accuracy_pct"]),
        "confirmation_baseline_pct": float(confirmation["majority_baseline_pct"]),
        "nonflat_sign_accuracy_pct": float(full["nonflat_sign_accuracy_pct"]),
        "confirmation_nonflat_sign_accuracy_pct": float(confirmation["nonflat_sign_accuracy_pct"]),
        "evidence": (
            "This was the old v2 weekly candidate and failed its 2026 confirmation; "
            "the live report therefore displays weekly context/playbook, not a directional call."
        ),
        "source": "recomputed with research/compare_v1_v2.py weekly candidate",
    }


def _level_component(metrics_path: Path) -> dict[str, Any]:
    metrics = json.loads(metrics_path.read_text())["metrics"]["level_reaction_daily_proxy"]
    return {
        "component": "Option-chain support/resistance hold",
        "status": "NO_VALIDATED_EDGE",
        "target": "next-session range touches level then support holds / resistance rejects",
        "samples": int(metrics["tests"]),
        "full_accuracy_pct": float(metrics["hold_accuracy_pct"]),
        "support_accuracy_pct": float(metrics["support"]["hold_accuracy_pct"]),
        "resistance_accuracy_pct": float(metrics["resistance"]["hold_accuracy_pct"]),
        "evidence": (
            "Daily-bar proxy only; it cannot establish candle order, sweep/reclaim, "
            "entry, stop, or slippage."
        ),
        "source": str(metrics_path.relative_to(ROOT)),
    }


def _v10_component(intraday_path: Path) -> tuple[dict[str, Any], pd.DataFrame]:
    _, daily = load_intraday_daily(intraday_path)
    table, yearly, _ = build_structural_rule_table(add_structural_features(daily))
    robust = robust_rules(table, min_train=100, min_val=40, min_confirm=25, min_hit=70.0)
    matched = table[table["rule"] == DEFAULT_V10_RULE]
    if len(matched) != 1:
        raise ValueError(f"V10 default rule missing from rebuilt table: {DEFAULT_V10_RULE}")
    row = matched.iloc[0]
    component = {
        "component": "V10 tiny-gap previous-close touch",
        "status": "VALIDATED_LEVEL_TOUCH_ALERT__NOT_STANDALONE_TRADE",
        "target": "at open, abs gap 0.03% to <0.12% → previous close touched intraday",
        "samples": int(row["calls"]),
        "full_accuracy_pct": float(row["hit_rate"]),
        "train_accuracy_pct": float(row["train_2017_2023_hit_rate"]),
        "validation_accuracy_pct": float(row["val_2024_2025_hit_rate"]),
        "confirmation_accuracy_pct": float(row["confirm_2026_hit_rate"]),
        "mean_target_distance_pts": float(row["mean_abs_gap_pts"]),
        "robust_rules_in_family": int(len(robust)),
        "evidence": (
            "This is known only after the cash-market open and predicts a level touch, "
            "not all-day close direction or a profitable options trade."
        ),
        "source": f"recomputed from {intraday_path.resolve().relative_to(ROOT)}",
    }
    return component, yearly


def _saved_execution_components() -> list[dict[str, Any]]:
    files = {
        "V7 intraday level confirmation": ROOT / "reports/v7_intraday_institutional_levels/summary.json",
        "V8 intraday target/stop simulation": ROOT / "reports/v8_intraday_trade_sim/summary.json",
        "V9 OI + intraday confirmation": ROOT / "reports/v9_oi_intraday_confirmation/summary.json",
        "V11 V10 execution audit": ROOT / "reports/v11_gap_sniper_execution/summary.json",
    }
    out: list[dict[str, Any]] = []
    for name, path in files.items():
        payload = json.loads(path.read_text())
        if name.startswith("V7"):
            value = payload.get("robust_70pct_rules", 0)
        elif name.startswith("V8"):
            value = payload.get("generic_robust_70pct_rules", 0) + payload.get("level_robust_70pct_rules", 0)
        elif name.startswith("V9"):
            value = payload.get("robust_70pct_rules", 0)
        else:
            value = payload.get("robust_positive_70pct_trade_rules", 0)
        out.append({
            "component": name,
            "status": "NO_VALIDATED_EDGE" if not value else "REVIEW_REQUIRED",
            "target": "intraday confirmation / executable trade conversion",
            "robust_rules": int(value),
            "evidence": "No production rule is promoted from this research stage.",
            "source": str(path.relative_to(ROOT)),
        })
    return out


def build_report_card(oi_path: Path, ohlc_path: Path, intraday_path: Path) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Recalculate direction/weekly/V10 claims and load bounded execution audits."""
    oi = load_participant_oi(oi_path)
    ohlc = load_ohlc(ohlc_path, symbol="NIFTY")
    runs = {
        version: run_backtest(oi, ohlc, config=BacktestConfig(decoder_version=version))
        for version in ("v2", "v3")
    }
    weekly, _, _ = weekly_comparison(oi, ohlc)
    v10, yearly = _v10_component(intraday_path)
    components = [
        _daily_component(runs["v2"], "v2"),
        _daily_component(runs["v3"], "v3"),
        _weekly_component(weekly),
        _level_component(ROOT / "reports/backtest_v2_levels_2023-08_to_2026-09/metrics.json"),
        v10,
        *_saved_execution_components(),
    ]
    card = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "component-level backtest of the daily market possibility report",
        "overall_verdict": "NOT_READY_AS_A_STANDALONE_TRADING_PREDICTOR",
        "why_no_single_accuracy": (
            "The email has conditional branches. A range/break/reclaim scenario is not "
            "one unconditional UP/DOWN prediction, so each claim is scored separately."
        ),
        "daily_default": components[0],
        "daily_v3_research": components[1],
        "weekly": components[2],
        "levels": components[3],
        "v10": components[4],
        "execution_audits": components[5:],
        "deployment_policy": {
            "next_day_default": "v2 remains educational conditional context only",
            "weekly": "NO-VALIDATED-EDGE; show a playbook, not a direction forecast",
            "levels": "conditional confirmation only; no validated generic sweep/break trade",
            "v10": "allow as an at-open previous-close-touch alert only, never as a standalone trade",
        },
    }
    return card, pd.DataFrame(components), yearly


def _markdown(card: dict) -> str:
    d, v3, w, levels, v10 = (card[key] for key in ("daily_default", "daily_v3_research", "weekly", "levels", "v10"))
    lines = [
        "# Prediction-Maker Backtest Report Card",
        "",
        "> Educational research, not investment advice. This report scores each precise",
        "> forecast claim in the email separately. It does not invent one misleading",
        "> accuracy number for conditional scenario branches.",
        "",
        f"## Overall verdict: **{card['overall_verdict']}**",
        "",
        "The complete daily next-day + Mon–Fri + level/sweep system is **not** yet",
        "validated as a standalone trading predictor. The tables below show exactly",
        "what is and is not supported by the historical evidence.",
        "",
        "## 1. Next-day UP / DOWN / CONSOLIDATION",
        "",
        "| Model used in report | Samples | Exact 3-class accuracy | Majority baseline | Executable next-open-to-close sign | Result |",
        "|---|---:|---:|---:|---:|---|",
        (
            f"| v2 (current default) | {_int(d['samples'])} | {_pct(d['full_accuracy_pct'])} | "
            f"{_pct(d['baseline_pct'])} | {_pct(d['executable_accuracy_pct'])} (n={_int(d['executable_samples'])}) | "
            "Below baseline / not standalone |"
        ),
        (
            f"| v3 (research candidate) | {_int(v3['samples'])} | {_pct(v3['full_accuracy_pct'])} | "
            f"{_pct(v3['baseline_pct'])} | {_pct(v3['executable_accuracy_pct'])} (n={_int(v3['executable_samples'])}) | "
            "Not promoted: executable basis is near chance |"
        ),
        "",
        "**Meaning:** v2 is the current emailed OI context. Its exact next-day",
        "UP/FLAT/DOWN result is below the naive majority baseline. V3 has a stronger",
        "close-to-close research number, but the usable entry-at-next-open result does",
        "not establish a trade edge, so it remains opt-in research only.",
        "",
        "## 2. Weekly Monday–Friday prediction",
        "",
        "| Status | Samples | Exact 3-class accuracy | Majority baseline | 2026 confirmation exact | 2026 baseline |",
        "|---|---:|---:|---:|---:|---:|",
        (
            f"| Rejected weekly candidate; production abstains | {_int(w['samples'])} | "
            f"{_pct(w['full_accuracy_pct'])} | {_pct(w['baseline_pct'])} | "
            f"{_pct(w['confirmation_accuracy_pct'])} | {_pct(w['confirmation_baseline_pct'])} |"
        ),
        "",
        "**Meaning:** the report correctly provides a Mon–Fri scenario playbook, but",
        "must not claim a validated weekly UP/DOWN direction prediction yet.",
        "",
        "## 3. Support, resistance, break and sweep claims",
        "",
        "| Claim tested | Tests | Hold / reject accuracy | Support | Resistance | Result |",
        "|---|---:|---:|---:|---:|---|",
        (
            f"| Option-chain level daily-bar proxy | {_int(levels['samples'])} | "
            f"{_pct(levels['full_accuracy_pct'])} | {_pct(levels['support_accuracy_pct'])} | "
            f"{_pct(levels['resistance_accuracy_pct'])} | Near coin-flip; no generic edge |"
        ),
        "",
        "V7/V8/V9 reran intraday candle confirmation and target/stop simulations. None",
        "produced a robust 70%+ production rule across train, validation, and 2026",
        "confirmation. Therefore level rows in the email remain conditional plans, not",
        "promised trades.",
        "",
        "## 4. V10 at-open tiny-gap alert",
        "",
        "| Event prediction | Calls | Overall | Train 2017–23 | Validation 2024–25 | Confirmation 2026 |",
        "|---|---:|---:|---:|---:|---:|",
        (
            f"| abs gap 0.03% to <0.12% → previous close touched intraday | {_int(v10['samples'])} | "
            f"{_pct(v10['full_accuracy_pct'])} | {_pct(v10['train_accuracy_pct'])} | "
            f"{_pct(v10['validation_accuracy_pct'])} | {_pct(v10['confirmation_accuracy_pct'])} |"
        ),
        "",
        f"Mean target distance: **{v10['mean_target_distance_pts']:.2f} NIFTY points**.",
        "This high statistic applies only after the opening price is known and only to",
        "a previous-close **touch**. It is not a next-day close direction forecast.",
        "The raw-1-minute V11 execution audit found **0** robust positive-P&L 70%",
        "target/stop conversions, so V10 is an alert/context module, not a trade bot.",
        "",
        "## Deployment decision",
        "",
        "- **Keep:** daily OI context, conditional range/break/reclaim map, and V10",
        "  at-open level-touch alert with its warning.",
        "- **Do not claim yet:** reliable every-day next-day direction, weekly direction,",
        "  generic sweep/break trade, or automated target/stop profitability.",
        "- **Next validation:** continue untouched live forward tracking and collect",
        "  timestamped option-chain, option-premium/spread, GIFT/pre-open, VIX, sector",
        "  leadership, and exact institutional-level data before changing any rule.",
        "",
        "## Method and audit sources",
        "",
        "- v2/v3 and weekly rows are recalculated by this run from committed point-in-time",
        "  participant-OI and NIFTY OHLC history.",
        f"- Level proxy: `{levels['source']}`.",
        f"- V10: `{v10['source']}`.",
    ]
    for audit in card["execution_audits"]:
        lines.append(f"- {audit['component']}: `{audit['source']}` → {audit['status']}.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participant-oi", default="historical/participant_oi.csv")
    parser.add_argument("--ohlc", default="historical/nifty_ohlc.csv")
    parser.add_argument("--intraday", default="historical/nifty_15m.csv")
    parser.add_argument("--out", default="reports/prediction_maker_backtest")
    args = parser.parse_args()

    card, components, yearly = build_report_card(
        Path(args.participant_oi), Path(args.ohlc), Path(args.intraday)
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(_markdown(card))
    (out / "summary.json").write_text(json.dumps(card, indent=2, default=str))
    components.to_csv(out / "component_scorecard.csv", index=False)
    yearly[yearly["rule"] == DEFAULT_V10_RULE].to_csv(out / "v10_yearly_breakdown.csv", index=False)
    print(f"wrote {out / 'report.md'}")
    print(f"overall verdict: {card['overall_verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
