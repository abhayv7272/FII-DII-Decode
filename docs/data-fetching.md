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
| Pre-open index/breadth state | NSE pre-open market-data API | **None**; stale/later values are rejected | No; forward research capture only |
| Intraday option-chain aggregates | NSE index option-chain API | **None**; EOD fallback is rejected for timed capture | No; forward research capture only |
| Exact institutional references | User-provided dated JSON | None; option-chain levels are labelled proxies, never exact replacements | No |

Third-party fallbacks are independently named in output. They are never labelled
as direct NSE responses, even if the site says its data originated at NSE.
`GITHUB_TOKEN`, when present on GitHub Actions, is used only to increase the rate
limit for public repository reads; no market-data credential is required.

## Forward pre-open and intraday research capture

The ordinary 9 PM report cannot reconstruct what was visible before the next
open or during a level interaction. The separate **Capture Forward Market
Context** workflow therefore writes two compact, timestamped research datasets:

- `data/preopen_snapshots.csv` from `fiidii capture-preopen`; and
- `data/intraday_option_snapshots.csv` from `fiidii capture-intraday`.

Both commands record actual UTC and IST capture time, source/as-of metadata and
a status diagnostic. The NSE pre-open endpoint normally supplies constituent
rows, not an official synthetic NIFTY IEP; in that case the collector labels the
record `constituent_breadth` (advances/declines and change distribution) rather
than inventing an unweighted index level. The intraday record stores aggregate
OI, signed change-OI (including largest build/unwind walls), volume, PCR,
near-ATM state, walls, IV summaries and a SHA-256
payload fingerprint—not a large raw strike array. `capture-intraday --save-raw`
is an explicit manual/audit opt-in for a full raw snapshot; scheduled collection
keeps it off to avoid an unbounded repository archive.

There is intentionally **no fallback** for either time-sensitive collector. A
same-date EOD web page, Yahoo daily bar or delayed provider response does not
prove what was available pre-open/intraday and is rejected. Pre-open collection
also rejects an actual capture outside 09:00–09:14 IST; it stores an explicit
rejection diagnostic rather than relabelling a later value. GitHub Actions cron
can start late, so research must use the stored actual timestamp, never merely
the intended schedule time. These records are zero-weight and cannot change the
production decoder until a separately frozen forward backtest validates them.
The predeclared acceptance/session-count gates and the no-outcome readiness audit
are in [`forward-validation-protocol.md`](forward-validation-protocol.md).

Manual collection:

```bash
PYTHONPATH=src python -m fiidii.cli capture-preopen --symbol NIFTY
PYTHONPATH=src python -m fiidii.cli capture-intraday --symbol NIFTY
```

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
