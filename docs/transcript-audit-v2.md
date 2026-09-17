# Transcript audit for decoder v2

This is the source audit behind `src/fiidii/decode.py`. It records what was
actually present in the supplied material, what v1 mistranslated or omitted, and
which parts can and cannot be tested with the available history.

## Scope and citation convention

The complete supplied sources were read, not just the earlier methodology
summary:

- `full_transcript.pdf` — 21 pages, approximately 01:13:34 of foundational
  discussion.
- `Market_Analysis_03_August_2026_Decoded-combined.pdf` — 182 pages containing
  27 dated analysis sections and their decoded summaries.

Citations below use **source / PDF page / media timestamp**. The PDFs contain
Hindi-English automatic transcription, so spelling is noisy; page and timestamp
ranges are provided to make the evidence independently findable. The cited
language is paraphrased rather than treated as a precise mathematical formula.

## What a complete reread changed

The recurring method is not “net participant OI predicts tomorrow's close.” It
is a hierarchy:

1. Separate today's additions and closures from as-on-date carry.
2. Identify who acted: Pro for the very short term, FII for multi-session
   context, Client mainly as a contrary/crowding read, and not DII F&O for
   direction.
3. Identify the instrument and horizon. Index calls and puts are the immediate
   NIFTY read; stock derivatives do not identify which stock or sector drove an
   aggregate number.
4. Read calls and puts together and preserve gross two-sided positions instead
   of trusting a small net in isolation.
5. Treat FII/Pro opposition as a path/reversal problem whose first move depends
   on information available before the open.
6. Build gap-up, flat, and gap-down scenarios around option-chain and
   institutional levels.
7. Enter only after price confirms the relevant plan; switch to Plan B when the
   level breaks. The OI view is context, not an unconditional order.

That hierarchy is repeated across the foundational interview and the dated
walk-throughs. V1 implemented parts of it as an unconditional weighted class,
which was too strong a claim.

## Evidence ledger and v1 mapping errors

| Rule or qualifier recovered from the sources | Transcript evidence | V1 mapping problem | V2 treatment |
|---|---|---|---|
| **Today's activity and carried position are separate questions.** | Foundational, pp. 8–9, 00:27:00–00:30:34, explains the participant-wise daily buy/sell column, prior carry, current carry, and the long/short comparison needed to split a net change. | `_instrument_biases()` reduced the change in `long-short` to one number. It could not distinguish a fresh long from short covering, or a fresh short from long unwinding. | `_fresh_pressure()` decomposes all four actions. Carry is calculated independently in `participant_carry_reads`. |
| **Fresh positions have more conviction than closures.** | Foundational, p. 9, 00:28:53–00:29:25, says mostly closing old shorts is not the same as adding new longs; 3 Aug, p. 4, 00:09:35–00:09:59, explicitly says real move strength comes when fresh longs are added. | V1 gave both mechanisms the same directional score because both produce the same net change. Its `move_quality` text noticed the distinction, but the distinction did not alter the composite. | Additions get full weight and closures get 0.5 weight. The 0.5 is a declared engineering translation of “weaker,” not a number quoted by the speaker. |
| **Absolute contract counts need market context.** | Foundational, pp. 7–9, 00:22:13–00:30:34, repeatedly compares long, short, daily, and total carried quantities; pp. 12 and 17, 00:40:59–00:41:42 and 00:58:42–01:00:18, warns that both large gross legs and both OI/change-in-OI matter. | V1 divided by hard-coded contract scales such as 30,000 or 120,000. Those scales age as participation and contract structure change. | Each quality-adjusted flow is divided by current one-sided market OI for that instrument, then smoothly bounded. This is a stable relative-activity translation; the exact scale constants remain implementation choices. |
| **Index options are the first-priority short-horizon read.** | Foundational, p. 12, 00:39:32–00:40:53, ranks options—especially index options—first because leverage and capital are concentrated there. 1 Sep, p. 59, 00:10:19–00:10:38, says index calls/puts affect the next day immediately. | V1 blended index options, stock options, index futures, and stock futures into every NIFTY next-day participant score. | The NIFTY daily score uses index calls, index puts, and index futures only, weighted 40/40/20. The exact proportions operationalize the stated priority; they are not transcript percentages. |
| **Calls and puts must be read together.** | Foundational, pp. 9–10, 00:31:38 onward, rejects forming a view from calls alone and moves to puts; p. 18, 01:02:00–01:02:50, again requires both for the path and target. | V1 included both, but simple averaging could conceal why opposing large legs canceled. It exposed only rounded directional instrument scores. | V2 exposes participant fresh reads, carry reads, and the four-way decomposition. Cancellation lowers or removes the directional edge rather than being narrated as high confidence. The raw archive still cannot reveal strike-level hedge pairings. |
| **A small net can hide two large opposing books.** | Foundational, p. 12, 00:40:59–00:41:42, notes that Pro's roughly 29,000 net masks roughly 315,000 puts bought and 285,000 sold and says the large gross positions still matter. | V1 scored only net changes and could imply that a small net meant little positioning. | V2 retains decomposed long/short additions and closures in the result. It does not claim to identify multi-leg strategies; when opposing pressure cancels, the directional output weakens or abstains. |
| **Aggregate stock-option OI is not a clean NIFTY direction.** | 3 Aug, p. 4, 00:12:35–00:13:00, says large Client stock-call buying may matter but the affected sector cannot be identified. 1 Sep, p. 59, 00:10:19–00:10:38, contrasts immediate index-option impact with stock-call impact that may arrive two or three days later. | V1 let stock calls, stock puts, and stock futures manufacture a next-day NIFTY direction. | Stock derivatives remain visible diagnostics. They contribute zero to the next-day NIFTY score. Stock futures are retained only in unvalidated positional carry context. |
| **Pro has the very-short-term edge; FII owns the longer horizon.** | Foundational, pp. 4–5, 00:11:30–00:13:14, introduces FII as roughly one-to-two-week and Pro as one-to-two-day positioning. pp. 18–19, 01:03:26–01:04:17 and 01:09:05–01:10:33, says Pro has more relevance for tomorrow while FII gets more importance for positional views and Pro should support it. | V1's 50/30/20 next-day and positional blends were plausible, but mixed stock/index inputs and an unconditional weekly class blurred the stated horizons. | Daily Smart Money is Pro-led, with Pro:FII set to 2:1, then blended 80% Smart Money / 20% contra-Client. These exact ratios are fixed operational translations, not spoken percentages. Positional carry is FII-led context only. |
| **DII F&O is contaminated by arbitrage.** | Foundational, p. 5, 00:13:20–00:14:20, says DII cash holdings and hedges make F&O difficult to decode and it is usually not used; p. 9, 00:28:42–00:28:47, repeats that it is not very important. | V1 set DII weight to zero correctly, but the previous methodology could still make the four groups look symmetric. | DII remains reported for transparency and has exactly zero directional weight. |
| **Retail is a contrary/crowding condition, not the primary driver.** | Foundational, pp. 8 and 11, 00:25:49–00:26:36 and 00:38:32–00:39:23, describes following Smart Money and says crowded Retail bullish positions can cap upside until Smart Money improves. | V1 contra-adjusted Client correctly, but its unconditional class did not communicate that Retail crowding can cap or delay a move rather than mechanically reverse it tomorrow. | Client is a secondary contra input. `retail_note` describes cap/unwind conditions; every directional lean remains conditional on price. |
| **FII and Pro opposition is not a safe closing-direction forecast.** | Foundational, pp. 12–13, 00:42:13–00:45:14, describes one side benefiting first and then a containment/reversal attempt; 11 Sep, pp. 25–26, 00:08:19–00:10:58, maps conflicting option/futures books to a possible gap/first-half rise and later wobble. | V1 lowered a heuristic confidence value but still published a directional next-day prediction and even narrated an expected reversal. | Strong fresh-index disagreement produces `WAIT_FOR_REVERSAL_CONFIRMATION`. The forced class is kept only so v1/v2 research metrics remain comparable. |
| **Pre-open news determines the first path and may override EOD data.** | Foundational, p. 13, 00:43:05–00:44:12, says the order depends on news flow and news can completely override the setup once; pp. 16–17, 00:58:42–01:00:18, requires gap-down, flat, and gap-up scenarios. | V1 emitted a single direction from EOD inputs, although its narrative also generated three scenarios. It did not mark the contradiction between a forced class and unknown opening information. | The daily class is explicitly an OI-only research lean. Production actionability is conditional, and the plan branches by opening state. Gift Nifty/news cannot alter the score unless those inputs are actually supplied and validated. |
| **A level and confirming candle are entry requirements; a broken level activates Plan B.** | Foundational, p. 15, 00:50:51–00:52:15, requires bullish price recovery before entry and a stop/backup plan if support fails. 6 Aug, pp. 17–18, 00:09:26–00:12:17, requires a bullish or bearish 15-minute candle and explicitly discards the bullish bias below support. 23 Jul, pp. 88–89, 00:12:12–00:14:04, again requires a 10–15-minute candle above resistance. | V1's report could be read as an entry recommendation even when no level or intraday candle was present. A high absolute score was labelled “confidence.” | Every v2 daily direction is `CONDITIONAL_*`, `NO_DIRECTIONAL_EDGE`, or a wait state. `confidence` is retained only for API compatibility and is labelled deterministic setup strength, never probability. |
| **Expiry changes interpretation.** | 1 Sep, pp. 59–60, 00:09:50–00:12:10, warns that expiry can conceal or shift option positions, gives extra weight to levels on the next day, and uses Gift Nifty as an important clue. The 27 dated analyses repeatedly separate fresh expiry action, roll/closure, and carry. | V1 treated every session identically and had no expiry calendar or roll detection. | V2's fresh-versus-closure split reduces one error source, but it does **not** claim expiry/roll awareness. Expiry regime remains an unavailable-input limitation and a reason to require confirmation. |
| **Positional setups are sparse and require multi-session alignment.** | Foundational, pp. 18–19, 01:09:05–01:10:55, makes FII primary and Pro supportive for longer views. The dated analyses repeatedly preserve a positional level while changing the immediate plan as price/news evolves. | V1 converted one day's positional composite plus a five-day average into a next-week direction on every run. | A transcript-grounded carry/trend candidate was evaluated separately. It failed the 2026 confirmation period, so production v2 returns `NO-VALIDATED-EDGE`; carry and an unvalidated research lean remain visible as context. |

## Conditions intentionally not converted into score

The dated analyses use several inputs that are absent from the historical replay:

- strike- and expiry-matched option-chain snapshots, including total OI and
  change in OI;
- FII/DII cash-market flow;
- Gift Nifty, global markets, crude, yields, war/news and scheduled events;
- institutional or technical levels known at the signal time;
- 10–15 minute candles, volume, retests and the order in which daily highs/lows
  occurred;
- expiry/roll mapping and the identity of stocks behind aggregate stock-option
  numbers.

V2 does not silently substitute present-day values or synthetic proxies for
these missing histories. Live cash and option levels can be shown as
**confirmation**, but they do not modify the validated OI-only class. This keeps
production behavior aligned with what was actually replayed.

The Participant-OI report itself aggregates NIFTY, Bank Nifty, Fin Nifty,
Midcap Nifty and expiries. This is stated in the foundational source, p. 7,
00:22:13–00:22:39, and is repeated in the dated walk-throughs (for example,
3 Aug, pp. 3–4, 00:09:06–00:09:30). Consequently, even v2's “NIFTY” score is an
aggregate participant association, not a pure NIFTY-contract reconstruction.

## Numeric rules: evidence versus engineering choices

The transcripts provide priorities and qualitative comparisons, not a complete
formula. V2 therefore distinguishes source rules from fixed engineering choices:

| Constant | Value | Status |
|---|---:|---|
| Addition weight | 1.0 | Reference unit for the transcript's stronger/fresh action. |
| Closure weight | 0.5 | Conservative operational meaning of “weaker”; not spoken. |
| Index flow scale | 2.5% of current market OI | Relative-activity engineering scale; replaces unstable contract counts. |
| Daily instruments | Calls 40%, puts 40%, futures 20% | Fixed translation of “both options first, futures secondary”; not spoken percentages. |
| Daily participants | Pro 53.33%, FII 26.67%, contra-Client 20%, DII 0% | Fixed translation of Pro > FII for tomorrow, Smart Money primary, Client secondary; only DII's zero and the hierarchy are directly grounded. |
| Research class boundary | ±0.10 | Selected and frozen on the 2023–2024 development partition before locked later-period evaluation. |
| FII/Pro conflict floor | 0.15 per side | Fixed materiality guard, not a transcript threshold. It controls actionability, not the forced research class. |
| Setup strength | `abs(score) / 0.45`, capped at 100 | Display intensity only. It is not probability and did not remain monotonic in 2026. |

These values must not be retuned on validation/confirmation merely to improve a
headline percentage. A future v3 should be declared in advance and validated on
new untouched data.

## Contradictions and unresolved ambiguity

1. **Directional net versus gross hidden books.** The source often gives a net
   view, but also warns that large gross long and short books matter. Public
   Participant-OI cannot identify which legs belong to one strategy. V2 exposes
   decompositions and avoids a hedge claim.
2. **Retail as reliable contrary signal versus perpetually bullish Retail.** If
   Retail is usually bullish, its level alone has little timing information. V2
   uses only fresh, relative Client activity and gives it a minority role.
3. **OI prediction versus news override.** The source discusses tomorrow's
   likely path but also says pre-open news chooses or overrides that path. V2
   resolves this by separating a forced research lean from actionability.
4. **Immediate index signal versus expiry obfuscation.** Index options are called
   immediate, while expiry sessions are described as deliberately difficult to
   decode. V2 does not pretend to resolve this without dated chain/expiry data.
5. **Longer-horizon FII context versus daily risk management.** A positional view
   may remain intact while the immediate plan reverses below a level. Therefore
   positional carry cannot be used as permission to average or ignore a daily
   stop.

## Validation consequence

The revised mapping improved the full forced close-to-close three-class result
from 36.20% to 37.91%, but 37.91% is still below the 42.14% majority baseline.
The executable next-open-to-close sign result remained approximately chance,
and higher setup-strength cutoffs deteriorated in the 2026 confirmation period.
The five-session candidate also failed confirmation.

Accordingly, the transcript reread justifies correcting v1's semantics, but it
does **not** justify claiming a reliable or profitable forecasting edge. Exact
period, basis, coverage, confidence-interval and rejection evidence is published
in `reports/backtest_v2_2023-08_to_2026-09/report.md`.
