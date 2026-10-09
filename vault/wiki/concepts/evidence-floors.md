---
title: Evidence Floors
category: concept
summary: "Per-family live-label and total-row minimums checked before any selection reading, so under-evidenced families cannot manufacture a lucky winner — and, 2026-08-09, the first case where the floors were CLEARED rather than locked: a corrupted era column took live_clean 5→299 and cleared gbt/blend/mlp/adaptive_gbt in ONE step, deploying a champion nine minutes later; a floor is only as true as the counter it reads, and four floors clearing simultaneously is itself an alarm"
tags: [model-selection, gates, live-labels, incident]
sources: 5
updated: 2026-08-14
---

# Evidence Floors

## Definition
Per-family minimums on **live labels** (`min_live_rows`) and **total rows** (`min_total_rows`) decide
whether a higher-capacity family is even admissible. Checked **FIRST**; PBO is read only over families
the floor already let in.

## Rationale
> "A family fit on too few real closed-trade labels only manufactures a lucky winner, which inflates
> PBO for no real reason."

## Observed values
`gbt`/`blend` require 150 total rows and 60 live rows; `adaptive_gbt` requires 250 live rows — a floor
that **never cleared in any document in this corpus** (live labels sat at 240-256 throughout).

## The floor as a derivation source
`ml.era_exclusion.min_new_era_rows = 150` is **derived, not invented**: it equals `ml.min_train_rows`
and `min_total_rows` for the first non-trivial rung. Deriving thresholds from existing floors rather
than picking numbers is a recurring pattern — see [[concepts/never-widen-a-gate]].

## How it became a lock
When [[concepts/era-exclusion]] activated with zero clean live rows, `admissible_families(0, ...)`
returned **`['logistic']`** and every richer family became unreachable **forever** on that path. The
floor did exactly what it was designed to do; the defect was upstream. See
[[concepts/deploy-deadlock]].

## How it became a *release* — the other failure direction (2026-08-09)

Until now every failure of this mechanism was a **lock** (floors too high for the evidence
that existed). The corpus-corruption incident produced the **opposite**: the floors were
**cleared by a counter that was lying**.

A corrupted `label_era` column disarmed era exclusion, so `live_clean` went **5 → 299** and
total rows **690 → 9,746**. In a single retrain, **all four gated families cleared at once**:

| Family | `min_live_rows` | Cleared by |
|---|---|---|
| `gbt` | 60 | 299 |
| `blend` | 60 | 299 |
| `mlp` | 150 | 299 |
| `adaptive_gbt` | **250** | 299 |

`adaptive_gbt`'s 250-live floor **"never cleared in any document in this corpus"** — and the
first thing that cleared it was a data bug. **`gbt` was deployed as champion at 20:10:44**,
nine minutes after the corrupting merge
([[sources/session-20260809-corpus-corruption]] §4).

> **The floors behaved correctly and produced a wrong outcome.** They are a predicate over a
> counter; nothing in them can distinguish evidence from corruption. **A floor is only as
> true as the population its counter describes** — which makes
> [[concepts/label-era]] integrity a *prerequisite* of this mechanism, not a neighbouring
> concern.

**A cheap detector falls out of the incident, and it is worth stating as a rule:**

> **Four independent floors clearing in one step is not evidence; it is an alarm.** These
> floors were deliberately set at *different* values (60 / 60 / 150 / 250) precisely so that
> families become admissible at different times, as evidence genuinely accrues. **Simultaneous
> clearance means the counter jumped, not that the corpus grew** — an append-only corpus
> cannot deliver +294 live rows between two retrains. The same arithmetic tell appears one
> layer up in the battery (+9,272 loaded rows against 33 appended), where it also went
> unread for a day.

## The floors held, and the promotion happened anyway (2026-08-14)

The 2026-08-09 case was floors **clearing on a false counter** (live_clean 5→299, four families
admitted in one step). The 08-14 case is the mirror: **the floors worked perfectly and were
bypassed downstream.**

`live` collapsed **314 → 5** when era exclusion activated, and the floors did exactly their job
— admitted families went **5 → 1**, with `gbt`, `blend`, `mlp` and `adaptive_gbt` all **gated**
for insufficient evidence (`ML_LADDER_GATED` logged with the admitted/gated/live payload). The
retrain matrix fell to **181 → 211 → 237** rows.

Then the sole surviving family deployed anyway — not through the floors, but **around** them,
via ML-083's unbounded era-orphan unlock ([[concepts/deploy-deadlock]] §third polarity). The
deployed logistic's own `family_brier` was **0.33105**, worse than a constant p=0.5 predictor.

**The lesson this adds:** *evidence floors gate SELECTION, not PROMOTION.* They correctly
decided *which family may be considered* and had no say in *whether the winner is good enough
to install*. A floor that admits exactly one under-evidenced family has not approved that
family — it has reported that the corpus can support at most one — **and nothing downstream
read it that way.** Four floors clearing at once was already filed here as an alarm; **four
floors GATING at once deserves the same status**, and currently raises none.
([[synthesis/owed-measurements]] item 73;
[[sources/session-20260814-cohort-instruments]] Finding 2)

Related: [[concepts/migration-idempotence]] · [[concepts/ghost-badge]] (the champion this
released is now wedged) · [[sources/session-20260809-corpus-corruption]] ·
[[concepts/era-exclusion]] · [[concepts/deploy-deadlock]]
