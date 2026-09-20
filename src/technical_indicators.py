from __future__ import annotations
import numpy as np
import pandas as pd


def _div(a,b): return a/b.replace(0,np.nan)
def _rsi(c,n=14):
 d=c.diff();up=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean();dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
 return 100-100/(1+_div(up,dn))
def _true_range(h,l,c): return pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
def _adx(h,l,c,n=14):
 up=h.diff();down=-l.diff();plus=pd.Series(np.where((up>down)&(up>0),up,0),index=h.index);minus=pd.Series(np.where((down>up)&(down>0),down,0),index=h.index)
 atr=_true_range(h,l,c).ewm(alpha=1/n,adjust=False).mean();pdi=100*_div(plus.ewm(alpha=1/n,adjust=False).mean(),atr);mdi=100*_div(minus.ewm(alpha=1/n,adjust=False).mean(),atr)
 return 100*_div((pdi-mdi).abs(),pdi+mdi),pdi,mdi

def technical_features(df:pd.DataFrame,prefix='')->pd.DataFrame:
    """Broad but leakage-safe indicators; row t depends only on bars through t."""
    p=(prefix+'_' if prefix else '')
    o,h,l,c=[pd.to_numeric(df[k],errors='coerce') for k in ['Open','High','Low','Close']]
    v=pd.to_numeric(df['Volume'],errors='coerce') if 'Volume' in df else pd.Series(0.,index=df.index)
    x=pd.DataFrame(index=df.index); ret=c.pct_change();tr=_true_range(h,l,c)
    for n in [2,3,5,10,14,20,50,100,200]:
        x[f'{p}ret_{n}']=c.pct_change(n);ma=c.rolling(n).mean();ema=c.ewm(span=n,adjust=False).mean()
        x[f'{p}sma_dist_{n}']=c/ma-1;x[f'{p}ema_dist_{n}']=c/ema-1
    for n in [5,10,14,20,60]:
        x[f'{p}rsi_{n}']=_rsi(c,n)/100;x[f'{p}roc_{n}']=c.pct_change(n)
        x[f'{p}realized_vol_{n}']=ret.rolling(n).std()*np.sqrt(252)
        x[f'{p}atr_{n}']=tr.rolling(n).mean()/c
        lo=l.rolling(n).min();hi=h.rolling(n).max();x[f'{p}stoch_{n}']=_div(c-lo,hi-lo)
        x[f'{p}williams_r_{n}']=-_div(hi-c,hi-lo)
    ema12=c.ewm(span=12,adjust=False).mean();ema26=c.ewm(span=26,adjust=False).mean();macd=(ema12-ema26)/c;sig=macd.ewm(span=9,adjust=False).mean()
    x[f'{p}macd']=macd;x[f'{p}macd_signal']=sig;x[f'{p}macd_hist']=macd-sig
    mid=c.rolling(20).mean();sd=c.rolling(20).std();x[f'{p}boll_z']=_div(c-mid,sd);x[f'{p}boll_width']=_div(4*sd,mid)
    typical=(h+l+c)/3;md=(typical-typical.rolling(20).mean()).abs().rolling(20).mean();x[f'{p}cci20']=_div(typical-typical.rolling(20).mean(),.015*md)/200
    adx,pdi,mdi=_adx(h,l,c);x[f'{p}adx14']=adx/100;x[f'{p}plus_di14']=pdi/100;x[f'{p}minus_di14']=mdi/100
    x[f'{p}gap']=o/c.shift()-1;x[f'{p}body']=(c-o)/o;x[f'{p}range']=tr/c.shift();x[f'{p}close_location']=_div(c-l,h-l)
    x[f'{p}upper_wick']=_div(h-pd.concat([o,c],axis=1).max(axis=1),c);x[f'{p}lower_wick']=_div(pd.concat([o,c],axis=1).min(axis=1)-l,c)
    x[f'{p}parkinson_vol20']=np.sqrt((np.log(_div(h,l))**2).rolling(20).mean()/(4*np.log(2))*252)
    x[f'{p}downside_vol20']=ret.where(ret<0,0).rolling(20).std()*np.sqrt(252);x[f'{p}upside_vol20']=ret.where(ret>0,0).rolling(20).std()*np.sqrt(252)
    if (v.fillna(0)>0).sum()>20:
        sign=np.sign(c.diff()).fillna(0);obv=(sign*v).cumsum();x[f'{p}obv_slope20']=obv.pct_change(20).replace([np.inf,-np.inf],np.nan)
        mf=typical*v;pos=mf.where(typical.diff()>0,0).rolling(14).sum();neg=mf.where(typical.diff()<0,0).rolling(14).sum();x[f'{p}mfi14']=100-100/(1+_div(pos,neg));x[f'{p}mfi14']/=100
        mult=_div((c-l)-(h-c),h-l);x[f'{p}cmf20']=(mult*v).rolling(20).sum()/v.rolling(20).sum().replace(0,np.nan)
        x[f'{p}volume_z20']=(v-v.rolling(20).mean())/v.rolling(20).std().replace(0,np.nan)
    for n in [5,20,60]:
        hi=h.rolling(n).max();lo=l.rolling(n).min();x[f'{p}range_location_{n}']=_div(c-lo,hi-lo)
        x[f'{p}distance_high_{n}']=c/hi-1;x[f'{p}distance_low_{n}']=c/lo-1
    x[f'{p}trend_strength']=x[f'{p}adx14']*np.sign(x[f'{p}sma_dist_50'])
    return x.replace([np.inf,-np.inf],np.nan)


def prune_correlated(train:pd.DataFrame,threshold=.97,min_non_null=.60)->list[str]:
    """Fit feature pruning on training data only; no target is inspected."""
    cols=[c for c in train if train[c].notna().mean()>=min_non_null and train[c].nunique(dropna=True)>2]
    if not cols:return []
    corr=train[cols].corr().abs();upper=corr.where(np.triu(np.ones(corr.shape),k=1).astype(bool));drop={c for c in upper.columns if (upper[c]>threshold).any()}
    return [c for c in cols if c not in drop]
