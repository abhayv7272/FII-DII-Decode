from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_TO = "abhayv7272@gmail.com"


def latest_report() -> Path:
    preferred = PROJECT / "reports" / "daily" / "LATEST_EMAIL_REPORT.md"
    if preferred.exists():
        return preferred
    reports = sorted((PROJECT / "reports" / "daily").glob("*_professional_report.md"), key=lambda p: p.stat().st_mtime)
    if not reports:
        raise FileNotFoundError("No professional report found")
    return reports[-1]


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
    report_json = report.with_suffix(".json")
    if report.name == "LATEST_EMAIL_REPORT.md":
        candidates = sorted((PROJECT / "reports" / "daily").glob("*_professional_report.json"), key=lambda p: p.stat().st_mtime)
        report_json = candidates[-1] if candidates else report_json

    decision = "MARKET REPORT"
    session = "unknown-session"
    if "PIPELINE FAILURE" in body:
        decision = "PIPELINE FAILURE"
    elif report_json.exists():
        try:
            payload = json.loads(report_json.read_text(encoding="utf-8"))
            decision = payload.get("decision", decision)
            session = payload.get("session_date", session)
        except (json.JSONDecodeError, OSError):
            pass

    msg = EmailMessage()
    msg["Subject"] = f"NIFTY 9 PM Report | {session} | {decision}"
    msg["From"] = sender
    msg["To"] = args.to
    msg.set_content(body)
    msg.add_attachment(body.encode("utf-8"), maintype="text", subtype="markdown", filename=report.name)

    attachments = [report_json, PROJECT / "data" / "hub" / "latest_manifest.json", PROJECT / "reports" / "ultra_hard_audit.md"]
    for path in attachments:
        if path.exists() and path != report:
            subtype = "json" if path.suffix == ".json" else "markdown" if path.suffix == ".md" else "plain"
            msg.add_attachment(path.read_bytes(), maintype="application" if subtype == "json" else "text", subtype=subtype, filename=path.name)

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
