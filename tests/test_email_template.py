"""Tests for the Gmail-compatible HTML email rendering.

These tests deliberately use only the standard library (no pandas) so the
email presentation layer can be verified in any environment. The critical
invariant under test: presentation may never weaken the financial safety
gates — WAIT / NO TRADE stays WAIT, raw probabilities stay labelled as
class probabilities, and gate failures stay loud.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from src.email_template import build_failure_html, build_html_email, build_success_html

PROJECT = Path(__file__).resolve().parents[1]

MARKDOWN = """# NIFTY Professional Decision Report — 2026-09-18

**Generated:** 2026-09-20T06:03:54+05:30
**Data quality:** 100%
**Data gate:** **PASS**
**Final decision:** **WAIT / NO TRADE**

## Executive view

- Specialist direction: **UP**
- Trading stance: **NO DIRECTIONAL POSITION**

## Key levels

- Resistance trigger: **23,394.83**

## Conditional playbook

### Bull path
Support/pivot hold → close above 23,394.83 → retest holds → only then long continuation is valid.
### Bear path
Resistance rejection → close below 23,292.28 → failed reclaim → only then short continuation is valid.
### Trap rule
A wick/sweep alone is not entry confirmation. Wait for a completed candle and follow-through.

## Monday–Friday risk map

| date       |   session |   expected_center |
|:-----------|----------:|------------------:|
| 2026-09-21 |         1 |          23346.40 |

## What not to do

- Do not trade below the confidence or data-quality gate.
- Do not average a losing leveraged position.

## Data-source health

| Dataset      | Selected source | Status   | As-of      |   Rows |
|:-------------|:----------------|:---------|:-----------|-------:|
| nifty_price  | yahoo_yfinance  | fresh    | 2026-09-18 |   2467 |
| india_vix    | nse_vix_archive | failed   | 2026-09-10 |      1 |

## Model evidence

- Later research test: 54.55% accuracy across 99 sessions.
- Current report automatically becomes WAIT if gates fail.

## Risk notice

Research/decision-support only; not personalized investment advice.
"""


def _payload() -> dict:
    return {
        "session_date": "2026-09-18",
        "decision_time_ist": "2026-09-20T06:03:54+05:30",
        "decision": "WAIT / NO TRADE",
        "quality_score": 1.0,
        "data_gate": {
            "passed": True,
            "quality_score": 1.0,
            "critical_fresh_date_matched": {
                "nifty_price": True,
                "nifty_options_eod": True,
                "nifty_futures_eod": True,
            },
            "history_update_ok": True,
        },
        "prediction": {
            "as_of": "2026-09-18",
            "direction": "UP",
            "p_up": 0.8794,
            "p_down": 0.1206,
            "confidence": 0.8794,
            "gate": 0.75,
            "confidence_pass": True,
            "research_approved": False,
            "model_pass": False,
        },
        "prediction_date_matches_session": True,
        "event_risk": {"blocked": False, "status": "NO_VERIFIED_CALENDAR", "events": []},
        "levels": {
            "pivot": 23340.72,
            "support_1": 23292.28,
            "resistance_1": 23394.83,
            "support_20d": 23116.10,
            "resistance_20d": 24378.60,
            "atr14_points": 195.57,
            "previous_close": 23346.40,
        },
        "trade_stance": "NO DIRECTIONAL POSITION",
        "swing_stance": "Do not initiate a new swing position until gates pass.",
        "investment_context": "Index is below its 200-day trend.",
        "weekly_scenarios": [
            {"date": "2026-09-21", "session": 1, "expected_center": 23346.40, "lower_risk_band": 23150.83, "upper_risk_band": 23541.97},
            {"date": "2026-09-22", "session": 2, "expected_center": 23346.40, "lower_risk_band": 23069.83, "upper_risk_band": 23622.98},
        ],
        "failed_sources": [],
        "cached_sources": [],
    }


def _manifest() -> dict:
    return {
        "session_date": "2026-09-18",
        "results": [
            {"dataset": "nifty_price", "source": "yahoo_yfinance", "status": "fresh", "as_of": "2026-09-18", "rows": 2467},
            {"dataset": "india_vix", "source": "nse_vix_archive", "status": "failed", "as_of": "2026-09-10", "rows": 1},
        ],
    }


# ---------------------------------------------------------------------------
# Safety invariants
# ---------------------------------------------------------------------------
def test_wait_decision_is_rendered_verbatim_and_never_becomes_a_trade():
    html = build_success_html(_payload(), _manifest(), MARKDOWN)
    assert "WAIT / NO TRADE" in html
    # The stance forbids directional positions; the email must not invent one.
    assert "LONG BIAS" not in html
    assert "SHORT BIAS" not in html
    assert "BUY" not in html.upper().replace("BUY **", "")
    assert "NO DIRECTIONAL POSITION" in html


def test_research_gate_failure_is_loud_and_probability_stays_diagnostic():
    html = build_success_html(_payload(), _manifest(), MARKDOWN)
    assert "RESEARCH PROMOTION GATE FAILED" in html
    # Raw class probability must never be sold as a profit probability.
    assert "NOT a calibrated profit probability" in html
    assert "class probability" in html


def test_failed_gate_renders_red_alert_and_status():
    payload = _payload()
    payload["data_gate"]["passed"] = False
    payload["data_gate"]["critical_fresh_date_matched"]["nifty_options_eod"] = False
    html = build_success_html(payload, _manifest(), MARKDOWN)
    assert "DATA GATE FAIL-CLOSED" in html
    assert "FAIL-CLOSED" in html  # gate pill
    assert "MISSING" in html  # critical dataset flag


def test_blocked_event_calendar_renders_red_alert():
    payload = _payload()
    payload["event_risk"] = {"blocked": True, "status": "MAJOR_EVENT", "events": []}
    html = build_success_html(payload, _manifest(), MARKDOWN)
    assert "EVENT CALENDAR: MAJOR_EVENT" in html
    assert "Trade blocked by event risk." in html


# ---------------------------------------------------------------------------
# Gmail compatibility
# ---------------------------------------------------------------------------
def test_gmail_compatible_inline_css_and_no_external_resources():
    html = build_success_html(_payload(), _manifest(), MARKDOWN)
    assert html.startswith("<!DOCTYPE html")
    assert "<style" not in html  # Gmail strips style blocks; all CSS must be inline
    assert "style=" in html  # inline styles present
    assert "<table" in html  # table-based layout
    # No external fetches of any kind.
    assert 'src="http' not in html
    assert "href=" not in html
    assert "background:url" not in html.lower()


def test_source_health_renders_status_pills():
    html = build_success_html(_payload(), _manifest(), MARKDOWN)
    assert "nifty_price" in html
    assert "yahoo_yfinance" in html
    assert "fresh" in html
    assert "failed" in html


def test_weekly_risk_map_renders_all_sessions():
    html = build_success_html(_payload(), _manifest(), MARKDOWN)
    assert "2026-09-21" in html
    assert "2026-09-22" in html
    assert "23,346.40" in html
    assert "23,150.83" in html


def test_key_levels_rendered():
    html = build_success_html(_payload(), _manifest(), MARKDOWN)
    for value in ("23,394.83", "23,340.72", "23,292.28", "195.57"):
        assert value in html


def test_markdown_fallback_when_payload_missing():
    html = build_html_email(MARKDOWN, None, None)
    # Decision recovered from markdown, never defaulted to a trade.
    assert "WAIT / NO TRADE" in html
    assert "2026-09-18" in html
    # Source-health table parsed from the markdown fallback.
    assert "nifty_price" in html
    assert "yahoo_yfinance" in html


# ---------------------------------------------------------------------------
# Failure email
# ---------------------------------------------------------------------------
FAILURE_MARKDOWN = """# NIFTY PIPELINE FAILURE

**UTC time:** 2026-09-20T15:30:00+00:00  
**Tests:** failure  
**Production pipeline:** skipped

No trading decision should be used from this failed run. The safe decision is **WAIT / NO TRADE**.

## Test log tail

```text
ERROR test_hardening - assert 1 == 2
```

## Production log tail

```text
Pipeline skipped because tests failed.
```
"""


def test_failure_email_renders_safe_decision():
    html = build_failure_html(FAILURE_MARKDOWN)
    assert "PIPELINE FAILURE" in html
    assert "SAFE DECISION: WAIT / NO TRADE" in html
    assert "FAILURE" in html  # tests status
    assert "SKIPPED" in html  # pipeline status
    assert "assert 1 == 2" in html  # log tail kept


def test_dispatcher_routes_failure_markdown():
    assert "PIPELINE FAILURE" in build_html_email(FAILURE_MARKDOWN, None, None)


# ---------------------------------------------------------------------------
# Full message composition (scripts/send_email_report.py)
# ---------------------------------------------------------------------------
@pytest.fixture()
def send_email_report():
    spec = importlib.util.spec_from_file_location(
        "send_email_report", PROJECT / "scripts" / "send_email_report.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_compose_message_keeps_plain_markdown_html_and_attachments(tmp_path, send_email_report):
    report = tmp_path / "2026-09-18_professional_report.md"
    report.write_text(MARKDOWN, encoding="utf-8")
    report_json = tmp_path / "2026-09-18_professional_report.json"
    report_json.write_text(json.dumps(_payload()), encoding="utf-8")
    manifest = tmp_path / "latest_manifest.json"
    manifest.write_text(json.dumps(_manifest()), encoding="utf-8")
    audit = tmp_path / "ultra_hard_audit.md"
    audit.write_text("# Ultra-hard audit\nAll checks passed.", encoding="utf-8")

    msg = send_email_report.compose_message(
        MARKDOWN, report, report_json, manifest, audit, to="user@example.com", sender="bot@example.com"
    )

    assert msg["To"] == "user@example.com"
    assert msg["From"] == "bot@example.com"
    # Subject carries session and decision verbatim.
    assert "2026-09-18" in msg["Subject"]
    assert "WAIT / NO TRADE" in msg["Subject"]

    body = msg.get_body(preferencelist=("plain",))
    assert body is not None
    assert "Final decision" in body.get_content()

    html_body = msg.get_body(preferencelist=("html",))
    assert html_body is not None
    assert html_body.get_content().startswith("<!DOCTYPE html")

    attachments = {part.get_filename(): part for part in msg.walk() if part.get_content_disposition() == "attachment"}
    assert set(attachments) == {
        "2026-09-18_professional_report.md",
        "2026-09-18_professional_report.json",
        "latest_manifest.json",
        "ultra_hard_audit.md",
    }
    # JSON report must be attached untouched.
    assert json.loads(attachments["2026-09-18_professional_report.json"].get_content())["decision"] == "WAIT / NO TRADE"


def test_compose_message_failure_report_keeps_wait_safety(tmp_path, send_email_report):
    report = tmp_path / "LATEST_EMAIL_REPORT.md"
    report.write_text(FAILURE_MARKDOWN, encoding="utf-8")
    report_json = tmp_path / "missing.json"  # absent -> payload None
    manifest = tmp_path / "missing_manifest.json"  # absent -> manifest None
    audit = tmp_path / "ultra_hard_audit.md"
    audit.write_text("# audit", encoding="utf-8")

    msg = send_email_report.compose_message(
        FAILURE_MARKDOWN, report, report_json, manifest, audit, to="user@example.com", sender="bot@example.com"
    )
    assert "PIPELINE FAILURE" in msg["Subject"]
    html_body = msg.get_body(preferencelist=("html",))
    assert "SAFE DECISION: WAIT / NO TRADE" in html_body.get_content()
