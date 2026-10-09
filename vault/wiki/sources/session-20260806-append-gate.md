---
title: "The Third Corpus Writer and the Append Gate (2026-08-06) — Converting an Invariant from Adoption to Enforcement"
category: source
summary: "Commit 0e30ca09, the residual of ee0ac4ad discharged the same day. Filing the sweep into the wiki forced the admission that the torn-append invariant was enforced by ADOPTION, not by a gate — so the very first AST inventory of shipped code (which is what the sweep should have been all along) immediately found a writer the sweep had missed: scripts/session_import.py:366, a THIRD independent appender to signal_history.csv, running HOURLY and UNATTENDED under corpus_sync --apply, with a bare append AND the size-0 header bug that makes csv.DictReader adopt the first TRAINING ROW as its column names. tests/test_append_invariant.py is now the gate: it walks the AST of every shipped module and fails on any open(..., mode containing 'a') outside a 13-entry reasoned allowlist, proven to bite by injecting a bare append into ml/interpret.py. Three companion tests keep the allowlist honest (no stale exemptions, no phantom files) and assert five data writers POSITIVELY call durable_append. Battery 3406 passed / 1 skipped (8 new), smoke 219, assurance 49, ruff + compileall clean."
tags: [session, durability, torn-append, enforcement, gate, corpus, static-analysis, defect-class]
sources: 1
source_path: none — session work product (see Provenance)
source_date: 2026-08
authors: [claude]
ingested: 2026-08-06
updated: 2026-08-06
---

# The Third Corpus Writer and the Append Gate (2026-08-06)

## Provenance

Session work product — no `raw/` snapshot. **One** commit on the working checkout
`liquiditybot_ab`, **head = `0e30ca09`**, parent `ee0ac4ad`. Battery at commit:
**pytest 3406 passed / 1 skipped** (**8 new**), **smoke 219**, **assurance 49**, **ruff +
compileall clean**. Files touched: **2** (`scripts/session_import.py`,
`tests/test_append_invariant.py`) — **+167 / −5**. The gate was re-run at filing time:
**8 passed in 1.09s**.

**This commit exists because of the previous one's filing.** Writing
[[sources/session-20260806-geometry-filing]] into the wiki required stating what the sweep did
*not* do, and that sentence — *"the invariant is enforced by adoption, not by a test that fails
when a new writer skips it"* — was the whole specification for this commit. **The residual named
on [[concepts/torn-append-fusion]] during the `ee0ac4ad` filing is discharged here, the same day
it was written.**

---

## 1. The missed writer — the corpus's THIRD independent appender

`scripts/session_import.py:366` appends to `outputs/signal_history.csv`, alongside the runner's
`HistoryStore._append_row` and `corpus_sync`'s recovery merge. **The sweep of `ee0ac4ad` checked
ten writers and did not find this one.**

It carried **every defect the other two had**:

- a **bare `open(dest_hist, "a")`** with **no torn-tail probe** and **no `fsync`**;
- a header written only under **`if dest_hist.exists()`** — the **size-0 variant**, for the
  **third time in this repo**. A zero-length corpus passes *through* that branch, stays
  headerless, and `csv.DictReader` then **adopts the first TRAINING ROW as its column names**.

> **It is the worst-placed of the three.** `corpus_sync --apply` runs it **hourly and
> unattended**, so a kill during an import fuses two labelled outcomes **with nobody watching**.
> The other two appenders at least run where a human is looking at the session.

**Three concurrent unhealed writers on one file is precisely the seam that produced SD-007**
(`audit_chain_break`) on the audit chain: whichever process is killed mid-row, the *others* weld
onto the fragment. The `ee0ac4ad` filing had already named two writers on this file as "exactly
the seam"; there were three.

**Fixed:** the import batch is now **one `durable_append` call**, and **the primitive owns the
header** (`header=",".join(expected) + "\n"`) rather than an `exists()` branch — so the size-0
hole closes by construction, not by remembering. **One probe per open, not per row.**

---

## 2. The gate — `tests/test_append_invariant.py`

The test **walks the AST of every shipped module** and fails on any `open(..., <mode containing
'a'>)` outside a reasoned allowlist.

**Scope:** `core`, `data`, `execution`, `ml`, `risk`, `regime`, `strategies`, `sentiment`, `api`,
`scripts` (recursive), plus `main.py` and `runner.py`. **Verified against the repo's actual
layout: those are exactly the ten non-test package directories and the two top-level modules.**

**AST rather than a text regex**, for the same reason `tests/test_code_registry.py` uses one:
**a regex false-positives on prose** — docstrings and comments in this repo discuss `open(...,
"a")` constantly, this very page included. Only real `open()` *calls* with a **literal** mode
count; a computed mode cannot be judged statically and has never appeared in the repo.

> **Proven to bite, not assumed to.** A bare append was injected into `ml/interpret.py`; the gate
> failed with the file and line number, and the injection was reverted. **A gate that has never
> been shown to fail is a gate whose passing means nothing** — the same discipline as the
> red-first tests in `ee0ac4ad`.

### The allowlist — 13 entries, each with a reason, in three groups

| Group | Entries | Reason |
|---|---|---|
| **The primitive and the heals that predate it** | `core/runtime.py`, `core/fill_ledger.py`, `ml/registry.py`, `core/audit.py` | `durable_append` **is** the primitive. `fill_ledger`'s probe/heal/fsync at `:70-86` is **what the primitive was generalized FROM**; `ml/registry.py` carries the JSONL variant at `:146-160`, coupled to the hash chain's torn-tail semantics. `core/audit.py`'s `_adopt_tail` does **more** than heal — it **truncates malformed lines and re-adopts `seq`/`prev`** — so only the newline probe is shared, and replacing the whole write **would take the chain logic with it**. |
| **Plain human-readable text logs** | `scripts/corpus_sync.py` (the `:57` log site), `auto_update`, `pc_supervisor`, `remote_control`, `checkin`, `run_checkin_quiet`, `assurance_check` | **Fusion costs two log lines**, nothing durable. |
| **Operator-invoked one-shots and the recorder** | `scripts/migrate_history.py`, `data/replay.py` | `migrate_history` is **never automatic** and its output is verified by the operator before it becomes the corpus. `data/replay.py` is the session recorder: a fused frame costs **one frame out of ~6.3 GB**, and the recorder **must not `fsync` on the hot REST path**. |

### Three companion tests keep the list honest

1. **`test_allowlist_has_no_stale_entries`** — an entry that **no longer appends must leave**.
   The reasoning is sharper than tidiness: **a stale exemption silently covers a FUTURE append.**
   The allowlist is the one part of the gate that can rot into a hole.
2. **`test_every_allowlist_entry_exists`** — every entry names a file that exists, so a rename
   cannot leave a phantom exemption behind.
3. **`test_the_data_writers_actually_use_the_primitive`** — five writers
   (`ml/history.py`, `scripts/session_import.py`, `ml/postmortem.py`, `ml/retrain_log.py`,
   `data/context_engine.py`) must **positively contain `durable_append`**. The negative gate
   catches *replacing* the call with a bare append; **this catches DELETING it.**

---

## 3. Deliberately not converted, and recorded as such

`core/runtime.py`'s **`JsonlEventHandler.emit` stays a bare append**. `durable_append` reports
failure via `log.exception`, and **calling it from inside a logging handler would re-enter that
handler**; `handleError` is the correct escape there.

> **This is filed in the allowlist with its reason rather than left as an oversight for the next
> sweep to re-discover.** The allowlist's real product is not the exemption — it is the
> **written reason**, which is what stops the same site being "found" a fifth time.

---

## 4. What the gate still does not cover — stated honestly

The gate is a real enforcement mechanism and it is **narrower than "no writer can ever re-open
this class."** Three known holes, smallest first:

1. **The allowlist is per-FILE, not per-CALL-SITE.** `scripts/corpus_sync.py` is exempted for its
   human-readable log at `:57` — but the same file is the corpus's **SECOND independent data
   appender** at `:160`, and it is **the one data writer absent from the positive
   `durable_append` assertion list**. **Replacing that call with a bare append would leave the
   battery green.** The same shape holds for `core/fill_ledger.py`, `ml/registry.py` and
   `core/audit.py`, which are wholesale-exempt while writing the three most valuable ledgers in
   the repo — those three do at least have their own tested heals; `corpus_sync` has only the
   primitive.
2. **`SCANNED_DIRS` is a hardcoded tuple.** It matches the repo exactly today. **A new top-level
   package is unscanned until someone remembers to add it** — which is
   [[concepts/adoption-is-not-enforcement]] one level up, now inside the gate itself.
3. **`tests/` is deliberately out of scope**, and correctly so: a test that **fabricates** a torn
   tail must be able to open a scratch file in append mode. But it means the gate **cannot catch
   a QA harness appending to a production path** — and that specific combination is this repo's
   **most-recurring defect class** ([[concepts/default-path-fallback-writes]], seven instances).
   The two classes meet exactly at the boundary this gate declines to cross.

None of these is a reason to withhold the gate. **The class went from "enforced by everyone
remembering" to "enforced except in 13 named files and one excluded directory,"** which is a
different order of exposure. They are recorded so the next sweep starts here instead of
rediscovering them.

---

## 5. What this session changes elsewhere in the wiki

- **[[concepts/torn-append-fusion]] — the residual named during the `ee0ac4ad` filing is
  DISCHARGED**, and a **fourth round** of the class is on the record: the sweep by inspection
  missed a writer that the first inventory found immediately.
- **New concept — [[concepts/adoption-is-not-enforcement]].** The generalizable lesson, with this
  commit as its type specimen: an invariant that depends on every future author remembering is
  not enforced, and the distance between "we fixed all of them" and "nothing new can appear" is
  where defect classes live.
- **[[comparisons/stated-invariants-vs-audited-reality]]** gains a row of a new kind — the
  invariant here was not merely unstated, it was **stated, believed, freshly swept, and still
  false**.
- **[[synthesis/owed-measurements]]** item 31's residual closes; the three narrower holes above
  replace it.
- **[[entities/historystore]]** — the corpus has **three** independent appenders, not two.

## Related
[[sources/session-20260806-geometry-filing]] · [[concepts/torn-append-fusion]] ·
[[concepts/adoption-is-not-enforcement]] · [[concepts/default-path-fallback-writes]] ·
[[entities/historystore]] · [[entities/reason-code-registry]] · [[entities/auto-update]] ·
[[comparisons/stated-invariants-vs-audited-reality]] · [[synthesis/owed-measurements]] ·
[[concepts/adversarial-verification]] · [[concepts/iron-law-of-debugging]] ·
[[concepts/location-invariant-tests]] · [[concepts/never-widen-a-gate]] ·
[[sources/session-20260805-evening]]
