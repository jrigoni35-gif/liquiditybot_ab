---
title: Location-Invariant Tests (the deploy-gate worktree contract)
category: concept
summary: The deploy-gate worktree location is part of the test contract — any test that filters files by path must be location-invariant, because the gate battery runs in a worktree nested inside outputs/ and a substring path filter there sees every file as excluded
tags: [tests, deploy, defect-class, contract]
sources: 1
updated: 2026-08-04
---

# Location-Invariant Tests (the deploy-gate worktree contract)

**The contract:** the deploy gate ([[entities/auto-update]]) runs the battery in a scratch
worktree at `outputs/_update_wt_<pid>` — *inside* `outputs/` (audit C-F11 reclaimability).
That location is **part of the test contract**: any test that filters files by path must
produce the same result regardless of where the checkout sits on disk.

## The defining incident (2026-08-04, fixed `242568fb`)

A HIG test excluded scan files by **substring on the absolute path**
(`"outputs" not in str(f)`). In the gate worktree every absolute path contains `"outputs"`,
so the scan saw an empty repo and `test_trajectory_metrics_exist_in_exporter` failed —
**green in every dev checkout, red exactly where deploys are decided.** The gate rejected the
first externally-pushed commits twice, deterministically, before the mechanism was named
([[sources/session-20260804-deploy-gate]]).

This is the worst polarity a test defect can have: it never fires where developers look, and
it always fires where deploys are decided — presenting as a deploy blocker, not a test bug.

## The fix pattern

- **Exclude by path components relative to ROOT**, never by substring on an absolute path.
- Or **enumerate directories explicitly** — `test_dependency_hygiene` is the by-construction
  example: explicit dir enumeration, location-invariant without trying.
- **Verify two-sided**: in a simulated outputs-nested worktree, the old filter must
  *reproduce the exact gate red* and the fixed filter must go green *in the same location*
  (here: 15/15). A fix verified only in a dev checkout proves nothing — that environment was
  never red.

## The wider defect class: substring where identity was required

Third instance in one week of the same class — matching by **substring/shape** where
**identity** was the requirement:

1. **`position_id` grouping** — one position under 16 ids, the 27x P&L error
   ([[synthesis/open-contradictions-register]] #2b: key on the fill pattern, not the id).
2. **The round-number error** (the week's data errors, per
   [[sources/session-20260804-deploy-gate]]).
3. **Absolute-path substrings** — this page's incident.

The sibling hazard is already filed under [[concepts/iron-law-of-debugging]]: arithmetic
*shape* is not provenance either ([[sources/session-20260803-bug-sweep]] finding 2). The
general rule: **match on the identifying structure (components, keys, chains), never on a
string that merely correlates with it.**

## Related
[[entities/auto-update]] · [[sources/session-20260804-deploy-gate]] ·
[[concepts/iron-law-of-debugging]] · [[concepts/default-path-fallback-writes]]
