---
title: Phase 3 Adjudication (2026-07-26)
category: source
summary: Three Phase-3 instruments measured against the binding PBO admission policy on one static corpus, all four readings adjudicated DEFER with every flag left off
tags: [pbo, adjudication, defer, feature-pruning, gbt-mono]
sources: 1
updated: 2026-08-01
---

# Phase 3 Adjudication (2026-07-26)

**Raw source:** `raw/quant/2026-07-26_phase3_adjudication.md`

## Verdict
All four readings **DEFER**. Every production flag stays OFF pending operator sign-off. Nothing in
the document flips a config default. See [[concepts/defer-verdict]].

## Method
One static corpus (4,642 rows, 240 live) for every reading. ADOPT requires the variant to win under
the DEPLOYED [[concepts/simplicity-ladder]] rule (`BRIER_MARGIN` climb, never argmax) AND not degrade
pbo. Ambient baseline: 4 passed / 4 failed, OF-3 pbo 0.23 over 7 configs / 70 splits.

## Experiment 1 — schema-ab (feature pruning)
Feature stability run 3x (3 seeds x 3 n_splits each): 13 / 10 / 10 always-dead. Three-way stable
intersection = **8 features**. Coverage-floor screen clears only **5** (`corr_shift`, `depth_ratio`,
`equity_risk_z`, `opt_oi_pcr_z`, `pat_engulf_dir`); `sent_fear`, `th_clockwork`, `th_metronome` are
DORMANT and not prune-eligible.

- **1a policy-cleared (5 pruned)**: widened pbo 0.21; pairwise pbo **0.94**; ladder_winner = the BASE
  (full-feature). **DEFER.**
- **1b raw 8-feature (contrast only)**: widened pbo 0.17; pairwise pbo 0.07; the pruned arm WINS —
  but is disqualified by the coverage floor. "The apparent PBO improvement here is mechanical:
  pruning nearly-all-zero columns lowers effective degrees of freedom, which improves CSCV's
  selection-bias reading almost by construction."

**The divergence between the two lists is itself the demonstration of why the coverage floor is
binding.** See [[concepts/coverage-floor]].

## Experiment 2 — epoch-ab (row filtering)
1,456/4,642 rows kept; fold 0 degraded (n=19 too thin to fit). Widened pbo degrades 0.23 -> 0.37;
base wins both ladder and mean. **DEFER, unambiguously.**

## Experiment 3 — gbt_mono (monotone constraints)
Widened pbo 0.1286; `gbt_mono` is not even the mean-argmax. Pairwise: mean neg-Brier
`gbt_d4_lr05` -0.165588 vs `gbt_mono` -0.197256 (delta -0.0317); pairwise pbo 0.0 — "the pairing
never varies". **DEFER.**

> Explicit citation hazard: `gbt_d4_lr05` is `gbt_mono`'s predecessor in `_BASE_ORDER` **only**. In
> the ladder the bot actually runs, `gbt_mono`'s predecessor is plain `gbt` (depth-2/lr-0.03), absent
> from the measured space. The pairing therefore confounds an architecture change with a
> hyperparameter change. **"This DEFER must not be cited as 'monotone constraints were measured
> against gbt and lost'."** The clean comparison was never run.

## Framing
"A DEFER verdict is a successful, informative outcome of this measurement exercise — not a failure of
it; nothing here was stretched to manufacture an ADOPT."

## Related
[[comparisons/dormant-vs-inert-features]] · [[entities/overfit-check]]
