#!/usr/bin/env python3
"""Build the point-in-time feature matrix used by the v3 deep dive.

Every feature row belongs to one *signal date* D and is computed only from:

* participant-OI published for D and earlier sessions;
* participant trading volumes published for D and earlier sessions;
* NIFTY (and other index) OHLC through the close of D.

Targets (never used as inputs at D):

* ``y_cc``  : close[D+1]/close[D] - 1          (headline repo metric basis)
* ``y_oc``  : close[D+1]/open[D+1] - 1         (executable basis)
* ``y_gap`` : open[D+1]/close[D] - 1
* ``y_5d``  : close[D+5]/close[D] - 1          (weekly carry basis)

Values are fractions/percent; no feature uses information after D's close.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fiidii.backtest import (  # noqa: E402
    _date_from_name,
    _file_texts,
    _parse_date,
    load_ohlc,
    load_participant_oi,
)
from fiidii.fetch import _parse_participant_csv  # noqa: E402


def load_named_participant_csvs(path: str, name_token: str) -> pd.DataFrame:
    """load_participant_oi variant that selects filenames by an arbitrary token
    (the production loader hard-requires 'oi', which excludes participant_vol)."""
    texts = _file_texts(Path(path), ".csv")
    texts = [t for t in texts if "participant" in t[0].lower() and name_token in t[0].lower()]
    if not texts:
        raise ValueError(f"no participant {name_token} CSV files under {path}")
    frames: list[pd.DataFrame] = []
    for name, text in texts:
        frame = _parse_participant_csv(text)
        if "ClientType" not in frame or frame.empty:
            continue
        file_date = _date_from_name(name)
        if file_date is None:
            continue
        frame["date"] = file_date
        frames.append(frame)
    if not frames:
        raise ValueError(f"no usable participant {name_token} data under {path}")
    combined = pd.concat(frames, ignore_index=True)
    combined["ClientType"] = combined["ClientType"].astype(str).str.strip()
    combined = combined.drop_duplicates(["date", "ClientType"], keep="last")
    return combined.sort_values(["date", "ClientType"]).reset_index(drop=True)

PARTICIPANTS = ("FII", "Pro", "Client", "DII")
# instrument key -> (long col, short col, market sign when long)
INSTRUMENTS = {
    "ifut": ("Future Index Long", "Future Index Short", +1.0),
    "sfut": ("Future Stock Long", "Future Stock Short", +1.0),
    "icall": ("Option Index Call Long", "Option Index Call Short", +1.0),
    "iput": ("Option Index Put Long", "Option Index Put Short", -1.0),
    "scall": ("Option Stock Call Long", "Option Stock Call Short", +1.0),
    "sput": ("Option Stock Put Long", "Option Stock Put Short", -1.0),
}
CLOSE_W = 0.5  # v2 closure weight


def _frame_by_date(df: pd.DataFrame) -> dict:
    return {d: g.set_index("ClientType") for d, g in df.groupby("date")}


def _oi_matrix(by_date, dates, participants, instruments):
    """Return dict[(participant, instrument)] -> DataFrame(index=date, columns=[l,s])."""
    out = {}
    for p in participants:
        for key, (lcol, scol, _sign) in instruments.items():
            rows = {}
            for d in dates:
                frame = by_date.get(d)
                if frame is None or p not in frame.index:
                    rows[d] = (np.nan, np.nan)
                    continue
                row = frame.loc[p]
                rows[d] = (float(row.get(lcol, np.nan)), float(row.get(scol, np.nan)))
            arr = pd.DataFrame.from_dict(rows, orient="index", columns=["l", "s"]).sort_index()
            out[(p, key)] = arr
    return out


def _total_one_sided(by_date, dates, lcol, scol) -> pd.Series:
    vals = {}
    for d in dates:
        frame = by_date.get(d)
        if frame is None:
            vals[d] = np.nan
            continue
        if "TOTAL" in frame.index:
            row = frame.loc["TOTAL"]
            vals[d] = max(float(row.get(lcol, 0) or 0), float(row.get(scol, 0) or 0))
        else:
            vals[d] = max(frame[lcol].sum(), frame[scol].sum())
    return pd.Series(vals).sort_index()


def expiry_weekday(d: pd.Timestamp) -> int:
    """NSE NIFTY weekly expiry weekday: Thursday before 2025-09-01, Monday after."""
    return 0 if d >= pd.Timestamp("2025-09-01") else 3


def days_to_expiry(d: pd.Timestamp) -> int:
    wd = expiry_weekday(d)
    return (wd - d.dayofweek) % 7


def build_features(oi_dir: str, vol_dir: str | None, ohlc_dir: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    oi = load_participant_oi(oi_dir)
    oi["date"] = pd.to_datetime(oi["date"])
    ohlc = load_ohlc(ohlc_dir, symbol="NIFTY").copy()
    ohlc["date"] = pd.to_datetime(ohlc["date"])
    ohlc = ohlc.sort_values("date").reset_index(drop=True)

    vol = None
    if vol_dir:
        try:
            vol = load_named_participant_csvs(vol_dir, "vol")
            vol["date"] = pd.to_datetime(vol["date"])
        except Exception as exc:  # pragma: no cover - optional input
            print(f"[warn] participant_vol not usable: {exc}")

    market_dates = list(ohlc["date"])
    idx = {d: i for i, d in enumerate(market_dates)}

    oi_dates = sorted(pd.to_datetime(oi["date"]).unique())
    oi_by_date = _frame_by_date(oi)
    level = _oi_matrix(oi_by_date, oi_dates, PARTICIPANTS, INSTRUMENTS)
    market_oi = {
        key: _total_one_sided(oi_by_date, oi_dates, lcol, scol)
        for key, (lcol, scol, _s) in INSTRUMENTS.items()
    }

    # volume matrices (same shape)
    vol_by_date = _frame_by_date(vol) if vol is not None else {}
    have_vol = bool(vol_by_date)
    vol_level = _oi_matrix(vol_by_date, oi_dates, PARTICIPANTS, INSTRUMENTS) if have_vol else {}
    total_vol_market = (
        {key: _total_one_sided(vol_by_date, oi_dates, lcol, scol)
         for key, (lcol, scol, _s) in INSTRUMENTS.items()}
        if have_vol else {}
    )

    feat_rows = {}
    prev_date: pd.Timestamp | None = None
    for d in oi_dates:
        i = idx.get(d)
        if i is None or i == 0 or i >= len(market_dates) - 1:
            prev_date = d
            continue
        prev_market = market_dates[i - 1]
        if prev_date != prev_market:  # same guard as the published replay
            prev_date = d
            continue
        feats: dict[str, float] = {"date": d}
        for p in PARTICIPANTS:
            for key, (_lcol, _scol, sign) in INSTRUMENTS.items():
                arr = level[(p, key)]
                moi = market_oi[key]
                m = moi.get(d, np.nan)
                l_t, s_t = arr.loc[d, "l"], arr.loc[d, "s"]
                l_p, s_p = arr.loc[prev_market, "l"], arr.loc[prev_market, "s"]
                dl = (l_t - l_p) / m if m and not np.isnan(m) else np.nan
                ds = (s_t - s_p) / m if m and not np.isnan(m) else np.nan
                feats[f"{p}_{key}_dl"] = dl
                feats[f"{p}_{key}_ds"] = ds
                feats[f"{p}_{key}_lvl"] = (l_t - s_t) / m if m and not np.isnan(m) else np.nan
                fl, fu = max(dl, 0.0), max(-dl, 0.0)
                fs, sc = max(ds, 0.0), max(-ds, 0.0)
                raw_p = fl - fs + sc - fu     # all actions full weight
                q_p = fl + CLOSE_W * sc - fs - CLOSE_W * fu  # v2 quality-adjusted
                feats[f"{p}_{key}_qflow"] = sign * q_p
                feats[f"{p}_{key}_rflow"] = sign * raw_p
            # index-family aggregates
            feats[f"{p}_index_qflow"] = (
                0.4 * feats[f"{p}_icall_qflow"]
                + 0.4 * feats[f"{p}_iput_qflow"]
                + 0.2 * feats[f"{p}_ifut_qflow"]
            )
            feats[f"{p}_index_rflow"] = (
                0.4 * feats[f"{p}_icall_rflow"]
                + 0.4 * feats[f"{p}_iput_rflow"]
                + 0.2 * feats[f"{p}_ifut_rflow"]
            )
        # market OI changes
        for key in INSTRUMENTS:
            moi = market_oi[key]
            m_t, m_p = moi.get(d, np.nan), moi.get(prev_market, np.nan)
            feats[f"mkt_{key}_dlogoi"] = (
                np.log(m_t / m_p) if m_t and m_p and not np.isnan(m_t) and not np.isnan(m_p) else np.nan
            )
        # participant volume features
        if have_vol:
            for p in PARTICIPANTS:
                for key, (_l, _s, sign) in INSTRUMENTS.items():
                    varr = vol_level[(p, key)]
                    tv = total_vol_market[key]
                    m = tv.get(d, np.nan)
                    vb, vs = varr.loc[d, "l"], varr.loc[d, "s"]
                    feats[f"{p}_{key}_dvol"] = (vb - vs) / m if m and not np.isnan(m) else np.nan
                    feats[f"{p}_{key}_volshare"] = (vb + vs) / (2 * m) if m and not np.isnan(m) else np.nan
        feats["dow"] = d.dayofweek
        feats["dte"] = days_to_expiry(d)
        feats["is_expiry_day"] = float(days_to_expiry(d) == 0)
        feat_rows[d] = feats
        prev_date = d

    feats_df = pd.DataFrame.from_dict(feat_rows, orient="index").sort_index().reset_index(drop=True)

    # ---- price context + targets ------------------------------------------------
    px = ohlc.set_index("date")
    close, open_ = px["close"], px["open"]
    ret1 = close.pct_change()
    ctx = pd.DataFrame(index=px.index)
    ctx["ret1"] = ret1 * 100
    ctx["ret2"] = close.pct_change(2) * 100
    ctx["ret3"] = close.pct_change(3) * 100
    ctx["ret5"] = close.pct_change(5) * 100
    ctx["ret10"] = close.pct_change(10) * 100
    ctx["gap1"] = (open_ / close.shift(1) - 1) * 100
    ctx["oc1"] = (close / open_ - 1) * 100
    ctx["rv5"] = ret1.rolling(5).std() * 100 * np.sqrt(244)
    ctx["rv20"] = ret1.rolling(20).std() * 100 * np.sqrt(244)
    span = (px["high"] - px["low"]) / close * 100
    ctx["range5"] = span.rolling(5).mean()
    ctx["atr5"] = span.rolling(5).mean() / close * 1000  # per-mille scale variant
    ctx["dow"] = px.index.dayofweek
    if "volume" in px:
        ctx["dvol"] = px["volume"].pct_change() * 100
    if "turnover" in px:
        ctx["dturnover"] = px["turnover"].pct_change() * 100

    tgt = pd.DataFrame(index=px.index)
    tgt["y_cc"] = (close.shift(-1) / close - 1) * 100
    tgt["y_oc"] = (close.shift(-1) / open_.shift(-1) - 1) * 100
    tgt["y_gap"] = (open_.shift(-1) / close - 1) * 100
    tgt["y_5d"] = (close.shift(-5) / close - 1) * 100
    tgt["target_date"] = px.index.to_series().shift(-1)
    tgt["target5_date"] = px.index.to_series().shift(-5)

    merged = feats_df.merge(
        pd.concat([ctx.add_prefix("px_"), tgt], axis=1).reset_index(),
        on="date", how="inner",
    ).sort_values("date").reset_index(drop=True)

    # multi-session rolling flow aggregates (sums over trailing k sessions)
    flow_cols = [c for c in merged.columns if c.endswith("_qflow") or c.endswith("_rflow")]
    for k in (2, 3, 5):
        rolled = merged[flow_cols].rolling(k, min_periods=k).sum().add_suffix(f"_sum{k}")
        merged = pd.concat([merged, rolled], axis=1)

    info = {
        "features": merged,
        "period": pd.cut(
            merged["date"].dt.year,
            bins=[2022, 2024, 2025, 2099],
            labels=["dev2023_24", "val2025", "confirm2026"],
        ),
    }
    merged["period"] = info["period"].astype(str)
    return merged, ohlc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oi", default="/home/user/historical/participant_oi")
    parser.add_argument("--vol", default="/home/user/historical/participant_vol")
    parser.add_argument("--ohlc", default="/home/user/historical/index_close")
    parser.add_argument("--out", default="/home/user/features/v3_matrix.csv")
    args = parser.parse_args()

    merged, _ = build_features(args.oi, args.vol, args.ohlc)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out, index=False, float_format="%.8f")
    print(f"wrote {out} with {len(merged)} rows x {merged.shape[1]} cols")
    print(merged["period"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
