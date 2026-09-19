# Forward Context Validation Protocol

> Last updated: 2026-09-19. This protocol is deliberately fixed **before**
> sufficient new data exist. It is a research guardrail, not investment advice
> and not a claim of a predictive edge.

## Purpose and non-negotiable boundary

`capture-preopen` and `capture-intraday` collect inputs that were unavailable in
the historical EOD-only studies: direct NSE pre-open state and time-stamped
option-chain OI/change-OI/volume/IV/wall context. The data remain separate from
`fiidii run`, decoder score, email direction and historical backtests.

No feature threshold, classifier, level rule, next-day claim or trade rule may
be selected from these data while the collection readiness gate is incomplete.
A large number of 15-minute rows is **not** a large number of independent
observations: all captures from one trading session count as one session for
sample gates.

## Accepted session definition

A session is `complete` only when the automated audit verifies all of the
following:

1. Exactly one direct NSE pre-open record, captured between **09:00 and 09:14
   IST**, with matching session date, source clock timestamp and payload hash.
   The normal NSE constituent response is kept as `constituent_breadth`; it is
   never converted to an invented unweighted NIFTY index level.
2. At least **20** direct NSE NIFTY option-chain snapshots. Their actual capture
   times must be in 09:15–15:45 IST, include an early capture no later than
   09:25 and a late capture no earlier than 15:20.
3. Each intraday row has a same-session source clock timestamp, source payload
   SHA-256, no timestamp duplicate and `source_fallback=false`.
4. Any source failure, delayed pre-open run, EOD/third-party fallback, stale
   payload, missing hash or malformed timestamp makes that session incomplete;
   it is logged rather than repaired/backfilled.

Run the collection-only audit at any time:

```bash
PYTHONPATH=src python research/forward_context_readiness.py
```

It writes `reports/forward_context_readiness/` and intentionally does not read
price outcomes or calculate accuracy.

## Predeclared sequential data gate

| Stage | Complete sessions needed | Permitted work | Forbidden work |
|---|---:|---|---|
| Collection quality review | 80 | Audit gaps, provenance, timestamp/source validity, and data dictionary only | Any label join, signal threshold/model selection, accuracy or P&L headline |
| Freeze initial study | 200 | Allocate the first 80 complete sessions to development, next 60 to validation, next 60 to confirmation; write feature/entry/label/execution specification before fitting | Moving dates, selecting with validation/confirmation data, counting intraday rows as independent sessions |
| Promotion-forward check | 260 | Evaluate the pre-frozen candidate on the next 60 complete sessions exactly once | Retuning after confirmation, changing the target, or calling success from an in-sample result |

Quality-based exclusion is allowed only through the accepted-session rules above
and must be reported before any outcomes are inspected. It may not be changed to
remove difficult labelled sessions.

## Timing and target contract

The eventual study must declare one of these modes per candidate. Mixing them in
one accuracy figure is prohibited.

- **At-open:** use pre-open state only; label open-to-close or an explicitly
  later, confirmed entry. Overnight return is not capturable from a pre-open
  entry and must not be credited as such.
- **Intraday:** use only a snapshot that exists before entry plus completed
  candles before entry. Compute deltas only from earlier snapshots on the same
  session. Score target/stop, costs, spread/slippage and ambiguous bars
  conservatively.
- **Next-day EOD context:** use only data published by the preceding close.
  Intraday captures from the target day must never become features.
- **Monday–Friday:** remains context-only until a separately predeclared weekly
  study has **130 completed Friday observations** (52 development, 26 validation,
  26 confirmation, 26 fresh forward). Daily snapshot counts cannot substitute
  for weekly observations.

## Candidate and promotion requirements

Before the 80-session development segment is opened, create a versioned feature
schema and one-page experiment specification naming: source columns,
normalisation, missing-data policy, entry time, target, stop, cost/slippage,
coverage, exact-class versus non-FLAT-sign metric, and `WAIT / NO TRADE` rule.
The validation/confirmation/fresh ranges must remain unread for feature
selection.

A candidate remains **research context only** unless it, without changes,
meets every predeclared gate in validation, confirmation and fresh-forward
ranges. A directional candidate targeting the requested 85% must show at least
85% on the relevant declared metric in every later range, with at least 30
eligible calls per range, disclose confidence intervals and coverage, and pass
an execution-aware audit. A selective abstention rule cannot hide losing days:
its coverage and every skipped reason are mandatory outputs. Failure at any
stage leaves the product at `WAIT / NO TRADE` / `CONTEXT_ONLY`.

This protocol is intentionally more conservative than a promising backtest. It
is designed to prevent the repeated EOD feature sweeps from being repeated on a
small new forward dataset.
