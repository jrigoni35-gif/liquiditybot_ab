---
title: ThalesEngine vs manip_suspect
category: comparison
status: SETTLED
summary: "SETTLED as a NULL — the established finding is that efficacy is UNRESOLVED in both directions and the two instruments disagree (owed item 94); that unresolvedness is the measured result, not an open investigation. Two stacks sharing the manipulation label: one shades confidence in shadow mode, the other actually reaches sizing
tags: [comparison, manipulation, influence]
sources: 3
updated: 2026-08-21
---

# ThalesEngine vs manip_suspect

> ⚠️ **Correction 2026-08-21 — the veto HAS fired, many times.** The line below
> ("no fill ever reached the veto threshold, so the veto has never fired in
> anger") was true when written on 2026-08-01 and is **false now**: the corpus
> snapshot of 2026-08-21 carries **454 rows stamped SZ-045**, 142 of them in the
> current label era (`triple_barrier_h432`), 95.8% of the era's veto band on
> MINA+FLOW. See [[sources/session-20260821-manip-gate-and-live-readiness]].

Two distinct systems share the word "manipulation," and conflating them produces wrong conclusions about
what the bot actually does.

| | ThalesEngine | manip_suspect |
|---|---|---|
| What it is | a **detector bank** (TH-010..TH-021) | a **composite score** (max of spoof, whiplash, cross-venue divergence) |
| Influence | `shadow` — **zero applied** | **live and enabled** |
| Reaches sizing | **no** | **yes** — downsize band then veto |
| Grading | Wilson-LCB vindication ledger | none |
| Evidence of effect | 65 events, all "would-shade" | 316 admissions above the downsize threshold |

## Where each actually binds
**manip_suspect** flows into a risk scale and reaches the sizer: a downsize band and a hard veto
threshold. It also drives a **training down-weight** that is wired, active and material — corpus mean
0.233 gives an average training weight factor of ~0.88.

**ThalesEngine** reaches nothing. Every shade it has ever computed was counterfactual.

## The measurement that complicates both
Neither shows a dose-response. Across 253 live fills: below 0.3 -> win 18.4%; the 0.3-0.6 band -> win
**2.9%**; above 0.6 -> win 9.1%. **High-suspicion entries do not lose more; the middle band is worst.**
And no fill ever reached the veto threshold, so the veto has never fired in anger. *(Last clause
superseded — see the correction callout above.)*

## What the 2026-08-21 efficacy audit added

**The dose-response question is now answered per label era, and the answer does not
carry across the era boundary**: in `triple_barrier` the counterfactual win rate is
monotone in the score (0.212 → 0.200 → 0.266 → **0.347**); in `triple_barrier_h432`
it is flat (0.500 → 0.419 → 0.468 → 0.457).

**The two ways of asking "did the gate refuse this trade" disagree with each other.**

| instrument | pooled MH delta (refused − passed), direction-adjusted, ESS-corrected | z | p |
|---|---|---|---|
| disposition `disp == SZ-045` | +11.71 pp | +2.41 | 0.016 |
| feature `manip_suspect >= 0.9` | +2.80 pp | +0.61 | 0.542 |

`both 277 · disp-only 104 · feature-only 218 · **Jaccard 0.462**`; **25.6% of
SZ-045-stamped rows record a manip_suspect BELOW the threshold they were refused
by**. Holding the stamp fixed, the score explains nothing (z = +0.46 / −0.11);
holding the score fixed, the stamp carries everything (z = +1.60 / +1.08, neither
significant). A **placebo** stamp (SZ-021, +33.51 pp) beats the manipulation stamp
(+15.48 pp). Within-asset in the current era, MINA shows nothing (dWR −0.7 pp on
n=87 vs n=114) and FLOW's +34.3 pp rides on a control arm of effective n **3.0**.

**Verdict: efficacy UNRESOLVED in both directions — and the instrument
disagreement must be reconciled before any efficacy claim is made from
`signal_history` at all** ([[synthesis/owed-measurements]] item 94).

## The deeper problem, upstream of both
The `spoof` component that feeds `manip_suspect` cannot distinguish honest maker
repricing in a trend from real layering — at matched cadence both score 0.949 and
label `spoofy` — so a gate reading it is not evidence about manipulation at all:
[[concepts/observational-equivalence]].

## The classification conflict
The same probe/shade interaction was ruled **"expected per config"** in one document and **patched as a
defect** in another on the same day — see [[synthesis/open-contradictions-register]].

## Related
[[entities/thales-engine]] · [[sources/thales-unit-audit]] · [[concepts/earning-its-keep-audit]] ·
[[sources/session-20260821-manip-gate-and-live-readiness]] ·
[[concepts/observational-equivalence]] · [[concepts/average-uniqueness-and-ess]]
