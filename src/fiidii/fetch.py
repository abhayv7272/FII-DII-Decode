"""High-level daily data collectors built on NseClient.

Provides:
  - fetch_participant_oi(date)   -> DataFrame (Client/DII/FII/Pro long/short by segment)
  - fetch_participant_vol(date)  -> DataFrame (participant-wise trading volume)
  - fetch_fii_dii_cash()         -> dict     (FII/DII cash provisional buy/sell/net)
  - fetch_option_chain(symbol)   -> dict     (raw option-chain JSON, indices)

All raw payloads are returned as close to source as possible so the decode
layer can compute derived metrics deterministically.
"""
from __future__ import annotations

import io
import logging
from datetime import date, datetime
from typing import Optional

import pandas as pd

from .nse import NseClient, ARCHIVES, BASE

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Participant-wise Open Interest (the core "who is positioned how" dataset)
# --------------------------------------------------------------------------- #
def _fao_participant_oi_url(d: date) -> str:
    return f"{ARCHIVES}/content/nsccl/fao_participant_oi_{d:%d%m%Y}.csv"


def _fao_participant_vol_url(d: date) -> str:
    return f"{ARCHIVES}/content/nsccl/fao_participant_vol_{d:%d%m%Y}.csv"


def _parse_participant_csv(text: str) -> pd.DataFrame:
    """The NSE participant CSV has a title line then a header row. Find it robustly."""
    lines = text.splitlines()
    header_idx = 0
    for i, ln in enumerate(lines):
        low = ln.lower()
        if "client type" in low or ("future index long" in low):
            header_idx = i
            break
    df = pd.read_csv(io.StringIO("\n".join(lines[header_idx:])))
    df.columns = [c.strip() for c in df.columns]
    # Some archived files contain an empty trailing header (and one known source
    # row contains an extra unnamed aggregate). It is not a decoder input.
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed:")]
    # Normalise participant/date labels. Preserving a date column lets the same
    # parser consume the consolidated data/participant_oi.csv history as well as
    # NSE's one-file-per-day archives.
    normalised = {c.lower().replace(" ", "").replace("_", ""): c for c in df.columns}
    if "clienttype" in normalised:
        df = df.rename(columns={normalised["clienttype"]: "ClientType"})
    if "date" in normalised and normalised["date"] != "date":
        df = df.rename(columns={normalised["date"]: "date"})
    if "ClientType" in df.columns:
        df["ClientType"] = df["ClientType"].astype(str).str.strip()
        df = df[df["ClientType"].str.upper().isin(["CLIENT", "DII", "FII", "PRO", "TOTAL"])]
    # Coerce only position columns. A consolidated history's ISO date must not be
    # turned into NaN by numeric conversion.
    for c in df.columns:
        if c not in ("ClientType", "date"):
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "", regex=False),
                                  errors="coerce")
    return df.reset_index(drop=True)


def fetch_participant_oi(client: NseClient, d: date) -> Optional[pd.DataFrame]:
    """Participant-wise OI for a given trading date. Returns None if not published yet."""
    url = _fao_participant_oi_url(d)
    try:
        text = client.get_text(url, referer=BASE + "/all-reports-derivatives")
    except RuntimeError as exc:
        log.warning("participant OI not available for %s: %s", d, exc)
        return None
    if "<html" in text.lower():
        return None
    df = _parse_participant_csv(text)
    df["date"] = d.isoformat()
    return df


def fetch_participant_vol(client: NseClient, d: date) -> Optional[pd.DataFrame]:
    url = _fao_participant_vol_url(d)
    try:
        text = client.get_text(url, referer=BASE + "/all-reports-derivatives")
    except RuntimeError as exc:
        log.warning("participant vol not available for %s: %s", d, exc)
        return None
    if "<html" in text.lower():
        return None
    df = _parse_participant_csv(text)
    df["date"] = d.isoformat()
    return df


# --------------------------------------------------------------------------- #
# FII / DII cash market provisional figures
# --------------------------------------------------------------------------- #
def fetch_fii_dii_cash(client: NseClient) -> Optional[list[dict]]:
    """FII/DII cash provisional buy/sell/net (today's provisional numbers)."""
    url = BASE + "/api/fiidiiTradeReact"
    try:
        data = client.get_json(url, referer=BASE + "/reports-indices-historical-index-data")
        return data
    except RuntimeError as exc:
        log.warning("FII/DII cash fetch failed: %s", exc)
        return None


# --------------------------------------------------------------------------- #
# Option chain (indices: NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY)
# --------------------------------------------------------------------------- #
def fetch_option_chain(client: NseClient, symbol: str = "NIFTY") -> Optional[dict]:
    url = f"{BASE}/api/option-chain-indices?symbol={symbol}"
    try:
        return client.get_json(url, referer=BASE + "/option-chain")
    except RuntimeError as exc:
        log.warning("option chain fetch failed for %s: %s", symbol, exc)
        return None


def fetch_index_quote(client: NseClient, symbol: str = "NIFTY 50") -> Optional[dict]:
    """Current daily index quote, including OHLC when supplied by NSE.

    Option-chain symbols and the all-indices API use different spellings (for
    example NIFTY vs NIFTY 50), so match their common aliases explicitly.
    """
    def norm(value: str) -> str:
        return "".join(ch for ch in str(value).upper() if ch.isalnum())

    aliases = {
        "NIFTY": {"NIFTY", "NIFTY50"},
        "NIFTY50": {"NIFTY", "NIFTY50"},
        "BANKNIFTY": {"BANKNIFTY", "NIFTYBANK"},
        "NIFTYBANK": {"BANKNIFTY", "NIFTYBANK"},
        "FINNIFTY": {"FINNIFTY", "NIFTYFINANCIALSERVICES"},
        "MIDCPNIFTY": {"MIDCPNIFTY", "NIFTYMIDSELECT"},
    }
    wanted = aliases.get(norm(symbol), {norm(symbol)})
    url = f"{BASE}/api/allIndices"
    try:
        data = client.get_json(url, referer=BASE + "/")
        for row in data.get("data", []):
            if norm(row.get("index", "")) in wanted:
                return row
    except RuntimeError as exc:
        log.warning("index quote failed: %s", exc)
    return None
