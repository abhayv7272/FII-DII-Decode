from __future__ import annotations
import argparse,hashlib,json,os,time
from dataclasses import asdict,dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd

IST=ZoneInfo('Asia/Kolkata');PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT/'data'/'hub';CACHE=ROOT/'last_good'

@dataclass
class SourceResult:
 dataset:str;source:str;status:str;as_of:str|None;rows:int;latency_ms:int;path:str|None=None;sha256:str|None=None;error:str|None=None;stale_days:int|None=None

def _sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def _atomic_text(path,text):
 path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(text,encoding='utf-8');os.replace(tmp,path)
def _save(dataset,source,df,run_dir):
 p=run_dir/f'{dataset}__{source}.csv';df.to_csv(p,index=False);return p

def _datefmt(d):return pd.Timestamp(d).strftime('%d-%m-%Y')
def _max_mixed_date(values):return pd.to_datetime(values,format='mixed',dayfirst=True,errors='coerce').max()
def _retry(fn,attempts=3):
 err=None
 for i in range(attempts):
  try:return fn()
  except Exception as e:err=e;time.sleep(.8*(i+1))
 raise err

def yahoo_history(ticker='^NSEI',period='10y'):
 import yfinance as yf
 d=yf.download(ticker,period=period,interval='1d',auto_adjust=False,progress=False,threads=False)
 if isinstance(d.columns,pd.MultiIndex):d.columns=d.columns.get_level_values(0)
 d=d[['Open','High','Low','Close','Volume']].dropna(subset=['Close']);d.index=pd.to_datetime(d.index).tz_localize(None).normalize();d.index.name='Date';return d.reset_index()
def nse_index_history(end):
 from nselib import capital_market
 start=(pd.Timestamp(end)-pd.Timedelta(days=3650)).strftime('%d-%m-%Y');stop=(pd.Timestamp(end)+pd.Timedelta(days=1)).strftime('%d-%m-%Y')
 d=capital_market.index_data('NIFTY 50',from_date=start,to_date=stop)
 if d.empty:raise ValueError('empty NSE index history')
 return pd.DataFrame({'Date':pd.to_datetime(d.TIMESTAMP,dayfirst=True),'Open':pd.to_numeric(d.OPEN_INDEX_VAL),'High':pd.to_numeric(d.HIGH_INDEX_VAL),'Low':pd.to_numeric(d.LOW_INDEX_VAL),'Close':pd.to_numeric(d.CLOSE_INDEX_VAL),'Volume':pd.to_numeric(d.TRADED_QTY,errors='coerce').fillna(0)}).sort_values('Date')
def yahoo_chart(ticker,start,end):
 import requests
 p1=int(pd.Timestamp(start,tz='UTC').timestamp());p2=int((pd.Timestamp(end,tz='UTC')+pd.Timedelta(days=1)).timestamp())
 u=f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={p1}&period2={p2}&interval=1d&events=history'
 j=requests.get(u,headers={'User-Agent':'Mozilla/5.0'},timeout=20).json()['chart']['result'][0];q=j['indicators']['quote'][0]
 return pd.DataFrame({'Date':pd.to_datetime(j['timestamp'],unit='s',utc=True).tz_convert(None).normalize(),'Open':q['open'],'High':q['high'],'Low':q['low'],'Close':q['close'],'Volume':q['volume']}).dropna(subset=['Close'])
def participant_nselib(session):
 from nselib import derivatives
 return derivatives.participant_wise_open_interest(_datefmt(session))
def participant_archive(session):
 import requests
 u=f"https://nsearchives.nseindia.com/content/nsccl/fao_participant_oi_{pd.Timestamp(session).strftime('%d%m%Y')}.csv"
 r=requests.get(u,headers={'User-Agent':'Mozilla/5.0'},timeout=25);r.raise_for_status();return pd.read_csv(BytesIO(r.content),skiprows=1,on_bad_lines='skip')
def futures_nselib(session):
 from nselib import derivatives
 d=pd.Timestamp(session);return derivatives.future_price_volume_data('NIFTY','FUTIDX',from_date=_datefmt(d),to_date=_datefmt(d+pd.Timedelta(days=1)))
def bhavcopy_filtered(session,kind):
 """Normalize both modern NSE UDiFF and legacy bhavcopy schemas."""
 from nselib import derivatives
 d=derivatives.fno_bhav_copy(_datefmt(session))
 if {'FinInstrmTp','TckrSymb'}.issubset(d.columns):
  code='IDF' if kind=='future' else 'IDO';q=d[(d.FinInstrmTp.eq(code))&(d.TckrSymb.eq('NIFTY'))].copy()
  if q.empty:raise ValueError(f'No NIFTY {kind} rows in UDiFF bhavcopy')
  out=q.rename(columns={'TradDt':'TIMESTAMP','XpryDt':'EXPIRY_DT','StrkPric':'STRIKE_PRICE','OptnTp':'OPTION_TYPE',
    'OpnPric':'OPENING_PRICE','HghPric':'TRADE_HIGH_PRICE','LwPric':'TRADE_LOW_PRICE','ClsPric':'CLOSING_PRICE',
    'LastPric':'LAST_TRADED_PRICE','PrvsClsgPric':'PREV_CLS','SttlmPric':'SETTLE_PRICE','TtlTradgVol':'TRADED_CONTRACTS',
    'OpnIntrst':'OPEN_INT','ChngInOpnIntrst':'CHANGE_IN_OI','NewBrdLotQty':'MARKET_LOT','UndrlygPric':'UNDERLYING_VALUE'})
  # Contract archive reports quantity; UDiFF bhavcopy reports traded contracts. Normalize to quantity.
  out['TOT_TRADED_QTY']=pd.to_numeric(out['TRADED_CONTRACTS'],errors='coerce').fillna(0)*pd.to_numeric(out['MARKET_LOT'],errors='coerce').fillna(1)
  return out
 cols={str(c).upper():c for c in d.columns};inst=cols.get('INSTRUMENT');symbol=cols.get('SYMBOL')
 if inst and symbol:
  token='FUT' if kind=='future' else 'OPT';q=d[(d[inst].astype(str).str.contains(token,case=False,na=False))&(d[symbol].astype(str).eq('NIFTY'))]
  if not q.empty:return q
 raise ValueError('Bhavcopy schema cannot be normalized automatically')
def options_nselib(session):
 from nselib import derivatives
 d=pd.Timestamp(session);a=_datefmt(d);b=_datefmt(d+pd.Timedelta(days=1));return pd.concat([derivatives.option_price_volume_data('NIFTY','OPTIDX',t,from_date=a,to_date=b) for t in ['CE','PE']],ignore_index=True)
def vix_nse(session):
 from nselib import capital_market
 d=pd.Timestamp(session);return capital_market.india_vix_data(from_date=_datefmt(d),to_date=_datefmt(d+pd.Timedelta(days=1)))
def vix_yahoo(session):return yahoo_chart('%5EINDIAVIX',pd.Timestamp(session)-pd.Timedelta(days=7),session)
def fii_cash_nse(session):
 from .collector import nse_json
 j=nse_json('/api/fiidiiTradeReact');return pd.DataFrame(j)
def fii_cash_groww(session):
 tables=pd.read_html('https://groww.in/fii-dii-data');d=tables[0];row=d.iloc[0]
 return pd.DataFrame([{'category':'FII/FPI','date':row.iloc[0],'buyValue':row.iloc[1],'sellValue':row.iloc[2],'netValue':row.iloc[3]},
                      {'category':'DII','date':row.iloc[0],'buyValue':row.iloc[4],'sellValue':row.iloc[5],'netValue':row.iloc[6]}])
def cross_yfinance(session):
 from .collector import collect_cross_market_context
 detail,summary=collect_cross_market_context(session,datetime.now(IST));return detail
def cross_yahoo_chart(session):
 groups={'india':['%5ENSEBANK','%5ECNXIT','%5EBSESN','%5EINDIAVIX'],'asia':['%5EN225','%5EHSI'],'global':['SPY','QQQ','%5EVIX','DX-Y.NYB','CL%3DF','GC%3DF','USDINR%3DX']};rows=[];s=pd.Timestamp(session)
 for group,tickers in groups.items():
  for ticker in tickers:
   d=yahoo_chart(ticker,s-pd.Timedelta(days=15),s);eligible=d[pd.to_datetime(d.Date)<s] if group=='global' else d[pd.to_datetime(d.Date)<=s]
   if len(eligible)<2:continue
   a,b=eligible.iloc[-2],eligible.iloc[-1];rows.append({'group':group,'ticker':ticker,'source_date':str(pd.Timestamp(b.Date).date()),'close':b.Close,'return_1d':b.Close/a.Close-1,'volume':b.Volume,'timing_rule':'strictly_before_D' if group=='global' else 'at_or_before_D','status':'ok'})
 return pd.DataFrame(rows)

def summarize_futures(d):
 x=d.copy();ren={'EXPIRY_DT':'expiry','CLOSING_PRICE':'close','OPEN_INT':'oi','CHANGE_IN_OI':'change_oi','TOT_TRADED_QTY':'volume','UNDERLYING_VALUE':'spot','TIMESTAMP':'date'};x=x.rename(columns=ren)
 for c in ['close','oi','change_oi','volume','spot']:x[c]=pd.to_numeric(x[c],errors='coerce')
 x['expiry']=pd.to_datetime(x.expiry,format='mixed',dayfirst=True,errors='coerce');x=x.sort_values('expiry');near=x.iloc[0];nxt=x.iloc[1] if len(x)>1 else None;tot=x.oi.sum()
 return pd.DataFrame([{'date':pd.to_datetime(near['date'],format='mixed',dayfirst=True).date().isoformat(),'future_expiry':near.expiry.date().isoformat(),'future_close':near.close,'future_basis_pct':near.close/near.spot-1,'future_oi':near.oi,'future_change_oi':near.change_oi,'future_volume':near.volume,'near_oi_share':near.oi/max(tot,1),'next_near_spread_pct':nxt.close/near.close-1 if nxt is not None else np.nan}])
def summarize_options(d):
 from fetch_historical_derivatives import aggregate_options
 return aggregate_options(d)

def summarize_participant(d,session):
 q=d.copy();q.columns=[str(c).strip() for c in q.columns];q['Client Type']=q['Client Type'].astype(str).str.strip();row={'date':session}
 for name in ['FII','DII','Client','Pro']:
  hit=q[q['Client Type'].str.casefold()==name.casefold()]
  if hit.empty:continue
  z=hit.iloc[0];pre=name.lower()
  row[f'{pre}_index_future_net']=float(z['Future Index Long'])-float(z['Future Index Short'])
  row[f'{pre}_stock_future_net']=float(z['Future Stock Long'])-float(z['Future Stock Short'])
  row[f'{pre}_index_call_net']=float(z['Option Index Call Long'])-float(z['Option Index Call Short'])
  row[f'{pre}_index_put_net']=float(z['Option Index Put Long'])-float(z['Option Index Put Short'])
  row[f'{pre}_index_option_direction']=row[f'{pre}_index_call_net']-row[f'{pre}_index_put_net']
  row[f'{pre}_total_net']=float(z['Total Long Contracts'])-float(z['Total Short Contracts'])
 return pd.DataFrame([row])

def truncate_price_history(price,session,min_rows=200):
 out=price[pd.to_datetime(price.Date).dt.normalize()<=pd.Timestamp(session)].copy().sort_values('Date')
 if len(out)<min_rows or pd.to_datetime(out.Date).max().date()!=pd.Timestamp(session).date():raise ValueError(f'No completed NIFTY candle for requested session {session}')
 return out

def append_history(path,row):
 """Idempotent, atomic history update; a crash cannot leave a half-written CSV."""
 if row is None or row.empty or 'date' not in row:raise ValueError(f'Invalid history row for {path}')
 old=pd.read_csv(path) if path.exists() else pd.DataFrame();new=pd.concat([old,row],ignore_index=True);new=new.drop_duplicates('date',keep='last').sort_values('date')
 tmp=path.with_suffix(path.suffix+'.tmp');new.to_csv(tmp,index=False);os.replace(tmp,path)

class DataHub:
 def __init__(self,requested='auto'):
  self.requested=requested;self.now=datetime.now(IST);self.run_id=self.now.strftime('%Y%m%d_%H%M%S_%f');self.run_dir=ROOT/'runs'/self.run_id;self.run_dir.mkdir(parents=True,exist_ok=False);CACHE.mkdir(parents=True,exist_ok=True);self.results=[];self.selected={}
 def fetch(self,dataset,sources,asof_fn,validator=lambda x:len(x)>0,max_stale=1):
  errors=[]
  for name,fn in sources:
   t=time.time()
   try:
    d=_retry(fn)
    if not validator(d):raise ValueError(f'{dataset} failed validation from {name}')
    asof=str(pd.Timestamp(asof_fn(d)).date())
    if hasattr(self,'session') and dataset!='cross_market':
     delta=(pd.Timestamp(self.session)-pd.Timestamp(asof)).days
     if delta<0: raise ValueError(f'future-dated payload {asof} for session {self.session}')
     if delta>0: raise ValueError(f'stale payload {asof} for session {self.session}')
    p=_save(dataset,name,d,self.run_dir);r=SourceResult(dataset,name,'fresh',asof,len(d),int((time.time()-t)*1000),str(p.relative_to(PROJECT)),_sha(p));self.results.append(r);self.selected[dataset]=d
    cp=CACHE/f'{dataset}.csv';meta_path=CACHE/f'{dataset}.json';existing=json.loads(meta_path.read_text()) if meta_path.exists() else None
    if existing is None or pd.Timestamp(asof)>=pd.Timestamp(existing['as_of']):
     tmp=cp.with_suffix('.csv.tmp');d.to_csv(tmp,index=False);os.replace(tmp,cp)
     _atomic_text(meta_path,json.dumps({'source':name,'as_of':asof,'saved':self.now.isoformat()}))
    return d
   except Exception as e:errors.append(f'{name}: {e}')
  cp=CACHE/f'{dataset}.csv';meta=CACHE/f'{dataset}.json'
  if cp.exists() and meta.exists():
   m=json.loads(meta.read_text());stale=None
   if hasattr(self,'session'):
    a=pd.Timestamp(m['as_of']).date();b=pd.Timestamp(self.session).date();stale=int(np.busday_count(a,b)) if b>=a else -1
   # Price is fetched before the canonical session is known. If all live price adapters
   # are blocked, use the last-good price history only to establish/report the latest
   # available completed session; downstream critical gates still require fresh,
   # same-session price/options/futures before any trade can be authorized.
   if stale is None or 0<=stale<=max_stale:
    d=pd.read_csv(cp);p=_save(dataset,'last_good_cache',d,self.run_dir);r=SourceResult(dataset,'last_good_cache','cached',m['as_of'],len(d),0,str(p.relative_to(PROJECT)),_sha(p),'; '.join(errors),stale);self.results.append(r);self.selected[dataset]=d;return d
  self.results.append(SourceResult(dataset,'none','failed',None,0,0,error='; '.join(errors)));return None
 def run(self):
  from filelock import FileLock
  ROOT.mkdir(parents=True,exist_ok=True)
  with FileLock(str(ROOT/'production.lock'),timeout=5):
   return self._run_unlocked()
 def _run_unlocked(self):
  # Price first determines the most recent completed trading session.
  end=pd.Timestamp(self.now.date() if self.requested=='auto' else self.requested)
  price=self.fetch('nifty_price',[('yahoo_yfinance',lambda:yahoo_history()),('nse_index_archive',lambda:nse_index_history(end)),('yahoo_chart',lambda:yahoo_chart('%5ENSEI',end-pd.Timedelta(days=3650),end))],lambda d:pd.to_datetime(d.Date).max(),lambda d:len(d)>=200,max_stale=4)
  if price is None:raise RuntimeError('No valid NIFTY price source or cache')
  self.session=str(pd.to_datetime(price.Date).max().date()) if self.requested=='auto' else str(pd.Timestamp(self.requested).date())
  sess=self.session
  # Canonical decision history must end at D; explicit historical reruns may never see later candles.
  price=truncate_price_history(price,sess)
  canonical=_save('nifty_price','canonical_truncated',price,self.run_dir);self.selected['nifty_price']=price
  pr=next(r for r in reversed(self.results) if r.dataset=='nifty_price');pr.path=str(canonical.relative_to(PROJECT));pr.sha256=_sha(canonical);pr.rows=len(price);pr.as_of=sess
  opt=self.fetch('nifty_options_eod',[('nselib_contract_archive',lambda:options_nselib(sess)),('nse_bhavcopy',lambda:bhavcopy_filtered(sess,'option'))],lambda d:_max_mixed_date(d['TIMESTAMP']) if 'TIMESTAMP' in d else sess,lambda d:len(d)>=20,max_stale=1)
  fut=self.fetch('nifty_futures_eod',[('nselib_contract_archive',lambda:futures_nselib(sess)),('nse_bhavcopy',lambda:bhavcopy_filtered(sess,'future'))],lambda d:_max_mixed_date(d['TIMESTAMP']) if 'TIMESTAMP' in d else sess,lambda d:len(d)>=1,max_stale=1)
  part=self.fetch('participant_oi',[('nselib_participant_archive',lambda:participant_nselib(sess)),('direct_nse_archive',lambda:participant_archive(sess))],lambda d:sess,lambda d:len(d)>=4,max_stale=1)
  vix=self.fetch('india_vix',[('nse_vix_archive',lambda:vix_nse(sess)),('yahoo_vix_chart',lambda:vix_yahoo(sess))],lambda d:_max_mixed_date(d['TIMESTAMP']) if 'TIMESTAMP' in d else _max_mixed_date(d['Date']),lambda d:len(d)>=1,max_stale=1)
  cash=self.fetch('fii_dii_cash',[('nse_fiidii_api',lambda:fii_cash_nse(sess)),('groww_public_table',lambda:fii_cash_groww(sess))],lambda d:pd.to_datetime(d['date'],dayfirst=True).max(),lambda d:len(d)>=2,max_stale=1)
  cross=self.fetch('cross_market',[('yfinance_multi_asset',lambda:cross_yfinance(sess)),('yahoo_chart_multi_asset',lambda:cross_yahoo_chart(sess))],lambda d:sess,lambda d:(d.status=='ok').sum()>=10,max_stale=1)
  # Update compact historical feature stores only with validated rows whose own as-of
  # date matches the canonical session. This prevents stale cache rows from being
  # re-labeled as a newer session during provider outages.
  try:
   opt_r=next((x for x in reversed(self.results) if x.dataset=='nifty_options_eod'),None)
   fut_r=next((x for x in reversed(self.results) if x.dataset=='nifty_futures_eod'),None)
   part_r=next((x for x in reversed(self.results) if x.dataset=='participant_oi'),None)
   if opt is not None and opt_r and opt_r.as_of==sess:
    s=summarize_options(opt);append_history(PROJECT/'data'/'historical_option_features.csv',s)
   if fut is not None and fut_r and fut_r.as_of==sess:
    append_history(PROJECT/'data'/'historical_futures_features.csv',summarize_futures(fut))
   if part is not None and part_r and part_r.as_of==sess:
    append_history(PROJECT/'data'/'historical_participant_oi.csv',summarize_participant(part,part_r.as_of))
  except Exception as e:self.results.append(SourceResult('history_update','internal','failed',sess,0,0,error=str(e)))
  weights={'nifty_price':.25,'nifty_options_eod':.20,'nifty_futures_eod':.15,'participant_oi':.15,'india_vix':.10,'fii_dii_cash':.05,'cross_market':.10};score=0
  for k,w in weights.items():
   r=next((x for x in reversed(self.results) if x.dataset==k),None);score+=w*(1 if r and r.status=='fresh' else .6 if r and r.status=='cached' else 0)
  # Never trade D+1 using D-1 cached price/option/futures structure.
  critical=all(any(r.dataset==k and r.status=='fresh' and r.as_of==sess for r in self.results) for k in ['nifty_price','nifty_options_eod','nifty_futures_eod'])
  manifest={'run_id':self.run_id,'requested_date':self.requested,'session_date':sess,'decision_ist':self.now.isoformat(),'quality_score':round(score,3),'prediction_allowed':bool(score>=.75 and critical),'results':[asdict(r) for r in self.results]}
  p=self.run_dir/'manifest.json';payload=json.dumps(manifest,indent=2);_atomic_text(p,payload);_atomic_text(ROOT/'latest_manifest.json',payload);return manifest

def main():
 ap=argparse.ArgumentParser();ap.add_argument('command',choices=['run']);ap.add_argument('--date',default='auto');args=ap.parse_args();print(json.dumps(DataHub(args.date).run(),indent=2))
if __name__=='__main__':main()
