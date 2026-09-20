import pandas as pd


def technical_levels(df: pd.DataFrame) -> dict:
    """Levels for D+1 computed from the latest completed D candle."""
    if len(df) < 20:
        raise ValueError("At least 20 completed candles are required for levels.")
    last = df.iloc[-1]
    pivot = (last.High + last.Low + last.Close) / 3
    atr = pd.concat([(df.High-df.Low), (df.High-df.Close.shift()).abs(),
                     (df.Low-df.Close.shift()).abs()], axis=1).max(axis=1).rolling(14).mean().iloc[-1]
    return {
        "pivot": pivot, "support_1": 2*pivot-last.High, "resistance_1": 2*pivot-last.Low,
        "support_20d": df.Low.tail(20).min(), "resistance_20d": df.High.tail(20).max(),
        "atr14_points": atr, "previous_close": last.Close,
    }


def tiny_gap(open_price: float, prior_close: float, threshold=.0015) -> dict:
    gap = open_price / prior_close - 1
    return {"active": abs(gap) <= threshold, "gap_pct": gap*100, "magnet": prior_close}
