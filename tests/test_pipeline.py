"""Smoke tests for the decode pipeline using bundled fixtures (no network)."""
import json
from pathlib import Path

import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fiidii.cli import _history_for_method
from fiidii.fetch import _parse_participant_csv
from fiidii.decode import _fresh_pressure, decode
from fiidii.levels import derive_levels
from fiidii.predict import build_predictions
from fiidii.report import render_markdown

FIX = Path(__file__).parent / "fixtures"


def _load():
    today = _parse_participant_csv((FIX / "fao_participant_oi_sample.csv").read_text())
    prev = _parse_participant_csv((FIX / "fao_participant_oi_prev.csv").read_text())
    oc = json.loads((FIX / "option_chain_nifty.json").read_text())
    return today, prev, oc


def test_parse_participants():
    today, _, _ = _load()
    assert set(today["ClientType"].str.upper()) >= {"CLIENT", "DII", "FII", "PRO"}
    assert "Future Index Long" in today.columns


def test_parse_drops_irrelevant_trailing_unnamed_column():
    text = (
        "Participant wise Open Interest,,,\n"
        "Client Type,Future Index Long,Future Index Short,\n"
        "FII,100,90,190\n"
    )
    parsed = _parse_participant_csv(text)
    assert list(parsed.columns) == ["ClientType", "Future Index Long", "Future Index Short"]
    assert parsed.iloc[0]["Future Index Long"] == 100


def test_history_does_not_mix_decoder_versions_or_current_date():
    legacy = pd.DataFrame([{"date": "2026-09-15", "positional_composite": 0.8}])
    assert _history_for_method(legacy, "v2", "2026-09-17").empty

    versioned = pd.DataFrame([
        {"date": "2026-09-15", "method_version": "v1"},
        {"date": "2026-09-16", "method_version": "v2"},
        {"date": "2026-09-17", "method_version": "v2"},
    ])
    selected = _history_for_method(versioned, "v2", "2026-09-17")
    assert selected[["date", "method_version"]].to_dict("records") == [
        {"date": "2026-09-16", "method_version": "v2"}
    ]


def test_decode_produces_bias():
    today, prev, _ = _load()
    res = decode(today, prev, date_str="2026-09-17")
    labels = {"STRONG BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "STRONG BEARISH"}
    assert res.bias in labels
    assert res.positional_bias in labels
    assert -1.0 <= res.composite <= 1.0
    assert -1.0 <= res.positional_composite <= 1.0
    assert 0 <= res.confidence <= 100
    assert res.signals
    # Retail must be treated as a contra indicator and appear in participant reads.
    assert "Client" in res.participant_reads
    assert res.retail_note


def test_retail_contra_logic():
    """If retail is heavily net-long futures, market read should lean the other way."""
    today, prev, _ = _load()
    res = decode(today, prev, date_str="2026-09-17")
    client = res.participant_reads["Client"]
    # Client reads are contra-adjusted; they must be finite numbers.
    assert all(-1.0 <= v <= 1.0 for v in client.values())


def test_v2_relative_oi_normalisation_is_scale_invariant():
    today, prev, _ = _load()
    original = decode(today, prev)
    scaled_today, scaled_prev = today.copy(), prev.copy()
    numeric = [column for column in today.columns if column != "ClientType"]
    scaled_today[numeric] = scaled_today[numeric] * 10
    scaled_prev[numeric] = scaled_prev[numeric] * 10
    scaled = decode(scaled_today, scaled_prev)
    assert scaled.composite == original.composite
    assert scaled.participant_reads == original.participant_reads


def test_v2_fresh_positions_outweigh_closures():
    current = pd.Series({"long": 200, "short": 100})
    prior_fresh = pd.Series({"long": 100, "short": 100})
    prior_cover = pd.Series({"long": 200, "short": 200})
    fresh, _ = _fresh_pressure(current, prior_fresh, "long", "short", 1.0)
    covering, _ = _fresh_pressure(current, prior_cover, "long", "short", 1.0)
    assert fresh == 100
    assert covering == 50


def test_v2_stock_options_do_not_manufacture_nifty_direction():
    today, prev, _ = _load()
    today = prev.copy()
    today.loc[today["ClientType"] == "FII", "Option Stock Call Long"] += 1_000_000
    result = decode(today, prev)
    assert result.composite == 0
    assert result.actionability == "NO_DIRECTIONAL_EDGE"
    assert result.participant_reads["FII"]["stock_call"] > 0


def test_v2_fii_pro_conflict_requires_reversal_confirmation():
    today, prev, _ = _load()
    today = prev.copy()
    today.loc[today["ClientType"] == "FII", "Option Index Call Long"] += 100_000
    today.loc[today["ClientType"] == "Pro", "Option Index Call Short"] += 100_000
    result = decode(today, prev)
    assert result.smart_money_conflict
    assert result.actionability == "WAIT_FOR_REVERSAL_CONFIRMATION"
    assert "not as an actionable" in result.conflict_note


def test_unvalidated_confirmation_inputs_do_not_change_v2_class_score():
    today, prev, _ = _load()
    oi_only = decode(today, prev)
    with_confirmation = decode(
        today,
        prev,
        cash={"FII": 1_000_000, "DII": -500_000},
        option_levels={"max_pain": 25_000, "pcr": 1.2, "spot": 25_100},
    )
    assert with_confirmation.composite == oi_only.composite
    assert with_confirmation.bias == oi_only.bias
    cash_signal = next(
        signal for signal in with_confirmation.signals
        if signal.name == "cash_confirmation"
    )
    assert cash_signal.weight == 0.0


def test_levels_and_predictions():
    today, prev, oc = _load()
    res = decode(today, prev, date_str="2026-09-17")
    levels = derive_levels(oc)
    assert levels["max_pain"] > 0
    assert levels["pcr"] > 0
    preds = build_predictions(res, levels)
    assert preds["next_day"]["direction"] in {
        "UP", "DOWN", "SIDEWAYS-UP", "SIDEWAYS-DOWN", "RANGE"}
    assert preds["next_week"]["direction"] == "NO-VALIDATED-EDGE"
    assert preds["next_week"]["confidence"] == 0.0
    assert "CONTEXT_ONLY" in preds["next_week"]["actionability"]
    assert "scenarios" in preds["next_day"]
    demo_report = render_markdown(
        res.to_dict(), preds, levels, "2026-09-17", demo=True
    )
    assert "DEMO FIXTURE" in demo_report


if __name__ == "__main__":
    test_parse_participants()
    test_decode_produces_bias()
    test_levels_and_predictions()
    print("All tests passed.")
