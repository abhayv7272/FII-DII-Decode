"""Send the daily report via email (SMTP).

Configured entirely through environment variables (GitHub Actions secrets):
  SMTP_HOST      e.g. smtp.gmail.com
  SMTP_PORT      e.g. 465 (SSL) or 587 (STARTTLS)
  SMTP_USER      sender login (e.g. your gmail address)
  SMTP_PASS      app password (NOT your normal password)
  MAIL_FROM      optional; defaults to SMTP_USER
  MAIL_TO        comma-separated recipients (defaults to abhayv72727@gmail.com)

For Gmail: enable 2FA, then create an "App Password" and use that as SMTP_PASS.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Optional


def send_report(subject: str, html_body: str,
                attachments: Optional[list[tuple[str, bytes]]] = None,
                text_body: Optional[str] = None) -> bool:
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    mail_from = os.environ.get("MAIL_FROM", user or "")
    mail_to = os.environ.get("MAIL_TO", "abhayv72727@gmail.com")

    if not user or not password:
        print("[email] SMTP_USER/SMTP_PASS not set; skipping send. "
              "Report was still generated on disk.")
        return False

    recipients = [r.strip() for r in mail_to.split(",") if r.strip()]

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = ", ".join(recipients)

    alt = MIMEMultipart("alternative")
    if text_body:
        alt.attach(MIMEText(text_body, "plain", "utf-8"))
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    for fname, content in (attachments or []):
        part = MIMEApplication(content, Name=fname)
        part["Content-Disposition"] = f'attachment; filename="{fname}"'
        msg.attach(part)

    context = ssl.create_default_context()
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as server:
                server.login(user, password)
                server.sendmail(mail_from, recipients, msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=30) as server:
                server.starttls(context=context)
                server.login(user, password)
                server.sendmail(mail_from, recipients, msg.as_string())
        print(f"[email] Sent '{subject}' to {recipients}")
        return True
    except Exception as exc:  # pragma: no cover - network
        print(f"[email] FAILED to send: {exc}")
        return False
