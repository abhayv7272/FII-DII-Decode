import pytest

from fiidii.gap_sniper import tiny_gap_fill_signal


def test_tiny_gap_fill_signal_gap_up_active():
    signal = tiny_gap_fill_signal(open_price=23020.0, previous_close=23000.0)

    assert signal["active"] is True
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
