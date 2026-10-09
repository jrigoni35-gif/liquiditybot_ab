---
title: Deploy Deadlock (Champion Watermark Orphaning)
category: concept
summary: "A champion trained on more rows than the entire post-filter corpus makes the like-for-like deploy gate fail closed forever — and 2026-08-09 adds the mirror spelling: a champion whose SCORE was computed on a corrupted corpus is wedged IN rather than locked out. The mirror case then RELEASED ITSELF: the ML-083 branch written for the first polarity fired unmodified on the second, because it keys on a STRUCTURAL condition (watermark 9,708 > matrix 701) rather than on why the populations diverged"
tags: [ml, deadlock, governance, incident, self-heal]
sources: 4
updated: 2026-08-14
---

# Deploy Deadlock (Champion Watermark Orphaning)

## Definition
When a corpus filter shrinks the training view below a deployed champion's `trained_rows` watermark,
the out-of-fold index range used to rescore the frozen champion becomes **empty**. The rescore returns
None, so the like-for-like comparison gate **REJECTs fail-closed on every retrain, forever**.

## The instance
Champion `blend` trained pre-exclusion on **4,823 rows**; the post-exclusion matrix held **1,516**.
Compounding it: the retrain flag file is cleared **only** by a successful deploy, never on reject — so
"RETRAIN: QUEUED" persists permanently. And with zero clean live rows the
[[concepts/evidence-floors|evidence gate]] admitted only `logistic`, a second independent lock.

## Why fail-closed is still correct
The gate is refusing to compare two things it cannot compare. The defect is upstream — a filter
activating without its consumers re-baselined.

## The fix, and the fix's failure
The first fix let a no-champion disjunct free the bar — but it was **ineffective**, because the
orphaned champion's badge (0.1237, measured on a dead 0.169-base population) still read as better than
challengers on a 0.30-base corpus. See [[concepts/ghost-badge]]. The working fix sets the champion
aside entirely and applies the true cold-start standard.

## The mirror spelling — the WEDGED champion (2026-08-09)

The same gate, the same incommensurability, **opposite polarity**: instead of a champion
that cannot be *compared*, a champion that cannot be *beaten*.

After the corpus corruption was repaired, the challenger (`logistic`, clean 692-row corpus,
OOF Brier **0.2714**) lost to the incumbent (`gbt`, **corrupted pooled** 9,708-row corpus,
**0.1537**) — so a champion that was **promoted by the data bug in the first place** is now
**wedged in place**, and no clean-corpus challenger can dislodge it
([[sources/session-20260809-corpus-corruption]] §10, [[concepts/ghost-badge]]).

| | Original deadlock | Wedged champion |
|---|---|---|
| Trigger | corpus **shrank** below the champion's `trained_rows` | corpus was **corrupted**, then repaired back down |
| Gate behaviour | rescore returns None → **REJECT fail-closed** | rescore succeeds → **REJECT on a better-looking number** |
| Consequence | nothing new deploys | **the bug's own choice keeps running** |
| Detectability | obvious (a None, a queued retrain that never clears) | **invisible** — both scores are well-formed |

**Both are the same missing field:** a stored watermark records a *score* and not the
*corpus* that produced it. Add provenance (corpus revision, era set, row count) and both
spellings become detectable instead of arguable.

### The wedge released itself — 2026-08-09 02:56:04

**No override, no re-baseline, no commit.** The fix for the *original* deadlock — the
**ML-083 era-orphan branch** (`main.py:6330`), written 2026-07-29 for the left-hand column
of the table above — **fired on the right-hand column and released the wedge**
([[sources/session-20260809-gate-policy-and-self-heal]] §1).

Once the corpus repair re-armed era exclusion, the champion's watermark (**9,708**, the
corrupted pooled population) **exceeded** the training matrix (**701** rows). That is
exactly the branch's trigger — `int(self.meta.trained_rows) > len(X)` — so the badge was
declared unfalsifiable, **set aside** (`ignore_champion=True`), and `logistic` cleared the
cold-start bar at **0.24728 < 0.25** and deployed. Under the normal branch,
`0.24728 < 0.1537 − 0.005` is FALSE and `champion_brier >= 0.25` is FALSE — **it would
have rejected**.

> **Why the doctrine transferred.** ML-083 keys on a **structural** condition (a watermark
> that indexes a population the matrix cannot contain), not on the *reason* the populations
> diverged. Shrink-by-filter and corrupt-then-repair produce the **same structural
> signature**, so a rule written for one polarity handled the other without modification.
> **This is the argument for stating gate conditions structurally rather than narratively.**

**What that does NOT establish.** The branch detects orphaning by a **row-count proxy**. It
caught this because the corrupted corpus was **larger**. A corrupt population that happened
to be **smaller** than the clean matrix would compare "successfully" against incommensurable
rows and pass unremarked. **The missing provenance field above is still missing**, and the
right reading of this episode is *the doctrine covered a case it was not designed for*, not
*the class is closed*.

**The operator restraint was load-bearing**, and is the reusable half: the gate was
deliberately **not** overridden, so the self-heal was **observable**. Overriding would have
produced the same deployed model while hiding the fact that the system could reach it
alone — and would have spent a [[concepts/conscious-re-baseline]] that was never needed.
**The corpus repair was the necessary and sufficient intervention; the model layer healed
itself once the data was true.**

## The general lesson
A filter that auto-activates on data must have **every consumer wired in the same commit** — the
consumer-consistency rule of the [[concepts/gort-rule]]. This deadlock is what that rule exists to
prevent.

**Extended 2026-08-09:** wiring is necessary and not sufficient. Every consumer *was* wired
for the wedged-champion case; they all read a corrupted input and behaved correctly on it.
The complementary rule: **a filter that auto-activates on data must also have its INPUT
protected independently of itself** ([[concepts/era-exclusion]] §the failure mode of arming
on data, [[concepts/migration-idempotence]]).

## The third polarity — the release mechanism over-releases (2026-08-14)

The first two polarities are *locked out* (watermark exceeds the corpus, gate fails closed
forever) and *wedged in* (champion's score computed on a corrupted corpus). ML-083 released
both, the second **unmodified**, because it keys on a structural condition rather than on why
the populations diverged. That remains this page's best result.

The third polarity is the same branch **releasing too far**, because nothing bounds how far
apart the populations may be:

```python
elif int(self.meta.trained_rows) > len(X):      # main.py:6387
    _deploy_ok = self.monitor.should_deploy(
        challenger_brier, n_oof=len(oof_cal), ignore_champion=True)
```

The branch's own comment records the case it was built for on 2026-07-29: **4,823 vs 1,516 —
a 3.2x orphan ratio.** On 2026-08-14T15:14:13Z it fired at **10,217 vs 211 — 48x** — and with
the badge set aside the challenger faced only the cold-start bar `Brier < 0.25`. A logistic
trained on **2.0%** of the incumbent's data deployed at `oof_brier` 0.21887 while its own
`family_brier` was **0.33105 — worse than the 0.25 a constant p=0.5 predictor scores.** The
only upstream floor is `len(X) < 60` (`main.py:6237`), which 211 clears comfortably.

Then the gate **defended the regression**: post-deploy `trained_rows` became 211, so the
unlock stopped firing, and the next challenger — with a *better* OOF Brier of **0.17959** —
was rejected by the like-for-like branch for having no shared row set. Correct fail-closed
logic protecting a worse incumbent.

**The rule this yields:** *a gate's refusal to compare is the gate working*
([[concepts/false-green]] design rule 9) — **but the escape hatch that resolves an
unfalsifiable badge must itself be bounded.** "Cannot compare" was read as *proceed on the
cold-start bar*, where the honest reading at 48x is *escalate*. Unbounded, "an unfalsifiable
badge may not gate forever" degrades into "a sufficiently stale badge may be ignored
entirely" — so the staler the badge, the weaker the bar, which is backwards.

Framed as a migration rather than a model problem this is a **cutover with no compatibility
gate and no rollback path** (repo `docs/quant/2026-08-14_model_promotion_migration_design.md`,
GAP-1/GAP-2). Lineage consequence: the registry held **134 `registered` events and ZERO
`deployed`** ones until `61c3b5c1`, so this promotion left no lifecycle record at all.

Fixing the floor changes which model deploys → entry decisioning → **cohort-resetting**, so it
is fenced by [[synthesis/governance-doctrine]] rule 17 and awaits operator adjudication. It is
**not independent of** [[synthesis/owed-measurements]] item 67: the h432 geometry cut shrank
the honest corpus, era exclusion correctly refused to pool it, *that* produced the 48x ratio,
and the promotion landed inside the accruing verdict window — 6 of 13 trips straddle a deploy
and two distinct champions opened trips.
— [[sources/session-20260814-cohort-instruments]] Finding 2
