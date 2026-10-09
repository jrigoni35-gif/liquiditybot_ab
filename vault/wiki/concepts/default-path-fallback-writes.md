---
title: Default-Path Fallback Writes
category: concept
summary: "A QA harness redirects the paths it knows about, but every path key absent from config falls back to a hardcoded production default and writes anyway — absence of a key is not absence of a write. Generalized twice since: absence of a PINNED VALUE is not absence of a dependency (2026-08-02, four harnesses riding the shipped passive_base_prob), and as of 2026-08-10 PRESENCE of a pinned value is not presence of a guarantee — the 08-02 pin itself silently decayed when the double-count fix made the pinned constant irrelevant, so fixtures were back on the ambient simulator with no edit to either fixture. Pin the PROPERTY, not the constant that currently produces it. NINTH INSTANCE at the Grand Synthesis filing: the new trade-path ledger's paths_path defaulted to production and five harnesses predate the key — a QA fixture row (2000,p1,ETH) was already in outputs/trade_paths.csv, the exact file Phase B parameterizes stop geometry from (owed 65) — CLOSED same session (2602371b): row QUARANTINED not deleted, five harnesses to tmp_path, and the class got its FIRST tripwire catch — battery 14 RED via the conftest production-outputs tripwire, so the contamination was caught twice independently"
tags: [data-hygiene, contamination, testing, defect-class]
sources: 9
updated: 2026-08-10
---

# Default-Path Fallback Writes

## The defect class
A QA or test harness "isolates" itself by redirecting an **enumerated list** of output paths
(`qa_redirect_paths`). But for any path the config does not set, the engine falls back to a
hardcoded default — and that default **is the production file**. The harness is only as isolated as
its enumeration is complete, and the enumeration is refuted by the next path anyone adds.

> **Absence of a key is not absence of a write.** `config.json` sets no `system.fills_ledger_path`
> and no retrain-history key, so grepping config for the key finds nothing — while the engine
> writes to `outputs/` on every simulated fill.

## The record: seven occurrences of the same class
Each found only after it corrupted a result; each previously "fixed" by adding one line to the
redirect list plus a comment claiming completeness:
`state.json` (deleted three real open positions) · postmortem summaries · retrain flags ·
`context_history.jsonl` (100+ rows) · `audit.jsonl` · `retrain_history.jsonl` (305 of 306 records
fixtures) · `fills.csv` (64 fixture rows → P&L wrong by **27x**, the error behind two wrong
binding-constraint headlines — see [[sources/session-20260802-digest]]).

The seventh instance: `scripts/debug_cycle.py` ran the real bot on mocked feeds (`ETH=2000.0`) and
appended simulated fills to the live ledger via `main.py:1652 _ledger_fill`. The "impossible"
prices in the ledger were fixture arithmetic — `1490.645739 = 1491.018493 × (1 − 2.5bps)`.

**Attribution corrected (08-02 addendum):** the fixture blocks in `fills.csv` were written by
**battery smoke runs** — not by bot restarts, and not by `debug_cycle.py` alone. `debug_cycle.py`
exposed the mechanism; the battery's smoke entrypoints were writers through the same fallback. A
same-day sweep found **18 more fixture positions (72 rows)**, including one block from a battery
run pre-dating the fix; all quarantined at commit `483f6727`, leaving `fills.csv`
**637/637 audit-crossref CLEAN**.

## The decisive provenance signal
**`order_id` membership in the hash-chained `audit.jsonl`.** QA always redirected the audit trail
even while leaking fills — so a fill whose `order_id` appears in the hash-chained audit log is
live, and one absent is fixture. This asymmetry (audit redirected, fills not) is what makes the
crossref decisive, and it is the classifier to reach for on any future suspect row. Where a file
carries no `order_id` (e.g. `horizon_shadow.csv`) provenance is only partially decidable.

## The eighth instance (2026-08-05): the enumeration that never joined the fixed one — CLOSED SAME DAY
The 08-05 read-only debug sweep ([[sources/session-20260805-debug-sweep]], finding 1, HIGH ·
confirmed) found the class **still alive in the replay family**: `scripts/replay.py:64-82` has
its own **hand-rolled** redirect list (state/weekly/monthly/history/postmortem/retrain-flag)
that **predates** four later paths, and `scripts/sweep.py` / `scripts/replay_gate.py` **never
call `qa_redirect_paths` at all**. The four production writes a replay run can make:
1. `system.fills_ledger_path` — absent from config, so every simulated fill appends to
   production `outputs/fills.csv` via `main.py:1663`'s default — **the exact 27x mechanism**;
2. `ml.multi_horizon.shadow_path` — `multi_horizon.enabled: true`, so shadow completions
   append to `outputs/horizon_shadow.csv`, the 23,826-row 432-migration evidence base — a
   **still-open candidate writer** for that file's undecidable rows;
3. `ml.model_path` — a monitor-flagged retrain during a long replay **deploys a
   replay-trained champion** into production `outputs/meta_model.json`;
4. the `ml/retrain_log` module path — the same retrain appends to the real retrain history.

**FIXED same day (commit `e7ebbf60`, battery green — [[synthesis/owed-measurements]] item
29a).** The fix is the **class fix, not a ninth line-item**: `run_replay` now prepares its
config via new `prepare_replay_config` → `qa_redirect_paths` — **one list, never two** (the
hand-rolled replay list is gone) — and `sweep.py` gained the
`configure_audit`/`configure_registry` isolation it **never had**: until this fix a sweep run
appended replayed dispositions to the **production audit trail and model registry**. Pinned by
new replay-family tests in `test_qa_isolation.py` that walk the real config through the real
replay preparation and pin all five known-leak keys plus the retrain rebind; `sweep.py` joins
the singleton-isolation entrypoint list; the module docstring now records **EIGHT** instances.
Unlike instances 1-7, this one was found by audit — and closed — **before** it corrupted a
measured result: a first for the class.

## The ninth instance (2026-08-11 ship, caught at the wiki filing): the key newer than every harness
The complete trade-path ledger ([[sources/directive-20260811-grand-synthesis]]) shipped
`paths_path` defaulting to production `"outputs/trade_paths.csv"` (`ml/postmortem.py:195`) —
and **five existing harnesses** construct `PostmortemEngine` with redirected
`summary_path`/`report_dir` but no `paths_path`, because **they predate the key**:
`scripts/smoke_test.py:1013`, `tests/test_cleanup_batch1.py:33`,
`tests/test_review_round2.py:82,93`, `tests/test_stop_gap_and_lapse_fixes.py:51`,
`tests/test_telemetry_fixes.py:31`. The production file's **single row at filing** is
byte-for-byte the `test_telemetry_fixes.py` `_thesis(pid="p1")` fixture
(`2000,p1,ETH,long,0.620,0.180,nan,…`). Caught by the wiki filing's verification pass, **before**
a measurement consumed it — but **after** the write, so it splits the difference between
instances 1-7 (found post-corruption) and 8 (found pre-write). The sting: the ledger exists to
feed the Grand Synthesis's evidence-derived stop geometry, so this class's write landed in the
**exact file the next algorithm parameterizes from**. Open as
[[synthesis/owed-measurements]] **item 65**; the class fix (a redirect mode that refuses
production defaults when any path key is overridden) is named there. **A new default path is a
new instance of this class by default** — the enumeration is refuted by the next path anyone
adds, exactly as this page's first paragraph has said since instance seven.

**CLOSED same session (`2602371b`, item 65)** — and the close is the instructive part, three
ways. (1) The five harnesses were redirected to `tmp_path` **in the same commit the ledger
landed**, so no window opened between writer and fix. (2) The contaminated row was
**QUARANTINED, not deleted** (`trade_paths.csv.quarantine_qa_1786`) — the
nothing-is-ever-deleted bound applied to a fixture row, keeping the contamination auditable.
(3) **The class got its first tripwire catch**: battery 14 went **RED via the conftest
production-outputs tripwire** — the first time in nine instances that an automated gate, not
a human sweep, caught a write to a production output ([[concepts/false-green]]
contrast-case: a gate that could fire and did). The contamination was therefore caught
**twice independently** (vault-filing verification + battery), which is what enforcement
looks like when it finally exists ([[concepts/adoption-is-not-enforcement]]). The structural
fix — a redirect mode that refuses production defaults when any path key is overridden —
remains the named class fix; the tripwire is the second layer, not the fix.

## The fix pattern: assert the invariant, not the known cases
Fixed 2026-08-02 (commit `858c8d71`), pinned by `tests/test_qa_isolation.py` (10 cases). The
load-bearing test walks the **real config through the real redirect** and fails on any
`*_path`/`*_dir` still resolving under `outputs/`. Asserting the invariant instead of enumerating
known offenders immediately found **two more** — including seven of eight QA entrypoints calling
`configure_registry()` while `debug_cycle.py` did not, so it also wrote the production model
registry.

> ⚠️ **Boundary found 2026-08-05:** the invariant test binds only entrypoints that pass
> through `qa_redirect_paths`. The replay family never enters that redirect — for it, the
> sweep reports `test_qa_isolation.py` checks only `configure_audit`/`configure_registry`
> **string presence** — so the eighth instance was invisible to CI. The invariant is only as
> wide as the set of entrypoints that walk it
> ([[sources/session-20260805-debug-sweep]]).
>
> **Boundary closed same day (`e7ebbf60`):** the replay family now enters the one redirect
> via `prepare_replay_config`, and the replay-family tests make the invariant walk these
> entrypoints too — the set that walks the invariant grew to match the set that writes.
> The lesson stands as stated: any future QA entrypoint that skips the redirect re-opens it.

## Boundaries of the fix
The test pins *future* isolation. Past contamination was a separate ledger, now largely assessed
(08-02 addendum): `fills.csv` **CLOSED** (637/637 audit-crossref CLEAN, `483f6727`);
`retrain_history.jsonl` assessed **158/165 clean** on the 08-02 snapshot (the 07-31 count of
305/306 fixtures was a different snapshot — qualify by date); `outputs/models/registry.jsonl`
**97/129 fixtures**, mitigated by **filter-at-read-time**; `horizon_shadow.csv` **58.8% proven
clean, rest undecidable** (no order_id). Still open: `calibrate_fills.py` reads `fills.csv` to
tune the fill simulator, so contamination **already fed forward** — its re-run on the clean ledger
is owed. Tracked in [[synthesis/owed-measurements]].

## The class generalizes beyond paths (08-02 follow-on)
The honest-fills commit (`8e5455e8` — [[sources/session-20260802-digest]] third addendum) found
the same lesson operating on a **constant, not a path**: four QA harnesses had declared
"deterministic fill" via `queue_aware=False` while **silently riding the shipped
`passive_base_prob`** — their determinism claim held only as long as the production constant
happened to be generous. When the constant moved 0.45 → 0.048, the unpinned assumption would
have broken. Fixed by pinning `passive_base_prob=1.0` explicitly alongside `queue_aware=False`;
fill realism keeps dedicated coverage in `test_sim_fill_queue`. **Absence of a pinned value is
not absence of a dependency** — the same shape as "absence of a key is not absence of a write."

> ⚠️ **THE PIN ITSELF DECAYED — 2026-08-10, and this is the class's next turn of the screw**
> ([[sources/session-20260810-fill-double-count]] §6). The double-count fix (`aeeaae36`) made
> `passive_base_prob` **irrelevant whenever a book is present**, so the 08-02 pin — the fix for
> the paragraph above — **silently stopped working.** The two smoke fixtures pinned to the
> deterministic fill model on **2026-07-21** (persistence + lifecycle plumbing; their subject is
> persistence/pipeline, not fill realism) were back on the ambient simulator with **no edit to
> either fixture**. Extended to the new flag at `scripts/smoke_test.py:571` and `:822`, following
> the precedent already written into `config.json`'s `queue_aware` `_doc`.
>
> **The generalized rule, third statement:**
> *absence of a key is not absence of a write* → *absence of a pinned value is not absence of a
> dependency* → **presence of a pinned value is not presence of a guarantee.** A pin binds a
> *value*; it does not bind the *mechanism* that value participates in. When the mechanism moves,
> the pin becomes a no-op that still reads as protection — and nothing goes red, because the
> pinned value is still there.
>
> **How to pin so it cannot decay:** pin the **property** (the fill is deterministic), not the
> **constant** that currently produces it — the same *assert-the-invariant-not-the-known-cases*
> move that fixed the path family. Note what the fixtures got instead: three of them extended the
> constant-pin, and only `tests/test_exec_quality_stats.py` moved to the **property** (a crossed
> book, so it exercises the real booking mechanism rather than a legacy flag). **One of four
> took the durable option.**
>
> **And the failure surfaced badly:** the persistence fixture failed with **`IndexError` on
> `open_positions()[0]`**, not an assertion — **it crashed rather than reporting "no position",
> so it could not distinguish a broken subject from a setup that never happened**
> ([[concepts/zero-is-not-a-reading]], test-plane instance). Companion class:
> [[concepts/generosity-masks-fragility]].

## The same book of record, a different way to lose it (2026-08-05 evening)
The class is about a **write landing in the wrong file**. Its neighbor, found the same evening by
an adversarial review of the day's own durability fixes (`46cdc19a`,
[[sources/session-20260805-evening]]), is a write landing in the **right file, unreadably**:

`fills.csv` could still be **born HEADERLESS**. The 29h torn-tail heal covers a torn *final* row
but not the **create-to-first-flush window** — a kill there leaves a **0-byte file**, and the next
append saw `path.exists() == True`, skipped the header, and wrote a **data row first**.
`csv.DictReader` then silently **adopts that FILL as the header**, and every consumer
(`breakeven_test`, `cost_attribution`, `calibrate_fills`, `provenance_audit`,
`random_entry_control`, `geometry_search`) misparses **the entire ledger with no error raised**.
Fixed: `new_file` counts **size 0 as new**.

> **Existence is not readiness.** `path.exists()` answered a question nobody asked — the same
> shape as *absence of a key is not absence of a write*, one level down: a predicate that
> correlates with the invariant instead of testing it. And the blast radius is the **same book of
> record** whose contamination produced the **27x** P&L error — this time silently mis-parsed
> rather than silently mis-written, which is **worse to detect** because no row is wrong, only
> every column.

**That neighbour is now its own class: [[concepts/torn-append-fusion]].** A third instance landed
2026-08-05 late evening (`4799bfc7`) — `ml/registry.py`'s provenance ledger had the **same torn-row
fusion defect as `fills.csv`**, found while writing a test for an unrelated property
([[synthesis/owed-measurements]] item 30a). Read the two classes as a pair: **this** page is a write
landing in the **wrong file**; that one is a write landing in the **right file, unreadably**. Both
are closed by asserting an invariant on the writer rather than enumerating the files that have
already been lost.

## Relation to the sibling classes
[[concepts/torn-append-fusion]] is the durability twin — same ledgers, same 27x book of record, but
the write lands in the right file in an unreadable shape. [[concepts/scoped-data-unscoped-record]]
is the mirror image: there the **data** writes honored the
redirect and only the **log** leaked.

> **The mirror class recurred 2026-08-01 and was only found on 2026-08-16** — eight fabricated
> remote-control commands in the operator's production `remote_control.log`, **24.74 h AFTER**
> the commit that fixed the class (`64b6fd52`), because the A/B tree was on an older checkout.
> **The rule it adds applies to THIS page too: date the CHECKOUT, not the fix commit** — every
> "this class is closed" claim here is closed *per worktree*, and this repo runs several
> (including the deploy gate's outputs-nested one, [[concepts/location-invariant-tests]]).
> ([[sources/session-20260811-16-vscode-3b307393]] §2) Here the redirect itself was incomplete because the path was
never in config to begin with. Both were found by the same instrument philosophy — snapshot-diff
the whole `outputs/` tree rather than trusting any enumeration
([[sources/test-suite-outputs-contamination]]).

> **The twin got a GATE on 2026-08-06 (`0e30ca09`); this class did not.**
> `tests/test_append_invariant.py` fails on any bare append-mode `open` in shipped code — but it
> **deliberately excludes `tests/`**, because a test that *fabricates* a torn tail must be able to
> open a scratch file in append mode. That exclusion is correct for the durability class and
> lands exactly on **this** class's home ground: **a QA harness appending to a production path is
> ungated by construction.** The two classes meet at the boundary the gate declines to cross —
> which is worth remembering given this is the repo's **most-recurring** class — seven
> instances when this was written, **nine** as of the Grand Synthesis filing — still enforced
> substantially by convention.
> ([[sources/session-20260806-append-gate]], [[concepts/adoption-is-not-enforcement]])
