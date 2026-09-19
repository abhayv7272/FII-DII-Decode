"""Compact, timestamped forward-research market-context records.

The production daily decoder intentionally does not consume this module.  Its
purpose is to preserve the missing time-sensitive inputs needed for later
point-in-time research: pre-open state and intraday option-chain aggregates.

Raw intraday chains can be large.  The default collector stores a compact,
auditable aggregate plus a SHA-256 fingerprint of the validated payload.  A raw
snapshot is saved only when the operator explicitly asks for it.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser

IST = ZoneInfo("Asia/Kolkata")


def _number(value: Any) -> float | None:
    try:
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _nonnegative(value: Any) -> float:
    number = _number(value)
    return number if number is not None and number >= 0 else 0.0


def _signed(value: Any) -> float:
    """Return a finite signed change; negative change-OI is informative unwinding."""
    number = _number(value)
    return number if number is not None else 0.0


def _date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date_parser.parse(str(value), dayfirst=True, fuzzy=True).date()
    except (TypeError, ValueError, OverflowError):
        return None


def payload_sha256(payload: dict) -> str:
    """Fingerprint a payload without keeping an ever-growing raw archive."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _weighted_mean(records: list[tuple[float, float]]) -> float | None:
    valid = [(value, weight) for value, weight in records if value > 0 and weight > 0]
    if not valid:
        return None
    denom = sum(weight for _, weight in valid)
    return sum(value * weight for value, weight in valid) / denom if denom else None


def _expiry_for_snapshot(raw_rows: list[dict], capture_date: date) -> tuple[date | None, list[dict]]:
    """Select the nearest non-expired chain expiry without knowing a future price."""
    expiry_rows: dict[date, list[dict]] = {}
    undated: list[dict] = []
    for row in raw_rows:
        expiry = _date(row.get("expiryDate"))
        if expiry is None:
            undated.append(row)
        else:
            expiry_rows.setdefault(expiry, []).append(row)
    non_expired = sorted(expiry for expiry in expiry_rows if expiry >= capture_date)
    if non_expired:
        expiry = non_expired[0]
        return expiry, expiry_rows[expiry]
    # Some providers omit expiryDate on individual strikes after already
    # filtering to one expiry.  It is safe only when all usable rows are undated.
    return None, undated


def option_chain_snapshot(
    raw: dict,
    *,
    symbol: str,
    captured_at: datetime,
    source_metadata: dict[str, Any],
    quote: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reduce a validated option chain to a compact forward-research snapshot.

    ``captured_at`` must be timezone-aware so a later replay can establish exact
    entry ordering.  The caller is responsible for accepting only a direct/live
    source; this function records whether a fallback was used for auditability.
    """
    if captured_at.tzinfo is None:
        raise ValueError("captured_at must be timezone-aware")
    records = raw.get("records") if isinstance(raw, dict) else None
    if not isinstance(records, dict):
        raise ValueError("option chain has no records object")
    spot = _number(records.get("underlyingValue"))
    raw_rows = records.get("data")
    if spot is None or spot <= 0 or not isinstance(raw_rows, list):
        raise ValueError("option chain has no positive spot/data rows")

    capture_date = captured_at.astimezone(IST).date()
    source_timestamp = records.get("timestamp")
    if _date(source_timestamp) != capture_date:
        raise ValueError(
            f"option-chain source timestamp date {_date(source_timestamp)} != capture date {capture_date}"
        )
    # A bare EOD date cannot establish what was visible at a particular
    # intraday interaction. NSE's live endpoint supplies a clock timestamp.
    if not isinstance(source_timestamp, str) or ":" not in source_timestamp:
        raise ValueError("option-chain source timestamp has no clock time")
    expiry, rows = _expiry_for_snapshot(raw_rows, capture_date)
    parsed: list[dict[str, Any]] = []
    for row in rows:
        strike = _number(row.get("strikePrice"))
        if strike is None or strike <= 0:
            continue
        ce = row.get("CE") if isinstance(row.get("CE"), dict) else {}
        pe = row.get("PE") if isinstance(row.get("PE"), dict) else {}
        if not ce and not pe:
            continue
        parsed.append({"strike": strike, "ce": ce, "pe": pe})
    if len(parsed) < 5:
        raise ValueError("option chain has fewer than five usable strikes for selected expiry")

    parsed.sort(key=lambda item: item["strike"])
    nearest = sorted(parsed, key=lambda item: abs(item["strike"] - spot))[:5]
    ce_oi = sum(_nonnegative(item["ce"].get("openInterest")) for item in parsed)
    pe_oi = sum(_nonnegative(item["pe"].get("openInterest")) for item in parsed)
    # Unlike OI/volume, day change in OI is intentionally signed: a negative
    # total is an unwind signal, not missing data or zero activity.
    ce_change = sum(_signed(item["ce"].get("changeinOpenInterest")) for item in parsed)
    pe_change = sum(_signed(item["pe"].get("changeinOpenInterest")) for item in parsed)
    ce_volume = sum(_nonnegative(item["ce"].get("totalTradedVolume")) for item in parsed)
    pe_volume = sum(_nonnegative(item["pe"].get("totalTradedVolume")) for item in parsed)
    call_wall = max(parsed, key=lambda item: _nonnegative(item["ce"].get("openInterest")))
    put_wall = max(parsed, key=lambda item: _nonnegative(item["pe"].get("openInterest")))
    call_doi_wall = max(parsed, key=lambda item: _signed(item["ce"].get("changeinOpenInterest")))
    put_doi_wall = max(parsed, key=lambda item: _signed(item["pe"].get("changeinOpenInterest")))
    call_unwind_wall = min(parsed, key=lambda item: _signed(item["ce"].get("changeinOpenInterest")))
    put_unwind_wall = min(parsed, key=lambda item: _signed(item["pe"].get("changeinOpenInterest")))
    atm = min(parsed, key=lambda item: abs(item["strike"] - spot))

    def near_sum(side: str, field: str) -> float:
        normalise = _signed if field == "changeinOpenInterest" else _nonnegative
        return sum(normalise(item[side].get(field)) for item in nearest)

    def quote_number(*keys: str) -> float | None:
        for key in keys:
            if quote and key in quote:
                candidate = _number(quote[key])
                if candidate is not None:
                    return candidate
        return None

    captured_utc = captured_at.astimezone(timezone.utc)
    captured_ist = captured_at.astimezone(IST)
    output = {
        "captured_at_utc": captured_utc.isoformat(),
        "captured_at_ist": captured_ist.isoformat(),
        "session_date": capture_date.isoformat(),
        "symbol": symbol.upper(),
        "source": source_metadata.get("source"),
        "source_url": source_metadata.get("url"),
        "source_as_of": source_metadata.get("as_of"),
        "source_fallback": bool(source_metadata.get("fallback", False)),
        "source_timestamp": source_timestamp,
        "payload_sha256": payload_sha256(raw),
        "spot": spot,
        "selected_expiry": expiry.isoformat() if expiry else None,
        "expiry_is_row_declared": expiry is not None,
        "strike_count": len(parsed),
        "atm_strike": atm["strike"],
        "call_oi": ce_oi,
        "put_oi": pe_oi,
        "pcr_oi": pe_oi / ce_oi if ce_oi else None,
        "call_change_oi": ce_change,
        "put_change_oi": pe_change,
        "pcr_change_oi": pe_change / ce_change if ce_change else None,
        "call_volume": ce_volume,
        "put_volume": pe_volume,
        "pcr_volume": pe_volume / ce_volume if ce_volume else None,
        "near_call_oi": near_sum("ce", "openInterest"),
        "near_put_oi": near_sum("pe", "openInterest"),
        "near_call_change_oi": near_sum("ce", "changeinOpenInterest"),
        "near_put_change_oi": near_sum("pe", "changeinOpenInterest"),
        "near_call_volume": near_sum("ce", "totalTradedVolume"),
        "near_put_volume": near_sum("pe", "totalTradedVolume"),
        "call_wall_strike": call_wall["strike"],
        "put_wall_strike": put_wall["strike"],
        "call_wall_oi": _nonnegative(call_wall["ce"].get("openInterest")),
        "put_wall_oi": _nonnegative(put_wall["pe"].get("openInterest")),
        "call_doi_wall_strike": call_doi_wall["strike"],
        "put_doi_wall_strike": put_doi_wall["strike"],
        "call_doi_wall": _signed(call_doi_wall["ce"].get("changeinOpenInterest")),
        "put_doi_wall": _signed(put_doi_wall["pe"].get("changeinOpenInterest")),
        "call_unwind_wall_strike": call_unwind_wall["strike"],
        "put_unwind_wall_strike": put_unwind_wall["strike"],
        "call_unwind_wall": _signed(call_unwind_wall["ce"].get("changeinOpenInterest")),
        "put_unwind_wall": _signed(put_unwind_wall["pe"].get("changeinOpenInterest")),
        "call_iv_oi_weighted": _weighted_mean([
            (_nonnegative(item["ce"].get("impliedVolatility")), _nonnegative(item["ce"].get("openInterest")))
            for item in parsed
        ]),
        "put_iv_oi_weighted": _weighted_mean([
            (_nonnegative(item["pe"].get("impliedVolatility")), _nonnegative(item["pe"].get("openInterest")))
            for item in parsed
        ]),
        "quote_open": quote_number("open"),
        "quote_high": quote_number("high"),
        "quote_low": quote_number("low"),
        "quote_last": quote_number("last", "lastPrice", "close"),
        "quote_previous_close": quote_number("previousClose", "previous_close"),
    }
    return output
