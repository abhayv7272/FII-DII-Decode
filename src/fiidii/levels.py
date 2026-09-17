"""Transcript-grounded option-chain levels and supplied institutional references.

The supplied PDFs do *not* disclose the formula used to draw the speaker's
proprietary "institutional levels". They explicitly say that construction is
covered in an advanced course. The transcripts do disclose how to use levels:

* total OI and change in OI both matter;
* put-side concentration below spot is a support candidate;
* call-side concentration above spot is a resistance candidate;
* a gap can skip a level, in which case the next level matters;
* a confirmed break flips support/resistance and opens the next level;
* an entry requires bullish/bearish price-action confirmation;
* option-chain + institutional + psychological-level confluence is stronger.

Accordingly, this module draws an auditable *option-chain proxy*. It never calls
positive OI change "writing": end-of-day OI alone cannot identify buyer versus
writer. Exact institutional levels can be supplied separately and are kept
visibly distinct from the automatic proxy.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from math import isfinite
from statistics import median

import pandas as pd

LEVEL_METHOD = "transcript_disclosed_option_chain_proxy_v2"
LEVEL_METHOD_WARNING = (
    "The PDFs do not disclose the proprietary institutional-level formula; they "
    "refer viewers to an advanced course. Automatically drawn values are option-chain "
    "support/resistance proxies, not reconstructed proprietary levels. Any externally "
    "supplied exact references are identified separately."
)


@dataclass
class Level:
    strike: float
    kind: str  # "resistance" | "support" | "pivot"
    basis: str
    oi: float
    oi_change: float
    distance_pct: float
    reaction: str
    source: str = "option_chain_proxy"
    evidence_score: float | None = None
    evidence_grade: str = "REFERENCE"
    evidence: str = ""
    label: str = ""
    confluence: bool = False
    confluence_note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def option_chain_to_frame(raw: dict, expiry: str | None = None) -> pd.DataFrame:
    """Flatten NSE option-chain JSON into a per-strike frame for one expiry."""
    records = raw["records"]["data"]
    if expiry is None:
        expiry = raw["records"]["expiryDates"][0]
    rows = []
    for record in records:
        if record.get("expiryDate") != expiry:
            continue
        call = record.get("CE", {}) or {}
        put = record.get("PE", {}) or {}
        rows.append({
            "strike": record["strikePrice"],
            "ce_oi": call.get("openInterest", 0) or 0,
            "ce_chg_oi": call.get("changeinOpenInterest", 0) or 0,
            "ce_ltp": call.get("lastPrice", 0) or 0,
            "ce_iv": call.get("impliedVolatility", 0) or 0,
            "ce_vol": call.get("totalTradedVolume", 0) or 0,
            "pe_oi": put.get("openInterest", 0) or 0,
            "pe_chg_oi": put.get("changeinOpenInterest", 0) or 0,
            "pe_ltp": put.get("lastPrice", 0) or 0,
            "pe_iv": put.get("impliedVolatility", 0) or 0,
            "pe_vol": put.get("totalTradedVolume", 0) or 0,
        })
    if not rows:
        raise ValueError(f"option chain contains no rows for expiry {expiry!r}")
    return pd.DataFrame(rows).sort_values("strike").reset_index(drop=True)


def max_pain(frame: pd.DataFrame) -> float:
    """Strike at which aggregate intrinsic payout is minimised."""
    strikes = frame["strike"].values
    best_strike, best_loss = strikes[0], float("inf")
    for expiry_price in strikes:
        call_loss = (
            (expiry_price - frame["strike"]).clip(lower=0) * frame["ce_oi"]
        ).sum()
        put_loss = (
            (frame["strike"] - expiry_price).clip(lower=0) * frame["pe_oi"]
        ).sum()
        total = call_loss + put_loss
        if total < best_loss:
            best_loss, best_strike = total, expiry_price
    return float(best_strike)


def pcr(frame: pd.DataFrame) -> float:
    call_oi = frame["ce_oi"].sum()
    return float(frame["pe_oi"].sum() / call_oi) if call_oi else 0.0


def _evidence_grade(score: float) -> str:
    if score >= 70:
        return "HIGH_RELATIVE_CONCENTRATION"
    if score >= 45:
        return "MEDIUM_RELATIVE_CONCENTRATION"
    return "WATCH_ONLY"


def _reaction_text(kind: str) -> str:
    if kind == "support":
        return (
            "Conditional support level. A bullish 10-15 minute rejection/reclaim "
            "activates a bounce toward the next upper level. A sustained bearish "
            "break below flips this level to resistance and activates the next lower level."
        )
    if kind == "resistance":
        return (
            "Conditional resistance level. A bearish 10-15 minute rejection activates "
            "a move toward the next lower level. A sustained bullish break above flips "
            "this level to support and activates the next upper level."
        )
    return (
        "Two-sided pivot. Wait for a 10-15 minute hold above or below; the confirmed "
        "side activates the next level in that direction."
    )


def _rank_option_side(frame: pd.DataFrame, spot: float, kind: str,
                      top_n: int) -> list[Level]:
    """Rank relevant-side strikes using both total OI and positive OI change.

    The 60/40 evidence score is a deterministic ranking aid, not probability.
    It operationalises the transcript's instruction that both quantities matter.
    """
    if kind == "support":
        candidates = frame[frame["strike"] < spot].copy()
        oi_col, change_col, side_name = "pe_oi", "pe_chg_oi", "put"
    else:
        candidates = frame[frame["strike"] > spot].copy()
        oi_col, change_col, side_name = "ce_oi", "ce_chg_oi", "call"
    if candidates.empty:
        return []

    side_oi_max = max(float(candidates[oi_col].max()), 1.0)
    positive_change_max = max(
        float(candidates[change_col].clip(lower=0).max()), 1.0
    )
    candidates["oi_component"] = candidates[oi_col] / side_oi_max
    candidates["change_component"] = (
        candidates[change_col].clip(lower=0) / positive_change_max
    )
    candidates["evidence_score"] = 100.0 * (
        0.60 * candidates["oi_component"]
        + 0.40 * candidates["change_component"]
    )
    selected = candidates.nlargest(top_n, "evidence_score")

    levels = []
    for _, row in selected.iterrows():
        score = round(float(row["evidence_score"]), 1)
        change = float(row[change_col])
        change_state = (
            "increased" if change > 0 else "decreased" if change < 0 else "unchanged"
        )
        levels.append(Level(
            strike=float(row["strike"]),
            kind=kind,
            basis=f"{side_name}_oi_total_plus_change",
            oi=float(row[oi_col]),
            oi_change=change,
            distance_pct=round((float(row["strike"]) - spot) / spot * 100, 2),
            reaction=_reaction_text(kind),
            evidence_score=score,
            evidence_grade=_evidence_grade(score),
            evidence=(
                f"{side_name.upper()} total OI {float(row[oi_col]):,.0f}; "
                f"OI change {change:+,.0f} ({change_state}); relative evidence "
                f"score {score:.1f}/100. OI alone does not identify buyer/writer."
            ),
            label=f"{side_name}-side concentration",
        ))
    return levels


def _reference_level(value, spot: float) -> Level:
    if isinstance(value, dict):
        strike = float(value["strike"])
        kind = str(value.get("kind", "")).lower()
        label = str(value.get("label", "supplied institutional reference"))
    else:
        strike = float(value)
        kind = ""
        label = "supplied institutional reference"
    if not isfinite(strike) or strike <= 0:
        raise ValueError("supplied institutional strikes must be positive and finite")
    if kind not in {"support", "resistance", "pivot"}:
        kind = "support" if strike < spot else "resistance" if strike > spot else "pivot"
    return Level(
        strike=strike,
        kind=kind,
        basis="supplied_reference_not_derived",
        oi=0.0,
        oi_change=0.0,
        distance_pct=round((strike - spot) / spot * 100, 2),
        reaction=_reaction_text(kind),
        source="supplied_institutional_reference",
        evidence_score=None,
        evidence_grade="SUPPLIED_NOT_SCORED",
        evidence=(
            "Externally supplied exact level. The repository did not derive it because "
            "the proprietary construction formula is absent from the supplied PDFs."
        ),
        label=label,
    )


def _strike_step(frame: pd.DataFrame) -> float:
    differences = frame["strike"].sort_values().diff().dropna()
    positive = [float(value) for value in differences if value > 0]
    return median(positive) if positive else 1.0


def _mark_confluence(levels: list[Level], tolerance: float) -> None:
    for level in levels:
        matches = [
            other for other in levels
            if other is not level
            and other.source != level.source
            and (
                other.kind == level.kind
                or other.kind == "pivot"
                or level.kind == "pivot"
            )
            and abs(other.strike - level.strike) <= tolerance
        ]
        if not matches:
            continue
        level.confluence = True
        names = ", ".join(
            f"{other.source} {other.strike:,.0f}" for other in matches
        )
        level.confluence_note = (
            f"Confluence within {tolerance:g} points: {names}. Still requires price confirmation."
        )


def derive_levels(raw: dict, spot: float | None = None,
                  expiry: str | None = None, top_n: int = 3,
                  institutional_levels: Iterable | None = None) -> dict:
    """Return option-chain proxy levels plus optional exact supplied references.

    ``top_n`` is the number of call-side and put-side proxy levels retained.
    ``institutional_levels`` accepts numbers or dictionaries containing ``strike``,
    optional ``kind``, and optional ``label``.
    """
    frame = option_chain_to_frame(raw, expiry)
    if spot is None:
        spot = raw["records"].get("underlyingValue") or frame["strike"].median()
    spot = float(spot)
    if not isfinite(spot) or spot <= 0:
        raise ValueError("spot must be positive and finite")

    option_levels = (
        _rank_option_side(frame, spot, "support", top_n)
        + _rank_option_side(frame, spot, "resistance", top_n)
    )
    references = [
        _reference_level(value, spot) for value in (institutional_levels or [])
    ]
    levels = option_levels + references
    # Two normal strike intervals includes the transcript's worked example where
    # a 24,076 institutional reference and 24,000 option strike form one zone.
    # This is a declared proximity heuristic, not the undisclosed level formula.
    confluence_tolerance = _strike_step(frame) * 2.0
    _mark_confluence(levels, confluence_tolerance)
    levels.sort(key=lambda level: (level.strike, level.source))

    supports = sorted(
        [level for level in levels if level.kind == "support" and level.strike < spot],
        key=lambda level: -level.strike,
    )
    resistances = sorted(
        [level for level in levels if level.kind == "resistance" and level.strike > spot],
        key=lambda level: level.strike,
    )

    selected_expiry = expiry or raw["records"]["expiryDates"][0]
    put_call_ratio = pcr(frame)
    return {
        "spot": spot,
        "expiry": selected_expiry,
        "level_method": LEVEL_METHOD,
        "level_method_warning": LEVEL_METHOD_WARNING,
        "exact_institutional_formula_available": False,
        "supplied_institutional_level_count": len(references),
        "confluence_tolerance_points": confluence_tolerance,
        "max_pain": max_pain(frame),
        "pcr": round(put_call_ratio, 3),
        "pcr_signal": _pcr_signal(put_call_ratio),
        "immediate_support": supports[0].to_dict() if supports else None,
        "immediate_resistance": resistances[0].to_dict() if resistances else None,
        "levels": [level.to_dict() for level in levels],
        "strike_frame": frame.to_dict(orient="records"),
    }


def _pcr_signal(value: float) -> str:
    if value >= 1.3:
        return (
            "Put OI is heavy relative to call OI. This is context only: without option-price "
            "and participant-side evidence it cannot be labelled put writing or a bullish signal."
        )
    if value <= 0.7:
        return (
            "Call OI is heavy relative to put OI. This is context only: without option-price "
            "and participant-side evidence it cannot be labelled call writing or a bearish signal."
        )
    return (
        "Put/call OI is comparatively balanced. Use confirmed support/resistance branches; "
        "PCR alone supplies no direction."
    )
