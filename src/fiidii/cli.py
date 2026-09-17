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
  python -m fiidii.cli run                 # validated live fetch; exits if OI is incomplete
  python -m fiidii.cli run --demo          # use tests/fixtures (works anywhere)
  python -m fiidii.cli run --no-email      # skip email
  python -m fiidii.cli run --symbol NIFTY
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from . import fetch, store
from .decode import decode
from .email_send import send_report
from .levels import derive_levels
from .nse import NseClient
from .predict import build_predictions
from .report import render_html, render_markdown

REPORTS_DIR = Path("reports")
FIXTURES = Path("tests/fixtures")


def _prev_trading_day(d: date) -> date:
    p = d - timedelta(days=1)
    while p.weekday() >= 5:  # Sat/Sun
        p -= timedelta(days=1)
    return p


def _load_demo():
    from .fetch import _parse_participant_csv

    today = _parse_participant_csv(
        (FIXTURES / "fao_participant_oi_sample.csv").read_text()
    )
    prev = _parse_participant_csv(
        (FIXTURES / "fao_participant_oi_prev.csv").read_text()
    )
    cash = [
        {"category": "DII **", "netValue": "1350.50"},
        {"category": "FII/FPI *", "netValue": "1150.25"},
    ]
    oc = json.loads((FIXTURES / "option_chain_nifty.json").read_text())
    return today, prev, cash, oc


def _load_institutional_levels(path: str | None):
    if not path:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("levels")
    if not isinstance(payload, list):
        raise TypeError(
            "institutional-level file must be a JSON list or {'levels': [...]}"
        )
    return payload


def _quote_number(quote: dict, *keys: str):
    for key in keys:
        value = quote.get(key)
        try:
            return float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            continue
    return None


def _persist_index_ohlc(quote: dict, symbol: str, report_date: str) -> bool:
    """Append a complete live-session index bar for eventual forward testing."""
    values = {
        "open": _quote_number(quote, "open"),
        "high": _quote_number(quote, "high"),
        "low": _quote_number(quote, "low"),
        "close": _quote_number(quote, "last", "lastPrice", "close"),
    }
    if any(value is None for value in values.values()):
        return False
    row = pd.DataFrame(
        [
            {
                "date": report_date,
                "symbol": symbol.upper(),
                **values,
                "previous_close": _quote_number(
                    quote, "previousClose", "previous_close"
                ),
            }
        ]
    )
    store.append_df(row, "index_ohlc", dedup_on=["date", "symbol"])
    return True


def _source_unavailable(note: str) -> dict:
    return {
        "status": "unavailable",
        "source": None,
        "url": None,
        "as_of": None,
        "fallback": False,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "warning": note,
    }


def _institutional_source_status(
    supplied_levels, path: str | None, report_date: str
) -> dict:
    return {
        "status": "available" if supplied_levels else "not_provided",
        "source": "user-supplied JSON" if supplied_levels else None,
        "url": path,
        "as_of": report_date if supplied_levels else None,
        "fallback": False,
        "warning": (
            "Exact reference provenance is user supplied; the repository cannot "
            "derive the proprietary formula."
            if supplied_levels
            else "Optional exact references were not supplied; automatic levels remain "
            "option-chain proxies."
        ),
    }


def _participant_frames_match(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    """Confirm two providers expose the same current participant matrix."""
    try:
        columns = list(fetch.POSITION_COLUMNS)
        left_values = (
            left[left["ClientType"].str.upper().isin({"CLIENT", "DII", "FII", "PRO"})]
            .assign(ClientType=lambda frame: frame["ClientType"].str.upper())
            .set_index("ClientType")[columns]
            .sort_index()
            .astype(float)
        )
        right_values = (
            right[right["ClientType"].str.upper().isin({"CLIENT", "DII", "FII", "PRO"})]
            .assign(ClientType=lambda frame: frame["ClientType"].str.upper())
            .set_index("ClientType")[columns]
            .sort_index()
            .astype(float)
        )
        return left_values.shape == right_values.shape and bool(
            ((left_values - right_values).abs() <= 1.0).all().all()
        )
    except (KeyError, TypeError, ValueError):
        return False


def _previous_oi_from_archives(
    client: NseClient,
    current_date: date,
    metadata: dict,
) -> tuple[pd.DataFrame | None, date | None]:
    candidate = _prev_trading_day(current_date)
    for _ in range(7):
        candidate_meta: dict = {}
        frame = fetch.fetch_participant_oi(client, candidate, candidate_meta)
        if frame is not None:
            metadata.update(candidate_meta)
            return frame, candidate
        candidate = _prev_trading_day(candidate)
    metadata.update(
        _source_unavailable(
            f"No complete prior participant-OI session found before {current_date}."
        )
    )
    return None, None


def _data_health(
    report_date: str,
    inputs: dict,
    demo: bool = False,
    run_date: str | None = None,
) -> dict:
    required_direction = ("participant_oi_current", "participant_oi_previous")
    direction_ready = all(
        inputs.get(name, {}).get("status") == "available" for name in required_direction
    )
    levels_ready = inputs.get("option_chain", {}).get("status") == "available"
    cash_ready = inputs.get("cash", {}).get("status") == "available"
    fallbacks = [
        name
        for name, item in inputs.items()
        if item.get("status") == "available" and item.get("fallback")
    ]
    unavailable = [
        name for name, item in inputs.items() if item.get("status") == "unavailable"
    ]
    if demo:
        overall = "DEMO_FIXTURE"
    elif not direction_ready:
        overall = "BLOCKED_MISSING_DIRECTION_INPUT"
    elif not levels_ready:
        overall = "DEGRADED_MISSING_LEVEL_INPUT"
    elif not cash_ready:
        overall = "DEGRADED_MISSING_CASH_INPUT"
    elif fallbacks:
        overall = "DEGRADED_FALLBACK_SOURCE"
    elif unavailable:
        overall = "READY_WITH_AUDIT_GAPS"
    else:
        overall = "READY"
    return {
        "overall": overall,
        "run_date": run_date or report_date,
        "report_date": report_date,
        "direction_inputs_ready": direction_ready,
        "level_inputs_ready": levels_ready,
        "fallback_inputs": fallbacks,
        "unavailable_inputs": unavailable,
        "inputs": inputs,
        "policy": (
            "A next-day OI lean requires complete current and previous participant OI. "
            "Actionable level branches additionally require a same-date option chain. "
            "Cash can alter setup strength but not the locked OI class; OHLC is an audit input."
        ),
    }


def _fetch_session_context(
    client: NseClient, symbol: str, session_date: date
) -> tuple[list[dict] | None, dict | None, dict | None, pd.DataFrame | None, dict]:
    """Collect non-OI inputs independently so one outage cannot hide the others."""
    cash_meta: dict = {}
    option_meta: dict = {}
    quote_meta: dict = {}
    volume_meta: dict = {}
    cash = fetch.fetch_fii_dii_cash(client, session_date, cash_meta)
    option_chain = fetch.fetch_option_chain(client, symbol, session_date, option_meta)
    quote = fetch.fetch_index_quote(client, symbol, session_date, quote_meta)
    participant_volume = fetch.fetch_participant_vol(client, session_date, volume_meta)
    return cash, option_chain, quote, participant_volume, {
        "cash": cash_meta,
        "option_chain": option_meta,
        "index_quote": quote_meta,
        "participant_volume": volume_meta,
    }


def _persist_session_context(
    cash: list[dict] | None,
    option_chain: dict | None,
    quote: dict | None,
    participant_volume: pd.DataFrame | None,
    source_status: dict[str, dict],
    symbol: str,
    session_date: date,
) -> None:
    """Persist every independently valid context input, even if decoding is blocked."""
    if participant_volume is not None:
        store.append_df(
            participant_volume,
            "participant_vol",
            dedup_on=["date", "ClientType"],
        )
    if cash:
        cash_frame = fetch.cash_rows_to_frame(
            cash, source_status["cash"].get("source", "")
        )
        store.append_df(cash_frame, "fii_dii_cash", dedup_on=["date", "category"])
    if option_chain:
        store.save_option_chain(option_chain, symbol, session_date)
    if quote:
        _persist_index_ohlc(quote, symbol, session_date.isoformat())
    elif option_chain:
        _persist_chain_spot(option_chain, symbol, session_date.isoformat())


def _persist_chain_spot(option_chain: dict, symbol: str, report_date: str) -> bool:
    """Close-only fallback bar from the same-date option chain's underlyingValue.

    The forward-validation gate only needs the close; open/high/low are left
    blank (the replay leaves their gap/level observations unscored).
    """
    records = option_chain.get("records", {}) if isinstance(option_chain, dict) else {}
    spot = _quote_number(records, "underlyingValue")
    if spot is None:
        return False
    row = pd.DataFrame(
        [
            {
                "date": report_date,
                "symbol": symbol.upper(),
                "open": None,
                "high": None,
                "low": None,
                "close": spot,
                "previous_close": None,
            }
        ]
    )
    store.append_df(row, "index_ohlc", dedup_on=["date", "symbol"])
    return True


def _history_for_method(
    history: pd.DataFrame, method_version: str, report_date: str
) -> pd.DataFrame:
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
    today_date = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    symbol = args.symbol.upper()
    supplied_levels = _load_institutional_levels(
        getattr(args, "institutional_levels", None)
    )
    source_status: dict[str, dict] = {}
    quote = None

    if args.demo:
        oi_today, oi_prev, cash, oc = _load_demo()
        report_date = args.date or today_date.isoformat()
        fixture_status = {
            "status": "available",
            "source": "bundled synthetic demo fixture",
            "url": None,
            "as_of": report_date,
            "fallback": False,
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
            "warning": "Synthetic/approximate values; not live market data.",
        }
        for name in (
            "participant_oi_current",
            "participant_oi_previous",
            "cash",
            "option_chain",
        ):
            source_status[name] = fixture_status.copy()
        source_status["index_quote"] = _source_unavailable(
            "Demo fixture has option-chain spot but no independent index OHLC fetch."
        )
        source_status["participant_volume"] = {
            "status": "not_used",
            "source": None,
            "as_of": report_date,
            "fallback": False,
            "warning": "Participant volume is not an input to the locked v2 score.",
        }
    else:
        client = NseClient(timeout=12, max_retries=2, backoff=1.5)
        target_date = (
            today_date if today_date.weekday() < 5 else _prev_trading_day(today_date)
        )
        current_meta: dict = {}
        oi_today = fetch.fetch_participant_oi(client, target_date, current_meta)
        d_today = target_date
        fallback_pair = None

        # If NSE and its date-exact GitHub mirror both fail, use a complete
        # third-party rendering only after date, completeness and balance checks.
        if oi_today is None:
            stocklyzer_meta: dict = {}
            fallback_pair = fetch.fetch_participant_oi_rendered(
                target_date, stocklyzer_meta
            )
            if fallback_pair is not None:
                oi_today, oi_prev, d_today = fallback_pair
                current_meta = stocklyzer_meta
            else:
                current_meta = _source_unavailable(
                    f"{current_meta.get('warning', 'NSE/archive sources unavailable')} "
                    f"Rendered fallbacks: {stocklyzer_meta.get('warning', 'unavailable')}"
                )
                # Last chance for exchange holidays: seek an older date-exact
                # official/mirror archive rather than stamping current data backward.
                candidate = _prev_trading_day(target_date)
                for _ in range(7):
                    candidate_meta: dict = {}
                    candidate_frame = fetch.fetch_participant_oi(
                        client, candidate, candidate_meta
                    )
                    if candidate_frame is not None:
                        oi_today = candidate_frame
                        d_today = candidate
                        current_meta = candidate_meta
                        break
                    candidate = _prev_trading_day(candidate)
        source_status["participant_oi_current"] = current_meta

        cash = oc = quote = participant_volume = None
        if d_today == target_date:
            cash, oc, quote, participant_volume, context_status = (
                _fetch_session_context(client, symbol, target_date)
            )
            source_status.update(context_status)
            _persist_session_context(
                cash,
                oc,
                quote,
                participant_volume,
                source_status,
                symbol,
                target_date,
            )
        else:
            note = (
                f"Latest validated participant OI is {d_today}, not target session "
                f"{target_date}; current-only endpoint was deliberately not mixed in."
            )
            for name in ("cash", "option_chain", "index_quote", "participant_volume"):
                source_status[name] = _source_unavailable(note)

        if oi_today is None:
            source_status["participant_oi_previous"] = _source_unavailable(
                "Current participant OI is unavailable, so no previous pair was used."
            )
            source_status["institutional_references"] = _institutional_source_status(
                supplied_levels,
                getattr(args, "institutional_levels", None),
                target_date.isoformat(),
            )
            status = _data_health(
                today_date.isoformat(),
                source_status,
                demo=False,
                run_date=today_date.isoformat(),
            )
            store.save_json(status, f"fetch_status_{today_date.isoformat()}")
            print(
                "ERROR: no complete, validated participant-OI matrix is available; "
                "prediction was blocked.",
                file=sys.stderr,
            )
            return 2

        previous_date = None
        previous_meta: dict = {}
        if fallback_pair is not None:
            previous_meta = current_meta.copy()
            previous_meta["source"] = (
                f"{current_meta.get('source')} — previous session from displayed deltas"
            )
            previous_meta["as_of"] = "immediately preceding trading session"
            previous_meta["warning"] = (
                f"{current_meta.get('warning', '')} Previous values equal current "
                "minus provider-displayed daily change; no holiday-sensitive date was guessed."
            ).strip()
        else:
            oi_prev, previous_date = _previous_oi_from_archives(
                client, d_today, previous_meta
            )
            if oi_prev is None:
                stocklyzer_meta = {}
                stocklyzer_pair = fetch.fetch_participant_oi_rendered(
                    d_today, stocklyzer_meta
                )
                if (
                    stocklyzer_pair is not None
                    and stocklyzer_pair[2] == d_today
                    and _participant_frames_match(oi_today, stocklyzer_pair[0])
                ):
                    oi_prev = stocklyzer_pair[1]
                    previous_meta = stocklyzer_meta.copy()
                    previous_meta["source"] = (
                        f"{stocklyzer_meta.get('source')} — previous session from "
                        "displayed deltas"
                    )
                    previous_meta["as_of"] = "immediately preceding trading session"
                else:
                    oi_prev = None
        source_status["participant_oi_previous"] = previous_meta

        if oi_prev is None:
            source_status["institutional_references"] = _institutional_source_status(
                supplied_levels,
                getattr(args, "institutional_levels", None),
                d_today.isoformat(),
            )
            status = _data_health(
                d_today.isoformat(),
                source_status,
                demo=False,
                run_date=today_date.isoformat(),
            )
            store.save_json(status, f"fetch_status_{today_date.isoformat()}")
            print(
                "ERROR: current participant OI exists but no complete previous-session "
                "matrix is available; prediction was blocked instead of forcing neutral.",
                file=sys.stderr,
            )
            return 2

        report_date = d_today.isoformat()
        source_status["institutional_references"] = _institutional_source_status(
            supplied_levels,
            getattr(args, "institutional_levels", None),
            report_date,
        )

        # Context inputs were persisted independently above. Persist the complete
        # OI pair only after both matrices have passed the directional gate.
        store.append_df(oi_today, "participant_oi", dedup_on=["date", "ClientType"])
        if previous_date is not None:
            store.append_df(oi_prev, "participant_oi", dedup_on=["date", "ClientType"])

    if "institutional_references" not in source_status:
        source_status["institutional_references"] = _institutional_source_status(
            supplied_levels,
            getattr(args, "institutional_levels", None),
            report_date,
        )
    data_status = _data_health(
        report_date,
        source_status,
        demo=args.demo,
        run_date=today_date.isoformat(),
    )
    status_file_date = report_date if args.demo else today_date.isoformat()
    store.save_json(data_status, f"fetch_status_{status_file_date}")

    # --- Levels first (feed into decode metrics) ---
    levels = (
        derive_levels(oc, institutional_levels=supplied_levels)
        if oc
        else {
            "levels": [],
            "max_pain": None,
            "pcr": None,
            "pcr_signal": "",
            "level_method_warning": (
                "No dated option chain was available, so no automatic level proxy "
                "or level-by-level prediction was generated."
            ),
            "exact_institutional_formula_available": False,
        }
    )

    levels["option_chain_input_source"] = source_status.get("option_chain", {}).get(
        "source"
    )

    # --- Decode ---
    result = decode(
        oi_today, oi_prev, cash=cash, option_levels=levels, date_str=report_date
    )
    if not data_status["level_inputs_ready"] and result.actionability.startswith(
        "CONDITIONAL_"
    ):
        result.actionability = "CONTEXT_ONLY_MISSING_SAME_DATE_OPTION_CHAIN"
        result.setup_note = (
            f"{result.setup_note} Same-date option-chain data is unavailable, so no "
            "level entry is actionable."
        )
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
    row = pd.DataFrame(
        [
            {
                "date": report_date,
                "method_version": result.method_version,
                "bias": result.bias,
                "composite": result.composite,
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
            }
        ]
    )
    store.append_df(row, "decoded", dedup_on=["date"])

    # --- Render ---
    rd = result.to_dict()
    rd["data_status"] = data_status
    html = render_html(rd, predictions, levels, report_date, symbol, demo=args.demo)
    md = render_markdown(rd, predictions, levels, report_date, symbol, demo=args.demo)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / f"report_{report_date}.html").write_text(html)
    (REPORTS_DIR / f"report_{report_date}.md").write_text(md)
    (REPORTS_DIR / "latest.html").write_text(html)
    (REPORTS_DIR / "latest.md").write_text(md)
    store.save_json(
        {
            "run_mode": "demo_fixture" if args.demo else "live",
            "data_status": data_status,
            "decode": rd,
            "predictions": predictions,
            "levels": {k: v for k, v in levels.items() if k != "strike_frame"},
        },
        f"decoded_full_{report_date}",
    )

    print(
        f"Report generated for {report_date}: next-day OI lean {result.bias} "
        f"(composite {result.composite:+.2f}, setup strength {result.confidence:.0f}/100) | "
        f"positional context {result.positional_bias} "
        f"({result.positional_composite:+.2f})"
    )
    print(
        f"  Next-day: {predictions['next_day']['direction']} | "
        f"Next-week: {predictions['next_week']['direction']}"
        + ("  [SMART-MONEY CONFLICT]" if result.smart_money_conflict else "")
    )
    print(f"  Data health: {data_status['overall']}")
    for name, item in source_status.items():
        print(
            f"    {name}: {item.get('status')} | "
            f"{item.get('source') or 'no source'} | as-of {item.get('as_of') or 'n/a'}"
        )

    # --- Email ---
    if not args.no_email:
        subject = (
            f"📊 FII/DII Decode {report_date} — {result.bias} | "
            f"Next-day {predictions['next_day']['direction']} | "
            f"Week {predictions['next_week']['direction']}"
        )
        send_report(
            subject,
            html,
            attachments=[(f"report_{report_date}.md", md.encode("utf-8"))],
            text_body=md,
        )
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
            if args.option_chains
            else {}
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
    print(
        f"Backtest complete: {metrics.get('signals_evaluated', 0)} evaluable signals; "
        f"{len(result.skipped)} skipped."
    )
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
    p = argparse.ArgumentParser(
        prog="fiidii", description="FII/DII/Pro/Client decode + daily report"
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="fetch, decode, predict, report, email")
    r.add_argument(
        "--demo", action="store_true", help="use bundled fixtures (no network)"
    )
    r.add_argument("--no-email", action="store_true", help="do not send email")
    r.add_argument("--symbol", default="NIFTY")
    r.add_argument("--date", default=None, help="override report date (demo mode)")
    r.add_argument(
        "--institutional-levels",
        metavar="JSON",
        help=(
            "optional exact externally supplied institutional references; JSON list "
            "of numbers or {strike, kind, label} objects"
        ),
    )
    r.set_defaults(func=run)

    b = sub.add_parser(
        "backtest", help="replay historical OI and score next-session predictions"
    )
    b.add_argument(
        "--participant-oi",
        required=True,
        metavar="PATH",
        help="consolidated CSV, directory of fao_participant_oi_DDMMYYYY.csv, or ZIP",
    )
    b.add_argument(
        "--ohlc",
        required=True,
        metavar="CSV",
        help="daily OHLC CSV, raw ind_close_all CSV directory, or ZIP",
    )
    b.add_argument(
        "--option-chains",
        "--option-chain-dir",
        dest="option_chains",
        metavar="PATH",
        help="optional directory or ZIP of dated option-chain JSON snapshots",
    )
    b.add_argument("--symbol", default="NIFTY", help="index symbol (default: NIFTY)")
    b.add_argument(
        "--decoder-version",
        choices=("v1", "v2", "v3"),
        default="v2",
        help="decoder rule set to replay (default: v2; v1 is frozen for comparison)",
    )
    b.add_argument(
        "--flat-threshold-pct",
        type=float,
        default=0.15,
        metavar="PCT",
        help="absolute close-to-close move labelled FLAT (default: 0.15)",
    )
    b.add_argument(
        "--level-touch-tolerance-pct",
        type=float,
        default=0.05,
        metavar="PCT",
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
