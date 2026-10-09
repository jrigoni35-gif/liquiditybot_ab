---
name: 432-migration-hold
description: The 432-bar horizon migration is an in-flight experiment at 6/50 closed trades - do not change geometry or retune until cohort_eval reaches 50
metadata: 
  node_type: memory
  type: project
  originSessionId: 63d8f842-8108-448c-b2d9-fa9a4c8a2da4
  modified: 2026-08-02T14:19:25.760Z
---

As of 2026-08-02 the bot is running a single deliberate experiment: the
432-bar (36h) horizon migration, shipped 2026-08-01 (commit 7566ea88). It has
**6 of a pre-registered 50 closed trades**. `scripts/cohort_eval.py` refuses
to render a verdict below 50 and that refusal is the point.

**Do not change the label horizon, barrier geometry, or exit policy until the
cohort fills.** Changing geometry resets the era clock in three places at
once — the cohort counter, era exclusion, and the era-keyed realized gate
ledger — and destroys the only test in progress. Expect roughly 2-3 weeks at
the observed close rate.

**The diagnosis this tests:** cost/sigma was 0.82 at the 2h horizon; the
deployed isotonic calibrator maps its entire input range to [0.0714, 0.2164]
against a gate bar of 0.63, so the bar was unreachable by construction. The
constraint is **cost, not learning**. Round-trip ~0.50% against ~0.3% moves.

**CORRECTED 2026-08-02 by research — three of my supporting claims were
weak or wrong, and the migration is NOT the strongest lever:**

- *"Median loss exceeds worst adverse excursion"* is arithmetically
  impossible on one series; MAE is measured GROSS, P&L is NET. The real
  statement is simpler and worse: **the typical adverse price excursion is
  smaller than the fee. The loss IS the fee.**
- *"87% of trades reached positive MFE"* is uninformative — over 2-36h on
  5-minute bars nearly every trade touches some positive MFE by diffusion.
  Needs a **random-entry control** at the same horizon before it means
  anything.
- *"Kappa rises with absolute horizon, an independent argument for the
  migration"* — under a random walk, cross-horizon correlation is
  sqrt(h1/h2) = 0.707 at ratio 2. Observed 48->96 kappa is **0.736, at or
  above the no-predictability null.** The kappa curve is consistent with
  pure path overlap. It is not evidence of signal.
- **The migration makes uniqueness WORSE**: ~18x concurrency drives mean
  uniqueness from 0.156 toward ~0.009. Hard ceiling on independent
  evidence is total_bars / 432 (~487 windows for two years).
- Novy-Marx & Velikov (2016, *RFS* 29(1):104-147) measured the mitigation
  techniques: **asymmetric entry banding cut turnover 41% and cost 42%
  WITHOUT significantly reducing gross returns and ranks FIRST; reducing
  rebalance frequency ranks LAST** and got zero weight in their efficient
  portfolios. Horizon extension is, in their taxonomy, the weakest lever.
  Qian et al. (2007, *JPM*): horizon extension yields **zero gross
  benefit** - the entire gain is the cost saving.

Migration still runs to n=50 because it is already in flight and thrashing
costs more than waiting. But it is not the best available lever, and
[[cost-is-the-binding-constraint]] lists the ones that are.

**State when this was written:** net -$50.44 over 200 windowed trades, win
rate 5.5%, payoff ratio 0.409, profit factor 0.024. Learning loop repaired
(live_clean 0 -> 24 after 13 days pinned at 0) — that is NOT the same as
profitable, and the two moved in opposite directions the day it was fixed.

**Two techniques ruled out with evidence, not preference** — see
[[meta-labeling-unvalidated]]. Do not propose either as a fix.

**Tripwires worth checking, in priority order:**
1. `ml.gate_stats.realized_closed` climbing from 0. Stuck at 0 while trades
   close means `gates_passed` is not reaching the position and the
   realized-outcome loop is dead — the exact failure it was built to fix.
2. `scripts/cohort_eval.py` progress toward 50.
3. `outputs/auto_update.log` showing `rev 162c595c` deployed.
4. `liquiditybot_era_mix_alarm` — was firing on 2026-08-02.

Related: [[grafana-boards-are-generated]]
