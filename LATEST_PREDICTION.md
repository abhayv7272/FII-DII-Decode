# SUPERSEDED RESEARCH SNAPSHOT

> This early price-only report is retained for audit history. Do not use it as the current decision. The authoritative output is `reports/daily/2026-09-18_professional_report.md`, whose hardened production decision is WAIT / NO TRADE.

# NIFTY Decision Report

**Decision time:** 20 September 2026 (Sunday)  
**Latest completed market session in source:** 18 September 2026  
**Forecast session:** Monday, 21 September 2026  
**Instrument:** NIFTY 50 (`^NSEI`)

## Final decision

# WAIT / NO TRADE

The model's largest class is **DOWN**, but its confidence is only **38.74%**, below the validated action gate of **65%**. UP probability is close at **35.57%**, so there is no reliable directional separation.

| Outcome | Probability |
|---|---:|
| DOWN | 38.74% |
| FLAT | 25.69% |
| UP | 35.57% |

This is **not** an actionable bearish call. The correct system output is WAIT because the confidence gate failed.

## Latest price snapshot

| Field | Value |
|---|---:|
| Open | 23,334.70 |
| High | 23,389.15 |
| Low | 23,286.60 |
| Close | 23,346.40 |
| ATR(14) | 195.57 points |

## Key levels for the next session

| Level | Value |
|---|---:|
| Resistance R1 | 23,358.22 |
| Pivot | 23,275.93 |
| Support S1 | 23,188.32 |
| 20-session support | 23,116.10 |
| 20-session resistance | 24,378.60 |

### Conditional bullish path

1. Price sustains above **23,358**.
2. A completed candle confirms the breakout.
3. Retest of 23,358 holds as support.
4. Only then consider bullish continuation; otherwise treat the move as a possible bull trap.

### Conditional bearish path

1. Price rejects around **23,358** or loses the **23,276 pivot**.
2. **23,188** breaks on a completed candle.
3. Failed reclaim of 23,188 confirms weakness.
4. Next important downside watch zone is approximately **23,116**.

### Trap / sweep rule

A wick above resistance or below support is not confirmation. Wait for close plus follow-through/reclaim failure. Abnormal opening gaps invalidate these simple paths until a new range forms.

## Monday–Friday risk map

These are ATR-based uncertainty bands, not promised closing targets.

| Date | Session | Centre | Lower risk band | Upper risk band |
|---|---:|---:|---:|---:|
| 21 Sep 2026 | 1 | 23,344.23 | 23,148.66 | 23,539.79 |
| 22 Sep 2026 | 2 | 23,343.33 | 23,066.75 | 23,619.90 |
| 23 Sep 2026 | 3 | 23,342.63 | 23,003.90 | 23,681.37 |
| 24 Sep 2026 | 4 | 23,342.05 | 22,950.92 | 23,733.19 |
| 25 Sep 2026 | 5 | 23,341.54 | 22,904.23 | 23,778.84 |

## Validation reality check

- Historical sessions: **2,467**
- Chronological unseen validation sessions: **494**
- All-day accuracy: **37.45%**
- Balanced accuracy: **36.47%**
- Sessions passing the 65% gate: **0**
- Validated 80% directional edge: **not found**

Therefore, claiming 80% accuracy would be false. The system correctly refuses a trade rather than fabricating a high-confidence prediction.

## Data currently missing from this run

This run used price/OHLCV features. It did **not** receive timestamped files for:

- FII/DII cash flow;
- FII/Pro/Client participant OI;
- EOD and intraday option chain;
- India VIX;
- GIFT Nifty and global context;
- sector/heavyweight breadth.

The dashboard already accepts a dated numeric context CSV. These inputs must contain values known by the decision time; future values must never be inserted into day D.

## Risk notice

This is a research output, not investment advice or a guarantee of profit. Derivatives and options may cause rapid losses. Use paper trading and forward validation before deploying capital.
