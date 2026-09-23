# Decision record — v10 mid-era activation; ruling B (split the read)

**Date:** 2026-09-23 · **Operator ruling:** B, given in session · **Status:** EXECUTED (code landed, readout live)

## The question

The dark-pool session (conv-eb3b19b7) left a 29-file diff uncommitted in the
main tree on 2026-09-21; the runner picked it up at **2026-09-21T20:25:20Z**
(derived, not asserted: first `avail_darkpool != ''` row in
`outputs/signal_history.csv`). The diff carried a v10 feature-schema bump
(64→68: `dp_surge_z`, `dp_vol_z`, `dp_hhi`, `avail_dp`), which forced the
width-guard in `ml/registry.py` to retire the v9 champion and let the
retrain loop promote a v10-space champion (live brier moved 0.2410 →
0.2015 on 2026-09-23, confirming a retrain-and-promote event).

Asked 2026-09-23: **should it have been active?**

## Finding: no

Under the letter of the era-9 moratorium this is a cohort-resetting change
to **entry decisioning** taken without adjudication:

1. The feature space the entry scorer reads changed mid-era.
2. Real new information reached the scorer — 632 signal rows with
   `avail_darkpool=1`, so the shadow block was lit, not inert.
3. Model-side investment was frozen by the 2026-08-10 adjudication; the
   retrain loop continuing by design blesses retraining on the SAME space,
   not adding columns to it.
4. Neither exemption applies (not a safety invariant, not a wrong-venue
   constant).

The correct play was a held branch (the R2 pattern), presented at this
boundary.

Mitigations, recorded for fairness: the construction itself is careful
(deny-list registration strengthening invariant 3, neutral-on-failure,
availability gating at the vector boundary, honest `""=UNKNOWN` migration
padding, pre-registered promotion criteria), and the full suite was green
on the tree (5610 passed) before the measurement plane committed it as
`12a164f06` under the operator's tree-settlement directive with the
sibling session's standing delegation.

## The ruling: B — split the read

- Era-9 keeps accruing. No mint, no restart of the clock.
- The era readout reports the **uncontaminated v9 cohort** beside the
  pooled SELECTED row. The verdict at n=100 reads on the v9 cohort.
- Cohort follows **entry time** (`t_open`): commit `12a164f06` changed the
  feature space but touched no exit/sizing code (verified hunk-by-hunk in
  this record's investigation), so a trip's decision regime is set when it
  opens.
- The cutoff is **derived at read time** from the first non-empty
  `avail_darkpool` row in `signal_history.csv` — never a hardcoded
  literal; if the column is absent the readout reports the split as not
  applicable instead of guessing.

## Mechanism (landed)

`scripts/era_readout.py`: `cohort_cutoff()` + a `cohorts` block in
`run()`/`render()` (additive key in `--json`, back-compatible).
`tests/test_era_readout.py`: 4 pins (first-non-empty cutoff, absent/empty
column, entry-time split incl. a straddler trip, back-compat with no
signal history). 48/48 green; ruff/bandit/compileall clean;
`boundary_payload.py` regenerated, all five sections ok.

## First live split (2026-09-23T~18:0xZ readout)

| cohort | n | net $/trip | 95% CI | lean |
|---|---|---|---|---|
| pooled SELECTED | 60 | −0.470 (prev. read) | excludes zero below | ACT-negative |
| **v9 (uncontaminated)** | **51** | **−0.4655** | **[−0.6858, −0.2558]** | **ACT-negative** |
| v10 | 9 | −0.4467 | [−0.5703, −0.1996] | not reached |

The v9 cohort has itself crossed n=50 with the CI excluding zero from
below — the lean is ACT-negative with or without the v10 trips. The two
cohort means are nearly identical (−0.4655 vs −0.4467); at n=9 the v10
cohort carries no independent information yet, and there is no sign the
dark-pool block changed outcomes.

## Consequence for the n=100 verdict

The verdict reads on the **v9 cohort**, currently 51/100. Pooled n=60 is
reported for continuity only. If the operator later rules the v10 block
promoted (its own pre-registered TANK quant-2 criteria), cohorts merge
from that date forward; the split stays in the readout either way —
turning it off would be a registration amendment, not a code fix.
