from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score
from .features import make_features

@dataclass
class DirectionResult:
    models: list
    weights: np.ndarray
    columns: list[str]
    gate: float
    metrics: dict
    test_predictions: pd.DataFrame


def advanced_features(p: pd.DataFrame) -> pd.DataFrame:
    x=make_features(p); c,h,l,o,v=[p[k].astype(float) for k in ['Close','High','Low','Open','Volume']]
    ret=c.pct_change()
    x['up_1']=(ret>0).astype(float); x['up_2']=((ret>0)&(ret.shift()>0)).astype(float)
    x['down_2']=((ret<0)&(ret.shift()<0)).astype(float)
    x['overnight']=o/c.shift()-1; x['intraday']=c/o-1
    x['upper_wick']=(h-np.maximum(o,c))/c; x['lower_wick']=(np.minimum(o,c)-l)/c
    for n in [3,5,10,20,60]:
        hi=h.rolling(n).max(); lo=l.rolling(n).min()
        x[f'loc_{n}']=(c-lo)/(hi-lo).replace(0,np.nan)
        x[f'break_hi_{n}']=c/hi.shift()-1; x[f'break_lo_{n}']=c/lo.shift()-1
        x[f'ret_mean_{n}']=ret.rolling(n).mean(); x[f'ret_skew_{n}']=ret.rolling(n).skew()
    ema12=c.ewm(span=12,adjust=False).mean(); ema26=c.ewm(span=26,adjust=False).mean()
    x['macd_pct']=(ema12-ema26)/c
    mid=c.rolling(20).mean(); sd=c.rolling(20).std(); x['boll_z']=(c-mid)/sd
    x['trend_vol']=x['sma_dist_20']*x['vol_20']; x['rsi_trend']=(x['rsi14']-.5)*np.sign(x['sma_dist_50'])
    return x.replace([np.inf,-np.inf],np.nan)


def _models():
    return [
      Pipeline([('i',SimpleImputer(strategy='median')),('s',StandardScaler()),('m',LogisticRegression(C=.1,max_iter=2000,class_weight='balanced'))]),
      Pipeline([('i',SimpleImputer(strategy='median')),('m',RandomForestClassifier(n_estimators=600,min_samples_leaf=10,max_features=.5,class_weight='balanced_subsample',n_jobs=-1,random_state=42))]),
      Pipeline([('i',SimpleImputer(strategy='median')),('m',ExtraTreesClassifier(n_estimators=600,min_samples_leaf=10,max_features=.7,class_weight='balanced',n_jobs=-1,random_state=42))]),
      Pipeline([('i',SimpleImputer(strategy='median')),('m',HistGradientBoostingClassifier(max_iter=250,learning_rate=.035,max_leaf_nodes=10,min_samples_leaf=25,l2_regularization=4,random_state=42))]),
    ]


def _choose_gate(actual,pred,conf,target=.65,min_n=20):
    rows=[]
    for g in np.arange(.50,.81,.01):
        mask=conf>=g
        if mask.sum()>=min_n: rows.append((float((pred[mask]==actual[mask]).mean()),float(mask.mean()),float(g),int(mask.sum())))
    passing=[r for r in rows if r[0]>=target]
    return max(passing,key=lambda z:z[1]) if passing else max(rows,key=lambda z:z[0]*np.sqrt(z[3]/min_n),default=(np.nan,0,.65,0))


def train_direction_model(price: pd.DataFrame, target_precision=.65) -> DirectionResult:
    X=advanced_features(price); nr=price.Close.shift(-1)/price.Close-1
    y=(nr>0).astype(float); y[nr.isna()]=np.nan
    d=X.join(y.rename('y')).dropna(subset=['y']); cols=list(X.columns)
    if len(d)<600: raise ValueError('At least 600 sessions required for strict train/calibration/test split.')
    a=int(len(d)*.60); b=int(len(d)*.80); tr,cal,te=d.iloc[:a],d.iloc[a:b],d.iloc[b:]
    weights=np.array([.1,.35,.35,.2]); ms=_models(); cp=[]; tp=[]
    for m in ms:
        m.fit(tr[cols],tr.y.astype(int)); cp.append(m.predict_proba(cal[cols])[:,1]); tp.append(m.predict_proba(te[cols])[:,1])
    cp=np.average(np.vstack(cp),axis=0,weights=weights); tp=np.average(np.vstack(tp),axis=0,weights=weights)
    cpr=(cp>=.5).astype(int); cc=np.maximum(cp,1-cp)
    gate_row=_choose_gate(cal.y.to_numpy(int),cpr,cc,target_precision,max(20,len(cal)//20)); gate=gate_row[2]
    tpr=(tp>=.5).astype(int); tc=np.maximum(tp,1-tp); sel=tc>=gate
    testout=pd.DataFrame({'actual':np.where(te.y.astype(int)==1,'UP','DOWN'),'prediction':np.where(tpr==1,'UP','DOWN'),'confidence':tc,'selected':sel},index=te.index)
    metrics={'train_sessions':len(tr),'calibration_sessions':len(cal),'test_sessions':len(te),
      'calibration_selected_accuracy':gate_row[0],'calibration_coverage':gate_row[1],
      'test_all_accuracy':accuracy_score(te.y,tpr),'test_balanced_accuracy':balanced_accuracy_score(te.y,tpr),
      'test_selected_accuracy':accuracy_score(te.y[sel],tpr[sel]) if sel.any() else np.nan,
      'test_coverage':float(sel.mean()),'test_selected_signals':int(sel.sum())}
    # Refit same frozen ensemble on all labeled rows only after test metrics have been computed.
    final=_models()
    for m in final: m.fit(d[cols],d.y.astype(int))
    return DirectionResult(final,weights,cols,gate,metrics,testout)


def predict_direction(result: DirectionResult, latest: pd.DataFrame) -> dict:
    ps=np.array([m.predict_proba(latest[result.columns])[:,1][0] for m in result.models])
    p_up=float(np.average(ps,weights=result.weights)); conf=max(p_up,1-p_up)
    return {'label':'UP' if p_up>=.5 else 'DOWN','p_up':p_up,'p_down':1-p_up,'confidence':conf,
            'actionable':bool(conf>=result.gate),'model_agreement':float(np.mean((ps>=.5)==(p_up>=.5)))}
