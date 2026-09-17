"""Tests for the v3 forward-validation gate helpers."""
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import json
import os
import subprocess

from v3_forward_validation import _window_stats  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[1]


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


def _make_forward_fixture(tmp_path: Path):
    """Fabricate a tiny forward window the gate can fully evaluate:
    OI on 2026-09-04/05/08 and bars on 09-04/05/08/09 → two signals
    (09-05, 09-08), both after the 2026-09-04 archive end."""
    oi_dir = tmp_path / "extra_oi"
    oi_dir.mkdir()
    template_next = (FIX / "fao_participant_oi_sample.csv").read_text()
    template_prev = (FIX / "fao_participant_oi_prev.csv").read_text()
    (oi_dir / "fao_participant_oi_04092026.csv").write_text(template_prev)
    (oi_dir / "fao_participant_oi_05092026.csv").write_text(template_next)
    (oi_dir / "fao_participant_oi_08092026.csv").write_text(template_prev)

    ohlc_csv = tmp_path / "extra_ohlc.csv"
    ohlc_csv.write_text(
        "Date,Open,High,Low,Close\n"
        "2026-09-04,24700,24900,24600,24750\n"
        "2026-09-05,24780,24950,24700,24850\n"
        "2026-09-08,24860,25200,24200,24900\n"
        "2026-09-09,24910,25050,24700,24800\n"
    )
    return oi_dir, ohlc_csv


def test_gate_smoke_on_synthetic_forward_window(tmp_path):
    oi_dir, ohlc_csv = _make_forward_fixture(tmp_path)
    out_dir = tmp_path / "gate_out"
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{REPO_ROOT / 'src'}:{REPO_ROOT / 'research'}"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "research" / "v3_forward_validation.py"),
        "--base-participant-oi", str(tmp_path / "missing_oi"),
        "--base-ohlc", str(tmp_path / "missing_bars"),
        "--extra-participant-oi", str(oi_dir),
        "--extra-ohlc", str(ohlc_csv),
        "--repo-participant-store", str(tmp_path / "no_store.csv"),
        "--repo-ohlc-store", str(tmp_path / "no_bars.csv"),
        "--output-dir", str(out_dir),
        "--from-date", "2026-09-05",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, env=env)
    assert result.returncode == 0, result.stderr[-2000:]

    status = json.loads((out_dir / "gate_status.json").read_text())
    assert status["state"] == "COLLECTING_DATA"  # 2 signals < 60 minimum
    for version in ("v1", "v2", "v3"):
        assert status["stats"][version]["signals"] == 2
        assert 0 <= status["stats"][version]["exact_pct"] <= 100

    # gate numbers must equal a direct run_backtest call on the same fabric
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from fiidii.backtest import (BacktestConfig, load_ohlc,
                                 load_participant_oi, run_backtest)
    oi = load_participant_oi(oi_dir)
    ohlc = load_ohlc(ohlc_csv, symbol="NIFTY")
    direct = run_backtest(oi, ohlc, config=BacktestConfig(
        decoder_version="v3", from_date="2026-09-05"))
    direct_stats = _window_stats(direct.predictions)
    assert status["stats"]["v3"]["exact_pct"] == direct_stats["exact_pct"]
    assert status["stats"]["v3"]["signals"] == direct_stats["signals"]
    predictions = out_dir / "forward_predictions.csv"
    assert predictions.exists()
    assert len(pd.read_csv(predictions)) == 6  # 2 signals x 3 versions
