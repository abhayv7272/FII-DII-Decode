import os
import sys
import json
from fetcher import FreeDataFetcher
from calculator import InstitutionalCalculator
from regime_engine import RegimeEngine
from sector_rotation import SectorRotationAnalyzer
from report_generator import ReportGenerator
from email_sender import EmailSender

def run_daily_prediction():
    print("="*80)
    print("🏛️  SMART MONEY INSTITUTIONAL PREDICTION ENGINE (PRO EDITION)")
    print("="*80)
    
    # 1. Fetch Latest Data
    print("\n[1/5] Fetching Official 100% Free Data...")
    fetcher = FreeDataFetcher()
    latest_oi = fetcher.fetch_latest_participant_oi()
    print(f"      • Latest Participant OI Date: {latest_oi['display_date']} ({latest_oi['status']})")
    
    macro_data = fetcher.fetch_global_macro()
    nifty_px = macro_data.get("nifty_50", {}).get("current", 24200.0)
    print(f"      • Nifty Current Spot: {nifty_px:,.2f} | Brent Crude: ${macro_data.get('brent_crude', {}).get('current', 0)}/bbl")
    
    raw_sectors = fetcher.fetch_sector_strength()
    print(f"      • Sector Rotation Data: Fetched {len(raw_sectors)} key sectors.")
    
    # 2. Multi-day History & Calculation
    print("\n[2/5] Calculating Amit Dhamija Multi-Day Sheets & Institutional Flow...")
    hist_df = fetcher.fetch_recent_history(days_count=10)
    calculator = InstitutionalCalculator(hist_df)
    calc_res = calculator.calculate_latest_sheet()
    
    cis = calc_res["cis_score"]
    fii_ratio = calc_res["fii_long_ratio"]
    fii_stk_3d = calc_res["fii_stk_flow_3d"]
    print(f"      • FII Long Ratio: {fii_ratio}% | FII 3-Day Stock Flow: {fii_stk_3d:+,} contracts")
    print(f"      • Composite Institutional Score (CIS): {cis:+.1f} / 10")
    
    # 3. Regime & Action Assignment
    print("\n[3/5] Assigning Market Regime & Capital Allocation...")
    regime_engine = RegimeEngine()
    regime_res = regime_engine.evaluate_regime_and_action(calc_res, macro_data, nifty_px)
    
    print(f"      • Market Regime: {regime_res['regime_name']}")
    print(f"      • Primary Signal: {regime_res['primary_signal']}")
    print(f"      • Capital Exposure: {regime_res['capital_allocation_pct']}% Stocks | {regime_res['cash_reserve_pct']}% Cash")
    
    # 4. Sector Rotation Analysis
    print("\n[4/5] Analyzing Institutional Sector Leadership...")
    sector_analyzer = SectorRotationAnalyzer()
    sector_res = sector_analyzer.analyze_sectors(raw_sectors)
    top_leaders = [s["name"] for s in sector_res.get("top_leaders", [])]
    print(f"      • Top Outperforming Sectors: {', '.join(top_leaders) if top_leaders else 'Broad-based'}")
    
    # 5. Generate Visual Reports & Send Email
    print("\n[5/5] Generating Ultra-Stunning HTML Dashboard & Dispatching...")
    report_gen = ReportGenerator()
    rep_res = report_gen.generate_html_report(calc_res, regime_res, sector_res, macro_data)
    print(f"      • HTML Dashboard saved to: {rep_res['html_path']}")
    print(f"      • Latest Dashboard saved to: {rep_res['latest_html_path']}")
    print(f"      • Markdown Report saved to: {rep_res['md_path']}")
    
    # Send Email
    email_sender = EmailSender(recipient_email=fetcher.config.get("recipient_email", "abhayv7272@gmail.com"))
    subject = f"🏛️ Smart Money Prediction ({calc_res['display_date']}): {regime_res['primary_signal']} | CIS {cis:+.1f} | Regime {regime_res['regime_id']}"
    email_sender.send_report(subject, rep_res["html_content"])
    
    print("\n" + "="*80)
    print("✅ PREDICTION COMPLETED SUCCESSFULLY!")
    print(f"   Signal        : {regime_res['primary_signal']}")
    print(f"   Allocation    : {regime_res['capital_allocation_pct']}% Stocks / {regime_res['cash_reserve_pct']}% Cash")
    print(f"   Target Swings : 10 to 40 Days Holding in Leading Stage-2 Sectors")
    print("="*80 + "\n")
    
    return rep_res

if __name__ == "__main__":
    # Ensure current directory is in path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    run_daily_prediction()
