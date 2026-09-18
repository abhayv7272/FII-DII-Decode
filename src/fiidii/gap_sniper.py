"""Validated structural gap-fill sniper signal.

This module deliberately stays separate from the FII/DII OI decoder.  V10 found
one high-accuracy pocket that is not an unconditional next-day close-direction
forecast: when NIFTY opens only a tiny distance away from the previous close,
the previous close is usually touched intraday.

The default band below is the strongest V10 robust rule on committed historical
NIFTY intraday data (2017-04-03 to 2026-09-17):

    abs(open gap) in [0.03%, 0.12%) -> previous-close touch intraday

Backtest split hit-rates:
    overall 90.33%, train 2017-2023 89.11%, validation 2024-2025 94.23%,
    confirmation 2026 87.50%.

Caution: this is a level-touch probability, not a standalone options trade.
The average target distance was only ~13 NIFTY points in the audit, so slippage,
spread, and stop placement matter a lot.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


DEFAULT_BAND = (0.03, 0.12)


@dataclass(frozen=True)
class TinyGapFillValidation:
    rule: str
    overall_calls: int
    overall_hit_rate: float
    train_2017_2023_calls: int
    train_2017_2023_hit_rate: float
    val_2024_2025_calls: int
    val_2024_2025_hit_rate: float
    confirm_2026_calls: int
    confirm_2026_hit_rate: float
    mean_target_distance_pts: float


DEFAULT_VALIDATION = TinyGapFillValidation(
    rule="abs_gap_0.03_0.12_both_fill_prev_close",
    overall_calls=393,
    overall_hit_rate=90.33078880407125,
    train_2017_2023_calls=257,
    train_2017_2023_hit_rate=89.10505836575877,
    val_2024_2025_calls=104,
    val_2024_2025_hit_rate=94.23076923076923,
    confirm_2026_calls=32,
    confirm_2026_hit_rate=87.5,
    mean_target_distance_pts=12.992941014630949,
)


def tiny_gap_fill_signal(
    open_price: float,
    previous_close: float,
    *,
    min_abs_gap_pct: float = DEFAULT_BAND[0],
    max_abs_gap_pct: float = DEFAULT_BAND[1],
) -> dict:
    """Return the V10 tiny-gap-fill prediction for a live open.

    Parameters
    ----------
    open_price:
        Current session NIFTY open.
    previous_close:
        Previous session NIFTY close.
    min_abs_gap_pct, max_abs_gap_pct:
        Inclusive lower / exclusive upper absolute-gap band.  Defaults to the
        validated V10 0.03%-0.12% band.

    Returns
    -------
    dict
        A JSON-serialisable signal.  ``active`` means the level-touch prediction
        is in force: gap up -> fade DOWN to previous close; gap down -> fade UP
        to previous close.
    """
    if previous_close <= 0 or open_price <= 0:
        raise ValueError("open_price and previous_close must be positive")
    if min_abs_gap_pct < 0 or max_abs_gap_pct <= min_abs_gap_pct:
        raise ValueError("gap band must satisfy 0 <= min_abs_gap_pct < max_abs_gap_pct")

    gap_pct = (open_price - previous_close) / previous_close * 100.0
    abs_gap_pct = abs(gap_pct)
    active = min_abs_gap_pct <= abs_gap_pct < max_abs_gap_pct
    if gap_pct > 0:
        direction = "DOWN"
        thesis = "Gap up is tiny; expect previous close to be touched intraday."
    elif gap_pct < 0:
        direction = "UP"
        thesis = "Gap down is tiny; expect previous close to be touched intraday."
    else:
        direction = "NO_SIGNAL"
        thesis = "No gap."

    target_distance_pts = abs(open_price - previous_close)
    return {
        "active": bool(active),
        "signal_type": "TINY_GAP_FILL_PREVIOUS_CLOSE_TOUCH",
        "open": float(open_price),
        "previous_close": float(previous_close),
        "gap_pct": float(gap_pct),
        "abs_gap_pct": float(abs_gap_pct),
        "band_min_abs_gap_pct": float(min_abs_gap_pct),
        "band_max_abs_gap_pct": float(max_abs_gap_pct),
        "direction_to_target": direction if active else "NO_SIGNAL",
        "target": float(previous_close) if active else None,
        "target_distance_pts": float(target_distance_pts),
        "actionability": (
            "LEVEL_TOUCH_ALERT_ONLY_EXECUTION_MODEL_REQUIRED"
            if active
            else "NO_TINY_GAP_FILL_SIGNAL"
        ),
        "thesis": thesis if active else "Gap is outside the validated tiny-gap band; skip this sniper rule.",
        "validation": asdict(DEFAULT_VALIDATION),
        "warning": (
            "V10 validates previous-close touch probability, not a standalone high-RR trade. "
            "Use live/tick execution, slippage, option premium, and stop logic before risking capital."
        ),
    }
