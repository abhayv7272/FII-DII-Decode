"""v3-candidate participant-OI decoder (research candidate, not production default).

Status 2026-09-17: **candidate under forward validation.** It was fitted on the
2023-2024 development partition of the pinned 757-session archive, then scrolled
unchanged through 2025 validation and 2026 confirmation. Evidence package:
``reports/backtest_v3_candidate_2023-08_to_2026-09/`` and
``reports/v3_deep_dive/``. It must not be presented as validated until a
forward window not used in any fitting reproduces the gains.

Differences from locked v2 (everything else is unchanged and reuses the v2
implementation so the two decoders cannot silently diverge):

1. **Index futures carry 40% of each participant read** (v2: 20%); index calls
   and puts 30% each. The deep dive found aggregated option-flow reads add
   noise relative to futures at the daily horizon.
2. **Pro:FII = 60:40** (v2: 80% smart money split 2:1, i.e. ~53:27). The
   development grid picked 60/40 on a broad plateau (50/50-60/40 behave alike).
3. **Client tilt of -0.10** (v2: +0.20 contra). The small development-period
   premium for a weakly-Client-*aligned* fresh read; zeroing it costs <1pp.
   Documented as a data-fitted tilt, not a transcript claim.
4. **Forced-class threshold 0.00** (v2: +-0.10). With FLAT only ~21% of sessions
   the +-0.10 abstain band cost more exact-class hits than it saved. The
   0.00 boundary only affects the forced research class; actionability still
   abstains on weak composites and FII/Pro conflicts.

Selected on dev2023_24 from ~840 structural combinations; the chosen point sits
inside a stable family (perturbations move results <2pp). See
``reports/v3_deep_dive/REPORT.md`` for the full search, null controls, and the
negative results (levels, FLAT gating, weekly candidates remain unvalidated).
"""
from __future__ import annotations

import fiidii.decode as v2

METHOD_VERSION = "v3"

# Candidate constants (development-fitted; see module docstring)
V3_INSTRUMENT_WEIGHT = {
    "index_call": 0.30,
    "index_put": 0.30,
    "index_fut": 0.40,
}
V3_PARTICIPANT_WEIGHT = {
    "Pro": 0.60,
    "FII": 0.40,
    "Client": -0.10,
    "DII": 0.0,
}

# Forced-class boundary used by fiidii.predict._direction for v3.
CLASS_THRESHOLD = 0.0


def decode(oi_today, oi_prev=None, cash=None, option_levels=None, date_str=""):
    """Run the v2 machinery with the locked v3-candidate constants.

    The override is applied for the duration of one call and then restored,
    so concurrent v2 usage cannot observe the candidate parameters.
    """
    overrides = {
        "NEXT_DAY_INSTRUMENT_WEIGHT": V3_INSTRUMENT_WEIGHT,
        "NEXT_DAY_PARTICIPANT_WEIGHT": V3_PARTICIPANT_WEIGHT,
    }
    saved = {key: getattr(v2, key) for key in overrides}
    try:
        for key, value in overrides.items():
            setattr(v2, key, value)
        result = v2.decode(
            oi_today, oi_prev, cash=cash, option_levels=option_levels, date_str=date_str
        )
    finally:
        for key, value in saved.items():
            setattr(v2, key, value)
    result.method_version = METHOD_VERSION
    result.bias = _bias_label_v3(result.composite)
    return result


def _bias_label_v3(value: float) -> str:
    if value >= 0.45:
        return "STRONG BULLISH"
    if value > 0.0:
        return "BULLISH"
    if value <= -0.45:
        return "STRONG BEARISH"
    if value < 0.0:
        return "BEARISH"
    return "NEUTRAL"
