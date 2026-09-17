"""Email delivery must degrade gracefully when SMTP secrets are absent.

Regression tests for a real workflow failure: GitHub Actions renders
``${{ secrets.X }}`` as an EMPTY STRING when the secret is not configured,
so the runner sets ``SMTP_PORT=""``. The old ``int(os.environ.get("SMTP_PORT",
"465"))`` then raised ``ValueError`` AFTER the report had been generated,
failing the whole daily job with exit code 1.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fiidii.email_send import send_report

ALL_SMTP_ENV = (
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASS",
    "MAIL_FROM",
    "MAIL_TO",
)


def _gmail_actions_env(monkeypatch, **overrides):
    """Env exactly as GitHub Actions provides it when NO secrets are set."""
    for name in ALL_SMTP_ENV:
        monkeypatch.setenv(name, "")
    for name, value in overrides.items():
        monkeypatch.setenv(name, value)


def test_blank_secrets_env_skips_send_without_raising(monkeypatch, capsys):
    """Unset secrets (empty strings on a runner) must skip, not crash."""
    _gmail_actions_env(monkeypatch)
    assert send_report("subject", "<html><body>t</body></html>") is False
    out = capsys.readouterr().out
    assert "skipping send" in out


def test_blank_or_non_numeric_port_never_raises_valueerror(monkeypatch):
    """A malformed SMTP_PORT must fall back, not exit the daily job."""
    for bad in ("", "   ", "abc", "465ssl", "port 465"):
        _gmail_actions_env(
            monkeypatch,
            SMTP_PORT=bad,
            SMTP_HOST="127.0.0.1",
            SMTP_USER="user@example.com",
            SMTP_PASS="apppassword",
        )
        # 127.0.0.1 refuses SMTP connections immediately: the guarded connect
        # path returns False instead of raising, and never ValueError.
        assert send_report("subject", "<html><body>t</body></html>") is False


def test_unsecrets_env_vars_still_default(monkeypatch):
    """Fully unset env (local runs) keeps the documented defaults."""
    for name in ALL_SMTP_ENV:
        monkeypatch.delenv(name, raising=False)
    assert send_report("subject", "<html><body>t</body></html>") is False


def test_valid_port_with_unreachable_host_reports_failure(monkeypatch):
    """A syntactically valid setup that cannot connect returns False."""
    _gmail_actions_env(
        monkeypatch,
        SMTP_HOST="127.0.0.1",
        SMTP_PORT="1",
        SMTP_USER="user@example.com",
        SMTP_PASS="apppassword",
        MAIL_TO="someone@example.com",
    )
    assert send_report("subject 📊", "<html><body>t</body></html>") is False
