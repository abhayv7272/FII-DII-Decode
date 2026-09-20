import numpy as np
import pandas as pd
from src.features import make_features, make_labels
from src.advanced_model import advanced_features


def sample(n=260):
    idx=pd.bdate_range("2020-01-01", periods=n)
    c=pd.Series(100+np.arange(n)*.1, index=idx)
    return pd.DataFrame({"Open":c-.2,"High":c+1,"Low":c-1,"Close":c,"Volume":1000}, index=idx)

def test_label_is_next_close():
    d=sample(); y,r=make_labels(d, 0)
    assert y.iloc[0] == 2 and pd.isna(y.iloc[-1])

def test_features_do_not_depend_on_future():
    d=sample(); a=make_features(d)
    d2=d.copy(); d2.iloc[-1, d2.columns.get_loc("Close")]=9999
    b=make_features(d2)
    pd.testing.assert_series_equal(a.iloc[-2], b.iloc[-2])

def test_advanced_features_do_not_depend_on_future():
    d=sample(); a=advanced_features(d)
    d2=d.copy(); d2.iloc[-1, d2.columns.get_loc("High")]=9999
    b=advanced_features(d2)
    pd.testing.assert_series_equal(a.iloc[-2], b.iloc[-2])
