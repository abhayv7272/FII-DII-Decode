# Ultra-Hard Diagnostic and Bug Audit

**Audit date:** 20 September 2026 IST  
**Final production decision after hardening:** **WAIT / NO TRADE**

## Executive outcome

The audit invalidated the earlier optimistic derivative-specialist result. Thirty-seven historical option sessions had been omitted because one contract endpoint returned blank underlying values, and one optimizer converted the final unlabeled session into DOWN. After repairing all missing sessions from NSE bhavcopies and rerunning the frozen chronology, the corrected candidate scored:

- 54.55% all-session accuracy on 99 later sessions;
- 55.51% balanced accuracy;
- 60.00% selected accuracy on 35 signals;
- negative net return at 3, 6 and 10 bps cost assumptions;
- approximately -3.99% net return and -4.21% max drawdown at 10 bps.

It fails the production promotion gate. A raw latest UP class probability is retained only as diagnostic output; it cannot create a trade while research approval is false.

## Critical/high-severity bugs fixed

1. **Historical-date future leakage:** explicit `--date` reruns could load price candles after the requested session. Price history is now canonically truncated at D, and specialist features are also truncated at D.
2. **Missing derivative sessions:** 37 option sessions were silently omitted when `UNDERLYING_VALUE` was blank. All were repaired from official F&O bhavcopies; options, futures and participant stores now each have 495 unique dates.
3. **Unlabeled final row mislabeled DOWN:** boolean conversion of a NaN next-day return created a false target. The missing target is now restored to NaN and excluded.
4. **Broken modern bhavcopy fallback:** the fallback expected legacy column names. Modern UDiFF IDO/IDF schemas are now normalized and tested.
5. **Fallback volume unit mismatch:** UDiFF traded contracts were compared with archive traded quantity. Bhavcopy volume is now multiplied by market lot; primary/fallback option and futures summaries match exactly.
6. **One-session-stale pivots:** D+1 pivot/S1/R1 used D-1 instead of the latest completed D candle. Levels now use D high/low/close.
7. **Partial participant overwrite:** daily hub updates replaced a 25-column historical participant row with a partial schema. Full participant features are now preserved; latest row has zero null fields.
8. **Model feature-set schema drift:** production always reconstructed derivative-only features even when optimization selected price-plus-derivatives/full. Production now reconstructs the exact frozen feature family and fails closed on missing columns.
9. **No promotion gate:** a high raw class probability could trigger a trade despite weak/negative holdout economics. Production now requires minimum sessions, all-day accuracy, selected sample, selected accuracy and positive 10-bps return.
10. **Specialist/session mismatch:** a model feature row from another date could feed the report. `prediction.as_of` must equal the manifest session or the decision becomes WAIT.
11. **Cached critical data allowed trading:** previous-day cached options/futures could satisfy the critical gate. Price, options and futures must now be fresh and date-matched.
12. **Historical rerun cache poisoning:** an older explicit rerun could overwrite a newer last-good cache. Cache writes are monotonic by as-of date.

## Medium/reliability bugs fixed

13. Friday-to-Monday cache age used calendar days rather than business days. It now uses business-day staleness.
14. Historical CSV and manifest writes were non-atomic. History, cache metadata, latest manifest and professional reports now use temporary files plus atomic replacement.
15. Concurrent scheduler/UI runs could race. A production file lock now serializes runs.
16. Run IDs had one-second resolution. Microseconds prevent run-directory collisions.
17. Event risk was not connected to the final report. A verified high-impact event can now block trading; absent verified calendar is explicitly reported.
18. Max drawdown omitted initial equity 1.0 and could understate a first-trade loss. All backtest engines now include initial equity.
19. Rejected-model directional probability still moved the weekly centre. When any production gate fails, the weekly centre is neutral and only ATR risk bands remain.
20. Data validation used `assert`, which disappears under optimized Python. It now raises explicit validation errors.
21. Corrupt feature-store manifests were silently ignored. They now count as failed source records.
22. Mixed ISO/day-first date parsing produced ambiguity warnings. Mixed-format parsing is explicit.

## Validation performed

- 16 automated regression tests passed.
- Python compilation passed.
- Critical Ruff static checks passed.
- Bandit high-severity scan found no high-severity issue.
- Two-run production reproducibility passed.
- CLI prediction and report JSON matched.
- Source names, dates, row counts and SHA-256 hashes matched across runs.
- Explicit historical rerun ended price/features on the requested date and did not poison the newer cache.
- Modern bhavcopy fallback was executed against real data.
- Primary and fallback option/futures aggregates matched exactly for PCR, walls, OI, basis, change-OI and normalized volume.
- Historical stores: 495 option dates, 495 futures dates, 495 participant dates; zero duplicate dates.

## Current authoritative status

- Data quality can be 100% while model quality fails; these are separate gates.
- Corrected derivative candidate is **not production-approved**.
- Latest authoritative decision is **WAIT / NO TRADE**.
- Long/short class scores are diagnostic only until a future model passes the promotion gate.
- Weekly output is a neutral ATR risk map while the model is rejected.
