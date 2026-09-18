"""Regression tests for durable compact historical research inputs."""
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "research"))

from build_compact_history import PINNED_SOURCE_COMMIT, build  # noqa: E402
from fiidii.backtest import load_ohlc, load_participant_oi  # noqa: E402
from v3_features import load_named_participant_csvs  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


def _write_index_close(path: Path, date_text: str, close: float) -> None:
    pd.DataFrame([
        {
            "Index Name": "Nifty 50",
            "Index Date": date_text,
            "Open Index Value": close - 30,
            "High Index Value": close + 50,
            "Low Index Value": close - 70,
            "Closing Index Value": close,
        },
        {
            "Index Name": "Nifty Bank",
            "Index Date": date_text,
            "Open Index Value": 54000,
            "High Index Value": 54100,
            "Low Index Value": 53900,
            "Closing Index Value": 54050,
        },
    ]).to_csv(path, index=False)


def test_compact_builder_outputs_replayable_oi_ohlc_and_volume(tmp_path):
    root = tmp_path / "source"
    archives = root / "nse_archives"
    oi_dir = archives / "participant_oi"
    close_dir = archives / "index_close"
    volume_dir = archives / "participant_vol"
    for path in (oi_dir, close_dir, volume_dir):
        path.mkdir(parents=True)

    previous = (FIX / "fao_participant_oi_prev.csv").read_text()
    current = (FIX / "fao_participant_oi_sample.csv").read_text()
    (oi_dir / "fao_participant_oi_01012026.csv").write_text(previous)
    (oi_dir / "fao_participant_oi_02012026.csv").write_text(current)
    (volume_dir / "fao_participant_vol_01012026.csv").write_text(previous)
    (volume_dir / "fao_participant_vol_02012026.csv").write_text(current)
    _write_index_close(close_dir / "ind_close_all_20260101.csv", "01-01-2026", 24750)
    _write_index_close(close_dir / "ind_close_all_20260102.csv", "02-01-2026", 24900)

    paths = build(root, tmp_path / "historical")
    assert set(paths) == {
        "participant_oi.csv", "nifty_ohlc.csv", "participant_vol.csv", "README.md"
    }
    assert all(path.exists() for path in paths.values())

    oi = load_participant_oi(paths["participant_oi.csv"])
    ohlc = load_ohlc(paths["nifty_ohlc.csv"], "NIFTY")
    # Regression: v3 research accepts the compact volume CSV, not only raw files.
    volume = load_named_participant_csvs(str(paths["participant_vol.csv"]), "vol")
    assert len(oi) == 10  # two dates x Client/DII/FII/Pro/TOTAL
    assert len(ohlc) == 2
    assert len(volume) == 10
    assert oi["date"].min().isoformat() == "2026-01-01"
    assert ohlc["close"].tolist() == [24750, 24900]
    assert volume["date"].max().isoformat() == "2026-01-02"
    readme = paths["README.md"].read_text()
    assert PINNED_SOURCE_COMMIT in readme
    assert "SHA-256" in readme
