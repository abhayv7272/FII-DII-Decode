#!/usr/bin/env python3
"""Build small, durable research inputs from raw archive-shaped NSE files.

The project must be able to replay its published daily and forward-validation
backtests after an Arena sandbox reset. Raw mirror directories contain roughly
1,500 dated files and are needlessly large for that purpose. This script
consolidates only the point-in-time fields the model uses:

* participant OI (all participant rows, one row per date/participant),
* NIFTY 50 daily OHLC,
* India VIX daily OHLC, and
* participant volumes (research-only; not a production-score input).

It does not mutate ``data/`` live stores. Use a pinned source directory such
as ``sahilempire/groww-market-data`` at the source commit recorded in the
output README. The four CSV outputs are deterministic for a given source
revision; the README additionally records its build time.

Example:
    PYTHONPATH=src python research/build_compact_history.py \
      --source-root /tmp/groww-market-data
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fiidii.backtest import _date_from_name, _file_texts, _parse_date, load_ohlc, load_participant_oi  # noqa: E402
from fiidii.fetch import _parse_participant_csv  # noqa: E402

PINNED_SOURCE_REPOSITORY = "https://github.com/sahilempire/groww-market-data"
PINNED_SOURCE_COMMIT = "7d481cf1fcffe44be68852892028195c4f12dddd"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_participant_volume(path: str | Path) -> pd.DataFrame:
    """Load raw dated volume reports into a compact point-in-time dataframe."""
    source = Path(path)
    texts = _file_texts(source, ".csv")
    texts = [item for item in texts if "participant" in item[0].lower() and "vol" in item[0].lower()]
    if not texts:
        raise ValueError(f"no participant-volume CSV files found under {source}")

    frames: list[pd.DataFrame] = []
    failures: list[str] = []
    for name, text in texts:
        try:
            frame = _parse_participant_csv(text)
        except Exception as exc:
            failures.append(f"{name}: {exc}")
            continue
        if "ClientType" not in frame or frame.empty:
            failures.append(f"{name}: no participant rows")
            continue
        file_date = _date_from_name(name)
        if file_date is None:
            failures.append(f"{name}: date missing from filename")
            continue
        frame["date"] = file_date
        frames.append(frame)

    if not frames:
        detail = "; ".join(failures[:5])
        raise ValueError(f"no usable participant-volume data in {source}. {detail}")
    combined = pd.concat(frames, ignore_index=True)
    combined["ClientType"] = combined["ClientType"].astype(str).str.strip()
    return (combined.drop_duplicates(["date", "ClientType"], keep="last")
            .sort_values(["date", "ClientType"]).reset_index(drop=True))


def _iso_date_column(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    parsed = output["date"].map(_parse_date)
    if parsed.isna().any():
        raise ValueError("consolidated frame contains an invalid date")
    output["date"] = parsed.map(lambda value: value.isoformat())
    leading = ["date", "ClientType"]
    remaining = [column for column in output.columns if column not in leading]
    return output[[column for column in leading if column in output] + remaining]


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, lineterminator="\n")


def _summary_line(name: str, frame: pd.DataFrame, path: Path) -> str:
    dates = pd.to_datetime(frame["date"], errors="raise")
    return (
        f"| `{name}` | {len(frame):,} | {dates.min():%Y-%m-%d} to "
        f"{dates.max():%Y-%m-%d} | `{_sha256(path)}` |"
    )


def build(source_root: Path, output_dir: Path) -> dict[str, Path]:
    archives = source_root / "nse_archives"
    oi_source = archives / "participant_oi"
    ohlc_source = archives / "index_close"
    volume_source = archives / "participant_vol"
    missing = [str(path) for path in (oi_source, ohlc_source, volume_source) if not path.exists()]
    if missing:
        raise FileNotFoundError("source archive is missing: " + ", ".join(missing))

    oi = _iso_date_column(load_participant_oi(oi_source))
    # Keep the established compact daily-OHLC schema (date/open/high/low/close)
    # for both indices.  ``load_ohlc`` accepts this canonical no-symbol form.
    ohlc = load_ohlc(ohlc_source, symbol="NIFTY").copy()
    ohlc["date"] = pd.to_datetime(ohlc["date"], errors="raise").dt.strftime("%Y-%m-%d")
    vix = load_ohlc(ohlc_source, symbol="India VIX").copy()
    vix["date"] = pd.to_datetime(vix["date"], errors="raise").dt.strftime("%Y-%m-%d")
    volume = _iso_date_column(load_participant_volume(volume_source))

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "participant_oi.csv": output_dir / "participant_oi.csv",
        "nifty_ohlc.csv": output_dir / "nifty_ohlc.csv",
        "india_vix_ohlc.csv": output_dir / "india_vix_ohlc.csv",
        "participant_vol.csv": output_dir / "participant_vol.csv",
    }
    _write_csv(oi, paths["participant_oi.csv"])
    _write_csv(ohlc, paths["nifty_ohlc.csv"])
    _write_csv(vix, paths["india_vix_ohlc.csv"])
    _write_csv(volume, paths["participant_vol.csv"])

    source_file_counts = {
        "participant OI": len(list(oi_source.glob("*.csv"))),
        "index close": len(list(ohlc_source.glob("*.csv"))),
        "participant volume": len(list(volume_source.glob("*.csv"))),
    }
    readme = [
        "# Compact historical research inputs",
        "",
        "This directory contains consolidated **point-in-time historical inputs** for",
        "reproducible model research and the v3 forward-validation gate. They are not",
        "live stores and are never overwritten by the scheduled workflow.",
        "",
        f"- Source mirror: `{PINNED_SOURCE_REPOSITORY}`",
        f"- Pinned source commit: `{PINNED_SOURCE_COMMIT}`",
        "- Source format: archive-shaped public NSE reports; source provenance and the",
        "  raw-archive hashes are in `reports/backtest_2023-08_to_2026-09/provenance.json`.",
        f"- Built at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"- Raw file counts: participant OI {source_file_counts['participant OI']}, "
        f"index close {source_file_counts['index close']}, participant volume "
        f"{source_file_counts['participant volume']}",
        "",
        "| File | Rows | Date range | SHA-256 |",
        "|---|---:|---|---|",
        _summary_line("participant_oi.csv", oi, paths["participant_oi.csv"]),
        _summary_line("nifty_ohlc.csv", ohlc, paths["nifty_ohlc.csv"]),
        _summary_line("india_vix_ohlc.csv", vix, paths["india_vix_ohlc.csv"]),
        _summary_line("participant_vol.csv", volume, paths["participant_vol.csv"]),
        "",
        "## Intended use",
        "",
        "```bash",
        "python backtest.py \\",
        "  --participant-oi historical/participant_oi.csv \\",
        "  --ohlc historical/nifty_ohlc.csv \\",
        "  --decoder-version v3 \\",
        "  --output-dir /tmp/v3-replay",
        "",
        "PYTHONPATH=src python research/v3_forward_validation.py",
        "```",
        "",
        "Participant volumes are research-only; they are not consumed by the locked",
        "v2 or candidate-v3 production score. Daily OHLC is sufficient for historical",
        "close-to-close and gap diagnostics, but not for validating 10–15 minute",
        "level-reclaim, sweep, stop, or slippage claims.",
    ]
    paths["README.md"] = output_dir / "README.md"
    paths["README.md"].write_text("\n".join(readme) + "\n")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root",
        required=True,
        help="checkout of sahilempire/groww-market-data at the pinned source commit",
    )
    parser.add_argument("--output-dir", default="historical")
    args = parser.parse_args()
    paths = build(Path(args.source_root), Path(args.output_dir))
    for name, path in paths.items():
        print(f"wrote {name}: {path} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
