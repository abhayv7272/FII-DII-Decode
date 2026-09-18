from __future__ import annotations

import pandas as pd

from india_vix_regime_audit import (
    MIN_CONFIRMATION_SIGNALS,
    MIN_DEVELOPMENT_SIGNALS,
    MIN_VALIDATION_SIGNALS,
    RULE_ORDER,
    assign_regimes,
    fit_policy,
    gate_rules,
    prepare_observations,
)


def test_prepare_observations_uses_signal_session_vix_not_target_session():
    predictions = pd.DataFrame([
        {
            "signal_date": "2024-12-30", "target_date": "2024-12-31",
            "actual_return_pct": -0.50, "predicted_class": "DOWN",
            "actual_class": "DOWN", "exact_hit": True,
        },
    ])
    vix = pd.DataFrame([
        {"date": "2024-12-30", "close": 12.0},
        # This would be a future observation and must not be joined instead.
        {"date": "2024-12-31", "close": 99.0},
    ])

    observations = prepare_observations(predictions, vix)

    assert observations["vix_close"].tolist() == [12.0]
    assert observations["abs_return_pct"].tolist() == [0.5]
    assert observations["period"].tolist() == ["development"]


def test_fit_policy_uses_development_rows_only():
    development = pd.DataFrame({
        "period": ["development"] * 100,
        "vix_close": list(range(1, 101)),
        "abs_return_pct": [value / 100 for value in range(1, 101)],
        "target_date": pd.date_range("2024-01-01", periods=100, freq="D"),
    })
    future = pd.DataFrame({
        "period": ["validation_2025", "confirmation_2026"],
        "vix_close": [10000.0, 20000.0],
        "abs_return_pct": [100.0, 200.0],
        "target_date": pd.to_datetime(["2025-01-02", "2026-01-02"]),
    })

    policy = fit_policy(pd.concat([development, future], ignore_index=True))
    labelled = assign_regimes(pd.concat([development, future], ignore_index=True), policy)

    assert policy.train_rows == 100
    assert policy.quiet_vix_close_lte == 25.75
    assert policy.elevated_vix_close_gte == 75.25
    assert policy.typical_abs_return_pct == 0.505
    assert labelled.iloc[-1]["vix_regime"] == "ELEVATED"


def test_gate_requires_development_validation_and_confirmation_lift():
    rows = []
    for rule in RULE_ORDER:
        for period, minimum in (
            ("development", MIN_DEVELOPMENT_SIGNALS),
            ("validation_2025", MIN_VALIDATION_SIGNALS),
            ("confirmation_2026", MIN_CONFIRMATION_SIGNALS),
        ):
            # ELEVATED fails only the in-sample development lift. QUIET passes all.
            lift = 2.0 if rule == "ELEVATED_RANGE" and period == "development" else 6.0
            rows.append({"rule": rule, "period": period, "calls": minimum, "lift_pct_points": lift})

    gates = gate_rules(pd.DataFrame(rows)).set_index("rule")

    assert not bool(gates.loc["ELEVATED_RANGE", "development_lift_ok"])
    assert bool(gates.loc["ELEVATED_RANGE", "validation_lift_ok"])
    assert bool(gates.loc["ELEVATED_RANGE", "confirmation_lift_ok"])
    assert gates.loc["ELEVATED_RANGE", "state"] == "NOT_PROMOTED"
    assert gates.loc["QUIET_RANGE", "state"] == "CONTEXT_RULE_CANDIDATE"
