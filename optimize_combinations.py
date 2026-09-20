from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import f_classif
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier,ExtraTreesClassifier,HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score,balanced_accuracy_score
from src.data import download_ohlcv
from src.features import make_features
from src.advanced_model import advanced_features
from src.multi_asset import multi_asset_technical
from src.technical_indicators import technical_features,prune_correlated

SEED=42

def models():
 return {
  'logit':lambda:Pipeline([('i',SimpleImputer(strategy='median')),('s',StandardScaler()),('m',LogisticRegression(C=.1,max_iter=2000,class_weight='balanced',random_state=SEED))]),
  'rf':lambda:Pipeline([('i',SimpleImputer(strategy='median')),('m',RandomForestClassifier(n_estimators=300,min_samples_leaf=10,max_features=.5,class_weight='balanced_subsample',n_jobs=-1,random_state=SEED))]),
  'extra':lambda:Pipeline([('i',SimpleImputer(strategy='median')),('m',ExtraTreesClassifier(n_estimators=300,min_samples_leaf=10,max_features=.7,class_weight='balanced',n_jobs=-1,random_state=SEED))]),
  'hist':lambda:Pipeline([('i',SimpleImputer(strategy='median')),('m',HistGradientBoostingClassifier(max_iter=220,learning_rate=.035,max_leaf_nodes=10,min_samples_leaf=25,l2_regularization=4,random_state=SEED))])}

def top_columns(X,y,base_rows,k):
 A=X.iloc[:base_rows];yy=y.iloc[:base_rows];cols=prune_correlated(A,.97,.60)
 imp=SimpleImputer(strategy='median');z=imp.fit_transform(A[cols]);score,_=f_classif(z,yy.astype(int));rank=np.argsort(np.nan_to_num(score,nan=-1))[::-1]
 return [cols[i] for i in rank[:min(k,len(cols))]]

def gate_from_oof(y,p,target=.65,min_signals=40):
 pred=(p>=.5).astype(int);conf=np.maximum(p,1-p);rows=[]
 for g in np.arange(.50,.86,.01):
  m=conf>=g
  if m.sum()>=min_signals:rows.append({'gate':float(g),'signals':int(m.sum()),'coverage':float(m.mean()),'accuracy':float((pred[m]==y[m]).mean())})
 valid=[r for r in rows if r['accuracy']>=target]
 return max(valid,key=lambda r:r['coverage']) if valid else None

def main():
 price=download_ohlcv('^NSEI','10y');ret=price.Close.shift(-1)/price.Open.shift(-1)-1;y=(ret>0).astype(float);y[ret.isna()]=np.nan
 print('Building timing-safe multi-asset feature matrix...')
 sets={'core':make_features(price),'structure':advanced_features(price),'nifty_technical':technical_features(price,'nifty'),'multi_asset':multi_asset_technical(price)}
 # common labeled timeline
 valid=y.notna();y=y[valid];ret=ret[valid];sets={k:v.loc[y.index] for k,v in sets.items()}
 n=len(y);hold_start=int(n*.80);base_rows=int(hold_start*.50)
 variants={}
 variants['core_all']=prune_correlated(sets['core'].iloc[:base_rows],.97,.60)
 variants['structure_all']=prune_correlated(sets['structure'].iloc[:base_rows],.97,.60)
 for k in [30,60,100]:variants[f'nifty_top{k}']=top_columns(sets['nifty_technical'],y,base_rows,k)
 for k in [40,80,120]:variants[f'multi_top{k}']=top_columns(sets['multi_asset'],y,base_rows,k)
 folds=[];val_size=250
 for start in range(max(800,hold_start-4*val_size),hold_start,val_size):
  end=min(start+val_size,hold_start)
  if end-start>=100:folds.append((np.arange(0,start),np.arange(start,end)))
 results=[];oof_cache={}
 for vname,cols in variants.items():
  X=sets['multi_asset'] if vname.startswith('multi') else sets['nifty_technical'] if vname.startswith('nifty') else sets['structure'] if vname.startswith('structure') else sets['core']
  for mname,factory in models().items():
   fold_acc=[];fold_bal=[];oof=[]
   for tr,va in folds:
    m=factory();m.fit(X.iloc[tr][cols],y.iloc[tr].astype(int));p=m.predict_proba(X.iloc[va][cols])[:,1];pred=(p>=.5).astype(int)
    fold_acc.append(accuracy_score(y.iloc[va],pred));fold_bal.append(balanced_accuracy_score(y.iloc[va],pred));oof.append(pd.DataFrame({'y':y.iloc[va].astype(int),'p':p},index=y.index[va]))
   stability=float(np.mean(fold_bal)-.25*np.std(fold_bal));results.append({'variant':vname,'model':mname,'features':len(cols),'mean_accuracy':np.mean(fold_acc),'mean_balanced':np.mean(fold_bal),'std_balanced':np.std(fold_bal),'selection_score':stability})
   oof_cache[(vname,mname)]=pd.concat(oof).sort_index()
 table=pd.DataFrame(results).sort_values(['selection_score','mean_accuracy'],ascending=False);best=table.iloc[0];vname,mname=best.variant,best.model
 cols=variants[vname];X=sets['multi_asset'] if vname.startswith('multi') else sets['nifty_technical'] if vname.startswith('nifty') else sets['structure'] if vname.startswith('structure') else sets['core']
 oof=oof_cache[(vname,mname)];gates={str(t):gate_from_oof(oof.y.to_numpy(),oof.p.to_numpy(),t,40) for t in [.60,.65,.70,.75]}
 # Gate policy frozen from OOF: prefer 65%, then 60%; never inspect holdout to choose it.
 chosen=gates['0.65'] or gates['0.6']
 model=models()[mname]();model.fit(X.iloc[:hold_start][cols],y.iloc[:hold_start].astype(int));p=model.predict_proba(X.iloc[hold_start:][cols])[:,1];pred=(p>=.5).astype(int);actual=y.iloc[hold_start:].to_numpy(int);conf=np.maximum(p,1-p)
 selected=np.zeros(len(p),dtype=bool) if chosen is None else conf>=chosen['gate'];gross=np.where(pred==1,1,-1)*ret.iloc[hold_start:].to_numpy()
 hold={'sessions':len(p),'accuracy':accuracy_score(actual,pred),'balanced_accuracy':balanced_accuracy_score(actual,pred),'selected_signals':int(selected.sum()),'coverage':float(selected.mean()),'selected_accuracy':float((pred[selected]==actual[selected]).mean()) if selected.any() else None,'costs':{}}
 for bps in [3,6,10]:
  net=gross[selected]-bps/10000;eq=np.r_[1.0,np.cumprod(1+net)];hold['costs'][str(bps)]={'net_total_return':float(eq[-1]-1) if len(net) else 0,'avg_net_trade':float(net.mean()) if len(net) else None,'win_rate':float((net>0).mean()) if len(net) else None,'max_drawdown':float(np.min(eq/np.maximum.accumulate(eq)-1)) if len(net) else None}
 output={'method':'Feature/model selected only by expanding development folds; holdout not used for selection.','target':'D+1 open-to-close direction','rows':n,'development_sessions':hold_start,'holdout_sessions':n-hold_start,'folds':len(folds),'ranking':table.to_dict('records'),'best_development_combination':best.to_dict(),'oof_gates':gates,'frozen_gate':chosen,'holdout':hold,'selected_columns':cols}
 Path('reports').mkdir(exist_ok=True);Path('reports/combination_optimizer.json').write_text(json.dumps(output,indent=2,default=float));table.to_csv('reports/combination_ranking.csv',index=False)
 print('\nTOP 12 DEVELOPMENT COMBINATIONS\n',table.head(12).to_string(index=False));print('\nFROZEN GATES',gates);print('\nFINAL HOLDOUT',hold)
if __name__=='__main__':main()
