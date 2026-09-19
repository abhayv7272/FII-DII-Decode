"""Quality gates for forward context, deliberately independent of outcomes."""
from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fiidii.forward_audit import audit_forward_context

IST = ZoneInfo("Asia/Kolkata")
SESSION = date(2026, 9, 19)


def _utc_iso(hour: int, minute: int) -> str:
    return datetime(2026, 9, 19, hour, minute, tzinfo=IST).astimezone(ZoneInfo("UTC")).isoformat()


def _complete_session_frames():
    preopen = pd.DataFrame([
        {
            "session_date": SESSION.isoformat(),
            "captured_at_utc": _utc_iso(9, 10),
            "source": "NSE pre-open market-data API",
            "source_fallback": False,
            "timestamp": "19-Sep-2026 09:09:30",
            "state_type": "constituent_breadth",
            "payload_sha256": "preopenhash",
            "source_lag_seconds": 30,
        }
    ])
    intraday_times = [time(9, 15)]
    hour, minute = 9, 30
    while (hour, minute) <= (13, 45):
        intraday_times.append(time(hour, minute))
        minute += 15
        if minute == 60:
            hour += 1
            minute = 0
    intraday_times.append(time(15, 30))
    assert len(intraday_times) == 20
    intraday = pd.DataFrame([
        {
            "session_date": SESSION.isoformat(),
            "captured_at_utc": _utc_iso(value.hour, value.minute),
            "source": "NSE option-chain API",
            "source_fallback": False,
            "source_timestamp": f"19-Sep-2026 {value:%H:%M}:00",
            "source_lag_seconds": 15,
            "payload_sha256": f"chainhash-{number}",
        }
        for number, value in enumerate(intraday_times)
    ])
    return preopen, intraday


def test_forward_audit_accepts_a_complete_direct_timed_session():
    preopen, intraday = _complete_session_frames()
    summary = audit_forward_context(preopen, intraday)
    assert summary["sessions_seen"] == 1
    assert summary["complete_sessions"] == 1
    assert summary["sessions"][0]["reasons"] == []
    assert summary["readiness"]["status"] == "COLLECTING_FORWARD_CONTEXT"
    assert "outcome" in summary["purpose"].lower()


def test_forward_audit_rejects_fallback_and_missing_late_coverage():
    preopen, intraday = _complete_session_frames()
    preopen.loc[0, "source_lag_seconds"] = 601
    intraday.loc[0, "source_fallback"] = True
    intraday = intraday.iloc[:-1].copy()
    summary = audit_forward_context(preopen, intraday)
    reasons = summary["sessions"][0]["reasons"]
    assert summary["complete_sessions"] == 0
    assert "preopen_source_lag_invalid" in reasons
    assert "intraday_not_direct_nse" in reasons
    assert "intraday_too_few_snapshots" in reasons
    assert "intraday_missing_late_window" in reasons


def test_forward_audit_fails_closed_when_store_schema_is_absent():
    summary = audit_forward_context(pd.DataFrame(), pd.DataFrame())
    assert summary["sessions_seen"] == 0
    assert summary["complete_sessions"] == 0
    assert "session_date" in summary["missing_required_columns"]["preopen"]
    assert not summary["readiness"]["frozen_study_ready"]
