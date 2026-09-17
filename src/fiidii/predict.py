"""Prediction assembly — Amit Dhamija style.

Next-day (Pro-led): builds Gap Up / Flat / Gap Down scenarios, because the 9 AM
news decides the open; for each open we say what should happen at the institutional
option-chain levels (hold->reversal, break->continuation), including the
liquidity-sweep-then-reverse pattern.

Next-week / positional (FII-led): uses the multi-day trend of carry positions
(longs building => upside brewing; shorts building => downside; mixed => range
between put wall & call wall). Notes the retail-unwind trigger.
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

    def to_dict(self) -> dict:
        return asdict(self)


def _direction(composite: float) -> str:
    if composite >= 0.45:
        return "UP"
    if composite >= 0.12:
        return "SIDEWAYS-UP"
    if composite <= -0.45:
        return "DOWN"
    if composite <= -0.12:
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
                f"sweep + institutional level + psychological level = high-probability "
                f"long confluence. A sustained close BELOW {sup_s} with bearish volume "
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
                       "plan": (f"Bias up but if retail is crowded long, expect "
                                f"'sell-on-rise / dip-then-recover': a dip into {sup_s} "
                                f"that reverses up is the high-probability path.")})
    else:
        out.insert(0, {"open": "PRIMARY",
                       "plan": (f"Bias down: rallies into {res_s} likely sold; "
                                f"a break below {sup_s} opens further downside.")})
    return out


def build_predictions(decode_result, levels: Optional[dict],
                      decoded_history: Optional[pd.DataFrame] = None) -> dict:
    levels = levels or {}
    key_levels = _levels_summary(levels)

    # ---- Next day (Pro-led) ----
    nd_dir = _direction(decode_result.composite)
    nd = Prediction(
        horizon="next_day",
        direction=nd_dir,
        confidence=decode_result.confidence,
        rationale=(
            f"Next-day bias {decode_result.composite:+.2f} ({decode_result.bias}), "
            f"Pro-led (ultra-short). {decode_result.retail_note} "
            f"Move quality: {decode_result.move_quality}. "
            f"PCR {levels.get('pcr','n/a')} — {levels.get('pcr_signal','')}"),
        scenarios=_gap_scenarios(levels, decode_result),
        key_levels=key_levels,
    )

    # ---- Next week / positional (FII-led) ----
    momentum = _rolling_positional(decoded_history)
    base = decode_result.positional_composite
    weekly = base if momentum is None else (0.55 * base + 0.45 * momentum)
    nw_dir = _direction(weekly)
    carry = _carry_trend(decoded_history)
    nw_conf = round(min(100, decode_result.positional_confidence * 0.85
                        + (abs(momentum) * 20 if momentum else 0)), 1)
    nw = Prediction(
        horizon="next_week",
        direction=nw_dir,
        confidence=nw_conf,
        rationale=(
            f"Positional bias {weekly:+.2f} ({_direction(weekly)}), FII-led "
            f"(Pro must be supportive). "
            f"{'Momentum ' + format(momentum, '+.2f') + '. ' if momentum is not None else ''}"
            f"{carry} Big positional moves come only 2-3x a year; otherwise the week "
            f"trades between the put wall (support) and call wall (resistance) unless a "
            f"wall breaks decisively. Retail must unwind longs before a sustained up-leg."),
        scenarios=[
            {"trigger": "FII longs keep building + Pro supportive",
             "then": "Positional UP-leg; buy dips into support."},
            {"trigger": "FII shorts keep building",
             "then": "Positional DOWN pressure; sell rises into resistance."},
            {"trigger": "Retail bullish positions start unwinding",
             "then": "Removes the cap on upside → reversal-up trigger."},
        ],
        key_levels=key_levels,
    )

    return {"next_day": nd.to_dict(), "next_week": nw.to_dict()}
