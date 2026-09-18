import json

import pytest

from fiidii.cli import main
from fiidii.gap_sniper import tiny_gap_fill_playbook, tiny_gap_fill_signal


def test_tiny_gap_fill_playbook_waits_for_open():
    playbook = tiny_gap_fill_playbook()

    assert playbook["active"] is None
    assert playbook["status"] == "WAITING_FOR_OPEN"
    assert playbook["direction_to_target"] == "DEPENDS_ON_OPEN_GAP"
    assert playbook["validation"]["overall_hit_rate"] > 90


def test_tiny_gap_fill_signal_gap_up_active():
    signal = tiny_gap_fill_signal(open_price=23020.0, previous_close=23000.0)

    assert signal["active"] is True
    assert signal["status"] == "ACTIVE"
    assert signal["direction_to_target"] == "DOWN"
    assert signal["target"] == 23000.0
    assert 0.03 <= signal["abs_gap_pct"] < 0.12
    assert signal["validation"]["confirm_2026_hit_rate"] == 87.5


def test_tiny_gap_fill_signal_gap_down_active():
    signal = tiny_gap_fill_signal(open_price=22980.0, previous_close=23000.0)

    assert signal["active"] is True
    assert signal["direction_to_target"] == "UP"
    assert signal["target"] == 23000.0


def test_tiny_gap_fill_signal_outside_band_skips():
    signal = tiny_gap_fill_signal(open_price=23200.0, previous_close=23000.0)

    assert signal["active"] is False
    assert signal["direction_to_target"] == "NO_SIGNAL"
    assert signal["target"] is None


def test_tiny_gap_fill_signal_rejects_bad_prices():
    with pytest.raises(ValueError):
        tiny_gap_fill_signal(open_price=0.0, previous_close=23000.0)


def test_sniper_cli_json(capsys):
    assert main([
        "sniper",
        "--open",
        "23020",
        "--previous-close",
        "23000",
        "--high",
        "23025",
        "--low",
        "22998",
        "--json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["active"] is True
    assert payload["direction_to_target"] == "DOWN"
    assert payload["target_observed_in_supplied_range"] is True
