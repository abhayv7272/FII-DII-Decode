"""The decode engine.

Turns raw participant-wise OI + cash + option-chain data into a directional
read, the way a "FII/DII/Pro/Client decode" YouTube channel does it.

============================================================================
METHODOLOGY (default; refined by the channel transcript in docs/methodology.md)
============================================================================
Participant-wise OI gives, for each group (FII, DII, Pro, Client), their
LONG and SHORT open interest in:
    Future Index, Future Stock, Option Index Call Long/Short,
    Option Index Put Long/Short (and stock equivalents).

Core derived reads:
  1. Index-future net long  = FutureIndexLong - FutureIndexShort  (per group)
     -> The cleanest directional footprint. FII net long rising = bullish.
  2. Long/Short RATIO for FII index futures: how many longs per short.
       ratio > 1  => net long bias; the higher, the more bullish
       ratio < 1  => net short bias; the lower, the more bearish
  3. Option index positioning:
       - Call SHORT (writing) by Pro/FII at highs = bearish/defensive.
       - Put  SHORT (writing) by Pro/FII        = bullish (support building).
       - Call LONG / Put LONG spikes by Client   = often the "wrong-way" crowd.
  4. Client vs Institution divergence:
       Client is usually the contra indicator. When Client is heavily long and
       FII/Pro heavily short (or vice-versa), lean with the institutions.
  5. Cash-market FII/DII net flow confirms or contradicts the F&O footprint.

Each signal is scored (-1 bearish .. +1 bullish), weighted, and combined into a
composite bias with a confidence figure. The weights live in DEFAULT_WEIGHTS so
the transcript's emphasis can be dialed in without touching logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

import pandas as pd


# Tunable weights (sum need not be 1; normalised internally). Refined per PDF.
DEFAULT_WEIGHTS = {
    "fii_index_fut_net": 0.35,
    "fii_index_fut_ratio": 0.15,
    "pro_index_fut_net": 0.15,
    "option_writing_bias": 0.15,
    "client_contra": 0.10,
    "cash_flow": 0.10,
}


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
    bias: str                       # STRONG BULLISH / BULLISH / NEUTRAL / BEARISH / STRONG BEARISH
    composite: float                # -1 .. +1
    confidence: float               # 0 .. 100
    signals: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["signals"] = [asdict(s) if isinstance(s, Signal) else s for s in self.signals]
        return d


# --------------------------------------------------------------------------- #
def _col(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    """Find the first column whose normalised name matches a candidate."""
    norm = {c.lower().replace(" ", "").replace("_", ""): c for c in df.columns}
    for cand in candidates:
        key = cand.lower().replace(" ", "").replace("_", "")
        if key in norm:
            return norm[key]
    return None


def _row(df: pd.DataFrame, participant: str) -> Optional[pd.Series]:
    if "ClientType" not in df.columns:
        return None
    m = df[df["ClientType"].str.upper() == participant.upper()]
    return m.iloc[0] if len(m) else None


def _net(row: pd.Series, long_col: str, short_col: str) -> float:
    return float(row.get(long_col, 0) or 0) - float(row.get(short_col, 0) or 0)


def _ratio(row: pd.Series, long_col: str, short_col: str) -> float:
    s = float(row.get(short_col, 0) or 0)
    l = float(row.get(long_col, 0) or 0)
    return l / s if s else (l if l else 1.0)


def _clip(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


# --------------------------------------------------------------------------- #
def decode(
    oi_today: pd.DataFrame,
    oi_prev: Optional[pd.DataFrame] = None,
    cash: Optional[dict] = None,
    option_levels: Optional[dict] = None,
    weights: Optional[dict] = None,
    date_str: str = "",
) -> DecodeResult:
    """Decode one day's participant OI (+ optional prev day, cash, option levels)."""
    W = {**DEFAULT_WEIGHTS, **(weights or {})}
    signals: list[Signal] = []
    metrics: dict = {}

    fil = _col(oi_today, "Future Index Long", "FutureIndexLong")
    fis = _col(oi_today, "Future Index Short", "FutureIndexShort")
    ocl = _col(oi_today, "Option Index Call Long", "OptionIndexCallLong")
    ocs = _col(oi_today, "Option Index Call Short", "OptionIndexCallShort")
    opl = _col(oi_today, "Option Index Put Long", "OptionIndexPutLong")
    ops = _col(oi_today, "Option Index Put Short", "OptionIndexPutShort")

    fii = _row(oi_today, "FII")
    pro = _row(oi_today, "Pro")
    client = _row(oi_today, "Client")
    dii = _row(oi_today, "DII")

    fii_prev = _row(oi_prev, "FII") if oi_prev is not None else None
    pro_prev = _row(oi_prev, "Pro") if oi_prev is not None else None

    # --- 1. FII index-future net long (level + day-change) ------------------ #
    if fii is not None and fil and fis:
        net = _net(fii, fil, fis)
        metrics["fii_index_fut_net"] = net
        chg = None
        if fii_prev is not None:
            chg = net - _net(fii_prev, fil, fis)
            metrics["fii_index_fut_net_change"] = chg
        # Score primarily on the day-over-day change (fresh positioning),
        # falling back to the sign of the absolute net.
        if chg is not None:
            denom = max(abs(_net(fii, fil, fis)), 20000, abs(chg))
            score = _clip(chg / denom * 3)
            note = (f"FII index-fut net {net:,.0f} "
                    f"({'+' if chg>=0 else ''}{chg:,.0f} vs prev): "
                    f"{'fresh longs' if chg>0 else 'fresh shorts/unwind'}.")
        else:
            score = _clip(net / max(abs(net), 50000))
            note = f"FII index-fut net {net:,.0f} (no prev day to compare)."
        signals.append(Signal("fii_index_fut_net", score, W["fii_index_fut_net"], note))

        # --- 2. FII long/short ratio ---------------------------------------- #
        r = _ratio(fii, fil, fis)
        metrics["fii_index_fut_ls_ratio"] = round(r, 3)
        # ratio 1.0 neutral; scale so 2.0 -> ~+1, 0.5 -> ~-1
        rscore = _clip((r - 1.0)) if r >= 1 else _clip((r - 1.0) * 2)
        signals.append(Signal(
            "fii_index_fut_ratio", rscore, W["fii_index_fut_ratio"],
            f"FII index-fut long/short ratio {r:.2f} "
            f"({'bullish' if r>1.05 else 'bearish' if r<0.95 else 'balanced'})."))

    # --- 3. Pro index-future net -------------------------------------------- #
    if pro is not None and fil and fis:
        net = _net(pro, fil, fis)
        metrics["pro_index_fut_net"] = net
        chg = (net - _net(pro_prev, fil, fis)) if pro_prev is not None else None
        if chg is not None:
            metrics["pro_index_fut_net_change"] = chg
            denom = max(abs(net), 20000, abs(chg))
            score = _clip(chg / denom * 3)
            note = f"Pro index-fut net {net:,.0f} ({'+' if chg>=0 else ''}{chg:,.0f} vs prev)."
        else:
            score = _clip(net / max(abs(net), 50000))
            note = f"Pro index-fut net {net:,.0f}."
        signals.append(Signal("pro_index_fut_net", score, W["pro_index_fut_net"], note))

    # --- 4. Option writing bias (Pro+FII) ----------------------------------- #
    if all([ocl, ocs, opl, ops]) and (fii is not None or pro is not None):
        call_short = put_short = 0.0
        for grp in (fii, pro):
            if grp is not None:
                call_short += float(grp.get(ocs, 0) or 0)
                put_short += float(grp.get(ops, 0) or 0)
        total = call_short + put_short
        if total:
            # More put writing than call writing => bullish (support building).
            ow = (put_short - call_short) / total
            metrics["inst_put_call_write_ratio"] = round(put_short / call_short, 3) if call_short else None
            signals.append(Signal(
                "option_writing_bias", _clip(ow), W["option_writing_bias"],
                f"Institutional option writing: put-writing {put_short:,.0f} vs "
                f"call-writing {call_short:,.0f} => "
                f"{'support building (bullish)' if ow>0 else 'resistance building (bearish)'}."))

    # --- 5. Client contra ---------------------------------------------------- #
    if client is not None and fil and fis:
        cnet = _net(client, fil, fis)
        metrics["client_index_fut_net"] = cnet
        # Client is the crowd; fade extreme client positioning.
        cscore = _clip(-cnet / max(abs(cnet), 80000))
        signals.append(Signal(
            "client_contra", cscore, W["client_contra"],
            f"Client index-fut net {cnet:,.0f}; "
            f"contrarian lean = {'bullish' if cscore>0 else 'bearish'} "
            f"(fade the crowd)."))

    # --- 6. Cash flow -------------------------------------------------------- #
    if cash:
        fii_net = _extract_cash_net(cash, "FII")
        dii_net = _extract_cash_net(cash, "DII")
        if fii_net is not None:
            metrics["fii_cash_net"] = fii_net
            metrics["dii_cash_net"] = dii_net
            combined = fii_net + (dii_net or 0) * 0.5  # DII flows weighted lower
            score = _clip(combined / 3000.0)  # ~3000 Cr => strong day
            signals.append(Signal(
                "cash_flow", score, W["cash_flow"],
                f"Cash: FII net {fii_net:,.0f} Cr, DII net {dii_net or 0:,.0f} Cr."))

    # --- Composite ----------------------------------------------------------- #
    total_w = sum(s.weight for s in signals) or 1.0
    composite = sum(s.contribution() for s in signals) / total_w
    composite = _clip(composite)

    bias = _bias_label(composite)
    # Confidence: magnitude of composite + agreement among signals.
    if signals:
        agree = sum(1 for s in signals if (s.score > 0) == (composite > 0) and s.score != 0)
        agreement = agree / len(signals)
    else:
        agreement = 0.0
    confidence = round(min(100, (abs(composite) * 60 + agreement * 40)), 1)

    if option_levels:
        metrics["max_pain"] = option_levels.get("max_pain")
        metrics["pcr"] = option_levels.get("pcr")
        metrics["spot"] = option_levels.get("spot")

    return DecodeResult(
        date=date_str, bias=bias, composite=round(composite, 3),
        confidence=confidence, signals=signals, metrics=metrics)


def _bias_label(x: float) -> str:
    if x >= 0.5:
        return "STRONG BULLISH"
    if x >= 0.15:
        return "BULLISH"
    if x <= -0.5:
        return "STRONG BEARISH"
    if x <= -0.15:
        return "BEARISH"
    return "NEUTRAL"


def _extract_cash_net(cash, group: str) -> Optional[float]:
    """cash may be a list of dicts from NSE fiidiiTradeReact."""
    if isinstance(cash, list):
        for row in cash:
            cat = str(row.get("category", "")).upper()
            if group.upper() in cat.replace(" ", "").replace("*", ""):
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
