"""Quality/readiness audit for the timestamped forward-context stores.

This is deliberately *not* a predictor and it never reads market outcomes.  It
answers the earlier question that must be settled before any model work: did we
actually collect enough direct, correctly timed observations to freeze a
forward study without silently treating missing or later EOD data as live?
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

IST = ZoneInfo("Asia/Kolkata")

# The scheduled workflow intends one pre-open capture and 26 chain captures.
# These checks tolerate an occasional delayed/missing run without calling a
# thin or partial session "complete".
PREOPEN_START = time(9, 0)
PREOPEN_END = time(9, 15)
INTRADAY_START = time(9, 15)
INTRADAY_FIRST_LATEST = time(9, 25)
INTRADAY_LAST_EARLIEST = time(15, 20)
INTRADAY_END = time(15, 45)
MIN_INTRADAY_SNAPSHOTS = 20

# These are session counts, never 15-minute-row counts: intraday samples inside
# one day are correlated and must not be used to inflate statistical evidence.
QUALITY_GATE_SESSIONS = 80
FROZEN_STUDY_SESSIONS = 200  # 80 development + 60 validation + 60 confirmation
PROMOTION_FORWARD_SESSIONS = 260  # then 60 untouched fresh sessions


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _ist_timestamp(value: Any) -> datetime | None:
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime().astimezone(IST)


def _source_timestamp_date(value: Any) -> date | None:
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return parsed.date()


def _session_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _in_window(value: datetime, start: time, end: time) -> bool:
    local_time = value.timetz().replace(tzinfo=None)
    return start <= local_time < end


def _preopen_reasons(rows: pd.DataFrame, session: date) -> list[str]:
    if len(rows) != 1:
        return ["preopen_not_exactly_one_row"]
    row = rows.iloc[0]
    reasons: list[str] = []
    if row.get("source") != "NSE pre-open market-data API" or _truthy(row.get("source_fallback")):
        reasons.append("preopen_not_direct_nse")
    captured = _ist_timestamp(row.get("captured_at_utc"))
    if captured is None or captured.date() != session or not _in_window(captured, PREOPEN_START, PREOPEN_END):
        reasons.append("preopen_capture_outside_window")
    source_date = _source_timestamp_date(row.get("timestamp"))
    if source_date != session or ":" not in str(row.get("timestamp", "")):
        reasons.append("preopen_source_timestamp_invalid")
    if row.get("state_type") not in {"index_quote", "constituent_breadth"}:
        reasons.append("preopen_unknown_state_type")
    if not str(row.get("payload_sha256", "")).strip():
        reasons.append("preopen_missing_payload_fingerprint")
    return reasons


def _intraday_reasons(rows: pd.DataFrame, session: date) -> list[str]:
    reasons: list[str] = []
    if rows.empty:
        return ["intraday_missing"]
    if not (rows["source"].eq("NSE option-chain API")).all() or rows["source_fallback"].map(_truthy).any():
        reasons.append("intraday_not_direct_nse")
    captures = [_ist_timestamp(value) for value in rows["captured_at_utc"]]
    if any(value is None or value.date() != session for value in captures):
        reasons.append("intraday_capture_timestamp_invalid")
        captures = [value for value in captures if value is not None and value.date() == session]
    if captures and any(not _in_window(value, INTRADAY_START, INTRADAY_END) for value in captures):
        reasons.append("intraday_capture_outside_session")
    source_dates = [_source_timestamp_date(value) for value in rows.get("source_timestamp", [])]
    if any(value != session for value in source_dates) or any(":" not in str(value) for value in rows.get("source_timestamp", [])):
        reasons.append("intraday_source_timestamp_invalid")
    if not rows.get("payload_sha256", pd.Series(dtype=str)).astype(str).str.strip().ne("").all():
        reasons.append("intraday_missing_payload_fingerprint")
    if rows["captured_at_utc"].duplicated().any():
        reasons.append("intraday_duplicate_capture_timestamp")
    if len(rows) < MIN_INTRADAY_SNAPSHOTS:
        reasons.append("intraday_too_few_snapshots")
    if captures:
        first_capture = min(captures).timetz().replace(tzinfo=None)
        last_capture = max(captures).timetz().replace(tzinfo=None)
        if first_capture > INTRADAY_FIRST_LATEST:
            reasons.append("intraday_missing_first_window")
        if last_capture < INTRADAY_LAST_EARLIEST:
            reasons.append("intraday_missing_late_window")
    return reasons


def audit_forward_context(preopen: pd.DataFrame, intraday: pd.DataFrame) -> dict[str, Any]:
    """Audit direct/timed collection coverage without accessing labels/outcomes."""
    required_preopen = {"session_date", "captured_at_utc", "source", "source_fallback", "timestamp", "state_type", "payload_sha256"}
    required_intraday = {"session_date", "captured_at_utc", "source", "source_fallback", "source_timestamp", "payload_sha256"}
    preopen = preopen.copy()
    intraday = intraday.copy()
    missing_preopen = sorted(required_preopen - set(preopen.columns))
    missing_intraday = sorted(required_intraday - set(intraday.columns))
    if missing_preopen:
        preopen = pd.DataFrame(columns=sorted(required_preopen))
    if missing_intraday:
        intraday = pd.DataFrame(columns=sorted(required_intraday))

    preopen["_session"] = preopen.get("session_date", pd.Series(dtype=str)).map(_session_date)
    intraday["_session"] = intraday.get("session_date", pd.Series(dtype=str)).map(_session_date)
    sessions = sorted(set(preopen["_session"].dropna()) | set(intraday["_session"].dropna()))
    session_rows: list[dict[str, Any]] = []
    failure_counts: Counter[str] = Counter()
    for session in sessions:
        pre_reasons = _preopen_reasons(preopen[preopen["_session"] == session], session)
        intra_reasons = _intraday_reasons(intraday[intraday["_session"] == session], session)
        reasons = pre_reasons + intra_reasons
        failure_counts.update(reasons)
        session_rows.append(
            {
                "session_date": session.isoformat(),
                "complete": not reasons,
                "preopen_rows": int((preopen["_session"] == session).sum()),
                "intraday_rows": int((intraday["_session"] == session).sum()),
                "reasons": reasons,
            }
        )
    complete_dates = [row["session_date"] for row in session_rows if row["complete"]]
    complete_count = len(complete_dates)
    readiness = {
        "quality_gate_sessions": QUALITY_GATE_SESSIONS,
        "frozen_study_sessions": FROZEN_STUDY_SESSIONS,
        "promotion_forward_sessions": PROMOTION_FORWARD_SESSIONS,
        "quality_gate_ready": complete_count >= QUALITY_GATE_SESSIONS,
        "frozen_study_ready": complete_count >= FROZEN_STUDY_SESSIONS,
        "promotion_forward_ready": complete_count >= PROMOTION_FORWARD_SESSIONS,
        "status": (
            "READY_FOR_PROMOTION_FORWARD_WINDOW"
            if complete_count >= PROMOTION_FORWARD_SESSIONS
            else "READY_TO_FREEZE_STUDY" if complete_count >= FROZEN_STUDY_SESSIONS
            else "READY_FOR_QUALITY_REVIEW" if complete_count >= QUALITY_GATE_SESSIONS
            else "COLLECTING_FORWARD_CONTEXT"
        ),
    }
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Collection-quality audit only; no outcomes, rules, predictions, or accuracy are evaluated.",
        "input_rows": {"preopen": int(len(preopen)), "intraday": int(len(intraday))},
        "missing_required_columns": {"preopen": missing_preopen, "intraday": missing_intraday},
        "sessions_seen": len(sessions),
        "complete_sessions": complete_count,
        "complete_session_dates": complete_dates,
        "failure_counts": dict(sorted(failure_counts.items())),
        "sessions": session_rows,
        "readiness": readiness,
    }
