from __future__ import annotations
import numpy as np
import pandas as pd
from .technical_indicators import technical_features

INDIA={'bank':'^NSEBANK','it':'^CNXIT','sensex':'^BSESN','india_vix':'^INDIAVIX'}
GLOBAL={'spy':'SPY','qqq':'QQQ','us_vix':'^VIX','dollar':'DX-Y.NYB','crude':'CL=F','gold':'GC=F','usdinr':'USDINR=X'}

def _download(ticker,period='10y'):
 import yfinance as yf
 d=yf.download(ticker,period=period,interval='1d',auto_adjust=False,progress=False,threads=False)
 if isinstance(d.columns,pd.MultiIndex):d.columns=d.columns.get_level_values(0)
 d.index=pd.to_datetime(d.index).tz_localize(None).normalize()
 return d[['Open','High','Low','Close','Volume']].dropna(subset=['Close'])

def multi_asset_technical(nifty:pd.DataFrame,period='10y')->pd.DataFrame:
    """Indicators aligned to NIFTY dates. Global features are shifted one NIFTY session."""
    out=technical_features(nifty,'nifty');idx=nifty.index
    for name,ticker in {**INDIA,**GLOBAL}.items():
        d=_download(ticker,period); aligned=d.reindex(idx).ffill()
        f=technical_features(aligned,name)
        if name in GLOBAL:f=f.shift(1)  # same-date global candle may be unknown at India D close/9 PM
        # External assets use a compact stable subset to limit dimensionality.
        keep=[c for c in f if any(k in c for k in ['ret_1','ret_5','ret_20','rsi_14','sma_dist_20','sma_dist_50','realized_vol_20','atr_14','macd_hist','boll_z','adx14','trend_strength','range_location_20'])]
        out=out.join(f[keep])
    return out.replace([np.inf,-np.inf],np.nan)
