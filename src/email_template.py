"""Gmail-compatible HTML email templates for the NIFTY 9 PM decision report.

Rendering rules (Gmail compatibility):
- Every style is inline; Gmail strips ``<style>`` blocks, so none are used.
- Layout is built with nested ``<table>`` elements; no flexbox/grid/position.
- No external images, web fonts, scripts, or links are referenced.
- Only standard-library imports so this module stays testable without pandas.

Safety rules (presentation must NEVER weaken the financial gates):
- The decision string is rendered verbatim from the report payload. A
  WAIT / NO TRADE decision is never rewritten into a trade instruction.
- Raw class probabilities are labelled as class probabilities, never as
  profit probabilities, and carry the diagnostic-only note while the
  research promotion gate is failed.
- Gate failures render as prominent red/amber alerts. Fail-closed stays
  fail-closed: this module only re-displays the report, it never recomputes
  or overrides the decision.
"""

from __future__ import annotations

import html
import re
from typing import Any

# ---------------------------------------------------------------------------
# Palette (dark fintech dashboard)
# ---------------------------------------------------------------------------
PAGE_BG = "#070b14"
WRAPPER_BG = "#0a0f1d"
CARD_BG = "#101828"
CARD_BG_SOFT = "#0d1422"
CARD_BORDER = "#1e2b45"
HEADER_BG = "#0c1526"
DIVIDER = "#1a2540"

TEXT = "#e8eef8"
TEXT_SOFT = "#aab6c8"
MUTED = "#7e8ba1"

GREEN = "#2ee6a8"
GREEN_BG = "#0c2a21"
GREEN_BORDER = "#1d5c46"

RED = "#ff6b6b"
RED_BG = "#2a1114"
RED_BORDER = "#6e2530"

AMBER = "#ffc24d"
AMBER_BG = "#2a2010"
AMBER_BORDER = "#6e5522"

BLUE = "#5caff2"
BLUE_BG = "#0d2036"
BLUE_BORDER = "#1f4a7a"

PURPLE = "#b79cff"
PURPLE_BG = "#1d1836"
PURPLE_BORDER = "#4a3a8a"

MONO = "'Courier New', Courier, monospace"
SANS = "Arial, Helvetica, sans-serif"

_MAX_LOG_LINES = 90


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _pct(value: Any, digits: int = 2, default: str = "N/A") -> str:
    try:
        return f"{float(value) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return default


def _num(value: Any, digits: int = 2, default: str = "N/A") -> str:
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return default


def _truthy(value: Any) -> bool:
    return bool(value)


# ---------------------------------------------------------------------------
# Building blocks (all inline CSS)
# ---------------------------------------------------------------------------
def _row(cells: str, bgcolor: str = WRAPPER_BG) -> str:
    return f'<tr><td style="padding:0 12px 12px 12px;background:{bgcolor};">{cells}</td></tr>'


def _card(inner: str, bg: str = CARD_BG, border: str = CARD_BORDER, padding: str = "18px 20px") -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{bg};border:1px solid {border};border-radius:12px;border-collapse:separate;">'
        f'<tr><td style="padding:{padding};">{inner}</td></tr></table>'
    )


def _label(text: str, color: str = MUTED, size: int = 10) -> str:
    return (
        f'<span style="font-family:{SANS};font-size:{size}px;font-weight:bold;color:{color};'
        f'text-transform:uppercase;letter-spacing:1px;">{_esc(text)}</span>'
    )


def _section_heading(title: str, accent: str = BLUE) -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td style="padding:2px 2px 10px 2px;">'
        f'<span style="display:inline-block;width:4px;height:14px;background:{accent};'
        f'border-radius:2px;font-size:0;line-height:0;">&nbsp;</span>&nbsp;&nbsp;'
        f'<span style="font-family:{SANS};font-size:15px;font-weight:bold;color:{TEXT};'
        f'letter-spacing:0.4px;">{_esc(title)}</span>'
        f'</td></tr></table>'
    )


def _pill(text: str, fg: str, bg: str, border: str) -> str:
    return (
        f'<span style="display:inline-block;font-family:{SANS};font-size:11px;font-weight:bold;'
        f'color:{fg};background:{bg};border:1px solid {border};border-radius:20px;'
        f'padding:3px 12px;letter-spacing:0.5px;">{_esc(text)}</span>'
    )


def _status_pill(passed: bool, pass_text: str, fail_text: str) -> str:
    if passed:
        return _pill(pass_text, GREEN, GREEN_BG, GREEN_BORDER)
    return _pill(fail_text, RED, RED_BG, RED_BORDER)


def _accent_line(color: str, width: int = 26) -> str:
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" '
        f'style="margin:0 auto 10px auto;"><tr>'
        f'<td style="padding:0;"><span style="display:block;width:{width}px;height:3px;'
        f'background:{color};border-radius:2px;font-size:0;line-height:0;">&nbsp;</span></td>'
        f'</tr></table>'
    )


def _metric_cell(label: str, value: str, sub: str, accent: str, width: str = "25%") -> str:
    return (
        f'<td width="{width}" valign="top" style="padding:0 6px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{CARD_BG_SOFT};border:1px solid {CARD_BORDER};border-radius:10px;'
        f'border-collapse:separate;">'
        f'<tr><td style="padding:14px 12px;text-align:center;">'
        f'{_accent_line(accent)}'
        f'{_label(label)}'
        f'<span style="display:block;font-family:{SANS};font-size:22px;font-weight:bold;'
        f'color:{TEXT};margin-top:6px;">{_esc(value)}</span>'
        f'<span style="display:block;font-family:{SANS};font-size:11px;color:{MUTED};margin-top:4px;">'
        f'{_esc(sub)}</span>'
        f'</td></tr></table></td>'
    )


def _gate_cell(
    title: str,
    passed: bool | None,
    pass_text: str,
    fail_text: str,
    detail: str,
    warn: bool = False,
) -> str:
    if passed is None:
        pill = _pill(fail_text if fail_text else "CHECK MANUALLY", AMBER, AMBER_BG, AMBER_BORDER)
        icon, icon_color = "&#9888;", AMBER
    elif warn and not passed:
        pill = _pill(fail_text, AMBER, AMBER_BG, AMBER_BORDER)
        icon, icon_color = "&#9888;", AMBER
    elif passed:
        pill = _pill(pass_text, GREEN, GREEN_BG, GREEN_BORDER)
        icon, icon_color = "&#10003;", GREEN
    else:
        pill = _pill(fail_text, RED, RED_BG, RED_BORDER)
        icon, icon_color = "&#10007;", RED
    return (
        f'<td width="50%" valign="top" style="padding:0 6px 12px 6px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{CARD_BG};border:1px solid {CARD_BORDER};border-radius:10px;'
        f'border-collapse:separate;">'
        f'<tr><td style="padding:14px 14px 12px 14px;">'
        f'<span style="font-family:{SANS};font-size:12px;font-weight:bold;color:{TEXT_SOFT};'
        f'text-transform:uppercase;letter-spacing:0.8px;">{_esc(title)}</span>'
        f'<span style="display:block;margin-top:8px;">{pill}</span>'
        f'<span style="display:block;font-family:{SANS};font-size:11px;color:{MUTED};margin-top:8px;'
        f'line-height:15px;"><b style="color:{icon_color};">{icon}</b>&nbsp;{_esc(detail)}</span>'
        f'</td></tr></table></td>'
    )


def _alert_banner(icon: str, title: str, body: str, tone: str, tone_bg: str, tone_border: str) -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{tone_bg};border:1px solid {tone_border};border-left:4px solid {tone};'
        f'border-radius:10px;border-collapse:separate;">'
        f'<tr><td style="padding:12px 16px;">'
        f'<span style="font-family:{SANS};font-size:13px;font-weight:bold;color:{tone};">'
        f'{icon} {_esc(title)}</span>'
        f'<span style="display:block;font-family:{SANS};font-size:12px;color:{TEXT_SOFT};'
        f'margin-top:4px;line-height:17px;">{_esc(body)}</span>'
        f'</td></tr></table>'
    )


def _two_col(left_td: str, right_td: str) -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr>{left_td}{right_td}</tr></table>'
    )


def _spacer(height: int = 14) -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td style="height:{height}px;font-size:0;line-height:0;">&nbsp;</td></tr></table>'
    )


# ---------------------------------------------------------------------------
# Markdown extraction helpers (single source of truth stays the report)
# ---------------------------------------------------------------------------
def _md_section_lines(markdown: str, heading: str) -> list[str]:
    """Return the non-empty content lines of a ``## heading`` section."""
    out: list[str] = []
    inside = False
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if inside:
                break
            inside = stripped.lower() == f"## {heading}".lower()
            continue
        if stripped.startswith("#"):
            continue
        if inside and stripped:
            out.append(stripped)
    return out


def _md_subsection(markdown: str, title: str) -> str:
    """Return the text following a ``### title`` marker."""
    match = re.search(
        rf"###\s*{re.escape(title)}\s*\n?(.*?)(?=\n###|\n##|\Z)", markdown, re.DOTALL
    )
    if not match:
        return ""
    return " ".join(match.group(1).split())


def _md_bold_kv(markdown: str, key: str) -> str:
    """Extract the value of a ``**Key:** value`` line (bold-value tolerant)."""
    match = re.search(
        rf"\*\*{re.escape(key)}:\*\*\s*\**([^*\n]+?)\**\s*$", markdown, re.MULTILINE
    )
    return match.group(1).strip() if match else ""


def _md_decision(markdown: str) -> str:
    match = re.search(r"\*\*Final decision:\*\*\s*\*\*(.+?)\*\*", markdown)
    return match.group(1).strip() if match else ""


def _md_code_blocks(markdown: str) -> list[str]:
    return re.findall(r"```(?:text)?\n(.*?)```", markdown, re.DOTALL)


def _md_table_rows(markdown: str, heading: str) -> list[dict[str, str]]:
    """Parse the pipe table under a ``## heading`` section (pandas to_markdown style)."""
    header: list[str] | None = None
    rows: list[dict[str, str]] = []
    for line in _md_section_lines(markdown, heading):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if all(set(c) <= {":", "-", " ", ""} for c in cells):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def _bullet_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        item = line[2:].strip() if line.startswith("- ") else line.strip()
        if item:
            items.append(re.sub(r"\*\*(.+?)\*\*", r"\1", item))
    return items


# ---------------------------------------------------------------------------
# Component renderers
# ---------------------------------------------------------------------------
def _decision_hero(decision: str, sub_line: str, specialist: str | None) -> str:
    decision = decision or "WAIT / NO TRADE"
    upper = decision.upper()
    if "FAIL" in upper or "PIPELINE" in upper:
        tone, tone_bg, tone_border, icon = (RED, RED_BG, RED_BORDER, "&#9888;")
    elif upper.startswith("UP") or "LONG" in upper:
        tone, tone_bg, tone_border, icon = (GREEN, GREEN_BG, GREEN_BORDER, "&#9650;")
    elif upper.startswith("DOWN") or "SHORT" in upper:
        tone, tone_bg, tone_border, icon = (RED, RED_BG, RED_BORDER, "&#9660;")
    else:
        tone, tone_bg, tone_border, icon = (AMBER, AMBER_BG, AMBER_BORDER, "&#10074;&#10074;")
    specialist_line = ""
    if specialist:
        specialist_line = (
            f'<span style="display:block;font-family:{SANS};font-size:11px;color:{MUTED};'
            f'margin-top:12px;">Specialist raw direction (diagnostic): '
            f'<b style="color:{TEXT_SOFT};">{_esc(specialist)}</b></span>'
        )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{tone_bg};border:1px solid {tone_border};border-radius:14px;'
        f'border-collapse:separate;">'
        f'<tr><td style="padding:22px 20px;text-align:center;">'
        f'{_label("Final decision", tone)}'
        f'<span style="display:block;font-family:{SANS};font-size:30px;font-weight:bold;'
        f'color:{tone};margin-top:8px;letter-spacing:0.5px;">{icon}&nbsp;{_esc(decision)}</span>'
        f'<span style="display:block;font-family:{SANS};font-size:13px;color:{TEXT_SOFT};'
        f'margin-top:10px;">{_esc(sub_line)}</span>'
        f'{specialist_line}'
        f'</td></tr></table>'
    )


def _probability_bar(p_up: Any, p_down: Any, research_approved: bool) -> str:
    try:
        up = max(0.0, min(1.0, float(p_up)))
    except (TypeError, ValueError):
        up = 0.5
    try:
        down = max(0.0, min(1.0, float(p_down)))
    except (TypeError, ValueError):
        down = 1.0 - up
    total = up + down
    if total <= 0:
        up, down, total = 0.5, 0.5, 1.0
    up_pct = round(up / total * 100)
    down_pct = 100 - up_pct
    note = (
        "Raw class probability — diagnostic only, NOT a calibrated profit probability."
        if not research_approved
        else "Model class probability (research-approved sample)."
    )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{CARD_BG};border:1px solid {CARD_BORDER};border-radius:12px;'
        f'border-collapse:separate;">'
        f'<tr><td style="padding:16px 18px;">'
        f'<span style="font-family:{SANS};font-size:12px;font-weight:bold;color:{TEXT_SOFT};">'
        f'UP / DOWN class probability</span>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="border-radius:6px;border-collapse:separate;margin-top:10px;">'
        f'<tr>'
        f'<td width="{up_pct}%" style="background:{GREEN};padding:8px 10px;text-align:center;">'
        f'<span style="font-family:{SANS};font-size:12px;font-weight:bold;color:#052e22;">'
        f'UP {_pct(up)}</span></td>'
        f'<td width="{down_pct}%" style="background:{RED};padding:8px 10px;text-align:center;">'
        f'<span style="font-family:{SANS};font-size:12px;font-weight:bold;color:#330a0a;">'
        f'DOWN {_pct(down)}</span></td>'
        f'</tr></table>'
        f'<span style="display:block;font-family:{SANS};font-size:10px;color:{MUTED};'
        f'margin-top:8px;">{_esc(note)}</span>'
        f'</td></tr></table>'
    )


def _levels_grid(levels: dict[str, Any]) -> str:
    def _get(key: str) -> str:
        return _num(levels.get(key))

    def level_cell(label: str, value: str, sub: str, fg: str, bg: str, border: str, arrow: str) -> str:
        return (
            f'<td width="25%" valign="top" style="padding:0 5px;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="background:{bg};border:1px solid {border};border-radius:10px;border-collapse:separate;">'
            f'<tr><td style="padding:13px 10px;text-align:center;">'
            f'<span style="font-family:{SANS};font-size:11px;font-weight:bold;color:{fg};'
            f'text-transform:uppercase;letter-spacing:0.6px;">{arrow} {_esc(label)}</span>'
            f'<span style="display:block;font-family:{SANS};font-size:17px;font-weight:bold;'
            f'color:{TEXT};margin-top:6px;">{_esc(value)}</span>'
            f'<span style="display:block;font-family:{SANS};font-size:10px;color:{MUTED};'
            f'margin-top:3px;">{_esc(sub)}</span>'
            f'</td></tr></table></td>'
        )

    cells = (
        level_cell("Resistance", _get("resistance_1"), "breakout trigger", RED, RED_BG, RED_BORDER, "&#9650;")
        + level_cell("Pivot", _get("pivot"), "intraday pivot", BLUE, BLUE_BG, BLUE_BORDER, "&#9679;")
        + level_cell("Support", _get("support_1"), "breakdown trigger", GREEN, GREEN_BG, GREEN_BORDER, "&#9660;")
        + level_cell("ATR (14)", _get("atr14_points"), "points / day", PURPLE, PURPLE_BG, PURPLE_BORDER, "&#8776;")
    )
    extra = (
        f'<span style="font-family:{SANS};font-size:11px;color:{MUTED};line-height:16px;">'
        f'20-day range: <b style="color:{TEXT_SOFT};">{_get("support_20d")}</b> '
        f'&mdash; <b style="color:{TEXT_SOFT};">{_get("resistance_20d")}</b>'
        f' &nbsp;|&nbsp; Previous close: <b style="color:{TEXT_SOFT};">{_get("previous_close")}</b></span>'
    )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr>{cells}</tr></table>'
        + _spacer(10)
        + _card(extra, CARD_BG, CARD_BORDER, padding="12px 18px")
    )


def _weekly_table(scenarios: list[dict[str, Any]]) -> str:
    def th(text: str, align: str = "center") -> str:
        return (
            f'<th style="font-family:{SANS};font-size:10px;font-weight:bold;color:{BLUE};'
            f'text-transform:uppercase;letter-spacing:0.7px;padding:9px 8px;text-align:{align};'
            f'border-bottom:1px solid {BLUE_BORDER};">{_esc(text)}</th>'
        )

    def td(text: str, bold: bool = False, align: str = "center", color: str = TEXT_SOFT) -> str:
        weight = "bold" if bold else "normal"
        return (
            f'<td style="font-family:{SANS};font-size:12px;font-weight:{weight};color:{color};'
            f'padding:9px 8px;text-align:{align};border-bottom:1px solid {DIVIDER};">{text}</td>'
        )

    head = "".join(
        [th("Date", "left"), th("Session"), th("Expected centre"), th("Lower band"), th("Upper band")]
    )
    body_rows: list[str] = []
    for i, scen in enumerate(scenarios or []):
        zebra = CARD_BG if i % 2 == 0 else CARD_BG_SOFT
        body_rows.append(
            f'<tr style="background:{zebra};">'
            + td(_esc(scen.get("date", "—")), bold=True, align="left", color=TEXT)
            + td(_pill(f"S{scen.get('session', '?')}", BLUE, BLUE_BG, BLUE_BORDER))
            + td(_esc(_num(scen.get("expected_center"))), color=TEXT)
            + td(_esc(_num(scen.get("lower_risk_band"))), color=RED)
            + td(_esc(_num(scen.get("upper_risk_band"))), color=GREEN)
            + "</tr>"
        )
    if not body_rows:
        body_rows.append(
            f'<tr><td colspan="5" style="font-family:{SANS};font-size:12px;color:{MUTED};'
            f'padding:12px 8px;text-align:center;border-bottom:1px solid {DIVIDER};">'
            f'No weekly scenario data available.</td></tr>'
        )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{CARD_BG};border:1px solid {CARD_BORDER};border-radius:12px;'
        f'border-collapse:separate;">'
        f'<tr>{head}</tr>{"".join(body_rows)}</table>'
    )


def _sources_table(manifest: dict[str, Any] | None, markdown: str) -> str:
    rows: list[dict[str, str]] = []
    if manifest and isinstance(manifest.get("results"), list):
        for record in manifest["results"]:
            rows.append(
                {
                    "Dataset": str(record.get("dataset", "")),
                    "Selected source": str(record.get("source", "")),
                    "Status": str(record.get("status", "")),
                    "As-of": str(record.get("as_of") or ""),
                    "Rows": str(record.get("rows", "")),
                }
            )
    if not rows:
        rows = _md_table_rows(markdown, "Data-source health")
    if not rows:
        return _card(
            f'<span style="font-family:{SANS};font-size:12px;color:{MUTED};">'
            f"Source-health table unavailable in this run.</span>"
        )

    def th(text: str, align: str = "left") -> str:
        return (
            f'<th style="font-family:{SANS};font-size:10px;font-weight:bold;color:{BLUE};'
            f'text-transform:uppercase;letter-spacing:0.7px;padding:9px 8px;text-align:{align};'
            f'border-bottom:1px solid {BLUE_BORDER};">{_esc(text)}</th>'
        )

    def status_pill(status: str) -> str:
        s = status.lower()
        if s == "fresh":
            return _pill("\u25cf fresh", GREEN, GREEN_BG, GREEN_BORDER)
        if s == "cached":
            return _pill("\u25cf cached", AMBER, AMBER_BG, AMBER_BORDER)
        if s == "failed":
            return _pill("\u25cf failed", RED, RED_BG, RED_BORDER)
        return _pill(f"\u25cf {status or 'unknown'}", MUTED, CARD_BG_SOFT, CARD_BORDER)

    head = "".join([th("Dataset"), th("Source"), th("Status"), th("As-of"), th("Rows", "right")])
    body_rows: list[str] = []
    for i, row in enumerate(rows):
        zebra = CARD_BG if i % 2 == 0 else CARD_BG_SOFT
        body_rows.append(
            f'<tr style="background:{zebra};">'
            f'<td style="font-family:{SANS};font-size:12px;font-weight:bold;color:{TEXT};'
            f'padding:9px 8px;border-bottom:1px solid {DIVIDER};">{_esc(row.get("Dataset", ""))}</td>'
            f'<td style="font-family:{SANS};font-size:11px;color:{TEXT_SOFT};padding:9px 8px;'
            f'border-bottom:1px solid {DIVIDER};">{_esc(row.get("Selected source", ""))}</td>'
            f'<td style="padding:6px 8px;border-bottom:1px solid {DIVIDER};">'
            f'{status_pill(row.get("Status", ""))}</td>'
            f'<td style="font-family:{SANS};font-size:11px;color:{MUTED};padding:9px 8px;'
            f'border-bottom:1px solid {DIVIDER};">{_esc(row.get("As-of", ""))}</td>'
            f'<td style="font-family:{SANS};font-size:11px;color:{TEXT_SOFT};padding:9px 8px;'
            f'text-align:right;border-bottom:1px solid {DIVIDER};">{_esc(row.get("Rows", ""))}</td>'
            f"</tr>"
        )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{CARD_BG};border:1px solid {CARD_BORDER};border-radius:12px;'
        f'border-collapse:separate;">'
        f'<tr>{head}</tr>{"".join(body_rows)}</table>'
    )


def _playbook(markdown: str, levels: dict[str, Any] | None) -> str:
    bull = _md_subsection(markdown, "Bull path")
    bear = _md_subsection(markdown, "Bear path")
    trap = _md_subsection(markdown, "Trap rule")
    if not bull and levels:
        bull = (
            f"Support/pivot hold \u2192 close above {_num(levels.get('resistance_1'))} "
            f"\u2192 retest holds \u2192 only then long continuation is valid."
        )
    if not bear and levels:
        bear = (
            f"Resistance rejection \u2192 close below {_num(levels.get('support_1'))} "
            f"\u2192 failed reclaim \u2192 only then short continuation is valid."
        )
    if not trap:
        trap = "A wick/sweep alone is not entry confirmation. Wait for a completed candle and follow-through."

    def path_card(title: str, body: str, fg: str, bg: str, border: str) -> str:
        return (
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="background:{bg};border:1px solid {border};border-left:4px solid {fg};'
            f'border-radius:10px;border-collapse:separate;">'
            f'<tr><td style="padding:12px 16px;">'
            f'<span style="font-family:{SANS};font-size:12px;font-weight:bold;color:{fg};'
            f'text-transform:uppercase;letter-spacing:0.7px;">{_esc(title)}</span>'
            f'<span style="display:block;font-family:{SANS};font-size:12px;color:{TEXT_SOFT};'
            f'margin-top:5px;line-height:17px;">{_esc(body)}</span>'
            f'</td></tr></table>'
        )

    return (
        _two_col(
            f'<td width="50%" valign="top" style="padding:0 6px 12px 0;">'
            + path_card("Bull path", bull, GREEN, GREEN_BG, GREEN_BORDER)
            + "</td>",
            f'<td width="50%" valign="top" style="padding:0 0 12px 6px;">'
            + path_card("Bear path", bear, RED, RED_BG, RED_BORDER)
            + "</td>",
        )
        + path_card("Trap rule", trap, AMBER, AMBER_BG, AMBER_BORDER)
    )


def _evidence_chips(markdown: str) -> str:
    items = _bullet_items(_md_section_lines(markdown, "Model evidence"))
    if not items:
        items = [
            "Model evidence unavailable for this run.",
            "Any gate failure automatically forces WAIT / NO TRADE.",
        ]
    chips: list[str] = []
    for item in items:
        chips.append(
            f'<span style="display:block;font-family:{SANS};font-size:12px;color:{TEXT_SOFT};'
            f'padding:7px 0;border-bottom:1px solid {DIVIDER};line-height:17px;">'
            f'<b style="color:{BLUE};">&#9670;</b>&nbsp;&nbsp;{_esc(item)}</span>'
        )
    return _card("".join(chips), CARD_BG, CARD_BORDER, padding="8px 18px")


def _dont_do_box(markdown: str) -> str:
    items = _bullet_items(_md_section_lines(markdown, "What not to do"))
    if not items:
        items = [
            "Do not trade below the confidence or data-quality gate.",
            "Do not average a losing leveraged position.",
        ]
    rows: list[str] = []
    for item in items:
        rows.append(
            f'<tr><td width="18" valign="top" style="font-family:{SANS};font-size:13px;color:{RED};'
            f'padding:6px 0;">&#10007;</td>'
            f'<td valign="top" style="font-family:{SANS};font-size:12px;color:{TEXT_SOFT};'
            f'padding:6px 0;line-height:17px;">{_esc(item)}</td></tr>'
        )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{RED_BG};border:1px solid {RED_BORDER};border-radius:12px;'
        f'border-collapse:separate;">'
        f'<tr><td style="padding:16px 18px;">'
        f'<span style="font-family:{SANS};font-size:13px;font-weight:bold;color:{RED};'
        f'text-transform:uppercase;letter-spacing:0.8px;">&#10007; What not to do</span>'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin-top:6px;">{"".join(rows)}</table>'
        f'</td></tr></table>'
    )


# ---------------------------------------------------------------------------
# Document scaffolding
# ---------------------------------------------------------------------------
def _page(inner_rows: str, preview: str, title: str) -> str:
    return (
        "<!DOCTYPE html PUBLIC \"-//W3C//DTD XHTML 1.0 Transitional//EN\" "
        '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n'
        '<html xmlns="http://www.w3.org/1999/xhtml">\n'
        f"<head><meta charset=\"utf-8\" /><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />"
        f"<title>{_esc(title)}</title></head>\n"
        f'<body style="margin:0;padding:0;background:{PAGE_BG};">'
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{_esc(preview)}</div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f"style=\"background:{PAGE_BG};\">"
        f'<tr><td align="center" style="padding:24px 8px;">'
        f'<table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0" '
        f"style=\"width:640px;max-width:640px;background:{WRAPPER_BG};border:1px solid {CARD_BORDER};"
        f'border-radius:16px;overflow:hidden;border-collapse:separate;">'
        f"{inner_rows}"
        f"</table></td></tr></table></body></html>"
    )


def _accent_strip() -> str:
    colors = [GREEN, BLUE, PURPLE, AMBER]
    cells = "".join(
        f'<td width="25%" style="background:{c};height:4px;font-size:0;line-height:0;">&nbsp;</td>'
        for c in colors
    )
    return (
        f'<tr><td style="padding:0;"><table role="presentation" width="100%" cellpadding="0" '
        f'cellspacing="0" border="0"><tr>{cells}</tr></table></td></tr>'
    )


def _header(session: str, generated: str, brand_line: str, accent: str = BLUE) -> str:
    return _row(
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        f"<tr>"
        f'<td align="left">'
        f"{_label('FII / DII Decode', accent)}"
        f'<span style="display:block;font-family:{SANS};font-size:24px;font-weight:bold;color:{TEXT};'
        f'margin-top:4px;">NIFTY 9 PM <span style="color:{accent};">Decision Report</span></span>'
        f'<span style="display:block;font-family:{SANS};font-size:12px;color:{MUTED};margin-top:4px;">'
        f"Session <b style=\"color:{TEXT_SOFT};\">{_esc(session)}</b> &nbsp;|&nbsp; Generated "
        f"{_esc(generated)} IST</span>"
        f"</td>"
        f'<td align="right" valign="top">'
        f"{_pill(brand_line, TEXT_SOFT, CARD_BG, CARD_BORDER)}"
        f"</td>"
        f"</tr></table>",
        bgcolor=HEADER_BG,
    )


def _footer(risk_notice: str) -> str:
    notice = risk_notice or (
        "Research/decision-support only; not personalized investment advice. Futures and options "
        "can cause rapid losses. Verify exchange data, liquidity, costs and your risk capacity "
        "before any trade."
    )
    notice_label = _label("Risk notice", AMBER)
    notice_card = _card(
        notice_label
        + f'<span style="display:block;font-family:{SANS};font-size:11px;color:{TEXT_SOFT};'
        f"margin-top:8px;line-height:16px;\">{_esc(notice)}</span>",
        CARD_BG_SOFT,
        CARD_BORDER,
    )
    return _row(
        notice_card
        + '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        '<tr><td align="center" style="padding:16px 10px 6px 10px;">'
        f'<span style="font-family:{SANS};font-size:10px;color:{MUTED};line-height:15px;">'
        f"Plain-text Markdown fallback, JSON report, source manifest and ultra-hard audit are "
        f"attached to this email.<br/>Sent automatically by the FII/DII Decode pipeline "
        f"(GitHub Actions) &nbsp;|&nbsp; Fail-closed by design: any gate failure &rarr; "
        f"WAIT / NO TRADE.</span>"
        f"</td></tr></table>"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def build_success_html(
    payload: dict[str, Any] | None, manifest: dict[str, Any] | None, markdown: str
) -> str:
    """Render the nightly decision report as a Gmail-compatible HTML email."""
    payload = payload or {}
    pred = payload.get("prediction", {}) or {}
    gate = payload.get("data_gate", {}) or {}
    event = payload.get("event_risk", {}) or {}
    levels = payload.get("levels", {}) or {}

    decision = payload.get("decision") or _md_decision(markdown) or "WAIT / NO TRADE"
    session = str(payload.get("session_date") or "—")
    generated = str(payload.get("decision_time_ist", "")) or _md_bold_kv(markdown, "Generated")
    research_approved = _truthy(pred.get("research_approved"))
    confidence_pass = _truthy(pred.get("confidence_pass"))
    date_match = _truthy(payload.get("prediction_date_matches_session", True))
    data_passed = gate.get("passed")
    if data_passed is None:
        normalized = markdown.replace("**Data gate:**", "Data gate:")
        data_passed = "DATA GATE FAIL-CLOSED" not in markdown and "Data gate: **PASS**" in normalized
    history_ok = _truthy(gate.get("history_update_ok", True))

    # ---- top alerts (fail-closed reasons stay loud) ----
    alerts: list[str] = []
    if pred.get("error"):
        alerts.append(
            _alert_banner("&#9888;", "MODEL ERROR — FAIL-CLOSED", str(pred["error"]), RED, RED_BG, RED_BORDER)
        )
    if not data_passed:
        alerts.append(
            _alert_banner(
                "&#10007;",
                "DATA GATE FAIL-CLOSED",
                "Critical price/options/futures were not all fresh/date-matched, compact history "
                "failed, or overall quality was below threshold.",
                RED,
                RED_BG,
                RED_BORDER,
            )
        )
    if not date_match:
        alerts.append(
            _alert_banner(
                "&#10007;",
                "DATE MISMATCH — FAIL-CLOSED",
                f"Specialist as-of {pred.get('as_of')} vs session {session}.",
                RED,
                RED_BG,
                RED_BORDER,
            )
        )
    if not research_approved:
        alerts.append(
            _alert_banner(
                "&#9888;",
                "RESEARCH PROMOTION GATE FAILED",
                "Corrected holdout/cost metrics do not support a live directional trade. Raw class "
                "probability is diagnostic only and is NOT a calibrated profit probability.",
                AMBER,
                AMBER_BG,
                AMBER_BORDER,
            )
        )
    event_status = str(event.get("status", "NO_VERIFIED_CALENDAR"))
    if event_status != "CLEAR":
        blocked = _truthy(event.get("blocked"))
        alerts.append(
            _alert_banner(
                "&#9888;",
                f"EVENT CALENDAR: {event_status}",
                "Trade blocked by event risk."
                if blocked
                else "Verified calendar unavailable; check manually.",
                RED if blocked else AMBER,
                RED_BG if blocked else AMBER_BG,
                RED_BORDER if blocked else AMBER_BORDER,
            )
        )

    # ---- gates grid ----
    critical = gate.get("critical_fresh_date_matched", {}) or {}
    critical_text = "  ".join(
        f"{k}: {'OK' if _truthy(v) else 'MISSING'}" for k, v in critical.items()
    ) or "critical datasets"
    gates = _two_col(
        _gate_cell(
            "Data Gate",
            bool(data_passed),
            "PASS",
            "FAIL-CLOSED",
            f"Quality {_pct(gate.get('quality_score', payload.get('quality_score')))} | {critical_text}",
        ),
        _gate_cell(
            "Research Gate",
            research_approved,
            "APPROVED",
            "FAILED",
            "Corrected holdout & cost metrics",
        ),
    ) + _two_col(
        _gate_cell(
            "Confidence Gate",
            confidence_pass,
            "PASS",
            "BELOW GATE",
            f"Confidence {_pct(pred.get('confidence'))} vs frozen gate {_pct(pred.get('gate'), 0)}",
        ),
        _gate_cell(
            "Event Calendar",
            True if event_status == "CLEAR" else None,
            "CLEAR",
            event_status,
            "No blocking events"
            if event_status == "CLEAR"
            else "No verified calendar — check manually",
            warn=not _truthy(event.get("blocked")),
        ),
    ) + _two_col(
        _gate_cell(
            "Date Match",
            date_match,
            "MATCHED",
            "MISMATCH",
            f"Specialist as-of {pred.get('as_of') or '—'} vs session {session}",
        ),
        _gate_cell("History Update", history_ok, "OK", "FAILED", "Compact history update"),
    )

    # ---- metrics ----
    metrics = (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        + _metric_cell("Data Quality", _pct(payload.get("quality_score"), 0), "source completeness", GREEN)
        + _metric_cell("Confidence", _pct(pred.get("confidence")), f"gate {_pct(pred.get('gate'), 0)}", BLUE)
        + _metric_cell("UP prob.", _pct(pred.get("p_up")), "class probability", GREEN)
        + _metric_cell("DOWN prob.", _pct(pred.get("p_down")), "class probability", RED)
        + "</tr></table>"
    )

    # ---- stances ----
    stance = payload.get("trade_stance") or _md_bold_kv(markdown, "Trading stance") or "NO DIRECTIONAL POSITION"
    swing = str(payload.get("swing_stance") or "")
    invest = str(payload.get("investment_context") or "")
    stance_inner = (
        _label("Trading stance", TEXT_SOFT)
        + f'<span style="display:block;font-family:{SANS};font-size:16px;font-weight:bold;'
        f'color:{TEXT};margin-top:6px;">{_esc(stance)}</span>'
    )
    if swing:
        stance_inner += (
            f'<span style="display:block;font-family:{SANS};font-size:12px;color:{TEXT_SOFT};'
            f'margin-top:10px;line-height:17px;"><b style="color:{PURPLE};">Swing:</b> '
            f"{_esc(swing)}</span>"
        )
    if invest:
        stance_inner += (
            f'<span style="display:block;font-family:{SANS};font-size:12px;color:{TEXT_SOFT};'
            f'margin-top:6px;line-height:17px;"><b style="color:{BLUE};">Investment:</b> '
            f"{_esc(invest)}</span>"
        )
    stance_card = _card(stance_inner)

    risk_notice_lines = _md_section_lines(markdown, "Risk notice")
    risk_notice = " ".join(risk_notice_lines)

    sections: list[str] = []
    sections.append(_accent_strip())
    sections.append(_header(session, generated, "AUTO • 9 PM IST"))
    sections.append(_row(_decision_hero(decision, stance, pred.get("direction"))))
    if alerts:
        sections.append(_row("".join(f"{a}{_spacer(8)}" for a in alerts)))
    sections.append(_row(_section_heading("Decision Gates", BLUE) + gates))
    sections.append(
        _row(
            _section_heading("Key Metrics", GREEN)
            + metrics
            + _spacer(10)
            + _probability_bar(pred.get("p_up"), pred.get("p_down"), research_approved)
        )
    )
    sections.append(_row(_section_heading("Key Levels", PURPLE) + _levels_grid(levels)))
    sections.append(_row(stance_card))
    sections.append(
        _row(_section_heading("Conditional Playbook", GREEN) + _playbook(markdown, levels or None))
    )
    sections.append(
        _row(_section_heading("Mon–Fri Risk Map", BLUE) + _weekly_table(payload.get("weekly_scenarios") or []))
    )
    sections.append(_row(_section_heading("Data-Source Health", GREEN) + _sources_table(manifest, markdown)))
    sections.append(_row(_section_heading("Model Evidence", PURPLE) + _evidence_chips(markdown)))
    sections.append(_row(_dont_do_box(markdown)))
    sections.append(_footer(risk_notice))

    preview = f"NIFTY {session}: {decision}. Data gate, research gate, event calendar and key levels inside."
    return _page("".join(sections), preview, f"NIFTY 9 PM Report — {session}")


def build_failure_html(markdown: str) -> str:
    """Render the CI/pipeline failure email (safe decision is always WAIT)."""
    tests = _md_bold_kv(markdown, "Tests") or "unknown"
    pipeline = _md_bold_kv(markdown, "Production pipeline") or "unknown"
    utc = _md_bold_kv(markdown, "UTC time") or ""
    blocks = _md_code_blocks(markdown)
    test_log = blocks[0] if blocks else "Log not available."
    prod_log = blocks[1] if len(blocks) > 1 else "Log not available."

    def clip(text: str) -> str:
        lines = text.strip().splitlines()
        if len(lines) > _MAX_LOG_LINES:
            lines = [f"... ({len(lines) - _MAX_LOG_LINES} earlier lines clipped) ..."] + lines[
                -_MAX_LOG_LINES:
            ]
        return _esc("\n".join(lines))

    def status_cell(label: str, value: str) -> str:
        ok = value == "success"
        fg, bg, border = (GREEN, GREEN_BG, GREEN_BORDER) if ok else (RED, RED_BG, RED_BORDER)
        return (
            f'<td width="50%" valign="top" style="padding:0 6px;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="background:{bg};border:1px solid {border};border-radius:10px;border-collapse:separate;">'
            f'<tr><td style="padding:14px;text-align:center;">'
            f"{_label(label, fg)}"
            f'<span style="display:block;font-family:{SANS};font-size:18px;font-weight:bold;'
            f'color:{fg};margin-top:6px;">{_esc(value.upper())}</span>'
            f"</td></tr></table></td>"
        )

    def log_block(title: str, body: str) -> str:
        return (
            _label(title, MUTED)
            + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="background:{CARD_BG_SOFT};border:1px solid {CARD_BORDER};border-radius:10px;'
            f'border-collapse:separate;margin-top:6px;">'
            f'<tr><td style="padding:12px;">'
            f'<pre style="font-family:{MONO};font-size:11px;line-height:15px;color:{TEXT_SOFT};'
            f'margin:0;white-space:pre-wrap;word-break:break-word;">{clip(body)}</pre>'
            f"</td></tr></table>"
        )

    checks = [
        "GitHub Actions logs for the exact failing step",
        "Market-data provider availability (NSE may block cloud IPs)",
        "Repository secrets: SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM",
        "Source-schema changes in the data adapters",
    ]
    check_rows = "".join(
        f'<tr><td width="18" valign="top" style="font-family:{SANS};font-size:13px;color:{BLUE};'
        f'padding:6px 0;">&#9656;</td>'
        f'<td valign="top" style="font-family:{SANS};font-size:12px;color:{TEXT_SOFT};padding:6px 0;'
        f'line-height:17px;">{_esc(item)}</td></tr>'
        for item in checks
    )

    header_label = _label("FII / DII Decode", RED)
    inner = (
        _accent_strip()
        + _row(
            header_label
            + f'<span style="display:block;font-family:{SANS};font-size:24px;font-weight:bold;'
            f'color:{TEXT};margin-top:4px;">NIFTY 9 PM <span style="color:{RED};">'
            f"Pipeline Failure</span></span>"
            f'<span style="display:block;font-family:{SANS};font-size:12px;color:{MUTED};'
            f'margin-top:4px;">UTC {_esc(utc)}</span>',
            bgcolor=HEADER_BG,
        )
        + _row(
            _decision_hero(
                "PIPELINE FAILURE", "No trading decision should be used from this failed run.", None
            )
        )
        + _row(
            _alert_banner(
                "&#10074;&#10074;",
                "SAFE DECISION: WAIT / NO TRADE",
                "The pipeline did not complete. Do not act on any stale prediction from earlier runs.",
                AMBER,
                AMBER_BG,
                AMBER_BORDER,
            )
        )
        + _row(
            _section_heading("Run Status", RED)
            + '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            f"<tr>{status_cell('Tests', tests)}{status_cell('Pipeline', pipeline)}</tr></table>"
        )
        + _row(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="background:{CARD_BG};border:1px solid {CARD_BORDER};border-radius:12px;'
            f'border-collapse:separate;">'
            f'<tr><td style="padding:16px 18px;">'
            + _label("What to check", BLUE)
            + f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
            f'style="margin-top:6px;">{check_rows}</table>'
            f"</td></tr></table>"
        )
        + _row(log_block("Test log tail", test_log))
        + _row(log_block("Production log tail", prod_log))
        + _footer("")
    )
    return _page(
        inner, "NIFTY pipeline failed. Safe decision: WAIT / NO TRADE.", "NIFTY 9 PM Report — Pipeline Failure"
    )


def build_html_email(
    markdown: str, payload: dict[str, Any] | None, manifest: dict[str, Any] | None
) -> str:
    """Dispatch: failure markdown gets the failure template, everything else the report."""
    if "PIPELINE FAILURE" in markdown:
        return build_failure_html(markdown)
    return build_success_html(payload, manifest, markdown)
