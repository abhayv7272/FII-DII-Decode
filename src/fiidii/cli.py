"""End-to-end daily runner.

Flow:
  1. Fetch (or load fixtures) participant OI (today + prev), FII/DII cash,
     option chain, index quote.
  2. Persist raw data into data/.
  3. Decode -> DecodeResult.
  4. Derive option-chain institutional levels.
  5. Build a conditional next-day plan + next-week carry context.
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
from datetime import date, timedelta
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
    cash = [{"category": "DII **", "netValue": "1350.50"},
            {"category": "FII/FPI *", "netValue": "1150.25"}]
    oc = json.loads((FIXTURES / "option_chain_nifty.json").read_text())
    return today, prev, cash, oc


def _quote_number(quote: dict, *keys: str):
    for key in keys:
        value = quote.get(key)
        try:
            return float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            continue
    return None


def _persist_index_ohlc(quote: dict, symbol: str, report_date: str) -> None:
    """Append the live session's index bar for eventual forward testing."""
    close = _quote_number(quote, "last", "lastPrice", "close")
    if close is None:
        return
    row = pd.DataFrame([{
        "date": report_date,
        "symbol": symbol.upper(),
        "open": _quote_number(quote, "open"),
        "high": _quote_number(quote, "high"),
        "low": _quote_number(quote, "low"),
        "close": close,
        "previous_close": _quote_number(quote, "previousClose", "previous_close"),
    }])
    store.append_df(row, "index_ohlc", dedup_on=["date", "symbol"])


def _history_for_method(history: pd.DataFrame, method_version: str,
                        report_date: str) -> pd.DataFrame:
    """Keep only earlier observations produced by the active decoder version."""
    if history.empty:
        return history
    if "method_version" in history:
        history = history[history["method_version"] == method_version]
    elif method_version == "v2":
        return pd.DataFrame()
    if not history.empty and "date" in history:
        dates = pd.to_datetime(history["date"], errors="coerce")
        history = history[dates < pd.Timestamp(report_date)]
    return history


def run(args) -> int:
    today_date = date.today()
    symbol = args.symbol.upper()

    quote = None
    if args.demo:
        oi_today, oi_prev, cash, oc = _load_demo()
        report_date = args.date or today_date.isoformat()
    else:
        client = NseClient()
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
        # Cash/option-chain/quote endpoints expose the current session only. If
        # participant OI fell back to an older date, omitting them is safer than
        # contaminating that date with a future snapshot.
        if d_today == today_date:
            cash = fetch.fetch_fii_dii_cash(client)
            oc = fetch.fetch_option_chain(client, symbol)
            quote = fetch.fetch_index_quote(client, symbol)
        else:
            cash, oc, quote = None, None, None
        report_date = d_today.isoformat()
        # Persist point-in-time inputs. index_ohlc.csv plus dated option-chain
        # snapshots make future forward tests reproducible without refetching.
        store.append_df(oi_today, "participant_oi", dedup_on=["date", "ClientType"])
        if oi_prev is not None:
            store.append_df(oi_prev, "participant_oi", dedup_on=["date", "ClientType"])
        if oc:
            store.save_option_chain(oc, symbol, d_today)
        # Do not stamp a current quote onto an older fallback OI date. Scheduled
        # weekday runs normally satisfy this; weekend/manual fallback runs skip it.
        if quote and d_today == today_date:
            _persist_index_ohlc(quote, symbol, report_date)

    # --- Levels first (feed into decode metrics) ---
    levels = derive_levels(oc) if oc else {"levels": [], "max_pain": None,
                                           "pcr": None, "pcr_signal": ""}

    # --- Decode ---
    result = decode(oi_today, oi_prev, cash=cash, option_levels=levels,
                    date_str=report_date)
    result.metrics.update({k: levels.get(k) for k in ("max_pain", "pcr", "spot")})

    # --- History + predictions ---
    # Never blend frozen-v1 positional scores into v2 carry context after an
    # upgrade. Legacy history has no method_version column and is deliberately
    # ignored until enough same-version observations accumulate.
    hist = _history_for_method(
        store.load_df("decoded"), result.method_version, report_date
    )
    predictions = build_predictions(result, levels, hist)

    # --- Persist decoded signal history (for positional momentum & carry trend) ---
    row = pd.DataFrame([{
        "date": report_date,
        "method_version": result.method_version,
        "bias": result.bias, "composite": result.composite,
        "confidence": result.confidence,
        "actionability": result.actionability,
        "setup_strength": result.setup_strength,
        "positional_bias": result.positional_bias,
        "positional_composite": result.positional_composite,
        "positional_confidence": result.positional_confidence,
        "fii_index_fut_net": result.metrics.get("fii_index_fut_net"),
        "pro_index_fut_net": result.metrics.get("pro_index_fut_net"),
        "client_index_fut_net": result.metrics.get("client_index_fut_net"),
        "smart_money_conflict": result.smart_money_conflict,
    }])
    store.append_df(row, "decoded", dedup_on=["date"])

    # --- Render ---
    rd = result.to_dict()
    html = render_html(rd, predictions, levels, report_date, symbol, demo=args.demo)
    md = render_markdown(rd, predictions, levels, report_date, symbol, demo=args.demo)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / f"report_{report_date}.html").write_text(html)
    (REPORTS_DIR / f"report_{report_date}.md").write_text(md)
    (REPORTS_DIR / "latest.html").write_text(html)
    (REPORTS_DIR / "latest.md").write_text(md)
    store.save_json({
        "run_mode": "demo_fixture" if args.demo else "live",
        "decode": rd,
        "predictions": predictions,
        "levels": {k: v for k, v in levels.items() if k != "strike_frame"},
    }, f"decoded_full_{report_date}")

    print(f"Report generated for {report_date}: next-day OI lean {result.bias} "
          f"(composite {result.composite:+.2f}, setup strength {result.confidence:.0f}/100) | "
          f"positional context {result.positional_bias} "
          f"({result.positional_composite:+.2f})")
    print(f"  Next-day: {predictions['next_day']['direction']} | "
          f"Next-week: {predictions['next_week']['direction']}"
          + ("  [SMART-MONEY CONFLICT]" if result.smart_money_conflict else ""))

    # --- Email ---
    if not args.no_email:
        subject = (f"📊 FII/DII Decode {report_date} — {result.bias} | "
                   f"Next-day {predictions['next_day']['direction']} | "
                   f"Week {predictions['next_week']['direction']}")
        send_report(subject, html,
                    attachments=[(f"report_{report_date}.md", md.encode("utf-8"))],
                    text_body=md)
    return 0


def run_backtest_command(args) -> int:
    """Load historical inputs, run a point-in-time replay, and write artifacts."""
    from .backtest import (
        BacktestConfig,
        load_ohlc,
        load_option_chains,
        load_participant_oi,
        run_backtest,
        write_backtest_outputs,
    )

    try:
        participant_oi = load_participant_oi(args.participant_oi)
        ohlc = load_ohlc(args.ohlc, symbol=args.symbol)
        option_chains = (
            load_option_chains(args.option_chains, symbol=args.symbol)
            if args.option_chains else {}
        )
        config = BacktestConfig(
            symbol=args.symbol.upper(),
            flat_threshold_pct=args.flat_threshold_pct,
            level_touch_tolerance_pct=args.level_touch_tolerance_pct,
            from_date=args.from_date,
            to_date=args.to_date,
            decoder_version=args.decoder_version,
        )
        result = run_backtest(participant_oi, ohlc, option_chains, config)
        paths = write_backtest_outputs(result, args.output_dir)
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"ERROR: backtest failed: {exc}", file=sys.stderr)
        return 2

    metrics = result.metrics
    print(f"Backtest complete: {metrics.get('signals_evaluated', 0)} evaluable signals; "
          f"{len(result.skipped)} skipped.")
    if metrics.get("status") == "ok":
        exact = metrics.get("exact_3_class_accuracy_pct")
        directional = metrics.get("directional_hit_rate_pct")
        exact_text = f"{exact:.2f}%" if exact is not None else "n/a"
        directional_text = f"{directional:.2f}%" if directional is not None else "n/a"
        print(f"  Exact 3-class accuracy: {exact_text}")
        print(f"  Directional hit rate:   {directional_text}")
    else:
        print("  No accuracy reported because no signals were evaluable.")
    print(f"  Report: {paths['report']}")
    print(f"  Per-date CSV: {paths['predictions']}")
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

    b = sub.add_parser("backtest", help="replay historical OI and score next-session predictions")
    b.add_argument(
        "--participant-oi", required=True, metavar="PATH",
        help="consolidated CSV, directory of fao_participant_oi_DDMMYYYY.csv, or ZIP",
    )
    b.add_argument(
        "--ohlc", required=True, metavar="CSV",
        help="daily OHLC CSV, raw ind_close_all CSV directory, or ZIP",
    )
    b.add_argument(
        "--option-chains", "--option-chain-dir", dest="option_chains", metavar="PATH",
        help="optional directory or ZIP of dated option-chain JSON snapshots",
    )
    b.add_argument("--symbol", default="NIFTY", help="index symbol (default: NIFTY)")
    b.add_argument(
        "--decoder-version", choices=("v1", "v2"), default="v2",
        help="decoder rule set to replay (default: v2; v1 is frozen for comparison)",
    )
    b.add_argument(
        "--flat-threshold-pct", type=float, default=0.15, metavar="PCT",
        help="absolute close-to-close move labelled FLAT (default: 0.15)",
    )
    b.add_argument(
        "--level-touch-tolerance-pct", type=float, default=0.05, metavar="PCT",
        help="daily range tolerance around an option level (default: 0.05)",
    )
    b.add_argument("--from-date", help="first signal date, inclusive (YYYY-MM-DD)")
    b.add_argument("--to-date", help="last signal date, inclusive (YYYY-MM-DD)")
    b.add_argument("--output-dir", default="reports/backtest", metavar="DIR")
    b.set_defaults(func=run_backtest_command)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
