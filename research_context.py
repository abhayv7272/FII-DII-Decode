from __future__ import annotations
import numpy as np, pandas as pd, yfinance as yf
from sklearn.metrics import accuracy_score, balanced_accuracy_score
from src.data import download_ohlcv
from src.advanced_model import advanced_features, _models, _choose_gate

INDIAN=['^NSEBANK','^CNXIT','^INDIAVIX','^BSESN']
GLOBAL=['SPY','QQQ','^VIX','CL=F','GC=F','USDINR=X']

def close(t):
 d=yf.download(t,period='10y',interval='1d',auto_adjust=False,progress=False,threads=False)
 if isinstance(d.columns,pd.MultiIndex): d.columns=d.columns.get_level_values(0)
 s=d.Close.copy(); s.index=pd.to_datetime(s.index).tz_localize(None); return s

def contextual(price):
 x=advanced_features(price); idx=price.index
 for t in INDIAN+GLOBAL:
  s=close(t).reindex(idx).ffill(); r=s.pct_change()
  safe_shift=1 if t in GLOBAL else 0
  key=t.replace('^','').replace('=','_').replace('-','_')
  for n in [1,5,20]: x[f'{key}_ret{n}']=s.pct_change(n).shift(safe_shift)
  x[f'{key}_vol10']=r.rolling(10).std().shift(safe_shift)
  x[f'{key}_z20']=((s-s.rolling(20).mean())/s.rolling(20).std()).shift(safe_shift)
 return x.replace([np.inf,-np.inf],np.nan)

def run():
 p=download_ohlcv('^NSEI','10y'); X=contextual(p); nr=p.Close.shift(-1)/p.Close-1
 y=(nr>0).astype(float); y[nr.isna()]=np.nan; d=X.join(y.rename('y')).dropna(subset=['y']); cols=list(X.columns)
 a=int(len(d)*.60); b=int(len(d)*.80); tr,cal,te=d.iloc[:a],d.iloc[a:b],d.iloc[b:]
 weights=np.array([.1,.35,.35,.2]); cp=[];tp=[]
 for m in _models():
  m.fit(tr[cols],tr.y.astype(int));cp.append(m.predict_proba(cal[cols])[:,1]);tp.append(m.predict_proba(te[cols])[:,1])
 cp=np.average(np.vstack(cp),axis=0,weights=weights);tp=np.average(np.vstack(tp),axis=0,weights=weights)
 for target in [.65,.70,.75]:
  cpr=(cp>=.5).astype(int); gate=_choose_gate(cal.y.to_numpy(int),cpr,np.maximum(cp,1-cp),target,max(20,len(cal)//20))
  tpr=(tp>=.5).astype(int); sel=np.maximum(tp,1-tp)>=gate[2]
  print({'target':target,'gate':gate,'test_all':accuracy_score(te.y,tpr),'test_bal':balanced_accuracy_score(te.y,tpr),
   'test_sel_acc':accuracy_score(te.y[sel],tpr[sel]) if sel.any() else None,'coverage':float(sel.mean()),'n':int(sel.sum())})
if __name__=='__main__':run()
