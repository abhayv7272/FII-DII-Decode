"""Render the daily decode report (Amit Dhamija format) as HTML + Markdown.

Sections mirror the "Market Analysis Academy — Decoded" PDF:
  1. Headline bias (next-day + positional)
  2. Institutional Data & Setup (FII/Pro/Retail/DII + cash + move quality)
  3. Next-Day Prediction (Gap Up / Flat / Gap Down scenarios)
  4. Next-Week / Positional Outlook
  5. Institutional Levels & Expected Reaction (option chain)
  6. Decode signals breakdown
  7. Trading strategy & risk management + disclaimer
"""
from __future__ import annotations

from datetime import datetime

_BIAS_COLOR = {
    "STRONG BULLISH": "#0f8a3c", "BULLISH": "#2fae5e",
    "NEUTRAL": "#7a7a7a",
    "BEARISH": "#e0663a", "STRONG BEARISH": "#c62828",
}
_DIR_EMOJI = {
    "UP": "🟢⬆️", "SIDEWAYS-UP": "🟢↗️", "RANGE": "🟡➡️",
    "SIDEWAYS-DOWN": "🔴↘️", "DOWN": "🔴⬇️",
}

_VALIDATION_WARNING = (
    "EXPERIMENTAL / NOT VALIDATED FOR TRADING: a 757-session NIFTY OI-only "
    "historical replay produced 36.20% exact UP/FLAT/DOWN accuracy versus a 42.14% "
    "majority-class baseline. Treat this as context, not a standalone entry signal."
)

_RISK = (
    "Never average a losing option-buy (premium decays to zero) — average at most "
    "once, only with a pre-set stop. Risk ≤10–15% capital per trade; scale in "
    "(e.g. 5%+5%) and place the stop-loss in the system immediately (~20–25 pts "
    "below support for a long). Wait for confluence."
)


def _levels_rows(levels: list) -> str:
    return "\n".join(
        f"<tr><td>{l['strike']:.0f}</td><td>{l['kind']}</td>"
        f"<td>{l['basis']}</td><td>{l['oi']:,.0f}</td>"
        f"<td>{l['oi_change']:+,.0f}</td><td>{l['distance_pct']:+.2f}%</td>"
        f"<td style='font-size:12px'>{l['reaction']}</td></tr>"
        for l in levels
    )


def _gap_html(scenarios: list) -> str:
    if not scenarios:
        return "<li>No level-based scenarios available.</li>"
    return "\n".join(
        f"<li><b>{s.get('open', s.get('trigger',''))}:</b> "
        f"{s.get('plan', s.get('then',''))}</li>" for s in scenarios
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


def render_html(dr: dict, predictions: dict, levels: dict,
                report_date: str, symbol: str = "NIFTY") -> str:
    bias = dr["bias"]
    color = _BIAS_COLOR.get(bias, "#333")
    pcolor = _BIAS_COLOR.get(dr["positional_bias"], "#333")
    nd, nw = predictions["next_day"], predictions["next_week"]

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
<div style="color:#666">{symbol} · {report_date} · generated {datetime.now():%Y-%m-%d %H:%M IST}</div>
<div style="margin:14px 0;padding:10px 14px;border-radius:8px;background:#fff8e1;
 border-left:6px solid #f9a825;font-size:13px"><b>Validation warning:</b>
 {_VALIDATION_WARNING}</div>

<div style="display:flex;gap:12px;flex-wrap:wrap;margin:16px 0">
  <div style="flex:1;min-width:240px;padding:14px 16px;border-radius:10px;
   background:{color}12;border-left:6px solid {color}">
    <div style="font-size:12px;color:#666">NEXT-DAY (Pro-led)</div>
    <div style="font-size:20px;font-weight:700;color:{color}">{bias}</div>
    <div>score <b>{dr['composite']:+.2f}</b> · conf <b>{dr['confidence']:.0f}%</b></div>
    <div style="margin-top:4px">{_DIR_EMOJI.get(nd['direction'],'')} <b>{nd['direction']}</b></div>
  </div>
  <div style="flex:1;min-width:240px;padding:14px 16px;border-radius:10px;
   background:{pcolor}12;border-left:6px solid {pcolor}">
    <div style="font-size:12px;color:#666">POSITIONAL / WEEK (FII-led)</div>
    <div style="font-size:20px;font-weight:700;color:{pcolor}">{dr['positional_bias']}</div>
    <div>score <b>{dr['positional_composite']:+.2f}</b> ·
     conf <b>{dr['positional_confidence']:.0f}%</b></div>
    <div style="margin-top:4px">{_DIR_EMOJI.get(nw['direction'],'')} <b>{nw['direction']}</b></div>
  </div>
</div>
{conflict_block}

<h2>🧩 Institutional Data & Setup</h2>
<p style="color:#444"><b>Retail:</b> {dr.get('retail_note','')}</p>
<p style="color:#444"><b>Move quality:</b> {dr.get('move_quality','')}</p>
{_participant_reads_html(dr.get('participant_reads', {}))}
<p style="font-size:12px;color:#777">Green = bullish contribution, red = bearish
(Client/Retail already shown contra-adjusted, i.e. bullish-for-market sign).</p>

<h2>🔮 Next-Day Prediction (Gap Up / Flat / Gap Down)</h2>
<div style="font-size:18px">{_DIR_EMOJI.get(nd['direction'],'')} <b>{nd['direction']}</b>
 · confidence {nd['confidence']:.0f}%</div>
<p style="color:#444">{nd['rationale']}</p>
<ul>{_gap_html(nd['scenarios'])}</ul>

<h2>🗓️ Next-Week / Positional Outlook (Mon–Fri)</h2>
<div style="font-size:18px">{_DIR_EMOJI.get(nw['direction'],'')} <b>{nw['direction']}</b>
 · confidence {nw['confidence']:.0f}%</div>
<p style="color:#444">{nw['rationale']}</p>
<ul>{_gap_html(nw['scenarios'])}</ul>

<h2>🧭 Institutional Levels & Expected Reaction</h2>
<table border="0" cellpadding="6" cellspacing="0" width="100%"
 style="border-collapse:collapse;font-size:14px">
<tr style="background:#f2f2f2;text-align:left">
 <th>Strike</th><th>Type</th><th>Basis</th><th>OI</th><th>ΔOI</th><th>Dist</th><th>Expected reaction</th></tr>
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
                    report_date: str, symbol: str = "NIFTY") -> str:
    nd, nw = predictions["next_day"], predictions["next_week"]
    L = [
        f"# FII/DII/Pro/Client Decode — {symbol} — {report_date}",
        "",
        f"> ⚠️ **Validation warning:** {_VALIDATION_WARNING}",
        "",
        f"**Next-day (Pro-led):** {dr['bias']}  ·  score `{dr['composite']:+.2f}`  ·  "
        f"conf {dr['confidence']:.0f}%  ·  {nd['direction']}",
        f"**Positional/Week (FII-led):** {dr['positional_bias']}  ·  "
        f"score `{dr['positional_composite']:+.2f}`  ·  conf "
        f"{dr['positional_confidence']:.0f}%  ·  {nw['direction']}",
        "",
    ]
    if dr.get("smart_money_conflict"):
        L += [f"> ⚠️ **Smart-money conflict:** {dr['conflict_note']}", ""]
    L += [
        "## Institutional Data & Setup",
        f"- **Retail:** {dr.get('retail_note','')}",
        f"- **Move quality:** {dr.get('move_quality','')}",
        "",
        "## Next-Day Prediction (Gap Up / Flat / Gap Down)",
        f"- Direction: **{nd['direction']}** (confidence {nd['confidence']:.0f}%)",
        f"- {nd['rationale']}",
    ]
    for s in nd["scenarios"]:
        L.append(f"  - **{s.get('open', s.get('trigger',''))}:** "
                 f"{s.get('plan', s.get('then',''))}")
    L += ["", "## Next-Week / Positional Outlook (Mon–Fri)",
          f"- Direction: **{nw['direction']}** (confidence {nw['confidence']:.0f}%)",
          f"- {nw['rationale']}"]
    for s in nw["scenarios"]:
        L.append(f"  - **{s.get('trigger','')}** → {s.get('then','')}")
    L += ["", "## Institutional Levels & Expected Reaction", "",
          "| Strike | Type | Basis | OI | ΔOI | Dist | Expected reaction |",
          "|---|---|---|---|---|---|---|"]
    for l in levels.get("levels", []):
        L.append(f"| {l['strike']:.0f} | {l['kind']} | {l['basis']} | "
                 f"{l['oi']:,.0f} | {l['oi_change']:+,.0f} | {l['distance_pct']:+.2f}% | "
                 f"{l['reaction']} |")
    L += ["", f"**Max Pain:** {levels.get('max_pain','n/a')} · "
          f"**PCR:** {levels.get('pcr','n/a')} — {levels.get('pcr_signal','')}", "",
          "## Decode Signals", "",
          "| Signal | Score | Weight | Note |", "|---|---|---|---|"]
    for s in dr["signals"]:
        L.append(f"| {s['name']} | {s['score']:+.2f} | {s['weight']:.2f} | {s['note']} |")
    L += ["", "## Trading Strategy & Risk Management", "", _RISK, "",
          "---",
          "_Auto-generated by FII-DII-Decode (participant-OI decode). "
          "Educational only — not investment advice._"]
    return "\n".join(L)
