"""Build conditional next-day plans and positional context.

The next-day output branches over gap-up, flat, and gap-down opens because the
transcript says pre-open information determines the opening path.  Each branch
still requires a price/option-level hold, rejection, or 10-15 minute break.

For v2, the multi-session FII carry calculation is context only: the locked
five-session candidate failed confirmation, so production emits
``NO-VALIDATED-EDGE`` rather than a next-week directional forecast.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class Prediction:
    horizon: str
    direction: str
    confidence: float
    rationale: str
    scenarios: list
    key_levels: dict
    actionability: str = ""
    research_lean: str = ""
    level_predictions: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _direction(composite: float, threshold: float = 0.10) -> str:
    if composite >= 0.45:
        return "UP"
    if composite >= threshold:
        return "SIDEWAYS-UP"
    if composite <= -0.45:
        return "DOWN"
    if composite <= -threshold:
        return "SIDEWAYS-DOWN"
    return "RANGE"


def _rolling_positional(hist: Optional[pd.DataFrame], n: int = 5) -> Optional[float]:
    if hist is None or hist.empty or "positional_composite" not in hist:
        return None
    tail = hist.sort_values("date").tail(n)
    if tail.empty:
        return None
    weights = list(range(1, len(tail) + 1))
    vals = tail["positional_composite"].astype(float).tolist()
    return sum(v * w for v, w in zip(vals, weights, strict=True)) / sum(weights)


def _carry_trend(hist: Optional[pd.DataFrame], n: int = 5) -> str:
    """Describe how the FII index-fut net has trended (longs/shorts building)."""
    if hist is None or hist.empty or "fii_index_fut_net" not in hist:
        return ""
    tail = hist.sort_values("date").tail(n)
    if len(tail) < 2:
        return ""
    vals = tail["fii_index_fut_net"].astype(float).tolist()
    delta = vals[-1] - vals[0]
    if delta > 15000:
        return (f"FII index-fut net rose {delta:,.0f} over last {len(tail)} sessions "
                f"— longs building, upside brewing.")
    if delta < -15000:
        return (f"FII index-fut net fell {delta:,.0f} over last {len(tail)} sessions "
                f"— shorts building, downside pressure.")
    return (f"FII index-fut net roughly flat over last {len(tail)} sessions "
            f"— range likely between the put wall (support) and call wall (resistance).")


def _levels_summary(levels: dict) -> dict:
    return {
        "support": [
            level for level in levels.get("levels", [])
            if level["kind"] == "support"
        ][:4],
        "resistance": [
            level for level in levels.get("levels", [])
            if level["kind"] == "resistance"
        ][:4],
        "max_pain": levels.get("max_pain"),
        "pcr": levels.get("pcr"),
        "immediate_support": levels.get("immediate_support"),
        "immediate_resistance": levels.get("immediate_resistance"),
        "level_method": levels.get("level_method"),
        "level_method_warning": levels.get("level_method_warning"),
        "exact_institutional_formula_available": levels.get(
            "exact_institutional_formula_available", False
        ),
        "supplied_institutional_level_count": levels.get(
            "supplied_institutional_level_count", 0
        ),
    }


def _level_name(level: dict | None, fallback: str) -> str:
    if not level:
        return fallback
    source = str(level.get("source", "level")).replace("_", " ")
    return f"{float(level['strike']):.0f} ({source})"


def _next_target(ordered: list[dict], strike: float, upward: bool,
                 confluence_tolerance: float = 0.0,
                 source: str = "") -> dict | None:
    """Find the next level, skipping cross-source records in the same zone."""
    candidates = []
    for level in ordered:
        candidate_strike = float(level["strike"])
        is_in_direction = candidate_strike > strike if upward else candidate_strike < strike
        same_confluence_zone = (
            level.get("source", "") != source
            and abs(candidate_strike - strike) <= confluence_tolerance
        )
        if is_in_direction and not same_confluence_zone:
            candidates.append(level)
    if not candidates:
        return None
    def strike_value(level: dict) -> float:
        return float(level["strike"])

    return (min if upward else max)(candidates, key=strike_value)


def _level_predictions(levels: dict, decode_result) -> list[dict]:
    """Build a conditional decision tree for every disclosed level.

    A preferred branch reflects only the OI lean; it remains inactive until its
    stated candle/hold condition occurs. This is deliberately not a claim that
    price must react at the level.
    """
    ordered = sorted(
        [
            level for level in levels.get("levels", [])
            if level.get("kind") in {"support", "resistance", "pivot"}
            and level.get("strike") is not None
        ],
        key=lambda level: float(level["strike"]),
    )
    if not ordered:
        return []

    immediate_support = levels.get("immediate_support") or {}
    immediate_resistance = levels.get("immediate_resistance") or {}
    immediate_support_strike = immediate_support.get("strike")
    immediate_resistance_strike = immediate_resistance.get("strike")
    composite = float(decode_result.composite)
    conflict = bool(getattr(decode_result, "smart_money_conflict", False))
    zone_tolerance = float(levels.get("confluence_tolerance_points", 0.0) or 0.0)

    predictions = []
    for level in ordered:
        strike = float(level["strike"])
        kind = level["kind"]
        lower = _next_target(
            ordered,
            strike,
            upward=False,
            confluence_tolerance=zone_tolerance,
            source=level.get("source", ""),
        )
        upper = _next_target(
            ordered,
            strike,
            upward=True,
            confluence_tolerance=zone_tolerance,
            source=level.get("source", ""),
        )
        lower_name = _level_name(lower, "next lower level not available")
        upper_name = _level_name(upper, "next upper level not available")

        if kind == "support":
            hold = {
                "outcome": "BOUNCE_OR_RECLAIM_UP",
                "confirmation": (
                    "10-15 minute bullish rejection/reclaim; enter only on the "
                    "confirming candle high break"
                ),
                "target": upper_name,
            }
            break_branch = {
                "outcome": "BREAK_DOWN_AND_ROLE_FLIP",
                "confirmation": (
                    "10-15 minute bearish close below, failed reclaim, and candle low break"
                ),
                "target": lower_name,
            }
            if conflict or abs(composite) < 0.10:
                preferred = "WAIT_FOR_CONFIRMED_BRANCH"
            else:
                preferred = (
                    "HOLD_OR_RECLAIM" if composite > 0 else "BREAK_DOWN_AND_ROLE_FLIP"
                )
        elif kind == "resistance":
            hold = {
                "outcome": "REJECTION_DOWN",
                "confirmation": (
                    "10-15 minute bearish rejection; enter only on the confirming "
                    "candle low break"
                ),
                "target": lower_name,
            }
            break_branch = {
                "outcome": "BREAK_UP_AND_ROLE_FLIP",
                "confirmation": (
                    "10-15 minute bullish close above, successful retest, and candle high break"
                ),
                "target": upper_name,
            }
            if conflict or abs(composite) < 0.10:
                preferred = "WAIT_FOR_CONFIRMED_BRANCH"
            else:
                preferred = (
                    "BREAK_UP_AND_ROLE_FLIP" if composite > 0 else "REJECTION_DOWN"
                )
        else:
            hold = {
                "outcome": "HOLD_ABOVE",
                "confirmation": "10-15 minute hold/retest above with bullish candle high break",
                "target": upper_name,
            }
            break_branch = {
                "outcome": "HOLD_BELOW",
                "confirmation": "10-15 minute hold/retest below with bearish candle low break",
                "target": lower_name,
            }
            preferred = "WAIT_FOR_CONFIRMED_BRANCH"

        is_immediate = strike in {
            float(immediate_support_strike) if immediate_support_strike is not None else None,
            float(immediate_resistance_strike) if immediate_resistance_strike is not None else None,
        }
        predictions.append({
            "strike": strike,
            "kind": kind,
            "source": level.get("source", "option_chain_proxy"),
            "basis": level.get("basis", ""),
            "evidence_grade": level.get("evidence_grade", ""),
            "evidence_score": level.get("evidence_score"),
            "confluence": bool(level.get("confluence", False)),
            "confluence_note": level.get("confluence_note", ""),
            "priority": "IMMEDIATE" if is_immediate else "SECONDARY",
            "oi_lean_preferred_branch": preferred,
            "hold_or_reject_branch": hold,
            "break_branch": break_branch,
            "gap_rule": (
                "If price opens and sustains beyond this level, do not assume a delayed "
                "reaction here; treat it as skipped/flipped and evaluate the next level."
            ),
            "cascade_rule": (
                "Once an opposite-direction break invalidates the original OI lean, ignore "
                "its preferred branches at later levels and follow confirmed price action only."
            ),
            "no_confirmation": "WAIT / NO TRADE AT THIS LEVEL",
        })
    return predictions


def _gap_scenarios(levels: dict, decode_result) -> list:
    """The three-open scenario tree Amit builds (Gap Up / Flat / Gap Down)."""
    sup = levels.get("immediate_support")
    res = levels.get("immediate_resistance")
    if not sup or not res:
        return [{
            "open": "DATA BLOCK",
            "plan": (
                "No same-date support/resistance pair is available. Preserve the OI "
                "lean as context only; do not create a gap or level trade from stale data."
            ),
        }]
    sup_s = f"{sup['strike']:.0f}"
    res_s = f"{res['strike']:.0f}"
    bullish = decode_result.composite > 0

    out = [
        {
            "open": "GAP DOWN",
            "plan": (
                f"Evaluate support {sup_s}; do not buy merely because price reached it. "
                f"A liquidity sweep followed by a confirmed reclaim activates the bounce "
                f"branch. Independently supplied institutional/psychological confluence "
                f"strengthens the setup. A sustained bearish break BELOW {sup_s} flips it "
                f"to resistance and activates the next lower level.")
        },
        {
            "open": "FLAT",
            "plan": (
                f"Treat {sup_s} to {res_s} as the decision band. A confirmed support "
                f"reclaim activates the bounce branch; confirmed resistance rejection "
                f"activates the fade branch. Without either candle, wait. Direction changes "
                f"only when a wall breaks and sustains.")
        },
        {
            "open": "GAP UP",
            "plan": (
                f"Evaluate resistance {res_s}. Confirmed rejection activates a move toward "
                f"{sup_s}; a decisive 15-minute close and retest ABOVE {res_s} means the "
                f"call-side concentration gave way and activates the next upper level.")
        },
    ]
    # Emphasise a conditional branch without forecasting the opening path.
    if getattr(decode_result, "smart_money_conflict", False):
        out.insert(0, {"open": "NOTE",
                       "plan": decode_result.conflict_note})
    elif abs(decode_result.composite) < 0.10:
        out.insert(0, {
            "open": "PRIMARY",
            "plan": (
                "No OI branch is preferred. Wait for a confirmed hold/rejection or "
                "break/role-flip at the relevant level."
            ),
        })
    elif bullish:
        out.insert(0, {
            "open": "PRIMARY",
            "plan": (
                f"Bullish OI context prefers a confirmed hold/reclaim at {sup_s} or a "
                f"confirmed break/retest above {res_s}; it does not forecast that either "
                f"path must occur."
            ),
        })
    else:
        out.insert(0, {
            "open": "PRIMARY",
            "plan": (
                f"Bearish OI context prefers a confirmed rejection at {res_s} or a "
                f"confirmed break/failed reclaim below {sup_s}; it does not forecast "
                f"that either path must occur."
            ),
        })
    return out


def build_predictions(decode_result, levels: Optional[dict],
                      decoded_history: Optional[pd.DataFrame] = None) -> dict:
    levels = levels or {}
    key_levels = _levels_summary(levels)
    level_predictions = _level_predictions(levels, decode_result)
    version = getattr(decode_result, "method_version", "v1")
    threshold = {"v1": 0.12, "v3": 0.0}.get(version, 0.10)

    # ---- Next day (Pro-led) ----
    # This is the forced OI-only research class used by the historical audit. V2
    # separately says whether it is actionable; every actual trade still needs the
    # transcript's price/level confirmation.
    nd_dir = _direction(decode_result.composite, threshold)
    nd_action = getattr(decode_result, "actionability", "LEGACY_UNCONDITIONAL")
    nd = Prediction(
        horizon="next_day",
        direction=nd_dir,
        confidence=decode_result.confidence,
        rationale=(
            f"OI-only next-day research lean {decode_result.composite:+.2f} "
            f"({decode_result.bias}), Pro-led (ultra-short). "
            f"{getattr(decode_result, 'setup_note', '')} {decode_result.retail_note} "
            f"Move quality: {decode_result.move_quality}. "
            f"PCR {levels.get('pcr','n/a')} — {levels.get('pcr_signal','')}"),
        scenarios=_gap_scenarios(levels, decode_result),
        key_levels=key_levels,
        actionability=nd_action,
        research_lean=nd_dir,
        level_predictions=level_predictions,
    )

    # ---- Next week / positional (FII-led) ----
    momentum = _rolling_positional(decoded_history)
    base = decode_result.positional_composite
    weekly = base if momentum is None else (0.55 * base + 0.45 * momentum)
    research_lean = _direction(weekly, threshold)
    carry = _carry_trend(decoded_history)

    if version == "v1":
        # Exact legacy behaviour for reproducible v1 replay.
        nw_dir = research_lean
        nw_conf = round(min(100, decode_result.positional_confidence * 0.85
                            + (abs(momentum) * 20 if momentum else 0)), 1)
        nw_action = "LEGACY_UNCONDITIONAL"
        validation_note = ""
    else:
        # The transcript-grounded FII carry/trend candidate improved 2025 but
        # failed 2026 confirmation. Do not promote it to a directional forecast.
        nw_dir = "NO-VALIDATED-EDGE"
        nw_conf = 0.0
        nw_action = "CONTEXT_ONLY_WAIT_FOR_MULTI_SESSION_CONFIRMATION"
        validation_note = (
            " The carry/trend lean is shown as research context only: its locked "
            "five-session candidate did not survive the 2026 confirmation period."
        )

    nw = Prediction(
        horizon="next_week",
        direction=nw_dir,
        confidence=nw_conf,
        rationale=(
            f"Positional carry context {weekly:+.2f} (research lean {research_lean}), "
            f"FII-led with Pro support required. "
            f"{'Momentum ' + format(momentum, '+.2f') + '. ' if momentum is not None else ''}"
            f"{carry} Big positional moves come only 2-3x a year; otherwise the week "
            f"trades between the put wall (support) and call wall (resistance) unless a "
            f"wall breaks decisively. Retail must unwind longs before a sustained up-leg."
            f"{validation_note}"),
        scenarios=[
            {"trigger": "FII carry longs build over several sessions + Pro supports",
             "then": "Bullish context only; require price/level confirmation."},
            {"trigger": "FII carry shorts build over several sessions + Pro supports",
             "then": "Bearish context only; require price/level confirmation."},
            {"trigger": "FII and Pro oppose, or Retail remains crowded",
             "then": "No positional entry; expect range/whipsaw until the conflict resolves."},
        ],
        key_levels=key_levels,
        actionability=nw_action,
        research_lean=research_lean,
    )

    return {"next_day": nd.to_dict(), "next_week": nw.to_dict()}
