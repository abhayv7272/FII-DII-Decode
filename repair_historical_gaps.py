from __future__ import annotations
from pathlib import Path
import pandas as pd
from src.data_hub import bhavcopy_filtered,summarize_options,participant_nselib,summarize_participant,append_history

def main():
 o=pd.read_csv('data/historical_option_features.csv');f=pd.read_csv('data/historical_futures_features.csv');missing=sorted(set(f.date.astype(str))-set(o.date.astype(str)));ok=[];failed=[]
 for i,date in enumerate(missing,1):
  try:
   row=summarize_options(bhavcopy_filtered(date,'option'))
   if row.empty:raise ValueError('empty option summary')
   append_history(Path('data/historical_option_features.csv'),row)
   try:append_history(Path('data/historical_participant_oi.csv'),summarize_participant(participant_nselib(date),date))
   except Exception:pass
   ok.append(date);print(i,'/',len(missing),date,'OK',flush=True)
  except Exception as e:failed.append({'date':date,'error':str(e)});print(i,'/',len(missing),date,'FAIL',e,flush=True)
 print('REPAIRED',len(ok),'FAILED',len(failed));
 if failed:pd.DataFrame(failed).to_csv('reports/history_repair_failures.csv',index=False)
if __name__=='__main__':main()
