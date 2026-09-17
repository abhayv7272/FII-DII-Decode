"""Build conditional next-day plans and positional context.

The next-day output branches over gap-up, flat, and gap-down opens because the
transcript says pre-open information determines the opening path.  Each branch
still requires a price/option-level hold, rejection, or 10-15 minute break.

For v2, the multi-session FII carry calculation is context only: the locked
five-session candidate failed confirmation, so production emits
``NO-VALIDATED-EDGE`` rather than a next-week directional forecast.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
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
    return sum(v * w for v, w in zip(vals, weights)) / sum(weights)


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
        "support": [l for l in levels.get("levels", []) if l["kind"] == "support"][:4],
        "resistance": [l for l in levels.get("levels", []) if l["kind"] == "resistance"][:4],
        "max_pain": levels.get("max_pain"),
        "pcr": levels.get("pcr"),
        "immediate_support": levels.get("immediate_support"),
        "immediate_resistance": levels.get("immediate_resistance"),
    }


def _gap_scenarios(levels: dict, decode_result) -> list:
    """The three-open scenario tree Amit builds (Gap Up / Flat / Gap Down)."""
    sup = levels.get("immediate_support")
    res = levels.get("immediate_resistance")
    sup_s = f"{sup['strike']:.0f}" if sup else "nearest put wall"
    res_s = f"{res['strike']:.0f}" if res else "nearest call wall"
    bullish = decode_result.composite > 0

    out = [
        {
            "open": "GAP DOWN",
            "plan": (
                f"Ideal for a long setup if Smart Money is bullish. Market likely digs "
                f"toward support {sup_s} (may even SWEEP liquidity just below a round "
                f"figure to grab retail stop-losses), then REVERSES up — that liquidity "
                f"sweep + institutional level + psychological level is the transcript's "
                f"preferred long confluence. A sustained close BELOW {sup_s} with bearish volume "
                f"flips it to resistance → continuation DOWN.")
        },
        {
            "open": "FLAT",
            "plan": (
                f"Trade the band: buy dips into support {sup_s} (hold → bounce), sell "
                f"rallies into resistance {res_s} (reject → fade). Direction resolves on "
                f"which wall breaks with follow-through.")
        },
        {
            "open": "GAP UP",
            "plan": (
                f"Watch resistance {res_s}. Rejection → fade back toward {sup_s}. A "
                f"decisive 15-min close ABOVE {res_s} (call writers unwinding) → "
                f"breakout continuation UP toward the next call wall.")
        },
    ]
    # Emphasise the likely primary path.
    if decode_result.smart_money_conflict:
        out.insert(0, {"open": "NOTE",
                       "plan": decode_result.conflict_note})
    elif bullish:
        out.insert(0, {"open": "PRIMARY",
                       "plan": (f"Bias up but if retail is crowded long, the transcript's "
                                f"preferred 'sell-on-rise / dip-then-recover' path is a dip "
                                f"into {sup_s} followed by a confirmed reversal.")})
    else:
        out.insert(0, {"open": "PRIMARY",
                       "plan": (f"Bias down: rallies into {res_s} likely sold; "
                                f"a break below {sup_s} opens further downside.")})
    return out


def build_predictions(decode_result, levels: Optional[dict],
                      decoded_history: Optional[pd.DataFrame] = None) -> dict:
    levels = levels or {}
    key_levels = _levels_summary(levels)
    version = getattr(decode_result, "method_version", "v1")
    threshold = 0.12 if version == "v1" else 0.10

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
