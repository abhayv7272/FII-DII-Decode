"""Validated daily data collectors with explicit source provenance.

Primary data comes from NSE. Date-exact fallbacks are used only after validation:

* participant OI: NSE archive -> public GitHub NSE mirror -> corroborated public EOD tables;
* FII/DII cash: NSE API -> MrChartist's GitHub-persisted NSE snapshot;
* option chain: NSE API -> MarketNetra's server-rendered EOD chain;
* index OHLC: NSE all-indices API -> Yahoo Finance daily chart.

Fallback data is never silently relabelled as NSE-direct. Callers can pass a
``metadata`` dictionary which is populated with source, URL, as-of date and any
warning. Every fallback must match the requested date and pass structural
validation; stale or partial payloads are rejected.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import math
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from .context import payload_sha256
from .nse import ARCHIVES, BASE, DEFAULT_HEADERS, NseClient

log = logging.getLogger(__name__)

LEGACY_ARCHIVES = "https://archives.nseindia.com"
GROWW_MIRROR_REPO = "sahilempire/groww-market-data"
MRCHARTIST_REPO = "MrChartist/fii-dii-data"
STOCKLYZER_PARTICIPANT_URL = "https://www.stocklyzer.com/participant-wise"
NIFTYTRADER_PARTICIPANT_URL = "https://www.niftytrader.in/participant-wise-oi"
MARKETNETRA_OPTION_URL = "https://marketnetra.in/indices/{symbol}/option-chain"

PARTICIPANTS = ("Client", "DII", "FII", "Pro")
POSITION_COLUMNS = (
    "Future Index Long",
    "Future Index Short",
    "Future Stock Long",
    "Future Stock Short",
    "Option Index Call Long",
    "Option Index Put Long",
    "Option Index Call Short",
    "Option Index Put Short",
    "Option Stock Call Long",
    "Option Stock Put Long",
    "Option Stock Call Short",
    "Option Stock Put Short",
    "Total Long Contracts",
    "Total Short Contracts",
)
BALANCE_PAIRS = (
    ("Future Index Long", "Future Index Short"),
    ("Future Stock Long", "Future Stock Short"),
    ("Option Index Call Long", "Option Index Call Short"),
    ("Option Index Put Long", "Option Index Put Short"),
    ("Option Stock Call Long", "Option Stock Call Short"),
    ("Option Stock Put Long", "Option Stock Put Short"),
)
LONG_COLUMNS = tuple(pair[0] for pair in BALANCE_PAIRS)
SHORT_COLUMNS = tuple(pair[1] for pair in BALANCE_PAIRS)


def _set_metadata(
    metadata: dict | None,
    *,
    source: str,
    url: str,
    as_of: date | str | None,
    fallback: bool,
    warning: str = "",
) -> None:
    if metadata is None:
        return
    metadata.clear()
    metadata.update(
        {
            "status": "available",
            "source": source,
            "url": url,
            "as_of": as_of.isoformat() if isinstance(as_of, date) else as_of,
            "fallback": fallback,
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        }
    )
    if warning:
        metadata["warning"] = warning


def _mark_unavailable(metadata: dict | None, warning: str) -> None:
    if metadata is None:
        return
    metadata.clear()
    metadata.update(
        {
            "status": "unavailable",
            "source": None,
            "url": None,
            "as_of": None,
            "fallback": False,
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
            "warning": warning,
        }
    )


def _parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date_parser.parse(str(value), dayfirst=True, fuzzy=True).date()
    except (TypeError, ValueError, OverflowError):
        return None


def _verified_get(url: str, **kwargs) -> requests.Response:
    """Verify with certifi first, then the OS trust store when it adds a proxy CA."""
    try:
        return requests.get(url, **kwargs)
    except requests.exceptions.SSLError as exc:
        system_bundle = "/etc/ssl/certs/ca-certificates.crt"
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc) or not os.path.exists(system_bundle):
            raise
        # This is still certificate verification; it never falls back to verify=False.
        return requests.get(url, verify=system_bundle, **kwargs)


def _third_party_get(url: str, *, as_json: bool = False, timeout: int = 25):
    """Small retrying client for non-NSE public fallbacks."""
    headers = {
        "User-Agent": DEFAULT_HEADERS["User-Agent"],
        "Accept": "application/json,text/html,text/plain,*/*",
        "Accept-Language": DEFAULT_HEADERS["Accept-Language"],
        "Accept-Encoding": "gzip, deflate",
    }
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = _verified_get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.json() if as_json else response.text
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(attempt)
    raise RuntimeError(f"fallback fetch failed for {url}: {last_error}")


def _github_content(repo: str, path: str) -> tuple[str, str]:
    api_url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "FII-DII-Decode",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = _verified_get(api_url, headers=headers, timeout=25)
    response.raise_for_status()
    payload = response.json()
    if payload.get("encoding") != "base64" or not payload.get("content"):
        raise RuntimeError(f"GitHub content response was not base64 for {path}")
    text = base64.b64decode(payload["content"]).decode("utf-8-sig")
    return text, payload.get("html_url") or api_url


# ---------------------------------------------------------------------------
# Participant-wise Open Interest (the core dataset)
# ---------------------------------------------------------------------------
def _fao_participant_oi_urls(d: date) -> list[tuple[str, str]]:
    filename = f"fao_participant_oi_{d:%d%m%Y}"
    return [
        ("NSE archive _b", f"{ARCHIVES}/content/nsccl/{filename}_b.csv"),
        ("NSE archive", f"{ARCHIVES}/content/nsccl/{filename}.csv"),
        ("NSE legacy archive _b", f"{LEGACY_ARCHIVES}/content/nsccl/{filename}_b.csv"),
        ("NSE legacy archive", f"{LEGACY_ARCHIVES}/content/nsccl/{filename}.csv"),
    ]


def _fao_participant_vol_urls(d: date) -> list[tuple[str, str]]:
    filename = f"fao_participant_vol_{d:%d%m%Y}"
    return [
        ("NSE archive _b", f"{ARCHIVES}/content/nsccl/{filename}_b.csv"),
        ("NSE archive", f"{ARCHIVES}/content/nsccl/{filename}.csv"),
        ("NSE legacy archive _b", f"{LEGACY_ARCHIVES}/content/nsccl/{filename}_b.csv"),
        ("NSE legacy archive", f"{LEGACY_ARCHIVES}/content/nsccl/{filename}.csv"),
    ]


def _parse_participant_csv(text: str) -> pd.DataFrame:
    """Parse NSE participant CSVs despite title rows and trailing empty columns."""
    lines = text.splitlines()
    header_idx = 0
    for index, line in enumerate(lines):
        low = line.lower()
        if "client type" in low or "future index long" in low:
            header_idx = index
            break
    frame = pd.read_csv(io.StringIO("\n".join(lines[header_idx:])))
    frame.columns = [column.strip() for column in frame.columns]
    frame = frame.loc[:, ~frame.columns.str.match(r"^Unnamed:")]
    normalised = {
        column.lower().replace(" ", "").replace("_", ""): column
        for column in frame.columns
    }
    if "clienttype" in normalised:
        frame = frame.rename(columns={normalised["clienttype"]: "ClientType"})
    if "date" in normalised and normalised["date"] != "date":
        frame = frame.rename(columns={normalised["date"]: "date"})
    if "ClientType" in frame.columns:
        frame["ClientType"] = frame["ClientType"].astype(str).str.strip()
        allowed = {"CLIENT", "DII", "FII", "PRO", "TOTAL"}
        frame = frame[frame["ClientType"].str.upper().isin(allowed)]
    for column in frame.columns:
        if column not in ("ClientType", "date"):
            frame[column] = pd.to_numeric(
                frame[column].astype(str).str.replace(",", "", regex=False),
                errors="coerce",
            )
    return frame.reset_index(drop=True)


def validate_participant_oi(frame: pd.DataFrame | None) -> tuple[bool, str]:
    """Reject partial, non-numeric or internally unbalanced participant matrices."""
    if frame is None or frame.empty:
        return False, "empty participant-OI frame"
    if "ClientType" not in frame:
        return False, "missing ClientType column"
    missing_columns = [column for column in POSITION_COLUMNS if column not in frame]
    if missing_columns:
        return False, f"missing columns: {', '.join(missing_columns)}"
    labels = {str(value).strip().upper() for value in frame["ClientType"]}
    missing_participants = [name for name in PARTICIPANTS if name.upper() not in labels]
    if missing_participants:
        return False, f"missing participants: {', '.join(missing_participants)}"

    participant_rows = frame[
        frame["ClientType"]
        .astype(str)
        .str.upper()
        .isin({name.upper() for name in PARTICIPANTS})
    ].copy()
    counts = participant_rows["ClientType"].astype(str).str.upper().value_counts()
    if any(counts.get(name.upper(), 0) != 1 for name in PARTICIPANTS):
        return False, "participant matrix has duplicate participant rows"
    numeric = participant_rows[list(POSITION_COLUMNS)].apply(
        pd.to_numeric, errors="coerce"
    )
    if numeric.isna().any().any():
        return False, "participant matrix contains non-numeric values"
    if (numeric < 0).any().any():
        return False, "participant matrix contains negative open interest"

    computed_long = numeric[list(LONG_COLUMNS)].sum(axis=1)
    computed_short = numeric[list(SHORT_COLUMNS)].sum(axis=1)
    if not (computed_long - numeric["Total Long Contracts"]).abs().le(1).all():
        return False, "participant Total Long Contracts does not equal its components"
    if not (computed_short - numeric["Total Short Contracts"]).abs().le(1).all():
        return False, "participant Total Short Contracts does not equal its components"

    for long_column, short_column in BALANCE_PAIRS:
        long_total = float(numeric[long_column].sum())
        short_total = float(numeric[short_column].sum())
        tolerance = max(1.0, 0.0001 * max(long_total, short_total, 1.0))
        if abs(long_total - short_total) > tolerance:
            return False, (
                f"unbalanced {long_column}/{short_column}: "
                f"{long_total:g} vs {short_total:g}"
            )

    total_rows = frame[frame["ClientType"].astype(str).str.upper() == "TOTAL"]
    if not total_rows.empty:
        if len(total_rows) != 1:
            return False, "participant matrix has duplicate TOTAL rows"
        reported = total_rows.iloc[0]
        for column in POSITION_COLUMNS:
            try:
                reported_value = float(reported[column])
            except (TypeError, ValueError):
                return False, f"TOTAL row has invalid {column}"
            expected_value = float(numeric[column].sum())
            if abs(reported_value - expected_value) > 1:
                return False, f"TOTAL row does not equal participant sum for {column}"
    return True, "ok"


def _with_total_row(frame: pd.DataFrame) -> pd.DataFrame:
    participant_rows = frame[
        frame["ClientType"]
        .astype(str)
        .str.upper()
        .isin({name.upper() for name in PARTICIPANTS})
    ].copy()
    totals = {
        column: float(participant_rows[column].sum()) for column in POSITION_COLUMNS
    }
    totals["ClientType"] = "TOTAL"
    return pd.concat([participant_rows, pd.DataFrame([totals])], ignore_index=True)


def _fetch_participant_github_mirror(d: date) -> tuple[pd.DataFrame, str]:
    path = f"nse_archives/participant_oi/fao_participant_oi_{d:%Y%m%d}.csv"
    text, url = _github_content(GROWW_MIRROR_REPO, path)
    frame = _parse_participant_csv(text)
    valid, reason = validate_participant_oi(frame)
    if not valid:
        raise RuntimeError(f"GitHub participant mirror failed validation: {reason}")
    frame["date"] = d.isoformat()
    return frame, url


def fetch_participant_oi(
    client: NseClient,
    d: date,
    metadata: dict | None = None,
) -> pd.DataFrame | None:
    """Fetch a date-exact complete participant-OI matrix.

    NSE's normal and ``_b`` filenames plus the legacy archive host are attempted
    first. The public Groww market-data repository is a date-exact archival
    fallback; a missing requested date is never replaced with its latest file.
    """
    errors: list[str] = []
    for source, url in _fao_participant_oi_urls(d):
        try:
            text = client.get_text(
                url,
                referer=BASE + "/all-reports-derivatives",
                prime_required=False,
            )
            if "<html" in text.lower():
                raise RuntimeError("HTML returned instead of CSV")
            frame = _parse_participant_csv(text)
            valid, reason = validate_participant_oi(frame)
            if not valid:
                raise RuntimeError(reason)
            frame["date"] = d.isoformat()
            _set_metadata(metadata, source=source, url=url, as_of=d, fallback=False)
            return frame
        except (RuntimeError, KeyError, ValueError, pd.errors.ParserError) as exc:
            errors.append(f"{source}: {exc}")

    try:
        frame, url = _fetch_participant_github_mirror(d)
        _set_metadata(
            metadata,
            source="Groww market-data GitHub mirror",
            url=url,
            as_of=d,
            fallback=True,
            warning="Date-exact mirror of NSE participant OI; NSE direct fetch failed.",
        )
        return frame
    except (RuntimeError, requests.RequestException, KeyError, ValueError) as exc:
        errors.append(f"GitHub mirror: {exc}")

    warning = f"participant OI unavailable for {d}: {'; '.join(errors[-3:])}"
    log.warning(warning)
    _mark_unavailable(metadata, warning)
    return None


def _cell_value_change(text: str) -> tuple[float, float]:
    numbers = re.findall(r"[+-]?\s*\d[\d,]*", text.replace("−", "-"))
    if len(numbers) < 2:
        raise ValueError(
            f"participant cell has no separately displayed daily change: {text!r}"
        )

    def number(token: str) -> float:
        return float(token.replace(" ", "").replace(",", ""))

    return number(numbers[0]), number(numbers[1])


def _stocklyzer_table(table, segment: str) -> tuple[list[dict], list[dict]]:
    if segment == "index":
        mapping = (
            "Future Index Long",
            "Future Index Short",
            "Option Index Call Long",
            "Option Index Call Short",
            "Option Index Put Long",
            "Option Index Put Short",
        )
    else:
        mapping = (
            "Future Stock Long",
            "Future Stock Short",
            "Option Stock Call Long",
            "Option Stock Call Short",
            "Option Stock Put Long",
            "Option Stock Put Short",
        )
    current_rows: list[dict] = []
    change_rows: list[dict] = []
    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) < 7:
            continue
        label = cells[0].get_text(" ", strip=True).upper()
        participant = next(
            (name for name in PARTICIPANTS if name.upper() == label), None
        )
        if participant is None:
            continue
        current = {"ClientType": participant}
        changes = {"ClientType": participant}
        for column, cell in zip(mapping, cells[1:7], strict=True):
            value, change = _cell_value_change(cell.get_text(" ", strip=True))
            current[column] = value
            changes[column] = change
        current_rows.append(current)
        change_rows.append(changes)
    return current_rows, change_rows


def fetch_participant_oi_stocklyzer(
    expected_on_or_before: date,
    metadata: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, date] | None:
    """Fetch latest full matrix and derive the prior matrix from reported deltas.

    This third-party fallback is accepted only when it is no more than five
    calendar days old, contains every participant/instrument, and balances long
    versus short for every segment. The previous matrix is reconstructed as
    ``current - displayed daily change``; it is used only as the immediately
    preceding session input and is not assigned a guessed holiday-sensitive date.
    """
    try:
        html = _third_party_get(STOCKLYZER_PARTICIPANT_URL)
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        match = re.search(r"As\s+on\s+(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
        if not match:
            raise RuntimeError("Stocklyzer as-of date not found")
        as_of = date.fromisoformat(match.group(1))
        age = (expected_on_or_before - as_of).days
        if age < 0 or age > 5:
            raise RuntimeError(
                f"Stocklyzer date {as_of} is not a fresh session for {expected_on_or_before}"
            )

        matching_tables = []
        for table in soup.find_all("table"):
            headers = " ".join(
                cell.get_text(" ", strip=True) for cell in table.find_all("th")
            ).lower()
            if "future long" in headers and "put short" in headers:
                matching_tables.append(table)
        if len(matching_tables) < 2:
            raise RuntimeError("Stocklyzer index/stock participant tables not found")

        index_current, index_changes = _stocklyzer_table(matching_tables[0], "index")
        stock_current, stock_changes = _stocklyzer_table(matching_tables[1], "stock")
        current_by_name = {row["ClientType"]: row for row in index_current}
        changes_by_name = {row["ClientType"]: row for row in index_changes}
        for row in stock_current:
            current_by_name.setdefault(row["ClientType"], {}).update(row)
        for row in stock_changes:
            changes_by_name.setdefault(row["ClientType"], {}).update(row)

        current_rows = []
        previous_rows = []
        for participant in PARTICIPANTS:
            current = current_by_name.get(participant, {})
            changes = changes_by_name.get(participant, {})
            if any(column not in current for column in POSITION_COLUMNS[:-2]):
                raise RuntimeError(f"Stocklyzer is incomplete for {participant}")
            current["Total Long Contracts"] = sum(
                current[column] for column in LONG_COLUMNS
            )
            current["Total Short Contracts"] = sum(
                current[column] for column in SHORT_COLUMNS
            )
            previous = {"ClientType": participant}
            for column in POSITION_COLUMNS:
                if column.startswith("Total "):
                    continue
                previous[column] = current[column] - changes.get(column, 0.0)
            previous["Total Long Contracts"] = sum(
                previous[column] for column in LONG_COLUMNS
            )
            previous["Total Short Contracts"] = sum(
                previous[column] for column in SHORT_COLUMNS
            )
            current_rows.append(current)
            previous_rows.append(previous)

        current_frame = _with_total_row(pd.DataFrame(current_rows))
        previous_frame = _with_total_row(pd.DataFrame(previous_rows))
        for frame, name in ((current_frame, "current"), (previous_frame, "previous")):
            valid, reason = validate_participant_oi(frame)
            if not valid:
                raise RuntimeError(
                    f"Stocklyzer {name} matrix failed validation: {reason}"
                )
        current_frame["date"] = as_of.isoformat()

        _set_metadata(
            metadata,
            source="Stocklyzer EOD participant table",
            url=STOCKLYZER_PARTICIPANT_URL,
            as_of=as_of,
            fallback=True,
            warning=(
                "Third-party rendering of NSE data; matrix passed completeness and "
                "long/short balance checks. Previous session derived from displayed deltas."
            ),
        )
        return current_frame, previous_frame, as_of
    except (RuntimeError, ValueError, KeyError, requests.RequestException) as exc:
        warning = f"Stocklyzer participant fallback rejected: {exc}"
        log.warning(warning)
        _mark_unavailable(metadata, warning)
        return None


def fetch_participant_oi_niftytrader(
    expected_on_or_before: date,
    metadata: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, date] | None:
    """Parse NiftyTrader's row-oriented complete participant matrix and deltas."""
    try:
        html = _third_party_get(NIFTYTRADER_PARTICIPANT_URL)
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        match = re.search(
            r"positioned\s+how\s+on\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
            text,
            re.IGNORECASE,
        )
        as_of = _parse_date(match.group(1)) if match else None
        if as_of is None:
            raise RuntimeError("NiftyTrader as-of date not found")
        age = (expected_on_or_before - as_of).days
        if age < 0 or age > 5:
            raise RuntimeError(
                f"NiftyTrader date {as_of} is not a fresh session for "
                f"{expected_on_or_before}"
            )

        matrix_table = next(
            (
                table
                for table in soup.find_all("table")
                if "Future Index Long" in table.get_text(" ", strip=True)
                and "Total Long Contracts" in table.get_text(" ", strip=True)
            ),
            None,
        )
        if matrix_table is None:
            raise RuntimeError("NiftyTrader participant matrix table not found")

        current_by_name = {name: {"ClientType": name} for name in PARTICIPANTS}
        changes_by_name = {name: {"ClientType": name} for name in PARTICIPANTS}
        wanted = {column.upper(): column for column in POSITION_COLUMNS}
        for row in matrix_table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) < 9:
                continue
            label = cells[0].get_text(" ", strip=True).upper()
            column = wanted.get(label)
            if column is None:
                continue
            for participant, value_index in zip(
                PARTICIPANTS, (1, 3, 5, 7), strict=True
            ):
                current_by_name[participant][column] = _magnitude(
                    cells[value_index].get_text(" ", strip=True)
                )
                changes_by_name[participant][column] = _magnitude(
                    cells[value_index + 1].get_text(" ", strip=True)
                )

        current_rows = []
        previous_rows = []
        for participant in PARTICIPANTS:
            current = current_by_name[participant]
            changes = changes_by_name[participant]
            if any(column not in current for column in POSITION_COLUMNS):
                raise RuntimeError(f"NiftyTrader is incomplete for {participant}")
            previous = {"ClientType": participant}
            for column in POSITION_COLUMNS:
                previous[column] = current[column] - changes.get(column, 0.0)
            current_rows.append(current)
            previous_rows.append(previous)

        current_frame = _with_total_row(pd.DataFrame(current_rows))
        previous_frame = _with_total_row(pd.DataFrame(previous_rows))
        for frame, name in ((current_frame, "current"), (previous_frame, "previous")):
            valid, reason = validate_participant_oi(frame)
            if not valid:
                raise RuntimeError(
                    f"NiftyTrader {name} matrix failed validation: {reason}"
                )
        current_frame["date"] = as_of.isoformat()
        _set_metadata(
            metadata,
            source="NiftyTrader EOD participant table",
            url=NIFTYTRADER_PARTICIPANT_URL,
            as_of=as_of,
            fallback=True,
            warning=(
                "Third-party rendering of NSE data; matrix passed completeness and "
                "long/short balance checks. Previous session derived from displayed deltas."
            ),
        )
        return current_frame, previous_frame, as_of
    except (RuntimeError, ValueError, KeyError, requests.RequestException) as exc:
        warning = f"NiftyTrader participant fallback rejected: {exc}"
        log.warning(warning)
        _mark_unavailable(metadata, warning)
        return None


def _participant_sources_match(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    try:
        left_values = left[left["ClientType"].isin(PARTICIPANTS)].set_index(
            "ClientType"
        )
        right_values = right[right["ClientType"].isin(PARTICIPANTS)].set_index(
            "ClientType"
        )
        return bool(
            (
                left_values.loc[list(PARTICIPANTS), list(POSITION_COLUMNS)]
                - right_values.loc[list(PARTICIPANTS), list(POSITION_COLUMNS)]
            )
            .abs()
            .le(1)
            .all()
            .all()
        )
    except (KeyError, TypeError, ValueError):
        return False


def fetch_participant_oi_rendered(
    expected_on_or_before: date,
    metadata: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, date] | None:
    """Use two independent public renderings when possible; reject disagreement."""
    stock_metadata: dict = {}
    nifty_metadata: dict = {}
    stock = fetch_participant_oi_stocklyzer(expected_on_or_before, stock_metadata)
    nifty = fetch_participant_oi_niftytrader(expected_on_or_before, nifty_metadata)
    if stock is not None and nifty is not None:
        if (
            stock[2] != nifty[2]
            or not _participant_sources_match(stock[0], nifty[0])
            or not _participant_sources_match(stock[1], nifty[1])
        ):
            warning = (
                "Stocklyzer and NiftyTrader participant matrices disagree; both "
                "third-party renderings were rejected."
            )
            log.warning(warning)
            _mark_unavailable(metadata, warning)
            return None
        _set_metadata(
            metadata,
            source="Stocklyzer + NiftyTrader corroborated participant tables",
            url=f"{STOCKLYZER_PARTICIPANT_URL}; {NIFTYTRADER_PARTICIPANT_URL}",
            as_of=stock[2],
            fallback=True,
            warning=(
                "Two independent public renderings agree and passed completeness and "
                "balance checks. Previous session derived from displayed daily changes."
            ),
        )
        return stock

    result, selected, other = (
        (stock, stock_metadata, nifty_metadata)
        if stock is not None
        else (nifty, nifty_metadata, stock_metadata)
    )
    if result is None:
        warning = "; ".join(
            item.get("warning", "participant rendering unavailable")
            for item in (stock_metadata, nifty_metadata)
        )
        _mark_unavailable(metadata, warning)
        return None
    _set_metadata(
        metadata,
        source=selected.get("source", "single participant rendering"),
        url=selected.get("url", ""),
        as_of=result[2],
        fallback=True,
        warning=(
            f"{selected.get('warning', '')} Independent corroborator unavailable: "
            f"{other.get('warning', 'unknown error')}"
        ).strip(),
    )
    return result


def fetch_participant_vol(
    client: NseClient,
    d: date,
    metadata: dict | None = None,
) -> pd.DataFrame | None:
    errors = []
    for source, url in _fao_participant_vol_urls(d):
        try:
            text = client.get_text(
                url,
                referer=BASE + "/all-reports-derivatives",
                prime_required=False,
            )
            if "<html" in text.lower():
                raise RuntimeError("HTML returned instead of CSV")
            frame = _parse_participant_csv(text)
            valid, reason = validate_participant_oi(frame)
            if not valid:
                raise RuntimeError(f"participant volume failed validation: {reason}")
            frame["date"] = d.isoformat()
            _set_metadata(
                metadata, source=source, url=url, as_of=d, fallback=False
            )
            return frame
        except (RuntimeError, ValueError, pd.errors.ParserError) as exc:
            errors.append(f"{source}: {exc}")
    warning = f"participant volume unavailable for {d}: {'; '.join(errors[-3:])}"
    log.warning(warning)
    _mark_unavailable(metadata, warning)
    return None


# ---------------------------------------------------------------------------
# FII / DII cash market provisional figures
# ---------------------------------------------------------------------------
def _cash_date(rows: Any) -> date | None:
    if not isinstance(rows, list):
        return None
    parsed = {
        parsed_date
        for row in rows
        if isinstance(row, dict)
        for parsed_date in [_parse_date(row.get("date"))]
        if parsed_date is not None
    }
    return next(iter(parsed)) if len(parsed) == 1 else None


def _valid_cash_rows(rows: Any, expected_date: date | None) -> tuple[bool, str]:
    if not isinstance(rows, list) or not rows:
        return False, "cash payload is not a non-empty list"
    categories = " ".join(str(row.get("category", "")).upper() for row in rows)
    if "FII" not in categories and "FPI" not in categories:
        return False, "cash payload has no FII/FPI row"
    if "DII" not in categories:
        return False, "cash payload has no DII row"
    for row in rows:
        for field in ("buyValue", "sellValue", "netValue"):
            try:
                value = float(str(row.get(field, "")).replace(",", ""))
            except (TypeError, ValueError):
                return False, f"cash payload contains invalid {field}"
            if not math.isfinite(value):
                return False, f"cash payload contains non-finite {field}"
    payload_date = _cash_date(rows)
    if expected_date and payload_date != expected_date:
        return False, f"cash payload date {payload_date} != requested {expected_date}"
    return True, "ok"


def _fetch_cash_mrchartist(expected_date: date) -> tuple[list[dict], str]:
    text, url = _github_content(MRCHARTIST_REPO, "data/latest.json")
    payload = json.loads(text)
    payload_date = _parse_date(payload.get("date"))
    if payload_date != expected_date:
        raise RuntimeError(
            f"MrChartist cash date {payload_date} != requested {expected_date}"
        )
    rows = [
        {
            "category": "FII/FPI *",
            "date": payload["date"],
            "buyValue": payload["fii_buy"],
            "sellValue": payload["fii_sell"],
            "netValue": payload["fii_net"],
        },
        {
            "category": "DII **",
            "date": payload["date"],
            "buyValue": payload["dii_buy"],
            "sellValue": payload["dii_sell"],
            "netValue": payload["dii_net"],
        },
    ]
    valid, reason = _valid_cash_rows(rows, expected_date)
    if not valid:
        raise RuntimeError(reason)
    return rows, url


def fetch_fii_dii_cash(
    client: NseClient,
    expected_date: date | None = None,
    metadata: dict | None = None,
) -> list[dict] | None:
    """Fetch date-checked FII/DII cash provisional values."""
    url = BASE + "/api/fiidiiTradeReact"
    errors = []
    try:
        rows = client.get_json(
            url, referer=BASE + "/reports-indices-historical-index-data"
        )
        valid, reason = _valid_cash_rows(rows, expected_date)
        if not valid:
            raise RuntimeError(reason)
        _set_metadata(
            metadata,
            source="NSE FII/DII API",
            url=url,
            as_of=_cash_date(rows) or expected_date,
            fallback=False,
        )
        return rows
    except RuntimeError as exc:
        errors.append(f"NSE: {exc}")

    if expected_date is not None:
        try:
            rows, fallback_url = _fetch_cash_mrchartist(expected_date)
            _set_metadata(
                metadata,
                source="MrChartist GitHub NSE cash snapshot",
                url=fallback_url,
                as_of=expected_date,
                fallback=True,
                warning="Third-party persisted NSE cash snapshot; NSE API failed.",
            )
            return rows
        except (RuntimeError, requests.RequestException, KeyError, ValueError) as exc:
            errors.append(f"MrChartist: {exc}")

    warning = f"FII/DII cash fetch failed: {'; '.join(errors)}"
    log.warning(warning)
    _mark_unavailable(metadata, warning)
    return None


def cash_rows_to_frame(rows: list[dict], source: str = "") -> pd.DataFrame:
    output = []
    for row in rows or []:
        row_date = _parse_date(row.get("date"))
        if row_date is None:
            raise ValueError("cash row has no parseable date")
        output.append(
            {
                "date": row_date.isoformat(),
                "category": row.get("category", ""),
                "buy_value": pd.to_numeric(
                    str(row.get("buyValue", "")).replace(",", ""), errors="coerce"
                ),
                "sell_value": pd.to_numeric(
                    str(row.get("sellValue", "")).replace(",", ""), errors="coerce"
                ),
                "net_value": pd.to_numeric(
                    str(row.get("netValue", "")).replace(",", ""), errors="coerce"
                ),
                "source": source,
            }
        )
    return pd.DataFrame(output)


# ---------------------------------------------------------------------------
# Option chain
# ---------------------------------------------------------------------------
def validate_option_chain(
    raw: Any, expected_date: date | None = None
) -> tuple[bool, str]:
    if not isinstance(raw, dict) or not isinstance(raw.get("records"), dict):
        return False, "option chain has no records object"
    records = raw["records"]
    data = records.get("data")
    expiries = records.get("expiryDates")
    try:
        spot = float(records.get("underlyingValue"))
    except (TypeError, ValueError):
        return False, "option chain has invalid spot"
    if spot <= 0 or not isinstance(data, list) or len(data) < 10:
        return False, "option chain lacks spot or sufficient strikes"
    if not isinstance(expiries, list) or not expiries:
        return False, "option chain has no expiry dates"
    strikes = []
    call_oi = put_oi = 0.0
    for row in data:
        try:
            strikes.append(float(row["strikePrice"]))
            call_oi += float((row.get("CE") or {}).get("openInterest", 0) or 0)
            put_oi += float((row.get("PE") or {}).get("openInterest", 0) or 0)
        except (TypeError, ValueError, KeyError):
            return False, "option chain contains malformed strike rows"
    if not (min(strikes) < spot < max(strikes)) or call_oi <= 0 or put_oi <= 0:
        return False, "option chain does not bracket spot or has empty OI side"
    timestamp_date = _parse_date(records.get("timestamp"))
    if expected_date and timestamp_date != expected_date:
        return False, (
            f"option-chain date {timestamp_date} != requested {expected_date}"
        )
    return True, "ok"


def _magnitude(value: str) -> float:
    text = value.replace("₹", "").replace(",", "").strip().upper()
    if not text or text in {"—", "-", "N/A"}:
        return 0.0
    match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*(CR|L|K)?", text)
    if not match:
        return 0.0
    number = float(match.group(1))
    multiplier = {"CR": 10_000_000, "L": 100_000, "K": 1_000}.get(match.group(2), 1)
    return number * multiplier


def _fetch_marketnetra_option_chain(
    symbol: str,
    expected_date: date,
) -> tuple[dict, str]:
    normalised = symbol.upper().replace(" ", "")
    slugs = {"NIFTY": "nifty", "NIFTY50": "nifty", "BANKNIFTY": "banknifty"}
    slug = slugs.get(normalised)
    if not slug:
        raise RuntimeError(f"MarketNetra fallback does not support {symbol}")
    url = MARKETNETRA_OPTION_URL.format(symbol=slug)
    html = _third_party_get(url)
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    updated_match = re.search(
        r"Updated\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4})", text, re.IGNORECASE
    )
    as_of = _parse_date(updated_match.group(1)) if updated_match else None
    if as_of != expected_date:
        raise RuntimeError(f"MarketNetra chain date {as_of} != {expected_date}")
    spot_match = re.search(r"₹\s*([\d,]+(?:\.\d+)?)", text)
    if not spot_match:
        raise RuntimeError("MarketNetra spot not found")
    spot = float(spot_match.group(1).replace(",", ""))

    expiry_values = re.findall(r"20\d{2}-\d{2}-\d{2}", text)
    if not expiry_values:
        raise RuntimeError("MarketNetra expiry not found")
    expiry_date = date.fromisoformat(expiry_values[0])
    expiry_label = expiry_date.strftime("%d-%b-%Y")

    option_table = None
    header_names: list[str] = []
    for table in soup.find_all("table"):
        headers = [
            cell.get_text(" ", strip=True).upper() for cell in table.find_all("th")
        ]
        if "CE OI" in headers and "PE OI" in headers and "STRIKE" in headers:
            option_table = table
            header_names = headers
            break
    if option_table is None:
        raise RuntimeError("MarketNetra option table not found")
    indexes = {name: header_names.index(name) for name in set(header_names)}
    change_indexes = [index for index, name in enumerate(header_names) if name == "CHG"]
    volume_indexes = [index for index, name in enumerate(header_names) if name == "VOL"]
    iv_indexes = [index for index, name in enumerate(header_names) if name == "IV"]
    ltp_indexes = [index for index, name in enumerate(header_names) if name == "LTP"]
    records = []
    for row in option_table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < len(header_names):
            continue
        values = [cell.get_text(" ", strip=True) for cell in cells]
        strike = _magnitude(values[indexes["STRIKE"]])
        if strike <= 0:
            continue
        call_oi = _magnitude(values[indexes["CE OI"]])
        put_oi = _magnitude(values[indexes["PE OI"]])
        record: dict[str, Any] = {
            "strikePrice": strike,
            "expiryDate": expiry_label,
        }
        record["CE"] = {
            "openInterest": call_oi,
            "changeinOpenInterest": _magnitude(values[change_indexes[0]])
            if change_indexes
            else 0.0,
            "totalTradedVolume": _magnitude(values[volume_indexes[0]])
            if volume_indexes
            else 0.0,
            "impliedVolatility": _magnitude(values[iv_indexes[0]])
            if iv_indexes
            else 0.0,
            "lastPrice": _magnitude(values[ltp_indexes[0]]) if ltp_indexes else 0.0,
        }
        # Duplicate generic metrics need positional lookup from the right-hand side.
        record["PE"] = {
            "openInterest": put_oi,
            "changeinOpenInterest": _magnitude(values[change_indexes[-1]])
            if change_indexes
            else 0.0,
            "totalTradedVolume": _magnitude(values[volume_indexes[-1]])
            if volume_indexes
            else 0.0,
            "impliedVolatility": _magnitude(values[iv_indexes[-1]])
            if iv_indexes
            else 0.0,
            "lastPrice": _magnitude(values[ltp_indexes[-1]]) if ltp_indexes else 0.0,
        }
        records.append(record)

    payload = {
        "records": {
            "timestamp": expected_date.strftime("%d-%b-%Y") + " 15:30:00",
            "underlyingValue": spot,
            "expiryDates": [expiry_label],
            "data": records,
        },
        "filtered": {"data": records},
        "_fallback_source": "MarketNetra",
    }
    valid, reason = validate_option_chain(payload, expected_date)
    if not valid:
        raise RuntimeError(f"MarketNetra chain failed validation: {reason}")
    return payload, url


def fetch_option_chain(
    client: NseClient,
    symbol: str = "NIFTY",
    expected_date: date | None = None,
    metadata: dict | None = None,
    *,
    allow_fallback: bool = True,
) -> dict | None:
    url = f"{BASE}/api/option-chain-indices?symbol={symbol}"
    errors = []
    try:
        payload = client.get_json(url, referer=BASE + "/option-chain")
        valid, reason = validate_option_chain(payload, expected_date)
        if not valid:
            raise RuntimeError(reason)
        _set_metadata(
            metadata,
            source="NSE option-chain API",
            url=url,
            as_of=expected_date or _parse_date(payload["records"].get("timestamp")),
            fallback=False,
        )
        return payload
    except RuntimeError as exc:
        errors.append(f"NSE: {exc}")

    if not allow_fallback:
        warning = f"option chain direct NSE fetch failed: {'; '.join(errors)}"
        log.warning(warning)
        _mark_unavailable(metadata, warning)
        return None

    if expected_date is not None:
        try:
            payload, fallback_url = _fetch_marketnetra_option_chain(
                symbol, expected_date
            )
            _set_metadata(
                metadata,
                source="MarketNetra EOD option chain",
                url=fallback_url,
                as_of=expected_date,
                fallback=True,
                warning=(
                    "Third-party rendering of NSE EOD chain; payload passed date, "
                    "spot, expiry and strike/OI validation."
                ),
            )
            return payload
        except (RuntimeError, ValueError, requests.RequestException) as exc:
            errors.append(f"MarketNetra: {exc}")

    warning = f"option chain fetch failed for {symbol}: {'; '.join(errors)}"
    log.warning(warning)
    _mark_unavailable(metadata, warning)
    return None


# ---------------------------------------------------------------------------
# Index quote / daily OHLC
# ---------------------------------------------------------------------------
def validate_index_quote(
    row: Any, expected_date: date | None = None
) -> tuple[bool, str]:
    if not isinstance(row, dict):
        return False, "index quote is not an object"
    values: dict[str, float] = {}
    aliases = {
        "open": ("open",),
        "high": ("high",),
        "low": ("low",),
        "close": ("last", "lastPrice", "close"),
    }
    for name, candidates in aliases.items():
        raw_value = next(
            (row.get(key) for key in candidates if row.get(key) is not None), None
        )
        try:
            value = float(str(raw_value).replace(",", ""))
        except (TypeError, ValueError):
            return False, f"index quote has invalid {name}"
        if not math.isfinite(value) or value <= 0:
            return False, f"index quote has non-positive/non-finite {name}"
        values[name] = value
    if values["high"] < max(values["open"], values["close"], values["low"]):
        return False, "index quote high is inconsistent with OHLC"
    if values["low"] > min(values["open"], values["close"], values["high"]):
        return False, "index quote low is inconsistent with OHLC"
    quote_date = _parse_date(
        row.get("lastUpdateTime") or row.get("timestamp") or row.get("date")
    )
    if expected_date and quote_date != expected_date:
        return False, f"index quote date {quote_date} != requested {expected_date}"
    return True, "ok"


def _normalise_symbol(value: str) -> str:
    return "".join(character for character in str(value).upper() if character.isalnum())


def _fetch_yahoo_index_quote(symbol: str, expected_date: date) -> tuple[dict, str]:
    aliases = {
        "NIFTY": "%5ENSEI",
        "NIFTY50": "%5ENSEI",
        "BANKNIFTY": "%5ENSEBANK",
        "NIFTYBANK": "%5ENSEBANK",
    }
    ticker = aliases.get(_normalise_symbol(symbol))
    if not ticker:
        raise RuntimeError(f"Yahoo quote fallback does not support {symbol}")
    start = int(
        datetime.combine(
            expected_date - timedelta(days=7),
            datetime.min.time(),
            tzinfo=timezone.utc,
        ).timestamp()
    )
    end = int(
        datetime.combine(
            expected_date + timedelta(days=2),
            datetime.min.time(),
            tzinfo=timezone.utc,
        ).timestamp()
    )
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?period1={start}&period2={end}&interval=1d&events=history"
    )
    payload = _third_party_get(url, as_json=True)
    result = payload["chart"]["result"][0]
    timestamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]
    dates = [
        datetime.fromtimestamp(value, ZoneInfo("Asia/Kolkata")).date()
        for value in timestamps
    ]
    if expected_date not in dates:
        raise RuntimeError(f"Yahoo has no {expected_date} bar")
    index = dates.index(expected_date)
    close = quote["close"][index]
    if close is None:
        raise RuntimeError("Yahoo close is null")
    previous_close = None
    if index > 0:
        previous_close = quote["close"][index - 1]
    row = {
        "index": symbol,
        "open": quote["open"][index],
        "high": quote["high"][index],
        "low": quote["low"][index],
        "last": close,
        "previousClose": previous_close,
        "lastUpdateTime": expected_date.isoformat(),
    }
    valid, reason = validate_index_quote(row, expected_date)
    if not valid:
        raise RuntimeError(f"Yahoo index bar failed validation: {reason}")
    return row, url


def fetch_index_quote(
    client: NseClient,
    symbol: str = "NIFTY 50",
    expected_date: date | None = None,
    metadata: dict | None = None,
) -> dict | None:
    aliases = {
        "NIFTY": {"NIFTY", "NIFTY50"},
        "NIFTY50": {"NIFTY", "NIFTY50"},
        "BANKNIFTY": {"BANKNIFTY", "NIFTYBANK"},
        "NIFTYBANK": {"BANKNIFTY", "NIFTYBANK"},
        "FINNIFTY": {"FINNIFTY", "NIFTYFINANCIALSERVICES"},
        "MIDCPNIFTY": {"MIDCPNIFTY", "NIFTYMIDSELECT"},
    }
    wanted = aliases.get(_normalise_symbol(symbol), {_normalise_symbol(symbol)})
    url = BASE + "/api/allIndices"
    errors = []
    try:
        data = client.get_json(url, referer=BASE + "/")
        for row in data.get("data", []):
            if _normalise_symbol(row.get("index", "")) in wanted:
                quote_row = dict(row)
                quote_row.setdefault("timestamp", data.get("timestamp"))
                valid, reason = validate_index_quote(quote_row, expected_date)
                if not valid:
                    raise RuntimeError(f"NSE index row failed validation: {reason}")
                _set_metadata(
                    metadata,
                    source="NSE all-indices API",
                    url=url,
                    as_of=expected_date,
                    fallback=False,
                )
                return quote_row
        raise RuntimeError(f"symbol {symbol} absent from NSE allIndices")
    except RuntimeError as exc:
        errors.append(f"NSE: {exc}")

    if expected_date is not None:
        try:
            row, fallback_url = _fetch_yahoo_index_quote(symbol, expected_date)
            _set_metadata(
                metadata,
                source="Yahoo Finance daily chart",
                url=fallback_url,
                as_of=expected_date,
                fallback=True,
                warning="Date-exact daily OHLC fallback; NSE all-indices API failed.",
            )
            return row
        except (RuntimeError, KeyError, IndexError, requests.RequestException) as exc:
            errors.append(f"Yahoo: {exc}")

    warning = f"index quote failed: {'; '.join(errors)}"
    log.warning(warning)
    _mark_unavailable(metadata, warning)
    return None


# ---------------------------------------------------------------------------
# NSE pre-open index state (forward research only)
# ---------------------------------------------------------------------------
def _first_number(mapping: dict, *keys: str) -> float | None:
    for key in keys:
        if mapping.get(key) is None:
            continue
        try:
            value = float(str(mapping[key]).replace(",", ""))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            return value
    return None


def _normalise_preopen_symbol(symbol: str) -> str:
    aliases = {
        "NIFTY": "NIFTY",
        "NIFTY50": "NIFTY",
        "BANKNIFTY": "BANKNIFTY",
        "NIFTYBANK": "BANKNIFTY",
    }
    normalised = _normalise_symbol(symbol)
    return aliases.get(normalised, normalised)


MAX_PREOPEN_SOURCE_LAG = timedelta(minutes=10)
MAX_SOURCE_FUTURE_SKEW = timedelta(minutes=2)


def _timestamp_ist(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = date_parser.parse(str(value), dayfirst=True, fuzzy=True)
    except (TypeError, ValueError, OverflowError):
        return None
    ist = ZoneInfo("Asia/Kolkata")
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ist)
    return parsed.astimezone(ist)


def validate_preopen_state(
    state: Any,
    expected_date: date | None = None,
    captured_at: datetime | None = None,
) -> tuple[bool, str]:
    """Reject stale/incomplete NSE pre-open index/basket records.

    The NSE pre-open endpoint normally returns the constituents of a named
    index, rather than an official synthetic NIFTY IEP.  The collector therefore
    accepts either a genuine index quote when NSE supplies one or a clearly
    labelled constituent-breadth aggregate.  It never invents an index level
    from unweighted stock prices.
    """
    if not isinstance(state, dict):
        return False, "pre-open state is not an object"
    timestamp = state.get("timestamp")
    timestamp_date = _parse_date(timestamp)
    if expected_date and timestamp_date != expected_date:
        return False, f"pre-open state date {timestamp_date} != requested {expected_date}"
    if not isinstance(timestamp, str) or ":" not in timestamp:
        return False, "pre-open state timestamp has no clock time"
    if captured_at is not None:
        if captured_at.tzinfo is None:
            return False, "pre-open capture timestamp is timezone-naive"
        source_ist = _timestamp_ist(timestamp)
        captured_ist = captured_at.astimezone(ZoneInfo("Asia/Kolkata"))
        if source_ist is None:
            return False, "pre-open source timestamp is unparseable"
        source_lag = captured_ist - source_ist
        if source_lag < -MAX_SOURCE_FUTURE_SKEW:
            return False, "pre-open source timestamp is implausibly after capture"
        if source_lag > MAX_PREOPEN_SOURCE_LAG:
            return False, f"pre-open source timestamp is stale by {source_lag.total_seconds() / 60:.1f} minutes"

    state_type = state.get("state_type")
    if state_type == "index_quote":
        for field in ("previous_close", "indicative_price"):
            value = _first_number(state, field)
            if value is None or value <= 0:
                return False, f"pre-open index quote has invalid {field}"
        return True, "ok"
    if state_type == "constituent_breadth":
        count = _first_number(state, "constituent_count")
        advances = _first_number(state, "advances")
        declines = _first_number(state, "declines")
        unchanged = _first_number(state, "unchanged")
        mean_change = _first_number(state, "mean_pchange")
        if count is None or count < 5:
            return False, "pre-open breadth has fewer than five usable constituents"
        if None in (advances, declines, unchanged, mean_change):
            return False, "pre-open breadth has incomplete directional metrics"
        if int(advances + declines + unchanged) != int(count):
            return False, "pre-open breadth counts do not sum to constituents"
        # A valid top-level timestamp cannot make a mixed stale constituent
        # response safe. Every input to the aggregate must carry a same-date
        # NSE clock timestamp, otherwise the aggregate is rejected as stale.
        if _first_number(state, "constituent_timestamp_count") != count:
            return False, "pre-open breadth has missing constituent timestamps"
        if _first_number(state, "constituent_timestamp_without_clock_count") != 0:
            return False, "pre-open breadth has constituent timestamp without clock time"
        if _first_number(state, "constituent_timestamp_invalid_date_count") != 0:
            return False, "pre-open breadth has invalid constituent timestamp date"
        earliest = _parse_date(state.get("constituent_timestamp_earliest"))
        latest = _parse_date(state.get("constituent_timestamp_latest"))
        if earliest != timestamp_date or latest != timestamp_date:
            return False, "pre-open breadth has mixed/stale constituent timestamp dates"
        if captured_at is not None:
            earliest_source = _timestamp_ist(state.get("constituent_timestamp_earliest"))
            captured_ist = captured_at.astimezone(ZoneInfo("Asia/Kolkata"))
            if earliest_source is None or captured_ist - earliest_source > MAX_PREOPEN_SOURCE_LAG:
                return False, "pre-open breadth has stale constituent source timestamp"
        return True, "ok"
    return False, f"unknown pre-open state type {state_type!r}"


def _preopen_row(item: dict, payload_timestamp: Any) -> dict[str, Any]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    detail = item.get("detail") if isinstance(item.get("detail"), dict) else {}
    merged = {**item, **metadata}
    previous_close = _first_number(merged, "previousClose", "previous_close")
    indicative_price = _first_number(merged, "lastPrice", "last", "iep", "finalPrice", "open")
    pchange = _first_number(merged, "pChange", "pchange", "perChange")
    if pchange is None and previous_close and indicative_price:
        pchange = (indicative_price / previous_close - 1.0) * 100.0
    return {
        "symbol": str(merged.get("symbol") or merged.get("identifier") or ""),
        "timestamp": merged.get("lastUpdateTime") or merged.get("timestamp") or payload_timestamp,
        "previous_close": previous_close,
        "indicative_price": indicative_price,
        "change": _first_number(merged, "change"),
        "pchange": pchange,
        "total_buy_quantity": _first_number(merged, "totalBuyQuantity")
        or _first_number(detail, "totalBuyQuantity"),
        "total_sell_quantity": _first_number(merged, "totalSellQuantity")
        or _first_number(detail, "totalSellQuantity"),
        "final_quantity": _first_number(merged, "finalQuantity")
        or _first_number(detail, "finalQuantity"),
        "market_status": merged.get("marketStatus") or detail.get("marketStatus"),
    }


def _preopen_breadth_state(rows: list[dict[str, Any]], symbol: str) -> dict[str, Any]:
    usable = [
        row for row in rows
        if row["previous_close"] is not None and row["previous_close"] > 0
        and row["indicative_price"] is not None and row["indicative_price"] > 0
        and row["pchange"] is not None
    ]
    timestamps = [row["timestamp"] for row in usable if isinstance(row["timestamp"], str)]
    timestamp_dates = [_parse_date(value) for value in timestamps]
    ordered_changes = sorted(float(row["pchange"]) for row in usable)
    midpoint = len(ordered_changes) // 2
    median_change = (
        ordered_changes[midpoint]
        if len(ordered_changes) % 2
        else (ordered_changes[midpoint - 1] + ordered_changes[midpoint]) / 2
    ) if ordered_changes else None
    advances = sum(1 for row in usable if row["pchange"] > 0)
    declines = sum(1 for row in usable if row["pchange"] < 0)
    return {
        "symbol": symbol.upper(),
        "state_type": "constituent_breadth",
        # This is an NSE-provided constituent timestamp, not an inferred clock.
        "timestamp": timestamps[0] if timestamps else None,
        "constituent_timestamp_count": len(timestamps),
        "constituent_timestamp_without_clock_count": sum(":" not in value for value in timestamps),
        "constituent_timestamp_earliest": min(timestamps) if timestamps else None,
        "constituent_timestamp_latest": max(timestamps) if timestamps else None,
        "constituent_timestamp_invalid_date_count": sum(value is None for value in timestamp_dates),
        "constituent_count": len(usable),
        "advances": advances,
        "declines": declines,
        "unchanged": len(usable) - advances - declines,
        "mean_pchange": sum(float(row["pchange"]) for row in usable) / len(usable) if usable else None,
        "median_pchange": median_change,
        "max_pchange": max((float(row["pchange"]) for row in usable), default=None),
        "min_pchange": min((float(row["pchange"]) for row in usable), default=None),
        "total_buy_quantity": sum(row["total_buy_quantity"] or 0.0 for row in usable),
        "total_sell_quantity": sum(row["total_sell_quantity"] or 0.0 for row in usable),
        "final_quantity": sum(row["final_quantity"] or 0.0 for row in usable),
    }


def fetch_preopen_index_state(
    client: NseClient,
    symbol: str = "NIFTY",
    expected_date: date | None = None,
    metadata: dict | None = None,
    *,
    captured_at: datetime | None = None,
) -> dict | None:
    """Fetch direct-NSE pre-open state without a third-party or EOD fallback.

    ``market-data-pre-open`` is a constituent feed for NIFTY/BANKNIFTY in the
    normal case.  We retain an official index indication only if the feed offers
    a real index row; otherwise a source-labelled advance/decline breadth state
    is more honest than constructing an unweighted pseudo-index.
    """
    key = _normalise_preopen_symbol(symbol)
    url = f"{BASE}/api/market-data-pre-open?key={key}"
    try:
        payload = client.get_json(url, referer=BASE + "/market-data-pre-open")
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise RuntimeError("NSE pre-open payload has no data array")
        rows = [
            _preopen_row(item, payload.get("timestamp"))
            for item in payload["data"]
            if isinstance(item, dict)
        ]
        wanted = _normalise_symbol(symbol)
        exact_labels = {wanted, "NIFTY50" if wanted == "NIFTY" else wanted}
        exact = next(
            (row for row in rows if _normalise_symbol(row["symbol"]) in exact_labels),
            None,
        )
        if exact is not None:
            state = {
                "symbol": symbol.upper(),
                "state_type": "index_quote",
                **{key: value for key, value in exact.items() if key != "symbol"},
            }
        else:
            state = _preopen_breadth_state(rows, symbol)
        state["payload_sha256"] = payload_sha256(payload)
        valid, reason = validate_preopen_state(state, expected_date, captured_at)
        if not valid:
            raise RuntimeError(reason)
        if captured_at is not None:
            # Breadth is only as fresh as its oldest constituent input.
            source_clock = state.get("constituent_timestamp_earliest") or state["timestamp"]
            source_ist = _timestamp_ist(source_clock)
            state["source_lag_seconds"] = round(
                (captured_at.astimezone(ZoneInfo("Asia/Kolkata")) - source_ist).total_seconds(), 3
            )
        _set_metadata(
            metadata,
            source="NSE pre-open market-data API",
            url=url,
            as_of=expected_date or _parse_date(state["timestamp"]),
            fallback=False,
        )
        return state
    except (RuntimeError, ValueError, KeyError) as exc:
        warning = f"pre-open index state failed for {symbol}: {exc}"
        log.warning(warning)
        _mark_unavailable(metadata, warning)
        return None
