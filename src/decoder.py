from __future__ import annotations
from dataclasses import dataclass,asdict
import math
import numpy as np
import pandas as pd

@dataclass
class Signal:
    name:str; score:float; reliability:float; evidence:str


def _clip(x,lo=-1,hi=1): return float(np.clip(x,lo,hi))
def _z_last(s:pd.Series,n=60):
    s=pd.to_numeric(s,errors='coerce').dropna()
    if len(s)<10:return 0.0
    q=s.tail(n); sd=q.std()
    return 0.0 if not sd or np.isnan(sd) else _clip((q.iloc[-1]-q.mean())/sd/2.5)

def participant_decode(snapshots:pd.DataFrame)->list[Signal]:
    """Decode *changes*, conflict and cash confirmation; static positioning gets lower reliability."""
    if snapshots is None or snapshots.empty:return [Signal('participant',0,0,'missing participant history')]
    d=snapshots.sort_values('session_date').copy(); cur=d.iloc[-1]; prev=d.iloc[-2] if len(d)>1 else None
    def delta(col):
        if prev is None or col not in d:return 0.0
        scale=max(abs(float(prev.get(col,0))),50000)
        return _clip((float(cur.get(col,0))-float(prev.get(col,0)))/scale*3)
    fii=delta('fii_index_futures_net'); pro=delta('pro_index_futures_net')
    cash=_clip((float(cur.get('fii_cash_net_cr',0))+0.35*float(cur.get('dii_cash_net_cr',0)))/4000)
    # Participant OI change leads; cash confirms. Opposing FII/Pro lowers reliability, not forcibly direction.
    raw=.45*fii+.35*pro+.20*cash
    conflict=(fii*pro<0 and abs(fii)>.15 and abs(pro)>.15)
    rel=.80 if prev is not None else .30
    if conflict: rel*=.55
    ev=f'FII Δ={fii:+.2f}, Pro Δ={pro:+.2f}, cash={cash:+.2f}'+('; FII–Pro conflict' if conflict else '')
    return [Signal('participant_position_change',_clip(raw),rel,ev)]

def technical_confluence_decode(price:pd.DataFrame)->list[Signal]:
    """Cluster correlated indicators so ten versions of momentum do not become ten votes."""
    from .technical_indicators import technical_features
    f=technical_features(price).iloc[-1]
    trend=_clip(.35*np.tanh(float(f.get('sma_dist_20',0))*50)+.25*np.tanh(float(f.get('sma_dist_50',0))*35)+
                .25*np.tanh(float(f.get('macd_hist',0))*250)+.15*float(f.get('trend_strength',0)))
    rsi=float(f.get('rsi_14',.5));stoch=float(f.get('stoch_14',.5));roc=float(f.get('roc_10',0))
    momentum=_clip(.35*(2*rsi-1)+.30*(2*stoch-1)+.35*np.tanh(roc*35))
    boll=float(f.get('boll_z',0)); mean_rev=_clip(-.55*np.tanh(boll/1.5)-.45*np.tanh((rsi-.5)*3)) if abs(boll)>1 or rsi<.3 or rsi>.7 else 0
    atr=float(f.get('atr_14',0));vol20=float(f.get('realized_vol_20',0));
    return [Signal('technical_trend_cluster',trend,.60,f'SMA/MACD/ADX cluster={trend:+.2f}'),
            Signal('technical_momentum_cluster',momentum,.55,f'RSI14={rsi*100:.1f}, stochastic={stoch:.2f}, ROC10={roc:+.2%}'),
            Signal('technical_mean_reversion',mean_rev,.40,f'Bollinger z={boll:+.2f}; active only near extremes'),
            Signal('volatility_regime',0,.45,f'ATR14={atr:.2%}, annualized vol20={vol20:.2%}; risk modifier, not direction')]

def cross_asset_decode(snapshots:pd.DataFrame|None)->list[Signal]:
    if snapshots is None or snapshots.empty:return [Signal('cross_asset_context',0,0,'missing cross-asset snapshot')]
    z=snapshots.sort_values('session_date').iloc[-1]
    def n(k,default=0):
        try:return float(z.get(k,default)) if pd.notna(z.get(k,default)) else default
        except:return default
    sector=_clip(n('india_sector_mean_return')*60);heavy=_clip(n('india_heavyweight_mean_return')*60)
    breadth=_clip(.45*sector+.55*heavy)
    asia=_clip(n('asia_mean_return')*50);glob=_clip(n('prior_global_mean_return')*45)
    global_score=_clip(.45*asia+.55*glob)
    vix_ch=n('india_vix_change_pct')/100;vix_level=n('india_vix_close',15);vix_score=_clip(-np.tanh(vix_ch*5))
    risk='compressed' if vix_level<12 else ('elevated' if vix_level>20 else 'normal')
    return [Signal('sector_and_heavyweight_breadth',breadth,.65,f'sector={sector:+.2f}, heavyweight={heavy:+.2f}'),
            Signal('timing_safe_global_context',global_score,.50,f'Asia={asia:+.2f}, prior-global={glob:+.2f}'),
            Signal('india_vix_regime',vix_score,.45,f'VIX={vix_level:.2f} ({risk}), change={vix_ch:+.2%}')]

def futures_decode(price:pd.DataFrame,snapshots:pd.DataFrame|None)->list[Signal]:
    if snapshots is None or snapshots.empty:return [Signal('futures_basis_and_oi',0,0,'missing futures data')]
    z=snapshots.sort_values('session_date').iloc[-1]
    if pd.isna(z.get('nifty_future_change_oi',np.nan)):return [Signal('futures_basis_and_oi',0,0,'missing NIFTY futures OI')]
    oi=float(z.get('nifty_future_change_oi',0));basis=float(z.get('nifty_future_basis_pct',0));ret=float(price.Close.pct_change().iloc[-1])
    # Price/OI matrix: up+OI up fresh longs; down+OI up fresh shorts; falling OI means covering/unwinding and lower conviction.
    if ret>0 and oi>0:score=.65;state='fresh long build-up'
    elif ret<0 and oi>0:score=-.65;state='fresh short build-up'
    elif ret>0 and oi<0:score=.30;state='short covering'
    elif ret<0 and oi<0:score=-.30;state='long unwinding'
    else:score=0;state='neutral'
    score=_clip(score+.15*np.tanh(basis*100))
    return [Signal('futures_basis_and_oi',score,.55,f'{state}; change-OI={oi:,.0f}, basis={basis:+.2%}')]

def price_psychology_decode(price:pd.DataFrame)->list[Signal]:
    """Observable crowd-behaviour proxies—not claims about hidden intent."""
    if len(price)<65:return [Signal('price_psychology',0,0,'insufficient OHLCV history')]
    p=price.copy(); c,o,h,l,v=[p[k].astype(float) for k in ['Close','Open','High','Low','Volume']]
    prev_hi=h.shift(1).rolling(20).max(); prev_lo=l.shift(1).rolling(20).min()
    bull_trap=bool((h.iloc[-1]>prev_hi.iloc[-1]) and (c.iloc[-1]<prev_hi.iloc[-1]))
    bear_trap=bool((l.iloc[-1]<prev_lo.iloc[-1]) and (c.iloc[-1]>prev_lo.iloc[-1]))
    close_loc=float((c.iloc[-1]-l.iloc[-1])/max(h.iloc[-1]-l.iloc[-1],1e-9))
    vol_z=_z_last(v,20); ret1=float(c.pct_change().iloc[-1]); trend=float(c.iloc[-1]/c.rolling(20).mean().iloc[-1]-1)
    score=_clip(.35*np.tanh(ret1*80)+.30*(2*close_loc-1)+.25*np.tanh(trend*40)+(.45 if bear_trap else 0)-(.45 if bull_trap else 0))
    flags=[]
    if bull_trap: flags.append('20D high sweep + close back below')
    if bear_trap: flags.append('20D low sweep + reclaim')
    if abs(vol_z)>.7: flags.append(f'abnormal volume z={vol_z:+.2f}')
    return [Signal('price_reaction_and_traps',score,.75,f'close-location={close_loc:.2f}; '+('; '.join(flags) if flags else 'no confirmed 20D sweep'))]

def normalize_chain(chain:pd.DataFrame)->pd.DataFrame:
    """Map common option-chain column names to strike/call_oi/put_oi/change/IV."""
    aliases={
      'strike':['strike','strikeprice','strike_price'], 'call_oi':['call_oi','ce_oi','ceopeninterest','calls_oi'],
      'put_oi':['put_oi','pe_oi','peopeninterest','puts_oi'],'call_change_oi':['call_change_oi','ce_change_oi','cechangeinopeninterest'],
      'put_change_oi':['put_change_oi','pe_change_oi','pechangeinopeninterest'],'call_iv':['call_iv','ce_iv','ceimpliedvolatility'],
      'put_iv':['put_iv','pe_iv','peimpliedvolatility'],'call_volume':['call_volume','ce_volume','cetotaltradedvolume'],
      'put_volume':['put_volume','pe_volume','petotaltradedvolume']}
    compact={''.join(ch for ch in str(c).lower() if ch.isalnum() or ch=='_'):c for c in chain.columns}; ren={}
    for std,names in aliases.items():
        for name in names:
            key=''.join(ch for ch in name.lower() if ch.isalnum() or ch=='_')
            if key in compact:ren[compact[key]]=std;break
    out=chain.rename(columns=ren).copy()
    if 'strike' not in out:raise ValueError('Option chain needs strike/strikePrice column.')
    for c in aliases:
        if c!='strike' and c not in out:out[c]=0.0
        out[c]=pd.to_numeric(out[c],errors='coerce').fillna(0)
    return out[list(aliases)].sort_values('strike')

def option_decode(chain:pd.DataFrame|None,spot:float,atr:float)->tuple[list[Signal],dict]:
    if chain is None or chain.empty:return [Signal('option_structure',0,0,'missing option chain')],{}
    q=normalize_chain(chain); band=q[(q.strike>=spot-3*atr)&(q.strike<=spot+3*atr)].copy()
    if band.empty:return [Signal('option_structure',0,0,'no near-spot strikes')],{}
    call_wall=band.loc[band.call_oi.idxmax()]; put_wall=band.loc[band.put_oi.idxmax()]
    call_chg=band.loc[band.call_change_oi.idxmax()]; put_chg=band.loc[band.put_change_oi.idxmax()]
    pcr=band.put_oi.sum()/max(band.call_oi.sum(),1); chg_pcr=band.put_change_oi.sum()/max(abs(band.call_change_oi.sum()),1)
    # OI is context: score is muted unless change-OI agrees with static walls.
    wall_score=_clip(np.log(max(pcr,1e-4))/1.2)
    change_score=_clip(np.tanh((band.put_change_oi.sum()-band.call_change_oi.sum())/max(abs(band.put_change_oi).sum()+abs(band.call_change_oi).sum(),1)*2))
    score=_clip(.35*wall_score+.65*change_score)
    iv_skew=float(band.put_iv.replace(0,np.nan).median()-band.call_iv.replace(0,np.nan).median())
    levels={'call_wall':float(call_wall.strike),'put_wall':float(put_wall.strike),'call_build_wall':float(call_chg.strike),
      'put_build_wall':float(put_chg.strike),'pcr_oi':float(pcr),'pcr_change_proxy':float(chg_pcr),'near_atm_iv_skew':iv_skew}
    ev=f"PCR={pcr:.2f}; call wall={call_wall.strike:.0f}; put wall={put_wall.strike:.0f}; build walls C/P={call_chg.strike:.0f}/{put_chg.strike:.0f}; IV skew={iv_skew:+.2f}"
    return [Signal('option_walls_and_migration',score,.70,ev)],levels

def ranked_levels(price:pd.DataFrame,option_levels:dict|None=None)->pd.DataFrame:
    c=float(price.Close.iloc[-1]); atr=pd.concat([(price.High-price.Low),(price.High-price.Close.shift()).abs(),(price.Low-price.Close.shift()).abs()],axis=1).max(axis=1).rolling(14).mean().iloc[-1]
    candidates=[]
    def add(level,kind,source,strength):
        if pd.notna(level):candidates.append({'level':float(level),'kind':kind,'source':source,'distance_atr':abs(float(level)-c)/max(atr,1e-9),'strength':strength})
    prev=price.iloc[-2];pivot=(prev.High+prev.Low+prev.Close)/3
    add(2*pivot-prev.High,'support','pivot S1',.60);add(2*pivot-prev.Low,'resistance','pivot R1',.60)
    add(price.Low.tail(20).min(),'support','20D swing',.75);add(price.High.tail(20).max(),'resistance','20D swing',.75)
    step=50 if c<30000 else 100;add(round(c/step)*step,'magnet','round number',.40);add(float(price.Close.iloc[-2]),'magnet','prior close',.50)
    for key,kind in [('put_wall','support'),('call_wall','resistance'),('put_build_wall','support'),('call_build_wall','resistance')]:
        if option_levels and key in option_levels:add(option_levels[key],kind,key,.85 if 'build' in key else .80)
    out=pd.DataFrame(candidates).sort_values(['distance_atr','strength'],ascending=[True,False])
    return out

def hard_decode(price:pd.DataFrame,snapshots:pd.DataFrame|None=None,chain:pd.DataFrame|None=None)->dict:
    atr=float(pd.concat([(price.High-price.Low),(price.High-price.Close.shift()).abs(),(price.Low-price.Close.shift()).abs()],axis=1).max(axis=1).rolling(14).mean().iloc[-1])
    sig=(participant_decode(snapshots)+futures_decode(price,snapshots)+price_psychology_decode(price)+technical_confluence_decode(price)+cross_asset_decode(snapshots))
    osig,olevel=option_decode(chain,float(price.Close.iloc[-1]),atr);sig+=osig
    usable=[s for s in sig if s.reliability>0];den=sum(s.reliability for s in usable)
    directional=[s for s in usable if abs(s.score)>=.05]
    score=sum(s.score*s.reliability for s in directional)/sum(s.reliability for s in directional) if directional else 0
    signs=[np.sign(s.score) for s in usable if abs(s.score)>=.15]
    agreement=abs(sum(signs))/len(signs) if signs else 0
    completeness=den/6.40
    confidence=float(np.clip(.45*agreement+.55*completeness,0,1))
    decision='WAIT'
    if confidence>=.68 and abs(score)>=.25:decision='BULLISH' if score>0 else 'BEARISH'
    return {'decision':decision,'structural_score':round(score*100,1),'evidence_confidence':round(confidence*100,1),
      'signals':[asdict(s) for s in sig],'option_context':olevel,'levels':ranked_levels(price,olevel).to_dict('records'),
      'warning':'Manipulation/psychology are inferred proxies, not directly observable facts. Confirmation remains mandatory.'}
