"""Single source of truth for the index-only scanners.

`index_symbol` is the actual Yahoo/NSE index feed. Some sector index symbols expose
intraday data but no usable daily history; `history_proxy` is then an index-tracking
ETF (never an individual constituent stock). Reports retain the index name and expose
the data symbol/source used.
"""
INDEX_UNIVERSE = [
    {"name":"Nifty 50","index_symbol":"^NSEI","history_proxy":"NIFTYBEES.NS","category":"Broad Market","description":"Top 50 benchmark"},
    {"name":"Nifty Next 50","index_symbol":"^NSMIDCP","history_proxy":"JUNIORBEES.NS","category":"Broad Market","description":"Next 50 large-cap index"},
    {"name":"Nifty Midcap 50","index_symbol":"^NSEMDCP50","history_proxy":"MIDQ50ADD.NS","category":"Broad Market","description":"Midcap 50 index"},
    {"name":"Nifty Smallcap 250","index_symbol":None,"history_proxy":"HDFCSML250.NS","category":"Broad Market","description":"Smallcap 250 index proxy"},
    {"name":"Nifty Bank","index_symbol":"^NSEBANK","history_proxy":"BANKBEES.NS","category":"Sectoral","description":"Banking index"},
    {"name":"Nifty PSU Bank","index_symbol":"^CNXPSUBANK","history_proxy":"PSUBNKBEES.NS","category":"Sectoral","description":"Public-sector bank index"},
    {"name":"Nifty IT","index_symbol":"^CNXIT","history_proxy":"ITBEES.NS","category":"Sectoral","description":"Information technology index"},
    {"name":"Nifty Pharma","index_symbol":"^CNXPHARMA","history_proxy":"PHARMABEES.NS","category":"Sectoral","description":"Pharmaceutical index"},
    {"name":"Nifty Healthcare","index_symbol":None,"history_proxy":"HEALTHIETF.NS","category":"Sectoral","description":"Healthcare index proxy"},
    {"name":"Nifty Auto","index_symbol":"^CNXAUTO","history_proxy":"AUTOBEES.NS","category":"Sectoral","description":"Automobile index"},
    {"name":"Nifty FMCG","index_symbol":"^CNXFMCG","history_proxy":"FMCGIETF.NS","category":"Sectoral","description":"FMCG index"},
    {"name":"Nifty Metal","index_symbol":"^CNXMETAL","history_proxy":"METALIETF.NS","category":"Sectoral","description":"Metals index"},
    {"name":"Nifty Energy","index_symbol":"^CNXENERGY","history_proxy":"ENERGY.NS","category":"Sectoral","description":"Energy index"},
    {"name":"Nifty Oil & Gas","index_symbol":None,"history_proxy":"OILIETF.NS","category":"Sectoral","description":"Oil and gas index proxy"},
    {"name":"Nifty Infrastructure","index_symbol":"^CNXINFRA","history_proxy":"INFRAIETF.NS","category":"Sectoral","description":"Infrastructure index"},
    {"name":"Nifty Realty","index_symbol":"^CNXREALTY","history_proxy":"MOREALTY.NS","category":"Sectoral","description":"Realty index"},
    {"name":"Nifty Consumer Durables","index_symbol":None,"history_proxy":"CONSUMBEES.NS","category":"Sectoral","description":"Consumer durables index proxy"},
    {"name":"Nifty Financial Services","index_symbol":"^CNXFIN","history_proxy":"FINIETF.NS","category":"Sectoral","description":"Financial services index"},
    {"name":"Nifty CPSE","index_symbol":None,"history_proxy":"CPSEETF.NS","category":"Thematic","description":"Central public-sector enterprise index proxy"},
]

def symbols_for_history(item):
    """Prefer actual index; fall back only to an index-tracking ETF."""
    return [s for s in (item.get("index_symbol"), item.get("history_proxy")) if s]
