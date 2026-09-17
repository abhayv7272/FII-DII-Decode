"""Data-source validation and fallback parser tests (network-free)."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fiidii import cli, fetch
from fiidii.cli import _data_health

FIX = Path(__file__).parent / "fixtures"


def _balanced(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame[frame["ClientType"] != "TOTAL"].copy()
    pro_index = frame.index[frame["ClientType"] == "Pro"][0]
    for long_column, short_column in fetch.BALANCE_PAIRS:
        difference = float(frame[long_column].sum() - frame[short_column].sum())
        if difference > 0:
            frame.loc[pro_index, short_column] += difference
        elif difference < 0:
            frame.loc[pro_index, long_column] -= difference
    frame["Total Long Contracts"] = frame[list(fetch.LONG_COLUMNS)].sum(axis=1)
    frame["Total Short Contracts"] = frame[list(fetch.SHORT_COLUMNS)].sum(axis=1)
    return fetch._with_total_row(frame)


def _sample_pair() -> tuple[pd.DataFrame, pd.DataFrame]:
    current = fetch._parse_participant_csv(
        (FIX / "fao_participant_oi_sample.csv").read_text()
    )
    previous = fetch._parse_participant_csv(
        (FIX / "fao_participant_oi_prev.csv").read_text()
    )
    return _balanced(current), _balanced(previous)


def test_participant_validator_rejects_partial_and_unbalanced_frames():
    current, _ = _sample_pair()
    assert fetch.validate_participant_oi(current) == (True, "ok")

    partial = current.drop(columns=["Option Index Put Short"])
    valid, reason = fetch.validate_participant_oi(partial)
    assert not valid
    assert "missing columns" in reason

    unbalanced = current.copy()
    unbalanced.loc[unbalanced["ClientType"] == "FII", "Future Index Long"] += 100
    unbalanced.loc[unbalanced["ClientType"] == "FII", "Total Long Contracts"] += 100
    unbalanced.loc[unbalanced["ClientType"] == "TOTAL", "Future Index Long"] += 100
    unbalanced.loc[unbalanced["ClientType"] == "TOTAL", "Total Long Contracts"] += 100
    valid, reason = fetch.validate_participant_oi(unbalanced)
    assert not valid
    assert "unbalanced" in reason


def _participant_table_html(
    current: pd.DataFrame,
    previous: pd.DataFrame,
    columns: list[str],
) -> str:
    headers = "".join(
        f"<th>{name}</th>"
        for name in (
            "Future Long",
            "Future Short",
            "Call Long",
            "Call Short",
            "Put Long",
            "Put Short",
        )
    )
    rows = []
    for participant in fetch.PARTICIPANTS:
        current_row = current[current["ClientType"] == participant].iloc[0]
        previous_row = previous[previous["ClientType"] == participant].iloc[0]
        cells = []
        for column in columns:
            value = int(current_row[column])
            change = int(current_row[column] - previous_row[column])
            cells.append(f"<td>{value:,} {change:+,}</td>")
        rows.append(f"<tr><td>{participant}</td>{''.join(cells)}</tr>")
    return f"<table><tr><th>Participant</th>{headers}</tr>{''.join(rows)}</table>"


def test_stocklyzer_fallback_reconstructs_complete_previous_matrix(monkeypatch):
    current, previous = _sample_pair()
    index_columns = [
        "Future Index Long",
        "Future Index Short",
        "Option Index Call Long",
        "Option Index Call Short",
        "Option Index Put Long",
        "Option Index Put Short",
    ]
    stock_columns = [
        "Future Stock Long",
        "Future Stock Short",
        "Option Stock Call Long",
        "Option Stock Call Short",
        "Option Stock Put Long",
        "Option Stock Put Short",
    ]
    html = (
        "<html><body><p>* As on 2026-09-17 20:42:39</p>"
        + _participant_table_html(current, previous, index_columns)
        + _participant_table_html(current, previous, stock_columns)
        + "</body></html>"
    )
    monkeypatch.setattr(fetch, "_third_party_get", lambda *args, **kwargs: html)
    metadata: dict = {}
    result = fetch.fetch_participant_oi_stocklyzer(date(2026, 9, 17), metadata)

    assert result is not None
    reconstructed_current, reconstructed_previous, as_of = result
    assert as_of == date(2026, 9, 17)
    assert metadata["fallback"]
    assert metadata["source"] == "Stocklyzer EOD participant table"
    assert fetch.validate_participant_oi(reconstructed_current) == (True, "ok")
    assert fetch.validate_participant_oi(reconstructed_previous) == (True, "ok")
    fii_previous = reconstructed_previous[
        reconstructed_previous["ClientType"] == "FII"
    ].iloc[0]
    expected = previous[previous["ClientType"] == "FII"].iloc[0]
    assert fii_previous["Option Index Put Short"] == expected["Option Index Put Short"]


def test_niftytrader_fallback_reconstructs_complete_previous_matrix(monkeypatch):
    current, previous = _sample_pair()
    rows = []
    for column in fetch.POSITION_COLUMNS:
        cells = []
        for participant in fetch.PARTICIPANTS:
            current_row = current[current["ClientType"] == participant].iloc[0]
            previous_row = previous[previous["ClientType"] == participant].iloc[0]
            value = int(current_row[column])
            change = int(current_row[column] - previous_row[column])
            cells.extend((f"<td>{value:,}</td>", f"<td>{change:+,}(1.0%)</td>"))
        rows.append(f"<tr><td>{column}</td>{''.join(cells)}<td>0</td><td>0</td></tr>")
    html = (
        "<html><body><h2>Who's positioned how on 17 Sep 2026</h2>"
        f"<table>{''.join(rows)}</table></body></html>"
    )
    monkeypatch.setattr(fetch, "_third_party_get", lambda *args, **kwargs: html)
    metadata: dict = {}
    result = fetch.fetch_participant_oi_niftytrader(date(2026, 9, 17), metadata)

    assert result is not None
    reconstructed_current, reconstructed_previous, as_of = result
    assert as_of == date(2026, 9, 17)
    assert fetch.validate_participant_oi(reconstructed_current) == (True, "ok")
    assert fetch.validate_participant_oi(reconstructed_previous) == (True, "ok")
    assert metadata["source"] == "NiftyTrader EOD participant table"


def test_rendered_participant_sources_must_agree(monkeypatch):
    current, previous = _sample_pair()
    pair = (current, previous, date(2026, 9, 17))
    monkeypatch.setattr(
        fetch, "fetch_participant_oi_stocklyzer", lambda *args, **kwargs: pair
    )
    disagreeing = current.copy()
    disagreeing.loc[disagreeing["ClientType"] == "FII", "Future Index Long"] += 10
    monkeypatch.setattr(
        fetch,
        "fetch_participant_oi_niftytrader",
        lambda *args, **kwargs: (disagreeing, previous, date(2026, 9, 17)),
    )
    metadata: dict = {}
    assert fetch.fetch_participant_oi_rendered(date(2026, 9, 17), metadata) is None
    assert "disagree" in metadata["warning"]


def test_marketnetra_option_fallback_maps_call_and_put_columns(monkeypatch):
    rows = []
    for strike in range(23000, 23550, 50):
        rows.append(
            "<tr>"
            f"<td>{1000 + strike}</td><td>+111</td><td>2K</td><td>12</td><td>100</td>"
            f"<td>{strike}</td>"
            f"<td>90</td><td>13</td><td>3K</td><td>+222</td><td>{2000 + strike}</td>"
            "</tr>"
        )
    html = (
        "<html><body><div>₹23,270.60 LIVE Updated 17 Sept 2026, 09:21 pm IST</div>"
        "<div>2026-09-22</div><table><tr>"
        "<th>CE OI</th><th>Chg</th><th>Vol</th><th>IV</th><th>LTP</th>"
        "<th>Strike</th><th>LTP</th><th>IV</th><th>Vol</th><th>Chg</th><th>PE OI</th>"
        f"</tr>{''.join(rows)}</table></body></html>"
    )
    monkeypatch.setattr(fetch, "_third_party_get", lambda *args, **kwargs: html)
    payload, url = fetch._fetch_marketnetra_option_chain("NIFTY", date(2026, 9, 17))
    valid, reason = fetch.validate_option_chain(payload, date(2026, 9, 17))

    assert (valid, reason) == (True, "ok")
    assert "marketnetra" in url
    first = payload["records"]["data"][0]
    assert first["CE"]["changeinOpenInterest"] == 111
    assert first["PE"]["changeinOpenInterest"] == 222
    assert first["CE"]["totalTradedVolume"] == 2000
    assert first["PE"]["totalTradedVolume"] == 3000


def test_github_cash_fallback_requires_exact_date(monkeypatch):
    payload = {
        "date": "17-Sep-2026",
        "fii_buy": 100,
        "fii_sell": 150,
        "fii_net": -50,
        "dii_buy": 200,
        "dii_sell": 125,
        "dii_net": 75,
    }
    monkeypatch.setattr(
        fetch,
        "_github_content",
        lambda *args, **kwargs: (
            json.dumps(payload),
            "https://github.test/latest.json",
        ),
    )
    rows, _ = fetch._fetch_cash_mrchartist(date(2026, 9, 17))
    assert rows[0]["netValue"] == -50

    try:
        fetch._fetch_cash_mrchartist(date(2026, 9, 16))
    except RuntimeError as exc:
        assert "requested" in str(exc)
    else:
        raise AssertionError("stale fallback cash was accepted")


def test_date_validators_reject_undated_current_endpoint_payloads():
    cash = [
        {"category": "FII/FPI", "buyValue": 1, "sellValue": 2, "netValue": -1},
        {"category": "DII", "buyValue": 2, "sellValue": 1, "netValue": 1},
    ]
    valid, reason = fetch._valid_cash_rows(cash, date(2026, 9, 17))
    assert not valid
    assert "date None" in reason

    chain = {
        "records": {
            "underlyingValue": 100,
            "expiryDates": ["24-Sep-2026"],
            "data": [
                {
                    "strikePrice": strike,
                    "CE": {"openInterest": 1},
                    "PE": {"openInterest": 1},
                }
                for strike in range(50, 151, 10)
            ],
        }
    }
    valid, reason = fetch.validate_option_chain(chain, date(2026, 9, 17))
    assert not valid
    assert "date None" in reason

    quote = {"open": 100, "high": 110, "low": 95, "last": 105}
    valid, reason = fetch.validate_index_quote(quote, date(2026, 9, 17))
    assert not valid
    assert "date None" in reason


def test_nse_index_quote_uses_top_level_timestamp():
    class Client:
        def get_json(self, *args, **kwargs):
            return {
                "timestamp": "17-Sep-2026 15:30:00",
                "data": [
                    {
                        "index": "NIFTY 50",
                        "open": 100,
                        "high": 110,
                        "low": 95,
                        "last": 105,
                    }
                ],
            }

    metadata: dict = {}
    quote = fetch.fetch_index_quote(
        Client(), "NIFTY", date(2026, 9, 17), metadata
    )
    assert quote is not None
    assert quote["timestamp"] == "17-Sep-2026 15:30:00"
    assert metadata["source"] == "NSE all-indices API"


def test_index_quote_validator_rejects_inconsistent_bar():
    quote = {
        "open": 100,
        "high": 101,
        "low": 95,
        "last": 105,
        "lastUpdateTime": "17-Sep-2026",
    }
    valid, reason = fetch.validate_index_quote(quote, date(2026, 9, 17))
    assert not valid
    assert "high is inconsistent" in reason


def test_live_run_fails_closed_before_decode_when_oi_is_missing(monkeypatch):
    manifests = []
    monkeypatch.setattr(cli, "NseClient", lambda **kwargs: object())
    monkeypatch.setattr(fetch, "fetch_participant_oi", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        fetch, "fetch_participant_oi_rendered", lambda *args, **kwargs: None
    )
    context_status = {
        name: cli._source_unavailable("test source unavailable")
        for name in ("cash", "option_chain", "index_quote", "participant_volume")
    }
    monkeypatch.setattr(
        cli,
        "_fetch_session_context",
        lambda *args, **kwargs: (None, None, None, None, context_status),
    )
    monkeypatch.setattr(cli, "_persist_session_context", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        cli.store, "save_json", lambda data, name: manifests.append((data, name))
    )
    monkeypatch.setattr(
        cli,
        "decode",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("decode must not run with missing OI")
        ),
    )
    args = SimpleNamespace(
        symbol="NIFTY",
        demo=False,
        institutional_levels=None,
    )

    assert cli.run(args) == 2
    assert len(manifests) == 1
    assert manifests[0][0]["overall"] == "BLOCKED_MISSING_DIRECTION_INPUT"
    assert {"cash", "option_chain", "index_quote", "participant_volume"}.issubset(
        manifests[0][0]["inputs"]
    )


def test_data_health_distinguishes_required_and_optional_inputs():
    available = {"status": "available", "fallback": False}
    unavailable = {"status": "unavailable", "fallback": False}
    inputs = {
        "participant_oi_current": available,
        "participant_oi_previous": available,
        "option_chain": unavailable,
        "cash": unavailable,
        "institutional_references": {"status": "not_provided", "fallback": False},
    }
    status = _data_health("2026-09-17", inputs)
    assert status["direction_inputs_ready"]
    assert not status["level_inputs_ready"]
    assert status["overall"] == "DEGRADED_MISSING_LEVEL_INPUT"

    inputs["option_chain"] = available
    status = _data_health("2026-09-17", inputs)
    assert status["overall"] == "DEGRADED_MISSING_CASH_INPUT"
