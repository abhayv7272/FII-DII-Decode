from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import time
import pandas as pd
from nselib import derivatives


def one(date):
 d=pd.Timestamp(date);key=d.date().isoformat()
 for attempt in range(3):
  try:
   q=derivatives.participant_wise_open_interest(d.strftime('%d-%m-%Y'));q.columns=[str(c).strip() for c in q.columns];q['Client Type']=q['Client Type'].astype(str).str.strip();row={'date':key}
   for name in ['FII','DII','Client','Pro']:
    z=q[q['Client Type'].str.casefold()==name.casefold()]
    if z.empty:continue
    z=z.iloc[0];pre=name.lower()
    row[f'{pre}_index_future_net']=float(z['Future Index Long'])-float(z['Future Index Short'])
    row[f'{pre}_stock_future_net']=float(z['Future Stock Long'])-float(z['Future Stock Short'])
    row[f'{pre}_index_call_net']=float(z['Option Index Call Long'])-float(z['Option Index Call Short'])
    row[f'{pre}_index_put_net']=float(z['Option Index Put Long'])-float(z['Option Index Put Short'])
    row[f'{pre}_index_option_direction']=row[f'{pre}_index_call_net']-row[f'{pre}_index_put_net']
    row[f'{pre}_total_net']=float(z['Total Long Contracts'])-float(z['Total Short Contracts'])
   return row
  except Exception as e:
   if attempt==2:return {'date':key,'error':str(e)[:160]}
   time.sleep(1+attempt)

def main():
 dates=pd.read_csv('data/historical_option_features.csv').date.astype(str).tolist();rows=[]
 with ThreadPoolExecutor(max_workers=3) as ex:
  fut={ex.submit(one,d):d for d in dates}
  for i,f in enumerate(as_completed(fut),1):
   rows.append(f.result())
   if i%50==0:print(i,'/',len(dates),flush=True)
 out=pd.DataFrame(rows).sort_values('date');ok=out[out.get('error',pd.Series(index=out.index,dtype=object)).isna()] if 'error' in out else out
 ok.to_csv('data/historical_participant_oi.csv',index=False);print('DONE',len(ok),'of',len(dates),'failed',len(dates)-len(ok))
if __name__=='__main__':main()
