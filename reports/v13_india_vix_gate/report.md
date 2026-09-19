# V13 India-VIX gate — daily next-session combination test

> **Research only; production decoder unchanged.** The India VIX source is a
> third-party derived historical dataset pinned in `historical/manifest.json`.
> It must not be treated as independently verified production data.

## Question and timing

Can the India VIX state known at the close of OI signal day **D** add a robust
gate to the v3 OI lean for D+1?  Every VIX feature here is calculated only from
D and earlier.  No D+1 VIX, D+1 high/low, outcome/hit field, or forward-filled
missing value is used.

- VIX-aligned signal rows: **745**
  (2023-08-08 to 2026-08-24).
- VIX source coverage excludes 12 v3 rows;
  those are not imputed.
- Development: 2023--24; validation: 2025; confirmation: 2026 through the
  available VIX cutoff. Flat band: ±0.15%.
- Strategies: VIX standalone direction; v3 only in a VIX state; and v3/VIX
  directional agreement. Threshold orientation and quantile are fitted on the
  development split only.
- Promotion gate: **85%** in *both* later splits with at
  least **20** calls each.

## Ungated v3 reference

| outcome | strategy | period | n | coverage_pct | exact_pct | sign_n | sign_pct |
|---|---|---|---|---|---|---|---|
| close_to_close | v3_ungated | dev2023_24 | 341 | 100 | 44.87 | 263 | 58.17 |
| close_to_close | v3_ungated | val2025 | 247 | 100 | 43.32 | 195 | 54.87 |
| close_to_close | v3_ungated | confirm2026 | 157 | 100 | 48.41 | 129 | 58.91 |
| open_to_close | v3_ungated | dev2023_24 | 341 | 100 | 38.42 | 248 | 52.82 |
| open_to_close | v3_ungated | val2025 | 247 | 100 | 41.3 | 201 | 50.75 |
| open_to_close | v3_ungated | confirm2026 | 157 | 100 | 38.22 | 120 | 50 |

## Result

- Rules passing the 85% exact gate: **0**.
- Rules passing the 85% non-FLAT sign gate: **0**.

The open-to-close section is the executable diagnostic because D's OI/VIX data
is only known after D's market close. Close-to-close includes the overnight gap,
so it cannot by itself prove a tradeable night-before edge.

## Best candidates with sample guards

| outcome | strategy | feature | mode | quantile | rho_dev | dev2023_24_n | dev2023_24_exact_pct | dev2023_24_sign_pct | val2025_n | val2025_exact_pct | val2025_sign_pct | confirm2026_n | confirm2026_exact_pct | confirm2026_sign_pct | min_holdout_exact_pct | min_holdout_sign_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| close_to_close | v3_vix_agree | vix_ret20 | upper | 0.85 | 0.02854 | 22 | 68.18 | 83.33 | 20 | 65 | 76.47 | 24 | 66.67 | 69.57 | 65 | 69.57 |
| close_to_close | v3_vix_agree | vix_ret20 | upper | 0.75 | 0.02854 | 40 | 47.5 | 59.38 | 27 | 59.26 | 69.57 | 25 | 64 | 69.57 | 59.26 | 69.57 |
| close_to_close | v3_vix_agree | vix_ret20 | upper | 0.8 | 0.02854 | 31 | 51.61 | 64 | 26 | 57.69 | 68.18 | 25 | 64 | 69.57 | 57.69 | 68.18 |
| close_to_close | v3_vix_gate | vix_ret20 | upper | 0.85 | 0.02854 | 52 | 50 | 60.47 | 37 | 56.76 | 65.62 | 39 | 64.1 | 65.79 | 56.76 | 65.62 |
| close_to_close | v3_vix_agree | vix_high | both | 0.925 | 0.03204 | 25 | 64 | 84.21 | 31 | 54.84 | 70.83 | 30 | 56.67 | 62.96 | 54.84 | 62.96 |
| close_to_close | vix_direct | vix_ret20 | upper | 0.85 | 0.02854 | 52 | 55.77 | 67.44 | 37 | 54.05 | 62.5 | 39 | 56.41 | 57.89 | 54.05 | 57.89 |
| close_to_close | v3_vix_gate | vix_high | both | 0.95 | 0.03204 | 36 | 61.11 | 73.33 | 50 | 54 | 67.5 | 29 | 62.07 | 66.67 | 54 | 66.67 |
| close_to_close | v3_vix_gate | vix_close | both | 0.95 | 0.04215 | 37 | 56.76 | 67.74 | 52 | 53.85 | 70 | 33 | 54.55 | 64.29 | 53.85 | 64.29 |
| close_to_close | v3_vix_gate | vix_ret20 | upper | 0.9 | 0.02854 | 35 | 51.43 | 62.07 | 28 | 53.57 | 65.22 | 34 | 61.76 | 63.64 | 53.57 | 63.64 |
| close_to_close | v3_vix_agree | vix_ret20 | both | 0.75 | 0.02854 | 74 | 39.19 | 53.7 | 75 | 53.33 | 64.52 | 56 | 58.93 | 64.71 | 53.33 | 64.52 |
| close_to_close | vix_direct | vix_ret20 | upper | 0.8 | 0.02854 | 69 | 47.83 | 60 | 45 | 53.33 | 61.54 | 42 | 54.76 | 57.5 | 53.33 | 57.5 |
| close_to_close | v3_vix_agree | vix_ret20 | upper | 0.7 | 0.02854 | 51 | 45.1 | 60.53 | 32 | 53.12 | 70.83 | 26 | 61.54 | 66.67 | 53.12 | 66.67 |
| close_to_close | v3_vix_agree | vix_close | both | 0.8 | 0.04215 | 69 | 49.28 | 62.96 | 72 | 52.78 | 63.33 | 49 | 53.06 | 63.41 | 52.78 | 63.33 |
| close_to_close | v3_vix_agree | vix_z20 | lower | 0.8 | 0.0336 | 22 | 36.36 | 66.67 | 40 | 52.5 | 65.62 | 21 | 61.9 | 72.22 | 52.5 | 65.62 |
| close_to_close | vix_direct | vix_ret20 | upper | 0.75 | 0.02854 | 86 | 46.51 | 57.97 | 48 | 52.08 | 59.52 | 43 | 53.49 | 56.1 | 52.08 | 56.1 |
| close_to_close | v3_vix_agree | vix_open | both | 0.8 | 0.04749 | 69 | 55.07 | 69.09 | 73 | 52.05 | 61.29 | 49 | 53.06 | 63.41 | 52.05 | 61.29 |
| close_to_close | v3_vix_agree | vix_ret20 | both | 0.85 | 0.02854 | 40 | 47.5 | 59.38 | 52 | 51.92 | 65.85 | 45 | 60 | 64.29 | 51.92 | 64.29 |
| close_to_close | v3_vix_agree | vix_z20 | both | 0.8 | 0.0336 | 50 | 48 | 68.57 | 58 | 51.72 | 65.22 | 37 | 64.86 | 72.73 | 51.72 | 65.22 |
| close_to_close | v3_vix_agree | vix_ret20 | both | 0.8 | 0.02854 | 58 | 41.38 | 55.81 | 66 | 51.52 | 62.96 | 53 | 58.49 | 64.58 | 51.52 | 62.96 |
| close_to_close | v3_vix_agree | vix_range_mean20 | both | 0.8 | 0.03046 | 72 | 45.83 | 63.46 | 70 | 51.43 | 58.06 | 30 | 53.33 | 59.26 | 51.43 | 58.06 |
| close_to_close | v3_vix_agree | vix_high | both | 0.8 | 0.03204 | 70 | 50 | 63.64 | 78 | 51.28 | 61.54 | 52 | 53.85 | 63.64 | 51.28 | 61.54 |
| close_to_close | v3_vix_agree | vix_z20 | both | 0.85 | 0.0336 | 36 | 50 | 72 | 43 | 51.16 | 66.67 | 27 | 59.26 | 66.67 | 51.16 | 66.67 |
| close_to_close | v3_vix_gate | vix_ret20 | upper | 0.8 | 0.02854 | 69 | 42.03 | 52.73 | 45 | 51.11 | 58.97 | 42 | 61.9 | 65 | 51.11 | 58.97 |
| close_to_close | v3_vix_agree | vix_ret20 | upper | 0.6 | 0.02854 | 68 | 50 | 66.67 | 47 | 51.06 | 64.86 | 31 | 61.29 | 70.37 | 51.06 | 64.86 |

## Decision

No VIX feature is wired into the production score unless it clears the stated
gate and then survives a new forward period from an independently verified VIX
source. In all other cases VIX may be displayed as qualitative risk context
only, never as a claimed 85% direction signal.
