"""Tests for the historical point-in-time replay harness."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fiidii.backtest import (
    BacktestConfig,
    actual_class,
    compute_metrics,
    load_ohlc,
    load_option_chains,
    load_participant_oi,
    prediction_class,
    render_backtest_markdown,
    run_backtest,
    write_backtest_outputs,
)
from fiidii.fetch import _parse_participant_csv

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


def test_class_contract_boundaries():
    assert prediction_class("SIDEWAYS-UP") == "UP"
    assert prediction_class("RANGE") == "FLAT"
    assert prediction_class("SIDEWAYS-DOWN") == "DOWN"
    assert actual_class(0.15, 0.15) == "FLAT"
    assert actual_class(-0.15, 0.15) == "FLAT"
    assert actual_class(0.151, 0.15) == "UP"
    assert actual_class(-0.151, 0.15) == "DOWN"


def test_load_raw_and_consolidated_participant_history(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "fao_participant_oi_01012026.csv").write_text(
        (FIX / "fao_participant_oi_prev.csv").read_text())
    (raw_dir / "fao_participant_oi_02012026.csv").write_text(
        (FIX / "fao_participant_oi_sample.csv").read_text())

    raw = load_participant_oi(raw_dir)
    assert sorted(d.isoformat() for d in raw["date"].unique()) == ["2026-01-01", "2026-01-02"]

    consolidated_path = tmp_path / "participant_oi.csv"
    history = _participant_history()
    history.to_csv(consolidated_path, index=False)
    consolidated = load_participant_oi(consolidated_path)
    assert len(consolidated) == len(history)
    assert consolidated["date"].notna().all()
    assert consolidated["Future Index Long"].notna().all()


def test_load_ohlc_nse_style_columns_and_symbol_filter(tmp_path):
    path = tmp_path / "nifty.csv"
    pd.DataFrame([
        {"Index Name": "NIFTY 50", "HistoricalDate": "01-Jan-2026", "OPEN ": "24,700", "HIGH ": "24,900", "LOW ": "24,600", "CLOSE ": "24,750"},
    ]).rename(columns={"HistoricalDate": "Date"}).to_csv(path, index=False)
    loaded = load_ohlc(path, "NIFTY")
    assert loaded.iloc[0]["close"] == 24750
    assert loaded.iloc[0]["date"].isoformat() == "2026-01-01"


def test_load_dated_option_chain(tmp_path):
    chain_dir = tmp_path / "chains"
    chain_dir.mkdir()
    payload = json.loads((FIX / "option_chain_nifty.json").read_text())
    (chain_dir / "NIFTY_2026-01-02.json").write_text(json.dumps(payload))
    bank_payload = json.loads(json.dumps(payload))
    bank_payload["records"]["underlyingValue"] = 55000
    (chain_dir / "BANKNIFTY_2026-01-02.json").write_text(json.dumps(bank_payload))
    # A decoded result JSON must be ignored.
    (chain_dir / "decoded_full_2026-01-02.json").write_text(json.dumps({"decode": {}}))
    chains = load_option_chains(chain_dir, "NIFTY")
    assert next(iter(chains)).isoformat() == "2026-01-02"
    assert chains[next(iter(chains))]["records"]["underlyingValue"] == 24850
    bank_chains = load_option_chains(chain_dir, "BANKNIFTY")
    assert bank_chains[next(iter(bank_chains))]["records"]["underlyingValue"] == 55000


def test_replay_uses_exact_previous_and_next_market_sessions():
    chain = json.loads((FIX / "option_chain_nifty.json").read_text())
    result = run_backtest(
        _participant_history(),
        _ohlc(),
        {pd.Timestamp("2026-01-02").date(): chain},
        BacktestConfig(flat_threshold_pct=0.15),
    )
    assert len(result.predictions) == 1
    row = result.predictions.iloc[0]
    assert row["signal_date"] == "2026-01-02"
    assert row["previous_oi_date"] == "2026-01-01"
    assert row["target_date"] == "2026-01-05"  # weekend skipped by supplied calendar
    assert row["actual_class"] == "UP"
    assert row["option_chain_available"]
    assert row["level_tests"] >= 1
    assert result.metrics["signals_evaluated"] == 1


def test_missing_exact_previous_oi_is_skipped_not_stretched():
    history = _participant_history()
    history.loc[history["date"] == "2026-01-02", "date"] = "2026-01-05"
    prices = pd.concat([
        _ohlc(),
        pd.DataFrame([{"date": "2026-01-06", "open": 24900, "high": 25000,
                       "low": 24800, "close": 24950}]),
    ], ignore_index=True)
    result = run_backtest(history, prices)
    assert result.predictions.empty
    assert "missing_previous_session_oi" in set(result.skipped["reason"])
    assert result.metrics["status"] == "no_evaluable_signals"


def test_metrics_confidence_curve_and_artifacts(tmp_path):
    frame = pd.DataFrame([
        {"signal_date": "2026-01-01", "predicted_class": "UP", "actual_class": "UP", "exact_hit": True, "direction_hit": True, "confidence": 30, "actual_return_pct": 0.5, "support_tested": True, "support_held": True, "resistance_tested": None, "resistance_held": None, "option_chain_available": True},
        {"signal_date": "2026-01-02", "predicted_class": "UP", "actual_class": "FLAT", "exact_hit": False, "direction_hit": False, "confidence": 50, "actual_return_pct": 0.1, "support_tested": True, "support_held": False, "resistance_tested": None, "resistance_held": None, "option_chain_available": True},
        {"signal_date": "2026-01-03", "predicted_class": "DOWN", "actual_class": "DOWN", "exact_hit": True, "direction_hit": True, "confidence": 90, "actual_return_pct": -0.7, "support_tested": False, "support_held": None, "resistance_tested": True, "resistance_held": True, "option_chain_available": True},
        {"signal_date": "2026-01-04", "predicted_class": "FLAT", "actual_class": "FLAT", "exact_hit": True, "direction_hit": None, "confidence": 70, "actual_return_pct": 0.0, "support_tested": False, "support_held": None, "resistance_tested": False, "resistance_held": None, "option_chain_available": True},
    ])
    metrics, curve = compute_metrics(frame)
    assert metrics["exact_3_class_accuracy_pct"] == 75.0
    assert metrics["directional_hit_rate_pct"] == 66.67
    assert metrics["class_metrics"]["UP"]["precision_pct"] == 50.0
    assert metrics["class_metrics"]["UP"]["recall_pct"] == 100.0
    assert metrics["level_reaction_daily_proxy"]["hold_accuracy_pct"] == 66.67
    assert curve["samples"].sum() == 4

    result = run_backtest(_participant_history(), _ohlc())
    paths = write_backtest_outputs(result, tmp_path / "report")
    assert all(path.exists() for path in paths.values())
    saved = json.loads(paths["metrics"].read_text())
    assert saved["metrics"]["signals_evaluated"] == 1
    assert "Point-in-time replay" in render_backtest_markdown(result)
