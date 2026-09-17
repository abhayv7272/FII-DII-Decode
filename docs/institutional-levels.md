# Institutional levels and level-by-level predictions

## Finding from the complete PDF review

The supplied PDFs do **not** disclose the formula used to construct the
speaker's exact proprietary “institutional levels.” They show many resulting
levels and explain how to trade their reactions, but explicitly place the
construction method in an Advanced Course:

- `full_transcript.pdf`, p. 13, 00:45:27–00:46:19 — levels such as 24,076 are
  described as institutional support/resistance; the speaker says the method
  for marking them is taught in the Advanced Level Course.
- `Market_Analysis_03_August_2026_Decoded-combined.pdf`, pp. 11–12 (4 Aug),
  00:15:35–00:16:15 — after showing updated lines, the speaker again says the
  course explains how institutional levels are drawn for indices and stocks.

The source also proves that an institutional level is **not the same thing as an
option-chain strike**:

- `full_transcript.pdf`, p. 15, 00:51:41–00:52:05 — 24,000 is identified as an
  option-chain support, while 24,076 is explicitly said not to exist in the
  round-number option chain. Their proximity gives “double confirmation.”

Therefore this repository must not claim that a largest-OI strike reconstructs
the undisclosed proprietary formula. It now supports two visibly separate level
sources:

1. **Automatic option-chain proxy** — reproducibly derived from dated total OI
   and change in OI.
2. **Supplied institutional reference** — an exact level obtained externally
   and passed to the pipeline; it is never presented as repository-derived.

## Rules that are disclosed

Although exact construction is absent, the PDFs repeatedly disclose the level
reaction framework.

### Both total OI and change in OI matter

`full_transcript.pdf`, pp. 16–17, 00:57:55–00:58:42 compares total put OI and
new OI at nearby strikes and explicitly says both numbers are important.

The automatic proxy therefore ranks relevant strikes using:

```text
OI component       = strike-side total OI / maximum strike-side total OI
change component   = max(change in OI, 0) / maximum positive strike-side change
level evidence     = 60% * OI component + 40% * change component
```

The 60/40 split is a declared engineering ranking rule, not a percentage quoted
in the PDFs. It is an **evidence score**, not probability.

### Buyer versus writer is not observable from OI alone

Positive call OI change does not, by itself, prove “fresh call writing”; every
open contract has both a buyer and seller. The transcripts interpret chain data
alongside participant positioning, premium behavior, price, and expiry.

The old implementation incorrectly labelled every positive call change as call
writing and every positive put change as put writing. The revised output says
only “call-side concentration” or “put-side concentration” unless independent
price/participant evidence identifies the position type.

### Relevant-side classification

For the automatic proxy:

- put-side concentrations **below spot** are support candidates;
- call-side concentrations **above spot** are resistance candidates;
- the highest combined evidence candidates are retained;
- immediate support is the nearest retained support below spot;
- immediate resistance is the nearest retained resistance above spot.

This prevents an already-crossed call strike below spot from being reported as
current overhead resistance, and prevents a put strike above spot from being
reported as current downside support.

### A level is a decision point, not a guaranteed reaction

The source requires price confirmation:

- `full_transcript.pdf`, pp. 14–15, 00:47:23–00:52:21 — support can flip to
  resistance; entry follows a visible reversal, and a failed support activates
  Plan B.
- Combined PDF, pp. 93–94 (24 Aug), 00:06:42–00:10:32 — resistance rejection
  requires a bearish candle low break; bullish continuation requires sustain
  above the level.
- Combined PDF, pp. 99–100 (25 Aug), 00:06:44–00:10:40 — a move above 24,357
  opens the next upper level, while a break below 24,200/24,179 increases the
  bearish branch.

The generated prediction consequently contains both branches for every level.

#### Support

```text
Confirmed bullish rejection/reclaim
    -> BOUNCE_OR_RECLAIM_UP
    -> target next listed upper level

Sustained bearish close below + failed reclaim + candle-low break
    -> BREAK_DOWN_AND_ROLE_FLIP
    -> old support becomes resistance
    -> target next listed lower level
```

#### Resistance

```text
Confirmed bearish rejection + candle-low break
    -> REJECTION_DOWN
    -> target next listed lower level

Sustained bullish close above + successful retest + candle-high break
    -> BREAK_UP_AND_ROLE_FLIP
    -> old resistance becomes support
    -> target next listed upper level
```

The default confirmation window is 10–15 minutes because that condition recurs
throughout the dated analyses. Without confirmation the output is:

```text
WAIT / NO TRADE AT THIS LEVEL
```

### Gap-skipped levels

`full_transcript.pdf`, pp. 17–18, 00:58:42–01:01:19 explains that if the market
opens below presumed supports, those supports cannot be blindly traded; the
next support is sought, and a broken support can become resistance.

Every level prediction therefore includes:

```text
If price opens and sustains beyond the level, treat it as skipped/flipped and
evaluate the next level.
```

Once a confirmed break in the opposite direction invalidates the original OI
lean, later “preferred” branches from that old lean are void. Price confirmation
controls the cascade.

### Confluence

`full_transcript.pdf`, pp. 15 and 17, 00:51:41–00:52:15 and
01:01:27–01:01:44 combines:

- institutional reference;
- option-chain level;
- psychological/round-number liquidity;
- reversal price action.

When a supplied institutional reference is within two normal strike intervals
of a same-role automatic proxy, both records are marked as confluence. This
proximity heuristic includes the transcript's 24,076/24,000 example; it is not
part of the undisclosed drawing formula. Confluence still does not remove the
candle-confirmation requirement.

## OI-lean preferred branch

The next-day participant-OI composite chooses only the **preferred branch**:

| OI state | At support | At resistance |
|---|---|---|
| Bullish | Prefer hold/reclaim | Prefer break-up/role-flip |
| Bearish | Prefer break-down/role-flip | Prefer rejection |
| Weak score or FII/Pro conflict | Wait for either confirmed branch | Wait for either confirmed branch |

This is a conditional scenario preference, not a probability that the level
will hold or break. If an opposite branch confirms, it invalidates the original
preference.

## Supplying exact external institutional references

Use a JSON list of numbers:

```json
[24076, 24179, 24254]
```

or objects when role/label is known:

```json
{
  "levels": [
    {"strike": 24076, "kind": "support", "label": "external chart level"},
    {"strike": 24179, "kind": "resistance", "label": "external chart level"}
  ]
}
```

Run:

```bash
PYTHONPATH=src python -m fiidii.cli run \
  --institutional-levels /path/to/levels.json \
  --no-email
```

If `kind` is omitted, a level below spot is classified as support and a level
above spot as resistance. The output source remains
`supplied_institutional_reference` and its basis remains
`supplied_reference_not_derived`.

## Output contract

`predictions.next_day.level_predictions[]` records:

- level, role, source, basis, and evidence grade;
- whether it is immediate or secondary;
- OI-lean preferred branch;
- confirmed hold/reject branch and next target;
- confirmed break/role-flip branch and next target;
- gap-skipped-level rule;
- cascade invalidation rule;
- explicit no-confirmation wait state.

`levels.level_method_warning` is rendered in every report so automatic proxy
levels cannot be mistaken for the undisclosed exact method.

## Validation limitation

The pinned 757-session archive contains Participant-OI and index OHLC but no
historical date-matched option-chain snapshots or exact institutional-level
series. Therefore the new level ranking and intraday reaction tree cannot be
genuinely backtested from that archive. Daily OHLC would still be insufficient
to prove whether a 10–15 minute confirmation occurred before a target or stop.

No level hit rate or profitability improvement is claimed. The existing
direction audit and validation warning remain unchanged.
