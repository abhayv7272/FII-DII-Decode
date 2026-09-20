from __future__ import annotations
import io
import json
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.data import download_ohlcv, load_csv, merge_context
from src.features import make_features, make_labels
from src.model import train_walk_forward, predict_latest, recursive_week_scenarios
from src.advanced_model import advanced_features, train_direction_model, predict_direction
from src.decoder import hard_decode
from src.data_hub import DataHub
from src.professional_report import create_report
from src.levels import technical_levels

st.set_page_config(page_title="NIFTY Decision Lab", page_icon="📈", layout="wide")
st.title("📈 NIFTY Decision Lab")
st.caption("Leakage-safe next-session probabilities, selective signals, levels and 5-session risk scenarios — research tool, not a profit guarantee.")

with st.sidebar:
    st.header("Configuration")
    source = st.radio("Price data", ["Yahoo Finance", "Upload CSV"])
    ticker = st.text_input("Ticker", "^NSEI", disabled=source != "Yahoo Finance")
    price_file = st.file_uploader("OHLCV CSV", type="csv", disabled=source != "Upload CSV")
    context_file = st.file_uploader("Optional dated context CSV", type="csv", help="Date + numeric columns such as FII/DII cash, VIX, PCR, Pro/FII net OI. Each row must contain only values known by that close.")
    chain_file = st.file_uploader("Optional current NIFTY option-chain CSV", type="csv", help="Supports common strike, CE/PE OI, change-OI, IV and volume column names.")
    flat_bps = st.slider("FLAT band (basis points)", 5, 75, 25, 5)
    precision_target = st.slider("Desired validation precision", .55, .90, .80, .01)
    run = st.button("Run leakage-safe analysis", type="primary", use_container_width=True)
    production_run = st.button("Run 9 PM resilient pipeline", use_container_width=True, help="Fetches all sources with fallback, validates quality, updates the specialist and writes a professional report.")

st.info("**80% mode ka matlab:** validation period par ≥80% precision milne par hi high-confidence calls select karna. Agar threshold validate nahi hota, system conservative default gate use karta hai. Future/live 80% guaranteed nahi hai.")

if production_run:
    try:
        with st.spinner("Fetching primary/fallback sources, validating and generating report..."):
            manifest=DataHub('auto').run();md_path,js_path,prod=create_report()
        st.success(f'Production report ready: {prod["decision"]} | data quality {prod["quality_score"]:.0%}')
    except Exception as e: st.exception(e)
latest_manifest=Path("data/hub/latest_manifest.json")
latest_reports=sorted(Path("reports/daily").glob("*_professional_report.md")) if Path("reports/daily").exists() else []
if latest_manifest.exists() and latest_reports:
    lm=json.loads(latest_manifest.read_text());latest_json=Path(str(latest_reports[-1]).replace('.md','.json'));live=json.loads(latest_json.read_text()) if latest_json.exists() else {}
    decision=live.get('decision','UNKNOWN');(st.warning if decision.startswith('WAIT') else st.success)(f'**Production-gated decision ({lm["session_date"]}): {decision}**')
    with st.expander(f'Latest 9 PM professional report — {lm["session_date"]}',expanded=production_run):
        st.markdown(latest_reports[-1].read_text())

if not run:
    st.markdown("""
### Workflow
1. 5–10 years completed daily OHLCV load करें.
2. Features use only data known at day **D close**; label is **D+1 close return**.
3. First 80% chronological data trains; last 20% unseen validation chooses the confidence gate.
4. Latest result becomes **UP / FLAT / DOWN** or **WAIT / NO TRADE**.
5. Weekly view is a volatility scenario band, not five fabricated candle predictions.

CSV columns: `Date, Open, High, Low, Close, Volume`. Optional context is joined by exact date; missing values are imputed inside training only.
""")
    st.stop()

try:
    with st.spinner("Loading, engineering features and training ensemble..."):
        if source == "Yahoo Finance":
            price = download_ohlcv(ticker, "10y")
        else:
            if price_file is None:
                st.error("Please upload an OHLCV CSV."); st.stop()
            price = load_csv(price_file)

        context = None
        if context_file is not None:
            raw_ctx = pd.read_csv(context_file)
            date_col = next((c for c in raw_ctx.columns if c.lower().strip() in {"date","datetime"}), None)
            if not date_col: raise ValueError("Context CSV requires Date column")
            raw_ctx[date_col] = pd.to_datetime(raw_ctx[date_col], errors="coerce")
            context = raw_ctx.dropna(subset=[date_col]).set_index(date_col)
        merged = merge_context(price, context)
        X = make_features(merged)
        y, next_returns = make_labels(price, flat_bps/10000)
        result = train_walk_forward(X, y, precision_target)
        latest_x = X.iloc[[-1]]
        pred = predict_latest(result, latest_x)
        direction_result = train_direction_model(price, .65)
        direction_x = advanced_features(price).iloc[[-1]]
        direction = predict_direction(direction_result, direction_x)
        levels = technical_levels(price)
        decoder_snapshots = pd.read_csv("data/eod_research_snapshots.csv") if Path("data/eod_research_snapshots.csv").exists() else None
        decoder_chain = pd.read_csv(chain_file) if chain_file is not None else None
        decoded = hard_decode(price, decoder_snapshots, decoder_chain)
except Exception as e:
    st.exception(e); st.stop()

m = result.metrics
dm = direction_result.metrics
c1,c2,c3,c4 = st.columns(4)
c1.metric("Next-session decision", direction["label"] if direction["actionable"] else "WAIT / NO TRADE")
c2.metric("Directional confidence", f'{direction["confidence"]:.1%}')
c3.metric("Untouched-test selected accuracy", "N/A" if pd.isna(dm["test_selected_accuracy"]) else f'{dm["test_selected_accuracy"]:.1%}')
c4.metric("Selected-signal coverage", f'{dm["test_coverage"]:.1%}', help="Fraction of untouched test days passing the frozen calibration gate")

st.subheader("Advanced binary direction model")
prob_df = pd.DataFrame({"Class": ["DOWN","UP"], "Probability": [direction["p_down"],direction["p_up"]]})
figp = go.Figure(go.Bar(x=prob_df.Class, y=prob_df.Probability, marker_color=["#ef4444","#22c55e"]))
figp.update_layout(yaxis_tickformat=".0%", height=330, margin=dict(l=10,r=10,t=20,b=10))
st.plotly_chart(figp, use_container_width=True)
st.caption(f'Ensemble agreement: {direction["model_agreement"]:.0%}. Frozen action gate: {direction_result.gate:.0%}. Separate three-class range model context: {pred["label"]} ({pred["confidence"]:.1%}).')

if direction["actionable"]:
    st.success(f'Conditional direction: **{direction["label"]}**. Trade only after level/candle confirmation; model confidence is not probability of profit.')
else:
    st.warning(f'Directional gate {direction_result.gate:.0%} not met → **WAIT / NO TRADE**.')

exec_report=Path("reports/execution_audit.json")
if exec_report.exists():
    ex=json.loads(exec_report.read_text()); es=ex["summary"];el=ex["latest"]
    st.subheader("Executable next-open → next-close audit")
    e1,e2,e3,e4=st.columns(4)
    e1.metric("Later-test accuracy",f'{es["all_test_accuracy"]:.1%}')
    e2.metric("Balanced accuracy",f'{es["all_test_balanced_accuracy"]:.1%}')
    e3.metric("Meta-selected signals",es["selected_test_signals"])
    e4.metric("Latest action","TRADE" if el["actionable"] else "WAIT")
    st.caption("Strict 60% base-train → 10% meta-train → 10% gate-calibration → 20% later-test. No gate met the minimum precision/sample rule, so transaction-cost P&L correctly remains zero.")

registry_path=Path("reports/model_registry.json")
if registry_path.exists():
    registry=json.loads(registry_path.read_text())
    with st.expander("Champion–challenger model selection",expanded=True):
        research=registry.get("research_champion");production=registry.get("production_champion")
        if research:
            msg=f'Research candidate: **{research["name"]}** — all-day {research["accuracy"]:.2%}, balanced {research["balanced_accuracy"]:.2%}, selected {research["selected_accuracy"]:.2%} on {research["selected_signals"]} signals.'
            (st.error if str(research.get('status','')).startswith(('REJECTED','REVOKED')) else st.success)(msg)
            st.warning(research["note"])
        if production: st.info(f'Production champion retained pending forward proof: **{production["name"]}** — {production["accuracy"]:.2%} across {production["later_test_sessions"]} sessions.')
        rejected=registry.get("rejected",registry.get("challengers",[]));st.dataframe(pd.DataFrame(rejected),use_container_width=True,hide_index=True)
        st.caption(registry["selection_rule"])

derivative_report=Path("reports/derivative_specialist.json")
if derivative_report.exists():
    dr=json.loads(derivative_report.read_text());dh=dr["holdout"];dl=dr.get("latest",{})
    st.subheader("EOD option–futures specialist")
    q1,q2,q3,q4=st.columns(4)
    q1.metric("Later-test accuracy",f'{dh["accuracy"]:.2%}')
    q2.metric("Balanced accuracy",f'{dh["balanced_accuracy"]:.2%}')
    q3.metric("Selected accuracy", "N/A" if dh["selected_accuracy"] is None else f'{dh["selected_accuracy"]:.2%}')
    q4.metric("Selected sample",f'{dh["signals"]}/{dh["sessions"]}')
    if dl:
        st.markdown(f'Latest specialist: **{dl["direction"]}**, confidence **{dl["confidence"]:.2%}**, frozen gate **{dl["gate"]:.0%}** → **{"ACTIONABLE" if dl["actionable"] else "WAIT"}**')
    st.caption("EOD strike-wise option/futures data; not 10/15-minute historical chain. Selected accuracy is provisional because only 12 later signals exist.")

gap_report=Path("reports/gap_audit.json")
if gap_report.exists():
    gr=json.loads(gap_report.read_text())
    with st.expander("Separate overnight gap audit"):
        st.write(gr)
        st.warning("Gap accuracy is approximately equal to the UP base rate; this does not demonstrate a usable edge and is not promoted as a trade signal.")

st.subheader("Hard Decoder: positioning, psychology proxies and traps")
h1,h2,h3=st.columns(3)
h1.metric("Decoded state",decoded["decision"])
h2.metric("Structural score",f'{decoded["structural_score"]:+.1f}',help="-100 bearish to +100 bullish; not a probability")
h3.metric("Evidence confidence",f'{decoded["evidence_confidence"]:.1f}%')
for s in decoded["signals"]:
    st.markdown(f"- **{s['name']}** — score `{s['score']:+.2f}`, reliability `{s['reliability']:.0%}`: {s['evidence']}")
st.caption(decoded["warning"])
with st.expander("Ranked support, resistance and magnet levels"):
    st.dataframe(pd.DataFrame(decoded["levels"]),use_container_width=True,hide_index=True)

left,right=st.columns([1.5,1])
with left:
    st.subheader("Price structure")
    chart=price.tail(180)
    fig=go.Figure(go.Candlestick(x=chart.index,open=chart.Open,high=chart.High,low=chart.Low,close=chart.Close,name="NIFTY"))
    for name,color in [("support_1","#22c55e"),("resistance_1","#ef4444"),("pivot","#f59e0b")]:
        fig.add_hline(y=levels[name],line_dash="dot",line_color=color,annotation_text=name)
    fig.update_layout(height=470,xaxis_rangeslider_visible=False,margin=dict(l=10,r=10,t=20,b=10))
    st.plotly_chart(fig,use_container_width=True)
with right:
    st.subheader("Conditional playbook")
    st.markdown(f"""
**Pivot:** {levels['pivot']:,.2f}  
**Support S1:** {levels['support_1']:,.2f}  
**Resistance R1:** {levels['resistance_1']:,.2f}  
**20D support:** {levels['support_20d']:,.2f}  
**20D resistance:** {levels['resistance_20d']:,.2f}  
**ATR(14):** {levels['atr14_points']:,.2f} points

- **Bull path:** support hold → pivot reclaim → R1 break and retest hold.
- **Bear path:** resistance reject → pivot/S1 breakdown → failed reclaim.
- **Trap:** level sweep without a confirming close = no entry.
- **Risk gate:** abnormal gap, FII/Pro conflict, missing context, or poor R:R → WAIT.
""")

st.subheader("Next 5 sessions (Mon–Fri style risk map)")
atr_pct=levels["atr14_points"]/levels["previous_close"]
week=recursive_week_scenarios(levels["previous_close"],pred["probabilities"],atr_pct,5)
# Map to actual weekdays, excluding weekends; exchange holidays require a supplied calendar.
future_dates=pd.bdate_range(price.index[-1]+pd.Timedelta(days=1),periods=5)
week.insert(0,"date",future_dates.date)
st.dataframe(week.style.format({"expected_center":"{:,.2f}","lower_risk_band":"{:,.2f}","upper_risk_band":"{:,.2f}"}),use_container_width=True,hide_index=True)
st.caption("Bands widen by √time using ATR. They are scenario/risk zones, not guaranteed daily closes. NSE holidays are not automatically removed.")

st.subheader("Strict train → calibration → untouched-test report")
a,b,c,d=st.columns(4)
a.metric("Untouched test sessions",dm["test_sessions"])
b.metric("All-day directional accuracy",f'{dm["test_all_accuracy"]:.1%}')
c.metric("Selected accuracy", "N/A" if pd.isna(dm["test_selected_accuracy"]) else f'{dm["test_selected_accuracy"]:.1%}')
d.metric("Selected signals",dm["test_selected_signals"])
st.dataframe(direction_result.test_predictions.tail(100),use_container_width=True)
st.caption("The action threshold is chosen on the middle calibration block, then evaluated once on the later test block. Low coverage is intentionally visible.")

report = pd.DataFrame([{
    "as_of": price.index[-1], "decision": direction["label"] if direction["actionable"] else "WAIT",
    "confidence": direction["confidence"], "p_up":direction["p_up"], "p_down":direction["p_down"],
    "test_accuracy_all":dm["test_all_accuracy"],"test_accuracy_selected":dm["test_selected_accuracy"],
    "test_coverage":dm["test_coverage"], "direction_gate":direction_result.gate,
    **levels
}])
st.download_button("Download decision snapshot CSV",report.to_csv(index=False).encode(),"decision_snapshot.csv","text/csv")

st.subheader("Free NSE forward-data programme")
snapshot_path="data/eod_research_snapshots.csv"
try:
    snapshots=pd.read_csv(snapshot_path)
    valid=snapshots[snapshots["quality_ok"].astype(str).str.lower().eq("true")]
    s1,s2,s3=st.columns(3)
    s1.metric("Quality-approved EOD sessions",len(valid))
    s2.metric("First frozen study",f"{len(valid)}/200")
    s3.metric("Promotion check",f"{len(valid)}/260")
    if not valid.empty:
        last=valid.iloc[-1]
        st.markdown(f"**Latest institutional context ({last['session_date']}):** FII index-futures net `{last.get('fii_index_futures_net',float('nan')):,.0f}`, Pro net `{last.get('pro_index_futures_net',float('nan')):,.0f}`, FII cash `{last.get('fii_cash_net_cr',float('nan')):,.2f} Cr`, DII cash `{last.get('dii_cash_net_cr',float('nan')):,.2f} Cr`, India VIX `{last.get('india_vix_close',float('nan')):.2f}`.")
        st.dataframe(valid.tail(10),use_container_width=True,hide_index=True)
    st.caption("Collected context is displayed immediately, but it is not trained into the ML model until enough independent sessions exist. This prevents a one-row overfit.")
except FileNotFoundError:
    st.info("No forward EOD snapshot yet. Run: python -m src.collector eod --date YYYY-MM-DD")

feature_store_path=Path("data/model_feature_store.csv")
if feature_store_path.exists():
    fs=pd.read_csv(feature_store_path); latest=fs.iloc[-1]
    readiness={
      "Participant OI/volume":pd.notna(latest.get("fii_index_futures_net")),
      "FII/DII cash":pd.notna(latest.get("fii_cash_net_cr")),
      "India VIX":pd.notna(latest.get("india_vix_close")),
      "Sector breadth":pd.notna(latest.get("india_sector_mean_return")),
      "Heavyweight breadth":pd.notna(latest.get("india_heavyweight_mean_return")),
      "Prior global session":pd.notna(latest.get("prior_global_mean_return")),
      "Asia context":pd.notna(latest.get("asia_mean_return")),
      "Intraday option migration":float(latest.get("option_captures",0) or 0)>=2,
      "Pre-open breadth":pd.notna(latest.get("preopen_mean_pct"))}
    ready=sum(readiness.values()); st.progress(ready/len(readiness),text=f"Context readiness: {ready}/{len(readiness)} layers")
    st.dataframe(pd.DataFrame([{"Layer":k,"Ready":v} for k,v in readiness.items()]),use_container_width=True,hide_index=True)
    st.caption(f"Feature store: {len(fs)} independent session(s), {len(fs.columns)-1} stored fields. Option-wall migration requires at least two intraday captures in the same session.")

with st.expander("Important limitations"):  
    st.markdown("""
- This is a research/decision-support system, not SEBI-registered investment advice.
- Accuracy varies by regime. Transaction costs, option premium decay, spread and slippage are not modeled.
- A single chronological holdout is useful but walk-forward live paper trading is required before capital use.
- FII/DII, option chain and VIX improve context only when timestamped and leakage-free; no signal guarantees profit.
- Weekly output deliberately avoids recursively pretending to know future OHLC candles.
""")
