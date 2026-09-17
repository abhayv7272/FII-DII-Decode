# Decode Methodology — Amit Dhamija's Participant-OI System

This is the **ultra-deep decode** of the channel's method, reconstructed line-by-line
from the two source PDFs:

- `full_transcript.pdf` — Amit Dhamija on the Upsurge Club podcast ("Most Retail
  Traders Never Look at This Setup"), the full conceptual explanation.
- `Market_Analysis_03_August_2026_Decoded-combined.pdf` — several days of the actual
  daily "Market Analysis Academy — Decoded" reports, showing the output format.

The engine in `src/fiidii/` implements exactly what is described below.

---

## 0. The one-line thesis

> The market is a **zero-sum game**. SEBI's own data shows **~90–93% of retail
> (Clients) lose**. That money flows to **Smart Money (FII + Pro + operators)**.
> So: **read what Smart Money is positioned for, fade what Retail is positioned
> for, and trade the next day / next move in Smart Money's direction — reacting at
> the institutional option-chain levels.**

"Operator" = anyone with enough capital to *move* (operate) the market. Not
necessarily one person — FIIs, Pro/proprietary desks, HNIs acting in the same
direction. They can keep secrecy (Pro desks trade direct-to-exchange via DMA), so
we can't see *who*, but the **NSE Participant-wise Open Interest** report shows us
*what* each group is doing. "Thanks to SEBI" this footprint is public.

---

## 1. The data (free, official NSE)

Google → **"NSE Participant Wise Open Interest"** → `nseindia.com/all-reports-derivatives`
→ download the **Participant wise Open Interest** file (also `fao_participant_oi_DDMMYYYY.csv`
from the archives). Data drops each evening ~7–8 PM.

Four participant categories, each with **6 instruments** (Long vs Short for each):

| # | Instrument | Meaning |
|---|---|---|
| 1 | **Future Index** Long / Short | Index futures directional bet |
| 2 | **Future Stock** Long / Short | Stock futures directional bet |
| 3 | **Option Index Call** Long / Short | Index call bought / **written (sold)** |
| 4 | **Option Index Put** Long / Short | Index put bought / **written (sold)** |
| 5 | **Option Stock Call** Long / Short | Stock call bought / written |
| 6 | **Option Stock Put** Long / Short | Stock put bought / written |

The four categories:

- **Client** = Retail (you and me). *Largest volume, but scattered / un-united.*
  **The contra indicator.**
- **DII** = mostly arbitrage funds (sell stock futures + buy cash). **Largely
  ignored** for F&O direction — not segregated by purpose, "we only get the numbers."
- **FII** = foreign institutions. F&O positions are **short-to-medium term** →
  drive the **positional / weekly / monthly** view.
- **Pro** = proprietary desks (DMA, fast, secret). Positions are **ultra-short term
  (1–2 days)** → drive the **next-day / very-short-term** view.

**FII + Pro = "Smart Money".**

---

## 2. The daily data sheet — TWO numbers per cell

He builds a sheet with, for every participant × instrument:

1. **"Positions Bought / Sold Today"** = the **net change today** (today's action /
   fresh positioning). *"आज क्या करके गए हैं।"*
2. **As-on-date total carry position** = the accumulated Long/Short still open
   (carried forward). *"As-on-date की total position."*

**Both matter.** Today's change tells you the immediate next-day story; the total
carry tells you the positional story and how "heavy" a group is leaned.

Always compare **Long vs Short** for each instrument to read the bias.

---

## 3. Reading the bias (the decode rules)

### 3a. Retail (Client) is the contra indicator — the core assumption
- *"Retailer bearish is generally good for market. That is the underlying assumption
  of this entire study."*
- Retail is "born a bull" — almost always net long futures, long calls, short puts.
- **When Retail is heavily bullish → upside is CAPPED** until those positions
  unwind. *"जब तक रिटेलर की पोजीशन हल्की नहीं होगी, बाजार बार-बार वापस आएगा — Sell on Rise."*
- **Reversal signal = Retail starts UNWINDING its bullish positions / builds fresh
  bearish.** *"जिस दिन रिटेलर की पोजीशन अनवाइंडिंग दिखे और बेयरिश पोजीशन बनती दिखे — वो साइन है कि रिवर्सल आ गया।"*
- Market rallies **only when Retail exits its long/buy positions.** *"बाजार में तेजी
  तभी आती है जब रिटेलर buy पोजीशन से एग्जिट कर जाता है।"*

### 3b. Option signals (options are the MOST important — rank #1)
Ranked by importance: **Index Options > Stock Options > Index Futures > Stock
Futures.** *"सबसे ज्यादा crucial — Options, particularly Index Options"* — most money,
most leverage, especially option **buying**.

For **Smart Money (FII + Pro)**:
- **Call BUYING (Call Long ↑)** = bullish.
- **Call WRITING (Call Short ↑)** = bearish / resistance building.
- **Put WRITING (Put Short ↑, i.e. put SELL)** = **bullish** (support building,
  downside capped). *"Put sell → downside capped for expiry."*
- **Put BUYING (Put Long ↑)** = bearish / hedging / expecting a dip.

For **Retail** the same actions are read **inverted** (contra):
- Retail put-selling = retail is bullish = **bearish** for market.
- Retail put-buying / call-selling = retail bearish = **bullish** for market.

### 3c. Fresh longs vs short covering (quality of the move)
- **Fresh Long buildup = real strength.** *"फ्रेश लॉन्ग जब add होंगे तब असली ताकत आएगी।"*
- **Short covering** (closing old shorts) while price rises = **not real strength
  yet** — the move happens in big gap-ups and fizzles. *"नए लॉन्ग नहीं ऐड कर रहे, बल्कि
  पुराने शॉर्ट्स क्लोज कर रहे हैं।"*
- So distinguish: is the bullishness from *new longs* (strong) or *short covering*
  (weak / gap-up-and-die)?

### 3d. Cash market flow (confirmation)
FII + DII cash net buying/selling confirms or contradicts the F&O footprint
(e.g. "strong institutional buying ~₹2,500 Cr combined from DIIs and FIIs").

### 3e. FII vs Pro weighting by horizon
- **Next-day / very short term** → weight **Pro** more (they create the near-term
  volatility; ultra-short view).
- **Positional (weekly / monthly)** → weight **FII** more, but **Pro must be
  supportive in the same direction**. Interestingly, *Pros themselves follow the
  FII positional view.*

### 3f. When FII and Pro are OPPOSITE (conflict → volatility)
If Smart Money is split (e.g. Pro put-long / bearish vs FII put-short / bullish),
expect a **one-sided move first, then reversal**:
- A **Gap Down** first → gives Pro room to book put profits AND gives FII shorts room
  to reverse → **dip then recovery** (contained). And vice-versa.
- Which side opens first depends on **overnight news flow** (US markets, Gift Nifty,
  geopolitics) — news before 9 AM overrides the data.

### 3g. Theta / expiry awareness
Near expiry, if Smart Money is **long options**, the market **must move their way
soon** or theta/weekend decay hurts them → raises the odds they defend/push that
direction (e.g. "if they bought calls, Nifty should close at par or higher, else
weekend decay kills the calls").

---

## 4. Institutional levels (option chain) & expected reaction

Levels are drawn from the **option chain** (OI + **change in OI**) plus the
channel's own "Institutional Levels" (support/resistance zones). Reading:

- **Highest Put OI / fresh Put writing = SUPPORT.** (e.g. 24,000 had highest Put OI
  16.6 L, +68k added today → strong support.)
- **Highest Call OI / fresh Call writing = RESISTANCE.**
- **Both OI and Change-in-OI matter** — fresh additions mark today's active levels.
- **Support broken & sustained → becomes RESISTANCE** (and vice-versa). *"Support
  अगर टूटी तो Resistance बन जाएगी।"*
- **Liquidity sweep:** below round-figure supports sit retail stop-losses; operators
  often **sweep just below** (e.g. below 24,000) to grab liquidity, *then* reverse up.
  A reversal after a liquidity sweep + institutional level + psychological level =
  big **confluence** (high-probability long).

### Expected reaction template
> At **<level>**: if price arrives and **holds / rejects** → **reversal**
> (bounce up from support / drop from resistance). If price gives a **decisive
> 15-min close through** with follow-through volume → **breakout continuation**
> (support→resistance flip or resistance→support flip).

---

## 5. Prediction assembly (next day + next week)

### Next-day (Pro-led)
1. Establish bias from the decode (§3), weighting **Pro** for the near term.
2. Build **three scenarios** — **Gap Up / Flat / Gap Down** — because we don't know
   the 9 AM news. For each: what should happen at the institutional levels.
3. Typical playbook when Smart Money is net bullish but Retail is bullish too:
   **"Sell on rise / dip-then-recover"** — a gap-down into support that reverses up
   is the high-probability pattern; a break below support (sustained, bearish
   volume) flips to downside.
4. State targets by the next resistance/support and note expiry/theta pressure.

### Next-week / positional (FII-led)
1. Track the **trend of the carry positions over several days** (longs building =
   big upside brewing; shorts building = downside; both mixed = range).
2. Weight **FII** (positional), require **Pro supportive**.
3. Big positional moves come only **2–3 times a year**; otherwise the week trades
   **between the strongest put wall (support) and call wall (resistance)** unless a
   wall breaks decisively.
4. Retail must **unwind its bullish positions** before a sustained up-leg; watch for
   that unwind as the trigger.

---

## 6. Output report format (matches the "Decoded" PDF)

1. **Market Review** — prior session recap + any anomaly; did institutional levels hold?
2. **Institutional Data & Expiry Setup** — FII/Pro stance (calls/puts/futures),
   Retail stance, Cash-market flow, fresh-longs vs short-covering note.
3. **Key Technical Levels** — Nifty 50 (and Bank Nifty): support / resistance /
   breakout targets, each with expected reaction.
4. **Next-Day Prediction** — bias + Gap Up/Flat/Gap Down scenarios.
5. **Next-Week / Positional Outlook** — Mon–Fri bias from the carry trend.
6. **Trading Strategy & Risk Management** — selective bias with strict SL; option
   buyers must NOT average losers; ≤10–15% capital per trade; wait for confluence.

---

## 7. Risk-management notes he stresses (included in the report footer)

- **Never average a losing option-buy** — retail's biggest mistake; premium decays
  to zero. Average at most once, only with a pre-set stop.
- **≤10–15% capital per trade**; scale in (e.g. 5% + 5%) with the stop-loss quantity
  auto-modified up on the second tranche.
- Always place the **stop-loss in the system immediately** (20–25 pts below the
  support level for a long).
- **Not investment advice** — educational decode of public data.

---

## 8. How this maps to code

| Concept | Code |
|---|---|
| 6 instruments × 4 participants parsing | `fetch.py::_parse_participant_csv` |
| Today's-change vs carry | `decode.py` (needs prev day; `store.py` history) |
| Retail contra, Smart Money = FII+Pro, options-first ranking, fresh-longs vs short-cover, FII/Pro horizon split, conflict detection | `decode.py::decode` + `DEFAULT_WEIGHTS` |
| OI + ΔOI levels, support/resistance flip, liquidity sweep, max pain, PCR | `levels.py::derive_levels` |
| Gap Up/Flat/Gap Down scenarios, next-day (Pro), next-week (FII, carry trend) | `predict.py::build_predictions` |
| 4+ section report | `report.py` |
