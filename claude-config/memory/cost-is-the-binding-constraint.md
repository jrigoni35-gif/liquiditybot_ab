---
name: cost-is-the-binding-constraint
description: "FREEZE LIFTED 2026-09-29 by operator ruling (repo CLAUDE.md) — the freeze half below is history. Corrected 3x. 2026-08-10 adjudication: MODEL-SIDE INVESTMENT FROZEN; the era-4 pre-registered gate (cohort_eval, n=50 honest-fill closes) is the only unfreeze/stop trigger. Earlier: payoff asymmetry, not cost, not signal"
metadata: 
  node_type: memory
  type: project
  originSessionId: 63d8f842-8108-448c-b2d9-fa9a4c8a2da4
  modified: 2026-10-04T13:48:23.220Z
---

**2026-10-04 CURRENCY NOTE — the freeze below is NO LONGER IN FORCE.** Repo
`CLAUDE.md`: "Model freeze LIFTED 2026-09-29 (operator, verbatim: 'Lift the
model freeze'; supersedes the 2026-08-10 adjudication)". It was lifted by
operator ruling, not by the era-4 gate this note names as the "only" trigger.
Guardrails that stay: overfit discipline, cohort fork for feature/schema
changes, CS-1 counting, no retuning on a cohort's own accruing gate numbers.
The payoff-asymmetry finding is unaffected. Original text kept below.

**2026-08-10 OPERATOR ADJUDICATION (CAIO review, "apply them") — READ FIRST.**

**Model-side investment is FROZEN**: no new model families, no meta-labeling
(already ruled out), no API/frontier/fine-tune escalation, no feature
expansion pitched as a fix. Why: champion Brier 0.24728 vs 0.25 coin; OOF
Brier flat across 196 retrains (0.16856→0.16743); gross edge −0.0019%/trade
(t=−0.332) with fees 368× |edge| — a better model multiplies a zero.

**The only unfreeze trigger** is the era-4 pre-registered gate in
`scripts/cohort_eval.py` (registered 2026-08-10 at n=1; boundary #4 =
aeeaae36, 2026-08-10T11:03:35Z — cut on the UTC instant, never a local
date): at n=50 entry-opened honest-fill closes it reads out NO_GROSS_EDGE
(stop-strategy question goes to operator) / COST_BOUND (h432 fee levers
become the live discussion) / CONTINUE. Do not read the accruing numbers
early; do not re-propose model work while frozen. Where AI spend does
continue: the measurement layer — that is where every verified win has come
from.

**How to apply:** if a session drifts toward "try a better model / new
features / another gate", cite this freeze and the gate instead. All four
execution eras before aeeaae36 carried a ~1.88× near-touch fill inflation;
pre-boundary fill statistics are not citable for the strategy verdict.

**$800 STRESSOR REGIME (2026-08-10T23:05:27Z, operator-adjudicated).**
Capital reset 5000→800, target $100/month (12.5%/mo), RP-072 ladder: each
month closing ≥100% attainment raises the bar ×1.5, never down. The gate's
verdict population cut is max(B4_TS, CAPITAL_EPOCH_TS) — one capital
regime, accrual restarted 0/50. Venue floors ($15 min ticket = 1.9% of
equity) deliberately unscaled: the bite IS the stressor. Every pre-reset
dollar figure (equity curves, perf windows, expectancy) is $5000-regime
and must not be compared against post-reset numbers without saying so.
The era-4 accrual moratorium in repo CLAUDE.md fences entry/sizing/fill
changes until readout.

---

**CORRECTED TWICE ON 2026-08-02. Read this block before anything below it.**

**Both earlier headlines were wrong, and both were wrong from contaminated
data.** The file first said cost was the binding constraint; then that the
strategy "loses ~0.34% per trade with fees at zero" and it was an ENTRY EDGE
problem. Neither survived measurement. Do not re-derive either.

**What is actually true**, measured per-fill from `outputs/fills.csv` by
`scripts/breakeven_test.py` and `scripts/cost_attribution.py` (commit
f0120393, n=215 - re-run rather than trusting these, the file grows live):

```
mean gross -0.048%   median gross +0.049%   win rate 57.5%
mean win   +0.2625%  mean loss    -0.4685%  payoff ratio 0.560
```

**The hit rate is fine. The sizes are wrong.** Break-even payoff at a 57.5%
win rate is 0.740; observed is 0.560. The average loser is 1.8x the average
winner - the AVERAGE loser, not a tail. Post-purge the distribution is
near-symmetric (min -2.38%, max +1.87%; dropping the worst 5% moves the mean
only to +0.031%), so **"tail risk" is refuted** - that read came entirely from
one fabricated trade counted 16 times.

**The decisive number.** Win rate needed to break even, holding sizes fixed,
`p = (cost + L)/(W + L)`: **IMPOSSIBLE (p > 1) at all three real fee
schedules**, including Kraken maker/maker at 0.320%. Only at zero fees does it
become finite, at 64.1%. So:

- **Raising the hit rate cannot fix this.** Only shrinking the average loser
  or extending the average winner can. That is **exit geometry** - stop
  distance, target distance, time stop.
- **A better model is not the first move.** A model raises `p`, and `p` is
  not the binding term. Same for gates, filters, and meta-labeling.
- Fees are still the larger term (0.667% against a 0.048% gross gap), but
  cutting them to zero leaves -0.048%. Cost levers are necessary and not
  sufficient.

**Why the old numbers were wrong** - the general lesson: they were computed by
grouping on `position_id`, and one position appeared under 16 ids. See
[[fills-duplicate-on-restart]]; that bug is UNFIXED, so this can recur.
The -1.32% figure was wrong by 27x, and the "net + assumed cost" method that
produced -0.34% could not separate fees from slippage at all.

Everything below still holds as literature and as ruled-out territory. The
random-entry control (test 1) is still worth running and was never run. Test 2
is now done - that is what this block reports.

---

Researched 2026-08-02 across three deep literature passes. Every thread
converged: **this is not a sample-size or model problem.**

**The identification impossibility.** At payoff ratio 0.409, profit factor 1
requires win rate **70.97%**. By Bayes at a 5.5% base rate, 71% precision
needs a **likelihood ratio of 42** - keep every winner while rejecting 97.6%
of losers. There are 11 winners x 0.156 uniqueness ~= **1.7 effective
independent positive examples**. An LR-42 boundary is not estimable from ~2
effective positives. No filter, model, or weighting scheme closes this.

## The two tests to run first - hours of work, decisive

1. **Random-entry control on MFE.** Sample entries uniformly at random at the
   same horizon; compute identical MFE statistics. If random entries also
   reach positive MFE ~87% of the time, **there is no signal and everything
   downstream is moot.** Highest information per hour available.
2. **Break-even transaction cost.** Mean **GROSS** (zero-cost) P&L per round
   trip at the intended exit rule. **If below 0.50%, no exit rule, holding
   period, or sizing scheme makes this profitable** and the correct action is
   to stop. This is what the entire cost literature implicitly computes.

Note there is **no statistical power problem**: win rate 5.5%, payoff 0.409,
200 trades gives t ~= -40. Do not spend effort on Deflated Sharpe or Minimum
Track Record Length - they answer "is this positive result real?", and there
is no positive result.

## Levers ranked by measured evidence

1. **Maker-only execution.** Kraken 0.16% maker / 0.26% taker: round trip
   0.52% -> **0.32%, a 38% cut**, moving cost/sigma 0.23 -> ~0.15 at 36h.
   Barber, Lee, Liu & Odean (2009, *RFS* 22(2):609-632) on every Taiwanese
   investor: *"virtually all individual trading losses can be traced to their
   aggressive orders"* while passive orders were profitable. Costs fill
   uncertainty, which changes label geometry - a real design change.
2. **Asymmetric entry banding** (high entry hurdle, low exit hurdle). 41%
   turnover cut, 42% cost cut, gross returns *not* significantly reduced -
   the only technique producing consistent net gains, and it rescued their
   high-turnover combo from t=1.11 to **t=5.23**.
3. **Pool across symbols.** The only method that genuinely RAISES effective
   sample size rather than redistributing it: ~50 pairs gives contemporaneous
   rather than temporally-overlapping labels, sidestepping the uniqueness
   ceiling instead of patching it. Gu, Kelly & Xiu (2020, *RFS* 33(5)).
4. Walk-forward validation, not CPCV (Schnaubelt: rolling-origin bias -0.166
   vs random CV -0.887; blocking captures 54% of the available reduction,
   purging adds ~1% more). **Check (purge width x test events) / sample
   length BEFORE enabling purging** - at 432 bars purging can starve the
   training set and inflate error estimates up to 65x.

## Ruled out with measured evidence - do not propose

Sequential bootstrap / uniqueness weighting (the one independent replication
is null; it raises uniqueness *of bootstrap draws*, not dataset ESS).
SMOTE or any oversampling (AUC 0.95 on **pure noise** if applied before
splitting; destroys calibration; ~0 benefit against gradient-boosted trees).
GAN / diffusion synthetic paths (five independent negatives; measured
degradation at NeurIPS 2023; 8% memorization). Jitter/warp/rotate/permute
(44 of 72 method-architecture pairs *harmful*; financial returns have none of
the invariances these assume). MFE-quantile exit tuning (folklore from a 1996
trade book, no peer-reviewed base; every published rescue works by trading
*less often*, never by changing the exit alone).

Also ruled out: [[meta-labeling-unvalidated]].

Related: [[432-migration-hold]]
