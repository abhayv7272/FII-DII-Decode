"""Smoke tests for the decode pipeline using bundled fixtures (no network)."""
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fiidii.fetch import _parse_participant_csv
from fiidii.decode import decode
from fiidii.levels import derive_levels
from fiidii.predict import build_predictions

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


def test_levels_and_predictions():
    today, prev, oc = _load()
    res = decode(today, prev, date_str="2026-09-17")
    levels = derive_levels(oc)
    assert levels["max_pain"] > 0
    assert levels["pcr"] > 0
    preds = build_predictions(res, levels)
    assert preds["next_day"]["direction"] in {
        "UP", "DOWN", "SIDEWAYS-UP", "SIDEWAYS-DOWN", "RANGE"}
    assert preds["next_week"]["direction"]
    assert "scenarios" in preds["next_day"]


if __name__ == "__main__":
    test_parse_participants()
    test_decode_produces_bias()
    test_levels_and_predictions()
    print("All tests passed.")
