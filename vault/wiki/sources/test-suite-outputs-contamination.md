---
title: Test Suite Outputs Contamination (2026-07-31)
category: source
summary: The pytest suite had been writing into the live outputs tree since 2026-07-18, fabricating INTEGRITY FAIL forensics and filling 99.7% of the learning ledger with fixtures — root cause of the wider class found and fixed 2026-08-02
tags: [data-hygiene, contamination, tests, forensics]
sources: 3
updated: 2026-08-05
---

# Test Suite Outputs Contamination (2026-07-31)

**Raw source:** `raw/quant/2026-07-31_test_suite_outputs_contamination.md`

## How it surfaced
By following a real-looking `INTEGRITY FAIL: signal_history.csv sha256 mismatch (bundle tampered or
corrupt)` line for bundle `peer` in `outputs/corpus_sync.log`. **`sessions/peer/` has never existed**
on any branch at any commit — `peer` is the bundle label used by a test.

Reproduced directly: 850 lines -> run 4 passing tests -> 851 lines. "Four passing tests appended one
fabricated corruption incident to the operator's diagnostic log."

## Root cause
`scripts/corpus_sync.py` threads a `root` parameter through every entry point precisely so callers can
operate on a throwaway tree, **but `_log` ignored it** and always wrote to the module-level output
path. **The data writes were correctly scoped; only the record of them leaked.**
[[concepts/scoped-data-unscoped-record]].

## Scope measured, not guessed
Snapshotted every file under `outputs/` (**460 files, sha256**), ran the full suite, diffed.
**Six files mutated**, two of them data:
- `retrain_history.jsonl` — the learning ledger, **305 of 306 records were test fixtures**, every one
  identical (`rows: 60, live: 60, oof_brier: 0.24193, selected: gbt, source: cli`).
- `corpus_sync.log` — fabricated INTEGRITY FAIL entries since 07-18.
- `remote_control.log` — 356 copies of "runner down".
- plus `session_digest.json`, `auto_update.log`, `pc_supervisor.log`.

## The collateral damage
`scripts/learning_curve.py`'s header reads "retrain_history.jsonl is degenerate at this corpus size"
and the whole script exists to work around that degeneracy. **The degeneracy was never about corpus
size; the file was 99.7% test output.** "A prior session correctly observed the symptom and built a
whole instrument on the wrong diagnosis."

## Fixes
Per-source path threading, plus two structural `conftest.py` guards: an `sys.addaudithook` write guard
that **fails the offending test by name** with an intentionally empty allowlist, and a sidecar-log
redirector **matched by value, not module name** (the suite imports the supervisor under two names —
a name list silently missed one).

Documented limit: the audit hook is in-process and **cannot see subprocess writes** — which is why it
reported four paths while the snapshot diff reported six. **The snapshot diff is the complete
instrument; the hook is the one that names the culprit.**

## Deliberate non-action
The contaminated history was **not rewritten** — "the files are the operator's record and editing them
retroactively is worse than a documented contamination window." Standing instruction: treat any
`outputs/*.log` line before commit `b459a90` as suspect.

## Sequel (2026-08-02): the class was wider than the suite
This document caught pytest writes. On 2026-08-02 a **seventh** member of the same class was
root-caused and fixed (commit `858c8d71`): `scripts/debug_cycle.py` — a QA entrypoint outside
pytest — appended 64 fixture fills to the live `outputs/fills.csv`, because `config.json` sets no
`system.fills_ledger_path` and the engine falls back to the production default. Those 64 rows made
the measured P&L **wrong by 27x** and produced two wrong binding-constraint headlines before the
purge. The general mechanism now has its own page, [[concepts/default-path-fallback-writes]];
the isolation invariant is pinned by `tests/test_qa_isolation.py`.

The same day's addendum closed the cleanup: a residual sweep quarantined **18 more fixture
positions (72 rows)** — attribution corrected to **battery smoke runs**, not bot restarts or
`debug_cycle.py` alone — leaving `fills.csv` **637/637 audit-crossref CLEAN** (commit `483f6727`).
*(Ledger stayed clean under live growth: 655 rows, zero fixture signatures, on the 2026-08-03
sweep — which also narrowed what counts as a "fixture signature": fills at an exact ref-multiple
can be design, not fabrication — the long book's −50.0bps resting offset was classified benign
by audit-chain crossref, [[sources/session-20260803-bug-sweep]].)*
The other suspect files were assessed: `retrain_history.jsonl` **158/165 clean** on the 08-02
snapshot (the 305/306 measured here on 07-31 was a different snapshot — qualify by date);
`outputs/models/registry.jsonl` **97/129 fixtures**, mitigated by filter-at-read-time;
`horizon_shadow.csv` **58.8% proven clean, rest undecidable**. Still owed: re-running
`calibrate_fills.py` on the clean ledger. Full account: [[sources/session-20260802-digest]].

## Third sequel (found 2026-08-16): the fix was real, the CONTAMINATION OUTLIVED IT BY A DAY in the A/B tree

The standing instruction above — *treat any `outputs/*.log` line before commit
`b459a90` as suspect* — turns out to be **too narrow by one date, in one tree**.

`remote_control.log`'s "356 copies of runner down" (§scope, above) has a
**sequel batch**: eight fabricated remote `pause`/`snapshot` commands, ids
`1785619944 … 1785622368`, logged **2026-08-01 16:32:24 – 17:12:48 local** as
`queued` + `RC-010 forwarded` (**16 lines**). They are pytest fixtures, and
**no real command exists** behind any of them — the exactly-once ledger
`outputs/remote_consumed.json` has not been written since **2026-07-25 19:49
local** and holds **5** entries, the last a genuine `snapshot` issued by the
phone/web sandbox (`issued_by: "vm"`).

Why after the fix: `64b6fd52` is stamped **2026-07-31T20:48:07Z**, but this A/B
tree ran its 08-01 audit session on an older checkout — reflog `checkout: moving
from main to fix/audit-20260801` at **2026-08-01 15:45:05 −0500**, the fix
merging in only at **17:20:10 −0500**. **Fix → first contaminated line: 24.74 h.**

**Amended standing instruction:** in the A/B tree, `remote_control.log` entries
**before 2026-08-01 17:20 local** are untrustworthy. The class rule generalizes —
**date the CHECKOUT, not the fix commit**
([[concepts/scoped-data-unscoped-record]] §the class recurred,
[[sources/session-20260811-16-vscode-3b307393]] §2, which lists the four
independent confirmations).

## Second sequel (2026-08-05): an eighth instance found before it bit — fixed the same day
The 08-05 read-only debug sweep ([[sources/session-20260805-debug-sweep]], finding 1, HIGH ·
confirmed) found the class **still open in the replay family**: `scripts/replay.py`'s
hand-rolled QA redirect (and `scripts/sweep.py` / `scripts/replay_gate.py`, which call no
redirect at all) omit `system.fills_ledger_path`, `ml.multi_horizon.shadow_path`,
`ml.model_path`, and the `ml/retrain_log` module path — so a replay run can append synthetic
fills to production `outputs/fills.csv` (the exact 27x mechanism), append to
`horizon_shadow.csv` (**a still-open candidate writer for this page's "rest undecidable"
rows**), deploy a replay-trained champion, and append to the retrain history measured
305/306-contaminated here. Unlike the seven prior instances, this one was found by audit
**before** a corrupted measurement — and **closed the same day** (commit `e7ebbf60`, battery
green): the replay family now routes through the canonical `qa_redirect_paths` via
`prepare_replay_config` (one list, never two), `sweep.py` gained the
`configure_audit`/`configure_registry` isolation it never had — until then a sweep run
appended replayed dispositions to the **production audit trail and model registry** — and new
replay-family tests in `test_qa_isolation.py` pin all five known-leak keys plus the retrain
rebind ([[synthesis/owed-measurements]] item 29a). The same sweep also found the clean
ledger's remaining hygiene hole: `fills.csv` had **no torn-row recovery** on crash mid-append
(finding 8, `core/fill_ledger.py:51-64` — contrast the audit trail's `_adopt_tail`); **also
fixed same day** (`b409a24b`): `append_fill` now heals a torn tail (the fragment isolates as
one junk row csv consumers skip) and fsyncs each row, so the torn window is the single row
being written.
