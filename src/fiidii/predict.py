"""Assemble next-day and next-week predictions from decode + levels.

Combines:
  * the composite directional bias from decode.py
  * the option-chain institutional levels from levels.py
  * a short rolling trend of past composites (momentum / persistence)

Outputs, for NEXT DAY and NEXT WEEK (Mon-Fri):
  * expected direction + confidence
  * the key institutional levels and the expected REACTION at each
    (go through / hold => continue; reject / break => reversal)
  * an explicit "if X then Y" scenario tree so the reader knows what to do
    when price actually reaches a level.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

import pandas as pd


@dataclass
class Prediction:
    horizon: str            # "next_day" | "next_week"
    direction: str          # UP / DOWN / SIDEWAYS-UP / SIDEWAYS-DOWN / RANGE
    confidence: float
    rationale: str
    scenarios: list         # list of {trigger, then}
    key_levels: dict        # {support:[...], resistance:[...]}

    def to_dict(self) -> dict:
        return asdict(self)


def _rolling_bias(decoded_history: Optional[pd.DataFrame], n: int = 5) -> Optional[float]:
    if decoded_history is None or decoded_history.empty or "composite" not in decoded_history:
        return None
    tail = decoded_history.sort_values("date").tail(n)
    if tail.empty:
        return None
    # Weight most-recent higher.
    weights = list(range(1, len(tail) + 1))
    vals = tail["composite"].astype(float).tolist()
    return sum(v * w for v, w in zip(vals, weights)) / sum(weights)


def _direction(composite: float, momentum: Optional[float]) -> str:
    strong = abs(composite) >= 0.5
    up = composite > 0.15
    down = composite < -0.15
    if up and strong:
        return "UP"
    if down and strong:
        return "DOWN"
    if up:
        return "SIDEWAYS-UP"
    if down:
        return "SIDEWAYS-DOWN"
    return "RANGE"


def _reaction_scenarios(levels: dict, direction: str) -> list:
    """Turn levels into actionable if/then scenarios."""
    out = []
    res = levels.get("immediate_resistance")
    sup = levels.get("immediate_support")
    if res:
        out.append({
            "trigger": f"Price rises to resistance {res['strike']:.0f} ({res['basis']})",
            "then": ("Watch the reaction. Rejection here => reversal DOWN toward support. "
                     "A 15-min close ABOVE with follow-through => resistance breaks, "
                     "continuation UP (short-covering).")
        })
    if sup:
        out.append({
            "trigger": f"Price falls to support {sup['strike']:.0f} ({sup['basis']})",
            "then": ("Watch the reaction. A hold/bounce => reversal UP toward resistance. "
                     "A 15-min close BELOW with follow-through => support breaks, "
                     "continuation DOWN (long unwinding).")
        })
    mp = levels.get("max_pain")
    spot = levels.get("spot")
    if mp and spot:
        if mp > spot:
            out.append({"trigger": f"Max-pain {mp:.0f} sits ABOVE spot {spot:.0f}",
                        "then": "Gentle upward pull into expiry (writers drag price up toward max pain)."})
        elif mp < spot:
            out.append({"trigger": f"Max-pain {mp:.0f} sits BELOW spot {spot:.0f}",
                        "then": "Gentle downward pull into expiry (writers drag price down toward max pain)."})
    return out


def build_predictions(decode_result, levels: Optional[dict],
                      decoded_history: Optional[pd.DataFrame] = None) -> dict:
    composite = decode_result.composite
    momentum = _rolling_bias(decoded_history)
    # Blend today's read with recent persistence for the weekly view.
    weekly_composite = composite if momentum is None else (0.6 * composite + 0.4 * momentum)

    levels = levels or {}
    key_levels = {
        "support": [l for l in levels.get("levels", []) if l["kind"] == "support"][:4],
        "resistance": [l for l in levels.get("levels", []) if l["kind"] == "resistance"][:4],
        "max_pain": levels.get("max_pain"),
        "pcr": levels.get("pcr"),
    }

    nd_dir = _direction(composite, momentum)
    nw_dir = _direction(weekly_composite, momentum)

    next_day = Prediction(
        horizon="next_day",
        direction=nd_dir,
        confidence=decode_result.confidence,
        rationale=(f"Composite bias {composite:+.2f} ({decode_result.bias}). "
                   + (f"Recent 5-day momentum {momentum:+.2f}. " if momentum is not None else "")
                   + f"PCR {levels.get('pcr','n/a')}, {levels.get('pcr_signal','')}"),
        scenarios=_reaction_scenarios(levels, nd_dir),
        key_levels=key_levels,
    )

    weekly_conf = round(min(100, decode_result.confidence * 0.85
                            + (abs(momentum) * 20 if momentum else 0)), 1)
    next_week = Prediction(
        horizon="next_week",
        direction=nw_dir,
        confidence=weekly_conf,
        rationale=(f"Blended weekly bias {weekly_composite:+.2f} "
                   f"(today {composite:+.2f}"
                   + (f", momentum {momentum:+.2f}" if momentum is not None else "")
                   + "). Institutions typically defend the highest-OI put/call walls; "
                   "the week trades between them unless a wall is decisively broken."),
        scenarios=_reaction_scenarios(levels, nw_dir),
        key_levels=key_levels,
    )

    return {"next_day": next_day.to_dict(), "next_week": next_week.to_dict()}
