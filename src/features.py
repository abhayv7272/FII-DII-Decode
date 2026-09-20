from __future__ import annotations
import numpy as np
import pandas as pd


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    gain = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    loss = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100 / (1 + gain / loss.replace(0, np.nan))


def make_features(df: pd.DataFrame) -> pd.DataFrame:
    """All row-t features use information available at/after t close only."""
    x = pd.DataFrame(index=df.index)
    o, h, l, c, v = (df[k].astype(float) for k in ["Open", "High", "Low", "Close", "Volume"])
    ret = c.pct_change()
    for lag in [1, 2, 3, 5, 10, 20]:
        x[f"ret_{lag}"] = c.pct_change(lag)
    x["gap"] = o / c.shift(1) - 1
    x["range"] = (h - l) / c.shift(1)
    x["body"] = (c - o) / o
    x["close_location"] = (c - l) / (h - l).replace(0, np.nan)
    x["rsi14"] = _rsi(c) / 100
    for n in [5, 10, 20, 50, 100, 200]:
        x[f"sma_dist_{n}"] = c / c.rolling(n).mean() - 1
    for n in [5, 10, 20, 60]:
        x[f"vol_{n}"] = ret.rolling(n).std() * np.sqrt(252)
    x["atr14"] = pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1).rolling(14).mean() / c
    x["volume_z20"] = (v - v.rolling(20).mean()) / v.rolling(20).std().replace(0, np.nan)
    x["dow"] = x.index.dayofweek / 4
    x["month"] = x.index.month / 12
    # Optional numeric context is lagged zero times because its row must represent data known by t close.
    for col in df.columns:
        if str(col).startswith("ctx_"):
            x[col] = pd.to_numeric(df[col], errors="coerce")
    return x.replace([np.inf, -np.inf], np.nan)


def make_labels(df: pd.DataFrame, flat_threshold: float = 0.0025):
    next_ret = df["Close"].shift(-1) / df["Close"] - 1
    y = pd.Series(1, index=df.index, name="target", dtype=float)  # 0 down, 1 flat, 2 up
    y[next_ret < -flat_threshold] = 0
    y[next_ret > flat_threshold] = 2
    y[next_ret.isna()] = np.nan
    return y, next_ret.rename("next_return")
