---
title: "Session 2026-08-26 — why it's still losing money: the era-4 dollar decomposition at readout (n=54, COST_BOUND) with same-day statistical validation"
category: source
status: SETTLED
summary: "SETTLED — the deep dive ran its own refuters the same day (bootstrap B=20k seed 7, ×1.58 concurrency deflation, confound checks) and the refuters DREW BLOOD: claim 5 (ticket-size fee floor) REFUTED, claim 3 (alt tail) demoted to POST-HOC, claim 6 amended twice. The era-4 gate crossed its pre-registered n=50 (54 entry-opened closes) and the readout arm is COST_BOUND: gross +$8.23, booked fees $6.87 → net +$1.36 booked, −$5.36 at the true ×1.979 fee anchor. The load-bearing split: conviction n=5 nets +2.132% booked / +1.463% true per trip; probe n=49 (91% of cohort) nets −0.392% booked / −1.052% true — probe gross (+0.283%/trip) sits STRUCTURALLY below the round trip it pays (0.65% booked, ~1.29% true), so the losses are fee-tuition on mispriced exploration, not alpha decay. Surviving spine after Bonferroni (5 claims, bar 0.01): the fee constant (arithmetic, conditional on FEE-3) and probe tuition at true fees (p≈0.001 raw, p≈0.027 deflated — clears 0.05, not 0.01). BTC/ETH/LINK +$4.56 on 18 trips carry the entire edge; DOGE/ARB/LTC/ADA/SUI −$3.67 on 27 — but the majors/alts grouping was chosen after seeing the data (deflated p≈0.08, do not act). Stops: 78% of the tb_sl channel's dollars are genuine adverse price movement AND 79% of losers (Wilson [60%,91%]) lose more than their own MAE — both true at once, the ~0.65% fee rides every loss. Effective n 21.5 of 54 (uniqueness 0.399). Verdict machinery vindicated: COST_BOUND is the instrument doing its job; the old postmortem gate independently printed STAND DOWN (−1.007% vs −1.0%). Everything sim-side; fee truth conditional on the unverified venue tier row (FEE-3). Re-derived by this filing at 2026-08-26T23:55:14Z: n=54, readout COST_BOUND, probe 49/5, eff-n 21.52 all reproduce."
tags: [session, era-4, cost-bound, readout, probe-tuition, fees, decomposition, bootstrap, money-path]
source_path: raw/quant/2026-08-26_why_losing_deep_dive.md
source_date: 2026-08
authors: [operator, "Claude session_01Vtimj57gP74wGjoo8dMxmD"]
ingested: 2026-08-26
sources: 1
updated: 2026-08-26
---

# Session 2026-08-26 — why it's still losing money (era-4 readout, n=54)

> [!note] **SETTLED, with per-claim dispositions inside.** This page is settled
> in the rule-21 sense — the measurement ran AND its refuters ran (same-day
> bootstrap validation, B=20k, seed 7) — and the refuters were not decorative:
> **claim 5 was refuted, claim 3 demoted, claim 6 amended twice.** Quote the
> per-claim verdict, never the page wholesale. Every dollar is
> **sim-side** of the [[concepts/paper-real-boundary|paper/real boundary]], the
> ×1.979 fee anchor is **conditional on the unverified venue tier row**
> (FEE-3, `docs/HANDOFF.md` — one read-only `TradeVolume` call settles it), and
> the numbers are as-of the readout moment — *"quote the tools, not this
> file, after more fills accrue"* is the document's own instruction.

**Operator question:** *"deep dive on why it's still losing money — what are we
doing wrong?"* Answered on live `outputs/fills.csv` at the moment the era-4
gate crossed its pre-registered n=50 (54 entry-opened closes). Repo artifact:
`docs/quant/2026-08-26_why_losing_deep_dive.md`, landed across three commits —
`e4577515` (the dive), `cb0a2461` (graded by its own reviewer), `5d5c4e40`
(exits paragraph graded). Snapshot: `raw/quant/2026-08-26_why_losing_deep_dive.md`.

## The one-sentence answer

**The strategy's real trades are profitable and its learning is not:** 91% of
the cohort is probe trades whose gross edge (+0.28%/trip) is smaller than the
round-trip cost (0.65% booked, ~1.29% true) — the book pays full fee-tuition on
ten trades for every one that can actually earn, in a fee world the config
understates by ×1.979, on $18 median tickets. **Tuition, not alpha decay.**

## The readout context — the gate FIRED

[[synthesis/the-money-path-thesis]]'s verdict instrument, pre-registered
2026-08-10 at era-4 n=1, crossed n=50 and named its arm: **COST_BOUND**
(gross > 0, net ≤ 0 at the honest fee constant). The old postmortem gate
independently printed **STAND DOWN** (−1.007% vs the −1.0% floor). Two gates,
one shape. This is the readout the model freeze has been waiting on since
2026-08-10 — per the moratorium's own law it **names which decision has become
decidable; it never decides.** All remedies are staged or docketed, **none
applied** — every one is cohort-resetting and the operator owns the cut.

## The decomposition (dollars, era-4 cohort, n=54)

**Totals:** gross **+$8.23**, booked fees **$6.87** → net **+$1.36** booked,
**−$5.36** at true fees. Fees consume 83% of gross at the configured schedule,
165% at the venue's real Tier-1 row.

| split | n | gross/trip | net (booked) | net (true ×1.979) |
|---|---:|---:|---:|---:|
| conviction | 5 | +2.815% | **+2.132%** | **+1.463%** |
| probe | 49 | +0.283% | **−0.392%** | **−1.052%** |

The five conviction entries clear the full true cost stack; the forty-nine
probes cannot clear even the booked one. This is the P3 finding of 2026-07-23
(probes 69% of closes, −$22.87 of −$31.68) still true a month later — the
throttles bounded the volume, not the shape. **Caveat stated on its face: n=5
is not evidence the conviction edge is real** (Wilson at n=5 spans nearly
everything); it is evidence the losses are not coming from there.

- **By asset:** BTC/ETH/LINK **+$4.56** net booked on 18 trips — the entire
  edge. DOGE/ARB/LTC/ADA/SUI **−$3.67** on 27 — half the trades, net-negative
  *before* fee truth. SUI/ADA gross-positive but fee-eaten.
- **By exit:** `tb_sl` −$6.23 on 14 (loss channel) · `tier trail` +$4.04 on 24
  (earn channel) · `tb_time` +$1.11 gross → −$0.21 net, fee churn on 19% of
  trips.
- **Ticket:** median entry notional **$18.00** (min $7.42) — Kraken minimums on
  an $800 book with concurrency caps force it.
- **Concurrency:** effective n **21.5 of 54** (uniqueness 0.399,
  [[concepts/average-uniqueness-and-ess]]) — 54 tuitions for ~21 independent
  lessons.

## What we are doing wrong, ranked — as graded by the same-day validation

1. **Booking half the true fee** (config 25/40 vs Tier-1 40/80): flips the
   cohort from +$1.36 to −$5.36. **REAL** — arithmetic on the measured ×1.979
   exact leg count (`fee_reprice.py`, dc107ce3), conditional on FEE-3. Fix
   fully staged as **boundary #5** (`scripts/boundary5_stage.py --apply`),
   inert, awaiting operator ([[synthesis/owed-measurements|owed 88]]).
2. **Probes trading at a mispriced tuition**: exploration EV was computed
   against the understated fee, so 49 trades ran whose gross ceiling was below
   their cost. **REAL at true fees** — probe net −1.051% CI[−1.65,−0.40],
   p≈0.001 raw, **p≈0.027 after ×1.58 concurrency deflation**; NOT yet
   resolvable at booked fees alone (p=0.11). Boundary #5's `p_win 0.85` +
   derived entry bar 0.8335 fixes the pricing; whether ~$0.19/trip true
   tuition is worth the labels then becomes a conscious learning budget.
3. **Trading the alt tail with real size**: majors−alts +1.69%
   CI[+0.20,+3.36], d=0.70 — but the grouping was chosen **after seeing the
   data** and the deflated p≈0.08. **POST-HOC** — pre-register the split for
   the next era; **do not act on this p** (owed 101).
4. **Geometry sized to the false fee world**: TRUE cost = 68% of the mean gross
   win, CI[48%,103%] — direction solid, magnitude uncertain by 2×. ALGO-5
   (pre-named boundary) widens targets; the power analysis independently
   demands gross ≥2.37%/trip for a significant CONTINUE at true fees.
5. ~~$18 tickets — the fee floor eats them alive~~ — **REFUTED, same-day.**
   Kraken fees are proportional: median booked round trip 65.2 bps on <$20
   tickets vs 64.8 bps on larger — **no fee floor penalizes small tickets** —
   and the small-vs-large net split is 100% confounded with probe/conviction
   (the ≥$20 trips ARE the 5 conviction trades). The real ticket-size issue is
   economic (absolute dollars too small to compound or buy labels quickly),
   not a per-trade loss mechanism. *A plausible mechanism stated without a
   measurement; the measurement refuted it.*

**Exits, amended twice:** grouping by exit reason selects on the outcome
(stopped trades lose by definition) — descriptive only, no causal content
(6). But composition CAN be measured: the pooled `tb_sl` loss is **78%
genuine adverse price movement, 22% fees** (6b) — so the dive's original
"cost, not stop placement" line was too strong — AND **19/24 joined losers
(79%, Wilson [60%,91%]) still lost more than the worst the price ever went
against them** (median excess +0.742%), because the ~0.65% fee rides on top of
every loss and MAE's poll-cadence sampling understates depth (6c). **Both are
true at once.** Timeout churn: n=10, mean net −0.624% CI[−1.06,−0.11], p=0.009
raw / ≈0.07 deflated — semi-mechanical (`tb_time` selects small-move trades,
so net ≈ −fee by construction); the actionable number is the **19% rate** (6d).

## The multiple-comparisons discipline

Five claims at α=0.05 ⇒ Bonferroni bar 0.01. Clearing it: the arithmetic
claims (1, 4's direction) and claim 2 at raw SE. Claim 2 after honest
concurrency deflation clears 0.05, not 0.01. **The ranking's spine — fees plus
probe tuition — stands; the asset and ticket stories were weaker than the
prose implied.** That sentence is the document grading itself, per
[[concepts/the-method]] stage 8.

## What is NOT wrong

The verdict machinery worked exactly as pre-registered. The system detected
that this configuration cannot pay its costs — **the instrument doing its job,
not the strategy mysteriously decaying. The market is allowed to be boring;
the apparatus was mispriced.**

## What this settles in the vault

- **[[sources/session-20260821-cost-stack-in-flight]]'s central question** —
  is the gross really positive and really eaten by costs? — is now answered
  **on the decision-grade population** (the pre-registered era-4 cohort,
  uniformly post-cut-#7, concurrency-deflated), which its refuters R1
  (pooling) and R2 (noise) demanded. The 434-position pooled numbers on that
  page remain unverified and are now **moot as evidence** — the clean-cohort
  route supersedes the need to verify them.
- **[[synthesis/live-readiness-verdict]] blocker (1)** (gate has not read out)
  is factually resolved: the gate crossed n=50 and the readout is COST_BOUND.
  **The verdict itself remains NOT READY** — blockers (3), (4), (5) stand
  untouched, and the readout's adjudication (boundary #5 batch + ALGO-5 +
  asset discipline) is the operator's.
- **[[synthesis/the-money-path-thesis]]'s corrected headline** ("gross
  indistinguishable from zero in both directions") moves on the era-4 cohort:
  gross is measured positive there, and net at the honest constant is what
  fails — the COST_BOUND arm by name.

## What this filing could not see

- All of it is **sim-side**: fills, fees, queue — simulated. The ×1.979 anchor
  multiplies a config constant by an exact measured leg count; the venue tier
  row itself is **unverified** (FEE-3 has never fired, OM-080 n_records=0).
- The **repo-side docket of 2026-08-22..08-25** (POWER-1/2, FEE-1/2/3, CONC-1,
  TRIALS-1, the boundary-#5 staging memo `docs/quant/2026-08-25_boundary5_adjudication.md`,
  four turbulence/walkforward docs of 08-22) is **not yet ingested into this
  vault** — this page cites those artifacts by repo path, not by vault page
  (owed 103).
- The conviction lane's edge is **directional only** (claim 2b: +2.52%/trip,
  d=1.03, CI[−0.59,+5.80], p=0.062; ~16 conviction trades needed for 80%
  power, have 5 — owed 102).

## Re-derivation by this filing (second route, contract clause e)

`./.venv/Scripts/python.exe scripts/cohort_eval.py --json`, read
**2026-08-26T23:55:14Z** (fills.csv is live; values as-of): era4 `n=54`,
`progress 54/50`, `readout "COST_BOUND"`, `gross_mean_pct +0.5172`,
`net_mean_pct −0.1579` (booked), `gross_win_rate 0.630`, `net_win_rate 0.519`;
composition `probe {1: 49, 0: 5}` (share 0.9074); `effective_n 21.523`,
`mean_uniqueness 0.3986`, `se_inflation 1.584`. All of the dive's cohort facts
reproduce. Homogeneity: **MIXED(both)** — 2 champions, 23 straddling trips, 2
label eras (28 exit_sim / 26 triple_barrier_h432) — the readout describes the
exploration constant plus a mixed cohort, exactly as
[[synthesis/live-readiness-verdict]] blocker (3) predicted it would.

## Provenance

`scripts/cohort_eval.py` (gate + effective n) · `scripts/cost_attribution.py`
(§1b dispersion, §2 schedules) · per-trip decomposition via
`scripts.cohort_eval.era4_trips` joined to `outputs/signal_history.csv` `probe`
column (54/54 joined) · fee truth ×1.979 from `fee_reprice.py`'s exact leg
count (`dc107ce3`) · bootstrap validation B=20k seed 7. All SAFE/report-only;
nothing changed any decision path. Repo HANDOFF row: **WHY-1**.

## Related

[[synthesis/the-money-path-thesis]] · [[synthesis/live-readiness-verdict]] ·
[[sources/session-20260821-cost-stack-in-flight]] ·
[[synthesis/comparability-boundaries]] · [[synthesis/owed-measurements]] ·
[[concepts/paper-real-boundary]] · [[concepts/average-uniqueness-and-ess]] ·
[[concepts/pooled-populations]] · [[concepts/the-method]] ·
[[concepts/cost-truth]] · [[concepts/self-flattery-gradient]]
