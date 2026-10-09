---
title: Scoped Data, Unscoped Record
category: concept
summary: "A defect class where a redirection parameter is honored by data writes but ignored by the logger — the data is correctly scoped, only the RECORD leaks. Recurred 2026-08-01 in its own type-specimen module (remote_control), 24.74 h AFTER the fix commit, because the A/B tree was on an older checkout: date the CHECKOUT, not the fix commit"
tags: [defect-class, hygiene, testing]
sources: 2
updated: 2026-08-16
---

# Scoped Data, Unscoped Record

## Definition
A module threads a `root`-style parameter through every entry point precisely so callers can operate on
a throwaway tree — **but the logging helper ignores it** and always writes to the module-level
production path.

> **"The data writes were correctly scoped; only the record of them leaked."**

## Why it is pernicious
The leaked artifacts are **forensics**, not data. They look exactly like real incidents. The
investigation that uncovered this started by chasing a convincing
`INTEGRITY FAIL: sha256 mismatch (bundle tampered or corrupt)` line — which turned out to be a passing
test's fixture. Four passing tests appended one fabricated corruption incident per run.

## Scale, when measured properly
**305 of 306 records** in the learning ledger were identical test fixtures. The one genuine record was
buried under a 305-row flat line.

## The collateral damage worth remembering
A whole analysis instrument had been built on the wrong diagnosis — its header comment attributed the
ledger's degeneracy to corpus size. **"The degeneracy was never about corpus size; the file was 99.7%
test output."** A prior session "correctly observed the symptom and built a whole instrument on the
wrong diagnosis."

## The method that scoped it
**Snapshot-diff, not grep**: sha256 every file in the output tree, run the full suite, diff. This found
**6 mutated files** where an in-process write-audit hook found only 4 — the hook cannot see subprocess
writes. **The snapshot diff is the complete instrument; the hook is the one that names the culprit.**

## The deliberate non-action
The contaminated history was **not rewritten**: "the files are the operator's record and editing them
retroactively is worse than a documented contamination window." A dated suspect-range instruction was
issued instead.

## The class recurred in its own type-specimen module — and outlived the fix by a day (2026-08-01, found 2026-08-16)

The 07-31 fix (`64b6fd52`, **2026-07-31T20:48:07Z**) closed this class by making
every logger honor `root`. On **2026-08-01 16:32:24 – 17:12:48 local** the A/B
tree nonetheless wrote **eight fabricated remote-control commands** into the
operator's production `outputs/remote_control.log` — `queued` + `RC-010
forwarded`, **16 lines**, ids `1785619944 … 1785622368` — because that tree was
sitting on an **older checkout**: reflog `checkout: moving from main to
fix/audit-20260801` at **2026-08-01 15:45:05 −0500**, `merge origin/main`
(landing the fix) at **17:20:10 −0500**.

**Fix → first contaminated line: 24.74 h. Fix → merge: 25.53 h.**

The signature is the class's own: **`_save_consumed(root, …)` and
`ControlChannel` honored the tests' `tmp_path`; `_log()` did not.** The data was
correctly scoped; only the record leaked — so the exactly-once ledger
`outputs/remote_consumed.json` (**5 entries, last written 2026-07-25 19:49
local**) is *right* and the operator-facing log is *false*.

**The rule this adds:** *date the CHECKOUT, not the fix commit.* A defect is
fixed **where the fix is checked out**, and a multi-worktree repo has as many
"is it fixed?" answers as it has checkouts.

**Fingerprint that identifies fixture lines** (useful for any future sweep of
this class): `queued` and `RC-010 forwarded` in the **same second** — impossible
for a 120 s git poll, against **470.86 s (~7.85 min)** for the one genuine
command — plus a deterministic `stale (1861s old > 1800s)`, which is
`MAX_AGE_SEC = 1800` (`scripts/remote_control.py:69`) against
`tests/test_remote_control.py:147`'s `time.time() + rc.MAX_AGE_SEC + 60`.

**Standing instruction:** in this tree, `remote_control.log` lines **before
2026-08-01 17:20 local are untrustworthy**. The trustworthy record is the ledger
+ the `pc_status` envelope + the paper-telemetry branch history, which agree
one-for-one. Full account and the four independent confirmations that no real
command ever existed: [[sources/session-20260811-16-vscode-3b307393]] §2.

*(The current `_log(msg, root=ROOT)` docstring in `scripts/remote_control.py`
records the incident in place — a fix that ships its own forensics, which is the
inverse of [[synthesis/documentation-drift-register]].)*

## Related
[[sources/test-suite-outputs-contamination]] · [[concepts/adversarial-verification]] ·
[[synthesis/documentation-drift-register]] · [[concepts/default-path-fallback-writes]]
(the DATA-plane sibling) · [[sources/session-20260811-16-vscode-3b307393]] ·
[[concepts/session-identity-is-not-stable]] (the same "which world am I in?" error,
one level up)
