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
    # Normalise the participant label column name.
    for cand in ("Client Type", "ClientType", "Client_Type"):
        if cand in df.columns:
            df = df.rename(columns={cand: "ClientType"})
            break
    if "ClientType" in df.columns:
        df["ClientType"] = df["ClientType"].astype(str).str.strip()
        df = df[df["ClientType"].str.upper().isin(["CLIENT", "DII", "FII", "PRO", "TOTAL"])]
    # Coerce numeric columns.
    for c in df.columns:
        if c != "ClientType":
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
    """Spot / index level and change."""
    url = f"{BASE}/api/allIndices"
    try:
        data = client.get_json(url, referer=BASE + "/")
        for row in data.get("data", []):
            if row.get("index", "").upper() == symbol.upper():
                return row
    except RuntimeError as exc:
        log.warning("index quote fetch failed: %s", exc)
    return None
