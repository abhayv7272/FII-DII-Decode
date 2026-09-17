"""Tests for the bhavcopy -> option-chain snapshot converter."""
from __future__ import annotations

import csv
import importlib.util
import io
import json
import zipfile
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "bhavcopy_to_option_chain", ROOT / "research" / "bhavcopy_to_option_chain.py")
conv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conv)

UDIFF_HEADER = ["TradDt", "BizDt", "Sgmt", "FinInstrmTp", "TckrSymb", "XpryDt",
                "StrkPric", "OptnTp", "ClsPric", "UndrlygPric", "OpnIntrst",
                "ChngInOpnIntrst", "TtlTradgVol"]
LEGACY_HEADER = ["INSTRUMENT", "SYMBOL", "EXPIRY_DT", "STRIKE_PR", "OPTION_TYP",
                 "CLOSE", "CONTRACTS", "OPEN_INT", "CHG_IN_OI", "TIMESTAMP"]


def _zip(tmp_path: Path, name: str, header: list[str], rows: list[list]) -> Path:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(name.replace(".zip", ""), buffer.getvalue())
    return path


def _udiff(tmp_path: Path) -> Path:
    rows = [
        # nearest expiry 2024-07-11
        ["2024-07-08", "2024-07-08", "FO", "IDO", "NIFTY", "2024-07-11",
         "24000.00", "CE", "150.5", "24010", "1000", "100", "50"],
        ["2024-07-08", "2024-07-08", "FO", "IDO", "NIFTY", "2024-07-11",
         "24000.00", "PE", "120.5", "24010", "2000", "-50", "70"],
        # far expiry must be excluded from records.data
        ["2024-07-08", "2024-07-08", "FO", "IDO", "NIFTY", "2024-07-25",
         "24500.00", "CE", "90.0", "24010", "500", "10", "5"],
        # other symbol must be excluded
        ["2024-07-08", "2024-07-08", "FO", "IDO", "BANKNIFTY", "2024-07-11",
         "51000.00", "CE", "10.0", "51010", "5", "1", "1"],
        # a future (no option type) must be excluded
        ["2024-07-08", "2024-07-08", "FO", "IDF", "NIFTY", "2024-07-25",
         "0", "", "24050", "24010", "9", "1", "1"],
    ]
    return _zip(tmp_path, "BhavCopy_NSE_FO_20240708.csv.zip", UDIFF_HEADER, rows)


def _legacy(tmp_path: Path) -> Path:
    rows = [
        ["OPTIDX", "NIFTY", "27-Jun-2024", "24000", "CE", "150.5", "50",
         "1000", "100", "31-MAY-2024"],
        ["OPTIDX", "NIFTY", "27-Jun-2024", "24000", "PE", "120.5", "70",
         "2000", "-50", "31-MAY-2024"],
        ["FUTIDX", "NIFTY", "27-Jun-2024", "0", "XX", "24050", "9",
         "10", "1", "31-MAY-2024"],
    ]
    return _zip(tmp_path, "fo31MAY2024bhav.csv.zip", LEGACY_HEADER, rows)


@pytest.fixture()
def closes() -> dict[date, float]:
    return {date(2024, 7, 8): 24011.25, date(2024, 5, 31): 22530.7}


def test_udiff_conversion_uses_nearest_expiry_and_index_close(tmp_path, closes):
    trade_date, chain = conv.convert_file(_udiff(tmp_path), "NIFTY", closes)

    assert trade_date == date(2024, 7, 8)
    assert chain["records"]["underlyingValue"] == 24011.25
    assert chain["records"]["expiryDates"][0] == "11-Jul-2024"
    assert [r["strikePrice"] for r in chain["records"]["data"]] == [24000.0]

    record = chain["records"]["data"][0]
    assert record["CE"]["openInterest"] == 1000
    assert record["CE"]["changeinOpenInterest"] == 100
    assert record["PE"]["openInterest"] == 2000
    assert record["PE"]["lastPrice"] == 120.5
    assert record["CE"]["impliedVolatility"] == 0.0
    assert chain["_source"]["underlying_source"] == "index_close_file"


def test_legacy_layout_is_supported(tmp_path, closes):
    trade_date, chain = conv.convert_file(_legacy(tmp_path), "NIFTY", closes)

    assert trade_date == date(2024, 5, 31)
    assert chain["records"]["underlyingValue"] == 22530.7
    assert chain["records"]["expiryDates"][0] == "27-Jun-2024"
    record = chain["records"]["data"][0]
    assert record["CE"]["openInterest"] == 1000
    assert record["PE"]["changeinOpenInterest"] == -50


def test_missing_index_close_falls_back_to_bhavcopy_underlying(tmp_path):
    trade_date, chain = conv.convert_file(_udiff(tmp_path), "NIFTY", {})
    assert trade_date == date(2024, 7, 8)
    assert chain["records"]["underlyingValue"] == 24010.0
    assert chain["_source"]["underlying_source"] == "bhavcopy_underlying_price"


def test_legacy_without_index_close_is_skipped(tmp_path):
    # legacy bhavcopy has no underlying column, so a date with no index close
    # must be dropped rather than guessed.
    assert conv.convert_file(_legacy(tmp_path), "NIFTY", {}) is None


def test_output_is_loadable_by_the_backtester(tmp_path, closes):
    from fiidii.backtest import load_option_chains
    from fiidii.levels import derive_levels

    out = tmp_path / "out"
    out.mkdir()
    trade_date, chain = conv.convert_file(_udiff(tmp_path), "NIFTY", closes)
    (out / f"option_chain_NIFTY_{trade_date.isoformat()}.json").write_text(
        json.dumps(chain), encoding="utf-8")

    chains = load_option_chains(out, "NIFTY")
    assert set(chains) == {date(2024, 7, 8)}
    levels = derive_levels(chains[date(2024, 7, 8)])
    assert "levels" in levels and levels["pcr"] == pytest.approx(2.0)
