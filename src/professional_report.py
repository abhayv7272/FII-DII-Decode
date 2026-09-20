from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .levels import technical_levels
from .model import recursive_week_scenarios

PROJECT = Path(__file__).resolve().parents[1]


def research_promotion_gate(bt: dict) -> bool:
    cost10 = bt.get("costs", {}).get("10", {})
    return bool(
        bt.get("sessions", 0) >= 80
        and bt.get("accuracy", 0) >= 0.58
        and bt.get("signals", 0) >= 30
        and (bt.get("selected_accuracy") or 0) >= 0.65
        and (cost10.get("net_return") or 0) > 0
    )


def _candidate_path(record: dict, key: str) -> Path | None:
    value = record.get(key)
    if not value:
        return None
    path = PROJECT / value
    return path if path.exists() else None


def _price_from_manifest(manifest: dict) -> pd.DataFrame:
    record = next(x for x in manifest["results"] if x["dataset"] == "nifty_price" and x["status"] in {"fresh", "cached"})
    candidates = [
        _candidate_path(record, "path"),
        _candidate_path(record, "cache_path"),
        PROJECT / "data" / "hub" / "last_good" / "nifty_price.csv",
    ]
    path = next((p for p in candidates if p and p.exists()), None)
    if path is None:
        raise FileNotFoundError("No persisted NIFTY price evidence found for latest manifest")
    data = pd.read_csv(path)
    data["Date"] = pd.to_datetime(data.Date, errors="coerce")
    data = data.dropna(subset=["Date"]).sort_values("Date")
    # Compact cache may contain a full history. Always re-truncate at manifest session
    # before computing levels/model features so a committed manifest never leaks later bars.
    data = data[data["Date"].dt.normalize() <= pd.Timestamp(manifest["session_date"])]
    if data.empty or data["Date"].max().date() != pd.Timestamp(manifest["session_date"]).date():
        raise ValueError(f"Persisted price evidence does not end at session {manifest['session_date']}")
    return data.set_index("Date")[["Open", "High", "Low", "Close", "Volume"]]


def specialist_latest(price: pd.DataFrame) -> dict:
    from optimize_derivative_specialists import derivative_features, models, participant_features
    from .advanced_model import advanced_features

    registry = json.loads((PROJECT / "reports" / "derivative_specialist.json").read_text(encoding="utf-8"))
    opt = pd.read_csv(PROJECT / "data" / "historical_option_features.csv")
    fut = pd.read_csv(PROJECT / "data" / "historical_futures_features.csv")
    der = derivative_features(opt, fut)
    px = advanced_features(price)
    part = participant_features(PROJECT / "data" / "historical_participant_oi.csv")
    feature_set = registry.get("best", {}).get("features", "option_futures")
    sets = {
        "price": px,
        "option_futures": der,
        "participant": part,
        "derivatives_participant": der.join(part, how="inner"),
        "price_plus_derivatives": px.join(der, how="inner"),
        "full": px.join(der, how="inner").join(part, how="inner"),
    }
    if feature_set not in sets:
        raise ValueError(f"Unknown frozen feature set: {feature_set}")
    X = sets[feature_set].sort_index()
    X = X[X.index <= pd.Timestamp(price.index.max()).normalize()]
    missing = [col for col in registry["selected_columns"] if col not in X]
    if missing:
        raise ValueError(f"Specialist schema drift; missing {len(missing)} frozen features: {missing[:8]}")
    cols = registry["selected_columns"]
    ret = price.Close.shift(-1) / price.Open.shift(-1) - 1
    y = (ret > 0).astype(float).reindex(X.index)
    y[ret.reindex(X.index).isna()] = np.nan
    labeled = y.notna()
    if labeled.sum() < 250:
        raise ValueError(f"Insufficient aligned specialist training sessions: {int(labeled.sum())}")
    model = models()["logit"]()
    model.fit(X.loc[labeled, cols], y[labeled].astype(int))
    p_up = float(model.predict_proba(X.iloc[[-1]][cols])[0, 1])
    gate = float(registry["frozen_gate"]["gate"])
    bt = registry["holdout"]
    research_approved = research_promotion_gate(bt)
    confidence = max(p_up, 1 - p_up)
    confidence_pass = confidence >= gate
    return {
        "as_of": str(X.index[-1].date()),
        "direction": "UP" if p_up >= 0.5 else "DOWN",
        "p_up": p_up,
        "p_down": 1 - p_up,
        "confidence": confidence,
        "gate": gate,
        "confidence_pass": confidence_pass,
        "research_approved": research_approved,
        "model_pass": bool(confidence_pass and research_approved),
        "backtest": bt,
        "error": None,
    }


def _source_table(manifest: dict) -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {
                "Dataset": record["dataset"],
                "Selected source": record["source"],
                "Status": record["status"],
                "As-of": record.get("as_of"),
                "Rows": record["rows"],
                "Stale days": record.get("stale_days"),
                "Error": record.get("error"),
            }
            for record in manifest["results"]
        ]
    )
    return df.fillna("")


def _fmt_pct(value, default: str = "N/A") -> str:
    return default if value is None or pd.isna(value) else f"{float(value):.2%}"


def create_report(manifest_path: str | Path | None = None):
    from .risk_gates import event_risk

    path = Path(manifest_path) if manifest_path else PROJECT / "data" / "hub" / "latest_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    price = _price_from_manifest(manifest)
    try:
        pred = specialist_latest(price)
    except Exception as exc:  # noqa: BLE001 - report must fail closed with explicit reason
        registry = json.loads((PROJECT / "reports" / "derivative_specialist.json").read_text(encoding="utf-8"))
        pred = {
            "as_of": None,
            "direction": "UNKNOWN",
            "p_up": 0.5,
            "p_down": 0.5,
            "confidence": 0.0,
            "gate": float(registry.get("frozen_gate", {}).get("gate", 1.0)),
            "confidence_pass": False,
            "research_approved": False,
            "model_pass": False,
            "backtest": registry.get("holdout", {}),
            "error": str(exc),
        }

    levels = technical_levels(price)
    last = float(price.Close.iloc[-1])
    sma200 = float(price.Close.rolling(200).mean().iloc[-1])
    atrp = levels["atr14_points"] / last
    event = event_risk(manifest["session_date"])
    date_match = pred["as_of"] == manifest["session_date"]
    allowed = bool(manifest["prediction_allowed"] and pred["model_pass"] and date_match and not event["blocked"])
    decision = pred["direction"] if allowed else "WAIT / NO TRADE"

    critical_names = ["nifty_price", "nifty_options_eod", "nifty_futures_eod"]
    critical_fresh = {
        name: any(
            record["dataset"] == name and record["status"] == "fresh" and record.get("as_of") == manifest["session_date"]
            for record in manifest["results"]
        )
        for name in critical_names
    }
    critical_fresh_text = ", ".join(f"{name}={value}" for name, value in critical_fresh.items())
    data_gate = {
        "passed": bool(manifest["prediction_allowed"]),
        "quality_score": manifest["quality_score"],
        "critical_fresh_date_matched": critical_fresh,
        "history_update_ok": bool(manifest.get("history_update_ok", True)),
    }

    if allowed and pred["direction"] == "UP":
        trade = "LONG BIAS — only after resistance breakout and successful retest"
        swing = "Swing long can be considered only above the trigger with defined stop."
    elif allowed:
        trade = "SHORT BIAS — only after support breakdown and failed reclaim"
        swing = "Swing short can be considered only below the trigger with defined stop."
    else:
        trade = "NO DIRECTIONAL POSITION"
        swing = "Do not initiate a new swing position until the confidence/data gate and price trigger both pass."
    invest = (
        "Long-term trend positive; staggered investment may be researched, but this next-day model is not a fundamental valuation model."
        if last > sma200
        else "Fresh long-term investment should be deferred or evaluated fundamentally; index is below its 200-day trend."
    )
    dates = pd.bdate_range(price.index[-1] + pd.Timedelta(days=1), periods=5)
    week_probs = {"UP": pred["p_up"], "DOWN": pred["p_down"], "FLAT": 0} if allowed else {"UP": 0.5, "DOWN": 0.5, "FLAT": 0}
    week = recursive_week_scenarios(last, week_probs, atrp, 5)
    week.insert(0, "date", [str(day.date()) for day in dates])
    sources = _source_table(manifest)
    failed = sources[sources.Status.eq("failed")].Dataset.tolist()
    cached = sources[sources.Status.eq("cached")].Dataset.tolist()
    backtest = pred.get("backtest", {})

    obj = {
        "session_date": manifest["session_date"],
        "decision_time_ist": manifest["decision_ist"],
        "decision": decision,
        "quality_score": manifest["quality_score"],
        "data_gate": data_gate,
        "prediction": pred,
        "prediction_date_matches_session": date_match,
        "event_risk": event,
        "levels": levels,
        "trade_stance": trade,
        "swing_stance": swing,
        "investment_context": invest,
        "weekly_scenarios": week.to_dict("records"),
        "failed_sources": failed,
        "cached_sources": cached,
    }
    lines = [
        f"# NIFTY Professional Decision Report — {manifest['session_date']}",
        "",
        f"**Generated:** {manifest['decision_ist']}",
        f"**Data quality:** {manifest['quality_score']:.0%}",
        f"**Data gate:** **{'PASS' if data_gate['passed'] else 'FAIL-CLOSED'}**",
        f"**Final decision:** **{decision}**",
        "",
        "## Executive view",
        "",
        f"- Specialist direction: **{pred['direction']}**",
        f"- UP/DOWN probability: **{pred['p_up']:.2%} / {pred['p_down']:.2%}**",
        f"- Model confidence: **{pred['confidence']:.2%}**; frozen gate: **{pred['gate']:.0%}**",
        f"- Prediction/session match: **{date_match}**",
        f"- Critical fresh/date-matched data: **{critical_fresh_text}**",
        f"- Compact history update ok: **{data_gate['history_update_ok']}**",
        f"- Trading stance: **{trade}**",
        f"- Swing stance: {swing}",
        f"- Investment context: {invest}",
        "",
        "## Key levels",
        "",
        f"- Resistance trigger: **{levels['resistance_1']:,.2f}**",
        f"- Pivot: **{levels['pivot']:,.2f}**",
        f"- Support trigger: **{levels['support_1']:,.2f}**",
        f"- 20-day support/resistance: **{levels['support_20d']:,.2f} / {levels['resistance_20d']:,.2f}**",
        f"- ATR(14): **{levels['atr14_points']:,.2f} points**",
        "",
        "## Conditional playbook",
        "",
        f"### Bull path\nSupport/pivot hold → close above {levels['resistance_1']:,.2f} → retest holds → only then long continuation is valid.",
        f"### Bear path\nResistance rejection → close below {levels['support_1']:,.2f} → failed reclaim → only then short continuation is valid.",
        "### Trap rule\nA wick/sweep alone is not entry confirmation. Wait for a completed candle and follow-through.",
        "",
        "## Monday–Friday risk map",
        "",
        week.to_markdown(index=False, floatfmt=".2f"),
        "",
        "## What not to do",
        "",
        "- Do not trade below the confidence or data-quality gate.",
        "- Do not chase an abnormal opening gap; wait for a new range.",
        "- Do not treat max pain/OI wall as a guaranteed target.",
        "- Do not average a losing leveraged position.",
        "- Do not use this next-day model as the sole basis for long-term investment.",
        "",
        "## Data-source health",
        "",
        sources.to_markdown(index=False),
        "",
        "## Model evidence",
        "",
        f"- Later research test: {_fmt_pct(backtest.get('accuracy'))} accuracy across {backtest.get('sessions', 'N/A')} sessions.",
        f"- Selected research sample: {backtest.get('signals', 'N/A')} signals, {_fmt_pct(backtest.get('selected_accuracy'))} observed accuracy; this sample is provisional.",
        "- Current report automatically becomes WAIT if critical data, compact-history, date, event, confidence or research-promotion gates fail.",
        "",
        "## Risk notice",
        "",
        "Research/decision-support only; not personalized investment advice. Futures and options can cause rapid losses. Verify exchange data, liquidity, costs and your risk capacity before any trade.",
    ]
    if pred.get("error"):
        lines.insert(7, f"**MODEL ERROR — fail-closed:** {pred['error']}")
    if not data_gate["passed"]:
        lines.insert(7, "**DATA GATE FAIL-CLOSED:** critical price/options/futures were not all fresh/date-matched, compact history failed, or overall quality was below threshold.")
    if not pred.get("research_approved", False):
        lines.insert(7, "**Diagnostic only:** raw class probability is not a calibrated profit probability and is excluded from the weekly centre.")
        lines.insert(7, "**RESEARCH PROMOTION GATE FAILED:** corrected holdout/cost metrics do not support a live directional trade.")
    if not date_match:
        lines.insert(7, f"**DATE MISMATCH — fail-closed:** specialist as-of {pred.get('as_of')} vs session {manifest['session_date']}")
    if event["status"] != "CLEAR":
        lines.insert(7, f"**Event-calendar status:** {event['status']}" + (" — trade blocked" if event["blocked"] else " — verified calendar unavailable; check manually"))
    executive_idx = lines.index("## Executive view")
    if executive_idx > 0 and lines[executive_idx - 1] != "":
        lines.insert(executive_idx, "")

    from .data_hub import _atomic_text

    out = PROJECT / "reports" / "daily"
    out.mkdir(parents=True, exist_ok=True)
    md = out / f"{manifest['session_date']}_professional_report.md"
    js = out / f"{manifest['session_date']}_professional_report.json"
    _atomic_text(md, "\n".join(lines))
    _atomic_text(js, json.dumps(obj, indent=2, default=float))
    return md, js, obj
