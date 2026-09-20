from __future__ import annotations

from pathlib import Path
import pandas as pd

DEFAULT_TICKER = "^NSEI"


def download_ohlcv(ticker: str = DEFAULT_TICKER, period: str = "10y") -> pd.DataFrame:
    """Download completed daily candles. Current incomplete session is removed."""
    import yfinance as yf

    raw = yf.download(ticker, period=period, interval="1d", auto_adjust=False,
                      progress=False, threads=False)
    if raw.empty:
        raise RuntimeError("No market data returned. Check internet/ticker.")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    needed = ["Open", "High", "Low", "Close", "Volume"]
    out = raw[needed].dropna(subset=["Open", "High", "Low", "Close"]).copy()
    out.index = pd.to_datetime(out.index).tz_localize(None)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out


def load_csv(path_or_buffer) -> pd.DataFrame:
    df = pd.read_csv(path_or_buffer)
    lower = {str(c).lower().strip(): c for c in df.columns}
    date_col = lower.get("date") or lower.get("datetime")
    if not date_col:
        raise ValueError("CSV needs a Date column.")
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).set_index(date_col).sort_index()
    rename = {c: str(c).strip().title() for c in df.columns}
    df = df.rename(columns=rename)
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    return df[list(required)].astype(float)


def merge_context(price: pd.DataFrame, context: pd.DataFrame | None) -> pd.DataFrame:
    """Left join dated information known by each market close (no backward fill)."""
    if context is None or context.empty:
        return price.copy()
    ctx = context.copy()
    ctx.index = pd.to_datetime(ctx.index).tz_localize(None).normalize()
    numeric = ctx.select_dtypes(include="number").add_prefix("ctx_")
    return price.join(numeric, how="left")
