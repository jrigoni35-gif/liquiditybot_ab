---
title: "Host-State-Dependent Green (a suite green is a claim about code × host state)"
category: concept
status: SETTLED
summary: "The same test suite, same day, produced three different reproducible outcomes on three host states — the live repo's long-running bot state MASKS fixture defects a fresh checkout exposes, so a live-repo green overstates; the honest corpus for 'does the code pass its suite' is a fresh worktree"
tags: [testing, false-green, host-state, worktree, ci, measurement-plane]
sources: 1
updated: 2026-08-27
---

# Host-State-Dependent Green

**The claim a passing suite makes is about (code × host state), never
about code alone — and the live repo is the most flattering host state
available.** A member of the [[concepts/false-green]] family, measured
2026-08-27 ([[sources/session-20260827-sdd-verification-and-era-confound]] §3).

## The type specimen (three outcomes, one day, all reproducible)

| corpus | result |
|---|---|
| live repo at `62ab10c0` (running bot's host state) | 4060 passed / 0 failed / 9 skipped |
| fresh worktree at `6f8b6315` — twice, independently | 2 failed / 4085 passed / 9 skipped / 1 error |
| fresh worktree at bare main `5e785c16` | the same 3 reds |

The 3 fresh-checkout reds are pre-existing **main** defects invisible on
the live repo, because host state supplies what the fixtures forgot:

- **Defect #9**: `tests/test_trading_dashboard.py`'s `_aux_emitted()`
  rebinds four sibling paths but never `gc_pusher.VETO_SCRIPT` — the
  veto-quality subprocess shells out for real. On the live repo it finds
  the running bot's **real audit history** and passes; on a fresh
  checkout it finds nothing and the metric family vanishes.
- **Defect #10**: `scripts/pc_supervisor.py:104` `_VAULT_GUARD_STAMP`
  is missing from conftest's `_REDIRECTED_PATH_ATTRS` (the 10th
  leak-class instance; `3ec6dbbc` fixed the 9th). On the live repo the
  stamp file **already existed** (written by the running bot at 15:49
  that day), so `_stamp_due` never fired; on a fresh checkout the write
  fires into `outputs/` and the conftest production-outputs tripwire
  catches it ([[sources/test-suite-outputs-contamination]]).

And the inversion: the live repo showed an **order-dependent flake**
(`test_fee_reconciliation::test_credential_less_environment_skips_silently`,
audit-chain state bleed, passes in isolation) that the fresh runs never
did. Host state manufactures reds as well as greens.

## The operating rules

1. **Cite the corpus with the green.** "The suite passed" is incomplete
   until it says *on which host state* — same law as "a green is only as
   big as its corpus" (CLAUDE.md), applied to the machine rather than
   the data.
2. **The honest corpus for "does the code pass its suite" is a fresh
   worktree.** A live-repo green **overstates**; use it to answer "does
   the code pass here", never "does the code pass". Remedy owed:
   a fresh-worktree CI leg (owed 105, [[synthesis/owed-measurements]];
   adoption ranked in the repo's `docs/research/llm_test_suites/`).
   *[UPD 2026-08-28: defects #9/#10 FIXED and pushed (`0257fd59` —
   stamp registered, fixture rebound; fresh-worktree acceptance green);
   the CI leg itself remains the open half of owed 105, and it gained a
   second customer — the C++ diode's 8 skips are PERMANENT on this box
   under Smart App Control, so diode verification has no other home.]*
3. **Two greens on different host states are two different
   measurements** — reconcile them, don't average or pick the greener.
4. Every fixture that stubs a path family must be checked against the
   *complete* family — both specimens here were siblings of correctly
   stubbed attributes. The leak-class count (now 10) says the family
   keeps growing; the redirect list is a coverage surface, not a
   one-time fix.

## What this page could not see

One session, one repo, Windows host, two host states plus a
self-polluted third (recorded [UNKNOWN, not re-established] in the T4
report). The class surely includes host-state dimensions not yet
measured here (clock, env vars, OS — the 08-22 "wrong OS, not wrong
code" HANDOFF row is the platform-axis sibling of this defect).

## Related
[[concepts/false-green]] · [[concepts/honest-absence-contract]] ·
[[sources/test-suite-outputs-contamination]] ·
[[sources/session-20260827-sdd-verification-and-era-confound]]
