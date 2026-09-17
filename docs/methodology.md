# Decode Methodology

This document is the **single source of truth** for how the engine decodes
FII / DII / Pro / Client positioning into a directional call. It currently
encodes a well-grounded default derived from standard institutional
option-chain + participant-OI reading.

> ⚠️ **Pending:** The user's YouTube-channel transcript PDF has not yet been
> provided. Once it is, this file will be updated to match that channel's exact
> decode rules, and the weights / thresholds in `src/fiidii/decode.py`
> (`DEFAULT_WEIGHTS`) and `src/fiidii/levels.py` will be tuned to reproduce it.

## 1. Data inputs (all free, official NSE)

| Dataset | Source | What it tells us |
|---|---|---|
| Participant-wise OI | `nsearchives.nseindia.com/content/nsccl/fao_participant_oi_DDMMYYYY.csv` | Long/short OI per group (Client, DII, FII, Pro) across index/stock futures & options |
| Participant-wise Volume | `.../fao_participant_vol_DDMMYYYY.csv` | Intraday aggression per group |
| FII/DII cash | `nseindia.com/api/fiidiiTradeReact` | Provisional cash buy/sell/net |
| Option chain | `nseindia.com/api/option-chain-indices?symbol=NIFTY` | Strike-wise OI, ΔOI, IV, price |
| Index quote | `nseindia.com/api/allIndices` | Spot level & change |

## 2. Core derived reads

1. **Index-future net long** `= FutureIndexLong − FutureIndexShort` per group.
   The cleanest directional footprint. Emphasis on the **day-over-day change**
   (fresh positioning) rather than the absolute level.
2. **FII long/short ratio** in index futures. >1 net-long bias; <1 net-short.
3. **Option writing bias** (Pro + FII): more **put writing** than call writing =
   support building (bullish); more **call writing** = resistance building (bearish).
4. **Client contra**: Client is the crowd; extreme Client positioning is faded.
5. **Cash flow confirmation**: FII/DII cash net confirms or contradicts F&O.

Each is scored in `[-1, +1]`, weighted (`DEFAULT_WEIGHTS`), normalised, and
combined into a composite bias with a confidence figure (magnitude × agreement).

## 3. Institutional levels (option chain)

- **Call walls** (highest Call OI) = resistance / supply zones.
- **Put walls** (highest Put OI) = support / demand zones.
- **Fresh OI addition** (largest ΔOI) = today's actionable institutional levels.
- **Max Pain** = gravitational pull into expiry.
- **PCR** = put/call OI ratio; extremes are contrarian.

For every level the engine emits an **expected reaction**:
> "At <level> price likely faces resistance; reject → reversal down;
>  15-min close above with follow-through → break → continuation up."

## 4. Predictions

- **Next day**: composite bias + immediate levels → direction + if/then scenarios.
- **Next week (Mon–Fri)**: blends today's read with a 5-day momentum of past
  composites; the week is expected to trade between the strongest put/call walls
  unless one is decisively broken.

## 5. Bias thresholds

| Composite | Label |
|---|---|
| ≥ +0.50 | STRONG BULLISH |
| +0.15 … +0.50 | BULLISH |
| −0.15 … +0.15 | NEUTRAL |
| −0.50 … −0.15 | BEARISH |
| ≤ −0.50 | STRONG BEARISH |

## 6. How to tune from the transcript

When the PDF arrives, map the channel's rules onto:
- `DEFAULT_WEIGHTS` — relative importance of each signal.
- `_bias_label` thresholds — how aggressive the labels are.
- `levels.derive_levels` — which OI columns / how many walls the channel uses.
- `predict.build_predictions` — the exact next-day/next-week logic & wording.
