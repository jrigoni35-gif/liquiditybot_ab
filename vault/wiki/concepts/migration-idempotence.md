---
title: Migration Idempotence (a migrator that is not a fixed point is a data-destruction loop)
category: concept
summary: A schema migrator runs an unknown number of times on the same rows, so any column it RECOMPUTES rather than passes through is destroyed on every pass — and the destruction is silent, cumulative, and invisible to every downstream instrument, which keeps reading a perfectly well-formed corpus that now means something else. Adjudicated 2026-08-09 as the SPECIAL CASE of two-derivations-of-one-truth in which one derivation persists — the top rung of that class's report/decide/persist ladder
tags: [defect-class, corpus, data-integrity, idempotence, migration, invariants]
sources: 2
updated: 2026-08-09
---

# Migration Idempotence

## The claim

**A migrator is not a transformation you apply; it is a transformation that gets applied an
unknown number of times.** Rotation, backup recovery, bundle import, an operator re-run —
each is a fresh pass over rows that may already be migrated. The only safe shape is a
**fixed point**: `migrate(migrate(x)) == migrate(x)`.

Any column the migrator **recomputes** rather than **passes through** violates this, and the
violation has three properties that make it unusually expensive:

1. **Silent.** The output is a well-formed corpus. No parse error, no width mismatch, no
   row loss. Every downstream reader succeeds.
2. **Cumulative.** Each pass re-applies the damage. Two rotations sixteen seconds apart cost
   twice.
3. **Lossy in the direction of *less* information.** A recomputation can only use what the
   recomputing function can see. If the persisted value was written by a producer that knew
   more, **the difference is destroyed** — and destroyed *toward a plausible value*, which
   is why nothing alarms.

> **The rule:** in a migrator, the default for every existing column is
> `r.get(X) or <pad>`. **Deriving is the exception, permitted only when the value is
> ABSENT.** A derivation that runs unconditionally is a bug even when the derivation
> function is correct.

## The type specimen — `label_era`, 2,729 rows

`scripts/migrate_history.py:125` recomputed `label_era` unconditionally as
`label_era_of(r.get("barrier") or "")`. It was the **ONLY non-idempotent trailing column**
in `migrate_rows` — `pt_frac`, `sl_frac`, the 7 `sg_*`, `entry_price`, `exit_price` and the
4 `avail_*` all use the pass-through shape.

The recomputing function **could not see what the writer saw**: `label_era_of()` has no
horizon knowledge and returns the unqualified `triple_barrier` for any `tb_*` barrier,
while the producer persists the qualified `triple_barrier_h432`
([[concepts/label-era]]). So each pass merged label definitions that must never share a
name — **2,729 rows across two rotations**, and a training corpus that had forgotten which
of three label definitions produced each row
([[sources/session-20260809-corpus-corruption]]).

**Zero rows were lost.** That is the point: row counts, checksums, widths, header
invariants and append gates were all satisfied throughout.

## Why the ordinary defenses do not see it

This corpus already has strong write-side machinery — `durable_append`
([[concepts/torn-append-fusion]]), the AST append gate, atomic writes, rotation with
backups. **None of them are aimed at this.** They protect the *record* (every byte that was
written is still there, uncorrupted). Migration idempotence protects the *meaning* (the
bytes still say what the producer meant).

| Defense | Protects against | Blind to this |
|---|---|---|
| `durable_append` / torn-append gate | crash mid-write welding two records | ✅ every write here was clean |
| atomic write + rotation backups | losing the file | ✅ nothing was lost — and the backups are what enabled repair |
| schema-width invariants | column drift | ✅ width was exactly right |
| row-count / position_id joins | dropped rows | ✅ counts matched exactly |
| era-exclusion arming threshold | training on the wrong era | ❌ **it read the corrupted column and disarmed itself** |

The last row is the sharp one: **the mechanism designed to protect the corpus's era
integrity consumed the corrupted era column and concluded it should stand down.** A guard
that reads the quantity it guards has no defense against that quantity being wrong.

## The recognition heuristics

- **Read the migrator's columns as a list and ask of each: derive or pass through?** A
  single derive among twenty pass-throughs is the signature. Mixed policy in one function is
  the smell; consistency is cheap to eyeball, correctness is not.
- **Ask what the deriving function CANNOT see.** Not "is it correct" — it usually is, for
  the rows it was written for. Ask what the *producer* knew that this function does not:
  config, horizon, mode, calendar, version. That delta is exactly what a pass destroys.
- **Count the entry paths.** Rotation, `.bak` recovery, bundle import, manual re-run,
  unattended hourly sync. The `label_era` defect existed in **two** scripts —
  `migrate_history.py` and `session_import.py:244`, the latter running **hourly and
  unattended**. A migrator called from one place is rare.
- **A schema change is a migration TRIGGER.** The incident fired because that session's own
  commit added four columns. **Any commit that changes corpus width should be read as "the
  migrator is about to run on every row you own."**

## The gate

`tests/test_migrate_history.py` now pins three properties, written red-first:

1. **a persisted era is preserved** (the specific defect);
2. **migration is a fixed point** — `migrate(migrate(x)) == migrate(x)` (**the class**);
3. **a legacy row still derives** (the fallback still works, so the fix is not a
   regression).

**Test 2 is the one that matters.** Tests 1 and 3 pin this instance; the fixed-point
property is a claim about the function's *shape* and would have caught the defect on any
column — the distinction [[concepts/adoption-is-not-enforcement]] keeps insisting on. It is
the same escalation the append invariant made when it moved from "we fixed all of them" to
an AST gate that immediately found a ninth writer.

> **A fixed-point test is unusually cheap for what it buys**: it needs no knowledge of what
> the columns mean, cannot go stale as columns are added, and fails loudly the first time
> anyone reintroduces a derive.

## Relation to neighbouring classes

- [[concepts/two-paths-one-quantity]] — **the supplier of the divergence, and the
  generalization.** Idempotence fails *because* two paths compute the era differently; if
  the migrator called the writer's own function it would still be wasteful but harmless.
  This class explains why the disagreement gets *written down*.
  > **Stated as the containment, 2026-08-09:** *this page is the special case of
  > two-derivations-of-one-truth in which one derivation **persists**.* The parent class's
  > severity ladder runs **report → decide → persist**; migration idempotence is the top
  > rung, and it is the only rung where the loser of the disagreement survives a restart.
  > The night that produced this page produced **three** instances of the parent class —
  > `label_era` (persist), `_explore_on` (report), the champion badge (decide) — which is
  > the evidence that the generalization is the real unit and this page is a specialization
  > of it ([[sources/session-20260809-gate-policy-and-self-heal]] §4).
  > **Practical consequence:** the fixed-point test below is the *persist*-rung gate. The
  > *decide* and *report* rungs need the parent class's remedy instead — **one shared
  > definition both paths invoke** — because there is no on-disk artefact to compare against
  > itself.
- [[concepts/adoption-is-not-enforcement]] — **the rule existed and was documented in the
  comment immediately below the violating line** ("a second migration pass must never
  clobber real geometry"). Twelve lines of proximity bought nothing.
- [[concepts/torn-append-fusion]] — the sibling corpus-integrity class, and the contrast
  above: record integrity vs meaning integrity.
- [[concepts/false-green]] — the downstream consequence: a corrupted corpus **cleared four
  evidence floors in one step** and produced a deployment. Nothing printed red until an
  independent instrument (the overfit battery) went red for the *wrong stated reason*.

## Related
[[sources/session-20260809-corpus-corruption]] · [[concepts/label-era]] ·
[[concepts/two-paths-one-quantity]] · [[concepts/adoption-is-not-enforcement]] ·
[[concepts/torn-append-fusion]] · [[concepts/era-exclusion]] ·
[[concepts/evidence-floors]] · [[concepts/false-green]] · [[entities/historystore]] ·
[[concepts/iron-law-of-debugging]]
