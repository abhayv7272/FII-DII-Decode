import pandas as pd
import src.data_hub as hubmod

def configure(tmp_path,monkeypatch):
    monkeypatch.setattr(hubmod,'PROJECT',tmp_path)
    monkeypatch.setattr(hubmod,'ROOT',tmp_path/'hub')
    monkeypatch.setattr(hubmod,'CACHE',tmp_path/'hub'/'last_good')

def test_adapter_fallback_and_hash(tmp_path,monkeypatch):
    configure(tmp_path,monkeypatch)
    h=hubmod.DataHub('2026-09-18');h.session='2026-09-18'
    def fail():raise RuntimeError('blocked')
    def backup():return pd.DataFrame({'date':['2026-09-18'],'value':[1]})
    d=h.fetch('demo',[('primary',fail),('backup',backup)],lambda x:x.date.max())
    assert d.iloc[0].value==1 and h.results[-1].source=='backup' and h.results[-1].sha256

def test_future_payload_is_rejected(tmp_path,monkeypatch):
    configure(tmp_path,monkeypatch)
    h=hubmod.DataHub('2026-09-18');h.session='2026-09-18'
    bad=lambda:pd.DataFrame({'date':['2026-09-19'],'value':[1]})
    d=h.fetch('demo',[('bad',bad)],lambda x:x.date.max())
    assert d is None and h.results[-1].status=='failed'


def test_price_cache_can_seed_session_before_session_is_known(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    h = hubmod.DataHub('auto')
    hubmod.CACHE.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({'Date':['2026-09-18'], 'Open':[1], 'High':[2], 'Low':[1], 'Close':[2], 'Volume':[10]}).to_csv(hubmod.CACHE/'nifty_price.csv', index=False)
    (hubmod.CACHE/'nifty_price.json').write_text('{"source":"cached","as_of":"2026-09-18","saved":"x"}')
    d = h.fetch('nifty_price', [('blocked', lambda: (_ for _ in ()).throw(RuntimeError('blocked')))], lambda x: pd.to_datetime(x.Date).max(), max_stale=4)
    assert d is not None
    assert h.results[-1].status == 'cached'
    assert h.results[-1].stale_days is None
