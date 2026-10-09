---
title: "Session 2026-09-29 — the directional-edge audit and a Markov-modulated Brownian state model, walk-forward: no state beats the fair game"
category: source
status: SETTLED-AS-OF-SNAPSHOT
summary: "Operator asked for the directional edges' formulas vs what they achieve, then a Markov chain combining them, Brownian theory, walk-forward, 'porcelain hands'. Per-feature screen: 11/68 pass CI+null (~3.4 expected), genuinely directional only venue_disloc_dir 0.414 and basis_dir 0.463. The state model (6 pre-registered specs x static/chain, 14 purged test days, 200-rep permutation null) loses to the driftless fair game out of sample in all 12 cells; the day LEVEL (per-day up-first share 0.005..0.962) dominates; only basis carries weak within-day rank info (AUC 0.533-0.558, not Bonferroni-clean, post-run metric); the chain dilutes short-lived states to the pooled drift. Nothing wired."
tags: [directional-edge, markov-chain, brownian-motion, first-passage, fair-game, walk-forward, permutation-null, basis, venue-dislocation, macro-hmm, era-9, research-only, cs-1]
sources: 1
updated: 2026-09-30
---

# Session 2026-09-29 — Markov-modulated Brownian edge, walk-forward

Raw: `raw/2026-09-29_markov_brownian_edge_walkforward.md` (verbatim stdout, snapshot-stamped).
Repo record: `docs/quant/2026-09-29_markov_brownian_edge_report.md`; code `ml/markov_edge.py`,
`scripts/markov_edge_report.py`, `tests/test_markov_edge.py` (37 tests, mutation 7/7 vs green control).
Framing: the operator's entry-fee / fair-game text, `raw/2026-09-26_operator_entry_fee_optimal_stopping_framing.md`,
and [[synthesis/the-money-path-thesis|the money-path thesis]].

> [!warning] CORRECTED 2026-10-01 — within-day AUC biased for path-related scores
> A pure random walk reads within-(day, asset) AUC 0.39 for the 1h return: rows in one day share one path.
> The within-day permutation null used here is too narrow for such scores. The basis / hmm_x_basis within-day
> readings (0.533-0.562) are AT RISK in proportion to their correlation with past returns - not refuted, not
> confirmed. The power test (path-independent planted edges) stands. See [[sources/session-20261001-new-information-and-conviction]].

## The model (why these formulas)

- Drifted BM hits +a before -b with `P = (e^{theta b}-1)/(e^{theta b}-e^{-theta a})`, `theta = 2mu/sigma^2`.
  Rewritten dimensionless: `psi = theta(a+b)`, `r = b/(a+b)`. The bot's bracket is always 4:3
  (r = 3/7 long, 4/7 short in market terms), so ONE psi per state serves every asset.
- psi = 0 is the fair game: P = r, and EV = -cost < 0, so the model never trades without drift.
- Break-even at the era-9 label geometry (pt ~181, sl ~136 bps, cost ~45 bps): p* = 0.571
  vs driftless 0.4286 -> needs psi ~ +1.2.
- Markov chain over states per asset; the drift a trade feels = psi averaged over the chain's
  occupancy across the driftless expected exit time `E[tau] = (a/sigma)(b/sigma)` bars (~48).

> [!warning] CORRECTED 2026-09-30 — test-side censoring
> Rows land only when labels resolve, so days younger than day_end + 36 h were censored toward fast outcomes; run 1 scored two (09-28, 09-29; 497 rows).
> Fixed (`mature_day`, as-of = corpus mtime) and re-run on the SAME snapshot: 12 mature days, 4,355 rows. Conclusions STAND: all 12 calibration gains negative
> (-0.029..-0.055); basis within-day AUC 0.543 [0.515, 0.572] (was 0.533), hmm_x_basis 0.562 (was 0.558), still not Bonferroni-clean;
> NEW: chained dislocation ranks BACKWARDS OOS (AUC 0.439 / 0.437, p=0.005). Raw: `raw/2026-09-30_markov_brownian_edge_walkforward_corrected.md`.
> Forward-registered `operator` spec (regime x vol, 6 states) scores from 2026-09-30; first mature day 2026-10-02T12:00Z. The numbers below are run 1's.

## Findings, run 1 (snapshot 2026-09-29T20:10:58Z; superseded numerically by the callout above)

1. All 12 cells: calibration gain vs driftless NEGATIVE (-0.023..-0.047 nats/row). [K raw]
2. Day level dominates — per-day up-first share 0.005..0.962; pooled drift fitted on the past
   swings -3.4..+0.8. Effective n = days (14 tested), not rows (4,852). [K debug run, this session]
3. Within-day rank info only in basis: AUC 0.533 [0.508, 0.560] (basis static), 0.558
   [0.514, 0.603] (hmm_x_basis static, p at the 1/201 floor). Metric added AFTER run 1 — flagged.
4. Chain dilutes: basis states stay ~0.4/step vs a ~48-step hold -> pooled drift; chain variants
   take 9-106 of 4,852 rows. HMM regimes persist (0.92-0.98) but carry no OOS drift.
5. In-sample "venue dislocation negative -> long, +17 bps" is walk-forward HARMFUL
   (disloc chain uplift -40.3 bps [-87.5, -2.2]).

## Disposition

SAFE, research only; no cohort fork; nothing in the order path imports it (pinned).
The lever is still NEW INFORMATION with persistent drift, not recombination of current features.
Owed: re-run as era-9 accrues (resolution = day count).
