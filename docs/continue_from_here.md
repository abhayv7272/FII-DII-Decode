# Continue From Here — Chat/Work Handoff

Last updated: 2026-09-18 IST
Branch: `arena/01a0b16b-fii-dii-decode`

## User's main objective

Build a real NIFTY prediction maker that can be emailed daily and explain:

- next day: UP / DOWN / CONSOLIDATION;
- coming week Monday-Friday: likely UP / DOWN / CONSOLIDATION or range context;
- important levels: support/resistance, break, reject, role-flip, sweep/reclaim;
- what can happen in the market under different scenarios;
- when to trade and when to wait/no-trade;
- backtested honestly before claiming it can be used.

Standing instruction: do **not** close, merge, rename, delete, or switch the active session branch unless the user explicitly asks. Keep backing up work/chat to GitHub periodically.

## Current honest validation status

The full original predictor is **not yet proven at 75-85%+ every-day next-day/weekly directional accuracy**.

Evidence summary:

- V2 production OI decoder: 37.91% exact UP/FLAT/DOWN on 757 historical sessions, below the 42.14% majority baseline.
- V3 candidate: 45.05% exact and better than V2/baseline in untouched splits, but not promoted because much of the gain is overnight-gap/non-executable and open-to-close remains near chance.
- V4-V9 psychology/OI/intraday/level confirmation searches: 0 robust production-ready 70-85% directional/trade rules.
- V12 direct Friday-to-following-Monday–Friday composite search tested 18,527 development-fitted rules plus 16,110 agreement pairs across 4,746 clean point-in-time features: 0 reached the 85% gate in both 2025 validation and 2026 confirmation with at least 10 calls each. A caught target-label leak was excluded before the clean rerun; see `reports/v12_weekly_composite_search/report.md`.
- V13 added timing-correct same-day India VIX risk-state gates across 745 aligned v3 signal rows: 0 of 1,022 rules reached the 85% gate in both later splits. The third-party historical VIX copy is research-only and no VIX term was promoted; see `reports/v13_india_vix_gate/report.md` and `docs/deep-dive-research-plan.md`.
- V10 found a **supporting** high-accuracy sub-signal only: at-open tiny-gap previous-close intraday touch.
- V11 tried to convert V10 into a simple target/stop trade: 0 robust 70% + positive-P&L trade conversions.

## What V10 means exactly

V10 is not the full prediction maker. It is only a sniper/level-touch module.

Rule:

- At cash-market open, if absolute gap from previous close is 0.03%-0.12%, predict previous close will be touched intraday.
- Gap up -> expected touch downward to previous close.
- Gap down -> expected touch upward to previous close.
- If outside the band -> no V10 signal.

Backtest:

| Rule | Calls | Overall | Train 2017-23 | Val 2024-25 | Confirm 2026 |
|---|---:|---:|---:|---:|---:|
| `abs_gap_0.03_0.12_both_fill_prev_close` | 393 | 90.33% | 89.11% | 94.23% | 87.50% |

Important: this does **not** mean every day next-day UP/DOWN/CONSOLIDATION is 90% correct. It only means selected tiny-gap days historically touched previous close intraday about 90% of the time.

## What is already implemented in the report/email

Latest pushed work expanded the report to include:

- data health / source provenance;
- next-day OI lean;
- weekly positional context;
- full market possibility map:
  - base OI context,
  - consolidation/range day possibility,
  - bullish expansion path,
  - bearish rejection/breakdown path,
  - liquidity sweep/trap watch,
  - V10 tiny-gap sniper,
  - no-trade/protect-capital conditions;
- Mon-Friday weekly playbook;
- gap-up / flat / gap-down scenario plan;
- level-by-level support/resistance hold/reject/break/role-flip plan;
- V10 opening-sniper status/playbook;
- risk-management warning.

Manual sniper CLI:

```bash
PYTHONPATH=src python -m fiidii.cli sniper \
  --open 23020 --previous-close 23000 --high 23025 --low 22998
```

## Important files

- `SESSION_LOG.md` — running session backup.
- `docs/prediction_maker_status.md` — original goal vs current evidence clarification.
- `src/fiidii/report.py` — report rendering; now includes full market possibility map and weekly playbook.
- `src/fiidii/predict.py` — prediction payload and V10 playbook hook.
- `src/fiidii/gap_sniper.py` — V10 tiny-gap helper.
- `research/v10_structural_gap_pivot_sniper.py` — V10 level-touch research.
- `reports/v10_structural_gap_pivot_sniper/report.md` — V10 evidence.
- `research/v11_gap_sniper_execution.py` — V11 execution audit.
- `reports/v11_gap_sniper_execution/report.md` — V11 evidence.
- `research/v12_weekly_composite_search.py` — direct next-Monday–Friday leak-safe combination search.
- `reports/v12_weekly_composite_search/report.md` — V12 weekly evidence and promotion gate.
- `research/v13_india_vix_gate.py` — timing-correct external India-VIX gate research.
- `reports/v13_india_vix_gate/report.md` — V13 daily evidence and promotion gate.
- `docs/deep-dive-research-plan.md` — complete input coverage, timing, protocol and data-priority map.

## Latest test status

Latest full suite after V12/V13 research and scenario-surface regression checks:

```text
55 passed
```

## Best next step

If continuing the project, do not claim the full predictor is solved. The best honest path is:

1. Keep/report the full scenario map as conditional market analysis.
2. Use V10 only as an at-open level-touch alert.
3. To improve toward the original full aim, collect or integrate missing data:
   - intraday option-chain snapshots (OI, change in OI, volume, IV, premium by strike),
   - tick/broker option-premium execution data,
   - GIFT/pre-open/global cues,
   - heavyweight stock/sector intraday leadership,
   - India VIX/straddle/expiry/event context,
   - exact timestamped institutional levels.
4. Backtest any new claim with train/validation/confirmation split and no leakage.

## Current Git state to expect

This Arena continuation is fixed to `arena/01a0b980-fii-dii-decode`. The initial
chat-backup commit is `86aa28e`; the V12 code/report checkpoint follows it.

Always run:

```bash
git status --short --branch
git log -3 --oneline --decorate
```

If a future workspace is unexpectedly missing the branch's committed files, fetch
the same fixed remote branch and inspect it before making changes; do not switch
branches or reset away uncommitted user work.
