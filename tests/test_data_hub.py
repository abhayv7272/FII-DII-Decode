import pandas as pd
import src.data_hub as hubmod
import src.professional_report as reportmod

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
    assert h.results[-1].cache_path == 'hub/last_good/nifty_price.csv'


def test_corrupt_cache_metadata_fails_closed_without_crashing(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    h = hubmod.DataHub('2026-09-18'); h.session = '2026-09-18'
    hubmod.CACHE.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({'date':['2026-09-18'], 'value':[1]}).to_csv(hubmod.CACHE/'demo.csv', index=False)
    (hubmod.CACHE/'demo.json').write_text('{not-json')
    d = h.fetch('demo', [('blocked', lambda: (_ for _ in ()).throw(RuntimeError('blocked')))], lambda x: x.date.max())
    assert d is None
    assert h.results[-1].status == 'failed'
    assert 'corrupt' in h.results[-1].error


def test_committed_manifest_can_rebuild_price_from_compact_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(reportmod, 'PROJECT', tmp_path)
    cache = tmp_path / 'data' / 'hub' / 'last_good'
    cache.mkdir(parents=True)
    dates = pd.bdate_range('2026-01-01', periods=260)
    session = str(dates[239].date())
    pd.DataFrame({'Date': dates, 'Open': 1, 'High': 2, 'Low': 1, 'Close': 2, 'Volume': 10}).to_csv(cache / 'nifty_price.csv', index=False)
    manifest = {'session_date': session, 'results': [{'dataset': 'nifty_price', 'status': 'fresh', 'path': 'data/hub/runs/missing/nifty_price.csv', 'cache_path': 'data/hub/last_good/nifty_price.csv'}]}
    price = reportmod._price_from_manifest(manifest)
    assert str(price.index.max().date()) == session
    assert len(price) == 240
