# Live data fetching, validation, and failure policy

## Purpose

The decoder needs two complete participant-wise open-interest matrices: the
completed session and the immediately preceding trading session. Cash flow can
modify setup strength, and a same-date option chain supplies context-only level
proxies. Index OHLC is persisted for later forward evaluation; it is not silently
substituted for participant OI.

A provider response is not treated as usable merely because the HTTP request
succeeded. Every accepted input has structural and date checks and a provenance
record in `data/fetch_status_<YYYY-MM-DD>.json`.

## Provider order

| Dataset | Primary | Fallbacks | Required to publish direction? |
|---|---|---|---|
| Current participant OI | NSE clearing archive (`_b` and standard filename, current and legacy archive hosts) | Exact-date file from `sahilempire/groww-market-data`; date-checked complete Stocklyzer/NiftyTrader EOD renderings | **Yes** |
| Previous participant OI | Holiday-aware NSE/archive search | Exact-date Groww archive; rendered `current − displayed daily change` only when its current matrix agrees with the independently fetched matrix | **Yes** |
| FII/DII cash | NSE provisional cash API | Same-date `MrChartist/fii-dii-data` JSON | No; missing cash is disclosed |
| Option chain | NSE index option-chain API | Same-date MarketNetra public EOD table | No direction block; missing chain blocks actionable levels and gap plans |
| Index OHLC | NSE all-indices API | Exact daily Yahoo Finance chart bar | No; an incomplete bar is never persisted |
| Participant volume | NSE clearing archive | None | No; currently collected for research but not scored by locked v2 |
| Exact institutional references | User-provided dated JSON | None; option-chain levels are labelled proxies, never exact replacements | No |

Third-party fallbacks are independently named in output. They are never labelled
as direct NSE responses, even if the site says its data originated at NSE.
`GITHUB_TOKEN`, when present on GitHub Actions, is used only to increase the rate
limit for public repository reads; no market-data credential is required.

## Acceptance checks

### Participant OI

- all four participants (`Client`, `DII`, `FII`, `Pro`) are present;
- all futures and call/put long/short columns for index and stock derivatives are
  numeric and non-negative;
- total-long and total-short columns exist (or are reconstructed from every
  validated component for the Stocklyzer renderer);
- market-wide long and short contracts balance for every derivative group within
  a very small rounding tolerance;
- the archive filename/date or rendered as-of date matches the requested session;
- Stocklyzer may be at most five calendar days behind the requested date to allow
  for weekends/market holidays, and its actual date becomes the report date.

The rendered prior matrix is not assigned a guessed date. It is labelled
"immediately preceding trading session" because the providers report changes
against that session but do not publish a reliable holiday-calendar date in the
same matrix. If both Stocklyzer and NiftyTrader are reachable, current and
reconstructed-prior values must agree; disagreement rejects both. If only one is
reachable, its use is explicitly marked as uncorroborated fallback data.

### Cash

Both FII and DII rows must exist, have the requested date, and contain finite buy,
sell, and net values. A latest snapshot with any other date is rejected.

### Option chain

The snapshot must have the requested update date, positive spot and expiry,
strike data on both sides of spot, at least ten strikes, and non-zero call and put
OI totals. Abbreviated public values (`K`, `L`, `Cr`) are expanded before use.

### Index bar

Date must match, all OHLC values must be finite and positive, `high >= open/close`,
`low <= open/close`, and `high >= low`. Only complete validated bars are appended.

## Failure states

- `BLOCKED_MISSING_DIRECTION_INPUT`: current or previous participant OI failed.
  The command exits non-zero and does **not** decode a directional report.
- `DEGRADED_MISSING_LEVEL_INPUT`: OI pair is complete but no same-date option
  chain exists. The OI research lean may be shown, but actionability becomes
  `CONTEXT_ONLY_MISSING_SAME_DATE_OPTION_CHAIN`; no pseudo level/gap plan is made.
- `DEGRADED_MISSING_CASH_INPUT`: OI and levels exist, but cash confirmation/setup
  input is missing.
- `DEGRADED_FALLBACK_SOURCE`: required direction, level, and cash components
  exist, but at least one available dataset came from a named fallback.
- `READY_WITH_AUDIT_GAPS`: scored inputs exist from primary sources, but a
  non-scoring research/audit input such as participant volume or OHLC is absent.
- `READY`: required OI, same-date option-chain, cash, and audit inputs passed
  validation without a fallback.
- `DEMO_FIXTURE`: synthetic/approximate repository fixtures. This is never proof
  of live fetch availability or forecasting accuracy.

Cash, index OHLC, participant volume, and optional exact references remain visible
in the manifest even when their absence does not block the OI direction. This
makes the distinction between "not used by the locked score" and "silently
missing" explicit.

## Operational verification

1. Merge the workflow and code into the repository default branch; GitHub only
   schedules workflows from that branch.
2. Ensure Actions has read/write workflow permission because the job commits its
   dated input/report artifacts.
3. Trigger `Daily FII/DII Decode Report` manually with `demo=false` and
   `no_email=true` before relying on the schedule.
4. Inspect the job exit status, `data/fetch_status_<date>.json`, source/as-of rows
   in the report, and persisted participant/cash/OHLC/option-chain files.
5. Enable SMTP secrets only after the data run is healthy. Email delivery and
   data completeness are separate checks.

A normal-looking demo report, a workflow definition with no runs, or a source
web page viewed manually is not evidence that production fetching succeeds.
