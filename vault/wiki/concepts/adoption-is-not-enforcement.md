---
title: Adoption Is Not Enforcement
category: concept
summary: An invariant that depends on every future author remembering it is not enforced — "we fixed all of them" and "nothing new can appear" are different claims, and the gap between them is where a defect class survives; the torn-append gate is the type specimen, where the very first AST inventory found a writer the by-inspection sweep had missed — the very next commit reopened the same gap for a different class, the recursion's sharpest instance arrived 08-07 when the DoD's own pyright stage turned out to have quietly not existed for weeks, and 08-09 supplied the extreme case of proximity — a migrator line that violated an idempotence rule documented in the comment TWELVE LINES BELOW it, with the other nineteen columns as correct worked examples, costing 2,729 corrupted corpus rows
tags: [method, discipline, defect-class, tests, gates, enforcement]
sources: 6
updated: 2026-08-09
---

# Adoption Is Not Enforcement

## The claim

Fixing every instance of a defect class closes the **instances**. It does not close the **class**.
The class stays open as long as re-opening it requires nothing but a future author typing the
obvious thing.

> **"We fixed all of them" and "nothing new can appear" are different claims, and only the second
> one is enforcement.** A rule that lives in a docstring, a convention, a review habit, or a wiki
> page is enforced by *everyone remembering*, which is not enforcement — it is a **prediction
> about future attention** that the repo has repeatedly falsified.

The distinction is not academic here. It is the difference between a fix that holds and one that
buys time until the next contributor — including a future session of the same agent — reaches for
the primitive that is *not* in scope and writes the plain one that is.

## The type specimen: three rounds of adoption, then a gate

[[concepts/torn-append-fusion]] is the worked example, and it is unusually clean because the
timeline is compressed into two days.

| Round | Mechanism of "enforcement" | What happened |
|---|---|---|
| 1–3 (`b409a24b`, `46cdc19a`, `4799bfc7`) | **Per-file fix.** Each writer heals its own tail. | The class reappeared in a **different subsystem** each time. |
| 4 (`ee0ac4ad`) | **A shared primitive.** `core/runtime.durable_append`, placed beside `atomic_write_json` in an already-imported module, adopted by eight writers. | **Ten files clean, zero fusions** — a genuine sweep. But the invariant was still enforced by **adoption**: a future writer typing `open(path, "a")` re-opened the class **silently**. |
| 5 (`0e30ca09`) | **A gate.** `tests/test_append_invariant.py` walks the AST of shipped code and fails on any append-mode `open` outside a 13-entry reasoned allowlist. | **The very first inventory found a writer the round-4 sweep had missed** — `scripts/session_import.py:366`, a third independent appender to the training corpus, running hourly and unattended. |

> **That last cell is the entire argument.** The round-4 sweep was careful, deliberate, and
> conducted by someone who had the defect shape fully in mind. It still missed a writer. **The
> gate found it on its first run, for free, as a side effect of existing** — because a gate does
> not search, it **enumerates**.

## The sharpest instance yet: the rule was in the comment TWELVE LINES BELOW (2026-08-09)

The corpus-corruption incident ([[sources/session-20260809-corpus-corruption]]) is this
page's extreme case, because the distance between the rule and its violation was as short as
it can physically be.

`scripts/migrate_history.py:125` recomputed `label_era` unconditionally. **The idempotence
rule it violated is documented in the `pt_frac` comment IMMEDIATELY BELOW it** — *"a second
migration pass must never clobber real geometry."* Every other trailing column in the same
function (`pt_frac`, `sl_frac`, 7 × `sg_*`, `entry_price`, `exit_price`, 4 × `avail_*`)
implements the rule correctly. **One line out of twenty, with the rule written directly
underneath it, and the surrounding twenty as worked examples.**

> **Proximity is not enforcement, and neither is unanimity.** A convention followed by
> nineteen of twenty sites is *more* dangerous than one followed by none: the consistency
> makes the file read as compliant. Nobody diffs a function against itself.

**Cost of the gap:** 2,729 corpus rows retagged, three label definitions pooled, the era
filter disarmed, four evidence floors cleared at once, a champion deployed on a data bug —
from a rule that was **present, correct, and adjacent**.

**The gate that closes it** is the middle test of `tests/test_migrate_history.py`:
**`migrate(migrate(x)) == migrate(x)`**. Note what it does *not* do — it does not know what
`label_era` means, does not enumerate columns, and cannot go stale as columns are added. It
is the [[concepts/migration-idempotence]] analogue of the AST append gate: **a property over
the function's shape rather than a check of its contents**, which is what lets it catch the
*next* instance rather than this one.

**And the recursion fired again the same day, one layer up.** The battery's timing-family
split (owed 44) registered `timing` under `--strict-markers` so a **typo'd** mark is a
collection error — genuine enforcement. But `tests/test_import_integrity.py` was **never
marked at all**, and `--strict-markers` cannot see an absence. It went red on
`TimeoutExpired` as the most self-saturating test in the suite (8 threads × ~100 interpreter
spawns; solo 4.3s). **A gate over the vocabulary of declarations does not enforce that a
declaration was made** — the same shape as the pyright stage that could report `SKIPPED`.
Timing family 17 → 18.

## Why sweeps by inspection under-find, structurally

A by-inspection sweep is a **search**: it finds what the searcher thinks to look at. Its coverage
is a function of attention, and attention is exactly the resource that is scarce at the end of a
long debugging session — which is precisely when sweeps get run.

A gate is an **inventory**: it evaluates a mechanical predicate over an enumerated set. Its
coverage is a function of the scan scope, which is **written down and reviewable**.

This is the same reason the corpus prefers [[concepts/adversarial-verification]] over
self-review, and it rhymes with [[concepts/iron-law-of-debugging]]: the failure is not
insufficient care, it is **trusting an enumeration nobody enumerated**.

## The design rules this class produced

1. **Make the exemption list the product.** The gate's real output is not the pass — it is the
   **written reason** attached to each of the 13 allowed files. `core/runtime.py`'s
   `JsonlEventHandler.emit` is a deliberate bare append (calling the primitive from inside a
   logging handler would **re-enter that handler**); recorded in the allowlist, it stops being
   an oversight for the next sweep to re-discover.
2. **Keep the allowlist from rotting.** A companion test removes entries that **no longer
   append**, because *a stale exemption silently covers a FUTURE append* — the allowlist is the
   one part of a gate that decays into a hole.
3. **Assert positively as well as negatively.** "No bare append" catches *replacing* the
   primitive's call. A separate parametrized test that five named data writers **contain**
   `durable_append` catches **deleting** it.
4. **Use the AST, not a regex.** Prose false-positives: this repo's docstrings, comments and wiki
   pages discuss `open(..., "a")` constantly. Only real calls with a **literal** mode count. The
   same reason `tests/test_code_registry.py` is AST-based.
5. **Prove the gate bites.** A bare append was injected into `ml/interpret.py`; the gate failed
   with file and line, and the injection was reverted. **A gate never shown to fail is a gate
   whose passing means nothing.**

## The recursion, stated honestly

**A gate is itself adopted.** `SCANNED_DIRS` in the append gate is a hardcoded tuple — verified
to match the repo's ten non-test packages today, but **a new top-level package is unscanned until
someone remembers to add it.** And the allowlist is **per-file, not per-call-site**, so a file
exempted for its text log is exempt for its data writes too.

> **This does not dissolve the distinction; it relocates it.** The class moved from "enforced by
> everyone remembering, everywhere" to "enforced except in 13 named files and one excluded
> directory." That is a **different order of exposure**, and — unlike a convention — the residue
> is **finite, listed, and greppable**.

The honest form of this concept is therefore not *"gates close classes"* but: **a gate converts an
unbounded obligation on all future authors into a bounded, written, reviewable list.** That is
what enforcement buys.

## The next commit reopened the question — one day later, a different class (2026-08-06)

`5c111962`, the **immediately following commit**, fixed the hedger's open/unwind thrash by
extracting a shared `_exposure_by_asset()` helper so both paths read one definition of *"which
asset are we exposed to."* **It shipped no gate.**

The shared helper is a **convention**. The commit's own
`test_exposure_helper_excludes_hedges_and_is_shared` **asserts sharing in its name only** — it
calls the helper directly and checks the hedge leg is excluded; it never checks that either path
*uses* it. **A future author re-inlining a third exposure computation is caught by nothing.**

> **The distance this concept names is exactly the distance that commit did not travel:** *"we
> fixed both paths"* is the round-4 claim, not the round-5 one. And the same commit's headline
> test — `test_open_and_unwind_agree_across_repeated_evaluations`, named for the money bug — is
> **green on the buggy code**, because `evaluate()` is a pure function of a state the test never
> mutates. **Design rule 5 below, stated on 2026-08-06, was not applied on 2026-08-06.**
> ([[sources/session-20260806-hedge-thrash]] §5-6)

**The honest asymmetry**: the append class had a **mechanical predicate** (`open(..., "a")`) that
an AST walk can enumerate. *"No quantity is computed twice"* has no such predicate, so the gate
here is genuinely harder to build — which is a reason to record the residual precisely, **not** a
reason to call the convention enforcement. The tractable substitutes are named on
[[concepts/two-paths-one-quantity]].

### The vacuous test was repaired the next night — and the repair taught a red-check technique (2026-08-07)

`af544d4c` closed the gap this section flagged: the test now drives the engine the way the
runner does — **evaluate, APPLY the returned actions to the book, evaluate again** — and was
proven RED against the genuine pre-fix engine: **13 opens / 12 unwinds alternating** over 25
cycles pre-fix, **1 / 0** post-fix ([[sources/session-20260807-hedge-churn-guards]] §4). Design
rule 5, stated 08-06 and skipped 08-06, discharged 08-07 — *by a different author reading the
written residual*, which is the mechanism this vault exists to provide.

> **Technique worth keeping: once a fix is COMMITTED, `git stash` cannot produce the red run.**
> The earlier "red-check" (`git stash push -- execution/hedging.py`) was a **no-op** — it
> compared the fixed engine against itself and reported green-means-nothing as green-means-red.
> The correct form loads the parent's blob as a scratch module
> (`git show <parent>:<path>` → separate module object), so the live tree is never reverted and
> the comparison is real. Proving a gate bites requires the **buggy code to actually run**;
> whether it still exists in the working tree is exactly the thing to verify, not assume.

## The recursion's sharpest instance: the gate that quietly did not exist (2026-08-07)

The capacity sweep ([[sources/session-20260807-capacity-sweep]]) caught the "a gate is itself
adopted" recursion in its purest form — not a gate with a coverage hole, but **a gate whose
entire existence was a convention**:

- **The pyright type-ratchet stage had printed `SKIPPED` for weeks** because the tool was
  never installed on the box — while CLAUDE.md claimed a **zero-error ratchet** as part of the
  Definition of Done. The stage was adopted into `test_windows.bat`; **nothing enforced that it
  could run**, so its absence rendered as its pass. Fixed: the bat now **hard-fails on a
  missing tool** (pyright 1.1.411 in-venv, 0 errors on shipped scope, measured).
- **Full-scope ruff was RED on the live tree** the whole time (C901: `restore()` 42 > 40, from
  `cf454d5e`'s hedger snapshot section) — a gate that existed and worked, **run by nobody**
  after the pull. Enforcement has a *cadence* dimension: a gate is only as true as its last
  full-scope run on the current tree.

> **"A gate that can quietly not exist is a gate that lies."** The reporting-channel variants
> of this failure — the skipped stage, the vacuous test above, and an invocation that exited 0
> without running any stage — now have their own page: [[concepts/false-green]].

## Where else this applies in the corpus

- [[concepts/never-widen-a-gate]] — the sibling rule about what to do when a gate **fires**. This
  concept is about whether the gate **exists**; that one is about not softening it once it does.
- [[concepts/location-invariant-tests]] — the deploy gate's own contract; a test that filters by
  path is an invariant enforced by an assumption about where it runs.
- [[concepts/default-path-fallback-writes]] — the repo's **most-recurring class (seven
  instances)**, still enforced substantially by convention. The append gate **deliberately
  excludes `tests/`** (a test that fabricates a torn tail must append), which is exactly where
  that class lives — so the two classes meet at the boundary the gate declines to cross.
- [[concepts/inertness-protocol]] and [[concepts/shadow-first-adoption]] — the same "shipped is
  not working" distinction one layer up: a mechanism that exists but influences nothing.
- [[comparisons/stated-invariants-vs-audited-reality]] — the running table of invariants that
  were believed and false. The torn-append row is unusual there: the invariant was **stated,
  believed, freshly swept, and still false**.

## Related
[[sources/session-20260806-append-gate]] · [[sources/session-20260806-geometry-filing]] ·
[[sources/session-20260806-hedge-thrash]] · [[sources/session-20260807-hedge-churn-guards]] ·
[[sources/session-20260807-capacity-sweep]] · [[concepts/false-green]] ·
[[concepts/two-paths-one-quantity]] ·
[[concepts/torn-append-fusion]] · [[concepts/never-widen-a-gate]] ·
[[concepts/default-path-fallback-writes]] · [[concepts/location-invariant-tests]] ·
[[concepts/adversarial-verification]] · [[concepts/iron-law-of-debugging]] ·
[[comparisons/stated-invariants-vs-audited-reality]] · [[synthesis/owed-measurements]] ·
[[entities/historystore]]
