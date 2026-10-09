---
title: Era Exclusion
category: concept
summary: "A load-time training filter that keeps only rows of the current label era, auto-arming at a derived row threshold, with an absolute nothing-is-ever-deleted bound — and, as of 2026-08-09, with its first measured failure mode: because it arms on a COUNT of the column it protects, corrupting that column DISARMS it silently (690→42 current-era rows < min_new_era_rows=150), releasing 9,746 pooled rows into training; the nothing-is-ever-deleted bound is what made the corpus recoverable"
tags: [corpus, filtering, labeling, ml-081, incident]
sources: 7
updated: 2026-08-14
---

# Era Exclusion

## Definition
A filter applied at **load time, in the training view only**, that keeps only rows tagged with the
current [[concepts/label-era]]. It auto-activates once enough new-era rows exist.

## The absolute bound
**Nothing is ever deleted.** Every row stays byte-for-byte on disk, in the audit trail, and in every
bundle. Structurally guaranteed: the filter runs as the **very last step** of the load, after every
other correction, and when inactive returns the pre-existing arrays unchanged **by reference**.
Rollback (`forced_off`) restores the pre-exclusion training set byte-for-byte as the *default*
behaviour of turning it off — not special-cased engineering.

## Armed vs active
`armed` = threshold met; `active` = armed (or forced on) and not forced off. Surfaced **independently**
so an operator can distinguish "threshold met but rolled back" from "not yet met". Reason code
**ML-081** fires once on the inactive->active transition, edge-triggered.

## Threshold-armed auto-activation
It turns itself on at a **data-derived row count** rather than an operator flip — which is precisely why
its cross-consumer wiring could not be deferred: an unwired consumer "could silently start measuring or
training a stale corpus the moment the threshold crosses on disk."

## The failure mode of arming on data (measured 2026-08-09)

**The property that makes it good — it arms on the data, not on an operator — is also its
one structural weakness: it arms on a COUNT of the very column it protects.** Corrupt
`label_era` and the filter does not misfire; **it stands down**, and it does so *silently
and legitimately*, because from its own point of view the current era genuinely has too few
rows to train on.

Measured chain ([[sources/session-20260809-corpus-corruption]] §4), from one
non-idempotent line in the migrator ([[concepts/migration-idempotence]]):

| Step | Before | After |
|---|---|---|
| Current-era rows | 690 | **42** |
| Filter | armed / active | **DISARMED** (42 < `min_new_era_rows` = 150) |
| Training load | 690 | **9,746** — three label definitions pooled |
| `live_clean` | 5 | **299** |

Everything downstream then behaved correctly *on false input*: [[concepts/evidence-floors]]
cleared four families in one step and a champion deployed nine minutes later.

> **The design lesson is not "don't arm on data."** It is that a **self-arming guard needs
> its input to be protected by something other than itself.** The era filter has no way to
> distinguish "the new era is young" from "the era column was destroyed" — the two look
> identical at the threshold. The protection had to come from upstream: the migrator's
> fixed-point test.

**The nothing-is-ever-deleted bound is what saved this.** Because exclusion is a **load-time
view** and no row is ever removed from `signal_history.csv`, the corruption touched only a
derived tag on rows that were otherwise intact — so the repair was a 2,729-cell restore by
`position_id` join from preserved backups, with **0 rows added, removed or reordered**. A
filter that had physically pruned the corpus would have made this unrecoverable. **An
absolute bound written for one reason paid out for a completely different one** — the
strongest available argument for keeping it absolute.

Post-repair verification: `armed=True` / `active=True`, load **9,746 → 690**, `live_clean`
**299 → 6**.

## Compared with the time-based filter
[[comparisons/era-exclusion-vs-epoch-filter]] — same consumers, opposite deferral decisions.

## Two conscious overrides
1. Exclusion covers **live rows too**, overriding a prior term that live rows were never excludable —
   because all measured live rows were themselves old-era, so keeping them "would shrink the corpus
   without cleaning it."
2. Ships **inert and auto-arming** rather than manually flipped: "never a manual flip."

## What it broke downstream
Activation orphaned a champion whose `trained_rows` exceeded the entire post-exclusion corpus
([[concepts/deploy-deadlock]]), and starved the evidence gate to a single family. Three consumers were
never re-baselined for it.

## The fix that hid a fix
The filter hardcoded the **un-qualified** era constant as the era to keep. When a horizon qualifier was
introduced, the filter kept the stale rows and **excluded the new ones including the first live labels**
— "left alone, `live_clean` would have stayed 0 forever and the horizon fix would have been wrongly
written off as a failure." Found only because the operator **verified rather than assumed**.

## The transfer question, closed (2026-08-02)
Could old-era rows enter the new era as *analogues* instead of being excluded?
`label_transfer_filter` was repaired to **refuse non-analogue transfer** — the closest
old-era/new-era pair is **4.5x off the 18x concurrency target** — and a **Kish-on-uniform bug**
was fixed along the way (the ESS check had applied the Kish formula to uniform weights, which
just returns the raw count; corrected to the weight sum —
[[concepts/average-uniqueness-and-ess]]). Verdict: **NO ANALOGUE — era exclusion stands.**
This pairs with the binding injection policy: the training corpus gets **nothing synthetic and
nothing relabeled, ever** ([[sources/session-20260802-digest]] second addendum,
[[synthesis/governance-doctrine]]).

## What correct exclusion costs (2026-08-14): 2.5% of the corpus survives

The filter is working exactly as designed, and this is what that looks like. `label_era`
across all **10,559** rows of `signal_history.csv` (snapshot 2026-08-14T23:38:18Z):

| `label_era` | n | share | base rate |
|---|---:|---:|---:|
| `triple_barrier` | 5,328 | 50.5% | 0.2508 |
| `exit_sim` | 2,732 | 25.9% | 0.1398 |
| `legacy` | 1,781 | 16.9% | 0.2611 |
| `exit_sim_time_stop` | 459 | 4.3% | **0.0065** |
| **`triple_barrier_h432`** (current) | **259** | **2.5%** | 0.2239 |

The base rates span **40x** (0.0065 → 0.2611), which is the affirmative case for the filter:
`exit_sim_time_stop` has **3 positives in 459 rows**, and pooling it with a 0.26 era would
produce a mixture describing neither ([[concepts/pooled-populations]]). Exclusion is not
merely defensible here; refusing it would be indefensible.

**But the cost is the whole point of this entry.** Keeping only the current era leaves a
**211-row** training matrix where the incumbent champion had learned on **10,217** — and that
48x gap is precisely the condition that fires ML-083's unbounded era-orphan unlock, which then
promoted a negative-skill model into the accruing verdict window
([[concepts/deploy-deadlock]] §third polarity, [[synthesis/owed-measurements]] item 73).

So the filter's correctness and the promotion defect are **the same event seen twice**. The
generalization for this page: **a filter that correctly refuses to pool must be paired with a
promotion gate that correctly refuses to promote on what little remains.** Excluding well and
deploying anyway is not two independent decisions — the first manufactures the conditions for
the second. The expand-contract alternative (dual-label through a transition, contract the
retired geometry only once the new one has n) is sketched in repo
`docs/quant/2026-08-14_model_promotion_migration_design.md` GAP-3 and is **ship-blocked**: it
alters the training matrix, hence model behavior.
— [[sources/session-20260814-cohort-instruments]] §supporting measurement
