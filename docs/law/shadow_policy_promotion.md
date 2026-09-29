# Shadow policy promotion law (items 1b + 3, operator ruling 2026-09-29)

The shadow traded-value rule — *enter iff the predicted value of this candidate
is > 0* — lives in `ml/shadow_policy.py` (store), is graded by
`scripts/shadow_policy_report.py`, and **decides nothing** until every condition
below holds at once. `tests/test_shadow_policy.py` pins that no order-path module
reads the store.

## Why the rule exists

The model is trained on a clean signal-quality label (the 2026-07-26 ruling:
exit-policy labels leaked exit mechanics — barrier-alone AUC 0.769 beat the model's
0.597). Since 1a the label bet and the bracket bet share one geometry function and
one cost input. But the live entry bar (0.6381) is derived from the label payoff,
and the fair-game arithmetic on the TRADED payoff (era-9: a_eff +85 / b_eff −140
bps) puts break-even near p\* ≈ 0.82 — the bar and the bet disagree. Deciding on
predicted value instead of a p threshold closes that gap, *if* the prediction is
real. This law is how "if" gets answered.

## Promotion conditions (ALL, simultaneously)

1. **Sample.** ≥ 200 would-enter shadow rows with RESOLVED outcomes, graded
   walk-forward (no look-ahead — pinned by mutation) under counting standard CS-1
   with a reconciliation line that reads OK.
2. **Sign with confidence.** The would-enter mean label return's 95% day-block
   bootstrap CI (the registered `era_readout.day_block_bootstrap`, 4,000 reps,
   seed 7) lies entirely above zero.
3. **Beats what trades today.** The would-enter mean exceeds the live-taken traded
   mean over the same window, and the report says so with both numbers.
4. **Overfit battery green** (`scripts/overfit_check.py`) on the corpus the rule
   was graded on — no new red rung, no lowered floor.
5. **An operator decision record** in `docs/quant/` naming the rule, the evidence
   run (report output + timestamp), and the fingerprint cohort it will fork.

A report line reading `EVIDENCE MET` covers conditions 1–2 only. It is never a
promotion by itself.

## What promotion changes

The entry decision reads the shadow prediction instead of (or beside) the p-bar.
That is a change on the fork axes — it forks the decision cohort automatically
(`core/cohort.py`), and the new cohort's own registered read decides whether it
stays. Rollback is the config switch that returns the entry decision to the p-bar.

## What this law does not do

It does not touch the label (the 2026-07-26 ruling stands), exits (the 2026-09-27
replay ruled exit geometry out as the lever), or sizing.
