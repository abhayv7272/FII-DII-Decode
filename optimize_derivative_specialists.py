from __future__ import annotations
import json,math
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier,ExtraTreesClassifier,HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score,balanced_accuracy_score
from src.data import download_ohlcv
from src.advanced_model import advanced_features
from src.technical_indicators import prune_correlated

def models():return {
 'logit':lambda:Pipeline([('i',SimpleImputer(strategy='median')),('s',StandardScaler()),('m',LogisticRegression(C=.15,max_iter=2000,class_weight='balanced',random_state=42))]),
 'rf':lambda:Pipeline([('i',SimpleImputer(strategy='median')),('m',RandomForestClassifier(n_estimators=500,min_samples_leaf=8,max_features=.65,class_weight='balanced_subsample',n_jobs=-1,random_state=42))]),
 'extra':lambda:Pipeline([('i',SimpleImputer(strategy='median')),('m',ExtraTreesClassifier(n_estimators=500,min_samples_leaf=8,max_features=.7,class_weight='balanced',n_jobs=-1,random_state=42))]),
 'hist':lambda:Pipeline([('i',SimpleImputer(strategy='median')),('m',HistGradientBoostingClassifier(max_iter=220,learning_rate=.035,max_leaf_nodes=9,min_samples_leaf=18,l2_regularization=4,random_state=42))])}

def derivative_features(opt,fut):
 o=opt.set_index(pd.to_datetime(opt.date)).drop(columns='date');f=fut.set_index(pd.to_datetime(fut.date)).drop(columns='date');d=o.join(f,how='inner',rsuffix='_fut')
 numeric=d.select_dtypes(include='number').copy()
 # Levels themselves are non-stationary; use distances, changes, ratios and rolling standardization.
 drop=[c for c in numeric if c in {'spot','call_wall','put_wall','call_build_wall','put_build_wall','call_unwind_wall','put_unwind_wall','max_pain','atm_strike','future_close','future_oi','future_volume'}]
 numeric=numeric.drop(columns=drop,errors='ignore')
 for c in ['pcr_oi','change_oi_imbalance','pcr_volume','call_wall_distance_pct','put_wall_distance_pct','max_pain_distance_pct','atm_straddle_pct','future_basis_pct','future_change_oi','near_oi_share','next_near_spread_pct']:
  if c in numeric:
   numeric[f'{c}_delta1']=numeric[c].diff();numeric[f'{c}_z20']=(numeric[c]-numeric[c].rolling(20).mean())/numeric[c].rolling(20).std().replace(0,np.nan)
 if {'call_wall_distance_pct','put_wall_distance_pct'}.issubset(numeric):numeric['wall_space_asymmetry']=numeric.call_wall_distance_pct.abs()-numeric.put_wall_distance_pct.abs()
 if {'call_oi','put_oi'}.issubset(numeric):numeric['total_option_oi_change_pct']=(numeric.call_oi+numeric.put_oi).pct_change()
 if {'call_volume','put_volume'}.issubset(numeric):numeric['total_option_volume_change_pct']=(numeric.call_volume+numeric.put_volume).pct_change()
 return numeric.replace([np.inf,-np.inf],np.nan)

def participant_features(path='data/historical_participant_oi.csv'):
 d=pd.read_csv(path);d.index=pd.to_datetime(d.pop('date'));x=pd.DataFrame(index=d.index)
 for c in d.select_dtypes(include='number'):
  s=pd.to_numeric(d[c],errors='coerce');x[f'{c}_delta1']=s.diff();x[f'{c}_delta5']=s.diff(5)
  x[f'{c}_z20']=(s-s.rolling(20).mean())/s.rolling(20).std().replace(0,np.nan)
  x[f'{c}_z60']=(s-s.rolling(60).mean())/s.rolling(60).std().replace(0,np.nan)
 # Explicit FII-Pro alignment/conflict features.
 if {'fii_index_future_net','pro_index_future_net'}.issubset(d):
  fd=d.fii_index_future_net.diff();pdlt=d.pro_index_future_net.diff();x['fii_pro_delta_agreement']=np.sign(fd)*np.sign(pdlt);x['fii_minus_pro_delta_z']=((fd-pdlt)-(fd-pdlt).rolling(20).mean())/(fd-pdlt).rolling(20).std().replace(0,np.nan)
 return x.replace([np.inf,-np.inf],np.nan)

def gate(y,p,target,min_n=25):
 pred=p>=.5;conf=np.maximum(p,1-p)
 for g in np.arange(.50,.86,.01):
  m=conf>=g
  if m.sum()>=min_n and (pred[m]==y[m]).mean()>=target:return {'gate':float(g),'signals':int(m.sum()),'accuracy':float((pred[m]==y[m]).mean()),'coverage':float(m.mean())}
 return None

def main():
 price=download_ohlcv('^NSEI','10y');opt=pd.read_csv('data/historical_option_features.csv');fut=pd.read_csv('data/historical_futures_features.csv')
 px=advanced_features(price);der=derivative_features(opt,fut);part=participant_features();idx=px.index.intersection(der.index).intersection(part.index).sort_values();px=px.loc[idx];der=der.loc[idx];part=part.loc[idx]
 ret=price.Close.shift(-1)/price.Open.shift(-1)-1;y=(ret>0).astype(float).reindex(idx);trade_ret=ret.reindex(idx);y[trade_ret.isna()]=np.nan;valid=y.notna();px,der,part,y,trade_ret=px[valid],der[valid],part[valid],y[valid],trade_ret[valid]
 sets={'price':px,'option_futures':der,'participant':part,'derivatives_participant':der.join(part),'price_plus_derivatives':px.join(der),'full':px.join(der).join(part)};n=len(y);hs=int(n*.80);folds=[];val=60
 for start in range(max(180,hs-3*val),hs,val):
  end=min(start+val,hs)
  if end-start>=40:folds.append((np.arange(start),np.arange(start,end)))
 results=[];cache={};columns={}
 for sname,X in sets.items():
  cols=prune_correlated(X.iloc[:max(150,folds[0][1][0])],.96,.60);columns[sname]=cols
  for mname,factory in models().items():
   acc=[];bal=[];parts=[]
   for tr,va in folds:
    m=factory();m.fit(X.iloc[tr][cols],y.iloc[tr].astype(int));p=m.predict_proba(X.iloc[va][cols])[:,1];pred=p>=.5
    acc.append(accuracy_score(y.iloc[va],pred));bal.append(balanced_accuracy_score(y.iloc[va],pred));parts.append(pd.DataFrame({'y':y.iloc[va].astype(int),'p':p},index=y.index[va]))
   score=np.mean(bal)-.5*np.std(bal);results.append({'features':sname,'model':mname,'columns':len(cols),'cv_accuracy':np.mean(acc),'cv_balanced':np.mean(bal),'cv_std':np.std(bal),'selection_score':score});cache[(sname,mname)]=pd.concat(parts)
 table=pd.DataFrame(results).sort_values(['selection_score','cv_accuracy'],ascending=False);best=table.iloc[0];sname,mname=best['features'],best['model'];X=sets[sname];cols=columns[sname];oof=cache[(sname,mname)]
 gates={str(t):gate(oof.y.to_numpy(),oof.p.to_numpy(),t,25) for t in [.60,.65,.70,.75]};chosen=gates['0.65'] or gates['0.6']
 m=models()[mname]();m.fit(X.iloc[:hs][cols],y.iloc[:hs].astype(int));p=m.predict_proba(X.iloc[hs:][cols])[:,1];pred=p>=.5;actual=y.iloc[hs:].to_numpy(int);conf=np.maximum(p,1-p);sel=np.zeros(len(p),bool) if chosen is None else conf>=chosen['gate'];gross=np.where(pred,1,-1)*trade_ret.iloc[hs:].to_numpy()
 hold={'sessions':len(p),'accuracy':accuracy_score(actual,pred),'balanced_accuracy':balanced_accuracy_score(actual,pred),'signals':int(sel.sum()),'coverage':float(sel.mean()),'selected_accuracy':float((pred[sel]==actual[sel]).mean()) if sel.any() else None,'costs':{}}
 for bps in [3,6,10]:
  net=gross[sel]-bps/10000;eq=np.r_[1.0,np.cumprod(1+net)];hold['costs'][str(bps)]={'net_return':float(eq[-1]-1) if len(net) else 0,'avg_trade':float(net.mean()) if len(net) else None,'win_rate':float((net>0).mean()) if len(net) else None,'max_drawdown':float(np.min(eq/np.maximum.accumulate(eq)-1)) if len(net) else None}
 # Simple setup diagnostics on holdout, reported but never used to choose model.
 test_der=der.iloc[hs:];diag={}
 rules={'put_build_dominant':test_der.change_oi_imbalance>0,'call_build_dominant':test_der.change_oi_imbalance<0,'positive_futures_basis':test_der.future_basis_pct>0,'negative_futures_basis':test_der.future_basis_pct<0}
 for name,mask in rules.items():
  mask=mask.fillna(False).to_numpy();diag[name]={'sessions':int(mask.sum()),'model_accuracy':float((pred[mask]==actual[mask]).mean()) if mask.any() else None}
 out={'availability':{'option_sessions_raw':len(opt),'futures_sessions_raw':len(fut),'participant_sessions_raw':len(pd.read_csv('data/historical_participant_oi.csv')),'joined_labeled_sessions':n},'method':'Feature/model selected on three expanding development folds; final 20% not used for selection.','ranking':table.to_dict('records'),'best':best.to_dict(),'oof_gates':gates,'frozen_gate':chosen,'holdout':hold,'holdout_diagnostics':diag,'selected_columns':cols}
 Path('reports/derivative_specialist.json').write_text(json.dumps(out,indent=2,default=float));table.to_csv('reports/derivative_specialist_ranking.csv',index=False)
 print('TOP\n',table.head(10).to_string(index=False));print('\nGATES',gates);print('\nHOLDOUT',hold);print('AVAILABILITY',out['availability'])
if __name__=='__main__':main()
