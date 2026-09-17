# Transcript-grounded v2 historical comparison

> Point-in-time research replay, not a P&L result and not investment advice. V2 was specified from the transcripts plus 2023-2024 development before 2025 validation and 2026 confirmation were inspected. The repository's earlier v1 audit had already exposed 2026, so 2026 is confirmation—not a pristine holdout.

## Decision

V2 raises full-sample close-to-close exact classification from **36.20%** to **37.91%**, but still trails the **42.14%** majority baseline. Its open-to-close sign is still approximately chance. The changes are retained because they correct transcript mistranslations and improve several development/confirmation diagnostics, not because they validate a trading edge.

Production v2 now marks FII/Pro conflicts as `WAIT_FOR_REVERSAL_CONFIRMATION`, weak scores as `NO_DIRECTIONAL_EDGE`, and all other leans as conditional on a 10-15 minute price/level trigger. Setup strength is not a probability.

## Locked v2 changes

1. Fresh additions receive full weight; short covering/long unwinding receive half weight.
2. Flows are divided by current instrument market OI; fixed contract-count scales are removed.
3. NIFTY next-day direction uses index calls (40%), index puts (40%), and index futures (20%).
4. Pro:FII is 2:1 inside the 80% Smart-Money share; contra-Retail is 20%; DII F&O is ignored.
5. Stock derivatives remain diagnostics but cannot manufacture a NIFTY next-day direction.
6. Forced research classes use a locked ±0.10 score boundary; actionability separately removes conflicts.
7. Cash and option-chain levels are confirmation-only unless date-matched history is supplied.

See `docs/transcript-audit-v2.md` for timestamp/page evidence and each v1 mapping error.

## Daily close-to-close (±0.15% FLAT band)

| Period | Version | N | Exact | Baseline | Dir. coverage | Dir. hit incl. FLAT | Non-FLAT sign | 95% CI | Trigger-eligible sign |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023-2024 development | v1 | 342 | 35.96% | 45.32% | 72.51% | 41.53% | 54.21% (190) | 47.11%-61.14% | 54.21% (190) |
| 2023-2024 development | v2 | 342 | 38.01% | 45.32% | 72.51% | 43.55% | 56.25% (192) | 49.18%-63.08% | 56.74% (178) |
| 2025 validation | v1 | 248 | 37.90% | 39.92% | 68.15% | 44.97% | 55.88% (136) | 47.49%-63.95% | 55.88% (136) |
| 2025 validation | v2 | 248 | 37.90% | 39.92% | 72.58% | 43.89% | 54.86% (144) | 46.71%-62.76% | 55.15% (136) |
| 2026 confirmation | v1 | 167 | 34.13% | 42.51% | 66.47% | 41.44% | 50.55% (91) | 40.46%-60.59% | 50.55% (91) |
| 2026 confirmation | v2 | 167 | 37.72% | 42.51% | 72.46% | 43.80% | 53.00% (100) | 43.29%-62.49% | 52.58% (97) |
| full | v1 | 757 | 36.20% | 42.14% | 69.75% | 42.61% | 53.96% (417) | 49.16%-58.68% | 53.96% (417) |
| full | v2 | 757 | 37.91% | 42.14% | 72.52% | 43.72% | 55.05% (436) | 50.35%-59.65% | 55.23% (411) |

## Following open-to-close (±0.15% FLAT band)

| Period | Version | N | Exact | Baseline | Dir. coverage | Dir. hit incl. FLAT | Non-FLAT sign | 95% CI | Trigger-eligible sign |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023-2024 development | v1 | 342 | 33.04% | 36.84% | 72.51% | 33.87% | 45.65% (184) | 38.62%-52.86% | 45.65% (184) |
| 2023-2024 development | v2 | 342 | 33.92% | 36.84% | 72.51% | 35.48% | 48.09% (183) | 40.96%-55.29% | 48.52% (169) |
| 2025 validation | v1 | 248 | 35.08% | 41.94% | 68.15% | 42.60% | 51.80% (139) | 43.56%-59.94% | 51.80% (139) |
| 2025 validation | v2 | 248 | 35.48% | 41.94% | 72.58% | 42.78% | 52.74% (146) | 44.68%-60.66% | 52.52% (139) |
| 2026 confirmation | v1 | 167 | 31.74% | 38.32% | 66.47% | 32.43% | 40.91% (88) | 31.23%-51.35% | 40.91% (88) |
| 2026 confirmation | v2 | 167 | 35.93% | 38.32% | 72.46% | 37.19% | 46.88% (96) | 37.21%-56.78% | 46.74% (92) |
| full | v1 | 757 | 33.42% | 38.71% | 69.75% | 36.36% | 46.72% (411) | 41.94%-51.55% | 46.72% (411) |
| full | v2 | 757 | 34.87% | 38.71% | 72.52% | 38.25% | 49.41% (425) | 44.69%-54.15% | 49.50% (400) |

The open-to-close basis is the more realistic executable-direction diagnostic because Participant-OI is published after the signal session. Neither version establishes a reliable edge on it.

## Overnight gap (±0.15% FLAT band)

| Period | Version | N | Exact | Baseline | Dir. coverage | Dir. hit incl. FLAT | Non-FLAT sign | 95% CI | Trigger-eligible sign |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023-2024 development | v1 | 342 | 41.23% | 45.32% | 72.51% | 43.95% | 66.06% (165) | 58.54%-72.85% | 66.06% (165) |
| 2023-2024 development | v2 | 342 | 43.27% | 45.32% | 72.51% | 45.56% | 67.26% (168) | 59.85%-73.90% | 67.10% (155) |
| 2025 validation | v1 | 248 | 35.48% | 43.15% | 68.15% | 31.95% | 56.25% (96) | 46.28%-65.74% | 56.25% (96) |
| 2025 validation | v2 | 248 | 33.87% | 43.15% | 72.58% | 31.67% | 57.00% (100) | 47.22%-66.27% | 57.45% (94) |
| 2026 confirmation | v1 | 167 | 38.92% | 37.13% | 66.47% | 45.05% | 63.29% (79) | 52.28%-73.07% | 63.29% (79) |
| 2026 confirmation | v2 | 167 | 38.92% | 37.13% | 72.46% | 42.98% | 59.77% (87) | 49.26%-69.45% | 60.71% (84) |
| full | v1 | 757 | 38.84% | 40.03% | 69.75% | 40.34% | 62.65% (340) | 57.39%-67.62% | 62.65% (340) |
| full | v2 | 757 | 39.23% | 40.03% | 72.52% | 40.44% | 62.54% (355) | 57.39%-67.41% | 62.76% (333) |

The transcript says pre-open news/Gift Nifty decides the opening order and can override EOD OI. Historical pre-open inputs were unavailable, so the gap result is an association—not an executable forecast claim.

## V2 setup strength is not calibrated confidence

| Period | Minimum strength | Eligible calls | Coverage | Non-FLAT sign | 95% CI |
|---|---:|---:|---:|---:|---:|
| 2023-2024 development | 0 | 229 | 66.96% | 56.74% (178) | 49.40%-63.80% |
| 2023-2024 development | 40 | 164 | 47.95% | 58.40% (125) | 49.64%-66.66% |
| 2023-2024 development | 60 | 112 | 32.75% | 60.23% (88) | 49.78%-69.82% |
| 2023-2024 development | 80 | 64 | 18.71% | 60.78% (51) | 47.09%-72.97% |
| 2025 validation | 0 | 171 | 68.95% | 55.15% (136) | 46.76%-63.25% |
| 2025 validation | 40 | 120 | 48.39% | 57.14% (98) | 47.26%-66.49% |
| 2025 validation | 60 | 76 | 30.65% | 56.25% (64) | 44.09%-67.71% |
| 2025 validation | 80 | 42 | 16.94% | 59.46% (37) | 43.49%-73.65% |
| 2026 confirmation | 0 | 117 | 70.06% | 52.58% (97) | 42.73%-62.23% |
| 2026 confirmation | 40 | 92 | 55.09% | 50.67% (75) | 39.60%-61.67% |
| 2026 confirmation | 60 | 68 | 40.72% | 48.21% (56) | 35.67%-60.99% |
| 2026 confirmation | 80 | 44 | 26.35% | 48.65% (37) | 33.45%-64.11% |
| full | 0 | 517 | 68.30% | 55.23% (411) | 50.40%-59.97% |
| full | 40 | 376 | 49.67% | 56.04% (298) | 50.36%-61.56% |
| full | 60 | 256 | 33.82% | 55.77% (208) | 48.98%-62.35% |
| full | 80 | 150 | 19.82% | 56.80% (125) | 48.04%-65.15% |

Strength was somewhat useful in development and 2025, but the relationship reversed in 2026. Raising the displayed score must not be interpreted as raising the probability of a correct trade.

## Five-session candidate (±0.20 score boundary; ±0.50% FLAT band)

| Period | Version/status | N | Exact | Baseline | Coverage | Dir. hit incl. FLAT | Non-FLAT sign | 95% CI |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2023-2024 development | v1 / production | 338 | 28.40% | 50.59% | 40.83% | 45.65% | 60.00% (105) | 50.44%-68.86% |
| 2023-2024 development | v2_candidate / rejected_candidate | 338 | 32.54% | 50.59% | 44.97% | 46.71% | 56.80% (125) | 48.04%-65.15% |
| 2025 validation | v1 / production | 248 | 32.26% | 41.13% | 35.48% | 44.32% | 54.93% (71) | 43.40%-65.95% |
| 2025 validation | v2_candidate / rejected_candidate | 248 | 33.47% | 41.13% | 42.34% | 47.62% | 62.50% (80) | 51.55%-72.31% |
| 2026 confirmation | v1 / production | 167 | 29.34% | 49.70% | 43.71% | 46.58% | 54.84% (62) | 42.53%-66.58% |
| 2026 confirmation | v2_candidate / rejected_candidate | 167 | 29.34% | 49.70% | 47.31% | 41.77% | 47.83% (69) | 36.47%-59.41% |
| full | v1 / production | 753 | 29.88% | 43.96% | 39.71% | 45.48% | 57.14% (238) | 50.79%-63.27% |
| full | v2_candidate / rejected_candidate | 753 | 32.14% | 43.96% | 44.62% | 45.83% | 56.20% (274) | 50.28%-61.95% |

The transcript-correct carry-trend candidate improved 2025 but failed 2026 confirmation; it was rejected. Production v2 therefore reports positional carry as context and emits `NO-VALIDATED-EDGE` instead of a standalone weekly direction.

## Data and limitations

- Public sahilempire/groww-market-data mirror pinned at commit 7d481cf1fcffe44be68852892028195c4f12dddd; provenance and hashes are in ../backtest_2023-08_to_2026-09/provenance.json.
- V1 evaluated 757 dates; v2 evaluated 757; both skipped 3 dates under the same point-in-time rules.
- Participant-OI combines NIFTY, Bank Nifty, Fin Nifty, Midcap Nifty, all expiries, and hedges.
- No historical date-matched option chains, FII/DII cash flow, Gift Nifty, global macro snapshot, or 10-15 minute trigger candles were available.
- Daily OHLC cannot verify move order, a liquidity sweep, candle confirmation, stop execution, slippage, fees, or P&L.
- V2 setup strength is a deterministic score intensity, not calibrated confidence.
- Future untouched forward validation remains required.

## Reproduction outputs

- `v1_predictions.csv` / `v2_predictions.csv`: every forced daily class and realised bar.
- `daily_comparison.csv`: every period × return basis metric above.
- `v2_strength_breakdown.csv`: trigger-eligible sign diagnostics by setup-strength floor.
- `v1_five_session_predictions.csv` / `rejected_v2_five_session_candidate.csv`.
- `weekly_comparison.csv`: five-session stability and rejection evidence.
- `run_config.json`: declared thresholds and input locations.

_Educational research only; not investment advice._