# FII/DII Decode methodology — v2

> **Status:** experimental research, not investment advice. The locked v2 replay
> reached 37.91% exact UP/FLAT/DOWN accuracy on 757 sessions, below the 42.14%
> majority-class baseline. Its next-open-to-close sign result remained
> approximately chance. Nothing here is a validated standalone trading signal.

This document describes the production v2 implementation. The frozen historical
implementation is `src/fiidii/legacy_v1.py`; it remains available through
`--decoder-version v1` so the published v1 audit is exactly reproducible.

The page/timestamp evidence, omitted conditions, contradictions, and explicit v1
mapping errors are in [transcript-audit-v2.md](transcript-audit-v2.md).

## 1. Scope of the model

The decoder uses two consecutive daily Participant-OI reports to produce:

1. a **forced next-session OI research class** for historical comparison;
2. a separate **actionability state** that may abstain or require confirmation;
3. an **as-on-date positional carry context**, not a validated weekly forecast;
4. transparent per-participant and per-instrument diagnostics.

It does not know the opening gap, intraday price path, news arriving after the OI
report, or option-chain levels unless those inputs are separately supplied. Even
when live confirmation data is supplied, it does not silently modify the locked
OI-only class that was historically tested.

The public Participant-OI file aggregates index families and expiries. Therefore
“NIFTY OI lean” means an association between aggregate index participant
positioning and the next NIFTY session; it is not a pure NIFTY-expiry position
reconstruction.

## 2. Participant hierarchy and horizons

| Participant | V2 interpretation | Daily weight | Positional-context weight |
|---|---|---:|---:|
| Pro | Primary one-to-two-session participant | 53.33% | 25% |
| FII | Secondary daily participant; primary multi-session participant | 26.67% | 60% |
| Client/Retail | Minority contrary/crowding condition | 20% | 15% |
| DII | Reported, but F&O direction ignored because of arbitrage/hedging contamination | 0% | 0% |

The daily values implement 80% Smart Money and 20% contra-Client, with Pro:FII
set to 2:1 inside Smart Money. These exact percentages are fixed engineering
translations of the transcript's hierarchy, not percentages stated by the
speaker.

Client scores are inverted before blending. This is a crowding heuristic, not a
claim that every Retail position must lose on the following day.

## 3. Fresh-flow decomposition

For each participant and instrument, let:

- `ΔL = long_today - long_previous`
- `ΔS = short_today - short_previous`

V2 keeps the four economically different actions separate:

```text
fresh_long = max( ΔL, 0)
long_unwind = max(-ΔL, 0)
fresh_short = max( ΔS, 0)
short_cover = max(-ΔS, 0)
```

For futures and calls, quality-adjusted bullish pressure is:

```text
P = fresh_long + 0.5*short_cover - fresh_short - 0.5*long_unwind
```

For puts, the sign is reversed: put buying is bearish and put writing is
bullish. For Client/Retail, the resulting market-direction sign is then inverted
for the contrary read.

Fresh additions receive full weight while closures receive half weight. The
transcript explicitly distinguishes stronger fresh positioning from weaker
covering/unwinding; `0.5` is the declared implementation choice for that
qualitative priority.

If no prior report is available, fresh pressure is zero rather than silently
using carry as if it were today's action.

## 4. Relative-OI normalisation

V1 used fixed contract denominators. V2 instead computes one-sided current market
OI for each instrument:

```text
market_oi = max(TOTAL long, TOTAL short)
relative_flow = P / market_oi
fresh_score = tanh(relative_flow / flow_scale)
```

If a `TOTAL` row is absent, totals are reconstructed by summing participant rows.
The fixed flow scales are:

- index instruments: 2.5% of current market OI;
- stock instruments: 1.5% of current market OI.

The result lies in `[-1, +1]`. Positive always means bullish for the market after
the put and Client sign adjustments; negative means bearish.

This removes hard-coded absolute contract thresholds, but does not solve changes
in contract size, expiry mix, or index composition. Those remain limitations.

## 5. Next-session OI score

The daily NIFTY participant read uses only aggregate index instruments:

```text
participant_daily =
    0.40 * index_call
  + 0.40 * index_put
  + 0.20 * index_future
```

Stock calls, stock puts, and stock futures are exposed as diagnostics but receive
zero daily NIFTY weight. The source says index options have immediate next-day
relevance, while aggregate stock-option activity may concern unidentified stocks
or sectors and can operate on a different horizon.

With complete participant rows, the composite is:

```text
daily_composite =
    0.533333 * Pro
  + 0.266667 * FII
  + 0.200000 * contra_Client
```

If a participant row is missing, available nonzero weights are renormalised.
DII is never assigned directional weight.

### Forced research class

The locked class boundary is `±0.10`:

| Composite | Research label |
|---:|---|
| `>= +0.45` | `UP` / strong bullish |
| `+0.10` to `< +0.45` | `SIDEWAYS-UP` / bullish |
| `>-0.10` to `<+0.10` | `RANGE` / neutral |
| `>-0.45` to `<= -0.10` | `SIDEWAYS-DOWN` / bearish |
| `<= -0.45` | `DOWN` / strong bearish |

For the historical three-class audit, both `UP` and `SIDEWAYS-UP` map to `UP`,
and both bearish labels map to `DOWN`. This forced class exists to compare v2 to
v1 on every date; it must not be confused with permission to trade.

The numeric boundary was frozen using the 2023–2024 development partition before
locked 2025 validation and 2026 confirmation evaluation.

## 6. Actionability and abstention

V2 separates the forced research class from what the report says a user can act
on.

### FII/Pro conflict

A material conflict exists when FII and Pro daily participant reads have opposite
signs and each absolute read exceeds `0.15`.

```text
FII * Pro < 0 and min(abs(FII), abs(Pro)) > 0.15
```

Output:

```text
WAIT_FOR_REVERSAL_CONFIRMATION
```

The source treats this as a possible first-move/then-reversal path whose order
depends on pre-open information. V2 therefore does not call the closing direction
a safe entry.

### Weak aggregate score

If there is no material FII/Pro conflict but `abs(daily_composite) < 0.10`, output:

```text
NO_DIRECTIONAL_EDGE
```

### Conditional directional setup

Otherwise output one of:

```text
CONDITIONAL_BULLISH_SETUP
CONDITIONAL_BEARISH_SETUP
```

“Conditional” means the relevant option-chain/institutional level must hold,
reject, or break with the transcript's price-action confirmation (typically a
10–15 minute candle). If the level fails, the backup plan replaces the original
lean. Without a date-matched chain and intraday candle, the repository cannot
verify that trigger.

### Setup strength is not confidence

For API compatibility, the `confidence` field remains present. In v2 it is only:

```text
setup_strength = min(100, abs(daily_composite) / 0.45 * 100)
```

Conflict caps it at 40. It is deterministic score intensity, **not a calibrated
probability of being right**. Historical strength buckets were not monotonic in
2026; higher displayed strength must not be presented as higher expected
accuracy.

## 7. Cash, option chain, and opening scenarios

### Cash flow

When supplied, FII/DII cash data is displayed as zero-weight confirmation. A
strong contradiction adds a warning; agreement adds a confirmation note. It does
not change the daily class because historical cash inputs were unavailable for
the locked v2 replay.

### Option-chain proxy versus exact institutional levels

The complete PDF review found that the speaker does not disclose the formula for
his exact institutional levels; he explicitly refers that construction to an
Advanced Course. He also distinguishes non-strike institutional values such as
24,076 from round-number option-chain levels such as 24,000. See
[institutional-levels.md](institutional-levels.md) for page/timestamp evidence.

Accordingly, automatic values are labelled `option_chain_proxy`, never exact
institutional levels. Put concentrations below spot are support candidates and
call concentrations above spot are resistance candidates. Relevant-side strikes
are ranked with both disclosed inputs:

```text
level_evidence =
    0.60 * (strike total OI / maximum side total OI)
  + 0.40 * (positive strike OI change / maximum side positive OI change)
```

The 60/40 split is an engineering ranking rule, not probability and not a
transcript percentage. Positive OI change is not called “writing,” because OI
alone cannot identify the buyer or seller.

Exact external references can be supplied with `--institutional-levels`. They
remain labelled `supplied_institutional_reference` and are never presented as
repository-derived. A supplied reference near an option-chain proxy is marked as
confluence.

Levels do not alter the locked OI class. Historical date-matched chains and exact
institutional-level series were unavailable, so no option-level reaction accuracy
is claimed for v2.

### Level-by-level prediction

Every retained level receives a structured decision tree in
`predictions.next_day.level_predictions`:

- support hold/reclaim with a bullish 10–15 minute candle → bounce toward the
  next upper level;
- support break, failed reclaim, and bearish candle → role flip and next lower
  level;
- resistance rejection with a bearish candle → next lower level;
- resistance break/retest with a bullish candle → role flip and next upper level;
- open and sustain beyond a level → treat it as skipped/flipped and evaluate the
  next level;
- no confirmation → `WAIT / NO TRADE AT THIS LEVEL`.

The participant-OI lean selects a preferred branch, not a guaranteed outcome. A
confirmed opposite-direction break invalidates that preference for later levels;
from that point the report follows confirmed price action only.

### Gap-up / flat / gap-down branches

The output creates plans for all three possible openings because pre-open news
and Gift Nifty were described as deciding or overriding the first path. These are
conditional scenario descriptions—not three simultaneous predictions and not a
claim that the opening gap is forecast from EOD OI.

## 8. Positional carry context

As-on-date carry uses the signed `long-short` level relative to current market OI:

```text
carry_ratio = direction_sign * (long - short) / market_oi
carry_score = tanh(carry_ratio / instrument_carry_scale)
```

Client carry is contra-adjusted. Participant carry combines:

| Instrument | Weight |
|---|---:|
| Index call | 30% |
| Index put | 30% |
| Index future | 25% |
| Stock future | 15% |

Participant carry is then FII 60%, Pro 25%, and contra-Client 15%. Stock futures
are included here because the source uses them as multi-session accumulation
context; stock options remain excluded.

`build_predictions()` can calculate a recency-weighted five-session context and
an internal `research_lean`. Production v2 nevertheless outputs:

```text
next_week.direction = NO-VALIDATED-EDGE
next_week.actionability = CONTEXT_ONLY_WAIT_FOR_MULTI_SESSION_CONFIRMATION
```

The locked five-session candidate improved 2025 but failed the 2026 confirmation
period. Publishing its direction as a production forecast would therefore be
dishonest. V1 weekly output remains available only for replay compatibility.

## 9. Chronological validation design

The real-data replay uses point-in-time Participant-OI and NIFTY daily OHLC from
the public `sahilempire/groww-market-data` mirror pinned at commit
`7d481cf1fcffe44be68852892028195c4f12dddd`.

The periods are:

- **development:** 2023–2024 target sessions;
- **validation:** 2025 target sessions;
- **confirmation:** 2026 target sessions through the pinned archive;
- **full:** all 757 evaluable signals.

V2 rules and candidate thresholds were frozen from transcript interpretation and
development work before evaluating unchanged logic on validation and
confirmation. The repository's earlier v1 audit had already exposed 2026, so the
confirmation period is not described as a pristine holdout.

For OI published after signal session `t`, the next tradable target is session
`t+1`. Three return bases are kept separate:

```text
close_to_close = close[t+1] / close[t] - 1
next_open_to_close = close[t+1] / open[t+1] - 1
overnight_gap = open[t+1] / close[t] - 1
```

Daily realised classes use a declared `±0.15%` FLAT band. The five-session audit
uses a `±0.50%` FLAT band.

Metrics distinguish:

- exact UP/FLAT/DOWN classification;
- majority-class baseline;
- directional coverage;
- directional-call hit rate with realised FLAT counted as a miss;
- sign accuracy only among realised non-FLAT observations;
- trigger-eligible/actionability subsets;
- Wilson 95% confidence intervals.

Sign accuracy after excluding FLAT observations answers a narrower question than
three-class accuracy and must always be reported with its denominator.

## 10. Locked result and interpretation

Authoritative production replays:

| Period | N | V1 exact close-to-close | V2 exact close-to-close | V1 non-FLAT sign | V2 non-FLAT sign |
|---|---:|---:|---:|---:|---:|
| 2023–2024 development | 342 | 35.96% | 38.01% | 54.21% | 56.25% |
| 2025 validation | 248 | 37.90% | 37.90% | 55.88% | 54.86% |
| 2026 confirmation | 167 | 34.13% | 37.72% | 50.55% | 53.00% |
| Full | 757 | 36.20% | 37.91% | 53.96% | 55.05% |

Full-sample basis diagnostics:

| Basis | V1 exact | V2 exact | V1 directional-call hit | V2 directional-call hit | V1 non-FLAT sign | V2 non-FLAT sign |
|---|---:|---:|---:|---:|---:|---:|
| Close-to-close | 36.20% | 37.91% | 42.61% | 43.72% | 53.96% | 55.05% |
| Overnight gap | 38.84% | 39.23% | 40.34% | 40.44% | 62.65% | 62.54% |
| Next-open-to-close | 33.42% | 34.87% | 36.36% | 38.25% | 46.72% | 49.41% |

The full close-to-close majority baseline is 42.14%, above both decoder versions.
V2's full non-FLAT close sign 95% interval is 50.35%–59.65%. Its trigger-eligible
next-open-to-close sign is 49.50% on 400 observations. Strength filtering did not
remain stable in confirmation, and the weekly candidate was rejected.

Therefore:

- v2 is a more faithful and auditable transcript translation than v1;
- it shows a modest historical improvement on several forced metrics;
- it has **not** established reliable executable accuracy or profitability;
- the old warning remains in generated reports;
- future untouched forward validation is required before any stronger claim.

The complete generated evidence is in
`reports/backtest_v2_2023-08_to_2026-09/`. The prior v1 package remains intact in
`reports/backtest_2023-08_to_2026-09/`.

## 10a. v3-candidate addendum (2026-09-17)

A dedicated deep dive (`reports/v3_deep_dive/REPORT.md`) tested the v2 rules and
their neighbourhood exhaustively. The adopted v3-candidate deltas (fitted on the
2023-2024 development partition, everything else unchanged):

| Parameter | V2 | V3 candidate |
|---|---|---|
| Instrument mix (next-day) | call 40 / put 40 / futures 20 | call 30 / put 30 / **futures 40** |
| Participant mix | Pro 53.3 / FII 26.7 / contra-Client 20 | **Pro 60 / FII 40** / Client-tilt −0.10 |
| Forced-class threshold | ±0.10 | **0.00** |
| Closure weight, OI normalisation, DII exclusion, stock-exclusion, actionability, weekly rule | unchanged | unchanged |

Close-to-close (±0.15% band): **exact 45.05% vs 42.14% baseline** full sample
(v2: 37.91%), with validation 43.95% and confirmation 46.71% beats over their
period baselines; non-FLAT sign 57.12% (95% CI 53.12-61.03). Paired McNemar vs
v2 pooled p≈0.0000. Caveats: gains concentrate in the overnight-gap channel;
the executable open-to-close basis stays ≈ chance (sign 51.30%); weekly
remains NO-VALIDATED-EDGE; levels remain a coin flip. **V3 is opt-in
(`--decoder-version v3`) until an untouched forward window confirms it.**

Evidence: `reports/backtest_v3_candidate_2023-08_to_2026-09/`. Implementation:
`src/fiidii/decode_v3.py` (delegates to the v2 machinery with candidate
constants so the two cannot silently diverge).

## 11. Reproduction

Run the full comparison against the pinned archive paths:

```bash
PYTHONPATH=src python research/compare_v1_v2.py \
  --participant-oi /path/to/groww-market-data/nse_archives/participant_oi \
  --ohlc /path/to/groww-market-data/nse_archives/index_close \
  --output-dir reports/backtest_v2_2023-08_to_2026-09 \
  --source-note "Public mirror pinned at 7d481cf1fcffe44be68852892028195c4f12dddd"
```

For the standard backtest CLI, choose the decoder explicitly:

```bash
PYTHONPATH=src python -m fiidii.cli backtest \
  --participant-oi /path/to/participant_oi \
  --ohlc /path/to/index_close \
  --decoder-version v2 \
  --output-dir /tmp/fiidii-v2-replay
```
