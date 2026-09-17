"""End-to-end daily runner.

Flow:
  1. Fetch (or load fixtures) participant OI (today + prev), FII/DII cash,
     option chain, index quote.
  2. Persist raw data into data/.
  3. Decode -> DecodeResult.
  4. Derive option-chain institutional levels.
  5. Build next-day + next-week predictions (with rolling history).
  6. Render HTML + Markdown, save to reports/.
  7. Email the report.

Usage:
  python -m fiidii.cli run                 # live NSE fetch (works on GitHub runners)
  python -m fiidii.cli run --demo          # use tests/fixtures (works anywhere)
  python -m fiidii.cli run --no-email      # skip email
  python -m fiidii.cli run --symbol NIFTY
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from . import fetch, store
from .nse import NseClient
from .decode import decode
from .levels import derive_levels
from .predict import build_predictions
from .report import render_html, render_markdown
from .email_send import send_report

REPORTS_DIR = Path("reports")
FIXTURES = Path("tests/fixtures")


def _prev_trading_day(d: date) -> date:
    p = d - timedelta(days=1)
    while p.weekday() >= 5:  # Sat/Sun
        p -= timedelta(days=1)
    return p


def _load_demo():
    from .fetch import _parse_participant_csv
    today = _parse_participant_csv((FIXTURES / "fao_participant_oi_sample.csv").read_text())
    prev = _parse_participant_csv((FIXTURES / "fao_participant_oi_prev.csv").read_text())
    cash = [{"category": "DII **", "netValue": "1250.50"},
            {"category": "FII/FPI *", "netValue": "-2100.75"}]
    oc = json.loads((FIXTURES / "option_chain_nifty.json").read_text())
    return today, prev, cash, oc


def run(args) -> int:
    today_date = date.today()
    symbol = args.symbol.upper()

    if args.demo:
        oi_today, oi_prev, cash, oc = _load_demo()
        report_date = args.date or today_date.isoformat()
    else:
        client = NseClient()
        d = _prev_trading_day(today_date) if today_date.weekday() < 5 else _prev_trading_day(today_date)
        # Participant OI is published for the *current* completed trading session.
        d_today = today_date if today_date.weekday() < 5 else _prev_trading_day(today_date)
        oi_today = fetch.fetch_participant_oi(client, d_today)
        # Fall back a day if today's file isn't out yet.
        tries = 0
        while oi_today is None and tries < 5:
            d_today = _prev_trading_day(d_today)
            oi_today = fetch.fetch_participant_oi(client, d_today)
            tries += 1
        if oi_today is None:
            print("ERROR: could not fetch participant OI.", file=sys.stderr)
            return 2
        oi_prev = fetch.fetch_participant_oi(client, _prev_trading_day(d_today))
        cash = fetch.fetch_fii_dii_cash(client)
        oc = fetch.fetch_option_chain(client, symbol)
        report_date = d_today.isoformat()
        # persist raw
        store.append_df(oi_today, "participant_oi", dedup_on=["date", "ClientType"])
        if oi_prev is not None:
            store.append_df(oi_prev, "participant_oi", dedup_on=["date", "ClientType"])
        if oc:
            store.save_option_chain(oc, symbol, d_today)

    # --- Decode ---
    result = decode(oi_today, oi_prev, cash=cash, date_str=report_date)

    # --- Levels ---
    levels = derive_levels(oc) if oc else {"levels": [], "max_pain": None, "pcr": None}
    result.metrics.update({k: levels.get(k) for k in ("max_pain", "pcr", "spot")})

    # --- History + predictions ---
    hist = store.load_df("decoded")
    predictions = build_predictions(result, levels, hist)

    # --- Persist decoded signal history ---
    row = pd.DataFrame([{"date": report_date, "bias": result.bias,
                         "composite": result.composite, "confidence": result.confidence}])
    store.append_df(row, "decoded", dedup_on=["date"])

    # --- Render ---
    rd = result.to_dict()
    html = render_html(rd, predictions, levels, report_date, symbol)
    md = render_markdown(rd, predictions, levels, report_date, symbol)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / f"report_{report_date}.html").write_text(html)
    (REPORTS_DIR / f"report_{report_date}.md").write_text(md)
    (REPORTS_DIR / "latest.html").write_text(html)
    (REPORTS_DIR / "latest.md").write_text(md)
    store.save_json({"decode": rd, "predictions": predictions, "levels":
                     {k: v for k, v in levels.items() if k != "strike_frame"}},
                    f"decoded_full_{report_date}")

    print(f"Report generated for {report_date}: {result.bias} "
          f"(composite {result.composite:+.2f}, conf {result.confidence:.0f}%)")
    print(f"  Next-day: {predictions['next_day']['direction']} | "
          f"Next-week: {predictions['next_week']['direction']}")

    # --- Email ---
    if not args.no_email:
        subject = (f"📊 FII/DII Decode {report_date} — {result.bias} | "
                   f"Next-day {predictions['next_day']['direction']}")
        send_report(subject, html,
                    attachments=[(f"report_{report_date}.md", md.encode("utf-8"))],
                    text_body=md)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="fiidii", description="FII/DII/Pro/Client decode + daily report")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="fetch, decode, predict, report, email")
    r.add_argument("--demo", action="store_true", help="use bundled fixtures (no network)")
    r.add_argument("--no-email", action="store_true", help="do not send email")
    r.add_argument("--symbol", default="NIFTY")
    r.add_argument("--date", default=None, help="override report date (demo mode)")
    r.set_defaults(func=run)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
