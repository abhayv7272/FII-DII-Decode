"""Transcript-grounded v2 participant-OI decoder.

The v1 decoder converted every participant/instrument net change through fixed
contract scales and blended stock and index derivatives into an unconditional
next-session direction.  A complete second reading of the source transcripts
showed six material problems with that translation:

* additions and closures are not equivalent (fresh positions are stronger);
* absolute contract thresholds age badly as participation changes;
* index options dominate the NIFTY very-short-term read;
* stock-option crowding is a risk/context flag, not a clean NIFTY direction;
* FII/Pro disagreement describes a path/reversal setup, not a safe close call;
* a data lean still requires an intraday price-action trigger.

V2 therefore scores fresh additions at full strength, closures at half strength,
normalises every flow by that instrument's current market OI, and builds the
next-day research lean from index calls, index puts, and index futures only.
The output explicitly separates the statistical lean from actionability.  Its
``confidence`` fields are retained for API compatibility but represent heuristic
*setup strength*, never a calibrated probability.

The frozen old implementation lives in :mod:`fiidii.legacy_v1` so historical v1
results remain exactly reproducible.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import tanh
from typing import Optional

import pandas as pd


METHOD_VERSION = "v2"
CLOSE_POSITION_WEIGHT = 0.50
INDEX_FLOW_SCALE = 0.025  # directional flow equal to 2.5% of current market OI
STOCK_FLOW_SCALE = 0.015
DIRECTION_THRESHOLD = 0.10
CONFLICT_THRESHOLD = 0.15

# Transcript order for a very-short-term NIFTY read: index options first, then
# index futures. Stock derivatives remain visible diagnostics but are not used to
# manufacture a NIFTY direction when their underlying stocks are unknown.
NEXT_DAY_INSTRUMENT_WEIGHT = {
    "index_call": 0.40,
    "index_put": 0.40,
    "index_fut": 0.20,
}
NEXT_DAY_PARTICIPANT_WEIGHT = {
    "Pro": 0.80 * (2.0 / 3.0),  # Pro has the 1-2 day edge
    "FII": 0.80 * (1.0 / 3.0),
    "Client": 0.20,             # already contra-adjusted
    "DII": 0.0,
}

# This is a carry-position *context* score, not a validated weekly forecast.
# Stock futures are retained here because the transcript's positional examples
# specifically use multi-session FII stock-future accumulation.
POSITIONAL_INSTRUMENT_WEIGHT = {
    "index_call": 0.30,
    "index_put": 0.30,
    "index_fut": 0.25,
    "stock_fut": 0.15,
}
POSITIONAL_PARTICIPANT_WEIGHT = {
    "FII": 0.60,
    "Pro": 0.25,
    "Client": 0.15,
    "DII": 0.0,
}
CARRY_SCALE = {
    "index_call": 0.08,
    "index_put": 0.08,
    "index_fut": 0.30,
    "stock_call": 0.08,
    "stock_put": 0.08,
    "stock_fut": 0.25,
}


@dataclass
class Signal:
    name: str
    score: float
    weight: float
    note: str

    def contribution(self) -> float:
        return self.score * self.weight


@dataclass
class DecodeResult:
    date: str
    bias: str
    composite: float
    confidence: float
    positional_bias: str
    positional_composite: float
    positional_confidence: float
    method_version: str = METHOD_VERSION
    actionability: str = "NO_DIRECTIONAL_EDGE"
    setup_note: str = ""
    setup_strength: float = 0.0
    smart_money_conflict: bool = False
    conflict_note: str = ""
    retail_note: str = ""
    move_quality: str = ""
    signals: list = field(default_factory=list)
    participant_reads: dict = field(default_factory=dict)
    participant_carry_reads: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        result = asdict(self)
        result["signals"] = [asdict(s) if isinstance(s, Signal) else s for s in self.signals]
        return result


# ---------------------------------------------------------------------------
def _normalise_name(value: str) -> str:
    return value.lower().replace(" ", "").replace("_", "")


def _col(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    available = {_normalise_name(str(column)): column for column in df.columns}
    for candidate in candidates:
        if _normalise_name(candidate) in available:
            return available[_normalise_name(candidate)]
    return None


def _row(df: Optional[pd.DataFrame], participant: str) -> Optional[pd.Series]:
    if df is None or "ClientType" not in df.columns:
        return None
    matches = df[df["ClientType"].astype(str).str.upper() == participant.upper()]
    return matches.iloc[0] if len(matches) else None


def _num(row: Optional[pd.Series], column: Optional[str]) -> float:
    if row is None or column is None:
        return 0.0
    value = row.get(column, 0)
    try:
        return float(value) if pd.notna(value) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _clip(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _squash(value: float, scale: float) -> float:
    return tanh(value / scale) if scale else 0.0


def _resolve_cols(df: pd.DataFrame) -> dict:
    return {
        "fut_idx_l": _col(df, "Future Index Long"),
        "fut_idx_s": _col(df, "Future Index Short"),
        "fut_stk_l": _col(df, "Future Stock Long"),
        "fut_stk_s": _col(df, "Future Stock Short"),
        "opt_idx_cl": _col(df, "Option Index Call Long"),
        "opt_idx_cs": _col(df, "Option Index Call Short"),
        "opt_idx_pl": _col(df, "Option Index Put Long"),
        "opt_idx_ps": _col(df, "Option Index Put Short"),
        "opt_stk_cl": _col(df, "Option Stock Call Long"),
        "opt_stk_cs": _col(df, "Option Stock Call Short"),
        "opt_stk_pl": _col(df, "Option Stock Put Long"),
        "opt_stk_ps": _col(df, "Option Stock Put Short"),
    }


INSTRUMENT_COLUMNS = {
    "index_fut": ("fut_idx_l", "fut_idx_s", 1.0),
    "stock_fut": ("fut_stk_l", "fut_stk_s", 1.0),
    "index_call": ("opt_idx_cl", "opt_idx_cs", 1.0),
    "index_put": ("opt_idx_pl", "opt_idx_ps", -1.0),
    "stock_call": ("opt_stk_cl", "opt_stk_cs", 1.0),
    "stock_put": ("opt_stk_pl", "opt_stk_ps", -1.0),
}


def _market_oi(total: Optional[pd.Series], rows: dict, long_col: Optional[str],
               short_col: Optional[str]) -> float:
    """Return one-sided market OI, with a safe fallback when TOTAL is absent."""
    if total is not None:
        value = max(_num(total, long_col), _num(total, short_col))
        if value > 0:
            return value
    long_total = sum(_num(row, long_col) for row in rows.values() if row is not None)
    short_total = sum(_num(row, short_col) for row in rows.values() if row is not None)
    return max(long_total, short_total, 1.0)


def _fresh_pressure(today: pd.Series, previous: Optional[pd.Series],
                    long_col: Optional[str], short_col: Optional[str],
                    bullish_when_long: float) -> tuple[float, dict]:
    """Quality-adjusted fresh pressure and its auditable decomposition.

    For futures/calls, fresh longs and short covering are bullish; fresh shorts
    and long unwinding are bearish. Puts reverse that sign. The transcript calls
    fresh positioning "real strength" and closures only an early/weak sign, so
    closures receive half weight.
    """
    if previous is None:
        return 0.0, {"fresh_long": 0.0, "short_cover": 0.0,
                     "fresh_short": 0.0, "long_unwind": 0.0}

    delta_long = _num(today, long_col) - _num(previous, long_col)
    delta_short = _num(today, short_col) - _num(previous, short_col)
    parts = {
        "fresh_long": max(delta_long, 0.0),
        "short_cover": max(-delta_short, 0.0),
        "fresh_short": max(delta_short, 0.0),
        "long_unwind": max(-delta_long, 0.0),
    }
    long_side = (
        parts["fresh_long"]
        + CLOSE_POSITION_WEIGHT * parts["short_cover"]
        - parts["fresh_short"]
        - CLOSE_POSITION_WEIGHT * parts["long_unwind"]
    )
    return bullish_when_long * long_side, parts


def _participant_reads(today: pd.Series, previous: Optional[pd.Series], C: dict,
                       totals: dict, contra: bool) -> tuple[dict, dict, dict]:
    fresh: dict[str, float] = {}
    carry: dict[str, float] = {}
    decompositions: dict[str, dict] = {}

    for instrument, (long_key, short_key, direction) in INSTRUMENT_COLUMNS.items():
        long_col, short_col = C[long_key], C[short_key]
        pressure, parts = _fresh_pressure(
            today, previous, long_col, short_col, direction
        )
        flow_scale = INDEX_FLOW_SCALE if instrument.startswith("index_") else STOCK_FLOW_SCALE
        score = _squash(pressure / totals[instrument], flow_scale)
        carry_ratio = direction * (
            _num(today, long_col) - _num(today, short_col)
        ) / totals[instrument]
        carry_score = _squash(carry_ratio, CARRY_SCALE[instrument])
        if contra:
            score = -score
            carry_score = -carry_score
        fresh[instrument] = score
        carry[instrument] = carry_score
        decompositions[instrument] = parts
    return fresh, carry, decompositions


def _weighted(reads: dict, weights: dict) -> float:
    total_weight = sum(weight for name, weight in weights.items() if name in reads)
    if not total_weight:
        return 0.0
    return _clip(sum(reads[name] * weight for name, weight in weights.items()
                     if name in reads) / total_weight)


def _blend(participant_scores: dict, weights: dict) -> float:
    total_weight = sum(weights.get(name, 0.0) for name in participant_scores)
    if not total_weight:
        return 0.0
    return _clip(sum(score * weights.get(name, 0.0)
                     for name, score in participant_scores.items()) / total_weight)


def _move_quality(decompositions: dict) -> str:
    notes: list[str] = []
    for participant in ("FII", "Pro"):
        parts = decompositions.get(participant, {}).get("index_fut", {})
        if not parts:
            continue
        strongest = max(parts, key=parts.get)
        amount = parts[strongest]
        if amount <= 0:
            continue
        wording = {
            "fresh_long": "fresh index-future longs (full-strength bullish)",
            "short_cover": "index-future short covering (weaker bullish)",
            "fresh_short": "fresh index-future shorts (full-strength bearish)",
            "long_unwind": "index-future long unwinding (weaker bearish)",
        }[strongest]
        notes.append(f"{participant}: {wording}, {amount:,.0f} contracts")
    return "; ".join(notes) if notes else "No dominant FII/Pro index-future change."


def _bias_label(value: float) -> str:
    if value >= 0.45:
        return "STRONG BULLISH"
    if value >= DIRECTION_THRESHOLD:
        return "BULLISH"
    if value <= -0.45:
        return "STRONG BEARISH"
    if value <= -DIRECTION_THRESHOLD:
        return "BEARISH"
    return "NEUTRAL"


def _setup_strength(composite: float, conflict: bool = False) -> float:
    # Intensity relative to the strong-bias boundary; deliberately not a
    # probability estimate.
    strength = min(100.0, abs(composite) / 0.45 * 100.0)
    if conflict:
        strength = min(strength, 40.0)
    return round(strength, 1)


# ---------------------------------------------------------------------------
def decode(
    oi_today: pd.DataFrame,
    oi_prev: Optional[pd.DataFrame] = None,
    cash: Optional[dict] = None,
    option_levels: Optional[dict] = None,
    date_str: str = "",
) -> DecodeResult:
    """Decode one participant-OI report with the locked v2 rules."""
    C = _resolve_cols(oi_today)
    participants = ("FII", "Pro", "Client", "DII")
    rows_t = {name: _row(oi_today, name) for name in participants}
    rows_p = {name: _row(oi_prev, name) for name in participants}
    total_row = _row(oi_today, "TOTAL")
    totals = {
        instrument: _market_oi(total_row, rows_t, C[long_key], C[short_key])
        for instrument, (long_key, short_key, _) in INSTRUMENT_COLUMNS.items()
    }

    participant_reads: dict = {}
    participant_carry_reads: dict = {}
    decompositions: dict = {}
    next_day_participant: dict = {}
    positional_participant: dict = {}

    for participant in participants:
        row = rows_t[participant]
        if row is None:
            continue
        fresh, carry, parts = _participant_reads(
            row, rows_p[participant], C, totals, contra=participant == "Client"
        )
        participant_reads[participant] = {
            name: round(score, 3) for name, score in fresh.items()
        }
        participant_carry_reads[participant] = {
            name: round(score, 3) for name, score in carry.items()
        }
        decompositions[participant] = parts
        next_day_participant[participant] = _weighted(fresh, NEXT_DAY_INSTRUMENT_WEIGHT)
        positional_participant[participant] = _weighted(carry, POSITIONAL_INSTRUMENT_WEIGHT)

    intraday = _blend(next_day_participant, NEXT_DAY_PARTICIPANT_WEIGHT)
    positional = _blend(positional_participant, POSITIONAL_PARTICIPANT_WEIGHT)

    fii = next_day_participant.get("FII", 0.0)
    pro = next_day_participant.get("Pro", 0.0)
    conflict = (
        fii * pro < 0
        and min(abs(fii), abs(pro)) > CONFLICT_THRESHOLD
    )
    conflict_note = ""
    if conflict:
        conflict_note = (
            f"FII ({fii:+.2f}) and Pro ({pro:+.2f}) fresh index reads oppose each other. "
            "The transcript treats this as a first-move/then-reversal setup whose order "
            "depends on pre-open news—not as an actionable closing-direction call."
        )

    if conflict:
        actionability = "WAIT_FOR_REVERSAL_CONFIRMATION"
        setup_note = (
            "Do not enter from the OI lean alone. Wait for the opening path, an option-chain "
            "level test, and a 10-15 minute reversal/break candle."
        )
    elif abs(intraday) < DIRECTION_THRESHOLD:
        actionability = "NO_DIRECTIONAL_EDGE"
        setup_note = (
            "Index participant flows do not clear the locked direction threshold; preserve "
            "capital rather than forcing an UP/DOWN call."
        )
    else:
        direction = "BULLISH" if intraday > 0 else "BEARISH"
        actionability = f"CONDITIONAL_{direction}_SETUP"
        setup_note = (
            f"OI-only {direction.lower()} lean. It becomes actionable only after the relevant "
            "option-chain/price level confirms with a 10-15 minute candle; a decisive break "
            "activates the opposite backup plan."
        )

    signals: list[Signal] = []
    for participant in ("Pro", "FII", "Client", "DII"):
        if participant not in next_day_participant:
            continue
        weight = NEXT_DAY_PARTICIPANT_WEIGHT[participant]
        top = sorted(
            ((name, score) for name, score in participant_reads[participant].items()
             if name in NEXT_DAY_INSTRUMENT_WEIGHT),
            key=lambda item: -abs(item[1]),
        )
        top_text = ", ".join(f"{name} {score:+.2f}" for name, score in top)
        label = {
            "Pro": "ultra-short driver",
            "FII": "secondary next-day / positional participant",
            "Client": "contra confirmation",
            "DII": "F&O direction ignored (arbitrage contamination)",
        }[participant]
        signals.append(Signal(
            f"{participant}_fresh_index",
            round(next_day_participant[participant], 3),
            weight,
            f"{label}; relative-OI quality score [{top_text}]",
        ))

    # Cash is retained as disclosed confirmation only. Historical cash was not
    # available for the 757-session validation, so silently changing the tested
    # class with live cash would create an unvalidated production variant.
    metrics: dict = {
        "method_version": METHOD_VERSION,
        "normalization": "quality-adjusted fresh flow / current instrument market OI",
        "close_position_weight": CLOSE_POSITION_WEIGHT,
        "direction_threshold": DIRECTION_THRESHOLD,
        "stock_derivatives_in_next_day_score": False,
    }
    cash_note = ""
    if cash:
        fii_cash = _extract_cash_net(cash, "FII")
        dii_cash = _extract_cash_net(cash, "DII")
        if fii_cash is not None:
            metrics["fii_cash_net"] = fii_cash
            metrics["dii_cash_net"] = dii_cash
            cash_score = _squash(fii_cash + 0.6 * (dii_cash or 0.0), 3000.0)
            signals.append(Signal(
                "cash_confirmation", round(cash_score, 3), 0.0,
                f"Confirmation only (not fitted in v2 backtest): FII {fii_cash:,.0f} Cr, "
                f"DII {dii_cash or 0:,.0f} Cr.",
            ))
            if cash_score * intraday < 0 and abs(cash_score) >= 0.25:
                cash_note = " Cash flow contradicts the OI lean; reduce conviction."
            elif cash_score * intraday > 0 and abs(cash_score) >= 0.25:
                cash_note = " Cash flow confirms the OI lean, but was not part of historical v2 scoring."

    for participant in ("FII", "Pro", "Client"):
        row = rows_t[participant]
        if row is not None:
            metrics[f"{participant.lower()}_index_fut_net"] = (
                _num(row, C["fut_idx_l"]) - _num(row, C["fut_idx_s"])
            )
    if option_levels:
        metrics.update({key: option_levels.get(key) for key in ("max_pain", "pcr", "spot")})

    client_score = next_day_participant.get("Client")
    retail_note = ""
    if client_score is not None:
        if client_score < -DIRECTION_THRESHOLD:
            retail_note = (
                "Retail fresh index positioning is bullish (contra-negative): upside can remain "
                "capped until those longs/short puts unwind."
            )
        elif client_score > DIRECTION_THRESHOLD:
            retail_note = (
                "Retail fresh index positioning is bearish (contra-positive), which supports a "
                "market bounce only after price confirmation."
            )
        else:
            retail_note = "Retail fresh index positioning is mixed; it provides no strong contra confirmation."

    strength = _setup_strength(intraday, conflict)
    positional_strength = _setup_strength(positional)
    return DecodeResult(
        date=date_str,
        bias=_bias_label(intraday),
        composite=round(intraday, 3),
        confidence=strength,
        positional_bias=_bias_label(positional),
        positional_composite=round(positional, 3),
        positional_confidence=positional_strength,
        actionability=actionability,
        setup_note=setup_note + cash_note,
        setup_strength=strength,
        smart_money_conflict=conflict,
        conflict_note=conflict_note,
        retail_note=retail_note,
        move_quality=_move_quality(decompositions),
        signals=signals,
        participant_reads=participant_reads,
        participant_carry_reads=participant_carry_reads,
        metrics=metrics,
    )


def _extract_cash_net(cash, group: str) -> Optional[float]:
    if isinstance(cash, list):
        for row in cash:
            category = str(row.get("category", "")).upper().replace(" ", "").replace("*", "")
            if group.upper() in category:
                for key in ("netValue", "netvalue", "net"):
                    if key in row:
                        try:
                            return float(str(row[key]).replace(",", ""))
                        except (TypeError, ValueError):
                            pass
    elif isinstance(cash, dict):
        value = cash.get(group)
        if isinstance(value, (int, float)):
            return float(value)
    return None
