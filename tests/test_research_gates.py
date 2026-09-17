"""Tests for the v3 forward-validation gate helpers."""
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from v3_forward_validation import _window_stats  # noqa: E402


def _stub_predictions():
    rows = [
        # exact, directional, nonflat actual, intraday present
        {"exact_hit": True, "predicted_class": "UP", "actual_class": "UP",
         "intraday_return_pct": 0.5},
        {"exact_hit": False, "predicted_class": "UP", "actual_class": "DOWN",
         "intraday_return_pct": -0.4},
        {"exact_hit": True, "predicted_class": "DOWN", "actual_class": "DOWN",
         "intraday_return_pct": -0.6},
        {"exact_hit": False, "predicted_class": "FLAT", "actual_class": "UP",
         "intraday_return_pct": 0.3},
        {"exact_hit": True, "predicted_class": "UP", "actual_class": "UP",
         "intraday_return_pct": 0.2},
        {"exact_hit": False, "predicted_class": "DOWN", "actual_class": "UP",
         "intraday_return_pct": 0.4},
    ]
    return pd.DataFrame(rows)


def test_window_stats_shape_and_values():
    stats = _window_stats(_stub_predictions())
    assert stats["signals"] == 6
    # majority actual class: UP x4 of 6
    assert stats["majority_baseline_pct"] == 66.67
    assert stats["exact_pct"] == 50.0
    # 5 directional calls out of 6
    assert stats["dir_coverage_pct"] == 83.33
    # non-FLAT sign: rows 1,3,5 correct of 5 -> 60%
    assert stats["nonflat_sign_pct"] == 60.0
    assert stats["nonflat_sign_n"] == 5
    assert stats["nonflat_sign_wilson_lo"] is not None
    # open-to-close: all 6 have |oc|>0.15; directional sign correct on 1,3,5 vs 5
    assert stats["open_to_close_sign_pct"] == 60.0


def test_window_stats_empty_frame_is_safe():
    stats = _window_stats(pd.DataFrame(columns=["exact_hit", "predicted_class",
                                                  "actual_class"]))
    assert stats == {"signals": 0}
