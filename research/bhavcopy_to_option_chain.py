"""Convert NSE F&O bhavcopy archives into dated option-chain JSON snapshots.

The backtester consumes NSE-shaped option-chain JSON (``records.data`` with
``CE``/``PE`` legs). Public archives only publish end-of-day *bhavcopy* files,
so this script rebuilds an equivalent EOD snapshot per trading date:

* only index options on the requested symbol (``OPTIDX``/``STO`` rows) are kept;
* only the nearest non-expired expiry as of that date is emitted, matching the
  live fetcher, which reads ``records.expiryDates[0]``;
* ``underlyingValue`` comes from the same-date index close file, never from a
  later session.

Honest limitations (these are EOD reconstructions, not live snapshots):

* ``lastPrice`` is the bhavcopy settlement/close price, not a 15:30 LTP;
* implied volatility is not published in bhavcopy and is emitted as 0;
* ``underlyingValue`` is the index *close*, whereas the live chain carries the
  spot at snapshot time.

Both NSE layouts are supported: the legacy ``fo<DDMONYYYY>bhav.csv`` columns and
the 2024+ ``BhavCopy_NSE_FO_*`` UDiFF columns.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import zipfile
from datetime import date, datetime
from pathlib import Path

LEGACY_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def _num(value, default=0.0):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _parse_legacy_date(text: str) -> date | None:
    text = (text or "").strip()
    match = re.fullmatch(r"(\d{1,2})-([A-Za-z]{3})-(\d{4})", text)
    if not match:
        return None
    day, mon, year = match.groups()
    month = LEGACY_MONTHS.get(mon.upper())
    return date(int(year), month, int(day)) if month else None


def _parse_iso_date(text: str) -> date | None:
    text = (text or "").strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text[:len(fmt) + 2].strip(), fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def _nse_expiry_label(value: date) -> str:
    return f"{value.day:02d}-{value.strftime('%b')}-{value.year}"


def _rows(zip_path: Path):
    with zipfile.ZipFile(zip_path) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if not names:
            return
        with archive.open(names[0]) as handle:
            reader = csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8",
                                                     errors="replace"))
            for row in reader:
                yield {(k or "").strip(): v for k, v in row.items()}


def _extract(row: dict, symbol: str):
    """Return (trade_date, expiry, strike, option_type, leg) or None."""
    if "TckrSymb" in row:  # UDiFF layout
        if (row.get("TckrSymb") or "").strip().upper() != symbol:
            return None
        option_type = (row.get("OptnTp") or "").strip().upper()
        if option_type not in {"CE", "PE"}:
            return None
        if (row.get("FinInstrmTp") or "").strip().upper() not in {"IDO", "STO", "OPTIDX"}:
            return None
        trade_date = _parse_iso_date(row.get("TradDt", ""))
        expiry = _parse_iso_date(row.get("XpryDt", ""))
        strike = _num(row.get("StrkPric"), None)
        leg = {
            "lastPrice": _num(row.get("ClsPric")),
            "openInterest": _num(row.get("OpnIntrst")),
            "changeinOpenInterest": _num(row.get("ChngInOpnIntrst")),
            "totalTradedVolume": _num(row.get("TtlTradgVol")),
            "impliedVolatility": 0.0,
            "underlyingValue": _num(row.get("UndrlygPric"), None),
        }
    else:  # legacy layout
        if (row.get("SYMBOL") or "").strip().upper() != symbol:
            return None
        if (row.get("INSTRUMENT") or "").strip().upper() != "OPTIDX":
            return None
        option_type = (row.get("OPTION_TYP") or "").strip().upper()
        if option_type not in {"CE", "PE"}:
            return None
        trade_date = _parse_legacy_date(row.get("TIMESTAMP", ""))
        expiry = _parse_legacy_date(row.get("EXPIRY_DT", ""))
        strike = _num(row.get("STRIKE_PR"), None)
        leg = {
            "lastPrice": _num(row.get("CLOSE")),
            "openInterest": _num(row.get("OPEN_INT")),
            "changeinOpenInterest": _num(row.get("CHG_IN_OI")),
            "totalTradedVolume": _num(row.get("CONTRACTS")),
            "impliedVolatility": 0.0,
            "underlyingValue": None,
        }
    if trade_date is None or expiry is None or strike is None:
        return None
    return trade_date, expiry, strike, option_type, leg


def load_index_closes(directory: Path, index_name: str) -> dict[date, float]:
    closes: dict[date, float] = {}
    wanted = index_name.strip().lower()
    for path in sorted(directory.glob("*.csv")):
        with path.open(newline="", encoding="utf-8", errors="replace") as handle:
            for row in csv.DictReader(handle):
                if (row.get("Index Name") or "").strip().lower() != wanted:
                    continue
                raw = (row.get("Index Date") or "").strip()
                try:
                    day = datetime.strptime(raw, "%d-%m-%Y").date()
                except ValueError:
                    continue
                value = _num(row.get("Closing Index Value"), None)
                if value is not None:
                    closes[day] = value
    return closes


def convert_file(zip_path: Path, symbol: str,
                 closes: dict[date, float]) -> tuple[date, dict] | None:
    by_expiry: dict[date, dict[float, dict]] = {}
    trade_dates: set[date] = set()
    underlying_hint: float | None = None

    for row in _rows(zip_path):
        parsed = _extract(row, symbol)
        if parsed is None:
            continue
        trade_date, expiry, strike, option_type, leg = parsed
        trade_dates.add(trade_date)
        hint = leg.pop("underlyingValue", None)
        if hint:
            underlying_hint = hint
        by_expiry.setdefault(expiry, {}).setdefault(strike, {})[option_type] = leg

    if not by_expiry or len(trade_dates) != 1:
        return None
    trade_date = trade_dates.pop()

    future = sorted(e for e in by_expiry if e >= trade_date)
    if not future:
        return None
    expiries = future + sorted(e for e in by_expiry if e < trade_date)
    nearest = future[0]

    spot = closes.get(trade_date, underlying_hint)
    if spot is None:
        return None

    data = []
    for strike in sorted(by_expiry[nearest]):
        record = {"strikePrice": strike,
                  "expiryDate": _nse_expiry_label(nearest)}
        for side, leg in by_expiry[nearest][strike].items():
            record[side] = dict(leg, strikePrice=strike,
                                expiryDate=_nse_expiry_label(nearest),
                                underlying=symbol, underlyingValue=spot)
        data.append(record)

    chain = {
        "records": {
            "expiryDates": [_nse_expiry_label(e) for e in expiries],
            "data": data,
            "timestamp": f"{trade_date.isoformat()} 15:30:00",
            "underlyingValue": spot,
        },
        "filtered": {"data": data},
        "_source": {
            "builder": "research/bhavcopy_to_option_chain.py",
            "bhavcopy_file": zip_path.name,
            "trade_date": trade_date.isoformat(),
            "nearest_expiry": nearest.isoformat(),
            "underlying_source": ("index_close_file" if trade_date in closes
                                  else "bhavcopy_underlying_price"),
            "limitations": [
                "lastPrice is the EOD close/settlement, not a live LTP",
                "impliedVolatility is not published in bhavcopy and is 0",
                "underlyingValue is the index close, not the snapshot-time spot",
            ],
        },
    }
    return trade_date, chain


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bhavcopy-dir", required=True)
    parser.add_argument("--index-close-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--symbol", default="NIFTY")
    parser.add_argument("--index-name", default="Nifty 50")
    args = parser.parse_args(argv)

    bhav_dir = Path(args.bhavcopy_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    closes = load_index_closes(Path(args.index_close_dir), args.index_name)
    if not closes:
        print(f"no '{args.index_name}' closes found", file=sys.stderr)
        return 2

    files = sorted(p for p in bhav_dir.iterdir()
                   if p.name.lower().endswith(".zip"))
    written = skipped = 0
    for path in files:
        try:
            result = convert_file(path, args.symbol.upper(), closes)
        except (zipfile.BadZipFile, OSError, csv.Error) as exc:
            print(f"skip {path.name}: {exc}", file=sys.stderr)
            skipped += 1
            continue
        if result is None:
            skipped += 1
            continue
        trade_date, chain = result
        target = out_dir / f"option_chain_{args.symbol.upper()}_{trade_date.isoformat()}.json"
        target.write_text(json.dumps(chain), encoding="utf-8")
        written += 1

    print(f"bhavcopy files: {len(files)}  written: {written}  skipped: {skipped}")
    print(f"output: {out_dir}")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
