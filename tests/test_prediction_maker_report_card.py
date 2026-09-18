"""Unit coverage for the prediction-maker component backtest scorecard."""
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "research"))

from prediction_maker_report_card import _open_to_close_sign  # noqa: E402


def test_open_to_close_sign_excludes_flat_actuals_and_flat_predictions():
    predictions = pd.DataFrame([
        {"predicted_class": "UP", "intraday_return_pct": 0.20},   # hit
        {"predicted_class": "DOWN", "intraday_return_pct": -0.30}, # hit
        {"predicted_class": "UP", "intraday_return_pct": -0.40},   # miss
        {"predicted_class": "FLAT", "intraday_return_pct": 0.60},  # no direction call
        {"predicted_class": "DOWN", "intraday_return_pct": 0.10}, # actual FLAT
        {"predicted_class": "UP", "intraday_return_pct": None},   # unavailable
    ])

    accuracy, samples = _open_to_close_sign(predictions)

    assert samples == 3
    assert accuracy == 66.67


def test_open_to_close_sign_returns_no_rate_without_evaluable_direction():
    predictions = pd.DataFrame([
        {"predicted_class": "FLAT", "intraday_return_pct": 0.40},
        {"predicted_class": "UP", "intraday_return_pct": 0.01},
    ])

    accuracy, samples = _open_to_close_sign(predictions)

    assert samples == 0
    assert accuracy is None
