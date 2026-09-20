from __future__ import annotations
import json
from pathlib import Path
import numpy as np,pandas as pd
from .levels import technical_levels
from .model import recursive_week_scenarios

PROJECT=Path(__file__).resolve().parents[1]

def research_promotion_gate(bt):
 cost10=bt.get('costs',{}).get('10',{})
 return bool(bt.get('sessions',0)>=80 and bt.get('accuracy',0)>=.58 and bt.get('signals',0)>=30 and (bt.get('selected_accuracy') or 0)>=.65 and (cost10.get('net_return') or 0)>0)

def _price_from_manifest(m):
 r=next(x for x in m['results'] if x['dataset']=='nifty_price' and x['status'] in {'fresh','cached'});d=pd.read_csv(PROJECT/r['path']);d['Date']=pd.to_datetime(d.Date);return d.set_index('Date').sort_index()[['Open','High','Low','Close','Volume']]
def specialist_latest(price):
 from optimize_derivative_specialists import derivative_features,participant_features,models
 from .advanced_model import advanced_features
 rep=json.loads((PROJECT/'reports'/'derivative_specialist.json').read_text());o=pd.read_csv(PROJECT/'data'/'historical_option_features.csv');f=pd.read_csv(PROJECT/'data'/'historical_futures_features.csv');der=derivative_features(o,f);px=advanced_features(price);part=participant_features(PROJECT/'data'/'historical_participant_oi.csv')
 feature_set=rep.get('best',{}).get('features','option_futures');sets={'price':px,'option_futures':der,'participant':part,'derivatives_participant':der.join(part,how='inner'),'price_plus_derivatives':px.join(der,how='inner'),'full':px.join(der,how='inner').join(part,how='inner')}
 if feature_set not in sets:raise ValueError(f'Unknown frozen feature set: {feature_set}')
 X=sets[feature_set].sort_index();X=X[X.index<=pd.Timestamp(price.index.max()).normalize()]
 missing=[c for c in rep['selected_columns'] if c not in X]
 if missing:raise ValueError(f'Specialist schema drift; missing {len(missing)} frozen features: {missing[:8]}')
 cols=rep['selected_columns'];ret=price.Close.shift(-1)/price.Open.shift(-1)-1;y=(ret>0).astype(float).reindex(X.index);y[ret.reindex(X.index).isna()]=np.nan;lab=y.notna()
 if lab.sum()<250:raise ValueError(f'Insufficient aligned specialist training sessions: {int(lab.sum())}')
 mdl=models()['logit']();mdl.fit(X.loc[lab,cols],y[lab].astype(int));p=float(mdl.predict_proba(X.iloc[[-1]][cols])[0,1]);gate=float(rep['frozen_gate']['gate']);bt=rep['holdout'];research_approved=research_promotion_gate(bt)
 confidence_pass=max(p,1-p)>=gate
 return {'as_of':str(X.index[-1].date()),'direction':'UP' if p>=.5 else 'DOWN','p_up':p,'p_down':1-p,'confidence':max(p,1-p),'gate':gate,'confidence_pass':confidence_pass,'research_approved':research_approved,'model_pass':bool(confidence_pass and research_approved),'backtest':bt,'error':None}
def _source_table(m):
 df=pd.DataFrame([{'Dataset':r['dataset'],'Selected source':r['source'],'Status':r['status'],'As-of':r.get('as_of'),'Rows':r['rows'],'Stale days':r.get('stale_days'),'Error':r.get('error')} for r in m['results']])
 return df.fillna('')
def create_report(manifest_path=None):
 from .risk_gates import event_risk
 mp=Path(manifest_path) if manifest_path else PROJECT/'data'/'hub'/'latest_manifest.json';m=json.loads(mp.read_text());price=_price_from_manifest(m)
 try:pred=specialist_latest(price)
 except Exception as e:
  rep=json.loads((PROJECT/'reports'/'derivative_specialist.json').read_text());pred={'as_of':None,'direction':'UNKNOWN','p_up':.5,'p_down':.5,'confidence':0.,'gate':float(rep.get('frozen_gate',{}).get('gate',1.)),'confidence_pass':False,'research_approved':False,'model_pass':False,'backtest':rep.get('holdout',{}),'error':str(e)}
 lev=technical_levels(price);last=float(price.Close.iloc[-1]);sma20=float(price.Close.rolling(20).mean().iloc[-1]);sma200=float(price.Close.rolling(200).mean().iloc[-1]);atrp=lev['atr14_points']/last
 event=event_risk(m['session_date']);date_match=pred['as_of']==m['session_date'];allowed=bool(m['prediction_allowed'] and pred['model_pass'] and date_match and not event['blocked']);decision=pred['direction'] if allowed else 'WAIT / NO TRADE'
 critical_names=['nifty_price','nifty_options_eod','nifty_futures_eod'];critical_fresh={k:any(r['dataset']==k and r['status']=='fresh' and r.get('as_of')==m['session_date'] for r in m['results']) for k in critical_names};critical_fresh_text=', '.join(f'{k}={v}' for k,v in critical_fresh.items());data_gate={'passed':bool(m['prediction_allowed']),'quality_score':m['quality_score'],'critical_fresh_date_matched':critical_fresh}
 if allowed and pred['direction']=='UP':trade='LONG BIAS — only after resistance breakout and successful retest';swing='Swing long can be considered only above the trigger with defined stop.'
 elif allowed:trade='SHORT BIAS — only after support breakdown and failed reclaim';swing='Swing short can be considered only below the trigger with defined stop.'
 else:trade='NO DIRECTIONAL POSITION';swing='Do not initiate a new swing position until the confidence/data gate and price trigger both pass.'
 invest='Long-term trend positive; staggered investment may be researched, but this next-day model is not a fundamental valuation model.' if last>sma200 else 'Fresh long-term investment should be deferred or evaluated fundamentally; index is below its 200-day trend.'
 dates=pd.bdate_range(price.index[-1]+pd.Timedelta(days=1),periods=5);week_probs={'UP':pred['p_up'],'DOWN':pred['p_down'],'FLAT':0} if allowed else {'UP':.5,'DOWN':.5,'FLAT':0};week=recursive_week_scenarios(last,week_probs,atrp,5);week.insert(0,'date',[str(x.date()) for x in dates])
 sources=_source_table(m);missing=sources[sources.Status.eq('failed')].Dataset.tolist();cached=sources[sources.Status.eq('cached')].Dataset.tolist()
 obj={'session_date':m['session_date'],'decision_time_ist':m['decision_ist'],'decision':decision,'quality_score':m['quality_score'],'data_gate':data_gate,'prediction':pred,'prediction_date_matches_session':date_match,'event_risk':event,'levels':lev,'trade_stance':trade,'swing_stance':swing,'investment_context':invest,'weekly_scenarios':week.to_dict('records'),'failed_sources':missing,'cached_sources':cached}
 lines=[f"# NIFTY Professional Decision Report — {m['session_date']}","",f"**Generated:** {m['decision_ist']}  ",f"**Data quality:** {m['quality_score']:.0%}  ",f"**Data gate:** **{'PASS' if data_gate['passed'] else 'FAIL-CLOSED'}**  ",f"**Final decision:** **{decision}**",'',"## Executive view",'',f"- Specialist direction: **{pred['direction']}**",f"- UP/DOWN probability: **{pred['p_up']:.2%} / {pred['p_down']:.2%}**",f"- Model confidence: **{pred['confidence']:.2%}**; frozen gate: **{pred['gate']:.0%}**",f"- Prediction/session match: **{date_match}**",f"- Critical fresh/date-matched data: **{critical_fresh_text}**",f"- Trading stance: **{trade}**",f"- Swing stance: {swing}",f"- Investment context: {invest}",'',"## Key levels",'',f"- Resistance trigger: **{lev['resistance_1']:,.2f}**",f"- Pivot: **{lev['pivot']:,.2f}**",f"- Support trigger: **{lev['support_1']:,.2f}**",f"- 20-day support/resistance: **{lev['support_20d']:,.2f} / {lev['resistance_20d']:,.2f}**",f"- ATR(14): **{lev['atr14_points']:,.2f} points**",'',"## Conditional playbook",'',f"### Bull path\nSupport/pivot hold → close above {lev['resistance_1']:,.2f} → retest holds → only then long continuation is valid.",f"### Bear path\nResistance rejection → close below {lev['support_1']:,.2f} → failed reclaim → only then short continuation is valid.","### Trap rule\nA wick/sweep alone is not entry confirmation. Wait for a completed candle and follow-through.",'',"## Monday–Friday risk map",'',week.to_markdown(index=False,floatfmt='.2f'),'',"## What not to do",'',"- Do not trade below the confidence or data-quality gate.","- Do not chase an abnormal opening gap; wait for a new range.","- Do not treat max pain/OI wall as a guaranteed target.","- Do not average a losing leveraged position.","- Do not use this next-day model as the sole basis for long-term investment.",'',"## Data-source health",'',sources.to_markdown(index=False),'',"## Model evidence",'',f"- Later research test: {pred['backtest']['accuracy']:.2%} accuracy across {pred['backtest']['sessions']} sessions.",f"- Selected research sample: {pred['backtest']['signals']} signals, {pred['backtest']['selected_accuracy']:.2%} observed accuracy; this sample is provisional.","- Current report automatically becomes WAIT if critical data or confidence gates fail.",'',"## Risk notice",'',"Research/decision-support only; not personalized investment advice. Futures and options can cause rapid losses. Verify exchange data, liquidity, costs and your risk capacity before any trade."]
 if pred.get('error'):lines.insert(7,f"**MODEL ERROR — fail-closed:** {pred['error']}")
 if not data_gate['passed']:
  lines.insert(7,"**DATA GATE FAIL-CLOSED:** critical price/options/futures were not all fresh/date-matched or overall quality was below threshold.")
 if not pred.get('research_approved',False):
  lines.insert(7,"**Diagnostic only:** raw class probability is not a calibrated profit probability and is excluded from the weekly centre.")
  lines.insert(7,"**RESEARCH PROMOTION GATE FAILED:** corrected holdout/cost metrics do not support a live directional trade.")
 if not date_match:lines.insert(7,f"**DATE MISMATCH — fail-closed:** specialist as-of {pred.get('as_of')} vs session {m['session_date']}")
 if event['status']!='CLEAR':lines.insert(7,f"**Event-calendar status:** {event['status']}" + (" — trade blocked" if event['blocked'] else " — verified calendar unavailable; check manually"))
 executive_idx=lines.index("## Executive view")
 if executive_idx>0 and lines[executive_idx-1] != '':lines.insert(executive_idx,'')
 from .data_hub import _atomic_text
 out=PROJECT/'reports'/'daily';out.mkdir(parents=True,exist_ok=True);md=out/f"{m['session_date']}_professional_report.md";js=out/f"{m['session_date']}_professional_report.json";_atomic_text(md,'\n'.join(lines));_atomic_text(js,json.dumps(obj,indent=2,default=float));return md,js,obj
