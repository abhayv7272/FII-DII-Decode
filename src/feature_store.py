from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd

PROJECT=Path(__file__).resolve().parents[1]
FORWARD=PROJECT/'data'/'forward'

def _num(x): return pd.to_numeric(x,errors='coerce')

def build_session_features(session_date:str)->dict:
    """Aggregate only snapshots captured for D; never reads D+1 market outcomes."""
    root=FORWARD/session_date; row={'session_date':session_date}
    if not root.exists(): return row
    option=[]; pre=[]; manifests=[]
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        m=folder/'manifest.json'
        if m.exists():
            try:
                manifests.append(json.loads(m.read_text()))
            except (json.JSONDecodeError, OSError) as exc:
                manifests.append({'records':[{'status':'failed','error':f'invalid manifest: {exc}'}]})
        p=folder/'nifty_option_summary.csv'
        if p.exists():
            q=pd.read_csv(p); q['capture_key']=folder.name; option.append(q)
        p=folder/'preopen_constituents.csv'
        if p.exists(): pre.append(pd.read_csv(p))
    if option:
        q=pd.concat(option,ignore_index=True).sort_values('capture_key'); row['option_captures']=len(q)
        metrics=['pcr_oi','call_oi_total','put_oi_total','call_change_oi_total','put_change_oi_total','call_volume_total','put_volume_total','median_call_iv','median_put_iv']
        for col in metrics:
            if col in q:
                vals=_num(q[col]); row[f'{col}_first']=vals.iloc[0];row[f'{col}_last']=vals.iloc[-1]
                row[f'{col}_change']=vals.iloc[-1]-vals.iloc[0];row[f'{col}_min']=vals.min();row[f'{col}_max']=vals.max()
        for col in ['call_wall','put_wall','call_build_wall','put_build_wall']:
            if col in q:
                vals=_num(q[col]);row[f'{col}_first']=vals.iloc[0];row[f'{col}_last']=vals.iloc[-1];row[f'{col}_migration']=vals.iloc[-1]-vals.iloc[0]
        if {'put_volume_total','call_volume_total'}.issubset(q): row['option_volume_pcr_last']=float(q.put_volume_total.iloc[-1]/max(q.call_volume_total.iloc[-1],1))
        if {'median_put_iv','median_call_iv'}.issubset(q): row['iv_skew_last']=float(q.median_put_iv.iloc[-1]-q.median_call_iv.iloc[-1])
    else: row['option_captures']=0
    if pre:
        p=pd.concat(pre,ignore_index=True).drop_duplicates('symbol',keep='last'); pc=_num(p.get('pchange',pd.Series(dtype=float)))
        row.update({'preopen_constituents':len(p),'preopen_advances':int((pc>0).sum()),'preopen_declines':int((pc<0).sum()),
          'preopen_unchanged':int((pc==0).sum()),'preopen_mean_pct':float(pc.mean()),'preopen_median_pct':float(pc.median())})
        if {'buy_qty','sell_qty'}.issubset(p):
            buy=_num(p.buy_qty).sum();sell=_num(p.sell_qty).sum();row['preopen_order_imbalance']=float((buy-sell)/max(buy+sell,1))
    row['manifest_count']=len(manifests)
    row['failed_sources']=sum(1 for m in manifests for r in m.get('records',[]) if r.get('status') not in {'ok','partial'})
    # Calendar/regime context known before D+1; expiry proximity is intentionally not guessed.
    d=pd.Timestamp(session_date);row['day_of_week']=d.dayofweek;row['month']=d.month;row['month_end_proximity']=int((d+pd.offsets.BMonthEnd(0)-d).days)
    return row

def update_feature_store(session_date:str)->pd.DataFrame:
    feature=build_session_features(session_date)
    eod=PROJECT/'data'/'eod_research_snapshots.csv'
    if eod.exists():
        q=pd.read_csv(eod); hit=q[q.session_date.astype(str)==session_date]
        if not hit.empty: feature.update(hit.iloc[-1].to_dict())
    out=PROJECT/'data'/'model_feature_store.csv'; old=pd.read_csv(out) if out.exists() else pd.DataFrame()
    if not old.empty and 'session_date' in old: old=old[old.session_date.astype(str)!=session_date]
    result=pd.concat([old,pd.DataFrame([feature])],ignore_index=True).sort_values('session_date')
    result.to_csv(out,index=False);return result
