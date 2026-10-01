# 2026-10-01 — New-information screen, the within-day AUC bias, and conviction evidence for the 2-week hold (SAFE)

Operator: "Yes" (start the new-information screen + regulation research during
the hold) and "Let's also look at ways to derive new information for
conviction labels to help for the next 2 weeks." **Class: SAFE** - report
tools, tests, docs, one report bug fix. No decision-module change, no config
change, no cohort fork; the 2-week hold on `6709bbc2778d` stands.

## 1. New information: the signed trade tape

`scripts/info_screen.py` (pre-registered; 7 tape signals never tested before,
DIRECTION target only, decision-time cutoff; CS-1 `n=35372 = ... + scored=17869`).

- Within-day AUCs 0.44-0.48, contrarian, five CIs excluding 0.5; pooled AUCs
  ~0.49. The 09-01 edge-hunter screen graded with a pooled metric and could
  not have seen this.
- **Then the instrument failed its own audit.** Rows within one day share one
  price path, so a path-derived score is compared against other rows' futures:
  a pure random walk reads within-(day, asset) AUC **0.39** for the 1 h return.
  The within-day permutation null shuffles that structure away and is too
  narrow. Flow correlates +0.23 with the 30 min return; residualised on past
  5m/30m/1h returns it reads **0.485 [0.459, 0.506]** - mostly the return in
  disguise. Decision-time cutoff (bar open): 0.460 [0.435, 0.481], stable
  across halves.
- **The fair test - sign-flip null** (real 5m returns, random signs: real
  volatility clustering kept, direction destroyed; identical close-only
  procedure): past 1 h return real **0.2945** vs null 0.360 [0.324, 0.398];
  30 min **0.3332** vs 0.392 [0.366, 0.431]; one-sided p 0.016 (beyond all 60
  null runs). Real short-horizon reversal exists beyond the artifact, about
  0.06-0.07 AUC - in features the bot ALREADY has (`ret_*_dir`).
- **Economics, independently:** Kitron & Wengrowicz, arXiv:2608.21888
  (abstract read verbatim): 15 min crypto reversal in 90% of 183 Binance
  pairs, concentrated after taker flow, gross ~1.3 bp vs a 5 bp cost - "too
  small to clear benchmark spot capture costs". This bot's round trip is ~45
  bps. Real, and sub-cost.

**Rule earned:** for any score derived from the label's own price path, grade
against a sign-flip (or equivalent structure-preserving) null, never a
within-group permutation null. This puts the 2026-09-29/30 within-day AUC
readings at risk wherever the state correlates with past returns (callout on
`2026-09-29_markov_brownian_edge_report.md`).

## 2. Conviction evidence without waiting 6 months

A conviction entry is one whose OWN model p clears the sizer's net-break-even
bar (SZ-023 "p X below bar 0.63"); ~2 per week, so n=50 is ~6 months away.
Every candidate carries the same bracket a trade uses (1a, 2026-09-29), so the
question conviction needs answered can be read from candidates - if each is
scored by a model that never saw it.

`scripts/conviction_value_report.py`: the bot's own `evaluate_and_select`,
time-purged walk-forward, the SELECTED family's (blend) out-of-fold p on
20,675 of 24,813 training rows (mean OOF AUC 0.574); audit isolated to a temp
file.

| OOF p decile | win rate | 95% day-block CI | vs p* 0.564 |
|---|---|---|---|
| 1-6 | 0.33-0.39 | - | below |
| 7 | 0.474 | [0.395, 0.561] | below |
| 8 | 0.500 | [0.404, 0.600] | spans |
| 9 | 0.501 | [0.390, 0.597] | spans |
| 10 (p 0.74-0.95) | 0.420 | [0.270, 0.534] | below - from only **13 days** |

Top 5%: 0.450 over 6 days; top 1%: 0.594 over 5 days.

- The model ranks (win rate rises with p) but no decile clears break-even.
- **Its highest-confidence calls arrive in bursts on a handful of days** - they
  are regime calls. Conviction lives at the very top, so conviction's
  effective sample is DAYS, not trades: 50 conviction trades from 5 days are
  ~5 data points. Count high-confidence DAYS when reading conviction.

## 3. The forward instrument was broken - fixed

`scripts/shadow_policy_report.py` (shipped 2026-09-29) keyed candidate labels
on `candidate_id`; the real writer puts a candidate's id in `position_id`
(candidate_id is blank on candidate rows). 765 shadow rows, 391 labeled, all
read "unresolved" - the promotion rule could never fire. Its tests used
hand-built fixtures. Fixed; new pin writes through the REAL writers
(`HistoryStore._append_row`, `ShadowPolicyStore.log`) and fails on the old
join. First real read: `765 = unresolved 374 + undecided 265 + would-enter 31
+ would-skip 95`; would-enter mean -135.3 bps over **2 day-blocks** - a
direction, not a verdict.

## 4. Two-week plan (read-only checkpoints; no code)

| when | read | question |
|---|---|---|
| daily | `scripts/shadow_policy_report.py` | would-enter outcomes by DAY (the deployed model's own p at registration) |
| daily | `scripts/trip_explain.py` | each real conviction trip's market / asset / fee split |
| ~10-01..02 | `status.json` ml.monitor `drift_calibrated` | did the retrain write the drift null |
| 10-02 12:00Z | `scripts/markov_edge_report.py` | first mature day of the regime x vol forward spec - grade it against a structure-preserving null, per this record |
| 10-12 (n=50 lean) | `scripts/era_readout.py` + `conviction_value_report.py` | lean on cohort `6709bbc2778d`; are high-confidence DAYS above p*? |

## 5. Regulation (US)

`docs/research/regulation/` (README + US binding layer + 2025-2026
literature). Pre-live blockers: state of residence unknown (NY/WA/ME reported
excluded from Kraken); `region_max_leverage: 10` exceeds Kraken's PAXG cap of
5x (verified on Kraken's own page); venue liquidation at 40% sits outside the
exit ladder; NFA registration unchecked; CPA for 1099-DA.
