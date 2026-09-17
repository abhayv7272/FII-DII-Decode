"""Tests for the v3-candidate decoder wiring."""
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import fiidii.decode as v2_module  # noqa: E402
from fiidii.backtest import BacktestConfig, run_backtest  # noqa: E402
from fiidii.decode_v3 import (  # noqa: E402
    CLASS_THRESHOLD,
    V3_INSTRUMENT_WEIGHT,
    V3_PARTICIPANT_WEIGHT,
    decode as decode_v3,
)
from fiidii.fetch import _parse_participant_csv  # noqa: E402
from fiidii.predict import build_predictions  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


def _participant_history() -> pd.DataFrame:
    previous = _parse_participant_csv((FIX / "fao_participant_oi_prev.csv").read_text())
    current = _parse_participant_csv((FIX / "fao_participant_oi_sample.csv").read_text())
    previous["date"] = "2026-01-01"
    current["date"] = "2026-01-02"
    return pd.concat([previous, current], ignore_index=True)


def _ohlc() -> pd.DataFrame:
    return pd.DataFrame([
        {"date": "2026-01-01", "open": 24700, "high": 24900, "low": 24600, "close": 24750},
        {"date": "2026-01-02", "open": 24780, "high": 24950, "low": 24700, "close": 24850},
        {"date": "2026-01-05", "open": 24860, "high": 25200, "low": 24200, "close": 24900},
    ])


def test_v3_constants_match_the_deep_dive_candidate():
    assert V3_INSTRUMENT_WEIGHT == {"index_call": 0.30, "index_put": 0.30, "index_fut": 0.40}
    assert V3_PARTICIPANT_WEIGHT == {"Pro": 0.60, "FII": 0.40,
                                     "Client": -0.10, "DII": 0.0}
    assert CLASS_THRESHOLD == 0.0


def test_v3_decode_marks_version_and_restores_v2_constants():
    oi = _participant_history()
    today = oi[oi["date"] == "2026-01-02"].reset_index(drop=True)
    prev = oi[oi["date"] == "2026-01-01"].reset_index(drop=True)
    before_instr = dict(v2_module.NEXT_DAY_INSTRUMENT_WEIGHT)
    before_part = dict(v2_module.NEXT_DAY_PARTICIPANT_WEIGHT)
    result = decode_v3(today, prev, date_str="2026-01-02")
    assert result.method_version == "v3"
    assert v2_module.NEXT_DAY_INSTRUMENT_WEIGHT == before_instr
    assert v2_module.NEXT_DAY_PARTICIPANT_WEIGHT == before_part


def test_v3_forced_class_uses_zero_threshold():
    oi = _participant_history()
    today = oi[oi["date"] == "2026-01-02"].reset_index(drop=True)
    prev = oi[oi["date"] == "2026-01-01"].reset_index(drop=True)
    decoded = decode_v3(today, prev, date_str="2026-01-02")
    direction = build_predictions(decoded, {}, decoded_history=None)["next_day"]["direction"]
    # A zero threshold means only an exactly-zero composite may map to RANGE.
    if decoded.composite > 0:
        assert direction in {"UP", "SIDEWAYS-UP"}
    elif decoded.composite < 0:
        assert direction in {"DOWN", "SIDEWAYS-DOWN"}
    else:
        assert direction == "RANGE"


def test_v3_is_replayable_through_the_harness():
    result = run_backtest(
        _participant_history(), _ohlc(),
        config=BacktestConfig(decoder_version="v3"),
    )
    pred = result.predictions.iloc[0]
    assert pred["method_version"] == "v3"
    assert pred["predicted_class"] in {"UP", "FLAT", "DOWN"}
    assert result.metrics["status"] == "ok"
