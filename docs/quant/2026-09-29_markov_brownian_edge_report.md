# 2026-09-29 — Markov-modulated Brownian edge: walk-forward result (SAFE, research only)

Operator, verbatim: "Look at the pursuit of direction price edges and what they
are accomplishing according to there formulas and focuses." / "Instead of just
finding one and using it do a Markov chain forming the best possible
solutions." / "Also included is brownian theory and walk forwards." / "These
need to be done with porcelain hands."

**Class: SAFE** (measurement tool + research module + tests). Nothing in the
order path imports `ml/markov_edge.py` (pinned). No config, no decision-path
code, no cohort fork.

## Instrument

- `ml/markov_edge.py` — drifted-Brownian first passage in dimensionless form
  `P_up = (e^{psi r} - 1)/(e^{psi r} - e^{-psi(1-r)})`, `psi = theta (a+b)`,
  `r = b/(a+b)`; per-state MAP drift under a prior worth 50 driftless
  observations; Dirichlet-smoothed per-asset transition matrix; occupancy-
  averaged drift over the driftless expected exit time
  `E[tau] = (a/sigma)(b/sigma)` bars; action = max EV over long/short/skip,
  `V = p a - (1-p) b - C`.
- `scripts/markov_edge_report.py` — pre-registered in its docstring before run 1:
  6 state specs x {static, chain}, one UTC test day per fold, train purged by
  the 36 h label horizon, within-day state-permutation null, day-block CI,
  CS-1 reconcile. Metric (3), within-day AUC, is an AMENDMENT added after run 1
  and labelled as such in the script.
- `tests/test_markov_edge.py` — 37 tests incl. Monte Carlo agreement, planted
  edge found / no edge not invented / null destroys a planted edge, purge,
  purity. Mutation sweep 7/7 caught against a green control (one pin was
  strengthened after it missed "prior ignored").

## Result (snapshot of `outputs/signal_history.csv` 2026-09-29T20:10:58Z,
sha256 prefix c732f653e3d853b, 34,771 lines; 200 null reps)

Corpus: 6,929 era-9 triple-barrier candidate rows over 22 days; 14 test days;
4,852 rows scored. `counting CS-1: n=34770 = not_candidate_tb=5203 +
pre_era9=22638 + unparseable=0 + burn_in_train_only=2077 + scored=4852 [OK]`.
Re-derive by running the script; do not copy these into law.

1. **No spec beats the fair game out of sample.** Calibration gain vs
   driftless (psi = 0) is negative in all 12 cells (-0.023 .. -0.047
   nats/row). Where the permutation null p is small, the real states merely
   lose LESS than shuffled states.
2. **The day level dominates.** The per-day share of up-first outcomes runs
   0.005 .. 0.962 (the four assets trend together); the pooled drift fitted on
   past days flips sign across the window (-3.4 .. +0.8). Effective n is the
   day count, not the row count.
3. **Weak within-day ranking exists, and only in basis.** Within-day AUC:
   `basis` static 0.533 [0.508, 0.560] p=0.010; `hmm_x_basis` static 0.558
   [0.514, 0.603] p=0.005 (= the 1/201 floor of 200 reps). 12 tests and a
   post-run metric: neither clears Bonferroni 0.0042 at this null
   resolution. Consistent with the 2026-09-29 per-feature screen (basis_dir
   AUC 0.463, the second genuinely directional feature). This is rank
   information, not a drift large enough to pay: break-even needs psi ~ +1.2
   (p from 0.4286 to p* 0.571 at the label geometry, cost ~45 bps).
4. **The chain dilutes, it does not compound.** Basis states persist
   stay ~0.4 per candidate step against a ~48-step expected hold, so occupancy
   averaging pulls every state to the pooled drift; chain variants take 9-106
   of 4,852 rows and their AUC falls to ~0.5. HMM regimes persist (stay
   0.92-0.98) but carry no out-of-sample drift.
5. **Decision uplift**: no positive CI anywhere; `basis_x_disloc` static
   (-47.8 bps [-88.8, -9.7]) and `disloc` chain (-40.3 [-87.5, -2.2]) are
   significantly HARMFUL — the in-sample "venue dislocation negative -> long,
   +17 bps" row does not survive walk-forward.

## Disposition

Nothing is wired. The honest reading matches the money-path thesis and the
2026-09-27 exit replay: under the fair game, a state model can only pay if
its drift survives the day-level trend AND the cost; none does here. The
lever remains new information (a persistent state with psi >= ~1.2), not a new
combination of the current features. Re-run the report as era-9 accrues —
14 test days is thin, and the day count is the resolution.

What the check could not see: time-outs (16% of rows) are censored out of the
calibration metric (conditioning on resolution is an approximation for a
finite horizon); the chain step is the candidate event, not a clock; theta
averaging assumes a common sigma across states; the conservative
stop-checked-first intrabar rule (ml/labeling.triple_barrier) biases every
row toward its own stop when both barriers sit inside one bar.
