"""Point-in-time backtesting for the FII/DII participant-OI decoder.

The harness deliberately replays the production pipeline instead of scoring a
precomputed signal file:

* signal date D uses participant OI from D and the immediately preceding market
  session only;
* the option-chain snapshot, when available, must also be dated D;
* the next-day prediction is compared with the next available market session's
  close-to-close NIFTY return.

No model parameters are fitted here, so "walk-forward" means chronological,
point-in-time replay.  Cash flow is omitted unless historical point-in-time cash
inputs are added in the future; using today's cash API for old dates would create
look-ahead bias.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
import json
from pathlib import Path
import re
from typing import Iterable, Mapping, Optional
import zipfile

import pandas as pd

from .decode import decode
from .fetch import _parse_participant_csv
from .levels import derive_levels
from .predict import build_predictions


CLASSES = ("UP", "FLAT", "DOWN")
REQUIRED_PARTICIPANTS = {"CLIENT", "FII", "PRO"}
PREDICTION_COLUMNS = (
    "signal_date", "previous_oi_date", "target_date", "prediction_raw",
    "predicted_class", "actual_class", "exact_hit", "direction_hit", "bias",
    "composite", "confidence", "smart_money_conflict", "signal_close",
    "target_open", "target_high", "target_low", "target_close", "gap_pct",
    "intraday_return_pct", "actual_return_pct", "option_chain_available",
    "support_level", "support_tested", "support_held", "resistance_level",
    "resistance_tested", "resistance_held", "level_tests", "level_hits",
)


@dataclass(frozen=True)
class BacktestConfig:
    """Settings whose values materially affect the reported metrics.

    Percent values use percentage points, not decimal fractions.  For example,
    ``flat_threshold_pct=0.15`` labels returns from -0.15% through +0.15% FLAT.
    """

    symbol: str = "NIFTY"
    flat_threshold_pct: float = 0.15
    level_touch_tolerance_pct: float = 0.05
    from_date: Optional[str] = None
    to_date: Optional[str] = None

    def __post_init__(self) -> None:
        if self.flat_threshold_pct < 0:
            raise ValueError("flat_threshold_pct must be >= 0")
        if self.level_touch_tolerance_pct < 0:
            raise ValueError("level_touch_tolerance_pct must be >= 0")
        if self.from_date and _parse_date(self.from_date) is None:
            raise ValueError(f"invalid from_date: {self.from_date!r}")
        if self.to_date and _parse_date(self.to_date) is None:
            raise ValueError(f"invalid to_date: {self.to_date!r}")
        if self.from_date and self.to_date:
            if _parse_date(self.from_date) > _parse_date(self.to_date):
                raise ValueError("from_date must not be later than to_date")


@dataclass
class BacktestResult:
    predictions: pd.DataFrame
    skipped: pd.DataFrame
    confidence_curve: pd.DataFrame
    metrics: dict
    config: BacktestConfig
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------
def _parse_date(value) -> Optional[date]:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None
    # Keep ISO dates unambiguous even though Indian exchange files otherwise use
    # day-first dates.
    iso = re.match(r"^(\d{4})-(\d{2})-(\d{2})(?:\D.*)?$", text)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return None
    try:
        parsed = pd.to_datetime(text, dayfirst=True, errors="raise")
        return None if pd.isna(parsed) else parsed.date()
    except (TypeError, ValueError, OverflowError):
        return None


def _date_from_name(name: str) -> Optional[date]:
    """Read YYYY-MM-DD, YYYYMMDD, or NSE's DDMMYYYY from a file name."""
    iso = re.search(r"(?<!\d)(20\d{2})[-_](\d{2})[-_](\d{2})(?!\d)", name)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return None

    compact = re.findall(r"(?<!\d)(\d{8})(?!\d)", name)
    for token in reversed(compact):
        try:
            if token.startswith("20"):
                return datetime.strptime(token, "%Y%m%d").date()
            return datetime.strptime(token, "%d%m%Y").date()
        except ValueError:
            continue
    return None


def _normalise_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _file_texts(path: Path, suffix: str) -> list[tuple[str, str]]:
    """Return named text files from one file, a directory, or a ZIP archive."""
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = suffix.lower()

    if path.is_dir():
        files = sorted(
            p for p in path.rglob("*") if p.is_file() and p.suffix.lower() == suffix
        )
        return [(str(p), p.read_text(encoding="utf-8-sig", errors="replace")) for p in files]
    if path.suffix.lower() == ".zip":
        out: list[tuple[str, str]] = []
        try:
            with zipfile.ZipFile(path) as archive:
                for member in sorted(archive.namelist()):
                    if not member.endswith("/") and Path(member).suffix.lower() == suffix:
                        text = archive.read(member).decode("utf-8-sig", errors="replace")
                        out.append((member, text))
        except zipfile.BadZipFile as exc:
            raise ValueError(f"invalid ZIP archive: {path}") from exc
        return out
    if path.suffix.lower() != suffix:
        raise ValueError(f"expected {suffix}, ZIP, or directory; got {path}")
    return [(str(path), path.read_text(encoding="utf-8-sig", errors="replace"))]


def load_participant_oi(path: str | Path) -> pd.DataFrame:
    """Load raw daily participant-OI files or one consolidated history CSV.

    Directory/ZIP inputs are restricted to CSV names containing both
    ``participant`` and ``oi`` so an adjacent OHLC CSV cannot be mistaken for OI.
    Raw NSE files get their date from ``fao_participant_oi_DDMMYYYY.csv``; a
    consolidated file must contain a ``date`` column.
    """
    source = Path(path)
    texts = _file_texts(source, ".csv")
    if source.is_dir() or source.suffix.lower() == ".zip":
        texts = [item for item in texts
                 if "participant" in item[0].lower() and "oi" in item[0].lower()]
    if not texts:
        raise ValueError(f"no participant-OI CSV files found under {source}")

    frames: list[pd.DataFrame] = []
    failures: list[str] = []
    for name, text in texts:
        try:
            frame = _parse_participant_csv(text)
        except Exception as exc:  # report bad archive members together
            failures.append(f"{name}: {exc}")
            continue
        if "ClientType" not in frame or frame.empty:
            failures.append(f"{name}: no participant rows")
            continue

        if "date" in frame.columns:
            parsed = frame["date"].map(_parse_date)
            if parsed.isna().any():
                failures.append(f"{name}: invalid or blank date values")
                continue
            frame["date"] = parsed
        else:
            file_date = _date_from_name(name)
            if file_date is None:
                failures.append(f"{name}: date missing from both data and filename")
                continue
            frame["date"] = file_date
        frames.append(frame)

    if not frames:
        detail = "; ".join(failures[:5])
        raise ValueError(f"no usable participant-OI data in {source}. {detail}")

    combined = pd.concat(frames, ignore_index=True)
    combined["ClientType"] = combined["ClientType"].astype(str).str.strip()
    combined = combined.drop_duplicates(["date", "ClientType"], keep="last")
    combined = combined.sort_values(["date", "ClientType"]).reset_index(drop=True)
    return combined


def _find_column(columns: Iterable[str], aliases: Iterable[str]) -> Optional[str]:
    available = {_normalise_key(c): c for c in columns}
    for alias in aliases:
        if _normalise_key(alias) in available:
            return available[_normalise_key(alias)]
    return None


def _symbol_aliases(symbol: str) -> set[str]:
    norm = _normalise_key(symbol)
    aliases = {
        "nifty": {"nifty", "nifty50"},
        "nifty50": {"nifty", "nifty50"},
        "banknifty": {"banknifty", "niftybank"},
        "niftybank": {"banknifty", "niftybank"},
        "finnifty": {"finnifty", "niftyfinancialservices"},
        "midcpnifty": {"midcpnifty", "niftymidselect"},
    }
    return aliases.get(norm, {norm})


def load_ohlc(path: str | Path, symbol: str = "NIFTY") -> pd.DataFrame:
    """Load daily index prices from a CSV with flexible NSE-style headings.

    Date and Close are mandatory. Open/High/Low are optional: direction metrics
    still work without them, while level-reaction observations are left unscored.
    """
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    if source.suffix.lower() != ".csv":
        raise ValueError("OHLC input must be a CSV file")

    raw = pd.read_csv(source)
    raw.columns = [str(c).strip() for c in raw.columns]
    date_col = _find_column(
        raw.columns,
        ("date", "historical date", "timestamp", "ch_timestamp", "eod_timestamp", "datetime"),
    )
    close_col = _find_column(
        raw.columns,
        ("close", "close price", "closing index value", "close index val",
         "eod close index val", "last"),
    )
    if not date_col or not close_col:
        raise ValueError("OHLC CSV must contain Date and Close columns")

    symbol_col = _find_column(raw.columns, ("symbol", "index", "index name", "name"))
    if symbol_col:
        wanted = _symbol_aliases(symbol)
        normalised = raw[symbol_col].astype(str).map(_normalise_key)
        selected = raw[normalised.isin(wanted)].copy()
        if selected.empty:
            available = sorted(raw[symbol_col].dropna().astype(str).unique())[:10]
            raise ValueError(f"symbol {symbol!r} not found in OHLC CSV; available: {available}")
        raw = selected

    parsed_dates = raw[date_col].map(_parse_date)
    if parsed_dates.isna().any():
        bad = raw.loc[parsed_dates.isna(), date_col].astype(str).head(3).tolist()
        raise ValueError(f"could not parse OHLC dates (examples: {bad})")

    aliases = {
        "open": ("open", "open price", "open index value", "open index val",
                 "eod open index val"),
        "high": ("high", "high price", "high index value", "high index val",
                 "eod high index val"),
        "low": ("low", "low price", "low index value", "low index val",
                "eod low index val"),
        "close": (close_col,),
    }
    out = pd.DataFrame({"date": parsed_dates})
    for target, choices in aliases.items():
        source_col = _find_column(raw.columns, choices)
        if source_col:
            values = raw[source_col].astype(str).str.replace(",", "", regex=False)
            out[target] = pd.to_numeric(values, errors="coerce")
        else:
            out[target] = float("nan")

    if out["close"].isna().any() or (out["close"] <= 0).any():
        raise ValueError("OHLC Close contains missing, non-numeric, or non-positive values")
    complete_range = out[["high", "low"]].notna().all(axis=1)
    if (out.loc[complete_range, "high"] < out.loc[complete_range, "low"]).any():
        raise ValueError("OHLC contains High values below Low")

    return (out.drop_duplicates("date", keep="last")
            .sort_values("date").reset_index(drop=True))


def _chain_date(name: str, raw: dict) -> Optional[date]:
    file_date = _date_from_name(name)
    if file_date:
        return file_date
    records = raw.get("records", {}) if isinstance(raw, dict) else {}
    for key in ("timestamp", "timeStamp", "date"):
        parsed = _parse_date(records.get(key))
        if parsed:
            return parsed
    return None


def _chain_matches_symbol(name: str, raw: dict, symbol: str) -> bool:
    wanted = _symbol_aliases(symbol)
    records = raw.get("records", {}) if isinstance(raw, dict) else {}
    underlying = records.get("underlying") or raw.get("underlying")
    if underlying:
        return _normalise_key(underlying) in wanted

    stem = Path(name).stem.lower()
    filename = _normalise_key(stem)
    tokens = {_normalise_key(token) for token in re.split(r"[^a-z0-9]+", stem) if token}
    symbol_groups = (
        {"banknifty", "niftybank"},
        {"finnifty", "niftyfinancialservices"},
        {"midcpnifty", "niftymidselect"},
    )
    detected: Optional[set[str]] = None
    for group in symbol_groups:
        if any(alias in filename for alias in group):
            detected = group
            break
    if detected is None and (
        "nifty" in tokens or "nifty50" in filename or "optionchainnifty" in filename
    ):
        detected = {"nifty", "nifty50"}

    # A generic dated option_chain file is accepted. A filename explicitly
    # identifying another index is not.
    if detected is not None:
        return bool(wanted & detected)
    return "optionchain" in filename


def load_option_chains(path: str | Path, symbol: str = "NIFTY") -> dict[date, dict]:
    """Load point-in-time option-chain JSON snapshots from a directory or ZIP."""
    source = Path(path)
    texts = _file_texts(source, ".json")
    chains: dict[date, dict] = {}
    for name, text in texts:
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(raw, dict) or not raw.get("records", {}).get("data"):
            continue
        if not _chain_matches_symbol(name, raw, symbol):
            continue
        snapshot_date = _chain_date(name, raw)
        if snapshot_date:
            chains[snapshot_date] = raw
    if not chains:
        raise ValueError(f"no dated {symbol} option-chain snapshots found under {source}")
    return chains


# ---------------------------------------------------------------------------
# Replay and scoring
# ---------------------------------------------------------------------------
def prediction_class(direction: str) -> str:
    mapping = {
        "UP": "UP",
        "SIDEWAYS-UP": "UP",
        "RANGE": "FLAT",
        "SIDEWAYS-DOWN": "DOWN",
        "DOWN": "DOWN",
    }
    try:
        return mapping[str(direction).upper()]
    except KeyError as exc:
        raise ValueError(f"unknown prediction direction: {direction!r}") from exc


def actual_class(return_pct: float, flat_threshold_pct: float) -> str:
    if return_pct > flat_threshold_pct:
        return "UP"
    if return_pct < -flat_threshold_pct:
        return "DOWN"
    return "FLAT"


def _participants_present(frame: pd.DataFrame) -> set[str]:
    return set(frame["ClientType"].astype(str).str.upper())


def _number(value) -> Optional[float]:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if pd.notna(result) else None


def _level_observation(level: Optional[dict], kind: str, target: pd.Series,
                       tolerance_pct: float) -> tuple[Optional[float], Optional[bool], Optional[bool]]:
    """Daily-bar proxy: did the range enter the level band, and did it close defended?"""
    if not level:
        return None, None, None
    strike = _number(level.get("strike"))
    high, low, close = (_number(target.get(k)) for k in ("high", "low", "close"))
    if strike is None or high is None or low is None or close is None:
        return strike, None, None

    tolerance = tolerance_pct / 100.0
    tested = low <= strike * (1 + tolerance) and high >= strike * (1 - tolerance)
    if not tested:
        return strike, False, None
    held = close >= strike if kind == "support" else close <= strike
    return strike, True, bool(held)


def run_backtest(participant_oi: pd.DataFrame, ohlc: pd.DataFrame,
                 option_chains: Optional[Mapping[date, dict]] = None,
                 config: Optional[BacktestConfig] = None) -> BacktestResult:
    """Chronologically replay and score next-session predictions.

    A signal is skipped unless OI exists for both the signal date and the exact
    previous date in the supplied OHLC trading calendar. This prevents a missing
    OI file from silently turning a multi-session change into a one-session change.
    """
    config = config or BacktestConfig()
    option_chains = option_chains or {}

    oi = participant_oi.copy()
    if "date" not in oi or "ClientType" not in oi:
        raise ValueError("participant_oi requires date and ClientType columns")
    oi["date"] = oi["date"].map(_parse_date)
    if oi["date"].isna().any():
        raise ValueError("participant_oi contains invalid dates")
    oi = oi.drop_duplicates(["date", "ClientType"], keep="last")

    prices = ohlc.copy()
    required_price_cols = {"date", "close"}
    if not required_price_cols.issubset(prices.columns):
        raise ValueError("ohlc requires date and close columns")
    for column in ("open", "high", "low"):
        if column not in prices:
            prices[column] = float("nan")
    prices["date"] = prices["date"].map(_parse_date)
    if prices["date"].isna().any():
        raise ValueError("ohlc contains invalid dates")
    prices = prices.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)
    if len(prices) < 3:
        raise ValueError("at least three OHLC sessions are required (previous, signal, target)")

    market_dates = prices["date"].tolist()
    market_index = {d: i for i, d in enumerate(market_dates)}
    price_by_date = prices.set_index("date", drop=False)
    oi_by_date = {d: group.reset_index(drop=True) for d, group in oi.groupby("date")}

    from_date = _parse_date(config.from_date) if config.from_date else None
    to_date = _parse_date(config.to_date) if config.to_date else None
    signal_dates = sorted(d for d in oi_by_date
                          if (from_date is None or d >= from_date)
                          and (to_date is None or d <= to_date))

    rows: list[dict] = []
    skipped: list[dict] = []
    warnings: list[str] = []
    bad_chain_dates: list[str] = []

    for signal_date in signal_dates:
        if signal_date not in market_index:
            skipped.append({"signal_date": signal_date.isoformat(),
                            "reason": "missing_signal_ohlc", "detail": ""})
            continue
        index = market_index[signal_date]
        if index == 0:
            skipped.append({"signal_date": signal_date.isoformat(),
                            "reason": "no_previous_market_session", "detail": ""})
            continue
        if index == len(market_dates) - 1:
            skipped.append({"signal_date": signal_date.isoformat(),
                            "reason": "no_next_market_session", "detail": ""})
            continue

        previous_date = market_dates[index - 1]
        target_date = market_dates[index + 1]
        if previous_date not in oi_by_date:
            skipped.append({"signal_date": signal_date.isoformat(),
                            "reason": "missing_previous_session_oi",
                            "detail": previous_date.isoformat()})
            continue

        today_oi = oi_by_date[signal_date]
        previous_oi = oi_by_date[previous_date]
        missing_today = REQUIRED_PARTICIPANTS - _participants_present(today_oi)
        missing_previous = REQUIRED_PARTICIPANTS - _participants_present(previous_oi)
        if missing_today or missing_previous:
            detail = (f"today={','.join(sorted(missing_today)) or '-'};"
                      f"previous={','.join(sorted(missing_previous)) or '-'}")
            skipped.append({"signal_date": signal_date.isoformat(),
                            "reason": "missing_required_participant", "detail": detail})
            continue

        chain = option_chains.get(signal_date)
        levels: dict = {"levels": [], "max_pain": None, "pcr": None,
                        "pcr_signal": "", "immediate_support": None,
                        "immediate_resistance": None}
        if chain:
            try:
                levels = derive_levels(chain)
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                bad_chain_dates.append(f"{signal_date.isoformat()} ({exc})")
                chain = None

        decoded = decode(today_oi, previous_oi, cash=None,
                         option_levels=levels if chain else None,
                         date_str=signal_date.isoformat())
        # next_day does not consume decoded_history; explicitly passing None keeps
        # the replay independent of later positional-history changes.
        prediction = build_predictions(decoded, levels, decoded_history=None)["next_day"]
        predicted = prediction_class(prediction["direction"])

        signal_bar = price_by_date.loc[signal_date]
        target_bar = price_by_date.loc[target_date]
        signal_close = float(signal_bar["close"])
        target_close = float(target_bar["close"])
        return_pct = (target_close / signal_close - 1.0) * 100.0
        realised = actual_class(return_pct, config.flat_threshold_pct)

        support, support_tested, support_held = _level_observation(
            levels.get("immediate_support"), "support", target_bar,
            config.level_touch_tolerance_pct)
        resistance, resistance_tested, resistance_held = _level_observation(
            levels.get("immediate_resistance"), "resistance", target_bar,
            config.level_touch_tolerance_pct)
        level_tests = sum(value is True for value in (support_tested, resistance_tested))
        level_hits = sum(value is True for value in (support_held, resistance_held))

        target_open = _number(target_bar.get("open"))
        gap_pct = ((target_open / signal_close - 1.0) * 100.0
                   if target_open is not None else None)
        intraday_return = ((target_close / target_open - 1.0) * 100.0
                           if target_open not in (None, 0) else None)

        direction_hit = realised == predicted if predicted in {"UP", "DOWN"} else None
        rows.append({
            "signal_date": signal_date.isoformat(),
            "previous_oi_date": previous_date.isoformat(),
            "target_date": target_date.isoformat(),
            "prediction_raw": prediction["direction"],
            "predicted_class": predicted,
            "actual_class": realised,
            "exact_hit": realised == predicted,
            "direction_hit": direction_hit,
            "bias": decoded.bias,
            "composite": decoded.composite,
            "confidence": decoded.confidence,
            "smart_money_conflict": decoded.smart_money_conflict,
            "signal_close": signal_close,
            "target_open": target_open,
            "target_high": _number(target_bar.get("high")),
            "target_low": _number(target_bar.get("low")),
            "target_close": target_close,
            "gap_pct": round(gap_pct, 6) if gap_pct is not None else None,
            "intraday_return_pct": round(intraday_return, 6) if intraday_return is not None else None,
            "actual_return_pct": round(return_pct, 6),
            "option_chain_available": bool(chain),
            "support_level": support,
            "support_tested": support_tested,
            "support_held": support_held,
            "resistance_level": resistance,
            "resistance_tested": resistance_tested,
            "resistance_held": resistance_held,
            "level_tests": level_tests,
            "level_hits": level_hits,
        })

    if bad_chain_dates:
        warnings.append("Malformed option-chain snapshots ignored: " + ", ".join(bad_chain_dates[:10]))
    if not option_chains:
        warnings.append("No option-chain history supplied; level-reaction metrics are unavailable.")
    if prices[["open", "high", "low"]].isna().any(axis=None):
        warnings.append("Some OHLC rows lack Open/High/Low; affected level and gap observations are unscored.")

    predictions = pd.DataFrame(rows, columns=PREDICTION_COLUMNS)
    skipped_frame = pd.DataFrame(skipped, columns=["signal_date", "reason", "detail"])
    metrics, curve = compute_metrics(predictions, config)
    return BacktestResult(predictions, skipped_frame, curve, metrics, config, warnings)


def _rate(numerator: int, denominator: int) -> Optional[float]:
    return round(numerator / denominator * 100.0, 2) if denominator else None


def _class_metrics(frame: pd.DataFrame, label: str) -> dict:
    predicted = frame["predicted_class"] == label
    actual = frame["actual_class"] == label
    tp = int((predicted & actual).sum())
    fp = int((predicted & ~actual).sum())
    fn = int((~predicted & actual).sum())
    precision = _rate(tp, tp + fp)
    recall = _rate(tp, tp + fn)
    if precision is None or recall is None or precision + recall == 0:
        f1 = None
    else:
        f1 = round(2 * precision * recall / (precision + recall), 2)
    return {
        "support_actual": int(actual.sum()),
        "calls_predicted": int(predicted.sum()),
        "true_positives": tp,
        "precision_pct": precision,
        "recall_pct": recall,
        "f1_pct": f1,
    }


def _confidence_curve(frame: pd.DataFrame) -> pd.DataFrame:
    columns = ["confidence_bin", "min_exclusive", "max_inclusive", "samples",
               "average_confidence", "exact_accuracy_pct", "directional_calls",
               "directional_hit_rate_pct"]
    if frame.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict] = []
    bounds = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100)]
    confidence = pd.to_numeric(frame["confidence"], errors="coerce")
    for lower, upper in bounds:
        mask = ((confidence >= lower) if lower == 0 else (confidence > lower)) & (confidence <= upper)
        bucket = frame[mask]
        if bucket.empty:
            continue
        directional = bucket[bucket["predicted_class"].isin(["UP", "DOWN"])]
        direction_hits = int(directional["direction_hit"].fillna(False).astype(bool).sum())
        rows.append({
            "confidence_bin": f"{lower}{'-' if lower == 0 else '<x<='}{upper}",
            "min_exclusive": lower,
            "max_inclusive": upper,
            "samples": len(bucket),
            "average_confidence": round(float(bucket["confidence"].mean()), 2),
            "exact_accuracy_pct": _rate(int(bucket["exact_hit"].sum()), len(bucket)),
            "directional_calls": len(directional),
            "directional_hit_rate_pct": _rate(direction_hits, len(directional)),
        })
    return pd.DataFrame(rows, columns=columns)


def compute_metrics(predictions: pd.DataFrame,
                    config: Optional[BacktestConfig] = None) -> tuple[dict, pd.DataFrame]:
    """Compute transparent classification and daily-level proxy metrics."""
    config = config or BacktestConfig()
    curve = _confidence_curve(predictions)
    n = len(predictions)
    if not n:
        return ({
            "status": "no_evaluable_signals",
            "signals_evaluated": 0,
            "flat_threshold_pct": config.flat_threshold_pct,
            "level_touch_tolerance_pct": config.level_touch_tolerance_pct,
        }, curve)

    directional = predictions[predictions["predicted_class"].isin(["UP", "DOWN"])]
    direction_hits = int(directional["direction_hit"].fillna(False).astype(bool).sum())
    exact_hits = int(predictions["exact_hit"].astype(bool).sum())

    class_counts = {label: int((predictions["actual_class"] == label).sum()) for label in CLASSES}
    predicted_counts = {label: int((predictions["predicted_class"] == label).sum()) for label in CLASSES}
    confusion = {
        actual: {predicted: int(((predictions["actual_class"] == actual)
                                & (predictions["predicted_class"] == predicted)).sum())
                 for predicted in CLASSES}
        for actual in CLASSES
    }

    level_parts: dict[str, dict] = {}
    total_level_tests = 0
    total_level_hits = 0
    for kind in ("support", "resistance"):
        tested_col, held_col = f"{kind}_tested", f"{kind}_held"
        if tested_col not in predictions:
            tests = hits = 0
        else:
            tests = int((predictions[tested_col] == True).sum())  # noqa: E712
            hits = int(((predictions[tested_col] == True)
                        & (predictions[held_col] == True)).sum())  # noqa: E712
        total_level_tests += tests
        total_level_hits += hits
        level_parts[kind] = {"tests": tests, "holds": hits,
                             "hold_accuracy_pct": _rate(hits, tests)}

    return_by_prediction = {}
    for label in CLASSES:
        values = predictions.loc[predictions["predicted_class"] == label, "actual_return_pct"]
        return_by_prediction[label] = {
            "samples": len(values),
            "mean_next_session_return_pct": (round(float(values.mean()), 4)
                                               if len(values) else None),
            "median_next_session_return_pct": (round(float(values.median()), 4)
                                                 if len(values) else None),
        }

    metrics = {
        "status": "ok",
        "signals_evaluated": n,
        "signal_date_start": str(predictions["signal_date"].min()),
        "signal_date_end": str(predictions["signal_date"].max()),
        "target_definition": "next trading session close / signal-session close - 1",
        "flat_threshold_pct": config.flat_threshold_pct,
        "exact_3_class_hits": exact_hits,
        "exact_3_class_accuracy_pct": _rate(exact_hits, n),
        "directional_calls": len(directional),
        "directional_coverage_pct": _rate(len(directional), n),
        "directional_hits": direction_hits,
        "directional_hit_rate_pct": _rate(direction_hits, len(directional)),
        "actual_class_counts": class_counts,
        "predicted_class_counts": predicted_counts,
        "majority_class_baseline_accuracy_pct": _rate(max(class_counts.values()), n),
        "class_metrics": {label: _class_metrics(predictions, label) for label in CLASSES},
        "confusion_matrix_actual_rows": confusion,
        "level_reaction_daily_proxy": {
            "definition": ("next-session range enters the level tolerance band; "
                           "support succeeds on close >= level and resistance on close <= level"),
            "touch_tolerance_pct": config.level_touch_tolerance_pct,
            "tests": total_level_tests,
            "holds": total_level_hits,
            "hold_accuracy_pct": _rate(total_level_hits, total_level_tests),
            **level_parts,
        },
        "return_by_prediction": return_by_prediction,
        "confidence_curve": curve.to_dict(orient="records"),
    }
    return metrics, curve


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
def _fmt_pct(value) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{float(value):.2f}%"


def render_backtest_markdown(result: BacktestResult) -> str:
    metrics = result.metrics
    cfg = result.config
    lines = [
        f"# {cfg.symbol} FII/DII Decode Backtest",
        "",
        "> Point-in-time replay of the participant-OI decoder. This is classification "
        "evaluation, not a trading-P&L claim and not investment advice.",
        "",
        "## Evaluation contract",
        "",
        "- Signal date **D** uses D participant OI and the exact previous trading session's OI.",
        "- Target is the **next trading session close-to-close return**.",
        f"- Actual FLAT band: **±{cfg.flat_threshold_pct:.3f}%** (inclusive).",
        "- `SIDEWAYS-UP` → UP, `SIDEWAYS-DOWN` → DOWN, `RANGE` → FLAT.",
        "- Historical cash flow is not used; a current API response is never applied to old dates.",
        "",
        "## Summary",
        "",
    ]
    if metrics.get("status") != "ok":
        lines += ["**No evaluable signals. No accuracy number is reported.**", ""]
    else:
        lines += [
            "| Metric | Result |",
            "|---|---:|",
            f"| Evaluable signals | {metrics['signals_evaluated']} |",
            f"| Signal period | {metrics['signal_date_start']} to {metrics['signal_date_end']} |",
            f"| Exact 3-class accuracy | {_fmt_pct(metrics['exact_3_class_accuracy_pct'])} |",
            f"| Directional hit rate | {_fmt_pct(metrics['directional_hit_rate_pct'])} |",
            f"| Directional coverage | {_fmt_pct(metrics['directional_coverage_pct'])} |",
            f"| Majority-class baseline | {_fmt_pct(metrics['majority_class_baseline_accuracy_pct'])} |",
            "",
            "Directional hit rate scores UP/DOWN calls; a directional call followed by a FLAT day is a miss.",
            "",
            "## Per-class precision / recall",
            "",
            "| Class | Actual | Calls | Precision | Recall | F1 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for label in CLASSES:
            item = metrics["class_metrics"][label]
            lines.append(
                f"| {label} | {item['support_actual']} | {item['calls_predicted']} | "
                f"{_fmt_pct(item['precision_pct'])} | {_fmt_pct(item['recall_pct'])} | "
                f"{_fmt_pct(item['f1_pct'])} |")

        lines += [
            "",
            "## Confusion matrix (actual rows)",
            "",
            "| Actual \\ Predicted | UP | FLAT | DOWN |",
            "|---|---:|---:|---:|",
        ]
        matrix = metrics["confusion_matrix_actual_rows"]
        for actual in CLASSES:
            lines.append(f"| {actual} | {matrix[actual]['UP']} | {matrix[actual]['FLAT']} | {matrix[actual]['DOWN']} |")

        lines += ["", "## Confidence vs accuracy", ""]
        if result.confidence_curve.empty:
            lines.append("No confidence buckets available.")
        else:
            lines += [
                "| Confidence bucket | N | Mean confidence | Exact accuracy | Directional hit rate |",
                "|---|---:|---:|---:|---:|",
            ]
            for _, item in result.confidence_curve.iterrows():
                lines.append(
                    f"| {item['confidence_bin']} | {int(item['samples'])} | "
                    f"{_fmt_pct(item['average_confidence'])} | "
                    f"{_fmt_pct(item['exact_accuracy_pct'])} | "
                    f"{_fmt_pct(item['directional_hit_rate_pct'])} |")

        level = metrics["level_reaction_daily_proxy"]
        lines += [
            "",
            "## Institutional-level reaction (daily-bar proxy)",
            "",
            f"Tolerance band: **±{cfg.level_touch_tolerance_pct:.3f}%** around the level.",
            "A support test succeeds when the next daily close is at/above support; a resistance "
            "test succeeds when it closes at/below resistance.",
            "",
            "| Observation | Tests | Holds | Accuracy |",
            "|---|---:|---:|---:|",
            f"| All levels | {level['tests']} | {level['holds']} | {_fmt_pct(level['hold_accuracy_pct'])} |",
            f"| Support | {level['support']['tests']} | {level['support']['holds']} | {_fmt_pct(level['support']['hold_accuracy_pct'])} |",
            f"| Resistance | {level['resistance']['tests']} | {level['resistance']['holds']} | {_fmt_pct(level['resistance']['hold_accuracy_pct'])} |",
            "",
            "> This is not 15-minute reaction accuracy: daily OHLC cannot prove sequence, volume, "
            "liquidity sweeps, or an intraday hold-and-retest.",
            "",
        ]

    lines += [
        "## Data quality",
        "",
        f"- Skipped signal dates: **{len(result.skipped)}**",
        f"- Option-chain snapshots matched to evaluated dates: **{int(result.predictions['option_chain_available'].sum()) if not result.predictions.empty else 0}**",
    ]
    for warning in result.warnings:
        lines.append(f"- Warning: {warning}")
    if not result.skipped.empty:
        counts = result.skipped["reason"].value_counts()
        for reason, count in counts.items():
            lines.append(f"- `{reason}`: {count}")

    lines += [
        "",
        "## Limitations",
        "",
        "- Accuracy is sensitive to the declared FLAT threshold; compare thresholds before drawing conclusions.",
        "- Decoder confidence is a heuristic score, not a calibrated probability; the buckets test whether it is empirically monotonic.",
        "- The report does not include transaction costs, slippage, tradable entry timing, or position sizing.",
        "- Option-chain level metrics require genuine end-of-day snapshots from each signal date; a current snapshot must not be copied backward.",
        "- Expiry-regime, volatility-regime, and sample-size breakdowns become meaningful only with enough real history.",
        "",
    ]
    return "\n".join(lines)


def write_backtest_outputs(result: BacktestResult, output_dir: str | Path) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths = {
        "predictions": output / "predictions.csv",
        "skipped": output / "skipped.csv",
        "confidence_curve": output / "confidence_curve.csv",
        "metrics": output / "metrics.json",
        "report": output / "report.md",
    }
    result.predictions.to_csv(paths["predictions"], index=False, na_rep="")
    result.skipped.to_csv(paths["skipped"], index=False, na_rep="")
    result.confidence_curve.to_csv(paths["confidence_curve"], index=False, na_rep="")
    payload = {
        "config": asdict(result.config),
        "metrics": result.metrics,
        "warnings": result.warnings,
        "skipped_count": len(result.skipped),
    }
    paths["metrics"].write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    paths["report"].write_text(render_backtest_markdown(result), encoding="utf-8")
    return paths
