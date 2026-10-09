---
title: Simons / Renaissance — what actually transfers to a zero-IC, cost-dominated crypto bot
date: 2026-09-05
type: raw/research
method: 14-agent workflow (wf_39fff113-0c7), 6 research angles each adversarially
  verified by an independent refuter, then synthesised. Primary sources fetched and
  text-extracted, not summarised from search results. 1.58M subagent tokens.
full_output: raw/research/2026-09-05_simons_transferability_full_workflow_output.json
tags: [renaissance, medallion, grinold, cost, breadth, horizon, folklore-correction]
---

# Simons transferability — the actionable delta

**Provenance legend as the agents used it:** `[K]` read directly · `[K†]`
verbatim-confirmed by a named adversarial verification stream · `[I]` derived ·
`[UNKNOWN]` no citation exists and we say so.

**Citation warning carried up from the run:** PSI line/page offsets are NOT
citable — three verification passes produced three different numberings of the
same PDF and the shared extraction was mutating mid-run. **Cite PSI by needle
string, never by offset.**

---

## 0. THE INVERSION — the headline

`IR = IC · √BR`. Measured IC here is indistinguishable from zero and per-trade
net is negative. **Every RenTec property that scales the business — breadth,
turnover, leverage, instrument count — is a multiplier on a number that is
≤ 0.** The largest structural gaps between this system and Medallion are
therefore the *lowest*-EV things to close. The ranking is deliberately inverted
against the folklore ordering.

The one sentence everybody quotes says less than it is made to say. RenTec's
joint statement to the Senate PSI, printed p.2, verbatim `[K†]`:

> "the model's recommendations are expected to be profitable only slightly more
> often than not, the rate of return obtained by applying the recommendations to
> an unleveraged portfolio would be **very small**."

It says **nothing about transaction costs** `[K†]`, and it sits inside a filing
whose legal purpose was to establish a **non-tax business purpose for leverage**
— RenTec had a direct adverse interest in characterising the unleveraged return
as small. It is not evidence that weak signals clear cost. It is evidence that
RenTec said they *don't*, without leverage.

## 1. THE FOLKLORE CORRECTIONS THAT SURVIVED VERIFICATION

- **"RenTec solved cost with long horizons" — REFUTED by the same document,
  five times** `[K†]`: *"Many of those trading positions lasted minutes, and the
  overall composition of the securities basket changed on a second-to-second
  basis"*; *"some of which lasted only seconds"*; Barclays DMA *"The trade is
  done within milliseconds"*; internal memo, *"very high frequency trader."*
  The holding-period chart cited against this is a **RenTec-prepared tax-lot
  table in a long-vs-short-term-gain proceeding**, top-coded at 1 year, printed
  as an excerpt whose finest bucket is an unresolved **74.72% residual below 3
  months**. It cannot bound position lifetime downward at all.
- **"They never override the models" — not the record.** Brown, under oath, on
  human involvement: *"It could also have an impact on what positions are bought
  and sold. … That is correct."* — four lines above the model-cadence answer
  everyone quotes `[K†]`.
- **"Colocation" — 0 occurrences in the PSI report** `[K†, grep]`. The
  millisecond execution documented there is *Barclays' DMA infrastructure*, not
  a RenTec asset. Nothing to buy.
- **"90 PhDs / 40TB per day / 50,000 cores"** — undated marketing copy on
  rentec.com, no as-of, corroborated by no filing `[K†]`. Not a target.
- **"Medallion is just the tax structure" — WRONG**, and this correction
  survived promotion: the 39.6%→20% conversion sits at the **investor's**
  return, not inside the fund, so it does not inflate the gross/net series
  `[K†]`.
- **PSI's own breadth arithmetic is internally inconsistent** and three
  independent passes caught it: *"100,000 to 150,000 trades per day **with each
  bank**"* vs a *"combined estimated average of 26–39 million trades per year"*
  — and 100,000 × 260 = 26.0M exactly, i.e. **PSI computed its "combined" figure
  from ONE bank's rate.** Every orders-per-round-trip ratio built on it is
  killed.
- **A FABRICATED QUOTATION is circulating in this corpus.** *"Predictors with
  slower mean reversion (alpha decay) get more weight"*, attributed to Gârleanu
  & Pedersen, appears **nowhere** — the paper was never fetched and the phrase
  exists in no artifact or vault page `[K†]`. Anything downstream is `[UNKNOWN]`.
  See [[concepts/tautological-instrument]] and [[concepts/no-orphan-claims]].

## 2. THE COST PROBLEM — the levers, priced

Gap: gross 0.0255 / cost 0.0825 = 0.30909 → **gross must rise 3.24× or cost
fall 69.09%** for net = 0 `[I]`.

**2a. Maker rebates are STRUCTURALLY UNAVAILABLE. Stop considering them.**
Kraken spot maker floors at **0.0 bps**; there is **no negative-maker row at any
volume** `[K, core/venue_fees.py:26-54]`. Combined with invariant 3 (Kraken sole
venue) the lever does not exist at any effort level.

**2b. The whole fee ladder does not close the gap** `[I]`, priced against the
only measured non-fee overrun on record (+21.17 bps):

| fee row | round trip | +21.17 non-fee | vs booked | reachable |
|---|---|---|---|---|
| booked 22/38 | 60 | 81.17 | — | **fictitious row** |
| 20/35 (current volume) | 55 | 76.17 | −6.2% | now |
| 12/22 | 34 | 55.17 | −32.0% | 5.7× volume |
| **0/10 (venue floor)** | 10 | 31.17 | **−61.6%** | **572× volume** |
| **required** | | | **−69.1%** | — |

**Kraken's cheapest published row — taken as a free gift, ignoring that it needs
572× the account's measured volume — still does not reach break-even.** And
climbing the ladder means trading more at −$0.057/trade.

Also: **22/38 is not a row Kraken publishes** (sits between 20/35 and 25/40,
matches neither); at the measured $17,482 30-day volume `binding_row` resolves to
**(20.0, 35.0)** `[I]`. This is the **fourth** struck-literal fee error in the
register (25/40 → 40/80 → 22/38).

**2c. The horizon case must stand on OUR numbers, and there it is strong and
unfinished.** Median winner hold **0.91 h** against a 0.71% round trip; **MFE
median 0.18% / p90 0.55%** against ~0.65–0.71% cost — *at its single best
instant, gross, the median trade never moves far enough to cover its own cost*.
Shadow win rate rises monotonically **22.3% → 30.4% → 35.4%** at 108 → 216 → 432
bars and **had not plateaued**. The pre-registered 48-combination bracket grid
found no surviving geometry — **but 432 bars is 1.5 days and the cost arithmetic
points at 6.9–120 days. The search space and the answer do not overlap.**

## 3. THE TWO FINDINGS AIMED AT OUR OWN NUMBERS

**(a) The stipulated cost is partly TAUTOLOGICAL.** *"In paper the fee component
of a round trip is the configured constant, by construction"* — the hedge-thrash's
294 fills read **exactly 40.00 bps per fill**, `pretrade.taker_fee_bps` to the
digit `[K, cost-truth.md:71-83]`. Slippage and spread are informative; **the fee
number is not a measurement.** This is [[concepts/tautological-instrument]]
applied to cost, and it is the single largest caveat on the whole diagnosis.

Compounding it: the cost instruments are **blind to 41% of round trips** —
`breakeven_test.py:126` filters `purpose == "entry"`, seeing 235 round trips and
**59.23 of the 382.59 in fees actually paid**; a further **6.24 in fees never
reach `fills.csv` at all**. And **60.6% of fills are TAKER** on a book whose
entire cost thesis is passive execution.

**(b) GROSS SIGN IS NOT RECONCILED ACROSS ERAS — this is open.** The session
stipulated gross **+$0.0255/trade**. The vault holds, on other corpora: mean
gross **−0.0501% per fill** (n=217); whole-book gross **−11.66 before any fees**
over ~250 closed positions; **median gross −0.0303%** over 394 corrected round
trips where `breakeven_test.py` reports **+0.0505%** over its 235. Different
eras, different corpora, **opposite signs**, and they may not be pooled
(accrual moratorium, CLAUDE.md 7(c)). **Whether this book has positive gross at
all is OPEN.**

## 4. THE THREE CHEAPEST EXPERIMENTS — all SAFE, a dependency chain

Honest cost → the horizon that clears it → whether the selector can find it.
None resets the era-6 cohort. *(Booking a corrected fee IS cohort-resetting and
needs operator adjudication; measuring the discrepancy is not.)*

- **E1 — cost-instrument truth.** Reconcile booked 22/38 against
  `binding_row($17,482)` = 20/35; re-measure realized round-trip bps and
  maker/taker mix on the FULL population, entry *and* hedge legs.
  **Null:** booked fee is a published row, mix is maker-dominant, realized ≈
  configured → the fee lever retires permanently and 100% of −$0.057 is a
  gross-edge problem.
- **E2 — empirical MFE/MAE-vs-horizon curve, entry-agnostic, per pair**, 12 bars
  → ≥30 days, **no Gaussian assumption** (observed barrier touch 3.6% vs ~0.07%
  predicted — ~50× off; every √h break-even horizon in circulation inherits that
  dead premise).
  **Null:** median MFE never crosses ~40 bps at any h on any of the 7 pairs →
  these instruments cannot pay this rake at any horizon regardless of skill. A
  clean, publishable kill.
- **E3 — random-entry MFE-percentile control re-run at E2's horizon.** Harness
  exists (`8062f46a`, n=51 vs 200 matched controls each; found mean MFE
  percentile **0.516 [0.439, 0.594]** at the short horizon only). This is the
  **economic-space** analogue of the permutation-importance result, and it tests
  the flipped anti-predictive rule in MFE space rather than the P(TP) space
  where it stalled at 0.4851 [0.4277, 0.5373].
  **Null:** CI covers 0.500 at the long horizon too → the "is there an
  exploitable edge" question closes, and the honest next move is instrument
  choice or stop, not another model.

## 5. WHAT CANNOT TRANSFER — stop paying for it

Leverage **11.7:1–16.8:1 with a non-recourse downside cap** (prime-brokerage
ceiling was 2:1; *"We know of no other way to obtain this combination of leverage
and loss protection"*) — Kraken spot has no such instrument, and **leverage on
negative expectancy is an accelerant**. The tax structure. **Cross-sectional
IC**: every published "tradeable factor IC 0.014–0.066" is a *cross-sectional* IC
across 1000–3000 names at one date; ours is a **time-series** IC on 7 correlated
pairs, and conflating them is named as Grinold's founding error `[K†]`. The
"breadth is not the binding constraint" claim is likewise scoped to N=1000–3000
and the same paper says the opposite below N=500.

**Our breadth:** 7 pairs, six of them crypto ≈ one factor. Effective breadth
`K_eff = K/(1+(K−1)ρ)`: at ρ=0.8 → 1.2, so **√BR ≈ 1.1**. Breadth buys ~10% and
multiplies a negative. **The measured cross-pair ρ is `[UNKNOWN]` and is a
one-liner nobody has run.**

## 6. THE ONE PLACE OUR MEASURED NON-NULL MIGHT LIVE

The "hard ceiling at `ic/√ρ`" for combining correlated signals is **KILLED**
`[K†]`: with *unequal* ICs, correlated signals are exploitable as a **spread via
negative weights** — explicit counterexample K=2, ρ=0.9, IC (0.02, −0.01) gives
IR **0.0673** against a claimed 0.0211 "ceiling". A reliably **negative** IC is a
signal. Our best grid survivor is genuinely anti-predictive (direction AUC
0.4634 / 0.4806, day-block CIs excluding 0.5). That is the one structural gap
worth closing — a covariance-aware signal *portfolio* with negative weights,
against the current single scalar meta-probability. It is also model-side work,
which is **FROZEN** under the 2026-08-10 adjudication.

## 7. UNKNOWN

RenTec's cost per trade, fee schedule, or net-of-cost IC: **never disclosed in
any of these documents** `[UNKNOWN]`. The only cost data are that costs were
itemised and borne, and that the bank took 20–25% of the premium as financing.
No bot-side statistic stipulated to the agents was independently verified by
them — all `[UNKNOWN]` to their verification.
