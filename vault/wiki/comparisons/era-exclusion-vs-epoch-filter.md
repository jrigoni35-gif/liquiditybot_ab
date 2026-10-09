---
title: Era Exclusion vs Epoch Filter
category: comparison
summary: Two corpus filters over the same consumers, deliberately kept separate: one keys on label definition, one on time
tags: [comparison, corpus, filtering]
sources: 3
updated: 2026-08-01
---

# Era Exclusion vs Epoch Filter

Two filters restricting which rows train, deliberately **not merged**.

| | Era exclusion | Epoch filter |
|---|---|---|
| Keys on | the row's **label definition** (its barrier vocabulary) | the row's **timestamp** |
| Scope | candidate **and live** rows | candidate rows **only** |
| Activation | **auto-arms** at a derived row count | ships `false`, requires a conscious flip |
| Runs | last, post-hoc over survivors | per-row, in the main loop |
| Status | **shipped and active** | shipped inert, never flipped |

## Why era-based beats time-based here
A backfill or replay written **today** under the old labeler is correctly excluded on its era, and a
re-simulated old row cannot sneak in on a fresh timestamp. A clock-based filter gets both cases wrong.

## The composition
Both may run simultaneously; the epoch filter runs first. In practice the composition is a no-op:
because new-era rows can only exist after a date that postdates the epoch cutoff, **no new-era row can
ever be epoch-excluded**, so the two filters together give the same corpus as era alone.

## The consequential asymmetry
Because era exclusion **auto-activates on data**, an unwired consumer could "silently start measuring or
training a stale corpus the moment the threshold crosses on disk." So all consumers were wired **in the
same commit**. The epoch filter, which requires a human flip, was allowed to defer that work — a
prerequisite owed at flip time.

**Two filters, same consumers, opposite deferral decisions — and the distinguishing reason is
auto-activation.** This is the clearest worked example of the consumer-consistency rule in the
[[concepts/gort-rule]].

## Related
[[concepts/era-exclusion]] · [[concepts/label-era]] · [[sources/pbo-admission-policy]]
