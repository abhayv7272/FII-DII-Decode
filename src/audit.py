from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score
from .advanced_model import advanced_features, _models

WEIGHTS=np.array([.10,.35,.35,.20])

def strict_gate(y,p,target,min_signals=25):
    pred=(p>=.5).astype(int); conf=np.maximum(p,1-p)
    for g in np.arange(.50,.851,.01):
        m=conf>=g
        if m.sum()>=min_signals and (pred[m]==y[m]).mean()>=target:
            return float(g),int(m.sum()),float((pred[m]==y[m]).mean()),float(m.mean())
    return None

def max_drawdown(equity):
    if len(equity)==0:return np.nan
    equity=np.r_[1.0,np.asarray(equity)];peak=np.maximum.accumulate(equity); return float(np.min(equity/peak-1))

def regime_stats(frame):
    out={}
    for col in ['trend_regime','vol_regime']:
        for regime,g in frame.groupby(col):
            if not len(g):continue
            out[f'{col}:{regime}']={'sessions':len(g),'signals':int(g.selected.sum()),
              'coverage':float(g.selected.mean()),'all_accuracy':float(g.correct.mean()),
              'selected_accuracy':float(g.loc[g.selected,'correct'].mean()) if g.selected.any() else None}
    return out

def walk_forward_audit(price:pd.DataFrame,target=.75,cal_size=250,test_size=250,min_train=900,min_signals=25,costs_bps=(3,6,10)):
    X=advanced_features(price)
    # Executable decision: at D close/9 PM, enter D+1 open and exit D+1 close.
    trade_ret=price.Close.shift(-1)/price.Open.shift(-1)-1
    y=(trade_ret>0).astype(float); y[trade_ret.isna()]=np.nan
    vol=price.Close.pct_change().rolling(20).std()*np.sqrt(252)
    expanding_median=vol.expanding(252).median().shift(1)
    sma200=price.Close.rolling(200).mean()
    base=X.join(pd.DataFrame({'y':y,'trade_return':trade_ret,
      'trend_regime':np.where(price.Close>=sma200,'BULL','BEAR'),
      'vol_regime':np.where(vol>=expanding_median,'HIGH_VOL','LOW_VOL')})).dropna(subset=['y'])
    cols=list(X.columns); starts=list(range(min_train+cal_size,len(base),test_size)); rows=[]; fold_meta=[]
    for fold,start in enumerate(starts,1):
        end=min(start+test_size,len(base)); train=base.iloc[:start-cal_size]; cal=base.iloc[start-cal_size:start]; test=base.iloc[start:end]
        if len(test)<50:continue
        cp=[];tp=[]
        for m in _models():
            m.fit(train[cols],train.y.astype(int)); cp.append(m.predict_proba(cal[cols])[:,1]);tp.append(m.predict_proba(test[cols])[:,1])
        cp=np.average(np.vstack(cp),axis=0,weights=WEIGHTS);tp=np.average(np.vstack(tp),axis=0,weights=WEIGHTS)
        gate=strict_gate(cal.y.to_numpy(int),cp,target,min_signals)
        pred=(tp>=.5).astype(int);conf=np.maximum(tp,1-tp)
        selected=np.zeros(len(test),dtype=bool) if gate is None else conf>=gate[0]
        for i,(idx,r) in enumerate(test.iterrows()):
            direction=1 if pred[i]==1 else -1; gross=direction*float(r.trade_return)
            rows.append({'date':idx,'fold':fold,'actual':'UP' if r.y==1 else 'DOWN','prediction':'UP' if pred[i]==1 else 'DOWN',
              'confidence':conf[i],'gate':None if gate is None else gate[0],'selected':bool(selected[i]),'correct':bool(pred[i]==r.y),
              'gross_return':gross if selected[i] else 0.0,'trend_regime':r.trend_regime,'vol_regime':r.vol_regime})
        fold_meta.append({'fold':fold,'train':len(train),'calibration':len(cal),'test':len(test),'test_start':str(test.index[0].date()),
          'test_end':str(test.index[-1].date()),'gate':None if gate is None else gate[0],
          'calibration_selected_signals':0 if gate is None else gate[1], 'calibration_selected_accuracy':None if gate is None else gate[2],
          'test_signals':int(selected.sum()),'test_selected_accuracy':float((pred[selected]==test.y.to_numpy(int)[selected]).mean()) if selected.any() else None})
    f=pd.DataFrame(rows).set_index('date'); sel=f[f.selected]
    summary={'target':target,'folds':len(fold_meta),'test_sessions':len(f),'selected_signals':len(sel),'coverage':float(f.selected.mean()) if len(f) else 0,
      'all_accuracy':float(f.correct.mean()) if len(f) else None,'selected_accuracy':float(sel.correct.mean()) if len(sel) else None,
      'folds_with_gate':sum(x['gate'] is not None for x in fold_meta),'minimum_calibration_signals':min_signals,'fold_details':fold_meta,
      'regimes':regime_stats(f),'cost_stress':{}}
    for bps in costs_bps:
        net=sel.gross_return-bps/10000
        equity=(1+net).cumprod()
        summary['cost_stress'][str(bps)]={'trades':len(net),'gross_total_return':float((1+sel.gross_return).prod()-1) if len(sel) else 0,
          'net_total_return':float(equity.iloc[-1]-1) if len(equity) else 0,'average_net_trade':float(net.mean()) if len(net) else None,
          'win_rate_after_cost':float((net>0).mean()) if len(net) else None,'max_drawdown':max_drawdown(equity.to_numpy())}
    return summary,f

def save_audit(price,outdir='reports'):
    out=Path(outdir);out.mkdir(parents=True,exist_ok=True); reports={}
    for target in [.65,.70,.75]:
        s,f=walk_forward_audit(price,target=target);reports[str(target)]=s;f.to_csv(out/f'walk_forward_{int(target*100)}.csv')
    (out/'strict_audit.json').write_text(json.dumps(reports,indent=2,default=str))
    return reports
