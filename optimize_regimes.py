from __future__ import annotations
import json,math
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from src.data import download_ohlcv
from src.multi_asset import multi_asset_technical

def model():return Pipeline([('i',SimpleImputer(strategy='median')),('m',RandomForestClassifier(n_estimators=400,min_samples_leaf=10,max_features=.5,class_weight='balanced_subsample',n_jobs=-1,random_state=42))])
def wilson_lower(correct,n,z=1.64):
 if n==0:return 0
 p=correct/n;den=1+z*z/n;return (p+z*z/(2*n)-z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/den

def main():
 opt=json.loads(Path('reports/combination_optimizer.json').read_text());cols=opt['selected_columns']
 p=download_ohlcv('^NSEI','10y');X=multi_asset_technical(p);r=p.Close.shift(-1)/p.Open.shift(-1)-1;y=(r>0).astype(float);y[r.isna()]=np.nan
 idx=y.dropna().index;X=X.loc[idx];y=y.loc[idx];n=len(y);hs=int(n*.80);val=250
 sma20=p.Close.rolling(20).mean().reindex(idx);sma200=p.Close.rolling(200).mean().reindex(idx);vol=p.Close.pct_change().rolling(20).std().reindex(idx);vcut=vol.expanding(252).median().shift(1)
 regimes=pd.DataFrame({'bull':p.Close.reindex(idx)>=sma200,'above20':p.Close.reindex(idx)>=sma20,'highvol':vol>=vcut},index=idx)
 oofs=[]
 for fold,start in enumerate(range(max(800,hs-4*val),hs,val),1):
  end=min(start+val,hs);m=model();m.fit(X.iloc[:start][cols],y.iloc[:start].astype(int));pr=m.predict_proba(X.iloc[start:end][cols])[:,1]
  q=regimes.iloc[start:end].copy();q['p']=pr;q['pred']=pr>=.5;q['y']=y.iloc[start:end].astype(int);q['fold']=fold;oofs.append(q)
 oof=pd.concat(oofs);policies={
  'all':np.ones(len(oof),bool),'bull':oof.bull,'bear':~oof.bull,'above20':oof.above20,'below20':~oof.above20,
  'highvol':oof.highvol,'lowvol':~oof.highvol,'bull_lowvol':oof.bull&~oof.highvol,'bull_highvol':oof.bull&oof.highvol,
  'bear_lowvol':~oof.bull&~oof.highvol,'bear_highvol':~oof.bull&oof.highvol,'predict_up':oof.pred,'predict_down':~oof.pred}
 for g in [.55,.60,.65]:policies[f'confidence_{g:.2f}']=np.maximum(oof.p,1-oof.p)>=g
 rows=[]
 for name,mask in policies.items():
  mask=np.asarray(mask);nsel=mask.sum();foldacc=[]
  for _,q in oof[mask].groupby('fold'):
   if len(q)>=20:foldacc.append(float((q.pred==q.y).mean()))
  acc=float((oof.loc[mask,'pred']==oof.loc[mask,'y']).mean()) if nsel else 0
  stable=len(foldacc)==4 and min(foldacc)>=.45
  score=wilson_lower(round(acc*nsel),nsel)-(.03*np.std(foldacc) if foldacc else 1)
  rows.append({'policy':name,'signals':int(nsel),'coverage':float(nsel/len(oof)),'oof_accuracy':acc,'fold_min':min(foldacc) if foldacc else None,'fold_std':np.std(foldacc) if foldacc else None,'stable':stable,'score':score})
 table=pd.DataFrame(rows);eligible=table[(table.signals>=150)&table.stable];chosen=eligible.sort_values('score',ascending=False).iloc[0] if len(eligible) else table[table.policy=='all'].iloc[0]
 # Evaluate one frozen policy on final holdout.
 m=model();m.fit(X.iloc[:hs][cols],y.iloc[:hs].astype(int));pr=m.predict_proba(X.iloc[hs:][cols])[:,1];pred=pr>=.5;rg=regimes.iloc[hs:]
 name=chosen.policy
 masks={'all':np.ones(len(pr),bool),'bull':rg.bull,'bear':~rg.bull,'above20':rg.above20,'below20':~rg.above20,'highvol':rg.highvol,'lowvol':~rg.highvol,
  'bull_lowvol':rg.bull&~rg.highvol,'bull_highvol':rg.bull&rg.highvol,'bear_lowvol':~rg.bull&~rg.highvol,'bear_highvol':~rg.bull&rg.highvol,'predict_up':pred,'predict_down':~pred}
 for g in [.55,.60,.65]:masks[f'confidence_{g:.2f}']=np.maximum(pr,1-pr)>=g
 mask=np.asarray(masks[name]);actual=y.iloc[hs:].to_numpy(int)
 hold={'policy':name,'signals':int(mask.sum()),'coverage':float(mask.mean()),'accuracy':float((pred[mask]==actual[mask]).mean()) if mask.any() else None,'all_accuracy':float((pred==actual).mean())}
 out={'policy_ranking':table.sort_values('score',ascending=False).to_dict('records'),'chosen_on_oof':chosen.to_dict(),'holdout':hold}
 Path('reports/regime_optimizer.json').write_text(json.dumps(out,indent=2,default=float));table.sort_values('score',ascending=False).to_csv('reports/regime_ranking.csv',index=False)
 print(table.sort_values('score',ascending=False).to_string(index=False));print('\nCHOSEN',chosen.to_dict());print('HOLDOUT',hold)
if __name__=='__main__':main()
