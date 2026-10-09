---
title: Label Era
category: concept
summary: "A per-row tag of which label-definition era produced the row — CORRECTED 2026-08-09: the era is a PERSISTED column, and 'derive it from the barrier string' is only the legacy fallback. Deriving it unconditionally is a corruption mechanism: label_era_of() has no horizon knowledge, so re-deriving a qualified row pools incompatible label definitions under one name — 2,729 rows, measured"
tags: [labeling, corpus, provenance, idempotence, incident]
sources: 7
updated: 2026-08-27
---

# Label Era

## Definition
Each corpus row carries a `label_era` tag identifying which label definition produced it.

> ⚠️ **CORRECTED 2026-08-09 — the "derived purely from the barrier string" framing below
> was the original design, and it is exactly the premise the corpus-corruption incident
> falsified.** The era is a **PERSISTED column written by the producer**. Derivation from
> the barrier string is a **legacy fallback for rows that have no persisted value** — never
> a recomputation rule. See §*The persisted-era rule* and
> [[sources/session-20260809-corpus-corruption]].

## The persisted-era rule (binding, 2026-08-09)

**The producer persists the era; every downstream reader passes it through unchanged;
derive ONLY when the value is absent.**

The reason is that the two computations are not the same function
([[concepts/two-paths-one-quantity]]):

| Path | Function | Produces |
|---|---|---|
| **Writer** (production) | `ml/history.py` `_row_era` → `triple_barrier_era(label_max_bars)` | `triple_barrier_h432` — **horizon-qualified** |
| **Derivation** (fallback only) | `label_era_of(barrier)` | `triple_barrier` — **unqualified for ANY `tb_*`** |

`label_era_of()` **has no horizon knowledge and cannot acquire it** — the barrier string
`tb_pt` is identical in the 96-, 24- and 432-bar eras. So **a barrier string is sufficient
to identify the label *vocabulary* but NOT the label *definition*.** The original page
below conflated the two, and so did the migrator.

**Measured cost of the conflation:** `scripts/migrate_history.py:125` re-derived
`label_era` on every migration pass — the only non-idempotent trailing column in
`migrate_rows` — retagging **2,729 rows** (`triple_barrier_h24` → `triple_barrier` 2,077;
`triple_barrier_h432` → `triple_barrier` 652) so that one bucket pooled **three
incompatible label definitions**. Downstream it disarmed the era filter, released 9,746
pooled rows into training, and deployed a champion on a data bug
([[sources/session-20260809-corpus-corruption]] §1–§4). Fixed in `3c0debd7`; corpus
repaired from backups by position_id join.

## Why source-agnostic purity matters (as originally designed)
Because era is a function of the row's own vocabulary, a **backfill or replay written today under the
old labeler is still tagged old-era**, and a re-simulated old row cannot sneak in on a fresh timestamp.
Verified with 20 test executions, zero flakes.

> **What survives and what does not.** Source-agnosticism **survives** — era must never
> depend on *which writer* produced the row. What does **not** survive is the inference
> that a pure function of the barrier string is therefore safe to apply **repeatedly**.
> Purity guarantees determinism, not **information sufficiency**: a pure function that
> cannot see the horizon destroys the horizon every time it runs.

## The vocabularies
- `triple_barrier`: `{tb_pt, tb_sl, tb_time}`
- `exit_sim`: `{trail, realized, tier, floor, sl, time}`
- `exit_sim_time_stop`, `legacy`, `unknown`

A **disjoint-vocabulary partition**, not a per-source rule.

## The era-collision that forced the design
The new labeler natively emitted bare `pt`/`sl`/`time` — the **same strings** older eras already
claimed. Flipping the label mode alone "would have silently mis-tagged every new row into two OLD,
incompatible populations — exactly the failure the era instrument exists to catch." Fix: prefix with
`tb_` **at the one dispatch call site whose output reaches the persisted corpus**, leaving the labeler
function itself untouched.

## Conservative unknown handling
`LABEL_ERA_UNKNOWN` is treated as **old-era (excludable)**: an unrecognized barrier string is only
evidence that the era map has never seen it, not evidence the row is new.

## Horizon qualification — the load-bearing extension, and the thing that keeps breaking
Because changing the horizon changes **what the label means**, the era identity was later extended to
encode it (`triple_barrier_h24`). This qualification immediately broke a filter that had hardcoded the
un-qualified constant — see [[concepts/era-exclusion]].

**It has now broken something THREE times, always the same way: a consumer that knows the
unqualified constant meets a corpus that speaks the qualified one.**

| # | Date | Where | Effect |
|---|---|---|---|
| 1 | 2026-08-01 | a filter hardcoding the unqualified constant | filter selected production's exact **complement** (audit H12) |
| 2 | 2026-08-01 | `overfit_check`'s bare `HistoryStore()` default (96) vs `main.py`'s `triple_barrier_h24` | every OF verdict measured on a corpus the bot **never trains on** |
| 3 | **2026-08-08/09** | `migrate_history.py:125` re-deriving with `label_era_of()` | **2,729 rows pooled**, era filter disarmed, champion deployed on a data bug |

> **The pattern to watch for:** anywhere the *unqualified* era name can be produced by code
> that never saw `label_max_bars`. Instances 1 and 2 were **read-side** (a wrong view,
> recoverable by fixing the reader). Instance 3 was **write-side** — it changed the corpus
> on disk, and only a preserved backup made it recoverable at all.

## Why this tag is worth the trouble
`label_era` is the **only** thing standing between the corpus and a silently pooled training
set. It is not bookkeeping: [[concepts/era-exclusion]] arms on a count of current-era rows,
[[concepts/evidence-floors]] gate on the same population, and the whole
[[comparisons/horizon-96-vs-24-bars]] experiment is defined by it. **A wrong era tag is not
a wrong label — it is a wrong CORPUS**, and every measurement taken on it inherits the error
without any instrument reading as broken.

## The gap it exposed
Live closes stamp a fixed `barrier="realized"` regardless of label mode ("a live fill has no barrier
vocabulary of its own"), so **no live row could ever join the new era** — the six-link chain of
[[sources/live-label-era-deadlock]]. *(Note the shape: because live rows carry no era-bearing
barrier vocabulary at all, they depend **entirely** on the persisted column — which is why
re-derivation is unusually destructive for exactly the rows the project most needs.)*

## Two provenance columns, two axes — do not confuse them (2026-08-14)

The corpus now carries **two** era stamps on **different axes**, and a session conflated them
once already:

| column | file | axis | current value |
|---|---|---|---|
| `label_era` | `signal_history.csv` | **label** definition | `triple_barrier_h432` |
| `exec_era` | `fills.csv` | **fill-simulator** regime | `7-e7d5ca1a` |

They move independently — [[synthesis/comparability-boundaries]] tracks the fill axis, the
label axis (`7566ea88`) and the capital axis as separate cuts. A row can be current on one and
retired on the other.

**Two facts measured the same day, one per axis:**

- **Label axis:** the current era is **259 of 10,559 rows — 2.5%** of the corpus, and base
  rates across eras span **40x** (`exit_sim_time_stop` 0.0065 → `legacy` 0.2611). Full table on
  [[concepts/era-exclusion]] §what correct exclusion costs.
- **Fill axis:** `exec_era` has a failure mode this page's own doctrine predicts. The page
  records that live rows *"depend **entirely** on the persisted column"* — the same is true of
  `exec_era`, and six `fills.csv` rows have it **ABSENT rather than blank** (width histogram
  `{17: 1059, 16: 6}`; it is the last of 17 columns), written by a binary whose `COLS` predate
  the stamp. The standing *blank = decide by ts* rule returns **era-7** for rows whose physics
  is **pre-boundary-#4**.

**The generalization for this page:** *"decide it by timestamp when the stamp is missing" is
safe only when a missing stamp means the writer was old-but-honest.* It is unsafe when a
missing stamp means **the writer did not know the column existed** — those two cases are
indistinguishable from the value alone and distinguishable from the **row shape**. Same family
as this page's 2026-08-09 correction (*derive it from the barrier string* is a legacy fallback,
not a rule): **a derived era is a guess wearing a column's name.**
([[sources/session-20260814-cohort-instruments]] Finding 1)

**2026-08-27 — the doctrine reached an instrument, and both of this page's rules were applied.**
The veto-quality report (`gate_efficacy_report.py`) had been grading vetoes against a baseline
with **zero `label_era` overlap** with the codes it graded (frozen 2026-07-20 backfill, 84.1%
`legacy`, 0% `triple_barrier*`) — a cross-era pooled comparison of exactly the kind this page
forbids, published as "ANTI-SELECTIVE at significance". The fix (`a94b5751` + hardened
`62ab10c0`) makes the instrument REFUSE across disjoint eras (weighted-overlap floor +
`CONFOUNDED_BASELINE`), and — this page's 2026-08-09 correction applied verbatim — rows whose
era can only be *derived* (no persisted column, no horizon information to qualify the guess)
now go to **UNKNOWN rather than through `label_era_of()`**. Consequence: every veto-quality
verdict is confounded pending a live baseline (owed 104).
([[sources/session-20260827-sdd-verification-and-era-confound]] §2)

## Related
[[concepts/era-exclusion]] · [[concepts/migration-idempotence]] ·
[[concepts/two-paths-one-quantity]] · [[concepts/triple-barrier-labeling]] ·
[[concepts/evidence-floors]] · [[entities/historystore]] ·
[[comparisons/horizon-96-vs-24-bars]] · [[comparisons/era-exclusion-vs-epoch-filter]] ·
[[sources/session-20260809-corpus-corruption]] · [[sources/live-label-era-deadlock]] ·
[[sources/live-row-era-gap]]
