"""Network-free tests for timestamped forward-research data collection."""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fiidii.context import option_chain_snapshot
from fiidii import cli, fetch, store


def _chain() -> dict:
    rows = []
    for index, strike in enumerate((23000, 23050, 23100, 23150, 23200), start=1):
        rows.append(
            {
                "strikePrice": strike,
                "expiryDate": "24-Sep-2026",
                "CE": {
                    "openInterest": 100 * index,
                    "changeinOpenInterest": 10 * index,
                    "totalTradedVolume": 20 * index,
                    "impliedVolatility": 12 + index,
                },
                "PE": {
                    "openInterest": 600 - 100 * index,
                    "changeinOpenInterest": 60 - 10 * index,
                    "totalTradedVolume": 120 - 20 * index,
                    "impliedVolatility": 15 + index,
                },
            }
        )
    return {
        "records": {
            "timestamp": "19-Sep-2026 10:00:00",
            "underlyingValue": 23110,
            "expiryDates": ["24-Sep-2026"],
            "data": rows,
        }
    }


def test_option_chain_snapshot_is_compact_timestamped_and_auditable():
    captured = datetime(2026, 9, 19, 4, 35, tzinfo=timezone.utc)
    snapshot = option_chain_snapshot(
        _chain(),
        symbol="NIFTY",
        captured_at=captured,
        source_metadata={
            "source": "NSE option-chain API",
            "url": "https://nse.test/chain",
            "as_of": "2026-09-19",
            "fallback": False,
        },
        quote={"open": 23080, "high": 23150, "low": 23040, "last": 23110, "previousClose": 23075},
    )
    assert snapshot["captured_at_utc"] == "2026-09-19T04:35:00+00:00"
    assert snapshot["session_date"] == "2026-09-19"
    assert snapshot["selected_expiry"] == "2026-09-24"
    assert snapshot["strike_count"] == 5
    assert snapshot["call_oi"] == 1500
    assert snapshot["put_oi"] == 1500
    assert snapshot["pcr_oi"] == 1.0
    assert snapshot["call_wall_strike"] == 23200
    assert snapshot["put_wall_strike"] == 23000
    assert snapshot["payload_sha256"]
    assert snapshot["quote_previous_close"] == 23075
    # The compact aggregate deliberately has no raw strike array.
    assert "data" not in snapshot


def test_option_chain_snapshot_preserves_signed_change_oi_and_unwind_wall():
    raw = _chain()
    for number, row in enumerate(raw["records"]["data"], start=1):
        row["CE"]["changeinOpenInterest"] = -10 * number
        row["PE"]["changeinOpenInterest"] = 5 * number
    snapshot = option_chain_snapshot(
        raw,
        symbol="NIFTY",
        captured_at=datetime(2026, 9, 19, 4, 35, tzinfo=timezone.utc),
        source_metadata={"fallback": False},
    )
    assert snapshot["call_change_oi"] == -150
    assert snapshot["near_call_change_oi"] == -150
    assert snapshot["call_doi_wall"] == -10
    assert snapshot["call_doi_wall_strike"] == 23000
    assert snapshot["call_unwind_wall"] == -50
    assert snapshot["call_unwind_wall_strike"] == 23200


def test_option_chain_snapshot_requires_timezone_aware_capture_and_usable_rows():
    with pytest.raises(ValueError, match="timezone-aware"):
        option_chain_snapshot(
            _chain(), symbol="NIFTY", captured_at=datetime(2026, 9, 19, 4, 35), source_metadata={}
        )
    malformed = _chain()
    malformed["records"]["data"] = malformed["records"]["data"][:2]
    with pytest.raises(ValueError, match="fewer than five"):
        option_chain_snapshot(
            malformed,
            symbol="NIFTY",
            captured_at=datetime(2026, 9, 19, 4, 35, tzinfo=timezone.utc),
            source_metadata={},
        )
    stale = _chain()
    stale["records"]["timestamp"] = "18-Sep-2026 15:29:00"
    with pytest.raises(ValueError, match="source timestamp date"):
        option_chain_snapshot(
            stale,
            symbol="NIFTY",
            captured_at=datetime(2026, 9, 19, 4, 35, tzinfo=timezone.utc),
            source_metadata={},
        )
    stale_same_day = _chain()
    stale_same_day["records"]["timestamp"] = "19-Sep-2026 09:00:00"
    with pytest.raises(ValueError, match="stale by"):
        option_chain_snapshot(
            stale_same_day,
            symbol="NIFTY",
            captured_at=datetime(2026, 9, 19, 4, 35, tzinfo=timezone.utc),
            source_metadata={},
        )


def test_preopen_fetch_normalises_direct_nse_payload_and_rejects_stale_state():
    payload = {
        "timestamp": "19-Sep-2026 09:07:00",
        "data": [
            {
                "metadata": {
                    "symbol": "NIFTY 50",
                    "lastUpdateTime": "19-Sep-2026 09:07:00",
                    "previousClose": 23000,
                    "lastPrice": 23025,
                    "change": 25,
                    "pChange": 0.1087,
                },
                "detail": {"totalBuyQuantity": 500, "totalSellQuantity": 300},
            }
        ],
    }

    class Client:
        def get_json(self, *args, **kwargs):
            return payload

    metadata: dict = {}
    state = fetch.fetch_preopen_index_state(Client(), "NIFTY", date(2026, 9, 19), metadata)
    assert state is not None
    assert state["indicative_price"] == 23025
    assert state["previous_close"] == 23000
    assert state["payload_sha256"]
    assert metadata["source"] == "NSE pre-open market-data API"
    assert not metadata["fallback"]

    stale_meta: dict = {}
    assert fetch.fetch_preopen_index_state(Client(), "NIFTY", date(2026, 9, 18), stale_meta) is None
    assert "requested" in stale_meta["warning"]

    delayed_meta: dict = {}
    assert fetch.fetch_preopen_index_state(
        Client(),
        "NIFTY",
        date(2026, 9, 19),
        delayed_meta,
        captured_at=datetime(2026, 9, 19, 3, 50, tzinfo=timezone.utc),  # 09:20 IST
    ) is None
    assert "stale by" in delayed_meta["warning"]


def test_preopen_constituent_feed_is_labelled_breadth_not_an_invented_index_level():
    changes = (1.2, -0.5, 0.0, 0.3, -0.2)
    payload = {
        "data": [
            {
                "metadata": {
                    "symbol": f"STOCK{number}",
                    "lastUpdateTime": "19-Sep-2026 09:07:00",
                    "previousClose": 100,
                    "lastPrice": 100 * (1 + change / 100),
                    "pChange": change,
                }
            }
            for number, change in enumerate(changes, start=1)
        ]
    }

    class Client:
        def get_json(self, *args, **kwargs):
            return payload

    state = fetch.fetch_preopen_index_state(Client(), "NIFTY", date(2026, 9, 19), {})
    assert state is not None
    assert state["state_type"] == "constituent_breadth"
    assert state["constituent_count"] == 5
    assert (state["advances"], state["declines"], state["unchanged"]) == (2, 2, 1)
    assert state["mean_pchange"] == pytest.approx(0.16)
    assert state.get("indicative_price") is None

    # One same-date-but-stale constituent must invalidate the whole aggregate
    # rather than letting the first/current timestamp mask a mixed payload.
    payload["data"][-1]["metadata"]["lastUpdateTime"] = "19-Sep-2026 09:00:00"
    stale_lag_metadata: dict = {}
    assert fetch.fetch_preopen_index_state(
        Client(),
        "NIFTY",
        date(2026, 9, 19),
        stale_lag_metadata,
        captured_at=datetime(2026, 9, 19, 3, 44, tzinfo=timezone.utc),  # 09:14 IST
    ) is None
    assert "stale constituent" in stale_lag_metadata["warning"]

    payload["data"][-1]["metadata"]["lastUpdateTime"] = "18-Sep-2026 09:07:00"
    stale_metadata: dict = {}
    assert fetch.fetch_preopen_index_state(Client(), "NIFTY", date(2026, 9, 19), stale_metadata) is None
    assert "mixed/stale" in stale_metadata["warning"]


def test_preopen_cli_rejects_a_delayed_non_preopen_capture(monkeypatch):
    # 10:00 IST: retaining an apparent pre-open value would leak later state.
    fixed = datetime(2026, 9, 19, 4, 30, tzinfo=timezone.utc)
    statuses = []
    monkeypatch.setattr(cli, "_context_now", lambda: fixed)
    monkeypatch.setattr(cli.store, "save_json", lambda obj, name: statuses.append((obj, name)))
    assert cli.run_capture_preopen_command(SimpleNamespace(symbol="NIFTY")) == 2
    assert statuses[-1][0]["status"] == "rejected"
    assert "outside" in statuses[-1][0]["warning"]


def test_direct_option_chain_mode_never_uses_eod_fallback(monkeypatch):
    class FailingClient:
        def get_json(self, *args, **kwargs):
            raise RuntimeError("NSE unavailable")

    monkeypatch.setattr(
        fetch,
        "_fetch_marketnetra_option_chain",
        lambda *args, **kwargs: pytest.fail("EOD fallback must not be called for timed capture"),
    )
    metadata: dict = {}
    result = fetch.fetch_option_chain(
        FailingClient(), "NIFTY", date(2026, 9, 19), metadata, allow_fallback=False
    )
    assert result is None
    assert metadata["status"] == "unavailable"
    assert metadata["source"] is None
    assert "direct NSE" in metadata["warning"]


def test_intraday_cli_rejects_eod_fallback_and_stores_only_direct_snapshot(monkeypatch):
    fixed = datetime(2026, 9, 19, 4, 35, tzinfo=timezone.utc)
    saved_statuses = []
    appended = []
    monkeypatch.setattr(cli, "_context_now", lambda: fixed)
    monkeypatch.setattr(cli, "NseClient", lambda **kwargs: object())
    monkeypatch.setattr(cli.store, "save_json", lambda obj, name: saved_statuses.append((obj, name)))
    monkeypatch.setattr(cli.store, "append_df", lambda frame, name, dedup_on: appended.append((frame, name, dedup_on)))

    def fallback_chain(_client, symbol, expected_date, metadata, **kwargs):
        metadata.update({"source": "EOD fallback", "fallback": True, "warning": "not timed"})
        return _chain()

    monkeypatch.setattr(fetch, "fetch_option_chain", fallback_chain)
    assert cli.run_capture_intraday_command(SimpleNamespace(symbol="NIFTY", save_raw=False)) == 2
    assert not appended
    assert saved_statuses[-1][0]["status"] == "unavailable"

    def direct_chain(_client, symbol, expected_date, metadata, **kwargs):
        metadata.update({
            "source": "NSE option-chain API", "url": "https://nse.test/chain",
            "as_of": expected_date.isoformat(), "fallback": False,
        })
        return _chain()

    def direct_quote(_client, symbol, expected_date, metadata):
        metadata.update({"source": "NSE all-indices API", "fallback": False})
        return {"open": 23080, "high": 23150, "low": 23040, "last": 23110, "previousClose": 23075}

    monkeypatch.setattr(fetch, "fetch_option_chain", direct_chain)
    monkeypatch.setattr(fetch, "fetch_index_quote", direct_quote)
    assert cli.run_capture_intraday_command(SimpleNamespace(symbol="NIFTY", save_raw=False)) == 0
    frame, name, keys = appended[-1]
    assert name == "intraday_option_snapshots"
    assert keys == ["symbol", "captured_at_utc"]
    assert frame.iloc[0]["source"] == "NSE option-chain API"
    assert frame.iloc[0]["source_fallback"] == False


def test_timestamped_context_store_deduplicates_at_capture_level_and_raw_is_opt_in(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path / "data")
    row = {"symbol": "NIFTY", "captured_at_utc": "2026-09-19T04:35:00+00:00", "spot": 23110}
    replacement = {**row, "spot": 23115}
    store.append_df(pd.DataFrame([row]), "intraday_option_snapshots", ["symbol", "captured_at_utc"])
    store.append_df(pd.DataFrame([replacement]), "intraday_option_snapshots", ["symbol", "captured_at_utc"])
    stored = store.load_df("intraday_option_snapshots")
    assert len(stored) == 1
    assert stored.iloc[0]["spot"] == 23115

    raw_path = store.save_intraday_option_chain({"records": {"data": []}}, "NIFTY", row["captured_at_utc"])
    assert raw_path.exists()
    assert "intraday_option_chain/NIFTY/2026-09-19" in str(raw_path)
