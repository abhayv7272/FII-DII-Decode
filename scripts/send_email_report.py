from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from src.email_template import build_html_email  # noqa: E402

DEFAULT_TO = "abhayv7272@gmail.com"

SUBJECT_ICONS = {
    "WAIT": "\u23f8",  # double vertical bar (pause)
    "UP": "\U0001F4C8",  # chart increasing
    "DOWN": "\U0001F4C9",  # chart decreasing
    "PIPELINE FAILURE": "\U0001F6A8",  # rotating light
}


def latest_report() -> Path:
    preferred = PROJECT / "reports" / "daily" / "LATEST_EMAIL_REPORT.md"
    if preferred.exists():
        return preferred
    reports = sorted((PROJECT / "reports" / "daily").glob("*_professional_report.md"), key=lambda p: p.stat().st_mtime)
    if not reports:
        raise FileNotFoundError("No professional report found")
    return reports[-1]


def _resolve_report_json(report: Path) -> Path:
    if report.name != "LATEST_EMAIL_REPORT.md":
        return report.with_suffix(".json")
    candidates = sorted(
        (PROJECT / "reports" / "daily").glob("*_professional_report.json"),
        key=lambda p: p.stat().st_mtime,
    )
    return candidates[-1] if candidates else report.with_suffix(".json")


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _subject_icon(decision: str) -> str:
    upper = decision.upper()
    for key, icon in SUBJECT_ICONS.items():
        if key in upper:
            return icon
    return ""


def compose_message(
    body: str,
    report: Path,
    report_json: Path,
    manifest_path: Path,
    audit_path: Path,
    *,
    to: str,
    sender: str,
) -> EmailMessage:
    """Build the full email: HTML body + plain-text Markdown fallback + attachments.

    The HTML alternative is presentation only. The decision text, gates and
    probabilities come verbatim from the report payload, so WAIT / NO TRADE
    fail-closed behaviour is never altered by rendering.
    """
    payload = _load_json(report_json)
    manifest = _load_json(manifest_path)

    decision = "MARKET REPORT"
    session = "unknown-session"
    if "PIPELINE FAILURE" in body:
        decision = "PIPELINE FAILURE"
    elif payload:
        decision = payload.get("decision", decision)
        session = payload.get("session_date", session)

    icon = _subject_icon(decision)
    prefix = f"{icon} " if icon else ""

    msg = EmailMessage()
    msg["Subject"] = f"{prefix}NIFTY 9 PM Report | {session} | {decision}"
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(body)

    html_body = build_html_email(body, payload, manifest)
    msg.add_alternative(html_body, subtype="html")

    msg.add_attachment(body.encode("utf-8"), maintype="text", subtype="markdown", filename=report.name)

    attachments = [report_json, manifest_path, audit_path]
    for path in attachments:
        if path.exists() and path != report:
            subtype = "json" if path.suffix == ".json" else "markdown" if path.suffix == ".md" else "plain"
            msg.add_attachment(
                path.read_bytes(),
                maintype="application" if subtype == "json" else "text",
                subtype=subtype,
                filename=path.name,
            )
    return msg


def main() -> None:
    parser = argparse.ArgumentParser(description="Email the latest professional market report")
    parser.add_argument("--to", default=os.getenv("REPORT_EMAIL_TO", DEFAULT_TO))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    host = os.getenv("SMTP_HOST", "").strip()
    port_raw = os.getenv("SMTP_PORT", "").strip()
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip()
    missing = [
        name
        for name, value in {
            "SMTP_HOST": host,
            "SMTP_PORT": port_raw,
            "SMTP_USERNAME": username,
            "SMTP_PASSWORD": password,
            "SMTP_FROM": sender,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing required GitHub Actions SMTP secrets: {', '.join(missing)}")
    port = int(port_raw)

    report = args.report or latest_report()
    body = report.read_text(encoding="utf-8")
    report_json = _resolve_report_json(report)

    msg = compose_message(
        body,
        report,
        report_json,
        PROJECT / "data" / "hub" / "latest_manifest.json",
        PROJECT / "reports" / "ultra_hard_audit.md",
        to=args.to,
        sender=sender,
    )

    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=30) as smtp:
            smtp.login(username, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(username, password)
            smtp.send_message(msg)
    print(f"Report emailed to {args.to}: {report.name}")


if __name__ == "__main__":
    main()
