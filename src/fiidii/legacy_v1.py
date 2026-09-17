"""Frozen v1 decoder retained for reproducible v1-vs-v2 comparisons.

The decode engine — Amit Dhamija's Participant-OI methodology.

See docs/methodology.md for the full line-by-line reconstruction. Summary of the
rules implemented here:

CORE THESIS
  Zero-sum market; ~90% of Retail (Client) loses; that money goes to Smart Money
  (FII + Pro). So: FADE Retail, FOLLOW Smart Money.

PARTICIPANTS
  Client = Retail (contra indicator).  DII = mostly arb (ignored for F&O direction).
  FII = short-to-medium term  -> drives POSITIONAL / weekly view.
  Pro = ultra-short term (1-2 days) -> drives NEXT-DAY view.
  Smart Money = FII + Pro.

INSTRUMENT IMPORTANCE (rank): Index Options > Stock Options > Index Fut > Stock Fut.
  Options carry the most money / leverage, especially option buying.

BIAS PER ACTION
  Smart Money:  Call BUY = bullish;  Call WRITE(short) = bearish;
                Put WRITE(short/sell) = bullish (support);  Put BUY(long) = bearish.
  Retail:       same actions read INVERTED (contra).

QUALITY OF MOVE
  Fresh Long buildup = real strength.  Short covering = weak (gap-up-and-die).

HORIZON
  Next-day view  -> weight Pro more.
  Positional view-> weight FII more (Pro must be supportive).

CONFLICT
  FII vs Pro opposite => expect one-sided move then reversal (flagged).

Each signal scores in [-1,+1]; weighted & normalised into TWO composites:
  * intraday_composite (Pro-led)  -> next-day
  * positional_composite (FII-led)-> next-week
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

import pandas as pd


# Instrument-importance multipliers (options first, index over stock).
INSTRUMENT_WEIGHT = {
    "index_call": 1.00,
    "index_put": 1.00,
    "stock_call": 0.55,
    "stock_put": 0.55,
    "index_fut": 0.80,
    "stock_fut": 0.40,
}

# How much each participant's read feeds the NEXT-DAY (Pro-led) composite ...
INTRADAY_PARTICIPANT_WEIGHT = {"Pro": 0.50, "FII": 0.30, "Client": 0.20, "DII": 0.0}
# ... and the POSITIONAL (FII-led) composite.
POSITIONAL_PARTICIPANT_WEIGHT = {"FII": 0.50, "Pro": 0.30, "Client": 0.20, "DII": 0.0}


@dataclass
class Signal:
    name: str
    score: float          # -1 .. +1
    weight: float
    note: str

    def contribution(self) -> float:
        return self.score * self.weight


@dataclass
class DecodeResult:
    date: str
    # Next-day (Pro-led)
    bias: str
    composite: float
    confidence: float
    # Positional (FII-led)
    positional_bias: str
    positional_composite: float
    positional_confidence: float
    # Diagnostics
    smart_money_conflict: bool = False
    conflict_note: str = ""
    retail_note: str = ""
    move_quality: str = ""          # "fresh longs" / "short covering" / etc.
    signals: list = field(default_factory=list)
    participant_reads: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["signals"] = [asdict(s) if isinstance(s, Signal) else s for s in self.signals]
        return d


# --------------------------------------------------------------------------- #
def _col(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    norm = {c.lower().replace(" ", "").replace("_", ""): c for c in df.columns}
    for cand in candidates:
        key = cand.lower().replace(" ", "").replace("_", "")
        if key in norm:
            return norm[key]
    return None


def _row(df: Optional[pd.DataFrame], participant: str) -> Optional[pd.Series]:
    if df is None or "ClientType" not in df.columns:
        return None
    m = df[df["ClientType"].str.upper() == participant.upper()]
    return m.iloc[0] if len(m) else None


def _num(row: pd.Series, col: Optional[str]) -> float:
    if row is None or col is None:
        return 0.0
    v = row.get(col, 0)
    try:
        return float(v) if pd.notna(v) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _clip(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _sig(x: float, scale: float) -> float:
    """Smooth-ish squashing to [-1,1] using a linear/clip on x/scale."""
    return _clip(x / scale) if scale else 0.0


# --------------------------------------------------------------------------- #
# Column resolution once (shared across participants).
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


def _instrument_biases(row_today: pd.Series, row_prev: Optional[pd.Series],
                       C: dict, contra: bool) -> dict:
    """Return per-instrument bullish/bearish scores in [-1,1] for one participant.

    Uses TODAY'S CHANGE (fresh action) primarily; falls back to the carry level.
    `contra=True` inverts everything (for Retail/Client).
    Sign convention (before contra):
      Futures long-net > 0 => bullish.
      Calls: long-net > 0 => bullish (buying calls); short-net (writing) => bearish.
      Puts:  short-net > 0 (writing/selling puts) => bullish; long-net => bearish.
    """
    def net(lc, sc):  # long - short (carry)
        return _num(row_today, C[lc]) - _num(row_today, C[sc])

    def net_change(lc, sc):
        if row_prev is None:
            return None
        prev = _num(row_prev, C[lc]) - _num(row_prev, C[sc])
        return net(lc, sc) - prev

    def score_dir(lc, sc, bullish_when_long: bool, scale: float):
        """Score based on change (fresh) else carry; bullish_when_long flips for puts."""
        ch = net_change(lc, sc)
        raw = ch if ch is not None else net(lc, sc)
        s = _sig(raw, scale)
        if not bullish_when_long:
            s = -s
        return s

    # Scales tuned to typical index/stock OI magnitudes (contracts).
    reads = {
        "index_fut": score_dir("fut_idx_l", "fut_idx_s", True, 30000),
        "stock_fut": score_dir("fut_stk_l", "fut_stk_s", True, 300000),
        # Calls: long => bullish.
        "index_call": score_dir("opt_idx_cl", "opt_idx_cs", True, 120000),
        "stock_call": score_dir("opt_stk_cl", "opt_stk_cs", True, 80000),
        # Puts: LONG => bearish, so bullish_when_long=False.
        "index_put": score_dir("opt_idx_pl", "opt_idx_ps", False, 120000),
        "stock_put": score_dir("opt_stk_pl", "opt_stk_ps", False, 80000),
    }
    if contra:
        reads = {k: -v for k, v in reads.items()}
    return reads


def _participant_composite(reads: dict) -> float:
    tw = sum(INSTRUMENT_WEIGHT[k] for k in reads)
    return _clip(sum(reads[k] * INSTRUMENT_WEIGHT[k] for k in reads) / tw) if tw else 0.0


def _move_quality(fii_t, fii_p, pro_t, pro_p, C) -> str:
    """Fresh longs vs short covering on index futures for Smart Money."""
    if fii_p is None and pro_p is None:
        return "unknown (no previous day)"
    notes = []
    for name, t, p in (("FII", fii_t, fii_p), ("Pro", pro_t, pro_p)):
        if t is None or p is None:
            continue
        dl = _num(t, C["fut_idx_l"]) - _num(p, C["fut_idx_l"])
        ds = _num(t, C["fut_idx_s"]) - _num(p, C["fut_idx_s"])
        if dl > 0 and abs(dl) >= abs(ds):
            notes.append(f"{name}: fresh longs added (real strength)")
        elif ds < 0 and abs(ds) > abs(dl):
            notes.append(f"{name}: short covering (weaker, gap-up risk)")
        elif ds > 0 and abs(ds) >= abs(dl):
            notes.append(f"{name}: fresh shorts added (real weakness)")
        elif dl < 0:
            notes.append(f"{name}: long unwinding")
    return "; ".join(notes) if notes else "flat positioning"


# --------------------------------------------------------------------------- #
def decode(
    oi_today: pd.DataFrame,
    oi_prev: Optional[pd.DataFrame] = None,
    cash: Optional[dict] = None,
    option_levels: Optional[dict] = None,
    date_str: str = "",
) -> DecodeResult:
    C = _resolve_cols(oi_today)
    signals: list[Signal] = []
    metrics: dict = {}
    participant_reads: dict = {}

    rows_t = {p: _row(oi_today, p) for p in ("FII", "Pro", "Client", "DII")}
    rows_p = {p: _row(oi_prev, p) for p in ("FII", "Pro", "Client", "DII")}

    # Per-participant instrument reads + composite (Client is contra).
    comp = {}
    for p in ("FII", "Pro", "Client", "DII"):
        if rows_t[p] is None:
            continue
        contra = (p == "Client")
        reads = _instrument_biases(rows_t[p], rows_p[p], C, contra=contra)
        participant_reads[p] = {k: round(v, 3) for k, v in reads.items()}
        comp[p] = _participant_composite(reads)

    # --- Build NEXT-DAY (Pro-led) and POSITIONAL (FII-led) composites -------- #
    def blended(weight_map):
        tw = sum(weight_map[p] for p in comp if weight_map.get(p, 0))
        if not tw:
            return 0.0
        return _clip(sum(comp[p] * weight_map[p] for p in comp
                         if weight_map.get(p, 0)) / tw)

    intraday = blended(INTRADAY_PARTICIPANT_WEIGHT)
    positional = blended(POSITIONAL_PARTICIPANT_WEIGHT)

    # Signals list (transparent breakdown) — one per participant + cash.
    for p in ("Pro", "FII", "Client", "DII"):
        if p not in comp:
            continue
        w = INTRADAY_PARTICIPANT_WEIGHT[p]
        label = {"Pro": "Pro (ultra-short, next-day driver)",
                 "FII": "FII (short-medium, positional driver)",
                 "Client": "Client/Retail (CONTRA — faded)",
                 "DII": "DII (arb — ignored for direction)"}[p]
        top = sorted(participant_reads[p].items(), key=lambda kv: -abs(kv[1]))[:3]
        top_txt = ", ".join(f"{k} {v:+.2f}" for k, v in top)
        signals.append(Signal(f"{p}_composite", round(comp[p], 3), w,
                              f"{label}: net {comp[p]:+.2f} [{top_txt}]."))

    # --- Cash flow ---------------------------------------------------------- #
    cash_score = None
    if cash:
        fii_net = _extract_cash_net(cash, "FII")
        dii_net = _extract_cash_net(cash, "DII")
        if fii_net is not None:
            metrics["fii_cash_net"] = fii_net
            metrics["dii_cash_net"] = dii_net
            combined = fii_net + (dii_net or 0) * 0.6
            cash_score = _sig(combined, 3000.0)
            signals.append(Signal("cash_flow", round(cash_score, 3), 0.15,
                                  f"Cash: FII net {fii_net:,.0f} Cr, "
                                  f"DII net {dii_net or 0:,.0f} Cr."))
            # Nudge both composites slightly with cash confirmation.
            intraday = _clip(intraday * 0.9 + cash_score * 0.1)
            positional = _clip(positional * 0.85 + cash_score * 0.15)

    # --- Smart-money conflict (FII vs Pro opposite) ------------------------- #
    conflict = False
    conflict_note = ""
    if "FII" in comp and "Pro" in comp:
        if comp["FII"] * comp["Pro"] < 0 and min(abs(comp["FII"]), abs(comp["Pro"])) > 0.12:
            conflict = True
            fii_dir = "bullish" if comp["FII"] > 0 else "bearish"
            pro_dir = "bullish" if comp["Pro"] > 0 else "bearish"
            conflict_note = (
                f"Smart-money SPLIT: FII {fii_dir} ({comp['FII']:+.2f}) vs "
                f"Pro {pro_dir} ({comp['Pro']:+.2f}). Expect a one-sided move first "
                f"(driven by 9 AM news) THEN a reversal — the classic dip-then-recover "
                f"(or pop-then-fade) setup. Watch institutional levels for the turn.")

    # --- Retail note -------------------------------------------------------- #
    retail_note = ""
    if "Client" in comp:
        rc = comp["Client"]  # already contra-adjusted (bullish-for-market sign)
        # Reconstruct raw retail lean for wording.
        raw_bullish = rc < 0  # contra-adjusted negative => retail itself bullish
        if raw_bullish:
            retail_note = ("Retail is net BULLISH → upside likely CAPPED / "
                           "'sell on rise' until retail unwinds. Reversal-up trigger = "
                           "retail starts unwinding longs / builds puts.")
        else:
            retail_note = ("Retail is net BEARISH → contrarian POSITIVE for market "
                           "(retail exiting longs is the fuel for a rally).")

    # --- Move quality ------------------------------------------------------- #
    quality = _move_quality(rows_t["FII"], rows_p["FII"], rows_t["Pro"], rows_p["Pro"], C)

    # --- Carry / key metrics ------------------------------------------------ #
    for p in ("FII", "Pro", "Client"):
        r = rows_t[p]
        if r is not None:
            metrics[f"{p.lower()}_index_fut_net"] = (
                _num(r, C["fut_idx_l"]) - _num(r, C["fut_idx_s"]))
    if option_levels:
        metrics.update({k: option_levels.get(k) for k in ("max_pain", "pcr", "spot")})

    # --- Confidence --------------------------------------------------------- #
    def confidence(composite, driver):
        base = abs(composite) * 60
        # Agreement between the driver group and the composite direction.
        agree = 40 if (driver in comp and (comp[driver] > 0) == (composite > 0)
                       and comp[driver] != 0) else 0
        conf = base + agree * 0.6
        if conflict:
            conf *= 0.75  # split smart money => lower confidence
        return round(min(100, conf), 1)

    return DecodeResult(
        date=date_str,
        bias=_bias_label(intraday), composite=round(intraday, 3),
        confidence=confidence(intraday, "Pro"),
        positional_bias=_bias_label(positional), positional_composite=round(positional, 3),
        positional_confidence=confidence(positional, "FII"),
        smart_money_conflict=conflict, conflict_note=conflict_note,
        retail_note=retail_note, move_quality=quality,
        signals=signals, participant_reads=participant_reads, metrics=metrics,
    )


def _bias_label(x: float) -> str:
    if x >= 0.45:
        return "STRONG BULLISH"
    if x >= 0.12:
        return "BULLISH"
    if x <= -0.45:
        return "STRONG BEARISH"
    if x <= -0.12:
        return "BEARISH"
    return "NEUTRAL"


def _extract_cash_net(cash, group: str) -> Optional[float]:
    if isinstance(cash, list):
        for row in cash:
            cat = str(row.get("category", "")).upper().replace(" ", "").replace("*", "")
            if group.upper() in cat:
                for k in ("netValue", "netvalue", "net"):
                    if k in row:
                        try:
                            return float(str(row[k]).replace(",", ""))
                        except (TypeError, ValueError):
                            pass
    elif isinstance(cash, dict):
        v = cash.get(group)
        if isinstance(v, (int, float)):
            return float(v)
    return None
