#!/usr/bin/env python3
"""Audit whether end-of-day India VIX improves the prediction-maker report.

India VIX is known at the close of the signal session, so it can be included in
that evening's next-session *range/risk context*.  It cannot be used to explain
an already-open market and this study deliberately does not turn it into an
unvalidated UP/DOWN override.

Protocol locked before this script is run
-----------------------------------------
* Target: next-session absolute NIFTY close-to-close return, calculated from
  the canonical NIFTY target used by the OI backtest.
* Development/fitting rows: target dates through 2024-12-31.
* Untuned validation: 2025 target dates.
* Confirmation: 2026 target dates available in the pinned archive. A prior
  broad descriptive correlation was seen before this formal audit. No threshold
  or rule choice below uses validation or confirmation observations, but neither
  evaluation split is described as a newly pristine blind sample.
* The development 25th/75th percentile of VIX close define QUIET/ELEVATED.
  Its median absolute return defines "typical" movement. No global quantile is
  used as a deployed threshold.
* Two pre-specified, non-directional claims are tested, separately:
  (1) ELEVATED VIX predicts an above-typical next-session absolute move;
  (2) QUIET VIX predicts a below-typical next-session absolute move.
* Promotion requires development, validation, and 2026 confirmation to have
  enough conditional observations and at least +5 percentage-point hit-rate
  lift over that period's unconditional target frequency. This intentionally
  strict, simple criterion is a reporting-context gate, not a trading-profit
  claim.

The output is an evidence record. A passing context rule would still require
live forward monitoring and must never be interpreted as a standalone trade,
direction, options-premium, stop, or slippage rule.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from math import sqrt
from pathlib import Path
import sys
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fiidii.backtest import BacktestConfig, load_ohlc, load_participant_oi, run_backtest  # noqa: E402

TRAIN_END = pd.Timestamp("2024-12-31")
VALIDATION_START = pd.Timestamp("2025-01-01")
VALIDATION_END = pd.Timestamp("2025-12-31")
CONFIRMATION_START = pd.Timestamp("2026-01-01")

MIN_DEVELOPMENT_SIGNALS = 50
MIN_VALIDATION_SIGNALS = 25
MIN_CONFIRMATION_SIGNALS = 15
MIN_LIFT_PCT_POINTS = 5.0

PERIOD_ORDER = ("development", "validation_2025", "confirmation_2026")
RULE_ORDER = ("ELEVATED_RANGE", "QUIET_RANGE")


@dataclass(frozen=True)
class Policy:
    """Thresholds fitted using development targets only."""

    quiet_vix_close_lte: float
    elevated_vix_close_gte: float
    typical_abs_return_pct: float
    train_rows: int
    train_start: str
    train_end: str


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None or pd.isna(value) else round(float(value), digits)


def _period(value: pd.Timestamp) -> str | None:
    if value <= TRAIN_END:
        return "development"
    if VALIDATION_START <= value <= VALIDATION_END:
        return "validation_2025"
    if value >= CONFIRMATION_START:
        return "confirmation_2026"
    return None


def _wilson_lower_pct(hits: int, total: int) -> float | None:
    """Two-sided 95% Wilson lower bound, for transparent small-n context."""
    if total <= 0:
        return None
    z = 1.959963984540054
    p = hits / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return _round((centre - half) * 100.0)


def prepare_observations(predictions: pd.DataFrame, vix: pd.DataFrame) -> pd.DataFrame:
    """Join EOD signal-date VIX to one next-session NIFTY target per prediction."""
    required_predictions = {
        "signal_date", "target_date", "actual_return_pct", "predicted_class",
        "actual_class", "exact_hit",
    }
    missing_predictions = required_predictions.difference(predictions.columns)
    if missing_predictions:
        raise ValueError(f"predictions missing columns: {sorted(missing_predictions)}")
    required_vix = {"date", "close"}
    missing_vix = required_vix.difference(vix.columns)
    if missing_vix:
        raise ValueError(f"VIX data missing columns: {sorted(missing_vix)}")

    p = predictions.copy()
    p["signal_date"] = pd.to_datetime(p["signal_date"], errors="raise").dt.normalize()
    p["target_date"] = pd.to_datetime(p["target_date"], errors="raise").dt.normalize()
    p["actual_return_pct"] = pd.to_numeric(p["actual_return_pct"], errors="coerce")
    if p["signal_date"].duplicated().any():
        raise ValueError("predictions contain duplicate signal dates")

    indexed_vix = vix[["date", "close"]].copy()
    indexed_vix["date"] = pd.to_datetime(indexed_vix["date"], errors="raise").dt.normalize()
    indexed_vix["close"] = pd.to_numeric(indexed_vix["close"], errors="coerce")
    indexed_vix = indexed_vix.dropna(subset=["close"])
    if indexed_vix["date"].duplicated().any():
        raise ValueError("India VIX data contain duplicate dates")
    indexed_vix = indexed_vix.rename(columns={"date": "signal_date", "close": "vix_close"})

    observations = p.merge(indexed_vix, on="signal_date", how="inner", validate="one_to_one")
    observations = observations.dropna(subset=["actual_return_pct", "vix_close"]).copy()
    observations["abs_return_pct"] = observations["actual_return_pct"].abs()
    observations["period"] = observations["target_date"].map(_period)
    observations = observations.dropna(subset=["period"])
    return observations.sort_values("signal_date").reset_index(drop=True)


def fit_policy(observations: pd.DataFrame) -> Policy:
    """Fit the sole VIX thresholds from development observations only."""
    train = observations[observations["period"] == "development"].copy()
    if len(train) < 100:
        raise ValueError(f"need at least 100 development observations, found {len(train)}")
    return Policy(
        quiet_vix_close_lte=_round(train["vix_close"].quantile(0.25), 4),
        elevated_vix_close_gte=_round(train["vix_close"].quantile(0.75), 4),
        typical_abs_return_pct=_round(train["abs_return_pct"].median(), 4),
        train_rows=int(len(train)),
        train_start=train["target_date"].min().date().isoformat(),
        train_end=train["target_date"].max().date().isoformat(),
    )


def assign_regimes(observations: pd.DataFrame, policy: Policy) -> pd.DataFrame:
    """Attach frozen VIX regime labels and pre-specified binary targets."""
    out = observations.copy()
    out["vix_regime"] = "NORMAL"
    out.loc[out["vix_close"] <= policy.quiet_vix_close_lte, "vix_regime"] = "QUIET"
    out.loc[out["vix_close"] >= policy.elevated_vix_close_gte, "vix_regime"] = "ELEVATED"
    out["above_typical_move"] = out["abs_return_pct"] >= policy.typical_abs_return_pct
    out["below_typical_move"] = out["abs_return_pct"] < policy.typical_abs_return_pct
    return out


def _score_claim(frame: pd.DataFrame, rule: str, period: str, policy: Policy) -> dict[str, Any]:
    if rule == "ELEVATED_RANGE":
        selected = frame["vix_close"] >= policy.elevated_vix_close_gte
        target = frame["above_typical_move"]
        claim = "ELEVATED VIX → above-typical next-session absolute move"
        expected_regime = "ELEVATED"
    elif rule == "QUIET_RANGE":
        selected = frame["vix_close"] <= policy.quiet_vix_close_lte
        target = frame["below_typical_move"]
        claim = "QUIET VIX → below-typical next-session absolute move"
        expected_regime = "QUIET"
    else:
        raise ValueError(f"unknown rule {rule}")

    period_frame = frame[frame["period"] == period]
    conditional = period_frame[selected.loc[period_frame.index]]
    n = int(len(conditional))
    hits = int(target.loc[conditional.index].sum())
    all_n = int(len(period_frame))
    base_hits = int(target.loc[period_frame.index].sum())
    hit_rate = (hits / n * 100.0) if n else None
    baseline = (base_hits / all_n * 100.0) if all_n else None
    lift = (hit_rate - baseline) if hit_rate is not None and baseline is not None else None
    return {
        "rule": rule,
        "claim": claim,
        "expected_regime": expected_regime,
        "period": period,
        "period_rows": all_n,
        "calls": n,
        "hits": hits,
        "hit_rate_pct": _round(hit_rate),
        "wilson_95_lower_pct": _wilson_lower_pct(hits, n),
        "unconditional_target_rate_pct": _round(baseline),
        "lift_pct_points": _round(lift),
        "mean_abs_return_pct_when_called": _round(conditional["abs_return_pct"].mean()),
        "mean_abs_return_pct_all": _round(period_frame["abs_return_pct"].mean()),
    }


def score_rules(observations: pd.DataFrame, policy: Policy) -> pd.DataFrame:
    """Score exactly the two locked claims in all three time periods."""
    rows = [_score_claim(observations, rule, period, policy)
            for rule in RULE_ORDER for period in PERIOD_ORDER]
    return pd.DataFrame(rows)


def gate_rules(scorecard: pd.DataFrame) -> pd.DataFrame:
    """Apply the locked validation + confirmation gate without inspecting train fit."""
    rows: list[dict[str, Any]] = []
    for rule in RULE_ORDER:
        selected = scorecard[scorecard["rule"] == rule].set_index("period")
        development = selected.loc["development"]
        validation = selected.loc["validation_2025"]
        confirmation = selected.loc["confirmation_2026"]
        development_sample_ok = int(development["calls"]) >= MIN_DEVELOPMENT_SIGNALS
        validation_sample_ok = int(validation["calls"]) >= MIN_VALIDATION_SIGNALS
        confirmation_sample_ok = int(confirmation["calls"]) >= MIN_CONFIRMATION_SIGNALS
        development_lift_ok = (development["lift_pct_points"] is not None
                               and float(development["lift_pct_points"]) >= MIN_LIFT_PCT_POINTS)
        validation_lift_ok = (validation["lift_pct_points"] is not None
                              and float(validation["lift_pct_points"]) >= MIN_LIFT_PCT_POINTS)
        confirmation_lift_ok = (confirmation["lift_pct_points"] is not None
                                and float(confirmation["lift_pct_points"]) >= MIN_LIFT_PCT_POINTS)
        promoted = all((development_sample_ok, validation_sample_ok, confirmation_sample_ok,
                        development_lift_ok, validation_lift_ok, confirmation_lift_ok))
        rows.append({
            "rule": rule,
            "development_min_calls": MIN_DEVELOPMENT_SIGNALS,
            "validation_min_calls": MIN_VALIDATION_SIGNALS,
            "confirmation_min_calls": MIN_CONFIRMATION_SIGNALS,
            "min_lift_pct_points": MIN_LIFT_PCT_POINTS,
            "development_sample_ok": development_sample_ok,
            "validation_sample_ok": validation_sample_ok,
            "confirmation_sample_ok": confirmation_sample_ok,
            "development_lift_ok": development_lift_ok,
            "validation_lift_ok": validation_lift_ok,
            "confirmation_lift_ok": confirmation_lift_ok,
            "state": "CONTEXT_RULE_CANDIDATE" if promoted else "NOT_PROMOTED",
        })
    return pd.DataFrame(rows)


def direction_by_regime(observations: pd.DataFrame) -> pd.DataFrame:
    """Descriptive v2 class accuracy strata; never a searched override rule."""
    rows: list[dict[str, Any]] = []
    for period in (*PERIOD_ORDER, "all"):
        subset = observations if period == "all" else observations[observations["period"] == period]
        for regime in ("QUIET", "NORMAL", "ELEVATED"):
            block = subset[subset["vix_regime"] == regime]
            n = int(len(block))
            rows.append({
                "period": period,
                "vix_regime": regime,
                "observations": n,
                "v2_exact_3class_accuracy_pct": _round(block["exact_hit"].mean() * 100.0) if n else None,
                "v2_directional_coverage_pct": _round(
                    block["predicted_class"].isin(["UP", "DOWN"]).mean() * 100.0
                ) if n else None,
                "mean_next_abs_return_pct": _round(block["abs_return_pct"].mean()) if n else None,
            })
    return pd.DataFrame(rows)


def correlations(observations: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for period in (*PERIOD_ORDER, "all"):
        subset = observations if period == "all" else observations[observations["period"] == period]
        rows.append({
            "period": period,
            "observations": int(len(subset)),
            "vix_vs_next_abs_return_spearman": _round(subset["vix_close"].corr(subset["abs_return_pct"], method="spearman"), 3),
            "vix_vs_next_signed_return_spearman": _round(subset["vix_close"].corr(subset["actual_return_pct"], method="spearman"), 3),
        })
    return rows


def build_audit(participant_oi_path: Path, nifty_ohlc_path: Path, vix_ohlc_path: Path) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Recompute the policy audit from durable source data."""
    oi = load_participant_oi(participant_oi_path)
    nifty = load_ohlc(nifty_ohlc_path, symbol="NIFTY")
    vix = load_ohlc(vix_ohlc_path, symbol="India VIX")
    predictions = run_backtest(oi, nifty, config=BacktestConfig(decoder_version="v2")).predictions
    raw_observations = prepare_observations(predictions, vix)
    policy = fit_policy(raw_observations)
    observations = assign_regimes(raw_observations, policy)
    scorecard = score_rules(observations, policy)
    gates = gate_rules(scorecard)
    direction = direction_by_regime(observations)

    any_promoted = bool((gates["state"] == "CONTEXT_RULE_CANDIDATE").any())
    summary: dict[str, Any] = {
        "overall_state": "CONTEXT_RULE_CANDIDATE_REQUIRES_LIVE_MONITORING" if any_promoted else "NO_VIX_RULE_PROMOTED",
        "scope": "EOD India VIX → next-session NIFTY range/risk context; no direction override tested or promoted",
        "sources": {
            "participant_oi": str(participant_oi_path),
            "nifty_ohlc": str(nifty_ohlc_path),
            "india_vix_ohlc": str(vix_ohlc_path),
        },
        "date_coverage": {
            "vix": {
                "rows": int(len(vix)),
                "start": pd.to_datetime(vix["date"]).min().date().isoformat(),
                "end": pd.to_datetime(vix["date"]).max().date().isoformat(),
            },
            "matched_prediction_observations": int(len(observations)),
            "first_signal_date": observations["signal_date"].min().date().isoformat(),
            "last_target_date": observations["target_date"].max().date().isoformat(),
        },
        "locked_protocol": {
            "development_target_through": TRAIN_END.date().isoformat(),
            "validation_target_dates": "2025-01-01 to 2025-12-31",
            "confirmation_target_dates": "2026-01-01 onward in the pinned archive",
            "threshold_source": "development only",
            "claims": [
                "ELEVATED VIX → above-typical next-session absolute move",
                "QUIET VIX → below-typical next-session absolute move",
            ],
            "promotion_gate": {
                "development_min_calls": MIN_DEVELOPMENT_SIGNALS,
                "validation_min_calls": MIN_VALIDATION_SIGNALS,
                "confirmation_min_calls": MIN_CONFIRMATION_SIGNALS,
                "minimum_lift_vs_period_unconditional_target_pct_points": MIN_LIFT_PCT_POINTS,
                "requires_development_validation_and_confirmation": True,
            },
            "evaluation_caveat": "A prior global descriptive VIX correlation was inspected. Neither 2025 nor 2026 entered threshold fitting, but neither is represented as a newly pristine blind sample.",
        },
        "fitted_policy": asdict(policy),
        "rule_gates": gates.to_dict(orient="records"),
        "correlations": correlations(observations),
        "direction_segmentation_status": "DESCRIPTIVE_ONLY__NO_VIX_DERIVED_DIRECTION_FILTER_OR_OVERRIDE",
        "non_claims": [
            "No standalone next-day UP/DOWN prediction.",
            "No weekly prediction, level, sweep, entry, stop, options-premium, or profitability claim.",
            "No claim that a VIX regime changes the locked v2 default decoder.",
        ],
    }
    return summary, observations, scorecard, direction


def _pct(value: Any) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{float(value):.2f}%"


def _markdown(summary: dict[str, Any], scorecard: pd.DataFrame, direction: pd.DataFrame) -> str:
    policy = summary["fitted_policy"]
    lines = [
        "# India VIX regime audit for the prediction-maker",
        "",
        "> Educational research, not investment advice. This tests a small, fixed",
        "> EOD VIX range/risk-context hypothesis—not an UP/DOWN trading signal.",
        "",
        f"## Decision: **{summary['overall_state']}**",
        "",
        "No VIX rule changes the locked v2 decoder or enables a standalone trade.",
        "The two rule gates below must independently pass in development, on 2025",
        "validation, and on 2026 confirmation before a rule could be shown as qualified",
        "report context.",
        "",
        "## Protocol locked before scoring",
        "",
        "- VIX close from the signal session is paired only with the following NIFTY",
        "  session's absolute close-to-close return.",
        f"- Development targets through **{policy['train_end']}** set every threshold",
        f"  (n={policy['train_rows']:,}); 2025 is validation and 2026 is confirmation.",
        f"- QUIET is VIX ≤ **{policy['quiet_vix_close_lte']:.4f}**; ELEVATED is VIX ≥ "
        f"**{policy['elevated_vix_close_gte']:.4f}**. The typical absolute move is "
        f"**{policy['typical_abs_return_pct']:.4f}%**.",
        f"- A claim needs at least {MIN_DEVELOPMENT_SIGNALS} development, "
        f"{MIN_VALIDATION_SIGNALS} validation, and {MIN_CONFIRMATION_SIGNALS} confirmation "
        f"calls, plus ≥{MIN_LIFT_PCT_POINTS:.0f} percentage-point hit-rate lift over the "
        "unconditional target frequency in each period.",
        "- A prior broad descriptive VIX correlation was seen. Neither 2025 nor 2026",
        "  fitted thresholds, but neither is described as a newly pristine blind sample.",
        "",
        "## Fixed range-context claims",
        "",
        "| Claim | Period | Calls | Hits | Hit rate | Unconditional target rate | Lift | Wilson 95% lower |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    labels = {"development": "Development through 2024", "validation_2025": "Validation 2025", "confirmation_2026": "Confirmation 2026"}
    for _, row in scorecard.iterrows():
        lines.append(
            f"| {row['claim']} | {labels[row['period']]} | {int(row['calls'])} | {int(row['hits'])} | "
            f"{_pct(row['hit_rate_pct'])} | {_pct(row['unconditional_target_rate_pct'])} | "
            f"{_pct(row['lift_pct_points'])} | {_pct(row['wilson_95_lower_pct'])} |"
        )
    lines += [
        "",
        "| Rule | Development checks | Validation checks | Confirmation checks | Gate state |",
        "|---|---|---|---|---|",
    ]
    for gate in summary["rule_gates"]:
        development = "PASS" if gate["development_sample_ok"] and gate["development_lift_ok"] else "no"
        validation = "PASS" if gate["validation_sample_ok"] and gate["validation_lift_ok"] else "no"
        confirmation = "PASS" if gate["confirmation_sample_ok"] and gate["confirmation_lift_ok"] else "no"
        lines.append(
            f"| {gate['rule']} | {development} | {validation} | {confirmation} | "
            f"{gate['state']} |"
        )

    lines += [
        "",
        "## Relationship, not direction",
        "",
        "| Period | Observations | VIX vs next absolute return (Spearman) | VIX vs next signed return (Spearman) |",
        "|---|---:|---:|---:|",
    ]
    for item in summary["correlations"]:
        lines.append(
            f"| {item['period']} | {item['observations']} | "
            f"{item['vix_vs_next_abs_return_spearman']} | {item['vix_vs_next_signed_return_spearman']} |"
        )
    lines += [
        "",
        "The signed-return association is shown to prevent a common category error:",
        "VIX is a volatility/range input here, not evidence for a next-day direction call.",
        "",
        "## v2 accuracy segmented by frozen VIX regime — descriptive only",
        "",
        "| Period | Regime | Observations | v2 exact 3-class | v2 directional coverage | Mean next absolute return |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for _, row in direction.iterrows():
        lines.append(
            f"| {row['period']} | {row['vix_regime']} | {int(row['observations'])} | "
            f"{_pct(row['v2_exact_3class_accuracy_pct'])} | "
            f"{_pct(row['v2_directional_coverage_pct'])} | {_pct(row['mean_next_abs_return_pct'])} |"
        )
    lines += [
        "",
        "This segmentation did **not** search for or adopt a VIX-based v2 filter/override.",
        "Given the report-card result that v2 is below its class baseline, stratifying",
        "the same history cannot establish a deployable directional improvement.",
        "",
        "## Reproducibility and limits",
        "",
        f"- Matched observations: {summary['date_coverage']['matched_prediction_observations']:,}; "
        f"VIX coverage: {summary['date_coverage']['vix']['start']} to "
        f"{summary['date_coverage']['vix']['end']} ({summary['date_coverage']['vix']['rows']:,} rows).",
        "- Inputs: committed `historical/participant_oi.csv`, `historical/nifty_ohlc.csv`,",
        "  and `historical/india_vix_ohlc.csv`, with hashes in `historical/manifest.json`.",
        "- VIX does not supply pre-open, option premium/spread, event, sector, exact",
        "  timestamped-level, execution, stop, or slippage evidence. It cannot repair",
        "  those separate validation gaps.",
        "- Continue prospective logging before any live report wording is changed.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participant-oi", default="historical/participant_oi.csv")
    parser.add_argument("--nifty-ohlc", default="historical/nifty_ohlc.csv")
    parser.add_argument("--india-vix-ohlc", default="historical/india_vix_ohlc.csv")
    parser.add_argument("--out", default="reports/india_vix_regime_audit")
    args = parser.parse_args()

    summary, observations, scorecard, direction = build_audit(
        Path(args.participant_oi), Path(args.nifty_ohlc), Path(args.india_vix_ohlc)
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(_markdown(summary, scorecard, direction))
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    observations.to_csv(out / "observations.csv", index=False)
    scorecard.to_csv(out / "rule_scorecard.csv", index=False)
    direction.to_csv(out / "v2_direction_by_regime.csv", index=False)
    print(f"wrote {out / 'report.md'}")
    print(f"decision: {summary['overall_state']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
