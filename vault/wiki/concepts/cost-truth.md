---
title: Cost Truth
category: concept
summary: "Measuring realized round-trip cost against configured cost and issuing a DANGEROUS verdict when configuration under-prices reality — and, as of 2026-08-07, the fee constants themselves are falsified: 25/40 bps matches NO row of Kraken's current schedule (Tier 1 is 40/80), the 'overstating is the safe direction' premise is inverted for a fresh account, the reconciler built to catch it is dead in DRY_RUN, and the correction is SEQUENCED behind the h432 verdict because the constant is load-bearing in the label definition. BOOK-LEVEL COST TRUTH 2026-08-09: the gate has always compared cost against CONFIGURATION and never against the edge the cost is paid to capture — that ratio is 32.8x (gross −11.66 before any fees vs 382.59 of fees, 100% of the −394.25 loss is costs), which makes the falsified constants matter more and cost work provably insufficient; plus a 6.24 (1.6%) gap that makes every fills.csv cost analysis read optimistic. AND THE INSTRUMENTS ARE BLIND, same day: BOTH cost tools filter out the hedge leg without a skip counter, so the cost picture this project reasons from was assembled from 59.23 of the 382.59 in fees it actually paid — 235 round trips seen against 394 that exist. 2026-08-11: the stale 16/26 resurfaced from config.json's own rationale in a fresh 7-agent audit — and the apply-batch 66744ed1 put the flag AT the source: a stale-fee note now ships in config.json market_maker recording that min_half_spread_bps=26 descends from the STRUCK schedule (a NEW surface — the quote floor, not just the fee constants); retuning it is quote-pricing = cohort-resetting, HELD with the fee constants behind the h432 gate"
tags: [cost, measurement, execution, fees, sequencing, gross-vs-net]
sources: 10
updated: 2026-08-10
---

# Cost Truth

## Definition
An instrument comparing **measured** round-trip execution cost against the **configured** cost stack the
pre-trade gate uses. When configured under-prices measured past a tolerance, it emits a
`DANGEROUS: configured UNDER measured` verdict.

## The reading
Mean cost overrun **+21.17 bps**; measured round-trip **86.17 bps** vs configured **65.00 bps** —
**+32.6%**, past the +/-20% tolerance. Corroborates an earlier diagnosis of ~20.5 bps overrun over 209
live closes.

## Three caveats, all load-bearing
1. **n=16 unique closed trades.**
2. The source file "contains only trades whose postmortem TRIGGERED — the **underperforming subset by
   construction**."
3. **The file itself was later found stale** (17 rows, ending ~12 days before the measurement), with
   the live series living elsewhere. The verdict was computed on a frozen corpus.

## The deliberate non-action
No config change. Per policy, **a fee edit is the operator's conscious commit, never an automatic
script correction**. The instrument reports; the human decides.

## The directionality principle, applied in reverse (2026-08-02)
The verdict is deliberately **one-directional**: only configuration *under*-pricing reality is
DANGEROUS. The honest-fills commit (`8e5455e8` — [[sources/session-20260802-digest]] third
addendum) applied the same principle from the other side: fee constants were **deliberately
left at 25/40 bps against Kraken's published 16/26**, because overstating cost is the safe
direction — while the fill-probability constant *had* to move (0.45 → 0.048, the XV-021
measured trade-through rate) because there the error flattered the strategy. Paper results may
only err against the strategy, never for it.

## ⚠️ The fee constants are FALSIFIED — and the fix is sequenced (2026-08-07, panel-confirmed)

**Triple-confirmed by three independent fetches of Kraken's current schedule
([[sources/session-20260807-institutional-review]] §C): 25/40 bps matches NO row.** Tier 1
($0+) is **40/80**, Tier 2 ($2.5k+) 30/60, Tier 3 ($10k+) 22/38, Tier 5 ($50k+) **~15/30**,
tiers keyed on best-of 30-day volume OR assets on platform. Consequences for this page:

- **The "Kraken's published 16/26" figure quoted above (and in `8e5455e8`'s rationale) is
  STALE.** Do not cite it. The `config.json:325` premise *"25/40 is the public spot floor"* is
  false.
- **The "overstating is the safe direction" premise is INVERTED for the realistic go-live
  case.** A fresh $5k account with low volume sits at Tier 1 (40/80): the modeled 25/40
  **understates** the real fee drag by ~1.6–2x — the config's own documented "dangerous
  direction" (`config.json:358`). The paper drawdown −384.67 is a **floor**, not an upper
  bound. (The bot's own 30-day notional, $97,015, looks Tier-5 — but **77.6% of that anchor
  is churn flow**; never cite it as a tier argument.)
- **The mechanism built to catch this is dead in the mode the bot runs in:** `fee_recon`
  (OM-080) *"fails silent … DRY_RUN without keys"* — the whole campaign runs on an unverified
  constant. And in paper the fee column of every fill is that constant by construction (the
  section below), so no ledger self-check can catch it either.
- **DO NOT "just fix the constant."** Panel ruling: the fee constant feeds the labeler's cost
  floor (`ml/labeling.py:45-52`, `sigma_eff = max(sigma_bar, pt_cost_mult × cost/pt_mult)`),
  the floor **binds 100% of brackets**, and both the candidate labeler and the live
  bracket-exit engine call it — a live change is a **disguised label-geometry retune** that
  breaches the 432-hold. The correction is **sequenced behind the h432 verdict** (or a
  consciously minted era). Allowed now, analysis-only: stamp the fee assumption on P&L
  panels, give `fee_recon` a read-only-keys DRY_RUN path, run the battery at 40/80 and ~15/30
  to see which admits flip. ([[synthesis/owed-measurements]] item 37.)

## What a paper fill can and cannot tell you about cost (2026-08-06)

The hedge thrash ([[sources/session-20260806-hedge-thrash]]) put **294 fills** of known
provenance on the ledger in 25 minutes, and their fee column reads **exactly 40.00 bps per fill** —
`pretrade.taker_fee_bps` to the digit. That is not a measurement; **in paper the fee component of
a round trip is the configured constant, by construction.**

> **Split the cost stack by what paper can inform.** **Fees: uninformative** — a paper fill can
> only ever return the constant, so any "measured fee rate" from `fills.csv` in dry-run is a
> restatement of `config.json`, the [[concepts/tautological-instrument]] shape applied to cost.
> **Slippage and spread: informative** — those come from the book and the fill model, and they are
> what makes the instrument's **86.17 bps measured vs 65.00 configured** a real disagreement rather
> than an identity. The thrash's own median slip was **2.03 bps**.

~~The direction rule holds either way: the constants stay at **25/40** against Kraken's
published **16/26**, so a paper cost figure is an **upper bound by policy**~~ — **superseded
by the falsification above**: at Tier 1 the paper figure is a *lower* bound. The incident
arithmetic that follows from the stale 16/26 ("the same churn is $188.33") inherits the
falsified premise; at Tier 1 rates the same churn is **~2x the booked figure**. What survives
rate-independently: the **non-fee** part of the window's loss was small (**panel-paired gross
−13.37**, ~4.3% of the loss — crossing cost, mean slip 1.87 bps), so **the defect was the
churn, not the schedule** — that conclusion stands at every tier.

## The gate that consumes it
[[entities/pretrade-gate]] — and [[comparisons/harness-vs-live-cost-stack]] for the
simulation-versus-live version of the same disagreement.

## The unreconciled tension
Three different round-trip cost numbers are in simultaneous use across the system: the label floor
assumes **0.50%**, the pre-trade gate is configured at **0.65%**, and measurement says **0.86%**. The
labeler therefore floors barriers using a cost **23% below** the gate's and **42% below** measured.
**No document reconciles this.** See [[synthesis/open-contradictions-register]]. *(08-07: the
falsified venue schedule adds a fifth number to the family — and the reconciliation must now
also state which side of the [[concepts/paper-real-boundary]] each figure lives on: in paper,
every fee "measurement" is the config constant restated.)*

## Cost truth at the book level (2026-08-09) — 32.8x

Every reading above measures cost **per round trip, against configuration**. The whole-book
version had never been computed ([[sources/session-20260809-unbiased-economics]]), because 49% of
lifetime fees sat in **no P&L counter at all** — `record_entry_fee` debits opening legs straight
to cash while `record_realized_pnl` nets only the closing leg. Recovered from the cash identity
and re-derived at filing from the live `outputs/state.json`:

```
GROSS trading P&L, before ANY fees : −11.66   over ~250 closed positions / 438 entry fills
total fees paid                    : −382.59  (opening 185.94 + closing 196.65)
NET realized, all-in               : −394.25  = −7.89% of 5000.00 starting capital
fees / |gross edge|                :  32.8x
```

> **This is what "cost truth" looks like when the denominator is the strategy rather than a
> trade.** The gate compares realized cost against configured cost and can return DANGEROUS. It
> has **never** compared cost against **the edge the cost is being paid to capture** — and that
> ratio is **32.8:1**. **100% of the book's loss is costs**, not as a rhetorical flourish but as
> an arithmetic identity: gross is −11.66, i.e. ~0.

Three consequences for this page's standing claims:

1. **The falsified fee constants matter MORE, not less.** 25/40 bps matches no row of Kraken's
   current schedule (Tier 1 is 40/80), so the real drag is **~1.6–2x modeled** — and it is being
   applied against a gross edge of **zero**. The h432 sequencing decision is unchanged; its
   stakes are not.
2. **But cost work is now provably insufficient.** Halving fees on a book with **no gross edge**
   converts a −394.25 loss into a smaller loss, never into a profit. Cost remains the **larger**
   term and is no longer a **sufficient** one — the strongest form of the 08-02 correction
   ([[concepts/payoff-asymmetry]]).
3. **The cost side is under-read by 1.6% in the ledger everyone analyses.** `fills.csv`
   `fees_delta_usd` sums **376.35** across 1,019 rows against `fees_paid_total` **382.59** —
   **6.24 never reaches the ledger**, so every offline cost analysis built on `fills.csv` reads
   **optimistic** by that much ([[synthesis/open-contradictions-register]] item 18).

**Paper/real:** all sim-side. And the simulator is one-way optimistic on fills, so **real gross
would be worse than −11.66** — the honest statement is **gross edge ≤ 0**
([[concepts/paper-real-boundary]]).

## Both cost instruments are blind to the largest cost event (2026-08-09)

([[sources/session-20260809-adversarial-audits]] §4.1, §4.4;
[[synthesis/owed-measurements]] items **53** and **56**.)

The two tools this project uses to reason about cost **both filter out the hedge leg**, and
neither says so:

| Tool | What it sees | What exists |
|---|---|---|
| `scripts/breakeven_test.py` (`:126`, `purpose == "entry"`) | **235** round trips, **fees 59.23** | **394** round trips, **fees 374.96** |
| `scripts/cost_attribution.py` (`:126`, a bare `continue` with no skip counter) | **n=235**, **0.668%/trade** — *correct for the directional population* | blended **0.7766%** across the real book |

> **The cost picture this project has been reasoning from was assembled from 59.23 of the 382.59
> in fees it actually paid.** The 159 discarded round trips were filed under *"partial or
> malformed"* — **none are malformed**; they close to within 0.0% of opening size
> ([[concepts/uncounted-exclusion]]).

**Three consequences for how cost claims on this page must now be read:**

1. **The DANGEROUS-verdict machinery has never seen the hedge leg.** Every per-fill cost reading
   filed since 08-02 describes the directional book only. The *verdicts* survive — the measured
   cost of a directional round trip is not changed by excluding hedges — but their **scope** was
   never stated, and readers took them for book-level.
2. **The gap compounds with the 6.24 ledger shortfall**, not competes with it. One is a missing
   1.6% of fee *records*; the other is a missing 41% of round-trip *rows*. **Both flatter.**
3. **Severity is not the magnitude.** `cost_attribution`'s error is only **1.16x** (corrected
   down from an initial 6.4x claim). The finding is that **a cost-attribution tool is
   structurally incapable of seeing its own largest cost event**, which is a statement about what
   the instrument can ever tell you, not about today's number.

## The stale 16/26 resurfaced (2026-08-11 audit) — the falsified premise is still propagating

> ⚠️ **Contradiction, flagged both ways** ([[sources/session-20260811-operator-audit]] §6.5).
> The since-6am audit's ledger lens described the fee constants as *"padded 25/40 bps vs
> Kraken 16/26 (intentional stress)"* — the **exact stale schedule this page struck on
> 2026-08-07** (triple-confirmed: 25/40 matches NO current Kraken row; Tier 1 is **40/80**).
> The audit's *coherence* verdict stands (the ledger is internally consistent with the
> configured constants, and the constants are a deliberate documented choice); its *venue*
> characterization does not — at Tier 1 the constants **understate**, and "padded /
> conservative / intentional stress" is only true against the falsified 16/26. **The lesson
> is about propagation:** the falsification has lived on this page since 08-07, yet a fresh
> 7-agent audit reproduced the stale figure from the config's own rationale — the
> `config.json:325` premise is still shipping, and any instrument that reads the config's
> prose inherits it ([[synthesis/documentation-drift-register]]'s reading rule: when a doc
> and an audit disagree, the audit wins — *this* audit read the doc). Sequencing unchanged:
> the correction stays behind the h432 verdict (owed 37).

**Follow-up, apply-batch `66744ed1`** ([[sources/session-20260811-apply-batch]] §4): the
propagation vector got its inline correction — a **stale-fee note now ships IN
`config.json`'s `market_maker` block**, recording that **`min_half_spread_bps=26` descends
from the STRUCK 16/26 schedule**. Two things this adds to this page's map: (1) a **new
surface** — the quote floor, not just the fee constants, was derived from the falsified
schedule (26 is the stale taker figure restated as a half-spread floor); (2) the flag now
lives at the source a fresh reader actually reads, so the next audit inherits the correction
instead of the premise. **Deliberately NOT retuned:** changing `min_half_spread_bps` is
quote-pricing = **cohort-resetting** — it is **HELD with the fee constants behind the h432
gate** (owed 37; [[synthesis/governance-doctrine]] rule 17).

## Related
[[sources/session-20260807-institutional-review]] · [[concepts/paper-real-boundary]] ·
[[sources/session-20260809-unbiased-economics]] · [[concepts/unfalsifiable-explanation]] ·
[[entities/pretrade-gate]] · [[entities/kraken]] · [[synthesis/the-money-path-thesis]] ·
[[synthesis/owed-measurements]] · [[synthesis/open-contradictions-register]] ·
[[sources/session-20260811-operator-audit]] · [[sources/session-20260811-apply-batch]]
