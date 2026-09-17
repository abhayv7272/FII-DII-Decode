# v3-candidate historical comparison (daily OI lean)

> **Status: research candidate, not production default.** V3 was fitted on the
> 2023-2024 development partition only, then replayed unchanged over 2025
> validation and 2026 confirmation. It must still pass an untouched forward
> window before any production promotion. Educational research; not investment advice.

Data: Public sahilempire/groww-market-data mirror pinned at commit 7d481cf1fcffe44be68852892028195c4f12dddd

## v3-candidate delta vs locked v2

- index call 30% / index put 30% / **index futures 40%** (v2: 40/40/20);
- **Pro 60% / FII 40%** (v2: Pro 53.3 / FII 26.7 / contra-Client 20) plus a small
  development-fitted Client-aligned tilt of -0.10 (zeroing it costs <1pp);
- forced-class threshold **0.00** (v2: +-0.10) — the ~79% of non-FLAT sessions makes
  a 0.10 abstain band cost more exact-class hits than it saves;
- closures still half weight, flows still normalised by market OI, DII still excluded,
  stock derivatives still out of the daily score, actionability still abstains on
  weak/composite-conflict states.

## close to close (+-0.15% FLAT band)

| Period | Version | N | Exact | Baseline | Dir. coverage | Dir. hit incl. FLAT | Non-FLAT sign | 95% CI |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2023-2024 development | v1 | 342 | 35.96% | 45.32% | 72.51% | 41.53% | 54.21% (190) | 47.11%-61.14% |
| 2023-2024 development | v2 | 342 | 38.01% | 45.32% | 72.51% | 43.55% | 56.25% (192) | 49.18%-63.08% |
| 2023-2024 development | v3 | 342 | 45.03% | 45.32% | 100.0% | 45.03% | 58.33% (264) | 52.31%-64.12% |
| 2025 validation | v1 | 248 | 37.9% | 39.92% | 68.15% | 44.97% | 55.88% (136) | 47.49%-63.95% |
| 2025 validation | v2 | 248 | 37.9% | 39.92% | 72.58% | 43.89% | 54.86% (144) | 46.71%-62.76% |
| 2025 validation | v3 | 248 | 43.95% | 39.92% | 100.0% | 43.95% | 55.33% (197) | 48.35%-62.1% |
| 2026 confirmation | v1 | 167 | 34.13% | 42.51% | 66.47% | 41.44% | 50.55% (91) | 40.46%-60.59% |
| 2026 confirmation | v2 | 167 | 37.72% | 42.51% | 72.46% | 43.8% | 53.0% (100) | 43.29%-62.49% |
| 2026 confirmation | v3 | 167 | 46.71% | 42.51% | 100.0% | 46.71% | 57.35% (136) | 48.95%-65.35% |
| full | v1 | 757 | 36.2% | 42.14% | 69.75% | 42.61% | 53.96% (417) | 49.16%-58.68% |
| full | v2 | 757 | 37.91% | 42.14% | 72.52% | 43.72% | 55.05% (436) | 50.35%-59.65% |
| full | v3 | 757 | 45.05% | 42.14% | 100.0% | 45.05% | 57.12% (597) | 53.12%-61.03% |

## overnight gap (+-0.15% FLAT band)

| Period | Version | N | Exact | Baseline | Dir. coverage | Dir. hit incl. FLAT | Non-FLAT sign | 95% CI |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2023-2024 development | v1 | 342 | 41.23% | 45.32% | 72.51% | 43.95% | 66.06% (165) | 58.54%-72.85% |
| 2023-2024 development | v2 | 342 | 43.27% | 45.32% | 72.51% | 45.56% | 67.26% (168) | 59.85%-73.9% |
| 2023-2024 development | v3 | 342 | 40.64% | 45.32% | 100.0% | 40.64% | 61.23% (227) | 54.76%-67.33% |
| 2025 validation | v1 | 248 | 35.48% | 43.15% | 68.15% | 31.95% | 56.25% (96) | 46.28%-65.74% |
| 2025 validation | v2 | 248 | 33.87% | 43.15% | 72.58% | 31.67% | 57.0% (100) | 47.22%-66.27% |
| 2025 validation | v3 | 248 | 32.26% | 43.15% | 100.0% | 32.26% | 56.74% (141) | 48.49%-64.63% |
| 2026 confirmation | v1 | 167 | 38.92% | 37.13% | 66.47% | 45.05% | 63.29% (79) | 52.28%-73.07% |
| 2026 confirmation | v2 | 167 | 38.92% | 37.13% | 72.46% | 42.98% | 59.77% (87) | 49.26%-69.45% |
| 2026 confirmation | v3 | 167 | 43.11% | 37.13% | 100.0% | 43.11% | 60.0% (120) | 51.06%-68.32% |
| full | v1 | 757 | 38.84% | 40.03% | 69.75% | 40.34% | 62.65% (340) | 57.39%-67.62% |
| full | v2 | 757 | 39.23% | 40.03% | 72.52% | 40.44% | 62.54% (355) | 57.39%-67.41% |
| full | v3 | 757 | 38.44% | 40.03% | 100.0% | 38.44% | 59.63% (488) | 55.22%-63.89% |

## next open to close (+-0.15% FLAT band)

| Period | Version | N | Exact | Baseline | Dir. coverage | Dir. hit incl. FLAT | Non-FLAT sign | 95% CI |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2023-2024 development | v1 | 342 | 33.04% | 36.84% | 72.51% | 33.87% | 45.65% (184) | 38.62%-52.86% |
| 2023-2024 development | v2 | 342 | 33.92% | 36.84% | 72.51% | 35.48% | 48.09% (183) | 40.96%-55.29% |
| 2023-2024 development | v3 | 342 | 38.6% | 36.84% | 100.0% | 38.6% | 53.01% (249) | 46.81%-59.12% |
| 2025 validation | v1 | 248 | 35.08% | 41.94% | 68.15% | 42.6% | 51.8% (139) | 43.56%-59.94% |
| 2025 validation | v2 | 248 | 35.48% | 41.94% | 72.58% | 42.78% | 52.74% (146) | 44.68%-60.66% |
| 2025 validation | v3 | 248 | 41.94% | 41.94% | 100.0% | 41.94% | 51.23% (203) | 44.4%-58.02% |
| 2026 confirmation | v1 | 167 | 31.74% | 38.32% | 66.47% | 32.43% | 40.91% (88) | 31.23%-51.35% |
| 2026 confirmation | v2 | 167 | 35.93% | 38.32% | 72.46% | 37.19% | 46.88% (96) | 37.21%-56.78% |
| 2026 confirmation | v3 | 167 | 36.53% | 38.32% | 100.0% | 36.53% | 48.03% (127) | 39.53%-56.65% |
| full | v1 | 757 | 33.42% | 38.71% | 69.75% | 36.36% | 46.72% (411) | 41.94%-51.55% |
| full | v2 | 757 | 34.87% | 38.71% | 72.52% | 38.25% | 49.41% (425) | 44.69%-54.15% |
| full | v3 | 757 | 39.23% | 38.71% | 100.0% | 39.23% | 51.3% (579) | 47.23%-55.34% |

## Paired McNemar (exact-class correctness, close-to-close): v3 vs v2

| Period | v3 right / v2 wrong | v2 right / v3 wrong | p-value |
|---|---:|---:|---:|
| 2023-2024 development | 47 | 23 | 0.0056 |
| 2025 validation | 36 | 21 | 0.0627 |
| 2026 confirmation | 26 | 11 | 0.0201 |
| full | 109 | 55 | 0.0 |

## Five-session diagnostic (+-0.50% FLAT band) — daily composite only

| Period | N | Majority baseline | Non-FLAT sign | n |
|---|---:|---:|---:|---:|
| 2023-2024 development | 338 | 50.59% | 54.78% | 272 |
| 2025 validation | 248 | 41.13% | 58.42% | 190 |
| 2026 confirmation | 167 | 49.7% | 49.65% | 141 |
| full | 753 | 43.96% | 54.73% | 603 |

> The weekly channel remains unvalidated; production continues to emit NO-VALIDATED-EDGE
> for next week. This table only records how the daily lean behaves over five sessions.

## Interpretation rules

- Next-open-to-close is the executable basis; no version shows a reliable edge there.
- Close-to-close gains are concentrated in the overnight-gap channel, which is not
  capturable at the signal date's close because Participant-OI is published after it
  (entry at next open loses the gap).
- Selection was done on 2023-2024 development from a bounded structural family; the
  2025/2026 columns were not used for fitting, but a fresh untouched forward window
  is still required before production promotion.
