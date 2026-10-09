---
title: PBO Admission Policy — the Gort Rule (BINDING)
category: source
summary: Binding policy that no policy-class challenger may become champion-swap eligible until measured inside CSCV under the deployed rule, plus the coverage floor and consumer-consistency prerequisite
tags: [policy, binding, pbo, cscv, coverage-floor]
sources: 1
updated: 2026-08-01
---

# PBO Admission Policy — the Gort Rule (BINDING)

**Raw source:** `raw/quant/pbo_admission_policy.md`

**Status: BINDING.** Governs every future policy-class challenger. See [[concepts/gort-rule]].

## The four rules
1. **CSCV entry gates champion-swap eligibility.** Any policy-class challenger (model family, schema
   variant, row-inclusion variant, constraint variant) enters OF-3's CSCV as a measured config BEFORE
   it may be considered for a champion swap. "Shipping the code path disabled is not, by itself,
   admission — it is the prerequisite that makes admission possible later, on its own conscious
   commit."
2. **Every space expansion is a conscious re-baseline**, investigated with the
   [[concepts/inertness-protocol]] and documented in `docs/quant/` — "never silently absorbed into
   'PBO is what it is this week'."
3. **The deployed simplicity-ladder rule is the only selection read** — never argmax. "A challenger
   that would win on argmax but isn't what the deployed rule would have picked is not evidence for
   anything; it is exactly the overfitting CSCV exists to catch."
4. **Live-label evidence floors gate family admission ahead of any PBO reading** — "a family fit on
   too few real closed-trade labels only manufactures a lucky winner, which inflates PBO for no real
   reason."

## The coverage floor
**`always_dead` alone is not sufficient evidence to prune a feature.** A coverage/variance probe
splits the 13 always-dead features into two populations:

- **Dormant / coverage-starved** (never prune-eligible): `sent_fear` (0.00% nonzero, feed constant),
  `th_clockwork` (1.34%), `th_metronome` (1.49%). The latter two are THALES manipulation detectors —
  "pruning them would permanently blind the anti-predation layer at exactly the moment manipulation
  begins to fire."
- **Inert** (legitimate prune candidates — real variance, well covered, zero measured DoF):
  `depth_ratio` (100% coverage), `liq_pocket_pull` (99.66%), `ret_12_dir` (98.73%), `corr_shift`
  (89.12%), `pat_marubozu_dir`, `imbalance_delta_dir`, `pat_engulf_dir` (12.43%), `equity_risk_z`
  (10.94%), `opt_oi_pcr_z` (5.45%). `dominance_delta` is **scale-suspect**, unresolved.

**There is NO numeric threshold** — `opt_oi_pcr_z` cleared at 5.45% while `th_metronome` did not at
1.49%. Every application must carry a named, written justification. "The burden of proof sits with
the prune, not with the feature."

## Consumer-consistency prerequisite
Only **1 of 6** training-corpus consumers received `epoch_cfg` (the production retrain path). If
`ml.epoch.exclude_old_candidates` flipped true, `main.py` would train on a filtered corpus while
`overfit_check.py` kept measuring the unfiltered one — "an adoption reading taken under that mismatch
would certify a selection process the bot no longer trains on." Before the flip, every consumer must
be threaded or consciously exempted in writing.
