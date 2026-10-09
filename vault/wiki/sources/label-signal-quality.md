---
title: Label Signal Quality (2026-07-26)
category: source
summary: The training label was flipped to triple_barrier because the old label recorded which exit fired rather than whether the signal was good
tags: [labeling, triple-barrier, leakage, label-era]
sources: 1
updated: 2026-08-01
---

# Label Signal Quality (2026-07-26)

**Raw source:** `raw/quant/2026-07-26_label_signal_quality.md`

## The finding
The old label came from replaying the live exit engine, so it recorded **which exit fired**, not
whether the signal was good.

## Evidence
- Label rate by exit reason spans **100x**: `time_stop` 0.0071, `sl` 0.0364, `time` 0.0686,
  `realized` 0.1036, `trail` **0.6867** (the only winning bucket).
- `trail` fell from 49.5% of daily rows to 0.0% while `sl` + `time_stop` grew to 100%, collapsing the
  base rate ~0.31 -> ~0.03.
- `time_stop` alone reached 43.8% of rows at a 0.71% win rate; its first appearance is **14 minutes
  after** commit `5f26d3f` taught the label simulator to mirror the P2 time-stop.
- **Barrier-alone AUC 0.769 beats the 62-feature model's own 0.597**; a pure clock scores 0.667; BSS
  negative for both champion and challenger. "The model was learning the barrier, not the signal."

## The conceptual claim
"A time-stop is a RISK CONTROL ('we chose not to wait'), not an OUTCOME ('the signal was wrong')."

## The change
`ml.label_mode = "triple_barrier"` — barriers all market- or horizon-determined, with the net-of-cost
rule unchanged (`label_pt_vol_mult=8`, `label_sl_vol_mult=6`, `label_round_trip_cost_pct=0.5`). No
policy exit reason can enter the label.

## The era-collision blocker
`triple_barrier()` emits bare `pt`/`sl`/`time` — the SAME strings `legacy` and `exit_sim` already
claim. Flipping `label_mode` alone would have silently mis-tagged every new row into two OLD
incompatible populations — "exactly the failure the era instrument exists to catch." Fix: prefix to
`tb_pt`/`tb_sl`/`tb_time` **at the one dispatch call site whose output reaches the persisted corpus**,
leaving `triple_barrier()` itself untouched. New constant `LABEL_ERA_TRIPLE_BARRIER`.

## Conscious override
Overrides commit `c36aa90` ("flip label default to exit-policy replay — train on the bet we trade").
That decision "was defensible; the operator weighed it against measured evidence and chose the other
side." `"exit_policy"` remains supported as the rollback path.

## Left open (closed same day)
"Whether to exclude the old eras from training is a SEPARATE operator decision this task leaves open
(excluding them would collapse the corpus below the evidence floors)" — answered by
[[sources/era-exclusion-decision]]. See [[concepts/label-era]].
