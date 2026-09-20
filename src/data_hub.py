from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

IST = ZoneInfo("Asia/Kolkata")
PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / "data" / "hub"
CACHE = ROOT / "last_good"


@dataclass
class SourceResult:
    dataset: str
    source: str
    status: str
    as_of: str | None
    rows: int
    latency_ms: int
    path: str | None = None
    sha256: str | None = None
    cache_path: str | None = None
    error: str | None = None
    stale_days: int | None = None


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_text(path: Path | str, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _save(dataset: str, source: str, df: pd.DataFrame, run_dir: Path) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / f"{dataset}__{source}.csv"
    df.to_csv(path, index=False)
    return path


def _datefmt(value) -> str:
    return pd.Timestamp(value).strftime("%d-%m-%Y")


def _max_mixed_date(values):
    return pd.to_datetime(values, format="mixed", dayfirst=True, errors="coerce").max()


def _asof(value) -> str:
    ts = pd.Timestamp(value)
    if pd.isna(ts):
        raise ValueError("invalid or missing as-of date")
    return str(ts.date())


def _safe_json(path: Path, errors: list[str] | None = None, label: str = "json") -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if errors is not None:
            errors.append(f"{label}: corrupt/unreadable metadata {path}: {exc}")
        return None


def _retry(fn, attempts: int = 3):
    err = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - provider adapters intentionally isolated
            err = exc
            time.sleep(0.8 * (i + 1))
    raise err


def _require_columns(df: pd.DataFrame, cols: set[str], name: str) -> None:
    missing = sorted(cols - set(df.columns))
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")


def _numeric_has_data(df: pd.DataFrame, cols: list[str]) -> bool:
    for col in cols:
        if col not in df:
            return False
        values = pd.to_numeric(df[col], errors="coerce")
        if values.notna().sum() == 0:
            return False
    return True


def validate_price_history(df: pd.DataFrame) -> bool:
    _require_columns(df, {"Date", "Open", "High", "Low", "Close"}, "nifty_price")
    dates = pd.to_datetime(df["Date"], errors="coerce")
    if len(df) < 200 or dates.notna().sum() < 200:
        return False
    return _numeric_has_data(df, ["Open", "High", "Low", "Close"])


def validate_options_payload(df: pd.DataFrame) -> bool:
    required = {
        "TIMESTAMP",
        "EXPIRY_DT",
        "STRIKE_PRICE",
        "OPTION_TYPE",
        "CLOSING_PRICE",
        "OPEN_INT",
        "CHANGE_IN_OI",
        "TOT_TRADED_QTY",
        "UNDERLYING_VALUE",
    }
    _require_columns(df, required, "nifty_options_eod")
    if len(df) < 20:
        return False
    types = set(df["OPTION_TYPE"].astype(str).str.upper())
    if not {"CE", "PE"}.issubset(types):
        return False
    return _numeric_has_data(df, ["STRIKE_PRICE", "OPEN_INT", "TOT_TRADED_QTY", "UNDERLYING_VALUE"])


def validate_futures_payload(df: pd.DataFrame) -> bool:
    required = {
        "TIMESTAMP",
        "EXPIRY_DT",
        "CLOSING_PRICE",
        "OPEN_INT",
        "CHANGE_IN_OI",
        "TOT_TRADED_QTY",
        "UNDERLYING_VALUE",
    }
    _require_columns(df, required, "nifty_futures_eod")
    if len(df) < 1:
        return False
    return _numeric_has_data(df, ["CLOSING_PRICE", "OPEN_INT", "TOT_TRADED_QTY", "UNDERLYING_VALUE"])


def validate_participant_payload(df: pd.DataFrame) -> bool:
    q = df.copy()
    q.columns = [str(c).strip() for c in q.columns]
    required = {
        "Client Type",
        "Future Index Long",
        "Future Index Short",
        "Future Stock Long",
        "Future Stock Short",
        "Option Index Call Long",
        "Option Index Call Short",
        "Option Index Put Long",
        "Option Index Put Short",
        "Total Long Contracts",
        "Total Short Contracts",
    }
    _require_columns(q, required, "participant_oi")
    clients = set(q["Client Type"].astype(str).str.strip().str.casefold())
    if not {"fii", "dii", "client", "pro"}.issubset(clients):
        return False
    numeric_cols = sorted(required - {"Client Type"})
    return _numeric_has_data(q, numeric_cols)


def validate_vix_payload(df: pd.DataFrame) -> bool:
    if len(df) < 1:
        return False
    return ("TIMESTAMP" in df or "Date" in df) and (
        "CLOSE_INDEX_VAL" in df or "Close" in df or "close" in df
    )


def validate_cash_payload(df: pd.DataFrame) -> bool:
    if len(df) < 2:
        return False
    cols = {str(c).lower() for c in df.columns}
    return {"date", "category"}.issubset(cols)


def validate_cross_market_payload(df: pd.DataFrame) -> bool:
    if "status" not in df:
        return False
    return int(df["status"].astype(str).str.casefold().eq("ok").sum()) >= 10


def yahoo_history(ticker: str = "^NSEI", period: str = "10y") -> pd.DataFrame:
    import yfinance as yf

    data = yf.download(ticker, period=period, interval="1d", auto_adjust=False, progress=False, threads=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data = data[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
    data.index = pd.to_datetime(data.index).tz_localize(None).normalize()
    data.index.name = "Date"
    return data.reset_index()


def nse_index_history(end) -> pd.DataFrame:
    from nselib import capital_market

    start = (pd.Timestamp(end) - pd.Timedelta(days=3650)).strftime("%d-%m-%Y")
    stop = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%d-%m-%Y")
    data = capital_market.index_data("NIFTY 50", from_date=start, to_date=stop)
    if data.empty:
        raise ValueError("empty NSE index history")
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(data.TIMESTAMP, dayfirst=True),
            "Open": pd.to_numeric(data.OPEN_INDEX_VAL),
            "High": pd.to_numeric(data.HIGH_INDEX_VAL),
            "Low": pd.to_numeric(data.LOW_INDEX_VAL),
            "Close": pd.to_numeric(data.CLOSE_INDEX_VAL),
            "Volume": pd.to_numeric(data.TRADED_QTY, errors="coerce").fillna(0),
        }
    ).sort_values("Date")


def yahoo_chart(ticker: str, start, end) -> pd.DataFrame:
    import requests

    p1 = int(pd.Timestamp(start, tz="UTC").timestamp())
    p2 = int((pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={p1}&period2={p2}&interval=1d&events=history"
    payload = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20).json()
    result = payload["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(result["timestamp"], unit="s", utc=True).tz_convert(None).normalize(),
            "Open": quote["open"],
            "High": quote["high"],
            "Low": quote["low"],
            "Close": quote["close"],
            "Volume": quote["volume"],
        }
    ).dropna(subset=["Close"])


def participant_nselib(session):
    from nselib import derivatives

    return derivatives.participant_wise_open_interest(_datefmt(session))


def participant_archive(session) -> pd.DataFrame:
    import requests

    url = f"https://nsearchives.nseindia.com/content/nsccl/fao_participant_oi_{pd.Timestamp(session).strftime('%d%m%Y')}.csv"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
    response.raise_for_status()
    return pd.read_csv(BytesIO(response.content), skiprows=1, on_bad_lines="skip")


def futures_nselib(session) -> pd.DataFrame:
    from nselib import derivatives

    day = pd.Timestamp(session)
    return derivatives.future_price_volume_data(
        "NIFTY", "FUTIDX", from_date=_datefmt(day), to_date=_datefmt(day + pd.Timedelta(days=1))
    )


def bhavcopy_filtered(session, kind: str) -> pd.DataFrame:
    """Normalize both modern NSE UDiFF and legacy bhavcopy schemas."""
    from nselib import derivatives

    data = derivatives.fno_bhav_copy(_datefmt(session))
    if {"FinInstrmTp", "TckrSymb"}.issubset(data.columns):
        code = "IDF" if kind == "future" else "IDO"
        rows = data[(data.FinInstrmTp.eq(code)) & (data.TckrSymb.eq("NIFTY"))].copy()
        if rows.empty:
            raise ValueError(f"No NIFTY {kind} rows in UDiFF bhavcopy")
        out = rows.rename(
            columns={
                "TradDt": "TIMESTAMP",
                "XpryDt": "EXPIRY_DT",
                "StrkPric": "STRIKE_PRICE",
                "OptnTp": "OPTION_TYPE",
                "OpnPric": "OPENING_PRICE",
                "HghPric": "TRADE_HIGH_PRICE",
                "LwPric": "TRADE_LOW_PRICE",
                "ClsPric": "CLOSING_PRICE",
                "LastPric": "LAST_TRADED_PRICE",
                "PrvsClsgPric": "PREV_CLS",
                "SttlmPric": "SETTLE_PRICE",
                "TtlTradgVol": "TRADED_CONTRACTS",
                "OpnIntrst": "OPEN_INT",
                "ChngInOpnIntrst": "CHANGE_IN_OI",
                "NewBrdLotQty": "MARKET_LOT",
                "UndrlygPric": "UNDERLYING_VALUE",
            }
        )
        # Contract archive reports quantity; UDiFF bhavcopy reports traded contracts.
        out["TOT_TRADED_QTY"] = pd.to_numeric(out["TRADED_CONTRACTS"], errors="coerce").fillna(0) * pd.to_numeric(
            out["MARKET_LOT"], errors="coerce"
        ).fillna(1)
        return out

    cols = {str(c).upper(): c for c in data.columns}
    inst = cols.get("INSTRUMENT")
    symbol = cols.get("SYMBOL")
    if inst and symbol:
        token = "FUT" if kind == "future" else "OPT"
        rows = data[
            (data[inst].astype(str).str.contains(token, case=False, na=False))
            & (data[symbol].astype(str).eq("NIFTY"))
        ]
        if not rows.empty:
            return rows
    raise ValueError("Bhavcopy schema cannot be normalized automatically")


def options_nselib(session) -> pd.DataFrame:
    from nselib import derivatives

    day = pd.Timestamp(session)
    start = _datefmt(day)
    stop = _datefmt(day + pd.Timedelta(days=1))
    return pd.concat(
        [derivatives.option_price_volume_data("NIFTY", "OPTIDX", typ, from_date=start, to_date=stop) for typ in ["CE", "PE"]],
        ignore_index=True,
    )


def vix_nse(session) -> pd.DataFrame:
    from nselib import capital_market

    day = pd.Timestamp(session)
    return capital_market.india_vix_data(from_date=_datefmt(day), to_date=_datefmt(day + pd.Timedelta(days=1)))


def vix_yahoo(session) -> pd.DataFrame:
    return yahoo_chart("%5EINDIAVIX", pd.Timestamp(session) - pd.Timedelta(days=7), session)


def fii_cash_nse(session) -> pd.DataFrame:  # noqa: ARG001 - adapter signature kept uniform
    from .collector import nse_json

    return pd.DataFrame(nse_json("/api/fiidiiTradeReact"))


def fii_cash_groww(session) -> pd.DataFrame:  # noqa: ARG001 - adapter signature kept uniform
    tables = pd.read_html("https://groww.in/fii-dii-data")
    data = tables[0]
    row = data.iloc[0]
    return pd.DataFrame(
        [
            {"category": "FII/FPI", "date": row.iloc[0], "buyValue": row.iloc[1], "sellValue": row.iloc[2], "netValue": row.iloc[3]},
            {"category": "DII", "date": row.iloc[0], "buyValue": row.iloc[4], "sellValue": row.iloc[5], "netValue": row.iloc[6]},
        ]
    )


def cross_yfinance(session) -> pd.DataFrame:
    from .collector import collect_cross_market_context

    detail, _summary = collect_cross_market_context(session, datetime.now(IST))
    return detail


def cross_yahoo_chart(session) -> pd.DataFrame:
    groups = {
        "india": ["%5ENSEBANK", "%5ECNXIT", "%5EBSESN", "%5EINDIAVIX"],
        "asia": ["%5EN225", "%5EHSI"],
        "global": ["SPY", "QQQ", "%5EVIX", "DX-Y.NYB", "CL%3DF", "GC%3DF", "USDINR%3DX"],
    }
    rows = []
    session_ts = pd.Timestamp(session)
    for group, tickers in groups.items():
        for ticker in tickers:
            data = yahoo_chart(ticker, session_ts - pd.Timedelta(days=15), session_ts)
            eligible = data[pd.to_datetime(data.Date) < session_ts] if group == "global" else data[pd.to_datetime(data.Date) <= session_ts]
            if len(eligible) < 2:
                continue
            prev, latest = eligible.iloc[-2], eligible.iloc[-1]
            rows.append(
                {
                    "group": group,
                    "ticker": ticker,
                    "source_date": str(pd.Timestamp(latest.Date).date()),
                    "close": latest.Close,
                    "return_1d": latest.Close / prev.Close - 1,
                    "volume": latest.Volume,
                    "timing_rule": "strictly_before_D" if group == "global" else "at_or_before_D",
                    "status": "ok",
                }
            )
    return pd.DataFrame(rows)


def summarize_futures(data: pd.DataFrame) -> pd.DataFrame:
    x = data.copy().rename(
        columns={
            "EXPIRY_DT": "expiry",
            "CLOSING_PRICE": "close",
            "OPEN_INT": "oi",
            "CHANGE_IN_OI": "change_oi",
            "TOT_TRADED_QTY": "volume",
            "UNDERLYING_VALUE": "spot",
            "TIMESTAMP": "date",
        }
    )
    for col in ["close", "oi", "change_oi", "volume", "spot"]:
        x[col] = pd.to_numeric(x[col], errors="coerce")
    x["expiry"] = pd.to_datetime(x.expiry, format="mixed", dayfirst=True, errors="coerce")
    x = x.dropna(subset=["expiry", "date", "close", "oi", "spot"]).sort_values("expiry")
    if x.empty:
        raise ValueError("No valid futures row after schema/date validation")
    near = x.iloc[0]
    nxt = x.iloc[1] if len(x) > 1 else None
    total_oi = float(x.oi.sum())
    if not near.spot or pd.isna(near.spot):
        raise ValueError("Missing NIFTY underlying value in futures payload")
    return pd.DataFrame(
        [
            {
                "date": pd.to_datetime(near["date"], format="mixed", dayfirst=True).date().isoformat(),
                "future_expiry": near.expiry.date().isoformat(),
                "future_close": near.close,
                "future_basis_pct": near.close / near.spot - 1,
                "future_oi": near.oi,
                "future_change_oi": near.change_oi,
                "future_volume": near.volume,
                "near_oi_share": near.oi / max(total_oi, 1),
                "next_near_spread_pct": nxt.close / near.close - 1 if nxt is not None else np.nan,
            }
        ]
    )


def summarize_options(data: pd.DataFrame) -> pd.DataFrame:
    from fetch_historical_derivatives import aggregate_options

    out = aggregate_options(data)
    if out.empty:
        raise ValueError("No valid option summary row after schema/date validation")
    return out


def summarize_participant(data: pd.DataFrame, session: str) -> pd.DataFrame:
    q = data.copy()
    q.columns = [str(c).strip() for c in q.columns]
    q["Client Type"] = q["Client Type"].astype(str).str.strip()
    row: dict[str, object] = {"date": session}
    for name in ["FII", "DII", "Client", "Pro"]:
        hit = q[q["Client Type"].str.casefold() == name.casefold()]
        if hit.empty:
            continue
        z = hit.iloc[0]
        prefix = name.lower()
        row[f"{prefix}_index_future_net"] = float(z["Future Index Long"]) - float(z["Future Index Short"])
        row[f"{prefix}_stock_future_net"] = float(z["Future Stock Long"]) - float(z["Future Stock Short"])
        row[f"{prefix}_index_call_net"] = float(z["Option Index Call Long"]) - float(z["Option Index Call Short"])
        row[f"{prefix}_index_put_net"] = float(z["Option Index Put Long"]) - float(z["Option Index Put Short"])
        row[f"{prefix}_index_option_direction"] = row[f"{prefix}_index_call_net"] - row[f"{prefix}_index_put_net"]
        row[f"{prefix}_total_net"] = float(z["Total Long Contracts"]) - float(z["Total Short Contracts"])
    return pd.DataFrame([row])


def truncate_price_history(price: pd.DataFrame, session: str, min_rows: int = 200) -> pd.DataFrame:
    _require_columns(price, {"Date", "Open", "High", "Low", "Close"}, "nifty_price")
    dates = pd.to_datetime(price.Date, errors="coerce").dt.normalize()
    out = price[dates <= pd.Timestamp(session)].copy().sort_values("Date")
    if len(out) < min_rows or pd.to_datetime(out.Date).max().date() != pd.Timestamp(session).date():
        raise ValueError(f"No completed NIFTY candle for requested session {session}")
    return out


def append_history(path: Path | str, row: pd.DataFrame) -> None:
    """Idempotent, atomic history update; a crash cannot leave a half-written CSV."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if row is None or row.empty or "date" not in row:
        raise ValueError(f"Invalid history row for {path}")
    old = pd.read_csv(path) if path.exists() else pd.DataFrame()
    new = pd.concat([old, row], ignore_index=True)
    new = new.drop_duplicates("date", keep="last").sort_values("date")
    tmp = path.with_suffix(path.suffix + ".tmp")
    new.to_csv(tmp, index=False)
    os.replace(tmp, path)


class DataHub:
    def __init__(self, requested: str = "auto"):
        self.requested = requested
        self.now = datetime.now(IST)
        self.run_id = self.now.strftime("%Y%m%d_%H%M%S_%f")
        self.run_dir = ROOT / "runs" / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=False)
        CACHE.mkdir(parents=True, exist_ok=True)
        self.results: list[SourceResult] = []
        self.selected: dict[str, pd.DataFrame] = {}

    def fetch(self, dataset: str, sources, asof_fn, validator=lambda x: len(x) > 0, max_stale: int = 1):
        errors: list[str] = []
        for name, fn in sources:
            started = time.time()
            try:
                data = _retry(fn)
                if not validator(data):
                    raise ValueError(f"{dataset} failed validation from {name}")
                as_of = _asof(asof_fn(data))
                if hasattr(self, "session") and dataset != "cross_market":
                    delta = (pd.Timestamp(self.session) - pd.Timestamp(as_of)).days
                    if delta < 0:
                        raise ValueError(f"future-dated payload {as_of} for session {self.session}")
                    if delta > 0:
                        raise ValueError(f"stale payload {as_of} for session {self.session}")

                path = _save(dataset, name, data, self.run_dir)
                result = SourceResult(
                    dataset,
                    name,
                    "fresh",
                    as_of,
                    len(data),
                    int((time.time() - started) * 1000),
                    str(path.relative_to(PROJECT)),
                    _sha(path),
                )
                self.results.append(result)
                self.selected[dataset] = data

                cache_csv = CACHE / f"{dataset}.csv"
                meta_path = CACHE / f"{dataset}.json"
                meta_errors: list[str] = []
                existing = _safe_json(meta_path, meta_errors, f"{dataset} cache") if meta_path.exists() else None
                if existing is None or pd.Timestamp(as_of) >= pd.Timestamp(existing.get("as_of")):
                    tmp = cache_csv.with_suffix(".csv.tmp")
                    data.to_csv(tmp, index=False)
                    os.replace(tmp, cache_csv)
                    _atomic_text(meta_path, json.dumps({"source": name, "as_of": as_of, "saved": self.now.isoformat()}))
                    result.cache_path = str(cache_csv.relative_to(PROJECT))
                return data
            except Exception as exc:  # noqa: BLE001 - each adapter must fail independently
                errors.append(f"{name}: {exc}")

        cache_csv = CACHE / f"{dataset}.csv"
        meta = CACHE / f"{dataset}.json"
        if cache_csv.exists() and meta.exists():
            meta_errors: list[str] = []
            payload = _safe_json(meta, meta_errors, f"{dataset} cache")
            if payload and payload.get("as_of"):
                stale = None
                if hasattr(self, "session"):
                    cached_date = pd.Timestamp(payload["as_of"]).date()
                    session_date = pd.Timestamp(self.session).date()
                    stale = int(np.busday_count(cached_date, session_date)) if session_date >= cached_date else -1
                # Price is fetched before the canonical session is known. If all live price adapters
                # are blocked, use the last-good price history only to establish/report the latest
                # available completed session; downstream critical gates still require fresh,
                # same-session price/options/futures before any trade can be authorized.
                if stale is None or 0 <= stale <= max_stale:
                    data = pd.read_csv(cache_csv)
                    path = _save(dataset, "last_good_cache", data, self.run_dir)
                    result = SourceResult(
                        dataset,
                        "last_good_cache",
                        "cached",
                        payload["as_of"],
                        len(data),
                        0,
                        str(path.relative_to(PROJECT)),
                        _sha(path),
                        str(cache_csv.relative_to(PROJECT)),
                        "; ".join(errors) if errors else None,
                        stale,
                    )
                    self.results.append(result)
                    self.selected[dataset] = data
                    return data
            errors.extend(meta_errors)

        self.results.append(SourceResult(dataset, "none", "failed", None, 0, 0, error="; ".join(errors)))
        return None

    def run(self):
        from filelock import FileLock

        ROOT.mkdir(parents=True, exist_ok=True)
        with FileLock(str(ROOT / "production.lock"), timeout=5):
            return self._run_unlocked()

    def _run_unlocked(self):
        # Price first determines the most recent completed trading session.
        end = pd.Timestamp(self.now.date() if self.requested == "auto" else self.requested)
        price = self.fetch(
            "nifty_price",
            [
                ("yahoo_yfinance", lambda: yahoo_history()),
                ("nse_index_archive", lambda: nse_index_history(end)),
                ("yahoo_chart", lambda: yahoo_chart("%5ENSEI", end - pd.Timedelta(days=3650), end)),
            ],
            lambda d: pd.to_datetime(d.Date).max(),
            validate_price_history,
            max_stale=4,
        )
        if price is None:
            raise RuntimeError("No valid NIFTY price source or cache")

        self.session = str(pd.to_datetime(price.Date).max().date()) if self.requested == "auto" else str(pd.Timestamp(self.requested).date())
        session = self.session

        # Canonical decision history must end at D; explicit historical reruns may never see later candles.
        price = truncate_price_history(price, session)
        canonical = _save("nifty_price", "canonical_truncated", price, self.run_dir)
        self.selected["nifty_price"] = price
        price_result = next(r for r in reversed(self.results) if r.dataset == "nifty_price")
        price_result.path = str(canonical.relative_to(PROJECT))
        price_result.sha256 = _sha(canonical)
        price_result.rows = len(price)
        price_result.as_of = session

        opt = self.fetch(
            "nifty_options_eod",
            [("nselib_contract_archive", lambda: options_nselib(session)), ("nse_bhavcopy", lambda: bhavcopy_filtered(session, "option"))],
            lambda d: _max_mixed_date(d["TIMESTAMP"]),
            validate_options_payload,
            max_stale=1,
        )
        fut = self.fetch(
            "nifty_futures_eod",
            [("nselib_contract_archive", lambda: futures_nselib(session)), ("nse_bhavcopy", lambda: bhavcopy_filtered(session, "future"))],
            lambda d: _max_mixed_date(d["TIMESTAMP"]),
            validate_futures_payload,
            max_stale=1,
        )
        part = self.fetch(
            "participant_oi",
            [("nselib_participant_archive", lambda: participant_nselib(session)), ("direct_nse_archive", lambda: participant_archive(session))],
            lambda _d: session,
            validate_participant_payload,
            max_stale=1,
        )
        vix = self.fetch(
            "india_vix",
            [("nse_vix_archive", lambda: vix_nse(session)), ("yahoo_vix_chart", lambda: vix_yahoo(session))],
            lambda d: _max_mixed_date(d["TIMESTAMP"]) if "TIMESTAMP" in d else _max_mixed_date(d["Date"]),
            validate_vix_payload,
            max_stale=1,
        )
        cash = self.fetch(
            "fii_dii_cash",
            [("nse_fiidii_api", lambda: fii_cash_nse(session)), ("groww_public_table", lambda: fii_cash_groww(session))],
            lambda d: pd.to_datetime(d["date"], format="mixed", dayfirst=True, errors="coerce").max(),
            validate_cash_payload,
            max_stale=1,
        )
        cross = self.fetch(
            "cross_market",
            [("yfinance_multi_asset", lambda: cross_yfinance(session)), ("yahoo_chart_multi_asset", lambda: cross_yahoo_chart(session))],
            lambda _d: session,
            validate_cross_market_payload,
            max_stale=1,
        )
        _ = (vix, cash, cross)  # fetched for health/provenance even when not used by the current model

        # Update compact historical feature stores only with validated rows whose own as-of
        # date matches the canonical session. This prevents stale cache rows from being
        # re-labeled as a newer session during provider outages.
        history_update_ok = True
        update_jobs = [
            ("nifty_options_eod", opt, lambda d: append_history(PROJECT / "data" / "historical_option_features.csv", summarize_options(d))),
            ("nifty_futures_eod", fut, lambda d: append_history(PROJECT / "data" / "historical_futures_features.csv", summarize_futures(d))),
            ("participant_oi", part, lambda d: append_history(PROJECT / "data" / "historical_participant_oi.csv", summarize_participant(d, session))),
        ]
        for dataset, frame, updater in update_jobs:
            result = next((x for x in reversed(self.results) if x.dataset == dataset), None)
            if frame is None or result is None or result.as_of != session:
                continue
            try:
                updater(frame)
            except Exception as exc:  # noqa: BLE001 - fail closed but keep reportable manifest
                history_update_ok = False
                self.results.append(SourceResult("history_update", dataset, "failed", session, 0, 0, error=str(exc)))

        weights = {
            "nifty_price": 0.25,
            "nifty_options_eod": 0.20,
            "nifty_futures_eod": 0.15,
            "participant_oi": 0.15,
            "india_vix": 0.10,
            "fii_dii_cash": 0.05,
            "cross_market": 0.10,
        }
        score = 0.0
        for dataset, weight in weights.items():
            result = next((x for x in reversed(self.results) if x.dataset == dataset), None)
            score += weight * (1 if result and result.status == "fresh" else 0.6 if result and result.status == "cached" else 0)

        # Never trade D+1 using D-1 cached price/option/futures structure.
        critical = all(
            any(r.dataset == dataset and r.status == "fresh" and r.as_of == session for r in self.results)
            for dataset in ["nifty_price", "nifty_options_eod", "nifty_futures_eod"]
        )
        manifest = {
            "run_id": self.run_id,
            "requested_date": self.requested,
            "session_date": session,
            "decision_ist": self.now.isoformat(),
            "quality_score": round(score, 3),
            "critical_data_fresh": critical,
            "history_update_ok": history_update_ok,
            "prediction_allowed": bool(score >= 0.75 and critical and history_update_ok),
            "results": [asdict(r) for r in self.results],
        }
        manifest_path = self.run_dir / "manifest.json"
        payload = json.dumps(manifest, indent=2)
        _atomic_text(manifest_path, payload)
        _atomic_text(ROOT / "latest_manifest.json", payload)
        return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--date", default="auto")
    args = parser.parse_args()
    print(json.dumps(DataHub(args.date).run(), indent=2))


if __name__ == "__main__":
    main()
