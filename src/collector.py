from __future__ import annotations
import argparse, hashlib, json, os, sys
from dataclasses import asdict, dataclass
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

IST=ZoneInfo('Asia/Kolkata')
BASE=Path(__file__).resolve().parents[1]/'data'/'forward'

@dataclass
class Record:
    dataset:str; session_date:str; captured_ist:str; status:str; rows:int=0
    source_timestamp:str|None=None; sha256:str|None=None; path:str|None=None; error:str|None=None

def _hash(path:Path): return hashlib.sha256(path.read_bytes()).hexdigest()
def _safe_name(s): return ''.join(c if c.isalnum() or c in '-_' else '_' for c in s)

def save_frame(name:str, session_date:str, df:pd.DataFrame, now:datetime)->Record:
    folder=BASE/session_date/now.strftime('%H%M%S'); folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'{_safe_name(name)}.csv'; df.to_csv(path,index=False)
    return Record(name,session_date,now.isoformat(),'ok',len(df),sha256=_hash(path),path=str(path.relative_to(BASE.parent.parent)))

def save_json(name:str, session_date:str, obj, now:datetime)->Record:
    folder=BASE/session_date/now.strftime('%H%M%S'); folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'{_safe_name(name)}.json'; path.write_text(json.dumps(obj,indent=2,default=str),encoding='utf-8')
    rows=len(obj) if isinstance(obj,(list,dict)) else 1
    return Record(name,session_date,now.isoformat(),'ok',rows,sha256=_hash(path),path=str(path.relative_to(BASE.parent.parent)))

def manifest(records:list[Record], mode:str, session_date:str, now:datetime):
    BASE.mkdir(parents=True,exist_ok=True); row={'mode':mode,'session_date':session_date,'captured_ist':now.isoformat(),'records':[asdict(r) for r in records]}
    p=BASE/session_date/now.strftime('%H%M%S')/'manifest.json'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(row,indent=2),encoding='utf-8')
    index=BASE/'collection_log.csv'; flat=[{'mode':mode,**asdict(r)} for r in records]
    pd.DataFrame(flat).to_csv(index,mode='a',header=not index.exists(),index=False)
    return p

def nse_json(endpoint:str):
    import requests
    s=requests.Session(); headers={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36','Accept':'application/json,text/plain,*/*','Referer':'https://www.nseindia.com/'}
    s.get('https://www.nseindia.com/',headers=headers,timeout=15)
    r=s.get('https://www.nseindia.com'+endpoint,headers=headers,timeout=25); r.raise_for_status(); return r.json()

def collect_preopen(session_date:str, now:datetime):
    if not (time(9,0)<=now.time()<=time(9,14,59)): raise ValueError('Pre-open capture rejected: run only 09:00–09:14:59 IST.')
    obj=nse_json('/api/market-data-pre-open?key=NIFTY')
    rec=save_json('nse_preopen_raw',session_date,obj,now)
    # Preserve constituent records without inventing a weighted index.
    rows=[]
    for item in obj.get('data',[]):
        meta=item.get('metadata',{}); detail=item.get('detail',{}); pre=detail.get('preOpenMarket',{})
        rows.append({'symbol':meta.get('symbol'),'previous_close':meta.get('previousClose'),'iep':pre.get('IEP'),
          'change':meta.get('change'),'pchange':meta.get('pChange'),'buy_qty':pre.get('totalBuyQuantity'),'sell_qty':pre.get('totalSellQuantity'),
          'source_timestamp':meta.get('lastUpdateTime')})
    return [rec,save_frame('preopen_constituents',session_date,pd.DataFrame(rows),now)]

def collect_intraday(session_date:str, now:datetime):
    from nselib import derivatives
    from .decoder import normalize_chain
    chain=derivatives.nse_live_option_chain('NIFTY',oi_mode='full')
    records=[save_frame('nifty_option_chain',session_date,chain,now)]
    # Reject implausible empty snapshots.
    if len(chain)<10:
        records[0].status='quality_failed'; records[0].error='Option chain has fewer than 10 rows.'; return records
    try:
        q=normalize_chain(chain)
        summary=pd.DataFrame([{'call_oi_total':q.call_oi.sum(),'put_oi_total':q.put_oi.sum(),
          'pcr_oi':q.put_oi.sum()/max(q.call_oi.sum(),1),'call_change_oi_total':q.call_change_oi.sum(),
          'put_change_oi_total':q.put_change_oi.sum(),'call_volume_total':q.call_volume.sum(),'put_volume_total':q.put_volume.sum(),
          'call_wall':q.loc[q.call_oi.idxmax(),'strike'],'put_wall':q.loc[q.put_oi.idxmax(),'strike'],
          'call_build_wall':q.loc[q.call_change_oi.idxmax(),'strike'],'put_build_wall':q.loc[q.put_change_oi.idxmax(),'strike'],
          'median_call_iv':q.call_iv.replace(0,np.nan).median(),'median_put_iv':q.put_iv.replace(0,np.nan).median()}])
        records.append(save_frame('nifty_option_summary',session_date,summary,now))
    except Exception as e: records.append(Record('nifty_option_summary',session_date,now.isoformat(),'failed',error=str(e)[:500]))
    return records

def collect_cross_market_context(session_date:str,now:datetime):
    """Collect only timing-safe EOD context. US/global daily bars must predate D."""
    import yfinance as yf
    session=pd.Timestamp(session_date)
    groups={
      'india_sector': ['^NSEBANK','^CNXIT','^CNXAUTO','^CNXPHARMA','^CNXMETAL','^CNXENERGY'],
      'india_heavyweight': ['HDFCBANK.NS','ICICIBANK.NS','RELIANCE.NS','INFY.NS','TCS.NS','BHARTIARTL.NS','SBIN.NS','ITC.NS','LT.NS','AXISBANK.NS'],
      'asia': ['^N225','^HSI'],
      'prior_global': ['SPY','QQQ','^VIX','DX-Y.NYB','CL=F','GC=F','USDINR=X']}
    rows=[]
    start=(session-pd.Timedelta(days=15)).strftime('%Y-%m-%d'); end=(session+pd.Timedelta(days=2)).strftime('%Y-%m-%d')
    for group,tickers in groups.items():
        for ticker in tickers:
            try:
                d=yf.download(ticker,start=start,end=end,interval='1d',auto_adjust=False,progress=False,threads=False)
                if isinstance(d.columns,pd.MultiIndex): d.columns=d.columns.get_level_values(0)
                d.index=pd.to_datetime(d.index).tz_localize(None).normalize(); d=d.dropna(subset=['Close'])
                # At 21:00 IST, same-date US/FX/commodity daily candles may be incomplete.
                eligible=d[d.index<session] if group=='prior_global' else d[d.index<=session]
                if len(eligible)<2: raise ValueError('fewer than two timing-safe completed bars')
                last,prev=eligible.iloc[-1],eligible.iloc[-2]
                rows.append({'group':group,'ticker':ticker,'source_date':eligible.index[-1].date().isoformat(),
                  'close':float(last.Close),'return_1d':float(last.Close/prev.Close-1),'volume':float(last.get('Volume',0) or 0),
                  'timing_rule':'strictly_before_D' if group=='prior_global' else 'at_or_before_D','status':'ok'})
            except Exception as e:
                rows.append({'group':group,'ticker':ticker,'source_date':None,'close':None,'return_1d':None,'volume':None,
                  'timing_rule':'strictly_before_D' if group=='prior_global' else 'at_or_before_D','status':'failed','error':str(e)[:200]})
    df=pd.DataFrame(rows)
    ok=df[df.status=='ok']; summary=[]
    for group,g in ok.groupby('group'):
        summary.append({'group':group,'instruments':len(g),'advances':int((g.return_1d>0).sum()),'declines':int((g.return_1d<0).sum()),
          'unchanged':int((g.return_1d==0).sum()),'mean_return':float(g.return_1d.mean()),'median_return':float(g.return_1d.median()),
          'dispersion':float(g.return_1d.std(ddof=0))})
    return df,pd.DataFrame(summary)

def collect_eod(session_date:str,now:datetime):
    from nselib import capital_market,derivatives
    session_dt=datetime.strptime(session_date,'%Y-%m-%d'); d=session_dt.strftime('%d-%m-%Y')
    next_d=(session_dt+pd.Timedelta(days=1)).strftime('%d-%m-%Y'); records=[]
    jobs=[('participant_oi',lambda:derivatives.participant_wise_open_interest(d)),
          ('participant_volume',lambda:derivatives.participant_wise_trading_volume(d)),
          ('fii_derivatives',lambda:derivatives.fii_derivatives_statistics(d)),
          ('nifty_futures_eod',lambda:derivatives.future_price_volume_data('NIFTY','FUTIDX',from_date=d,to_date=next_d)),
          ('india_vix',lambda:capital_market.india_vix_data(from_date=d,to_date=next_d))]
    for name,fn in jobs:
        try:
            df=fn(); records.append(save_frame(name,session_date,df,now))
            if df.empty: records[-1].status='quality_failed'; records[-1].error='Empty dataset.'
        except Exception as e: records.append(Record(name,session_date,now.isoformat(),'failed',error=str(e)[:500]))
    try: records.append(save_json('fii_dii_cash_latest',session_date,nse_json('/api/fiidiiTradeReact'),now))
    except Exception as e: records.append(Record('fii_dii_cash_latest',session_date,now.isoformat(),'failed',error=str(e)[:500]))
    try:
        detail,summary=collect_cross_market_context(session_date,now)
        records.append(save_frame('cross_market_detail',session_date,detail,now))
        records.append(save_frame('cross_market_summary',session_date,summary,now))
        failed=int((detail.status!='ok').sum())
        if failed: records[-2].status='partial'; records[-2].error=f'{failed} instruments failed'
    except Exception as e:
        records.append(Record('cross_market_detail',session_date,now.isoformat(),'failed',error=str(e)[:500]))
        records.append(Record('cross_market_summary',session_date,now.isoformat(),'failed',error=str(e)[:500]))
    return records

def build_eod_snapshot(records:list[Record],session_date:str,now:datetime):
    """Create one leakage-safe feature row using only files captured in this EOD run."""
    project=BASE.parent.parent; by={r.dataset:r for r in records if r.status in {'ok','partial'} and r.path}
    row={'session_date':session_date,'decision_ist':now.isoformat(),'quality_ok':False}
    required={'participant_oi','participant_volume','india_vix','fii_dii_cash_latest'}
    row['missing_sources']='|'.join(sorted(required-set(by)))
    if 'participant_oi' in by:
        oi=pd.read_csv(project/by['participant_oi'].path); oi.columns=[str(c).strip() for c in oi.columns]
        oi['Client Type']=oi['Client Type'].astype(str).str.strip()
        for participant in ['FII','DII','Client','Pro']:
            q=oi[oi['Client Type'].str.casefold()==participant.casefold()]
            if not q.empty:
                row[f'{participant.lower()}_index_futures_net']=float(q.iloc[0]['Future Index Long'])-float(q.iloc[0]['Future Index Short'])
                row[f'{participant.lower()}_total_net']=float(q.iloc[0]['Total Long Contracts'])-float(q.iloc[0]['Total Short Contracts'])
    if 'participant_volume' in by:
        vol=pd.read_csv(project/by['participant_volume'].path); vol.columns=[str(c).strip() for c in vol.columns]
        vol['Client Type']=vol['Client Type'].astype(str).str.strip()
        for participant in ['FII','DII','Client','Pro']:
            q=vol[vol['Client Type'].str.casefold()==participant.casefold()]
            if not q.empty: row[f'{participant.lower()}_index_futures_volume']=float(q.iloc[0]['Future Index Long'])+float(q.iloc[0]['Future Index Short'])
    if 'india_vix' in by:
        v=pd.read_csv(project/by['india_vix'].path)
        if not v.empty:
            row['india_vix_close']=float(v.iloc[-1]['CLOSE_INDEX_VAL']); row['india_vix_change_pct']=float(v.iloc[-1]['VIX_PERC_CHG'])
    if 'nifty_futures_eod' in by:
        fut=pd.read_csv(project/by['nifty_futures_eod'].path); fut['EXPIRY_PARSED']=pd.to_datetime(fut['EXPIRY_DT'],errors='coerce')
        fut=fut.sort_values('EXPIRY_PARSED')
        if not fut.empty:
            near=fut.iloc[0];spot=float(near.get('UNDERLYING_VALUE',np.nan));fclose=float(near.get('CLOSING_PRICE',np.nan))
            row['nifty_future_near_expiry']=str(near.get('EXPIRY_DT'));row['nifty_future_close']=fclose
            row['nifty_future_basis_pct']=fclose/spot-1 if spot else np.nan;row['nifty_future_open_interest']=float(near.get('OPEN_INT',np.nan))
            row['nifty_future_change_oi']=float(near.get('CHANGE_IN_OI',np.nan));row['nifty_future_volume']=float(near.get('TOT_TRADED_QTY',np.nan))
            total_oi=pd.to_numeric(fut['OPEN_INT'],errors='coerce').sum();row['nifty_future_near_oi_share']=float(near.get('OPEN_INT',0))/total_oi if total_oi else np.nan
    if 'fii_dii_cash_latest' in by:
        cash=json.loads((project/by['fii_dii_cash_latest'].path).read_text())
        dates=set()
        for z in cash:
            dates.add(datetime.strptime(z['date'],'%d-%b-%Y').date().isoformat())
            key='fii' if str(z['category']).upper().startswith('FII') else 'dii'
            row[f'{key}_cash_net_cr']=float(z['netValue'])
        row['cash_source_date']='|'.join(sorted(dates))
        if dates!={session_date}: row['missing_sources']=(row['missing_sources']+'|cash_date_mismatch').strip('|')
    if 'cross_market_summary' in by:
        cm=pd.read_csv(project/by['cross_market_summary'].path)
        for _,z in cm.iterrows():
            key=str(z['group']).lower()
            for col in ['instruments','advances','declines','unchanged','mean_return','median_return','dispersion']:
                row[f'{key}_{col}']=z[col]
    if 'cross_market_detail' in by:
        detail=pd.read_csv(project/by['cross_market_detail'].path)
        for _,z in detail[detail.status=='ok'].iterrows():
            key=''.join(c.lower() if c.isalnum() else '_' for c in str(z.ticker)).strip('_')
            row[f'asset_{key}_return_1d']=z.return_1d; row[f'asset_{key}_source_date']=z.source_date
    row['quality_ok']=not bool(row['missing_sources'])
    out=project/'data'/'eod_research_snapshots.csv'; out.parent.mkdir(parents=True,exist_ok=True)
    old=pd.read_csv(out) if out.exists() else pd.DataFrame()
    new=pd.concat([old[old.session_date.astype(str)!=session_date] if not old.empty and 'session_date' in old else old,pd.DataFrame([row])],ignore_index=True)
    new.to_csv(out,index=False)
    return row

def main():
    ap=argparse.ArgumentParser(description='Timestamped NSE forward-data collector')
    ap.add_argument('mode',choices=['preopen','intraday','eod']); ap.add_argument('--date',help='Session YYYY-MM-DD; defaults to current IST date')
    args=ap.parse_args(); now=datetime.now(IST); session=args.date or now.date().isoformat()
    try:
        records={'preopen':collect_preopen,'intraday':collect_intraday,'eod':collect_eod}[args.mode](session,now)
    except Exception as e:
        records=[Record(args.mode,session,now.isoformat(),'failed',error=str(e)[:500])]
    snapshot=None
    if args.mode=='eod':
        try: snapshot=build_eod_snapshot(records,session,now)
        except Exception as e: snapshot={'quality_ok':False,'snapshot_error':str(e)[:500]}
    p=manifest(records,args.mode,session,now)
    feature_status=None
    try:
        from .feature_store import update_feature_store
        store=update_feature_store(session); feature_status={'rows':len(store),'path':'data/model_feature_store.csv'}
    except Exception as e: feature_status={'error':str(e)[:500]}
    print(json.dumps({'manifest':str(p),'records':[asdict(r) for r in records],'snapshot':snapshot,'feature_store':feature_status},indent=2))
    if not all(r.status in {'ok','partial'} for r in records): sys.exit(2)
if __name__=='__main__': main()
