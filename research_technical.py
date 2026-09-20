from __future__ import annotations
import json,numpy as np,pandas as pd
from sklearn.metrics import accuracy_score,balanced_accuracy_score
from src.data import download_ohlcv
from src.multi_asset import multi_asset_technical
from src.technical_indicators import prune_correlated
from src.advanced_model import _models,_choose_gate

def main():
 p=download_ohlcv('^NSEI','10y');X=multi_asset_technical(p);r=p.Close.shift(-1)/p.Close-1;y=(r>0).astype(float);y[r.isna()]=np.nan
 d=X.join(y.rename('y')).dropna(subset=['y']);n=len(d);a=int(n*.60);b=int(n*.80);tr,cal,te=d.iloc[:a],d.iloc[a:b],d.iloc[b:]
 cols=prune_correlated(tr.drop(columns='y'),.97,.60);weights=np.array([.1,.35,.35,.2]);cp=[];tp=[]
 for m in _models():m.fit(tr[cols],tr.y.astype(int));cp.append(m.predict_proba(cal[cols])[:,1]);tp.append(m.predict_proba(te[cols])[:,1])
 cp=np.average(np.vstack(cp),axis=0,weights=weights);tp=np.average(np.vstack(tp),axis=0,weights=weights)
 rows=[]
 for target in [.60,.65,.70,.75]:
  gate=_choose_gate(cal.y.to_numpy(int),(cp>=.5).astype(int),np.maximum(cp,1-cp),target,max(25,len(cal)//20));pred=(tp>=.5).astype(int);sel=np.maximum(tp,1-tp)>=gate[2]
  rows.append({'target':target,'raw_features':X.shape[1],'selected_features':len(cols),'cal_gate':gate[2],'cal_acc':gate[0],'cal_n':gate[3],
   'test_all_accuracy':accuracy_score(te.y,pred),'test_balanced_accuracy':balanced_accuracy_score(te.y,pred),
   'test_selected_accuracy':accuracy_score(te.y[sel],pred[sel]) if sel.any() else None,'test_signals':int(sel.sum()),'test_coverage':float(sel.mean())})
 print(pd.DataFrame(rows).to_string(index=False));open('technical_research_results.json','w').write(json.dumps(rows,indent=2))
if __name__=='__main__':main()
