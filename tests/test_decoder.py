import pandas as pd
import numpy as np
from src.decoder import hard_decode,normalize_chain

def price(n=260):
 idx=pd.bdate_range('2025-01-01',periods=n); c=pd.Series(22000+np.arange(n)*2,index=idx)
 return pd.DataFrame({'Open':c-5,'High':c+30,'Low':c-30,'Close':c,'Volume':100000},index=idx)

def test_chain_alias_and_decode():
 chain=pd.DataFrame({'strikePrice':[22400,22500,22600],'CE_OI':[100,500,200],'PE_OI':[200,600,100],
  'CE_Change_OI':[10,30,-5],'PE_Change_OI':[20,40,-2],'CE_IV':[12,13,14],'PE_IV':[14,15,16]})
 q=normalize_chain(chain); assert {'strike','call_oi','put_oi'}.issubset(q.columns)
 out=hard_decode(price(),None,chain)
 assert out['decision'] in {'WAIT','BULLISH','BEARISH'} and len(out['levels'])>=6

def test_missing_data_reduces_confidence():
 out=hard_decode(price(),None,None)
 assert out['decision']=='WAIT' and out['evidence_confidence']<68
