#!/usr/bin/env python3
"""Reproduce the locked v1-vs-v2 chronological comparison on real archives.

The script never fetches current data and never fits against validation periods.
It expects a directory/ZIP/consolidated CSV of dated Participant-OI reports and a
directory/ZIP/CSV of dated NIFTY OHLC, then writes auditable per-date and summary
artifacts.

The v2 rule constants were selected from the transcripts and 2023-2024 development
period before 2025 validation and 2026 confirmation were evaluated. The separate
five-session carry-trend candidate is included only to document its rejection; v2
production intentionally emits NO-VALIDATED-EDGE for that horizon.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date
import json
from math import comb, sqrt, tanh
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
from fiidii.decode import (  # noqa: E402
    CLOSE_POSITION_WEIGHT,
    CONFLICT_THRESHOLD,
    DIRECTION_THRESHOLD,
    INDEX_FLOW_SCALE,
    NEXT_DAY_INSTRUMENT_WEIGHT,
    NEXT_DAY_PARTICIPANT_WEIGHT,
)
from fiidii.legacy_v1 import decode as decode_v1  # noqa: E402
from fiidii.predict import build_predictions  # noqa: E402


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
WEEKLY_FLAT_THRESHOLD = 0.50
WEEKLY_SCORE_THRESHOLD = 0.20
DAILY_FLAT_THRESHOLD = 0.15


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator * 100.0, 2) if denominator else None


def _actual(values: pd.Series, threshold: float) -> pd.Series:
    return values.map(lambda value: "UP" if value > threshold else
                      "DOWN" if value < -threshold else "FLAT")


def _wilson(hits: int, samples: int) -> tuple[float | None, float | None]:
    if not samples:
        return None, None
    z = 1.959963984540054
    p = hits / samples
    denominator = 1 + z * z / samples
    centre = (p + z * z / (2 * samples)) / denominator
    half = z * sqrt((p * (1 - p) + z * z / (4 * samples)) / samples) / denominator
    return round((centre - half) * 100, 2), round((centre + half) * 100, 2)


def _binomial_two_sided(hits: int, samples: int) -> float | None:
    if not samples:
        return None
    observed = comb(samples, hits)
    numerator = sum(comb(samples, value) for value in range(samples + 1)
                    if comb(samples, value) <= observed)
    return round(numerator / (2 ** samples), 6)


def _period_mask(frame: pd.DataFrame, years: set[int] | None) -> pd.Series:
    if years is None:
        return pd.Series(True, index=frame.index)
    return pd.to_datetime(frame["target_date"]).dt.year.isin(years)


def _daily_row(frame: pd.DataFrame, version: str, period: str,
               basis: str, return_column: str) -> dict:
    values = pd.to_numeric(frame[return_column], errors="coerce")
    valid = values.notna()
    sample = frame.loc[valid].copy()
    actual = _actual(values.loc[valid], DAILY_FLAT_THRESHOLD)
    predicted = sample["predicted_class"]
    directional = predicted.isin(["UP", "DOWN"])
    nonflat = directional & actual.isin(["UP", "DOWN"])
    directional_hits = int((predicted[directional] == actual[directional]).sum())
    sign_hits = int((predicted[nonflat] == actual[nonflat]).sum())
    low, high = _wilson(sign_hits, int(nonflat.sum()))

    if version == "v2":
        eligible = directional & sample["actionability"].str.startswith("CONDITIONAL_")
    else:
        eligible = directional
    eligible_nonflat = eligible & actual.isin(["UP", "DOWN"])
    eligible_hits = int((predicted[eligible] == actual[eligible]).sum())
    eligible_sign_hits = int((predicted[eligible_nonflat] == actual[eligible_nonflat]).sum())
    eligible_low, eligible_high = _wilson(eligible_sign_hits, int(eligible_nonflat.sum()))

    counts = actual.value_counts()
    return {
        "version": version,
        "period": period,
        "return_basis": basis,
        "samples": len(sample),
        "forced_exact_hits": int((predicted == actual).sum()),
        "forced_exact_accuracy_pct": _rate(int((predicted == actual).sum()), len(sample)),
        "majority_baseline_pct": _rate(int(counts.max()), len(sample)),
        "directional_calls": int(directional.sum()),
        "directional_coverage_pct": _rate(int(directional.sum()), len(sample)),
        "directional_hits_including_flat_misses": directional_hits,
        "directional_hit_rate_including_flat_misses_pct": _rate(
            directional_hits, int(directional.sum())
        ),
        "nonflat_directional_samples": int(nonflat.sum()),
        "nonflat_sign_hits": sign_hits,
        "nonflat_sign_accuracy_pct": _rate(sign_hits, int(nonflat.sum())),
        "nonflat_sign_ci95_low_pct": low,
        "nonflat_sign_ci95_high_pct": high,
        "nonflat_sign_p_two_sided": _binomial_two_sided(sign_hits, int(nonflat.sum())),
        "trigger_eligible_calls": int(eligible.sum()),
        "trigger_eligible_coverage_pct": _rate(int(eligible.sum()), len(sample)),
        "trigger_eligible_hits_including_flat_misses": eligible_hits,
        "trigger_eligible_hit_rate_including_flat_misses_pct": _rate(
            eligible_hits, int(eligible.sum())
        ),
        "trigger_eligible_nonflat_samples": int(eligible_nonflat.sum()),
        "trigger_eligible_nonflat_sign_hits": eligible_sign_hits,
        "trigger_eligible_nonflat_sign_accuracy_pct": _rate(
            eligible_sign_hits, int(eligible_nonflat.sum())
        ),
        "trigger_eligible_nonflat_ci95_low_pct": eligible_low,
        "trigger_eligible_nonflat_ci95_high_pct": eligible_high,
    }


def daily_comparison(v1: pd.DataFrame, v2: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    periods = {"full": None, **PERIODS}
    for version, frame in (("v1", v1), ("v2", v2)):
        for period, years in periods.items():
            selected = frame.loc[_period_mask(frame, years)]
            for basis, return_column in RETURN_BASES.items():
                rows.append(_daily_row(selected, version, period, basis, return_column))
    return pd.DataFrame(rows)


def strength_breakdown(v2: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    periods = {"full": None, **PERIODS}
    for period, years in periods.items():
        frame = v2.loc[_period_mask(v2, years)]
        actual = frame["actual_class"]
        for minimum in (0, 20, 40, 60, 80):
            selected = (
                frame["predicted_class"].isin(["UP", "DOWN"])
                & frame["actionability"].str.startswith("CONDITIONAL_")
                & (frame["setup_strength"] >= minimum)
            )
            nonflat = selected & actual.isin(["UP", "DOWN"])
            hits = int((frame.loc[nonflat, "predicted_class"] == actual[nonflat]).sum())
            low, high = _wilson(hits, int(nonflat.sum()))
            rows.append({
                "period": period,
                "minimum_setup_strength": minimum,
                "trigger_eligible_calls": int(selected.sum()),
                "coverage_pct": _rate(int(selected.sum()), len(frame)),
                "nonflat_samples": int(nonflat.sum()),
                "nonflat_sign_hits": hits,
                "nonflat_sign_accuracy_pct": _rate(hits, int(nonflat.sum())),
                "ci95_low_pct": low,
                "ci95_high_pct": high,
            })
    return pd.DataFrame(rows)


def _participants_present(frame: pd.DataFrame) -> set[str]:
    return set(frame["ClientType"].astype(str).str.upper())


def _eligible_signal_dates(oi: pd.DataFrame, prices: pd.DataFrame) -> list[date]:
    market_dates = prices["date"].tolist()
    market_index = {value: index for index, value in enumerate(market_dates)}
    oi_dates = set(oi["date"])
    present = {value: _participants_present(group) for value, group in oi.groupby("date")}
    out = []
    for signal_date in sorted(oi_dates):
        index = market_index.get(signal_date)
        if index is None or index == 0 or index >= len(market_dates) - 1:
            continue
        previous = market_dates[index - 1]
        if previous not in oi_dates:
            continue
        if not {"CLIENT", "FII", "PRO"}.issubset(present[signal_date]):
            continue
        if not {"CLIENT", "FII", "PRO"}.issubset(present[previous]):
            continue
        out.append(signal_date)
    return out


def _v1_weekly(oi: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    groups = {value: group.reset_index(drop=True) for value, group in oi.groupby("date")}
    market_dates = prices["date"].tolist()
    market_index = {value: index for index, value in enumerate(market_dates)}
    price = prices.set_index("date")
    history: list[dict] = []
    rows: list[dict] = []
    for signal_date in _eligible_signal_dates(oi, prices):
        index = market_index[signal_date]
        previous = market_dates[index - 1]
        decoded = decode_v1(groups[signal_date], groups[previous], date_str=signal_date.isoformat())
        hist = pd.DataFrame(history)
        prediction = build_predictions(decoded, {}, hist)["next_week"]
        if index + 5 < len(market_dates):
            target = market_dates[index + 5]
            realised = (float(price.loc[target, "close"]) /
                        float(price.loc[signal_date, "close"]) - 1) * 100
            rows.append({
                "signal_date": signal_date,
                "target_date": target,
                "predicted_class": (
                    "UP" if prediction["direction"] in {"UP", "SIDEWAYS-UP"}
                    else "DOWN" if prediction["direction"] in {"DOWN", "SIDEWAYS-DOWN"}
                    else "FLAT"
                ),
                "actual_return_pct": realised,
            })
        history.append({
            "date": signal_date.isoformat(),
            "positional_composite": decoded.positional_composite,
            "fii_index_fut_net": decoded.metrics.get("fii_index_fut_net"),
        })
    return pd.DataFrame(rows)


WEEKLY_INSTRUMENTS = {
    "index_call": ("Option Index Call Long", "Option Index Call Short", 1.0, 0.375, 0.05),
    "index_put": ("Option Index Put Long", "Option Index Put Short", -1.0, 0.375, 0.05),
    "index_fut": ("Future Index Long", "Future Index Short", 1.0, 0.25, 0.10),
}


def _v2_weekly_candidate(oi: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    groups = {value: group.set_index(group["ClientType"].str.lower())
              for value, group in oi.groupby("date")}
    market_dates = prices["date"].tolist()
    market_index = {value: index for index, value in enumerate(market_dates)}
    price = prices.set_index("date")
    features: list[dict] = []
    for signal_date in _eligible_signal_dates(oi, prices):
        group = groups[signal_date]
        row: dict = {"signal_date": signal_date}
        for participant in ("fii", "pro", "client"):
            for name, (long_col, short_col, direction, _, _) in WEEKLY_INSTRUMENTS.items():
                total = max(float(group.loc["total", long_col]),
                            float(group.loc["total", short_col]), 1.0)
                row[f"{participant}_{name}"] = direction * (
                    float(group.loc[participant, long_col])
                    - float(group.loc[participant, short_col])
                ) / total
        features.append(row)
    frame = pd.DataFrame(features)
    scores = []
    for index in range(len(frame)):
        participant_scores: dict[str, float] = {}
        for participant in ("fii", "pro", "client"):
            score = 0.0
            for name, (_, _, _, weight, scale) in WEEKLY_INSTRUMENTS.items():
                current = frame.loc[index, f"{participant}_{name}"]
                previous = frame.loc[index - 5, f"{participant}_{name}"] if index >= 5 else current
                score += weight * tanh((current - previous) / scale)
            participant_scores[participant] = score
        scores.append(
            0.60 * participant_scores["fii"]
            + 0.25 * participant_scores["pro"]
            - 0.15 * participant_scores["client"]
        )
    frame["score"] = scores
    frame["predicted_class"] = frame["score"].map(
        lambda score: (
            "UP" if score > WEEKLY_SCORE_THRESHOLD
            else "DOWN" if score < -WEEKLY_SCORE_THRESHOLD
            else "FLAT"
        )
    )
    targets, returns = [], []
    for signal_date in frame["signal_date"]:
        index = market_index[signal_date]
        if index + 5 >= len(market_dates):
            targets.append(None)
            returns.append(None)
            continue
        target = market_dates[index + 5]
        targets.append(target)
        returns.append((float(price.loc[target, "close"]) /
                        float(price.loc[signal_date, "close"]) - 1) * 100)
    frame["target_date"] = targets
    frame["actual_return_pct"] = returns
    return frame.dropna(subset=["target_date", "actual_return_pct"])


def _weekly_metrics(frame: pd.DataFrame, version: str, period: str) -> dict:
    actual = _actual(frame["actual_return_pct"], WEEKLY_FLAT_THRESHOLD)
    predicted = frame["predicted_class"]
    directional = predicted.isin(["UP", "DOWN"])
    nonflat = directional & actual.isin(["UP", "DOWN"])
    hits = int((predicted[nonflat] == actual[nonflat]).sum())
    low, high = _wilson(hits, int(nonflat.sum()))
    counts = actual.value_counts()
    return {
        "version": version,
        "status": "production" if version == "v1" else "rejected_candidate",
        "period": period,
        "samples": len(frame),
        "exact_accuracy_pct": _rate(int((predicted == actual).sum()), len(frame)),
        "majority_baseline_pct": _rate(int(counts.max()), len(frame)),
        "directional_calls": int(directional.sum()),
        "directional_coverage_pct": _rate(int(directional.sum()), len(frame)),
        "directional_hit_rate_including_flat_misses_pct": _rate(
            int((predicted[directional] == actual[directional]).sum()), int(directional.sum())
        ),
        "nonflat_samples": int(nonflat.sum()),
        "nonflat_sign_hits": hits,
        "nonflat_sign_accuracy_pct": _rate(hits, int(nonflat.sum())),
        "ci95_low_pct": low,
        "ci95_high_pct": high,
    }


def weekly_comparison(oi: pd.DataFrame, prices: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    v1 = _v1_weekly(oi, prices)
    v2 = _v2_weekly_candidate(oi, prices)
    rows = []
    periods = {"full": None, **PERIODS}
    for version, frame in (("v1", v1), ("v2_candidate", v2)):
        for period, years in periods.items():
            selected = frame if years is None else frame[
                pd.to_datetime(frame["target_date"]).dt.year.isin(years)
            ]
            rows.append(_weekly_metrics(selected, version, period))
    return pd.DataFrame(rows), v1, v2


def _fmt(value) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{float(value):.2f}%"


def _daily_table(comparison: pd.DataFrame, basis: str) -> list[str]:
    lines = [
        "| Period | Version | N | Exact | Baseline | Dir. coverage | Dir. hit incl. FLAT | Non-FLAT sign | 95% CI | Trigger-eligible sign |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    selected = comparison[comparison["return_basis"] == basis]
    order = ["2023-2024 development", "2025 validation", "2026 confirmation", "full"]
    for period in order:
        for version in ("v1", "v2"):
            row = selected[(selected["period"] == period) & (selected["version"] == version)].iloc[0]
            lines.append(
                f"| {period} | {version} | {int(row['samples'])} | "
                f"{_fmt(row['forced_exact_accuracy_pct'])} | {_fmt(row['majority_baseline_pct'])} | "
                f"{_fmt(row['directional_coverage_pct'])} | "
                f"{_fmt(row['directional_hit_rate_including_flat_misses_pct'])} | "
                f"{_fmt(row['nonflat_sign_accuracy_pct'])} ({int(row['nonflat_directional_samples'])}) | "
                f"{_fmt(row['nonflat_sign_ci95_low_pct'])}-{_fmt(row['nonflat_sign_ci95_high_pct'])} | "
                f"{_fmt(row['trigger_eligible_nonflat_sign_accuracy_pct'])} "
                f"({int(row['trigger_eligible_nonflat_samples'])}) |"
            )
    return lines


def render_report(comparison: pd.DataFrame, strength: pd.DataFrame,
                  weekly: pd.DataFrame, v1_result, v2_result,
                  source_note: str) -> str:
    full_close = comparison[(comparison["period"] == "full") &
                            (comparison["return_basis"] == "close_to_close")]
    v1 = full_close[full_close["version"] == "v1"].iloc[0]
    v2 = full_close[full_close["version"] == "v2"].iloc[0]
    lines = [
        "# Transcript-grounded v2 historical comparison",
        "",
        "> Point-in-time research replay, not a P&L result and not investment advice. "
        "V2 was specified from the transcripts plus 2023-2024 development before 2025 "
        "validation and 2026 confirmation were inspected. The repository's earlier v1 "
        "audit had already exposed 2026, so 2026 is confirmation—not a pristine holdout.",
        "",
        "## Decision",
        "",
        f"V2 raises full-sample close-to-close exact classification from "
        f"**{v1['forced_exact_accuracy_pct']:.2f}%** to **{v2['forced_exact_accuracy_pct']:.2f}%**, "
        f"but still trails the **{v2['majority_baseline_pct']:.2f}%** majority baseline. "
        "Its open-to-close sign is still approximately chance. The changes are retained "
        "because they correct transcript mistranslations and improve several development/"
        "confirmation diagnostics, not because they validate a trading edge.",
        "",
        "Production v2 now marks FII/Pro conflicts as `WAIT_FOR_REVERSAL_CONFIRMATION`, "
        "weak scores as `NO_DIRECTIONAL_EDGE`, and all other leans as conditional on a "
        "10-15 minute price/level trigger. Setup strength is not a probability.",
        "",
        "## Locked v2 changes",
        "",
        "1. Fresh additions receive full weight; short covering/long unwinding receive half weight.",
        "2. Flows are divided by current instrument market OI; fixed contract-count scales are removed.",
        "3. NIFTY next-day direction uses index calls (40%), index puts (40%), and index futures (20%).",
        "4. Pro:FII is 2:1 inside the 80% Smart-Money share; contra-Retail is 20%; DII F&O is ignored.",
        "5. Stock derivatives remain diagnostics but cannot manufacture a NIFTY next-day direction.",
        "6. Forced research classes use a locked ±0.10 score boundary; actionability separately removes conflicts.",
        "7. Cash and option-chain levels are confirmation-only unless date-matched history is supplied.",
        "",
        "See `docs/transcript-audit-v2.md` for timestamp/page evidence and each v1 mapping error.",
        "",
        "## Daily close-to-close (±0.15% FLAT band)",
        "",
        *_daily_table(comparison, "close_to_close"),
        "",
        "## Following open-to-close (±0.15% FLAT band)",
        "",
        *_daily_table(comparison, "next_open_to_close"),
        "",
        "The open-to-close basis is the more realistic executable-direction diagnostic "
        "because Participant-OI is published after the signal session. Neither version "
        "establishes a reliable edge on it.",
        "",
        "## Overnight gap (±0.15% FLAT band)",
        "",
        *_daily_table(comparison, "overnight_gap"),
        "",
        "The transcript says pre-open news/Gift Nifty decides the opening order and can "
        "override EOD OI. Historical pre-open inputs were unavailable, so the gap result "
        "is an association—not an executable forecast claim.",
        "",
        "## V2 setup strength is not calibrated confidence",
        "",
        "| Period | Minimum strength | Eligible calls | Coverage | Non-FLAT sign | 95% CI |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for period in ["2023-2024 development", "2025 validation", "2026 confirmation", "full"]:
        for minimum in (0, 40, 60, 80):
            row = strength[(strength["period"] == period) &
                           (strength["minimum_setup_strength"] == minimum)].iloc[0]
            lines.append(
                f"| {period} | {minimum} | {int(row['trigger_eligible_calls'])} | "
                f"{_fmt(row['coverage_pct'])} | {_fmt(row['nonflat_sign_accuracy_pct'])} "
                f"({int(row['nonflat_samples'])}) | {_fmt(row['ci95_low_pct'])}-"
                f"{_fmt(row['ci95_high_pct'])} |"
            )
    lines += [
        "",
        "Strength was somewhat useful in development and 2025, but the relationship "
        "reversed in 2026. Raising the displayed score must not be interpreted as raising "
        "the probability of a correct trade.",
        "",
        "## Five-session candidate (±0.20 score boundary; ±0.50% FLAT band)",
        "",
        "| Period | Version/status | N | Exact | Baseline | Coverage | Dir. hit incl. FLAT | Non-FLAT sign | 95% CI |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    order = ["2023-2024 development", "2025 validation", "2026 confirmation", "full"]
    for period in order:
        for version in ("v1", "v2_candidate"):
            row = weekly[(weekly["period"] == period) & (weekly["version"] == version)].iloc[0]
            lines.append(
                f"| {period} | {version} / {row['status']} | {int(row['samples'])} | "
                f"{_fmt(row['exact_accuracy_pct'])} | {_fmt(row['majority_baseline_pct'])} | "
                f"{_fmt(row['directional_coverage_pct'])} | "
                f"{_fmt(row['directional_hit_rate_including_flat_misses_pct'])} | "
                f"{_fmt(row['nonflat_sign_accuracy_pct'])} ({int(row['nonflat_samples'])}) | "
                f"{_fmt(row['ci95_low_pct'])}-{_fmt(row['ci95_high_pct'])} |"
            )
    lines += [
        "",
        "The transcript-correct carry-trend candidate improved 2025 but failed 2026 "
        "confirmation; it was rejected. Production v2 therefore reports positional carry "
        "as context and emits `NO-VALIDATED-EDGE` instead of a standalone weekly direction.",
        "",
        "## Data and limitations",
        "",
        f"- {source_note}",
        f"- V1 evaluated {len(v1_result.predictions)} dates; v2 evaluated {len(v2_result.predictions)}; "
        f"both skipped {len(v2_result.skipped)} dates under the same point-in-time rules.",
        "- Participant-OI combines NIFTY, Bank Nifty, Fin Nifty, Midcap Nifty, all expiries, and hedges.",
        "- No historical date-matched option chains, FII/DII cash flow, Gift Nifty, global macro snapshot, or 10-15 minute trigger candles were available.",
        "- Daily OHLC cannot verify move order, a liquidity sweep, candle confirmation, stop execution, slippage, fees, or P&L.",
        "- V2 setup strength is a deterministic score intensity, not calibrated confidence.",
        "- Future untouched forward validation remains required.",
        "",
        "## Reproduction outputs",
        "",
        "- `v1_predictions.csv` / `v2_predictions.csv`: every forced daily class and realised bar.",
        "- `daily_comparison.csv`: every period × return basis metric above.",
        "- `v2_strength_breakdown.csv`: trigger-eligible sign diagnostics by setup-strength floor.",
        "- `v1_five_session_predictions.csv` / `rejected_v2_five_session_candidate.csv`.",
        "- `weekly_comparison.csv`: five-session stability and rejection evidence.",
        "- `run_config.json`: declared thresholds and input locations.",
        "",
        "_Educational research only; not investment advice._",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--participant-oi", required=True)
    parser.add_argument("--ohlc", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--source-note", default="Real dated archives supplied by the operator.")
    args = parser.parse_args(argv)

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    oi = load_participant_oi(args.participant_oi)
    prices = load_ohlc(args.ohlc, symbol="NIFTY")
    v1_result = run_backtest(oi, prices, config=BacktestConfig(decoder_version="v1"))
    v2_result = run_backtest(oi, prices, config=BacktestConfig(decoder_version="v2"))
    comparison = daily_comparison(v1_result.predictions, v2_result.predictions)
    strength = strength_breakdown(v2_result.predictions)
    weekly, v1_weekly, v2_weekly = weekly_comparison(oi, prices)

    v1_result.predictions.to_csv(output / "v1_predictions.csv", index=False)
    v2_result.predictions.to_csv(output / "v2_predictions.csv", index=False)
    v2_result.skipped.to_csv(output / "skipped.csv", index=False)
    comparison.to_csv(output / "daily_comparison.csv", index=False)
    strength.to_csv(output / "v2_strength_breakdown.csv", index=False)
    weekly.to_csv(output / "weekly_comparison.csv", index=False)
    v1_weekly.to_csv(output / "v1_five_session_predictions.csv", index=False)
    v2_weekly.to_csv(output / "rejected_v2_five_session_candidate.csv", index=False)

    config = {
        "participant_oi": args.participant_oi,
        "ohlc": args.ohlc,
        "daily_flat_threshold_pct": DAILY_FLAT_THRESHOLD,
        "weekly_flat_threshold_pct": WEEKLY_FLAT_THRESHOLD,
        "periods": {key: sorted(value) for key, value in PERIODS.items()},
        "v1_config": asdict(v1_result.config),
        "v2_config": asdict(v2_result.config),
        "v2_daily_rule": {
            "direction_threshold": DIRECTION_THRESHOLD,
            "conflict_threshold_per_participant": CONFLICT_THRESHOLD,
            "closure_weight": CLOSE_POSITION_WEIGHT,
            "relative_index_flow_scale": INDEX_FLOW_SCALE,
            "instrument_weights": NEXT_DAY_INSTRUMENT_WEIGHT,
            "participant_weights": NEXT_DAY_PARTICIPANT_WEIGHT,
        },
        "weekly_candidate": {
            "status": "rejected_after_2026_confirmation",
            "score_threshold": WEEKLY_SCORE_THRESHOLD,
            "lookback_sessions": 5,
            "instrument_parameters": WEEKLY_INSTRUMENTS,
        },
        "source_note": args.source_note,
    }
    (output / "run_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    report = render_report(
        comparison, strength, weekly, v1_result, v2_result, args.source_note
    )
    (output / "report.md").write_text(report, encoding="utf-8")
    print(f"Wrote v1-v2 comparison to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
