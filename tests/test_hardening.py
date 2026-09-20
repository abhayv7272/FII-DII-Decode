import json
import pandas as pd
import src.data_hub as hub
from src.levels import technical_levels
from src.professional_report import research_promotion_gate
from src.execution_model import _max_dd


def configure(tmp_path,monkeypatch):
    monkeypatch.setattr(hub,'PROJECT',tmp_path)
    monkeypatch.setattr(hub,'ROOT',tmp_path/'hub')
    monkeypatch.setattr(hub,'CACHE',tmp_path/'hub'/'last_good')


def test_historical_price_is_truncated_without_future_leakage():
    dates=pd.bdate_range('2024-01-01',periods=300)
    d=pd.DataFrame({'Date':dates,'Open':1,'High':2,'Low':.5,'Close':1.5,'Volume':1})
    session=dates[249].date().isoformat();out=hub.truncate_price_history(d,session)
    assert len(out)==250 and out.Date.max().date().isoformat()==session


def test_levels_use_latest_completed_candle():
    idx=pd.bdate_range('2026-01-01',periods=20)
    d=pd.DataFrame({'Open':100.,'High':110.,'Low':90.,'Close':100.,'Volume':1},index=idx)
    d.iloc[-1,d.columns.get_loc('High')]=130;d.iloc[-1,d.columns.get_loc('Low')]=80;d.iloc[-1,d.columns.get_loc('Close')]=120
    z=technical_levels(d);assert z['pivot']==110 and z['support_1']==90 and z['resistance_1']==140


def test_modern_udiff_bhavcopy_fallback(monkeypatch):
    raw=pd.DataFrame({'TradDt':['2026-09-18']*2,'FinInstrmTp':['IDF','IDO'],'TckrSymb':['NIFTY','NIFTY'],'XpryDt':['2026-09-29']*2,
      'StrkPric':[0,23500],'OptnTp':['XX','CE'],'OpnPric':[1,2],'HghPric':[2,3],'LwPric':[.5,1],'ClsPric':[1.5,2.5],'LastPric':[1.5,2.5],
      'PrvsClsgPric':[1,2],'SttlmPric':[1.5,2.5],'TtlTradgVol':[10,20],'OpnIntrst':[100,200],'ChngInOpnIntrst':[5,10],'NewBrdLotQty':[65,65],'UndrlygPric':[23346.4,23346.4]})
    from nselib import derivatives
    monkeypatch.setattr(derivatives,'fno_bhav_copy',lambda _:raw)
    f=hub.bhavcopy_filtered('2026-09-18','future');o=hub.bhavcopy_filtered('2026-09-18','option')
    assert len(f)==1 and len(o)==1 and {'TIMESTAMP','EXPIRY_DT','CLOSING_PRICE','OPEN_INT','UNDERLYING_VALUE'}.issubset(f.columns)
    assert f.iloc[0].TOT_TRADED_QTY==650 and o.iloc[0].TOT_TRADED_QTY==1300


def test_participant_summary_preserves_full_schema():
    cols={'Client Type':['FII'],'Future Index Long':[10],'Future Index Short':[2],'Future Stock Long':[9],'Future Stock Short':[3],
      'Option Index Call Long':[8],'Option Index Call Short':[1],'Option Index Put Long':[4],'Option Index Put Short':[2],
      'Total Long Contracts':[31],'Total Short Contracts':[8]}
    z=hub.summarize_participant(pd.DataFrame(cols),'2026-09-18')
    required=['fii_index_future_net','fii_stock_future_net','fii_index_call_net','fii_index_put_net','fii_index_option_direction','fii_total_net']
    assert z[required].notna().all().all()


def test_friday_cache_is_one_business_day_old(tmp_path,monkeypatch):
    configure(tmp_path,monkeypatch);h=hub.DataHub('2026-09-21');h.session='2026-09-21';hub.CACHE.mkdir(parents=True,exist_ok=True)
    pd.DataFrame({'date':['2026-09-18'],'value':[1]}).to_csv(hub.CACHE/'demo.csv',index=False)
    (hub.CACHE/'demo.json').write_text(json.dumps({'source':'x','as_of':'2026-09-18','saved':'x'}))
    d=h.fetch('demo',[('blocked',lambda:(_ for _ in ()).throw(RuntimeError('blocked')))],lambda x:x.date.max(),max_stale=1)
    assert d is not None and h.results[-1].status=='cached' and h.results[-1].stale_days==1


def test_historical_run_does_not_poison_newer_cache(tmp_path,monkeypatch):
    configure(tmp_path,monkeypatch);h=hub.DataHub('2026-09-17');h.session='2026-09-17';hub.CACHE.mkdir(parents=True,exist_ok=True)
    pd.DataFrame({'date':['2026-09-18'],'value':[2]}).to_csv(hub.CACHE/'demo.csv',index=False)
    meta=hub.CACHE/'demo.json';meta.write_text(json.dumps({'source':'new','as_of':'2026-09-18','saved':'x'}))
    h.fetch('demo',[('historical',lambda:pd.DataFrame({'date':['2026-09-17'],'value':[1]}))],lambda x:x.date.max())
    assert json.loads(meta.read_text())['as_of']=='2026-09-18'


def test_atomic_history_update_is_idempotent(tmp_path):
    p=tmp_path/'h.csv';hub.append_history(p,pd.DataFrame([{'date':'2026-09-18','x':1}]));hub.append_history(p,pd.DataFrame([{'date':'2026-09-18','x':2}]))
    d=pd.read_csv(p);assert len(d)==1 and d.iloc[0].x==2 and not p.with_suffix('.csv.tmp').exists()


def test_research_promotion_gate_fails_negative_costs_and_passes_robust_result():
    bad={'sessions':100,'accuracy':.70,'signals':40,'selected_accuracy':.75,'costs':{'10':{'net_return':-.01}}}
    good={'sessions':100,'accuracy':.60,'signals':40,'selected_accuracy':.70,'costs':{'10':{'net_return':.01}}}
    assert not research_promotion_gate(bad) and research_promotion_gate(good)


def test_drawdown_includes_initial_equity():
    assert abs(_max_dd([-0.10,0.20])+0.10)<1e-12
