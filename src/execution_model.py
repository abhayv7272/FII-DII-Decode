from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score,balanced_accuracy_score
from .advanced_model import advanced_features,_models

WEIGHTS=np.array([.10,.35,.35,.20])

@dataclass
class ExecutionAudit:
    summary:dict
    predictions:pd.DataFrame
    latest:dict


def _base_prob(models,X):
    probs=np.vstack([m.predict_proba(X)[:,1] for m in models])
    return np.average(probs,axis=0,weights=WEIGHTS),probs

def _meta_frame(p,member_probs,X):
    out=pd.DataFrame(index=X.index)
    out['p_up']=p;out['confidence']=np.maximum(p,1-p);out['dispersion']=member_probs.std(axis=0)
    out['agreement']=np.mean((member_probs>=.5)==(p>=.5),axis=0)
    for c in ['atr14','rsi14','vol_20','sma_dist_20','sma_dist_50','gap','close_location','dow']:
        out[c]=pd.to_numeric(X[c],errors='coerce') if c in X else 0
    out['trend_bull']=(out.get('sma_dist_50',0)>=0).astype(int)
    # Threshold is based on past feature distribution only when model is used live; here raw vol remains continuous.
    return out

def _strict_gate(y,p,target=.70,min_signals=20):
    for g in np.arange(.50,.91,.01):
        m=p>=g
        if m.sum()>=min_signals and float(y[m].mean())>=target:return float(g),int(m.sum()),float(y[m].mean())
    return None

def _max_dd(ret):
    if not len(ret):return None
    eq=np.r_[1.0,np.cumprod(1+np.asarray(ret))];peak=np.maximum.accumulate(eq);return float(np.min(eq/peak-1))

def audit_execution_model(price:pd.DataFrame,target_precision=.70,cost_bps=(3,6,10))->ExecutionAudit:
    """Strict 60/10/10/20 chronology. Tradable label is D+1 open-to-close."""
    X=advanced_features(price)
    overnight=price.Open.shift(-1)/price.Close-1
    intraday=price.Close.shift(-1)/price.Open.shift(-1)-1
    y=(intraday>0).astype(float);y[intraday.isna()]=np.nan
    d=X.join(pd.DataFrame({'y':y,'intraday_return':intraday,'overnight_return':overnight})).dropna(subset=['y'])
    n=len(d);i1=int(n*.60);i2=int(n*.70);i3=int(n*.80)
    tr,meta,gate,test=d.iloc[:i1],d.iloc[i1:i2],d.iloc[i2:i3],d.iloc[i3:]
    cols=list(X.columns);models=_models()
    for m in models:m.fit(tr[cols],tr.y.astype(int))
    mp,mm=_base_prob(models,meta[cols]);gp,gm=_base_prob(models,gate[cols]);tp,tm=_base_prob(models,test[cols])
    metaX=_meta_frame(mp,mm,meta[cols]);gateX=_meta_frame(gp,gm,gate[cols]);testX=_meta_frame(tp,tm,test[cols])
    meta_correct=((mp>=.5).astype(int)==meta.y.to_numpy(int)).astype(int)
    meta_model=Pipeline([('imp',SimpleImputer(strategy='median')),('m',RandomForestClassifier(n_estimators=500,min_samples_leaf=10,max_features=.8,class_weight='balanced',random_state=42,n_jobs=-1))])
    meta_model.fit(metaX,meta_correct)
    gate_quality=meta_model.predict_proba(gateX)[:,list(meta_model.classes_).index(1)]
    gate_correct=((gp>=.5).astype(int)==gate.y.to_numpy(int)).astype(int)
    chosen=_strict_gate(gate_correct,gate_quality,target_precision,max(15,len(gate)//10))
    test_quality=meta_model.predict_proba(testX)[:,list(meta_model.classes_).index(1)]
    selected=np.zeros(len(test),dtype=bool) if chosen is None else test_quality>=chosen[0]
    pred=(tp>=.5).astype(int);actual=test.y.to_numpy(int);direction=np.where(pred==1,1,-1);gross=direction*test.intraday_return.to_numpy()
    # Regimes known on D.
    vol=pd.to_numeric(testX.get('vol_20',0),errors='coerce');vol_cut=pd.to_numeric(metaX.get('vol_20',0),errors='coerce').median()
    out=pd.DataFrame({'actual':np.where(actual==1,'UP','DOWN'),'prediction':np.where(pred==1,'UP','DOWN'),'direction_confidence':np.maximum(tp,1-tp),
      'meta_quality':test_quality,'selected':selected,'correct':pred==actual,'gross_return':np.where(selected,gross,0),
      'trend_regime':np.where(testX.trend_bull==1,'BULL','BEAR'),'vol_regime':np.where(vol>=vol_cut,'HIGH_VOL','LOW_VOL')},index=test.index)
    sel=out[out.selected];summary={'split':{'train':len(tr),'meta_train':len(meta),'gate_calibration':len(gate),'later_test':len(test)},
      'target_precision':target_precision,'gate':None if chosen is None else chosen[0],'gate_calibration_signals':0 if chosen is None else chosen[1],
      'gate_calibration_accuracy':None if chosen is None else chosen[2], 'all_test_accuracy':accuracy_score(actual,pred),
      'all_test_balanced_accuracy':balanced_accuracy_score(actual,pred),'selected_test_signals':len(sel),'coverage':float(selected.mean()),
      'selected_test_accuracy':float(sel.correct.mean()) if len(sel) else None,'cost_stress':{},'regimes':{}}
    for bps in cost_bps:
        net=sel.gross_return-bps/10000
        summary['cost_stress'][str(bps)]={'net_total_return':float((1+net).prod()-1) if len(net) else 0,'average_net_trade':float(net.mean()) if len(net) else None,
          'win_rate_after_cost':float((net>0).mean()) if len(net) else None,'max_drawdown':_max_dd(net)}
    for col in ['trend_regime','vol_regime']:
        for regime,g in out.groupby(col):
            sg=g[g.selected];summary['regimes'][f'{col}:{regime}']={'sessions':len(g),'signals':len(sg),'coverage':float(g.selected.mean()),
              'all_accuracy':float(g.correct.mean()),'selected_accuracy':float(sg.correct.mean()) if len(sg) else None}
    # Latest score: preserve trained chronology; it is an audit/research signal, not promoted automatically.
    lx=X.iloc[[-1]];lp,lm=_base_prob(models,lx[cols]);lmeta=_meta_frame(lp,lm,lx[cols]);lq=float(meta_model.predict_proba(lmeta)[:,list(meta_model.classes_).index(1)][0])
    latest={'direction':'UP' if lp[0]>=.5 else 'DOWN','direction_probability':float(max(lp[0],1-lp[0])),'estimated_signal_quality':lq,
      'actionable':bool(chosen is not None and lq>=chosen[0])}
    return ExecutionAudit(summary,out,latest)

def audit_gap_model(price:pd.DataFrame)->dict:
    """Separate D-close to D+1-open direction model; evaluated independently from intraday execution."""
    X=advanced_features(price);gap=price.Open.shift(-1)/price.Close-1;y=(gap>0).astype(float);y[gap.isna()]=np.nan
    d=X.join(pd.DataFrame({'y':y,'gap_return':gap})).dropna(subset=['y']);cut=int(len(d)*.80);tr,te=d.iloc[:cut],d.iloc[cut:];cols=list(X.columns)
    models=_models()
    for m in models:m.fit(tr[cols],tr.y.astype(int))
    p,_=_base_prob(models,te[cols]);pred=(p>=.5).astype(int)
    lp,_=_base_prob(models,X.iloc[[-1]][cols])
    return {'train_sessions':len(tr),'later_test_sessions':len(te),'test_accuracy':accuracy_score(te.y,pred),
      'test_balanced_accuracy':balanced_accuracy_score(te.y,pred),'up_base_rate':float(te.y.mean()),
      'latest_direction':'GAP_UP' if lp[0]>=.5 else 'GAP_DOWN','latest_confidence':float(max(lp[0],1-lp[0])),
      'warning':'Gap forecast is context; a 9 PM decision cannot capture the already-realized next open without an overnight instrument.'}
