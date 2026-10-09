---
title: Torn-Append Fusion
category: concept
summary: A crash mid-append leaves a fragment; the next append welds onto it, so ONE bad write destroys a GOOD record too — found three times one file at a time, SWEPT 2026-08-06 into a single primitive (core/runtime.durable_append, eight adopters), then GATED the same day by an AST test whose first run immediately found a ninth writer the sweep had missed: a THIRD independent appender to the training corpus, running hourly and unattended
tags: [durability, data-hygiene, defect-class, append-only, ledgers, enforcement]
sources: 5
updated: 2026-08-06
---

# Torn-Append Fusion

## The defect class
An append-only ledger (CSV or JSONL) is written a record at a time. A process death **inside** a
write leaves a **fragment** — a line with no terminating newline. The file is not corrupt yet: one
partial row at the end is a bounded, obvious loss.

Then the process restarts and appends the next record. Because the writer seeks to end-of-file and
starts typing, the new record **welds onto the fragment**. The result is one syntactically-plausible
line that is **neither record**:

> **One bad write takes a GOOD record down with it.** The damage is not the torn row — it is the
> *next* row, which was written correctly by a healthy process onto a file that was not ready to
> receive it. Unbounded in time: nothing about the fused line says when the tear happened.

The fusion is worse than the tear in three ways:
1. **It is silent.** A CSV reader sees a row; a JSONL reader may see valid JSON with merged fields.
   No exception is raised, so no alarm fires.
2. **It destroys a record that was never at risk.** The crash cost one row; the heal-less restart
   costs two, and the second one is a *live* record from the current generation.
3. **It looks like data.** A truncated tail is diagnosable by shape. A fused row has to be
   diagnosed by *meaning*, which usually means downstream.

## The fix pattern — a standing rule that became a PRIMITIVE (2026-08-06)
**Every append-only writer in this repo must, before appending: check whether the file's last byte
is a newline, terminate the tail if it is not, and `fsync` each record after writing.**

> **As of `ee0ac4ad` this is no longer a rule writers are asked to remember — it is a function
> they call.** `core/runtime.durable_append` ([[sources/session-20260806-geometry-filing]]) is the
> **append-mode sibling of `atomic_write_json`**, deliberately placed beside it in a module that
> is already the established import direction. Same durability contract, same never-raise
> discipline; one is for the file republished whole, the other for the file that grows a record
> at a time. **A new append-only writer now re-opens this class only by declining to import
> something that is already in scope.**
>
> **And as of `0e30ca09`, declining is no longer silent.** `tests/test_append_invariant.py`
> ([[sources/session-20260806-append-gate]]) walks the **AST of every shipped module** and fails
> on any `open(..., <mode containing 'a'>)` outside a **13-entry reasoned allowlist**. The rule
> went from *a function they call* to *a function they cannot avoid without writing down why* —
> see [[concepts/adoption-is-not-enforcement]].

**Its three guarantees, in the order the docstring ranks them:**
1. **Size-0 counts as new** — `not path.exists()` does not catch a zero-length file.
2. **A torn tail is ISOLATED, never repaired** — *repair would have to invent the missing bytes;
   isolation loses exactly the one record the kill already destroyed, and no more.*
3. **`fsync` bounds the torn window** to the single record being written.

It **returns `False` on `OSError` rather than raising**, because **every call site is bookkeeping
on a path where the trade, decision or disposition has ALREADY happened** (CLAUDE.md invariant 5).

- **Terminate the torn tail.** The fragment then isolates as **one** junk record that consumers
  skip, instead of fusing with the next good one. The loss stays bounded at exactly what the crash
  cost.
- **`fsync` each record.** Bounds the window in which a record can be torn at all, and makes the
  "last byte is a newline" test meaningful rather than a read of the page cache's opinion.
- **Treat size 0 as "new", not "exists".** The birth-time variant (below): `path.exists()` is true
  of a 0-byte file, so a header-writing branch keyed on existence skips the header forever.

## The record: three found one at a time, eight swept at once, one found by the gate
| # | File | Commit | Mechanism |
|---|---|---|---|
| 1 | `outputs/fills.csv` (`core/fill_ledger.py`) | `b409a24b` — [[synthesis/owed-measurements]] item 29h | Torn final row; next append welds onto it. Heal + per-row `fsync`. |
| 2 | `outputs/fills.csv`, **create window** | `46cdc19a` | Kill in the **create-to-first-flush** gap leaves a **0-byte** file; next append saw `path.exists() == True`, **skipped the header**, and wrote a data row first — `csv.DictReader` then **adopts that FILL as the header** and every consumer misparses the whole ledger. Fixed: `new_file` counts **size 0 as new**. |
| 3 | `outputs/models/registry.jsonl` (`ml/registry.py`) | `4799bfc7` — item 30a | **Same torn-row fusion as instance 1**, in the model provenance ledger. Same heal applied, in the same commit that gave the registry a genuine hash chain. |

Instances 1 and 2 hit the **same book of record** behind the historical **27x P&L error** — see
[[concepts/default-path-fallback-writes]], the sibling class about writes landing in the **wrong
file**. This class is about a write landing in the **right file, unreadably**.

Instance 3 matters beyond hygiene: `registry.jsonl` is the model **provenance** ledger. A fused row
there is a provenance claim that describes no artifact — in a file whose whole job is to make
"which bytes were the champion" answerable later ([[entities/ml-governor]]).

### The sweep — eight more writers, one commit (`ee0ac4ad`, 2026-08-06)
All eight now call `durable_append`. Verified call sites, and why each one earned the fix:

| Writer | File | The specific loss |
|---|---|---|
| `ml/history.py::_append_row` | `signal_history.csv` | The **89-column ground-truth corpus**. A fused row destroys **two labelled outcomes and their 64-feature vectors**, and `load_training_data`'s `except (KeyError, ValueError): continue` **dropped the chimera with no counter and no log line** — so the corpus lost two labelled outcomes per kill, **invisibly**. |
| `scripts/corpus_sync.py` | `signal_history.csv` | The corpus's **SECOND independent appender**. **Two writers with no heal is exactly the seam that produced SD-007** (`audit_chain_break`) on the audit chain: whichever process is killed mid-row, the other welds onto the fragment. Now **one append per recovery batch**, not per row. |
| `ml/history.py::HorizonShadowStore` | `horizon_shadow.csv` | The **size-0 variant, live** — see below. |
| `ml/retrain_log.py` | `retrain_history.jsonl` | **Reproduced: one kill destroyed 2 retrain records.** |
| `data/context_engine.py` | `context_history.jsonl` | **The least reversible append in the repo.** Its point-in-time contract ("never re-fetch") makes a fused snapshot **permanently unrecoverable by design** — *even though its cadence is the lowest*. Frequency is not the right prior for durability; **reversibility is**. |
| `core/runtime.py` | `equity.csv` | 145,576 rows. |
| `ml/postmortem.py` | `postmortem_summary.csv` | Header and row were **two literal lists in two methods**; unified as `SUMMARY_COLS` in the same pass. |
| `main.py::_append_period_row` | weekly + monthly period ledgers | **The only append-only writer in the repo with NO error handling at all** — an `OSError` propagated into the period-close path, so an **unwritable `outputs/` could abort a weekly or monthly roll**. Durability and invariant 5 were both missing here. |

**The size-0 variant recurred one day later, in a different file.** `HorizonShadowStore._ensure`
creates its header under `not exists()`, **which a zero-length file passes THROUGH** — so a kill
in the create-to-first-flush window left a **headerless** file and `csv.DictReader` **adopted the
first RESEARCH ROW as its column names**. **Two consumers read it that way.** This is
**instance 2's exact mechanism**, and its independent reappearance is the strongest argument in
the record for a **shared primitive over a per-file fix**.

**Preventive, not remedial.** All ten files were **clean on disk** at the sweep — **9,692 corpus
rows · 145,576 equity rows · 29,013 audit records · 25,039 events · 44 rotated generations —
zero fusions.** The class was closed before it fired at scale, which is the only time a
durability fix is cheap.

### The writer the sweep MISSED — found by the gate's first run (`0e30ca09`, same day)

`scripts/session_import.py:366` is a **THIRD independent appender to `signal_history.csv`**,
alongside `HistoryStore._append_row` and `corpus_sync`'s recovery merge. **The by-inspection
sweep of `ee0ac4ad` checked ten writers and did not find it.** The **first AST inventory of
shipped code did, immediately** — which is the whole argument of
[[concepts/adoption-is-not-enforcement]].

It had **every defect the other two had**: a bare append with **no torn-tail probe and no
`fsync`**, plus a header written only under `if dest_hist.exists()` — **the size-0 variant for
the THIRD time in this repo**, so a zero-length corpus stays headerless and `csv.DictReader`
**adopts the first TRAINING ROW as its column names**.

> **It is the worst-placed of the three.** `corpus_sync --apply` runs it **HOURLY and
> UNATTENDED**, so a kill during an import fuses two labelled outcomes **with nobody watching**.
> The other two appenders at least run where a session is being observed.

**Three concurrent unhealed writers on one file is precisely the seam that produced SD-007**
(`audit_chain_break`) on the audit chain — whichever process is killed mid-row, the *others* weld
onto the fragment. The `ee0ac4ad` filing named two writers on this file as "exactly the seam."
**There were three.**

**Fixed:** the import batch is **one `durable_append` call**, and **the primitive owns the
header** rather than an `exists()` branch — the size-0 hole now closes by construction.

### `ee0ac4ad`'s ninth site, from the same class but a different cause: `core/audit.py`
Fixed in the same commit as the eight above (**not** related to the missed writer in the previous
section, which came later), and worth separating because the fragment came from an **`OSError`
part-way through `f.write`**, not a process kill. The handler dropped the record but **`_synced`
was already `True`**, so **no later `log()` re-adopted the tail** and the next append welded on.
`verify_chain` then saw a break with `tail_after_break > 0`, classified it **`torn=False` →
`tamper=True`**, and would report **the regulated trail of record as TAMPERED, permanently, for
what was crash damage**. One line — re-arm `_synced` — routes the next write through
`_adopt_tail`'s already-tested truncation.

> **This instance changes what the class costs.** In the ledgers, fusion destroys *data*. In the
> audit chain, fusion manufactures a **false accusation against the instrument that does the
> convicting** — and it does not decay ([[entities/reason-code-registry]],
> [[comparisons/stated-invariants-vs-audited-reality]]).

## The way it was found is itself the lesson
Instance 3 was **not** found by looking for it. It surfaced while writing
`tests/test_registry_chain.py` — a test suite for a **completely different property** (that the
hash chain detects edited, deleted, reordered and rewritten rows). Constructing the torn-row case as
*input* to a chain test revealed that the writer could produce it in the first place, and that the
next write would weld onto it.

> **A test written for property A finds bug B, because writing the test forces you to construct
> states the code has never been asked to survive.** This is the same instrument philosophy the
> corpus already runs on ([[concepts/adversarial-verification]],
> [[concepts/iron-law-of-debugging]]): the value of a test is not only its assertion, it is the
> **state space you have to enumerate to write it**. Neither the 29h fix nor the round-2 sweep of
> `ml/` had flagged the registry writer — five parallel area agents read that file and did not see
> it. The test did.

Corollary for the ledger of instances: **finding the third one took no search**, which is the
argument for making the pattern a **standing rule on the writer** rather than a per-file fix. Any
new append-only writer that skips it re-opens the class — exactly as
[[concepts/default-path-fallback-writes]] re-opens for any QA entrypoint that skips the redirect.

## ~~Where the class has NOT been swept~~ — SWEPT 2026-08-06
> **What this page asked for, verbatim (2026-08-05):** *"The heal is applied per writer, not
> enforced by a shared primitive or an invariant test… The remaining append-only writers in the
> repo have not been individually checked against this rule — `outputs/events.jsonl`, the retrain
> history, `context_history.jsonl` and the horizon shadow ledger among them. **A sweep that
> asserts the invariant across all append-only writers — rather than fixing them one crash at a
> time — is the honest close for this class.**"*
>
> **Discharged by `ee0ac4ad` the following day.** Every writer named above was checked; the
> retrain history, `context_history.jsonl` and the horizon shadow ledger were three of the eight
> adopters. **The named close was delivered in the form it was named in** — a shared primitive,
> not another round of per-file fixes.

## ~~What the sweep did NOT do~~ — GATED 2026-08-06 (`0e30ca09`)

> **What this page asked for, verbatim (2026-08-06, written while filing `ee0ac4ad`):** *"The
> invariant is enforced by **adoption**, not by a test that fails when a new writer skips it…
> **a future writer that opens a file in `"a"` mode by hand still re-opens the class silently.**
> A repo-wide static assertion (no bare `open(..., "a")` outside `core/runtime`) would convert
> the discipline into a gate. That is the remaining gap, and it is smaller than the one that was
> closed."*
>
> **Discharged the same day by `0e30ca09`, in the form it was named in** —
> `tests/test_append_invariant.py` ([[sources/session-20260806-append-gate]]). **And the gap was
> not merely theoretical: the gate's first run found a live instance the sweep had missed**
> (above). The residual was written as a discipline gap; it was also a **coverage** gap.

**How the gate works.** AST walk of `core`, `data`, `execution`, `ml`, `risk`, `regime`,
`strategies`, `sentiment`, `api`, `scripts`, plus `main.py` and `runner.py` — **verified to be
exactly the repo's ten non-test packages and two top-level modules**. Any `open()` call with a
**literal** mode containing `'a'`, outside the allowlist, fails with file and line. **AST rather
than regex** because prose false-positives — this repo's docstrings and wiki pages discuss
`open(..., "a")` constantly. **Proven to bite:** a bare append injected into `ml/interpret.py`
failed the gate; the injection was reverted.

**Three companion tests keep it honest:** stale exemptions must leave (*an entry that no longer
appends silently covers a FUTURE append*), every entry must name a real file, and five named data
writers must **positively contain** `durable_append` — so **deleting** the call is caught as well
as replacing it.

**`core/events.jsonl` is now a REASONED exemption, not an oversight.** `JsonlEventHandler.emit`
stays a bare append because `durable_append` reports failure via `log.exception`, and calling it
from inside a logging handler **would re-enter that handler**; `handleError` is the correct escape
there. Its **rotation** race was isolated separately so a rotation error can never lose the log
line being emitted. Previously this was an unexplained hole in the sweep; it is now line 1 of the
allowlist with that reason attached.

### What the GATE still does not cover — the new, smaller residual
1. **The allowlist is per-FILE, not per-call-site.** `scripts/corpus_sync.py` is exempt for its
   human-readable log at `:57` — while being the corpus's **second independent data appender** at
   `:160`, and **the one data writer absent from the positive `durable_append` assertion list**.
   **Replacing that call with a bare append would leave the battery green.** Same shape for
   `core/fill_ledger.py`, `ml/registry.py`, `core/audit.py` — though those three carry their own
   tested heals, and `corpus_sync` carries only the primitive.
2. **`SCANNED_DIRS` is a hardcoded tuple.** Correct today; **a new top-level package is unscanned
   until someone remembers to add it** — the same shape one level up, now inside the gate.
3. **`tests/` is deliberately out of scope** (a test that *fabricates* a torn tail must append),
   which is exactly where [[concepts/default-path-fallback-writes]] lives. **The two classes meet
   at the boundary this gate declines to cross.**

> **The residue is finite, listed and greppable** — which is what the conversion bought. See
> [[concepts/adoption-is-not-enforcement]] for why that, and not "the class is closed", is the
> honest statement.

## Relation to the neighbouring classes
- [[concepts/default-path-fallback-writes]] — the write goes to the **wrong file**. Here it goes to
  the right file in an unusable shape. Both were found the same way: by distrusting an enumeration.
- [[concepts/liveness-by-output-cadence]] — the same "a predicate that correlates with the invariant
  instead of testing it" shape (`path.exists()` for readiness; log mtime for liveness).
- **Cause vs consequence:** 29b/29h shrank the *consequences* of an unclean kill. The *cause* —
  `auto_update`'s 45s force-kill grace against measured 88.1s/55.5s/50.2s runner stalls — was fixed
  separately as item 30f, and is the likely origin of the `audit_tail_truncations` counter
  ([[entities/auto-update]], [[entities/observability-sidecars]]).

## The arc, as a lesson about defect classes
1. **Instance 1** looked like a bug in `fills.csv`.
2. **Instance 2**, one day later, was the same shape in the **same file's create window** — so it
   was a bug in a *pattern*, not a file.
3. **Instance 3** appeared in a completely different subsystem, found by a test for a **different
   property** — so it was a bug in a *habit*.
4. **The sweep** found it in **eight more writers**, including one (`horizon_shadow.csv`) that had
   independently reproduced instance 2's exact size-0 mechanism.
5. **The gate** found a **ninth** — the third corpus appender — **on its first run**, after a
   careful by-inspection sweep conducted one day earlier with the defect shape fully in mind had
   walked past it. So it was a bug in the **method of looking**.

> **Four fixes were needed before the class was worth a primitive, and the fourth was where the
> arithmetic changed.** The lesson is not "abstract earlier" — instances 1 and 2 genuinely looked
> local. It is that **the second independent recurrence of a mechanism is the signal**, because
> the third through eleventh cost nothing to find once you go looking with the shape in hand.

> **And the fifth round is where the lesson stopped being about the defect.** A sweep is a
> **search** — its coverage is a function of attention, spent at the end of a long session. A
> gate is an **inventory** — its coverage is a function of a scan scope that is written down.
> **The sweep was careful and still missed a writer; the gate found it for free, as a side effect
> of existing.** ([[concepts/adoption-is-not-enforcement]])

## Related
[[sources/session-20260806-append-gate]] · [[concepts/adoption-is-not-enforcement]] ·
[[sources/session-20260806-geometry-filing]] · [[sources/session-20260805-evening]] ·
[[sources/session-20260805-debug-sweep]] · [[synthesis/owed-measurements]] ·
[[comparisons/stated-invariants-vs-audited-reality]] ·
[[concepts/default-path-fallback-writes]] · [[entities/historystore]] ·
[[entities/reason-code-registry]] · [[entities/auto-update]]
