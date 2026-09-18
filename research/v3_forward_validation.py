#!/usr/bin/env python3
"""v3 forward-validation gate.

Replays v1/v2/v3 (production code path) on signal dates strictly AFTER the
fitted archive end (2026-09-04). Nothing about v3 was fitted on these dates,
so once enough sessions accumulate this is the promotion gate.

Data sources, in overlay order (later wins on duplicates):
  1. the pinned mirror archives (through 2026-09-04) — so previous-session OI
     for the first forward week resolves correctly;
  2. the repository's own accumulating stores (data/participant_oi.csv and
     data/index_ohlc.csv) which the daily 9 PM IST workflow appends to;
  3. optionally refreshed mirror/other directories via --extra-* arguments.

Promotion criteria (locked here, not after seeing results):
  - at least MIN_FORWARD_SIGNALS evaluable forward sessions;
  - v3 exact >= the window's majority-class baseline;
  - v3 exact >= v2 exact;
  - v3 non-FLAT sign accuracy >= 52% (and Wilson 95% lower bound > 50%);
  - open-to-close sign is reported but not part of the gate (it is the
    executable-basis diagnostic, historically ~chance for all versions).

Exit code 0 always: INSUFFICIENT_FORWARD_DATA is a normal interim state.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fiidii.backtest import (  # noqa: E402
    BacktestConfig,
    load_ohlc,
    load_participant_oi,
    run_backtest,
)

ARCHIVE_END = "2026-09-04"
MIN_FORWARD_SIGNALS = 60
SIGN_TARGET = 52.0
FLAT_BAND = 0.15


def _load_forward_oi(base_dir: str | None, extras: list[str],
                     repo_store: str = "data/participant_oi.csv") -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if base_dir and Path(base_dir).exists():
        frames.append(load_participant_oi(base_dir))
    for extra in extras:
        frames.append(load_participant_oi(extra))
    store_path = Path(repo_store)
    if store_path.exists():
        store = pd.read_csv(store_path)
        if "date" in store.columns and "ClientType" in store.columns:
            store["date"] = store["date"].astype(str)
            frames.append(store)
    if not frames:
        raise SystemExit("no participant-OI data available at all")
    combined = pd.concat(frames, ignore_index=True)
    combined["date"] = combined["date"].astype(str).str[:10]
    combined = combined.drop_duplicates(["date", "ClientType"], keep="last")
    return combined


def _load_forward_ohlc(base_dir: str | None, extras: list[str],
                       repo_store: str = "data/index_ohlc.csv") -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if base_dir and Path(base_dir).exists():
        frames.append(load_ohlc(base_dir, symbol="NIFTY"))
    for extra in extras:
        frames.append(load_ohlc(extra, symbol="NIFTY"))
    store_path = Path(repo_store)
    if store_path.exists():
        store = load_ohlc(store_path, symbol="NIFTY")
        frames.append(store)
    if not frames:
        raise SystemExit("no NIFTY OHLC available at all")
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates("date", keep="last").sort_values("date")
    return combined.reset_index(drop=True)


def _window_stats(pred: pd.DataFrame) -> dict:
    n = len(pred)
    if not n:
        return {"signals": 0}
    actual_counts = pred["actual_class"].value_counts()
    majority = round(actual_counts.max() / n * 100, 2)
    exact = round(pred["exact_hit"].mean() * 100, 2)
    dir_mask = pred["predicted_class"].isin(["UP", "DOWN"])
    subset = pred[dir_mask]
    nonflat = subset[subset["actual_class"].isin(["UP", "DOWN"])]
    sign_hits = int((nonflat["predicted_class"] == nonflat["actual_class"]).sum())
    sign_n = len(nonflat)
    # Wilson 95% lower bound
    lo = None
    if sign_n:
        from math import sqrt
        z = 1.959963984540054
        p = sign_hits / sign_n
        denom = 1 + z * z / sign_n
        centre = (p + z * z / (2 * sign_n)) / denom
        half = z * sqrt((p * (1 - p) + z * z / (4 * sign_n)) / sign_n) / denom
        lo = round((centre - half) * 100, 2)
    oc = pred.dropna(subset=["intraday_return_pct"])
    oc_nonflat = oc[(oc["intraday_return_pct"].abs() > FLAT_BAND)
                    & oc["predicted_class"].isin(["UP", "DOWN"])]
    oc_sign = None
    if len(oc_nonflat):
        oc_hits = (oc_nonflat["predicted_class"]
                   == oc_nonflat["intraday_return_pct"].map(
                       lambda v: "UP" if v > 0 else "DOWN")).mean()
        oc_sign = round(float(oc_hits) * 100, 2)
    return {
        "signals": n,
        "exact_pct": exact,
        "majority_baseline_pct": majority,
        "dir_coverage_pct": round(dir_mask.mean() * 100, 2),
        "nonflat_sign_pct": round(sign_hits / sign_n * 100, 2) if sign_n else None,
        "nonflat_sign_wilson_lo": lo,
        "nonflat_sign_n": sign_n,
        "open_to_close_sign_pct": oc_sign,
        "open_to_close_sign_n": len(oc_nonflat),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    # Durable compact history is committed with this repository. It replaces the
    # former Arena-local mirror defaults, which disappeared between sessions.
    parser.add_argument("--base-participant-oi", default="historical/participant_oi.csv")
    parser.add_argument("--base-ohlc", default="historical/nifty_ohlc.csv")
    parser.add_argument("--extra-participant-oi", action="append", default=[])
    parser.add_argument("--extra-ohlc", action="append", default=[])
    parser.add_argument("--repo-participant-store", default="data/participant_oi.csv")
    parser.add_argument("--repo-ohlc-store", default="data/index_ohlc.csv")
    parser.add_argument("--output-dir", default="reports/v3_forward_validation")
    parser.add_argument("--from-date", default="2026-09-05")
    args = parser.parse_args()

    oi = _load_forward_oi(args.base_participant_oi, args.extra_participant_oi,
                          repo_store=args.repo_participant_store)
    ohlc = _load_forward_ohlc(args.base_ohlc, args.extra_ohlc,
                              repo_store=args.repo_ohlc_store)
    last_oi = max(oi["date"])
    last_bar = max(ohlc["date"])

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    stats = {}
    all_frames = []
    for version in ("v1", "v2", "v3"):
        cfg = BacktestConfig(decoder_version=version, from_date=args.from_date)
        result = run_backtest(oi, ohlc, config=cfg)
        stats[version] = _window_stats(result.predictions)
        if not result.predictions.empty:
            frame = result.predictions.copy()
            frame.insert(0, "version", version)
            all_frames.append(frame)
        skipped = len(result.skipped)
        stats[version]["skipped"] = skipped

    if all_frames:
        pd.concat(all_frames, ignore_index=True).to_csv(
            out / "forward_predictions.csv", index=False, na_rep="")

    v3, v2 = stats["v3"], stats["v2"]
    n = v3.get("signals", 0)
    checks = {
        "enough_signals": n >= MIN_FORWARD_SIGNALS,
        "v3_beats_baseline": (n >= MIN_FORWARD_SIGNALS
                               and v3.get("exact_pct", 0) >= v3.get("majority_baseline_pct", 100)),
        "v3_beats_v2": (n >= MIN_FORWARD_SIGNALS
                         and v3.get("exact_pct", 0) >= v2.get("exact_pct", 100)),
        "v3_sign_target": (n >= MIN_FORWARD_SIGNALS
                            and (v3.get("nonflat_sign_pct") or 0) >= SIGN_TARGET
                            and (v3.get("nonflat_sign_wilson_lo") or 0) > 50.0),
    }
    state = "COLLECTING_DATA" if not checks["enough_signals"] else (
        "PROMOTE" if all(checks.values()) else "REJECT")

    payload = {
        "archive_fitted_through": ARCHIVE_END,
        "from_date": args.from_date,
        "promotion_criteria": {
            "min_forward_signals": MIN_FORWARD_SIGNALS,
            "exact_ge_majority_baseline": True,
            "exact_ge_v2": True,
            "nonflat_sign_ge_pct": SIGN_TARGET,
            "nonflat_sign_wilson_lower_gt": 50.0,
        },
        "checks": checks,
        "state": state,
        "available_oi_through": last_oi,
        "available_ohlc_through": last_bar.isoformat()[:10] if hasattr(last_bar, "isoformat") else str(last_bar)[:10],
        "stats": {k: v for k, v in stats.items()},
    }
    (out / "gate_status.json").write_text(json.dumps(payload, indent=2, default=str))

    lines = [
        "# v3 forward-validation gate",
        "",
        f"Forward window: signal dates **{args.from_date}** onward "
        f"(fitted archive ended {ARCHIVE_END}).",
        f"Data available: OI through {last_oi}, NIFTY bars through "
        f"{payload['available_ohlc_through']}.",
        "",
        f"## Gate state: **{state}**",
        "",
        "| Check | Result |",
        "|---|---|",
    ]
    for name, ok in checks.items():
        lines.append(f"| {name} | {'PASS' if ok else 'no'} |")
    lines += ["", "| Version | Signals | Exact | Baseline | Coverage | "
              "Non-FLAT sign | Wilson lo | Open-Close sign |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for version in ("v1", "v2", "v3"):
        s = stats[version]
        if not s.get("signals"):
            lines.append(f"| {version} | 0 | n/a | n/a | n/a | n/a | n/a | n/a |")
            continue
        lines.append(
            f"| {version} | {s['signals']} | {s['exact_pct']}% | "
            f"{s['majority_baseline_pct']}% | {s['dir_coverage_pct']}% | "
            f"{s['nonflat_sign_pct']}% (n={s['nonflat_sign_n']}) | "
            f"{s['nonflat_sign_wilson_lo']} | "
            f"{s['open_to_close_sign_pct']}% (n={s['open_to_close_sign_n']}) |"
        )
    lines += [
        "",
        f"`COLLECTING_DATA` until at least {MIN_FORWARD_SIGNALS} evaluable forward "
        "sessions accumulate via the daily 9 PM IST workflow stores "
        "(data/participant_oi.csv + data/index_ohlc.csv), optionally augmented by "
        "--extra-* refreshed mirrors. Rerun: "
        "`PYTHONPATH=src python research/v3_forward_validation.py`.",
        "",
    ]
    (out / "gate_report.md").write_text("\n".join(lines))
    print("\n".join(lines))
    print(f"\nwrote {out}/gate_status.json + gate_report.md")


if __name__ == "__main__":
    main()
