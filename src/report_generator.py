import os
import datetime

class ReportGenerator:
    def __init__(self, output_dir="reports"):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.output_dir = os.path.join(self.base_dir, output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_html_report(self, calc_res, regime_res, sector_res, macro_res):
        date_str = calc_res["date"]
        display_date = calc_res["display_date"]
        cis = calc_res["cis_score"]
        fii_ratio = calc_res["fii_long_ratio"]
        fii_stk_3d = calc_res["fii_stk_flow_3d"]
        
        regime_name = regime_res["regime_name"]
        regime_desc = regime_res["regime_desc"]
        signal = regime_res["primary_signal"]
        signal_color = regime_res["signal_color"]
        cap_pct = regime_res["capital_allocation_pct"]
        cash_pct = regime_res["cash_reserve_pct"]
        action_text = regime_res["action_instructions"]
        
        # Build Sector HTML Rows
        sector_rows_html = ""
        for s in sector_res.get("all_sectors", []):
            if s["status_code"] == "LEADER":
                badge = '<span style="background:rgba(16,185,129,0.2);color:#10B981;padding:4px 8px;border-radius:6px;font-weight:700;font-size:12px;">🚀 TOP LEADER</span>'
            elif s["status_code"] == "IMPROVING":
                badge = '<span style="background:rgba(59,130,246,0.2);color:#3B82F6;padding:4px 8px;border-radius:6px;font-weight:600;font-size:12px;">📈 IMPROVING</span>'
            elif s["status_code"] == "NEUTRAL":
                badge = '<span style="background:rgba(245,158,11,0.2);color:#F59E0B;padding:4px 8px;border-radius:6px;font-weight:600;font-size:12px;">⚖️ NEUTRAL</span>'
            else:
                badge = '<span style="background:rgba(239,68,68,0.2);color:#EF4444;padding:4px 8px;border-radius:6px;font-weight:600;font-size:12px;">🔻 LAGGARD</span>'
                
            ema_badge = '✅ Above 20 EMA' if s['above_20_ema'] else '❌ Below 20 EMA'
            chg_1w_color = '#10B981' if s['chg_1w'] >= 0 else '#EF4444'
            chg_1m_color = '#10B981' if s['chg_1m'] >= 0 else '#EF4444'
            
            sector_rows_html += f"""
            <tr style="border-bottom: 1px solid #1E293B;">
                <td style="padding: 12px; font-weight: 700; color: #F8FAFC;">{s['name']}</td>
                <td style="padding: 12px; color: #94A3B8; font-size: 13px;">{s['description']}</td>
                <td style="padding: 12px; font-weight: 600; color: {chg_1w_color};">{s['chg_1w']:+.2f}%</td>
                <td style="padding: 12px; font-weight: 600; color: {chg_1m_color};">{s['chg_1m']:+.2f}%</td>
                <td style="padding: 12px; font-size: 13px; color: #CBD5E1;">{ema_badge}</td>
                <td style="padding: 12px; font-weight: 700; color: #38BDF8;">{s['rs_score']:+.2f}</td>
                <td style="padding: 12px;">{badge}</td>
            </tr>
            """

        # Build Sheet Tables HTML
        sheet_sections_html = ""
        for sec_name, rows in calc_res["sheet_sections"].items():
            rows_html = ""
            for r in rows:
                p_name = r["participant"]
                l_action = r["long_action"]
                s_action = r["short_action"]
                n_action = r["net_action"]
                c_today = f"{r['carried_t0']:,}"
                c_1d = f"{r['carried_t1']:,}"
                c_2d = f"{r['carried_t2']:,}"
                
                net_color = "#10B981" if r["sentiment"] == "BULLISH" else "#EF4444" if r["sentiment"] == "BEARISH" else "#94A3B8"
                car_color = "#10B981" if r["carried_sentiment"] == "BULLISH" else "#EF4444" if r["carried_sentiment"] == "BEARISH" else "#94A3B8"
                
                rows_html += f"""
                <tr style="border-bottom: 1px solid #1E293B; font-size: 13px;">
                    <td style="padding: 8px 12px; font-weight: 700; color: #E2E8F0;">{p_name}</td>
                    <td style="padding: 8px 12px; color: #CBD5E1;">{l_action}</td>
                    <td style="padding: 8px 12px; color: #CBD5E1;">{s_action}</td>
                    <td style="padding: 8px 12px; font-weight: 700; color: {net_color};">{n_action}</td>
                    <td style="padding: 8px 12px; font-weight: 700; color: {car_color};">{c_today}</td>
                    <td style="padding: 8px 12px; color: #94A3B8;">{c_1d}</td>
                    <td style="padding: 8px 12px; color: #64748B;">{c_2d}</td>
                </tr>
                """
                
            sheet_sections_html += f"""
            <div style="background: #0F172A; border-radius: 12px; border: 1px solid #1E293B; margin-bottom: 20px; overflow: hidden;">
                <div style="background: #1E293B; padding: 10px 16px; font-weight: 800; color: #38BDF8; font-size: 15px; letter-spacing: 0.5px;">
                    📊 {sec_name.upper()}
                </div>
                <table style="width: 100%; border-collapse: collapse; text-align: left;">
                    <thead>
                        <tr style="background: #0B1120; color: #94A3B8; font-size: 12px; text-transform: uppercase;">
                            <th style="padding: 10px 12px;">Participant</th>
                            <th style="padding: 10px 12px;">Long Delta</th>
                            <th style="padding: 10px 12px;">Short Delta</th>
                            <th style="padding: 10px 12px;">Net Today</th>
                            <th style="padding: 10px 12px;">Carried (Today)</th>
                            <th style="padding: 10px 12px;">1 Day Ago</th>
                            <th style="padding: 10px 12px;">2 Days Ago</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
            """

        # Traps HTML
        traps_html = ""
        for trap in calc_res.get("traps", []):
            traps_html += f"""
            <div style="background: rgba(15, 23, 42, 0.8); border-left: 4px solid {trap['color']}; padding: 14px 18px; border-radius: 8px; margin-bottom: 12px; border: 1px solid #1E293B;">
                <div style="font-weight: 800; color: {trap['color']}; font-size: 15px; margin-bottom: 4px;">{trap['title']}</div>
                <div style="color: #CBD5E1; font-size: 13.5px; line-height: 1.5;">{trap['description']}</div>
            </div>
            """
        if not traps_html:
            traps_html = '<div style="color:#94A3B8;font-size:13px;padding:10px;">No extreme trapping divergence detected today. Market trading in structural alignment.</div>'

        # Macro Cards HTML
        macro_cards_html = ""
        if macro_res:
            m_items = [
                ("Brent Crude", macro_res.get("brent_crude", {}), "USD/bbl", "<$85 is Bullish"),
                ("US 10Y Yield", macro_res.get("us_10y_yield", {}), "%", "<4.4% is Bullish"),
                ("Dollar Index (DXY)", macro_res.get("us_dollar_index", {}), "pts", "<102 is Bullish"),
                ("Dow Jones", macro_res.get("dow_jones", {}), "pts", "US Sentiment"),
                ("Nifty 50 Index", macro_res.get("nifty_50", {}), "pts", "Domestic Benchmark"),
            ]
            for label, data, unit, note in m_items:
                chg = data.get("change_pct", 0)
                px = data.get("current", 0)
                chg_c = "#10B981" if chg >= 0 else "#EF4444"
                macro_cards_html += f"""
                <div style="background: #0F172A; border: 1px solid #1E293B; border-radius: 10px; padding: 12px 16px; flex: 1; min-width: 140px;">
                    <div style="color: #94A3B8; font-size: 12px; font-weight: 600;">{label}</div>
                    <div style="color: #F8FAFC; font-size: 18px; font-weight: 800; margin: 4px 0;">{px:,.2f} <span style="font-size: 12px; color: #64748B;">{unit}</span></div>
                    <div style="font-size: 12px; font-weight: 700; color: {chg_c};">{chg:+.2f}% <span style="font-size: 11px; color: #64748B; font-weight: 400;">({note})</span></div>
                </div>
                """

        # Full HTML Template
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Money Institutional Prediction Report - {display_date}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: #030712;
            color: #F8FAFC;
            margin: 0;
            padding: 24px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1100px;
            margin: 0 auto;
        }}
        .card {{
            background: #0B1120;
            border: 1px solid #1E293B;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        }}
        .btn-badge {{
            display: inline-block;
            padding: 8px 18px;
            border-radius: 30px;
            font-weight: 800;
            font-size: 16px;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- HEADER HERO BANNER -->
        <div class="card" style="background: linear-gradient(135deg, #0B1120 0%, #111827 50%, #0F172A 100%); border-top: 4px solid #38BDF8;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; margin-bottom: 16px;">
                <div>
                    <span style="background: rgba(56, 189, 248, 0.15); color: #38BDF8; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; text-transform: uppercase;">
                        Institutional Intelligence Report
                    </span>
                    <h1 style="margin: 8px 0 4px 0; font-size: 28px; font-weight: 900; color: #FFFFFF;">
                        Smart Money Daily Market Prediction
                    </h1>
                    <div style="color: #94A3B8; font-size: 14px;">
                        Date: <strong style="color: #E2E8F0;">{display_date}</strong> | Official NSE Participant Open Interest & Quantitative Analytics
                    </div>
                </div>
                <div>
                    <div class="btn-badge" style="background: {signal_color}; color: #FFFFFF; box-shadow: 0 4px 14px rgba(0,0,0,0.4);">
                        {signal}
                    </div>
                </div>
            </div>

            <!-- REGIME & SCORE HERO GRID -->
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-top: 20px;">
                <div style="background: #030712; border: 1px solid #1E293B; border-radius: 12px; padding: 16px;">
                    <div style="color: #94A3B8; font-size: 12px; font-weight: 600; text-transform: uppercase;">Composite Institutional Score (CIS)</div>
                    <div style="font-size: 32px; font-weight: 900; color: {'#10B981' if cis >= 3 else '#EF4444' if cis <= -3 else '#F59E0B'}; margin: 4px 0;">
                        {cis:+.1f} <span style="font-size: 14px; color: #64748B;">/ 10</span>
                    </div>
                    <div style="color: #CBD5E1; font-size: 12.5px;">
                        {'🟢 High Bullish Conviction' if cis >= 4 else '🔴 High Bearish Pressure' if cis <= -4 else '🟡 Range-Bound / Neutral'}
                    </div>
                </div>

                <div style="background: #030712; border: 1px solid #1E293B; border-radius: 12px; padding: 16px;">
                    <div style="color: #94A3B8; font-size: 12px; font-weight: 600; text-transform: uppercase;">Market Regime</div>
                    <div style="font-size: 18px; font-weight: 800; color: {regime_res['regime_color']}; margin: 8px 0;">
                        {regime_name}
                    </div>
                    <div style="color: #94A3B8; font-size: 12px; line-height: 1.4;">
                        FII Index Long Ratio: <strong style="color: #F8FAFC;">{fii_ratio}%</strong>
                    </div>
                </div>

                <div style="background: #030712; border: 1px solid #1E293B; border-radius: 12px; padding: 16px;">
                    <div style="color: #94A3B8; font-size: 12px; font-weight: 600; text-transform: uppercase;">Capital Allocation %</div>
                    <div style="display: flex; gap: 12px; align-items: baseline; margin: 6px 0;">
                        <span style="font-size: 26px; font-weight: 900; color: #10B981;">{cap_pct}% <span style="font-size: 12px; color: #94A3B8;">Stocks</span></span>
                        <span style="font-size: 20px; font-weight: 800; color: #F59E0B;">{cash_pct}% <span style="font-size: 12px; color: #94A3B8;">Cash</span></span>
                    </div>
                    <div style="color: #CBD5E1; font-size: 12px;">
                        Exposure level recommended for 10-40 day swings.
                    </div>
                </div>

                <div style="background: #030712; border: 1px solid #1E293B; border-radius: 12px; padding: 16px;">
                    <div style="color: #94A3B8; font-size: 12px; font-weight: 600; text-transform: uppercase;">FII 3-Day Stock Flow</div>
                    <div style="font-size: 24px; font-weight: 900; color: {'#10B981' if fii_stk_3d > 0 else '#EF4444'}; margin: 6px 0;">
                        {fii_stk_3d:+,}
                    </div>
                    <div style="color: #94A3B8; font-size: 12px;">
                        {'Institutional Stock Accumulation' if fii_stk_3d > 0 else 'Institutional Stock Distribution'}
                    </div>
                </div>
            </div>
        </div>

        <!-- ACTIONABLE SWING STRATEGY & NIFTY TRAJECTORY -->
        <div class="card">
            <h2 style="margin-top: 0; font-size: 20px; color: #38BDF8; display: flex; align-items: center; gap: 8px;">
                🎯 10-TO-40 DAY SWING STRATEGY & CHART TRAJECTORY
            </h2>
            
            <div style="background: #030712; border: 1px solid #1E293B; border-radius: 12px; padding: 18px; margin-bottom: 16px;">
                <div style="color: #F8FAFC; font-weight: 700; font-size: 15px; margin-bottom: 6px;">Actionable Protocol:</div>
                <div style="color: #CBD5E1; font-size: 14px; line-height: 1.6;">
                    {action_text}
                </div>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px;">
                <div style="background: #030712; border: 1px solid #1E293B; border-radius: 12px; padding: 16px;">
                    <div style="color: #94A3B8; font-size: 12px; font-weight: 700; text-transform: uppercase; margin-bottom: 8px;">Expected Trajectory Curve</div>
                    <div style="color: #38BDF8; font-size: 14px; font-weight: 600; line-height: 1.5;">
                        {regime_res['trajectory']}
                    </div>
                </div>

                <div style="background: #030712; border: 1px solid #1E293B; border-radius: 12px; padding: 16px;">
                    <div style="color: #94A3B8; font-size: 12px; font-weight: 700; text-transform: uppercase; margin-bottom: 8px;">Key Technical & Sweep Levels</div>
                    <div style="font-size: 13.5px; color: #CBD5E1; line-height: 1.8;">
                        <div>🛑 Resistance 2: <strong style="color: #F8FAFC;">{regime_res['resistance_2']}</strong></div>
                        <div>🚧 Resistance 1: <strong style="color: #F8FAFC;">{regime_res['resistance_1']}</strong></div>
                        <div>🛡️ Support 1: <strong style="color: #10B981;">{regime_res['support_1']}</strong></div>
                        <div>⚠️ SL Sweep Zone: <strong style="color: #F59E0B;">{regime_res['sweep_zone']}</strong> (Liquidity Hunt)</div>
                        <div>⛔ Support 2: <strong style="color: #EF4444;">{regime_res['support_2']}</strong></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- INSTITUTIONAL TRAPS & SETUP DETECTION -->
        <div class="card">
            <h2 style="margin-top: 0; font-size: 20px; color: #F59E0B; display: flex; align-items: center; gap: 8px;">
                ⚡ SMART MONEY TRAP DETECTION & MARKET FOOTPRINTS
            </h2>
            {traps_html}
        </div>

        <!-- SECTOR ROTATION LEADERBOARD -->
        <div class="card">
            <h2 style="margin-top: 0; font-size: 20px; color: #10B981; display: flex; align-items: center; gap: 8px;">
                🔄 INSTITUTIONAL SECTOR ROTATION LEADERBOARD
            </h2>
            <div style="color: #94A3B8; font-size: 13px; margin-bottom: 16px;">
                {sector_res.get('rotation_summary', '')}
            </div>
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; text-align: left;">
                    <thead>
                        <tr style="background: #1E293B; color: #94A3B8; font-size: 12px; text-transform: uppercase;">
                            <th style="padding: 10px 12px;">Sector Name</th>
                            <th style="padding: 10px 12px;">Constituents</th>
                            <th style="padding: 10px 12px;">1-Week %</th>
                            <th style="padding: 10px 12px;">1-Month %</th>
                            <th style="padding: 10px 12px;">20 EMA Status</th>
                            <th style="padding: 10px 12px;">RS Score vs Nifty</th>
                            <th style="padding: 10px 12px;">Institutional Stance</th>
                        </tr>
                    </thead>
                    <tbody>
                        {sector_rows_html}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- GLOBAL MACRO MATRIX -->
        <div class="card">
            <h2 style="margin-top: 0; font-size: 20px; color: #38BDF8; display: flex; align-items: center; gap: 8px;">
                🌐 GLOBAL MACRO MATRIX
            </h2>
            <div style="display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px;">
                {macro_cards_html}
            </div>
        </div>

        <!-- AMIT DHAMIJA EXCEL SHEET SECTION TABLES -->
        <div class="card">
            <h2 style="margin-top: 0; font-size: 20px; color: #E2E8F0; display: flex; align-items: center; gap: 8px;">
                📋 COMPLETE PARTICIPANT OPEN INTEREST MATRIX
            </h2>
            <div style="color: #94A3B8; font-size: 13px; margin-bottom: 16px;">
                Detailed breakdown across Index Futures, Calls, Puts, Stock Futures, Stock Calls, and Stock Puts.
            </div>
            {sheet_sections_html}
        </div>

        <!-- FOOTER -->
        <div style="text-align: center; color: #64748B; font-size: 12px; padding: 16px 0;">
            Smart Money Institutional Prediction System • Built for 10-40 Day Positional & Swing Traders • Zero Paid Subscriptions
        </div>
    </div>
</body>
</html>
"""
        # Save HTML file
        out_html_path = os.path.join(self.output_dir, f"prediction_report_{date_str}.html")
        latest_html_path = os.path.join(self.output_dir, "latest_prediction_report.html")
        
        with open(out_html_path, "w", encoding="utf-8") as f:
            f.write(html)
        with open(latest_html_path, "w", encoding="utf-8") as f:
            f.write(html)
            
        # Also generate Markdown Report
        md = self._generate_markdown(calc_res, regime_res, sector_res, macro_res)
        out_md_path = os.path.join(self.output_dir, f"prediction_report_{date_str}.md")
        latest_md_path = os.path.join(self.output_dir, "latest_prediction_report.md")
        
        with open(out_md_path, "w", encoding="utf-8") as f:
            f.write(md)
        with open(latest_md_path, "w", encoding="utf-8") as f:
            f.write(md)
            
        return {
            "html_path": out_html_path,
            "latest_html_path": latest_html_path,
            "md_path": out_md_path,
            "latest_md_path": latest_md_path,
            "html_content": html
        }

    def _generate_markdown(self, calc_res, regime_res, sector_res, macro_res):
        display_date = calc_res["display_date"]
        cis = calc_res["cis_score"]
        fii_ratio = calc_res["fii_long_ratio"]
        fii_stk_3d = calc_res["fii_stk_flow_3d"]
        signal = regime_res["primary_signal"]
        
        md = f"""# 🏛️ Smart Money Institutional Prediction Report — {display_date}

**Primary Signal**: `{signal}`
**Market Regime**: `{regime_res['regime_name']}`
**Composite Score (CIS)**: `{cis:+.1f} / 10`
**FII Index Long Ratio**: `{fii_ratio}%`
**FII 3-Day Stock Futures Flow**: `{fii_stk_3d:+,} contracts`
**Capital Allocation**: `{regime_res['capital_allocation_pct']}% Stocks | {regime_res['cash_reserve_pct']}% Cash`

---

## 🎯 10-to-40 Day Swing Protocol
{regime_res['action_instructions']}

### Expected Chart Trajectory
{regime_res['trajectory']}

### Key Institutional Levels
- **Resistance 2**: `{regime_res['resistance_2']}`
- **Resistance 1**: `{regime_res['resistance_1']}`
- **Support 1**: `{regime_res['support_1']}`
- **SL Sweep Zone (Liquidity Hunt)**: `{regime_res['sweep_zone']}`
- **Support 2**: `{regime_res['support_2']}`

---

## 🔄 Sector Rotation Ranking
{sector_res.get('rotation_summary', '')}

| Sector Name | 1-Week % | 1-Month % | 20 EMA Status | RS Score | Institutional Stance |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""
        for s in sector_res.get("all_sectors", []):
            ema_str = "Above 20 EMA" if s["above_20_ema"] else "Below 20 EMA"
            md += f"| {s['name']} | {s['chg_1w']:+.2f}% | {s['chg_1m']:+.2f}% | {ema_str} | {s['rs_score']:+.2f} | {s['status']} |\n"
            
        md += "\n---\n\n## ⚡ Smart Money Traps Detected\n"
        for t in calc_res.get("traps", []):
            md += f"- **{t['title']}**: {t['description']}\n"
        if not calc_res.get("traps"):
            md += "- *No extreme retail trapping divergence detected today.*\n"
            
        return md
