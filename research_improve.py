from __future__ import annotations
import json
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, HistGradientBoostingClassifier, VotingClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score
from src.data import download_ohlcv
from src.features import make_features


def add_features(p):
    x=make_features(p)
    c,h,l,o,v=[p[k].astype(float) for k in ['Close','High','Low','Open','Volume']]
    ret=c.pct_change()
    # Direction and streak
    x['up_1']=(ret>0).astype(float)
    x['up_2']=((ret>0)&(ret.shift()>0)).astype(float)
    x['down_2']=((ret<0)&(ret.shift()<0)).astype(float)
    x['overnight']=o/c.shift()-1
    x['intraday']=c/o-1
    x['upper_wick']=(h-np.maximum(o,c))/c
    x['lower_wick']=(np.minimum(o,c)-l)/c
    # Quantile/range location and breakouts, all known at D close
    for n in [3,5,10,20,60]:
        hi=h.rolling(n).max(); lo=l.rolling(n).min()
        x[f'loc_{n}']=(c-lo)/(hi-lo).replace(0,np.nan)
        x[f'break_hi_{n}']=c/hi.shift()-1
        x[f'break_lo_{n}']=c/lo.shift()-1
        x[f'ret_mean_{n}']=ret.rolling(n).mean()
        x[f'ret_skew_{n}']=ret.rolling(n).skew()
    # MACD-like and Bollinger distance
    ema12=c.ewm(span=12,adjust=False).mean(); ema26=c.ewm(span=26,adjust=False).mean()
    x['macd_pct']=(ema12-ema26)/c
    mid=c.rolling(20).mean(); sd=c.rolling(20).std()
    x['boll_z']=(c-mid)/sd
    # Regime interactions
    x['trend_vol']=x['sma_dist_20']*x['vol_20']
    x['rsi_trend']=(x['rsi14']-.5)*np.sign(x['sma_dist_50'])
    return x.replace([np.inf,-np.inf],np.nan)


def models():
    return {
      'logit':Pipeline([('i',SimpleImputer(strategy='median')),('s',StandardScaler()),('m',LogisticRegression(C=.1,max_iter=2000,class_weight='balanced'))]),
      'rf':Pipeline([('i',SimpleImputer(strategy='median')),('m',RandomForestClassifier(n_estimators=600,min_samples_leaf=10,max_features=.5,class_weight='balanced_subsample',n_jobs=-1,random_state=42))]),
      'extra':Pipeline([('i',SimpleImputer(strategy='median')),('m',ExtraTreesClassifier(n_estimators=600,min_samples_leaf=10,max_features=.7,class_weight='balanced',n_jobs=-1,random_state=42))]),
      'hist':Pipeline([('i',SimpleImputer(strategy='median')),('m',HistGradientBoostingClassifier(max_iter=250,learning_rate=.035,max_leaf_nodes=10,min_samples_leaf=25,l2_regularization=4,random_state=42))]),
    }


def choose_gate(actual,pred,conf,target=.65,min_n=20):
    viable=[]
    for g in np.arange(.50,.81,.01):
        m=conf>=g
        if m.sum()>=min_n:
            viable.append((float((pred[m]==actual[m]).mean()),float(m.mean()),float(g),int(m.sum())))
    # Prefer gate reaching target with max coverage, otherwise highest lower-bound-ish score penalizing tiny n
    passing=[r for r in viable if r[0]>=target]
    return max(passing,key=lambda r:r[1]) if passing else max(viable,key=lambda r:r[0]*np.sqrt(r[3]/max(min_n,1)),default=(np.nan,0,.65,0))


def main():
    p=download_ohlcv('^NSEI','10y'); X=add_features(p)
    # Strict binary close-to-close direction. Zero returns excluded.
    nr=p.Close.shift(-1)/p.Close-1
    y=(nr>0).astype(float); y[nr.isna()]=np.nan
    d=X.join(y.rename('y')).dropna(subset=['y'])
    cols=list(X.columns); n=len(d); a=int(n*.60); b=int(n*.80)
    tr,cal,te=d.iloc[:a],d.iloc[a:b],d.iloc[b:]
    output=[]; fitted={}; cal_probs=[]; test_probs=[]
    for name,m in models().items():
        m.fit(tr[cols],tr.y.astype(int)); fitted[name]=m
        cp=m.predict_proba(cal[cols])[:,1]; tp=m.predict_proba(te[cols])[:,1]
        cal_probs.append(cp); test_probs.append(tp)
        cpr=(cp>=.5).astype(int); cc=np.maximum(cp,1-cp)
        gate=choose_gate(cal.y.to_numpy(int),cpr,cc,.65,max(20,len(cal)//20))
        tpr=(tp>=.5).astype(int); tc=np.maximum(tp,1-tp); mask=tc>=gate[2]
        output.append({'model':name,'cal_all_acc':accuracy_score(cal.y,cpr),'cal_selected_acc':gate[0],
          'gate':gate[2],'cal_coverage':gate[1],'cal_n':gate[3], 'test_all_acc':accuracy_score(te.y,tpr),
          'test_bal_acc':balanced_accuracy_score(te.y,tpr),'test_selected_acc':accuracy_score(te.y[mask],tpr[mask]) if mask.any() else None,
          'test_coverage':float(mask.mean()),'test_n':int(mask.sum())})
    for mode,weights in [('ensemble_equal',np.ones(4)/4),('ensemble_tree',np.array([.1,.35,.35,.2]))]:
        cp=np.average(np.vstack(cal_probs),axis=0,weights=weights); tp=np.average(np.vstack(test_probs),axis=0,weights=weights)
        cpr=(cp>=.5).astype(int); cc=np.maximum(cp,1-cp); gate=choose_gate(cal.y.to_numpy(int),cpr,cc,.65,max(20,len(cal)//20))
        tpr=(tp>=.5).astype(int); tc=np.maximum(tp,1-tp); mask=tc>=gate[2]
        output.append({'model':mode,'cal_all_acc':accuracy_score(cal.y,cpr),'cal_selected_acc':gate[0], 'gate':gate[2],
          'cal_coverage':gate[1],'cal_n':gate[3],'test_all_acc':accuracy_score(te.y,tpr),'test_bal_acc':balanced_accuracy_score(te.y,tpr),
          'test_selected_acc':accuracy_score(te.y[mask],tpr[mask]) if mask.any() else None,'test_coverage':float(mask.mean()),'test_n':int(mask.sum())})
    print(pd.DataFrame(output).to_string(index=False))
    with open('model_research_results.json','w') as f: json.dump(output,f,indent=2)

if __name__=='__main__': main()
