---
title: "Pooled Populations (a mean that describes neither)"
category: concept
summary: "When two populations differ BY DESIGN — one admitted through an EV gate, one deliberately bypassing it — a count-weighted pooled statistic describes neither, and the majority population silently sets the headline: probe n=182 expectancy −0.1636 and conviction n=17 expectancy −1.5840 are reported as one number, −0.2838, understating the population the strategy is actually about by 5.6x; the codebase already holds the opposite doctrine in its ML-validation lane and it never travelled to the P&L-reporting lane. SECOND SPECIMEN, same day: pooling entry tickets (modal $18.00) with hedge tickets ($265.44), populations that differ 14.7x by construction, FABRICATED a '7.04x revenge sizing' finding that exists in neither sub-population — the disaggregated after-win/after-loss ratio is 1.000 — so pooling does not merely distort a magnitude, it can invent a phenomenon; and the analysis agent committed it while writing up the audit of the first specimen, which is why the split is an absolute rule rather than advice. SIBLING CLASS 2026-08-12 (calendar-anchored-state): a dollar-denominated anchor read across a capital epoch is a one-number pool of two capital regimes — completing the escalation: pooling can understate a magnitude (5.6x), invent a phenomenon (7.04x), and, wired to a protective action, STOP THE SYSTEM (RP-041, 25 hours, zero entries)"
tags: [statistics, reporting, population, probes, expectancy, audit, sizing]
sources: 3
updated: 2026-08-14
---

# Pooled Populations

## The claim

**Two populations that differ by design must be reported separately.** Pooling them produces a
number that is arithmetically correct and **descriptively about nothing** — and because the
weighting is by **count**, the population that happens to be more numerous **silently becomes the
headline**.

This is not a precision problem. Both sub-means can be far from the pooled mean, and the pooled
mean can sit outside the decision-relevant range of **both**.

## The specimen (2026-08-09)

`performance.overall` pools **91% EV-gate-BYPASSED probes** with **conviction trades**,
count-weighted. Inside the exact 200-close window (197/200 joined):

| Population | n | expectancy |
|---|---|---|
| **probe** | 182 | **−0.1636** |
| **conviction** | 17 | **−1.5840** |
| **reported (pooled)** | 199 | **−0.2838** |

> **The reported figure understates the conviction population by 5.6x** — and conviction trades
> are the ones the strategy is *about*. Probes exist precisely because they **bypass** the gate
> that defines a conviction trade; they are a different experiment, not a smaller version of the
> same one.

`sharpe −1.067`, `sortino −0.751` and `max_loss_streak 57` are all computed on the mixed sample
and **describe neither population.** A loss streak spanning two interleaved populations is not a
property of either.

**`pos.is_probe` is in scope 22 lines earlier at `main.py:1650`** and is simply not passed to
`perf.record_close`. ([[sources/session-20260809-adversarial-audits]] §4.3)

**Proposed fix:** pass `is_probe` at `main.py:1672`; emit **overall / conviction / probe** blocks;
compute **streaks within-population**.

## The correction the audit made to itself

> ⚠️ **Notional weighting does NOT support the argument.** Return-on-notional is **−0.692% probe
> vs −0.479% conviction** — the *opposite* ordering. Re-weighting is not the repair.
> **The SPLIT is what recovers the truth.**

Recorded because it matters *how* the class is fixed: the instinct *"weight it properly"* would
have produced a different wrong number, and the discarded half of the argument is the evidence
that the surviving half was tested ([[concepts/adversarial-verification]]).

## The second specimen (2026-08-09, later the same day) — and the analysis agent committed it

A Turing-test sweep of the ledger briefly produced a spectacular behavioural finding:
**"the bot exhibits 7.04x revenge sizing after losses."**

**It was an artifact, and it was killed before filing**
([[sources/session-20260809-turing-test-hedge-verdict]] §8.3).

| Population | modal ticket |
|---|---|
| **entry** | **$18.00** |
| **hedge** | **$265.44** |

The two populations differ **14.7x by construction**, and **losses are disproportionately followed
by hedges**. Pooling them therefore manufactures a post-loss size jump that is **purely
compositional** — no sizing rule changed, no risk appetite moved, nothing "revenged."

**What the disaggregated statistic actually says:** the **after-win / after-loss size ratio is
1.000** — perfect emotional invariance, the single strongest *machine* tell in the whole sweep
([[concepts/behavioral-isomorphism]]). **The pooled version did not merely exaggerate the truth;
it inverted it.**

> **The uncomfortable part, recorded deliberately.** This is the same class the corpus filed
> against the bot's own reporting **eight hours earlier** (the specimen above). The analysis agent
> committed it **while writing up the audit of it.**
>
> **Knowing a failure class by name does not confer immunity to it.** Only running the
> disaggregation does. That is the practical reason rule 2 below is written as an absolute rather
> than as advice.

**The generalisation this specimen adds:** the first specimen showed pooling **understating** a
sub-population by 5.6x. This one shows pooling **fabricating a finding that does not exist in
either sub-population**. Both sub-populations have an after-win/after-loss ratio near 1.0; the
7.04x lives **only in the mixture**. A pooled statistic is not merely imprecise — **it can report
a phenomenon that is present in no member of the pool.**

## The sharpest part: the doctrine already existed, one lane over

**`overfit_check.py:1031-1034` refuses to grade DSR on the mixed sample for exactly this
reason.** The correction is **fully present in the ML-validation lane and entirely absent from the
P&L-reporting lane.**

> **This is not a missing idea. It is an idea that did not travel.**

That is a distinct organizational failure mode from ignorance, and it has a distinct fix: when a
lane adopts a statistical discipline, **sweep the other lanes for the same question**. The
project already knows this shape from [[concepts/adoption-is-not-enforcement]] — *"we fixed all
of them"* and *"nothing new can appear"* are different claims, and here they are joined by a
third: *"we know better in one place"* is not *"the system knows better."*

## Why the direction flatters

The bypassed population is **more numerous** (91%) and — in this book — **less bad per trade**.
Count-weighting therefore pulls the headline toward the benign sub-population. Nothing forces
that in general; but it is what happened here, and it is why this class is a mechanism of
[[concepts/self-flattery-gradient]].

## The rules

1. **If a gate distinguishes two kinds of trade, the reporting must distinguish them too.**
   A population defined by *bypassing a gate* is definitionally not the gated population.
2. **Never report a pooled mean without its sub-means.** *"overall"* is legitimate only when it
   ships beside *"conviction"* and *"probe"*. **This is an absolute, not a preference** — the
   second specimen was produced by an agent who had filed the first one hours earlier.
2b. **A behavioural finding computed across populations of different SIZE is void until
   disaggregated.** Sizing, hold-time, streak and sequence statistics are all mixture-sensitive;
   *entry* and *hedge* legs differ **14.7x** in this book and interleave non-randomly.
3. **Path statistics must be computed within-population.** Streaks, drawdown runs and
   autocorrelations across an interleaved sample are artefacts of the interleaving.
4. **When one lane adopts a statistical discipline, ask which other lanes owe it.** The DSR
   refusal was right for three months while the expectancy headline was wrong for the same three
   months.

## The mirror class

[[concepts/uncounted-exclusion]] is the opposite error: **dropping** a population rather than
**merging** one. Both are failures to state **what population a number describes**.

## The sibling class (2026-08-12)

[[concepts/calendar-anchored-state]] is the same defect one representation down: a
**dollar-denominated anchor read across a capital epoch** is a one-number pool of two capital
regimes. The first specimen here **understated** (5.6x); the second **fabricated** (7.04x
revenge sizing); the sibling's type specimen **vetoed** — the W33 week anchor (4614.22,
pre-reset) read the $800 reset as an 82.7% in-week trading loss = 1378% of the weekly budget,
and RP-041 blocked all new risk for 25 hours
([[sources/session-20260812-weekly-anchor-lockout]]). The escalation across the three is the
point: a pooled statistic can misstate a magnitude, invent a phenomenon, or — once wired to a
protective action — **stop the system**.

## Status of the fix (2026-08-09)

The split **shipped** as `f11b7e32` with a third **`unknown`** bucket for pre-upgrade rows — and is
**currently inert**: live reads **`unknown 200 · probe 0 · conviction 0`**, because every live row
predates the flag. **The specimen above cannot yet be reproduced from the live split.** Owed item
**54** stays **open** ([[comparisons/dormant-vs-inert-features]]; domain rule 5 — *shipped is not
working*).

## The split is no longer inert — and the pooled population is now 75% probe (2026-08-14)

**Status change to the paragraph above.** It records `probe 0 · conviction 0` because every
live row predated the flag. That is no longer true. Over the exact 24h window
`[1786664298, 1786750698]` (snapshot 2026-08-14T23:38:18Z), `signal_history.csv` live rows
carry the flag: **`probe=1` × 3, `probe=0` × 1** (the 119 blanks are `source=candidate`).
Owed item **54** therefore moves from *shipped-and-inert* to **populating** — though **not to
closed**: at n=4 the specimen above still cannot be reproduced from the live split, and
[[comparisons/dormant-vs-inert-features]]'s distinction is what the counter must clear.

The consequence matters more than the status. The live half of the corpus is now **75%
probe** — a lane deliberately exempt from the EV gate — so the pooled live population is
mostly the population this page says must never be pooled with the other. The gate itself
produced **one** entry in 24h (BTC, `label=0`, −$0.42) against three probes (+0.02/+0.13/+0.12),
for a net of **−$0.15**. See [[concepts/probe-livelock]] §terminal state: the drought floor
has become the principal supplier of live labels, and therefore of era-4 accrual.

**A second pooling axis, measured the same day:** `label_era` base rates span **40x** across
the corpus — `exit_sim_time_stop` **0.0065** (3 positives in 459 rows) to `legacy` **0.2611**
— which is the affirmative case for [[concepts/era-exclusion]] and a textbook instance of this
page's rule at corpus scale. The deploy gate already enforces the principle *between* champion
and challenger (`main.py:6371-6376`: *"Brier is not comparable across differing base rates"*)
and does **not** enforce it *within* the training matrix.

**And a base-rate split worth flagging as a lead, not a finding:** in the same 24h window
`source=live` shows base rate **0.750** (3 of 4) against `source=candidate` **0.227** (27 of
119). At n=4 the Wilson interval is nearly the unit interval and this is **not** evidence of
anything — it is recorded only because the model trains on a pool that is **96.7% candidate**
and is applied to live decisions, so if the two populations *do* differ systematically, the
training/deployment mismatch is a pooling defect of exactly this page's kind. *What would
close it:* the same live-split counter reaching a population where the comparison means
something.
— [[sources/session-20260814-cohort-instruments]] §supporting measurement

## Related
[[concepts/uncounted-exclusion]] · [[concepts/self-flattery-gradient]] ·
[[concepts/ratio-aggregation-bias]] · [[concepts/adoption-is-not-enforcement]] ·
[[concepts/adversarial-verification]] · [[concepts/behavioral-isomorphism]] ·
[[entities/overfit-check]] · [[comparisons/dormant-vs-inert-features]] ·
[[concepts/payoff-asymmetry]] · [[sources/session-20260809-adversarial-audits]] ·
[[sources/session-20260809-turing-test-hedge-verdict]] ·
[[synthesis/owed-measurements]]
