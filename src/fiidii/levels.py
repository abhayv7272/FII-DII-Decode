"""Derive institutional support/resistance levels from the option chain.

The idea (standard "smart money" option-chain reading):
  * Call writers defend RESISTANCE  -> highest Call OI strikes = supply zones.
  * Put writers defend SUPPORT      -> highest Put OI strikes  = demand zones.
  * Fresh OI *addition* (change in OI) marks where institutions are building
    today's positions -> the freshest, most actionable levels.
  * Max Pain = strike where option writers lose the least -> gravitational pull.
  * PCR (Put/Call OI ratio) -> >1 skew to put-writing (bullish/oversold),
    <1 skew to call-writing (bearish/overbought), with extremes = contrarian.

Every level carries an "expected reaction" annotation so the report can say:
  "At <level> (call wall) price likely faces resistance; break+hold => continuation,
   rejection => reversal down."
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

import pandas as pd


@dataclass
class Level:
    strike: float
    kind: str            # "resistance" | "support"
    basis: str           # "call_oi" | "put_oi" | "call_oi_change" | "put_oi_change"
    oi: float
    oi_change: float
    distance_pct: float  # signed % from spot (+ above, - below)
    reaction: str        # human-readable expected reaction

    def to_dict(self) -> dict:
        return asdict(self)


def option_chain_to_frame(raw: dict, expiry: Optional[str] = None) -> pd.DataFrame:
    """Flatten NSE option-chain JSON into a tidy per-strike frame for one expiry."""
    records = raw["records"]["data"]
    if expiry is None:
        expiry = raw["records"]["expiryDates"][0]
    rows = []
    for rec in records:
        if rec.get("expiryDate") != expiry:
            continue
        ce = rec.get("CE", {}) or {}
        pe = rec.get("PE", {}) or {}
        rows.append({
            "strike": rec["strikePrice"],
            "ce_oi": ce.get("openInterest", 0) or 0,
            "ce_chg_oi": ce.get("changeinOpenInterest", 0) or 0,
            "ce_ltp": ce.get("lastPrice", 0) or 0,
            "ce_iv": ce.get("impliedVolatility", 0) or 0,
            "ce_vol": ce.get("totalTradedVolume", 0) or 0,
            "pe_oi": pe.get("openInterest", 0) or 0,
            "pe_chg_oi": pe.get("changeinOpenInterest", 0) or 0,
            "pe_ltp": pe.get("lastPrice", 0) or 0,
            "pe_iv": pe.get("impliedVolatility", 0) or 0,
            "pe_vol": pe.get("totalTradedVolume", 0) or 0,
        })
    df = pd.DataFrame(rows).sort_values("strike").reset_index(drop=True)
    return df


def max_pain(df: pd.DataFrame) -> float:
    """Strike at which total option-writer payout is minimised."""
    strikes = df["strike"].values
    best_strike, best_loss = strikes[0], float("inf")
    for expiry_price in strikes:
        ce_loss = ((expiry_price - df["strike"]).clip(lower=0) * df["ce_oi"]).sum()
        pe_loss = ((df["strike"] - expiry_price).clip(lower=0) * df["pe_oi"]).sum()
        total = ce_loss + pe_loss
        if total < best_loss:
            best_loss, best_strike = total, expiry_price
    return float(best_strike)


def pcr(df: pd.DataFrame) -> float:
    ce = df["ce_oi"].sum()
    return float(df["pe_oi"].sum() / ce) if ce else 0.0


def _reaction_text(kind: str, fresh: bool) -> str:
    if kind == "resistance":
        base = "Expect selling pressure. If price approaches and rejects -> reversal down."
        if fresh:
            base += " Fresh call writing today => sellers active; a decisive break+close above flips it to support (short-covering fuel)."
        else:
            base += " A sustained break above => resistance becomes support."
    else:
        base = "Expect buying support. If price dips into it and holds -> bounce/reversal up."
        if fresh:
            base += " Fresh put writing today => buyers active; a decisive break+close below flips it to resistance (long unwinding)."
        else:
            base += " A sustained break below => support becomes resistance."
    return base


def derive_levels(raw: dict, spot: Optional[float] = None,
                  expiry: Optional[str] = None, top_n: int = 3) -> dict:
    """Return institutional levels + summary metrics from an option chain."""
    df = option_chain_to_frame(raw, expiry)
    if spot is None:
        spot = raw["records"].get("underlyingValue") or df["strike"].median()

    levels: list[Level] = []

    def add(rows, kind, basis, oi_col, chg_col, fresh):
        for _, r in rows.iterrows():
            levels.append(Level(
                strike=float(r["strike"]), kind=kind, basis=basis,
                oi=float(r[oi_col]), oi_change=float(r[chg_col]),
                distance_pct=round((r["strike"] - spot) / spot * 100, 2),
                reaction=_reaction_text(kind, fresh),
            ))

    # Standing walls (largest absolute OI)
    add(df.nlargest(top_n, "ce_oi"), "resistance", "call_oi", "ce_oi", "ce_chg_oi", False)
    add(df.nlargest(top_n, "pe_oi"), "support", "put_oi", "pe_oi", "pe_chg_oi", False)
    # Fresh positioning today (largest positive OI change)
    add(df.nlargest(top_n, "ce_chg_oi"), "resistance", "call_oi_change", "ce_oi", "ce_chg_oi", True)
    add(df.nlargest(top_n, "pe_chg_oi"), "support", "put_oi_change", "pe_oi", "pe_chg_oi", True)

    mp = max_pain(df)
    p = pcr(df)

    # Immediate actionable band = nearest strong SUPPORT below & RESISTANCE above.
    supports = sorted([l for l in levels if l.kind == "support" and l.strike < spot],
                      key=lambda l: -l.strike)
    resistances = sorted([l for l in levels if l.kind == "resistance" and l.strike > spot],
                         key=lambda l: l.strike)
    # Fallbacks if nothing strictly on the right side.
    if not supports:
        supports = sorted([l for l in levels if l.strike < spot], key=lambda l: -l.strike)
    if not resistances:
        resistances = sorted([l for l in levels if l.strike > spot], key=lambda l: l.strike)

    return {
        "spot": float(spot),
        "expiry": expiry or raw["records"]["expiryDates"][0],
        "max_pain": mp,
        "pcr": round(p, 3),
        "pcr_signal": _pcr_signal(p),
        "immediate_support": supports[0].to_dict() if supports else None,
        "immediate_resistance": resistances[0].to_dict() if resistances else None,
        "levels": [l.to_dict() for l in levels],
        "strike_frame": df.to_dict(orient="records"),
    }


def _pcr_signal(p: float) -> str:
    if p >= 1.3:
        return "High PCR (put-heavy): bullish underlying bias, but >1.5 is over-stretched (contrarian sell risk)."
    if p <= 0.7:
        return "Low PCR (call-heavy): bearish underlying bias, but <0.5 is over-stretched (contrarian buy risk)."
    return "Neutral PCR: range-bound; trade the support/resistance band."
