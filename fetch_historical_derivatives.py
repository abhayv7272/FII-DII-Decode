from __future__ import annotations
import argparse,time
from pathlib import Path
import numpy as np,pandas as pd
from nselib import derivatives

OUT=Path('data');OUT.mkdir(exist_ok=True)

def aggregate_options(df):
 if df.empty:return pd.DataFrame()
 d=df.copy();d['date']=pd.to_datetime(d.TIMESTAMP,format='mixed',dayfirst=True,errors='coerce');d['expiry']=pd.to_datetime(d.EXPIRY_DT,format='mixed',dayfirst=True,errors='coerce')
 for c in ['STRIKE_PRICE','CLOSING_PRICE','OPEN_INT','CHANGE_IN_OI','TOT_TRADED_QTY','UNDERLYING_VALUE']:d[c]=pd.to_numeric(d[c],errors='coerce').fillna(0)
 rows=[]
 for day,g in d.dropna(subset=['date','expiry']).groupby('date'):
  future=g[g.expiry>=day]
  if future.empty:continue
  expiry=future.expiry.min();q=future[future.expiry==expiry].copy();spot=float(q.UNDERLYING_VALUE.replace(0,np.nan).median())
  if not spot or np.isnan(spot):continue
  q=q[(q.STRIKE_PRICE>=spot*.94)&(q.STRIKE_PRICE<=spot*1.06)]
  ce=q[q.OPTION_TYPE=='CE'];pe=q[q.OPTION_TYPE=='PE']
  if ce.empty or pe.empty:continue
  call_wall=ce.loc[ce.OPEN_INT.idxmax()];put_wall=pe.loc[pe.OPEN_INT.idxmax()]
  call_build=ce.loc[ce.CHANGE_IN_OI.idxmax()];put_build=pe.loc[pe.CHANGE_IN_OI.idxmax()]
  call_unwind=ce.loc[ce.CHANGE_IN_OI.idxmin()];put_unwind=pe.loc[pe.CHANGE_IN_OI.idxmin()]
  strikes=np.sort(q.STRIKE_PRICE.unique());pain=[]
  for settle in strikes:
   call_pay=((settle-ce.STRIKE_PRICE).clip(lower=0)*ce.OPEN_INT).sum();put_pay=((pe.STRIKE_PRICE-settle).clip(lower=0)*pe.OPEN_INT).sum();pain.append(call_pay+put_pay)
  max_pain=float(strikes[int(np.argmin(pain))])
  atm_strike=float(strikes[np.argmin(abs(strikes-spot))]);atm=q[q.STRIKE_PRICE==atm_strike]
  atm_ce=atm.loc[atm.OPTION_TYPE=='CE','CLOSING_PRICE'].median();atm_pe=atm.loc[atm.OPTION_TYPE=='PE','CLOSING_PRICE'].median()
  coi=ce.OPEN_INT.sum();poi=pe.OPEN_INT.sum();cchg=ce.CHANGE_IN_OI.sum();pchg=pe.CHANGE_IN_OI.sum();cvol=ce.TOT_TRADED_QTY.sum();pvol=pe.TOT_TRADED_QTY.sum()
  rows.append({'date':day.date().isoformat(),'spot':spot,'near_expiry':expiry.date().isoformat(),'days_to_expiry':(expiry-day).days,
   'call_oi':coi,'put_oi':poi,'pcr_oi':poi/max(coi,1),'call_change_oi':cchg,'put_change_oi':pchg,
   'change_oi_imbalance':(pchg-cchg)/max(abs(pchg)+abs(cchg),1),'call_volume':cvol,'put_volume':pvol,'pcr_volume':pvol/max(cvol,1),
   'call_wall':call_wall.STRIKE_PRICE,'put_wall':put_wall.STRIKE_PRICE,'call_build_wall':call_build.STRIKE_PRICE,'put_build_wall':put_build.STRIKE_PRICE,
   'call_unwind_wall':call_unwind.STRIKE_PRICE,'put_unwind_wall':put_unwind.STRIKE_PRICE,'call_wall_distance_pct':call_wall.STRIKE_PRICE/spot-1,
   'put_wall_distance_pct':put_wall.STRIKE_PRICE/spot-1,'max_pain':max_pain,'max_pain_distance_pct':max_pain/spot-1,
   'atm_strike':atm_strike,'atm_call_close':atm_ce,'atm_put_close':atm_pe,'atm_straddle_pct':(atm_ce+atm_pe)/spot,
   'call_oi_concentration':call_wall.OPEN_INT/max(coi,1),'put_oi_concentration':put_wall.OPEN_INT/max(poi,1)})
 return pd.DataFrame(rows)

def fetch_options(start,end,chunk_days=30):
 path=OUT/'historical_option_features.csv';old=pd.read_csv(path) if path.exists() else pd.DataFrame();parts=[];cur=pd.Timestamp(start);finish=pd.Timestamp(end)
 while cur<finish:
  nxt=min(cur+pd.Timedelta(days=chunk_days),finish);a=cur.strftime('%d-%m-%Y');b=nxt.strftime('%d-%m-%Y');print('options',a,b,flush=True)
  try:
   frames=[]
   for typ in ['CE','PE']:frames.append(derivatives.option_price_volume_data('NIFTY','OPTIDX',typ,from_date=a,to_date=b))
   parts.append(aggregate_options(pd.concat(frames,ignore_index=True)))
  except Exception as e:print('  failed',e,flush=True)
  cur=nxt+pd.Timedelta(days=1);time.sleep(.25)
 new=pd.concat([old,*parts],ignore_index=True) if parts or not old.empty else pd.DataFrame()
 if not new.empty:new=new.drop_duplicates('date',keep='last').sort_values('date');new.to_csv(path,index=False)
 return new

def fetch_futures(start,end):
 a=pd.Timestamp(start).strftime('%d-%m-%Y');b=pd.Timestamp(end).strftime('%d-%m-%Y');print('futures',a,b,flush=True)
 d=derivatives.future_price_volume_data('NIFTY','FUTIDX',from_date=a,to_date=b);d['date']=pd.to_datetime(d.TIMESTAMP,dayfirst=True,errors='coerce');d['expiry']=pd.to_datetime(d.EXPIRY_DT,dayfirst=True,errors='coerce')
 for c in ['CLOSING_PRICE','OPEN_INT','CHANGE_IN_OI','TOT_TRADED_QTY','UNDERLYING_VALUE']:d[c]=pd.to_numeric(d[c],errors='coerce')
 rows=[]
 for day,g in d.dropna(subset=['date','expiry']).groupby('date'):
  q=g[g.expiry>=day].sort_values('expiry');
  if q.empty:continue
  near=q.iloc[0];nxt=q.iloc[1] if len(q)>1 else None;total=q.OPEN_INT.sum();spot=near.UNDERLYING_VALUE
  rows.append({'date':day.date().isoformat(),'future_expiry':near.expiry.date().isoformat(),'future_close':near.CLOSING_PRICE,'future_basis_pct':near.CLOSING_PRICE/spot-1,
   'future_oi':near.OPEN_INT,'future_change_oi':near.CHANGE_IN_OI,'future_volume':near.TOT_TRADED_QTY,'near_oi_share':near.OPEN_INT/max(total,1),
   'next_near_spread_pct':(nxt.CLOSING_PRICE/near.CLOSING_PRICE-1) if nxt is not None else np.nan})
 out=pd.DataFrame(rows).drop_duplicates('date',keep='last').sort_values('date');out.to_csv(OUT/'historical_futures_features.csv',index=False);return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--start',default='2024-09-20');ap.add_argument('--end',default='2026-09-19');args=ap.parse_args()
 o=fetch_options(args.start,args.end);f=fetch_futures(args.start,args.end);print('DONE option sessions',len(o),'futures sessions',len(f))
if __name__=='__main__':main()
