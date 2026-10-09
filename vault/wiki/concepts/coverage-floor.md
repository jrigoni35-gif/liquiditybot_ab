---
title: The Coverage Floor
category: concept
summary: A feature appearing in always_dead is not by itself sufficient evidence to prune it; dormant features are capability held in reserve
tags: [features, pruning, policy]
sources: 3
updated: 2026-08-01
---

# The Coverage Floor

## Definition
`always_dead` membership alone does not make a feature prune-eligible. A coverage/variance probe splits
the always-dead set into two populations:

- **Dormant / coverage-starved** — dead **for lack of exposure**. Never prune-eligible.
- **Inert** — real variance, well covered, still zero measured degrees of freedom. Legitimate prune
  candidate.

## The governing principle
> "A feature that is dead for lack of exposure is a capability held in reserve, not a capability proven
> useless... **the burden of proof sits with the prune, not with the feature.**"

The exemption already granted to regime one-hots "is not a special case — it is an instance of a
general principle."

## The load-bearing example
`th_clockwork` (1.34% nonzero) and `th_metronome` (1.49%) are THALES manipulation detectors —
**"pruning them would permanently blind the anti-predation layer at exactly the moment manipulation
begins to fire."**

## Deliberately no numeric threshold
`opt_oi_pcr_z` cleared at **5.45%** nonzero while `th_metronome` did not at **1.49%**. Because the floor
is only ever used to BLOCK a prune, ambiguity errs safe ("when in doubt, don't prune") — but every
application must carry a **named, written justification**, "never a bare `nonzero_frac > X` cutoff."

## Why it is load-bearing, demonstrated
In [[sources/phase3-adjudication]] the raw 8-feature prune WINS under the deployed rule (pairwise pbo
0.07) while the policy-cleared 5-feature prune LOSES (0.94). Rather than treating the winning read as
evidence, the divergence is reframed as proof the floor is binding — because the win is **mechanical**:
"pruning nearly-all-zero columns lowers the model's effective degrees of freedom, which improves CSCV's
selection-bias reading almost by construction."

## Compare
[[comparisons/dormant-vs-inert-features]] — the two populations side by side.

## Unresolved
`dominance_delta` is classified **scale-suspect** (79.41% coverage but std 0.0143 — near-constant),
neither dormant nor clearly inert.
