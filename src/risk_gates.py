from __future__ import annotations
from pathlib import Path
import pandas as pd

def event_risk(as_of,calendar_path='data/event_calendar.csv',lookahead_days=1):
    p=Path(calendar_path)
    if not p.exists():return {'blocked':False,'status':'NO_VERIFIED_CALENDAR','events':[]}
    d=pd.read_csv(p);date_col=next((c for c in d if c.lower()=='date'),None)
    if not date_col:return {'blocked':True,'status':'INVALID_CALENDAR','events':[]}
    d[date_col]=pd.to_datetime(d[date_col],errors='coerce');start=pd.Timestamp(as_of).normalize();end=start+pd.Timedelta(days=lookahead_days)
    hit=d[(d[date_col]>start)&(d[date_col]<=end)];severe=hit[hit.get('Severity',pd.Series('',index=hit.index)).astype(str).str.upper().eq('HIGH')]
    return {'blocked':not severe.empty,'status':'HIGH_EVENT_RISK' if not severe.empty else 'CLEAR','events':hit.to_dict('records')}

def combined_risk_gate(*,event,abnormal_gap=False,missing_option_data=False,participant_conflict=False,spread_ok=True):
    reasons=[]
    if event.get('blocked'):reasons.append('high-impact event')
    if abnormal_gap:reasons.append('abnormal opening gap')
    if missing_option_data:reasons.append('missing option-chain confirmation')
    if participant_conflict:reasons.append('FII–Pro conflict')
    if not spread_ok:reasons.append('spread/slippage too high')
    return {'allow_trade':not reasons,'reasons':reasons}
