"""Local persistence for daily datasets + history loading.

Everything is stored as plain CSV/JSON under the data/ directory so the
history can be committed (small) and analysed over rolling windows.

Layout:
  data/participant_oi.csv      # appended daily, one block of rows per date
  data/participant_vol.csv
  data/fii_dii_cash.csv
  data/option_chain/<SYMBOL>_<DATE>.json
  data/decoded.csv             # decoded metrics per date (the "signal" history)
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

DATA_DIR = Path(os.environ.get("FIIDII_DATA_DIR", "data"))


def _ensure() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "option_chain").mkdir(parents=True, exist_ok=True)


def append_df(df: pd.DataFrame, name: str, dedup_on: Optional[list[str]] = None) -> None:
    """Append a dataframe to data/<name>.csv, de-duplicating on given columns."""
    _ensure()
    path = DATA_DIR / f"{name}.csv"
    if path.exists():
        existing = pd.read_csv(path)
        combined = pd.concat([existing, df], ignore_index=True)
    else:
        combined = df.copy()
    if dedup_on:
        combined = combined.drop_duplicates(subset=dedup_on, keep="last")
    combined.to_csv(path, index=False)


def load_df(name: str) -> pd.DataFrame:
    path = DATA_DIR / f"{name}.csv"
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def save_option_chain(raw: dict, symbol: str, d: date) -> Path:
    _ensure()
    path = DATA_DIR / "option_chain" / f"{symbol}_{d.isoformat()}.json"
    path.write_text(json.dumps(raw))
    return path


def load_option_chain(symbol: str, d: date) -> Optional[dict]:
    path = DATA_DIR / "option_chain" / f"{symbol}_{d.isoformat()}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def save_json(obj: dict, name: str) -> Path:
    _ensure()
    path = DATA_DIR / f"{name}.json"
    path.write_text(json.dumps(obj, indent=2, default=str))
    return path
