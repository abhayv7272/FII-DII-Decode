"""Render the daily decode report (Amit Dhamija format) as HTML + Markdown.

Sections mirror the "Market Analysis Academy — Decoded" PDF while clearly
separating the automatic option-chain proxy from externally supplied exact
institutional references. Each level gets confirmed hold/reject and break/flip
branches with its next target; no unconditional reaction is claimed.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

_BIAS_COLOR = {
    "STRONG BULLISH": "#0f8a3c", "BULLISH": "#2fae5e",
    "NEUTRAL": "#7a7a7a",
    "BEARISH": "#e0663a", "STRONG BEARISH": "#c62828",
}
_DIR_EMOJI = {
    "UP": "🟢⬆️", "SIDEWAYS-UP": "🟢↗️", "RANGE": "🟡➡️",
    "SIDEWAYS-DOWN": "🔴↘️", "DOWN": "🔴⬇️",
    "NO-VALIDATED-EDGE": "⚪⏸️",
}

_VALIDATION_WARNING = (
    "EXPERIMENTAL / NOT VALIDATED FOR TRADING: the locked v2 rules reached 37.91% "
    "exact UP/FLAT/DOWN accuracy on 757 sessions versus a 42.14% majority baseline. "
    "Its next-open-to-close sign result remained approximately chance. Treat the OI "
    "lean as conditional context, never a standalone entry signal."
)
_DEMO_WARNING = (
    "DEMO FIXTURE: inputs are bundled synthetic/approximate sample values for pipeline "
    "testing. This report date is not a historical forecast or backtest observation."
)

_RISK = (
    "Never average a losing option-buy (premium decays to zero) — average at most "
    "once, only with a pre-set stop. Risk ≤10–15% capital per trade; scale in "
    "(e.g. 5%+5%) and place the stop-loss in the system immediately (~20–25 pts "
    "below support for a long). Wait for confluence."
)


def _levels_rows(levels: list) -> str:
    if not levels:
        return "<tr><td colspan='8'>No dated level inputs available.</td></tr>"
    return "\n".join(
        f"<tr><td>{level['strike']:.0f}</td><td>{level['kind']}</td>"
        f"<td>{level.get('source','')}<br><span style='font-size:11px'>"
        f"{level.get('label','')}</span></td><td>{level.get('basis','')}</td>"
        f"<td>{level.get('oi',0):,.0f}</td>"
        f"<td>{level.get('oi_change',0):+,.0f}</td>"
        f"<td>{level.get('evidence_grade','')}"
        f"{' · CONFLUENCE' if level.get('confluence') else ''}</td>"
        f"<td style='font-size:12px'>{level.get('evidence','')} "
        f"{level.get('confluence_note','')}</td></tr>"
        for level in levels
    )


def _level_prediction_rows(predictions: list) -> str:
    if not predictions:
        return "<tr><td colspan='8'>No level-by-level prediction: dated levels unavailable.</td></tr>"
    rows = []
    for prediction in predictions:
        hold = prediction["hold_or_reject_branch"]
        broken = prediction["break_branch"]
        rows.append(
            f"<tr><td>{prediction['strike']:.0f}</td><td>{prediction['kind']}</td>"
            f"<td>{prediction['source']}</td><td>{prediction['priority']}</td>"
            f"<td><b>{prediction['oi_lean_preferred_branch']}</b></td>"
            f"<td style='font-size:12px'><b>{hold['outcome']}</b>: "
            f"{hold['confirmation']} → {hold['target']}</td>"
            f"<td style='font-size:12px'><b>{broken['outcome']}</b>: "
            f"{broken['confirmation']} → {broken['target']}</td>"
            f"<td style='font-size:12px'>{prediction['gap_rule']} "
            f"{prediction['cascade_rule']} Without confirmation: "
            f"{prediction['no_confirmation']}.</td></tr>"
        )
    return "\n".join(rows)


def _gap_html(scenarios: list) -> str:
    if not scenarios:
        return "<li>No level-based scenarios available.</li>"
    return "\n".join(
        f"<li><b>{s.get('open', s.get('trigger',''))}:</b> "
        f"{s.get('plan', s.get('then',''))}</li>" for s in scenarios
    )


def _data_health_html(status: dict) -> str:
    if not status:
        return "<p>No fetch provenance was recorded.</p>"
    rows = []
    for name, item in status.get("inputs", {}).items():
        state = item.get("status", "unknown")
        color = "#0f8a3c" if state == "available" else (
            "#7a7a7a" if state in {"not_used", "not_provided"} else "#c62828"
        )
        rows.append(
            f"<tr><td>{name.replace('_',' ')}</td>"
            f"<td style='color:{color}'><b>{state}</b></td>"
            f"<td>{item.get('source') or '—'}</td>"
            f"<td>{item.get('as_of') or '—'}</td>"
            f"<td style='font-size:11px'>{item.get('warning','')}</td></tr>"
        )
    return (
        "<table border='0' cellpadding='5' width='100%' "
        "style='border-collapse:collapse;font-size:12px'>"
        "<tr style='background:#f2f2f2'><th>Input</th><th>Status</th>"
        "<th>Source</th><th>As of</th><th>Warning</th></tr>"
        + "".join(rows)
        + "</table>"
    )


def _participant_reads_html(reads: dict) -> str:
    if not reads:
        return ""
    rows = []
    order = ["Pro", "FII", "Client", "DII"]
    cols = ["index_call", "index_put", "index_fut", "stock_call", "stock_put", "stock_fut"]
    head = "".join(f"<th>{c.replace('_',' ')}</th>" for c in cols)
    for p in order:
        if p not in reads:
            continue
        cells = "".join(
            f"<td style='color:{'#0f8a3c' if reads[p].get(c,0)>0 else '#c62828' if reads[p].get(c,0)<0 else '#888'}'>"
            f"{reads[p].get(c,0):+.2f}</td>" for c in cols)
        rows.append(f"<tr><td><b>{p}</b></td>{cells}</tr>")
    return (f"<table border='0' cellpadding='5' style='border-collapse:collapse;font-size:12px'>"
            f"<tr style='background:#f2f2f2'><th>Group</th>{head}</tr>{''.join(rows)}</table>")


def _fmt_price(value) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _opening_sniper_html(sniper: dict) -> str:
    if not sniper:
        return "<p>No V10 opening sniper status was recorded.</p>"
    active = sniper.get("active")
    if active is True:
        color = "#0f8a3c"
        status = "ACTIVE"
    elif active is False:
        color = "#7a7a7a"
        status = "NO SIGNAL"
    else:
        color = "#f9a825"
        status = "WAIT FOR OPEN"
    validation = sniper.get("validation", {})
    gap = sniper.get("gap_pct")
    if isinstance(gap, (int, float)):
        gap_text = f"{gap:+.4f}%"
    elif gap is not None:
        gap_text = str(gap)
    else:
        gap_text = "—"
    observed = sniper.get("target_observed_in_quote_range")
    observed_text = "not checked"
    if observed is True:
        observed_text = "target already observed in fetched quote range"
    elif observed is False:
        observed_text = "target not observed in fetched quote range yet"
    return (
        f"<div style='margin:10px 0;padding:12px 14px;border-radius:8px;"
        f"background:{color}12;border-left:6px solid {color};font-size:13px'>"
        f"<div style='font-size:12px;color:#666'>V10 OPENING SNIPER — previous-close touch</div>"
        f"<div style='font-size:18px;font-weight:700;color:{color}'>{status}</div>"
        f"<div><b>Rule:</b> abs(open gap) "
        f"{sniper.get('band_min_abs_gap_pct', 0):.2f}% to &lt;"
        f"{sniper.get('band_max_abs_gap_pct', 0):.2f}% → target previous close intraday.</div>"
        f"<div><b>Current signal:</b> {sniper.get('direction_to_target','—')} "
        f"toward {_fmt_price(sniper.get('target'))}; gap {gap_text}</div>"
        f"<div><b>Validation:</b> overall {validation.get('overall_hit_rate', 0):.2f}% · "
        f"train {validation.get('train_2017_2023_hit_rate', 0):.2f}% · "
        f"val {validation.get('val_2024_2025_hit_rate', 0):.2f}% · "
        f"2026 confirm {validation.get('confirm_2026_hit_rate', 0):.2f}%.</div>"
        f"<div><b>Observed status:</b> {observed_text}</div>"
        f"<div style='font-size:12px;color:#666;margin-top:4px'>{sniper.get('warning','')}</div>"
        f"</div>"
    )


def _opening_sniper_markdown(sniper: dict) -> list[str]:
    if not sniper:
        return ["## V10 Opening Sniper", "", "No V10 opening sniper status was recorded.", ""]
    validation = sniper.get("validation", {})
    active = sniper.get("active")
    status = "ACTIVE" if active is True else "NO SIGNAL" if active is False else "WAIT FOR OPEN"
    observed = sniper.get("target_observed_in_quote_range")
    observed_text = "not checked"
    if observed is True:
        observed_text = "target already observed in fetched quote range"
    elif observed is False:
        observed_text = "target not observed in fetched quote range yet"
    gap = sniper.get("gap_pct")
    gap_text = f"{gap:+.4f}%" if isinstance(gap, (int, float)) else "—"
    return [
        "## V10 Opening Sniper — Previous-Close Touch",
        "",
        f"- **Status:** {status}",
        (
            f"- **Rule:** abs(open gap) {sniper.get('band_min_abs_gap_pct', 0):.2f}% "
            f"to <{sniper.get('band_max_abs_gap_pct', 0):.2f}% → target previous close intraday."
        ),
        f"- **Current signal:** {sniper.get('direction_to_target','—')} toward {_fmt_price(sniper.get('target'))}; gap {gap_text}",
        (
            f"- **Validation:** overall {validation.get('overall_hit_rate', 0):.2f}% · "
            f"train {validation.get('train_2017_2023_hit_rate', 0):.2f}% · "
            f"val {validation.get('val_2024_2025_hit_rate', 0):.2f}% · "
            f"2026 confirm {validation.get('confirm_2026_hit_rate', 0):.2f}%"
        ),
        f"- **Observed status:** {observed_text}",
        f"- **Warning:** {sniper.get('warning','')}",
        "",
    ]


def render_html(dr: dict, predictions: dict, levels: dict,
                report_date: str, symbol: str = "NIFTY",
                demo: bool = False) -> str:
    bias = dr["bias"]
    color = _BIAS_COLOR.get(bias, "#333")
    pcolor = _BIAS_COLOR.get(dr["positional_bias"], "#333")
    nd, nw = predictions["next_day"], predictions["next_week"]
    data_status = dr.get("data_status", {})
    level_method_warning = levels.get(
        "level_method_warning",
        "No dated option-chain or supplied institutional levels were available.",
    )
    demo_block = ""
    if demo:
        demo_block = (
            "<div style='margin:12px 0;padding:10px 14px;border-radius:8px;"
            "background:#ffebee;border-left:6px solid #c62828;font-size:13px'>"
            f"<b>Demo warning:</b> {_DEMO_WARNING}</div>"
        )

    conflict_block = ""
    if dr.get("smart_money_conflict"):
        conflict_block = (
            f"<div style='margin:12px 0;padding:10px 14px;border-radius:8px;"
            f"background:#fff3e0;border-left:6px solid #ef6c00'>"
            f"<b>⚠️ Smart-money conflict:</b> {dr['conflict_note']}</div>")

    signal_rows = "\n".join(
        f"<tr><td>{s['name']}</td><td>{s['score']:+.2f}</td>"
        f"<td>{s['weight']:.2f}</td><td style='font-size:12px'>{s['note']}</td></tr>"
        for s in dr["signals"]
    )

    m = dr.get("metrics", {})
    generated_at = datetime.now(ZoneInfo("Asia/Kolkata"))
    metric_items = "".join(
        (f"<span style='display:inline-block;margin:2px 10px 2px 0'><b>{k}</b>: "
         + (f"{v:,.0f}" if isinstance(v, (int, float)) else f"{v}") + "</span>")
        for k, v in m.items() if v is not None
    )

    return f"""\
<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FII/DII Decode — {report_date}</title></head>
<body style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;
 max-width:860px;margin:0 auto;padding:16px;color:#1c1c1c;background:#fff">
<h1 style="margin-bottom:0">📊 FII/DII/Pro/Client Decode</h1>
<div style="color:#666">{symbol} · {report_date} · generated {generated_at:%Y-%m-%d %H:%M IST}</div>
<div style="margin:14px 0;padding:10px 14px;border-radius:8px;background:#fff8e1;
 border-left:6px solid #f9a825;font-size:13px"><b>Validation warning:</b>
 {_VALIDATION_WARNING}</div>
{demo_block}

<h2>🛰️ Data Fetch Health</h2>
<p><b>Overall:</b> {data_status.get('overall', 'NOT_RECORDED')} &nbsp;|&nbsp;
<b>Run date:</b> {data_status.get('run_date', '—')} &nbsp;|&nbsp;
<b>Report session:</b> {data_status.get('report_date', report_date)}</p>
{_data_health_html(data_status)}
<p style="font-size:11px;color:#666">{data_status.get('policy','')}</p>

<div style="display:flex;gap:12px;flex-wrap:wrap;margin:16px 0">
  <div style="flex:1;min-width:240px;padding:14px 16px;border-radius:10px;
   background:{color}12;border-left:6px solid {color}">
    <div style="font-size:12px;color:#666">NEXT-DAY OI LEAN (Pro-led)</div>
    <div style="font-size:20px;font-weight:700;color:{color}">{bias}</div>
    <div>score <b>{dr['composite']:+.2f}</b> · setup strength <b>{dr['confidence']:.0f}/100</b></div>
    <div style="margin-top:4px">{_DIR_EMOJI.get(nd['direction'],'')} <b>{nd['direction']}</b></div>
    <div style="font-size:12px;margin-top:4px"><b>{nd.get('actionability','')}</b></div>
  </div>
  <div style="flex:1;min-width:240px;padding:14px 16px;border-radius:10px;
   background:{pcolor}12;border-left:6px solid {pcolor}">
    <div style="font-size:12px;color:#666">POSITIONAL CARRY CONTEXT (FII-led)</div>
    <div style="font-size:20px;font-weight:700;color:{pcolor}">{dr['positional_bias']}</div>
    <div>context score <b>{dr['positional_composite']:+.2f}</b></div>
    <div style="margin-top:4px">{_DIR_EMOJI.get(nw['direction'],'')} <b>{nw['direction']}</b></div>
    <div style="font-size:12px;margin-top:4px">Research lean: <b>{nw.get('research_lean','')}</b></div>
  </div>
</div>
{conflict_block}

<h2>🧩 Institutional Data & Setup</h2>
<p style="color:#444"><b>Retail:</b> {dr.get('retail_note','')}</p>
<p style="color:#444"><b>Move quality:</b> {dr.get('move_quality','')}</p>
<h3>Fresh-flow reads</h3>
{_participant_reads_html(dr.get('participant_reads', {}))}
<h3>As-on-date carry reads</h3>
{_participant_reads_html(dr.get('participant_carry_reads', {}))}
<p style="font-size:12px;color:#777">Green = bullish contribution, red = bearish.
Client/Retail is already contra-adjusted. Stock derivatives are diagnostics only in the
v2 next-day NIFTY score; carry is positional context, not the next-day trigger.</p>

<h2>🔮 Next-Day Conditional Plan (Gap Up / Flat / Gap Down)</h2>
<div style="font-size:18px">{_DIR_EMOJI.get(nd['direction'],'')} <b>{nd['direction']}</b>
 · setup strength {nd['confidence']:.0f}/100</div>
<p><b>Actionability:</b> {nd.get('actionability','')}</p>
<p style="color:#444">{nd['rationale']}</p>
<ul>{_gap_html(nd['scenarios'])}</ul>
{_opening_sniper_html(predictions.get('opening_sniper', {}))}

<h2>🗓️ Next-Week / Positional Context (Mon–Fri)</h2>
<div style="font-size:18px">{_DIR_EMOJI.get(nw['direction'],'')} <b>{nw['direction']}</b></div>
<p><b>Unvalidated research lean:</b> {nw.get('research_lean','')} ·
 <b>Actionability:</b> {nw.get('actionability','')}</p>
<p style="color:#444">{nw['rationale']}</p>
<ul>{_gap_html(nw['scenarios'])}</ul>

<h2>🧭 Level-by-Level Conditional Prediction</h2>
<div style="margin:10px 0;padding:10px 14px;background:#fff8e1;border-left:5px solid #f9a825;font-size:12px">
<b>Level-method disclosure:</b> {level_method_warning}<br>
<b>Option-chain input source:</b> {levels.get('option_chain_input_source') or 'unavailable'}</div>
<table border="0" cellpadding="6" cellspacing="0" width="100%"
 style="border-collapse:collapse;font-size:12px">
<tr style="background:#f2f2f2;text-align:left">
 <th>Level</th><th>Role</th><th>Source</th><th>Priority</th>
 <th>OI-lean preferred branch</th><th>Hold / reject confirmation</th>
 <th>Break / flip confirmation</th><th>Gap / no-confirmation rule</th></tr>
{_level_prediction_rows(nd.get('level_predictions', []))}
</table>
<p style="font-size:12px"><b>Preferred branch is conditional, not a probability.</b>
 No confirming candle means no level trade.</p>

<h2>📐 Level Evidence</h2>
<table border="0" cellpadding="6" cellspacing="0" width="100%"
 style="border-collapse:collapse;font-size:12px">
<tr style="background:#f2f2f2;text-align:left">
 <th>Strike</th><th>Role</th><th>Source</th><th>Basis</th><th>OI</th><th>ΔOI</th>
 <th>Evidence grade</th><th>Evidence / confluence</th></tr>
{_levels_rows(levels.get('levels', []))}
</table>
<p><b>Max Pain:</b> {levels.get('max_pain','n/a')} ·
 <b>PCR:</b> {levels.get('pcr','n/a')} — {levels.get('pcr_signal','')}</p>

<h2>🧬 Decode Signals</h2>
<table border="0" cellpadding="6" cellspacing="0" width="100%"
 style="border-collapse:collapse;font-size:14px">
<tr style="background:#f2f2f2;text-align:left">
 <th>Signal</th><th>Score</th><th>Weight</th><th>Note</th></tr>
{signal_rows}
</table>

<h2>📈 Key Metrics</h2>
<div style="font-size:13px;color:#333">{metric_items}</div>

<h2>🛡️ Trading Strategy & Risk Management</h2>
<p style="font-size:13px;color:#444">{_RISK}</p>

<hr style="margin-top:26px;border:none;border-top:1px solid #eee">
<p style="font-size:11px;color:#999">
Auto-generated by FII-DII-Decode using the participant-OI decode methodology
(see docs/methodology.md). Educational analysis of publicly available NSE data —
<b>not investment advice</b>. Markets are risky; do your own research.</p>
</body></html>"""


def render_markdown(dr: dict, predictions: dict, levels: dict,
                    report_date: str, symbol: str = "NIFTY",
                    demo: bool = False) -> str:
    nd, nw = predictions["next_day"], predictions["next_week"]
    L = [
        f"# FII/DII/Pro/Client Decode — {symbol} — {report_date}",
        "",
        f"> ⚠️ **Validation warning:** {_VALIDATION_WARNING}",
        "",
        (
            f"**Next-day OI lean (Pro-led):** {dr['bias']}  ·  score "
            f"`{dr['composite']:+.2f}`  ·  setup strength "
            f"{dr['confidence']:.0f}/100  ·  {nd['direction']}  ·  "
            f"{nd.get('actionability','')}"
        ),
        (
            f"**Positional carry context (FII-led):** {dr['positional_bias']}  ·  "
            f"score `{dr['positional_composite']:+.2f}`  ·  {nw['direction']}  ·  "
            f"research lean {nw.get('research_lean','')}"
        ),
        "",
    ]
    if demo:
        L[3:4] = [f"> 🧪 **Demo warning:** {_DEMO_WARNING}", ""]
    if dr.get("smart_money_conflict"):
        L += [f"> ⚠️ **Smart-money conflict:** {dr['conflict_note']}", ""]
    data_status = dr.get("data_status", {})
    L += [
        "## Data Fetch Health",
        "",
        f"**Overall:** `{data_status.get('overall', 'NOT_RECORDED')}`",
        (f"**Run date:** {data_status.get('run_date', '—')} · "
         f"**Report session:** {data_status.get('report_date', report_date)}"),
        "",
        "| Input | Status | Source | As of | Warning |",
        "|---|---|---|---|---|",
    ]
    for name, item in data_status.get("inputs", {}).items():
        warning = str(item.get("warning", "")).replace("|", "/")
        L.append(
            f"| {name.replace('_',' ')} | {item.get('status','unknown')} | "
            f"{item.get('source') or '—'} | {item.get('as_of') or '—'} | "
            f"{warning} |"
        )
    L += ["", data_status.get("policy", ""), ""]
    L += [
        "## Institutional Data & Setup",
        f"- **Retail:** {dr.get('retail_note','')}",
        f"- **Move quality:** {dr.get('move_quality','')}",
        "",
        "## Next-Day Conditional Plan (Gap Up / Flat / Gap Down)",
        f"- Forced research class: **{nd['direction']}** (setup strength {nd['confidence']:.0f}/100)",
        f"- Actionability: **{nd.get('actionability','')}**",
        f"- {nd['rationale']}",
    ]
    for s in nd["scenarios"]:
        L.append(f"  - **{s.get('open', s.get('trigger',''))}:** "
                 f"{s.get('plan', s.get('then',''))}")
    L += [""]
    L += _opening_sniper_markdown(predictions.get("opening_sniper", {}))
    L += ["## Next-Week / Positional Context (Mon–Fri)",
          f"- Forecast status: **{nw['direction']}**",
          f"- Unvalidated research lean: **{nw.get('research_lean','')}**",
          f"- Actionability: **{nw.get('actionability','')}**",
          f"- {nw['rationale']}"]
    for s in nw["scenarios"]:
        L.append(f"  - **{s.get('trigger','')}** → {s.get('then','')}")
    L += [
        "",
        "## Level-by-Level Conditional Prediction",
        "",
        f"> **Level-method disclosure:** {levels.get('level_method_warning', 'No dated level inputs available.')}",
        f"> **Option-chain input source:** {levels.get('option_chain_input_source') or 'unavailable'}",
        "",
        (
            "The OI-lean preferred branch is conditional, not a probability. Without a "
            "confirming candle: **WAIT / NO TRADE AT THIS LEVEL**."
        ),
        "",
        "| Level | Role | Source | Priority | OI-lean preferred branch | Hold/reject branch | Break/flip branch |",
        "|---:|---|---|---|---|---|---|",
    ]
    level_predictions = nd.get("level_predictions", [])
    if not level_predictions:
        L.append("| n/a | n/a | n/a | n/a | NO DATED LEVELS | Wait | Wait |")
    for prediction in level_predictions:
        hold = prediction["hold_or_reject_branch"]
        broken = prediction["break_branch"]
        L.append(
            f"| {prediction['strike']:.0f} | {prediction['kind']} | "
            f"{prediction['source']} | {prediction['priority']} | "
            f"{prediction['oi_lean_preferred_branch']} | "
            f"**{hold['outcome']}**: {hold['confirmation']} → {hold['target']} | "
            f"**{broken['outcome']}**: {broken['confirmation']} → {broken['target']} |"
        )
    L += [
        "",
        (
            "Every row also uses this gap rule: if price opens and sustains beyond the "
            "level, treat that level as skipped/flipped and evaluate the next level. "
            "Once an opposite-direction break invalidates the original OI lean, later "
            "preferred branches are void; follow confirmed price action only."
        ),
        "",
        "## Level Evidence",
        "",
        "| Strike | Role | Source | Basis | OI | ΔOI | Evidence score | Evidence grade | Confluence |",
        "|---:|---|---|---|---:|---:|---:|---|---|",
    ]
    for level in levels.get("levels", []):
        confluence = level.get("confluence_note", "") or "—"
        score = level.get("evidence_score")
        score_text = f"{score:.1f}" if score is not None else "n/a"
        source = level.get("source", "")
        label = level.get("label", "")
        source_text = f"{source} ({label})" if label else source
        L.append(
            f"| {level['strike']:.0f} | {level['kind']} | "
            f"{source_text} | {level.get('basis','')} | "
            f"{level.get('oi',0):,.0f} | {level.get('oi_change',0):+,.0f} | "
            f"{score_text} | {level.get('evidence_grade','')} | {confluence} |"
        )
    L += [
        "",
        (
            f"**Max Pain:** {levels.get('max_pain','n/a')} · "
            f"**PCR:** {levels.get('pcr','n/a')} — {levels.get('pcr_signal','')}"
        ),
        "",
        "## Decode Signals",
        "",
        "| Signal | Score | Weight | Note |",
        "|---|---|---|---|",
    ]
    for s in dr["signals"]:
        L.append(f"| {s['name']} | {s['score']:+.2f} | {s['weight']:.2f} | {s['note']} |")
    L += [
        "",
        "## Trading Strategy & Risk Management",
        "",
        _RISK,
        "",
        "---",
        (
            "_Auto-generated by FII-DII-Decode (participant-OI decode). "
            "Educational only — not investment advice._"
        ),
    ]
    return "\n".join(L)
