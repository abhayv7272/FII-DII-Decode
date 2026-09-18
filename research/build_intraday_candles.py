"""Build durable NIFTY intraday candles from a raw 1-minute archive.

The raw files are intentionally kept outside Git because they are bulky.  This
script converts them into compact, reproducible 10/15-minute bars that can be
committed under ``historical/``.

Example
-------

    .venv/bin/python research/build_intraday_candles.py \
      --raw-root /home/user/historical/technovusin-nifty50-historical-data/1min \
      --interval 15 \
      --out historical/nifty_15m.csv
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

MARKET_OPEN_MINUTE = 9 * 60 + 15
MARKET_CLOSE_LAST_MINUTE = 15 * 60 + 29


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_raw_file(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols = {c: c.strip().lower() for c in df.columns}
    df = df.rename(columns=cols)
    required = {"timestamp", "open", "high", "low", "close"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {missing}")
    if "volume" not in df.columns:
        df["volume"] = pd.NA
    out = df[["timestamp", "open", "high", "low", "close", "volume"]].copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["timestamp", "open", "high", "low", "close"])
    return out


def load_raw_files(paths: Iterable[Path]) -> pd.DataFrame:
    frames = [_load_raw_file(p) for p in paths]
    if not frames:
        raise ValueError("no raw CSV files found")
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["timestamp"], keep="last")
    df = df.sort_values("timestamp").reset_index(drop=True)
    minute = df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute
    df = df[(minute >= MARKET_OPEN_MINUTE) & (minute <= MARKET_CLOSE_LAST_MINUTE)].copy()
    df["date"] = df["timestamp"].dt.date.astype(str)
    return df


def resample_intraday(df: pd.DataFrame, interval: int) -> pd.DataFrame:
    if interval <= 0:
        raise ValueError("interval must be positive")
    minute = df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute
    offset = minute - MARKET_OPEN_MINUTE
    valid = offset >= 0
    if interval == 15:
        # NSE cash session has exactly 375 one-minute observations (09:15-15:29),
        # so 15m gives 25 complete bars without a partial close bar.
        complete_last_offset = MARKET_CLOSE_LAST_MINUTE - MARKET_OPEN_MINUTE
    else:
        # For intervals such as 10m the session length is not divisible by the
        # interval. Keep the last partial bar but mark its minute count.
        complete_last_offset = MARKET_CLOSE_LAST_MINUTE - MARKET_OPEN_MINUTE
    work = df[valid & (offset <= complete_last_offset)].copy()
    offset = work["timestamp"].dt.hour * 60 + work["timestamp"].dt.minute - MARKET_OPEN_MINUTE
    work["bar_index"] = (offset // interval).astype(int)
    work["bar_start_minute"] = MARKET_OPEN_MINUTE + work["bar_index"] * interval
    work["bar_start"] = pd.to_datetime(work["date"]) + pd.to_timedelta(
        work["bar_start_minute"], unit="m"
    )
    grouped = work.groupby(["date", "bar_index", "bar_start"], sort=True)
    out = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", lambda s: s.sum(min_count=1)),
        minute_count=("timestamp", "count"),
        first_timestamp=("timestamp", "first"),
        last_timestamp=("timestamp", "last"),
    ).reset_index()
    out["timestamp"] = out["bar_start"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    out = out[
        [
            "date",
            "timestamp",
            "bar_index",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "minute_count",
            "first_timestamp",
            "last_timestamp",
        ]
    ]
    # Preserve blanks rather than zeros for archive segments that do not contain
    # volume (older files only have OHLC).
    if out["volume"].isna().all():
        out["volume"] = pd.NA
    return out


def write_manifest(out: Path, raw_files: list[Path], interval: int, rows: int) -> Path:
    manifest = {
        "source_repo": "technovusin/nifty50-historical-data",
        "source_url": "https://github.com/technovusin/nifty50-historical-data",
        "source_branch": "main",
        "source_license": "MIT License per upstream repository metadata/README",
        "raw_files_kept_outside_git": True,
        "raw_root_used": str(raw_files[0].parents[1]) if raw_files else None,
        "interval_minutes": interval,
        "output": str(out),
        "output_rows": rows,
        "output_sha256": _sha256(out),
        "raw_files": [
            {"path": str(p), "bytes": p.stat().st_size, "sha256": _sha256(p)}
            for p in raw_files
        ],
    }
    path = out.with_suffix(out.suffix + ".manifest.json")
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-root", default="/home/user/historical/technovusin-nifty50-historical-data/1min")
    ap.add_argument("--interval", type=int, default=15, help="bar interval in minutes")
    ap.add_argument("--out", default="historical/nifty_15m.csv")
    args = ap.parse_args()

    raw_root = Path(args.raw_root)
    raw_files = sorted(raw_root.rglob("*.csv"))
    if not raw_files:
        raise SystemExit(f"no CSV files found below {raw_root}")
    df = load_raw_files(raw_files)
    bars = resample_intraday(df, args.interval)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    bars.to_csv(out, index=False)
    manifest = write_manifest(out, raw_files, args.interval, len(bars))
    print(
        json.dumps(
            {
                "raw_files": len(raw_files),
                "raw_rows": int(len(df)),
                "bars": int(len(bars)),
                "date_min": str(bars["date"].min()),
                "date_max": str(bars["date"].max()),
                "output": str(out),
                "manifest": str(manifest),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
