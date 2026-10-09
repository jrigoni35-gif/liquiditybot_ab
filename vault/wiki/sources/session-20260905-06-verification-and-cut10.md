---
title: Session 2026-09-05/06 — signal factory, verified-findings sweep, Simons pass, cut #10
category: source
status: SETTLED; cut #11 LIVE (runner pid 7808, 2026-09-07T14:58:47Z, era-8 accruing; era-7 closed at 2 trips)
date: 2026-09-06
commits: 41146368, 1e2996f4, 21ae38f5, a5acfe2d, b638da67 (PUSHED); 4bb6f3ae, b6ab541a + the E2/E3 record (closeout, pushed at session end)
raw:
  - raw/research/2026-09-05_simons_transferability.md
  - raw/research/2026-09-05_simons_transferability_full_workflow_output.json
  - raw/research/2026-09-05_self_referential_verification_research.md
  - raw/research/2026-09-05_self_referential_verification_ecosystems.md
  - raw/audits/2026-09-05_deferred_findings_verification.json
repo_records:
  - docs/quant/2026-09-05_signal_factory_readout.md
  - docs/quant/2026-09-05_verified_findings_batch.md
  - docs/quant/2026-09-06_verified_findings_batch2.md
  - docs/quant/2026-09-06_cut10_boundary_adjudication.md
  - docs/quant/2026-09-06_e2_horizon_curve_and_per_era_gross.md
tags: [signal-factory, cost-bar, no-skill, verification-by-execution, cut-10, era-7, simons, fee-truth, mutation]
---

# What this session established

## 1. The signal factory read out; the champion has no measurable skill
`scripts/signal_factory.py` — 1,454 pre-registered candidates, scored on the
DIRECTION channel against `null_calibration`'s **measured** chance rate (0.10,
not nominal 0.05). 217 raw flags vs 145.4 expected from noise → 54 BH
survivors, mostly one marginal re-flagged through its interactions. Two
replicated out-of-sample (`fv_edge_bps`, `basis_dir`) **and still died on the
cost bar** — flipped-rule P(pt) 0.4851, CI upper 0.5373 < 0.5714 cost-floor
break-even. The cost screen now lives IN the tool; ledger frozen at schema v1.

Champion re-derived on ONE population (deployed `evaluate_and_select`, 12,425
OOF rows, 18 day-blocks): Brier 0.248069 vs 0.247458 constant, skill −0.0025,
CI [−0.0029, +0.0043] — **indistinguishable from a constant**. Corrects
[[synthesis/the-money-path-thesis]]'s fair-coin baseline (0.25 → honest
0.2475 at base rate 0.4496); strengthens the thesis. A first read of "2.72%
worse" divided the OOF subset by the full-matrix `class_balance` — two
populations, one ratio ([[concepts/the-method]] 7a).

## 2. Verification by execution, then the fixes
24 deferred critical/high findings verified against the RUNNING system (17
agents, each reproduced then adversarially refuted): 16 CONFIRMED+SAFE, 7
CONFIRMED+BOUNDARY, long REFUTED list incl. agents' own hypotheses killed by
their own mutations. 15 SAFE fixed across two commits; mutation **26/26 RED**
after corrections, catching: two pins that tested helpers not call sites
(finding #11's shape, reproduced inside the commit fixing it), a fix
swallowed by the very `except` it addressed (`risk/protocols.py` had no
logger), a test that WAS the defect (`test_benchmarks_against_the_verified_
tier` pinned the invented 40/80), and a self-referential grep needle.

## 3. Simons / Renaissance — the inversion
`IR = IC·√BR` on IC ≈ 0: every scaling property multiplies a number ≤ 0.
Maker rebates **structurally unavailable** (Kraken maker floors at 0.0). The
whole fee ladder cannot close the gap (venue floor at 572× volume → −61.6% vs
−69.1% required). "Long horizons solved cost" **refuted by the PSI record five
times**. Two findings aimed at us: paper fees restate `config.json` to the
digit; **gross sign is unreconciled across eras** — whether the book has
positive gross is OPEN. Fabricated Gârleanu–Pedersen quotation found in the
corpus. See [[raw/research/2026-09-05_simons_transferability]].

## 4. Cut #10 — the verified-defects boundary (era-7)
Operator-approved one reset. B1 never-delivered books read FRESH; B2
`est_fee_bps` absent-default 0.0; B3 NaN equity → multiplier 1.0 silently
(`max(nan,0)` keeps NaN); B4 execution feed an unchecked injectable (a
non-Kraken submit PLACED); B5 dedup disarmed on an unloadable cache; B6
capacity constant 18.3 → **43.7** (two derivations agree), cap 1200 → 1800.
**E1** (cheapest experiment): 22/38 is NOT a published row; binding at
$17,482 is **20/35**; derived bar 0.6772 → 0.6642. **[CORRECTED 2026-09-08:
both premises were the venue's LEGACY ladder, read from a JSON endpoint that
now serves no fee arrays. On the current ladder (fee page raw text 09-08;
operator's 08-29 screenshot) 22/38 IS Tier 3 at $10K and 20/35 is Tier 4 at
$25K or $50k assets-on-platform — E1 booked a row the account did not hold
on 08-29 (under-states by 5 bps at $17,482); the operator's 09-08 reading
is Tier 5 on $69,652.65 (AoP $822.24) → 15/30, so as of 09-08 it OVER-states
by 10 bps. The tier rolls with real trading. Re-booking is docketed
FEE-4. See [[concepts/the-method]] #13 and
`docs/quant/2026-09-08_fee_ladder_correction.md`.]** **92% of fees on
exit+hedge legs at taker rates, 60% taker mix** — the next cost question is
execution. **NOT bundled on evidence:** ALGO-5 (adjudicated *do not arm*
09-02; proposed for the bundle on a stale docket read and retracted), GB-1
(refuted at HEAD by the 07-30 arm cost floor, effective arm 1.27%). No second
reset queued; CONC-1 next. Stamp `10-a5acfe2d` names the record commit.

## 6. Cut #11 — the COMMIT configuration (2026-09-07, era-8) — LIVE
Operator objective, verbatim: *"Make it do things that would make it have to
either end with a positive or negative PnL."* Three zero-makers that are not
the model removed, nothing else touched: **hedger OFF** (40% of all fees; a
hedged bet cannot end clearly ±), **universe → PAXG/ETH/BTC/LINK** (alts the
measured loss channel; skimmer OFF or it re-widens at boot), **probe ticket
floor $15 → $60** (`size_scale` already at its 1.0 clamp). Under H0 the loss
GROWS to ~−$1.3/day — accepted knowingly. Read points: n=50 lean, n=100
verdict; STOP never reverts to the hedged 12-asset book. The design pass
(`wf_83900ef6-2d2`) recommended fewer trades instead; overridden on the
operator's objective, its universe cut kept. Record:
`docs/quant/2026-09-07_cut11_commit_adjudication.md`; stamp `11-6e584923`;
commits `6e584923` + `776dbd44`. Boot proof: `fees=20/35bps`, no
"universe widened" line, 5 majors positions resumed (straddling → excluded
from era-8 accrual by stamp purity).

## 7. Beta/alpha attribution — what the bot was hedging against (2026-09-07)

Operator question: *does the bot have a way to learn what it is hedging
against?* Answer by attribution — `scripts/beta_alpha_decomposition.py`
regresses each closed hedge-free trip's gross return on a crypto basket
(BTC+ETH+LINK minus the traded coin) over the same window. Slope = beta,
intercept = alpha (Jensen's). Record:
`docs/quant/2026-09-07_beta_alpha_attribution.md`; raw
`raw/quant/2026-09-07_beta_alpha_attribution.json`; refutation verdict
`raw/audits/2026-09-07_beta_alpha_refutation_verdict.md`.

**The instrument was wrong first, eight ways, all silent** — the cleanest
[[concepts/the-method]] instance this month: (D0) alpha = mean residual ≡ 0;
(D1) the 5m store ended 09-02 while fills ran to 09-07, so **22 trips were
dropped silently — the losing recent ones** (mean gross −52 bps, era-9 20 of
29); (D2) the anchor was the close of the bar CONTAINING the fill — a price
printed up to 5 min AFTER it — and **the pin named `no_look_ahead` asserted
that behaviour** (the 08-2026 "pin satisfied by a comment" shape, now "pin
satisfied by the defect it is named against"); (D3) day-block percentile CI
~2× anti-conservative at ≤ 15 days (P(≥1 of 10 per-asset CIs falsely
excludes 0) = 0.62); (D4) PAXG diluting the factor; (D5) one day = 47% of
Sxy; (D7) dead bootstrap helper, live inline copy; (D9, mine) "clear" rule
that every negative interval passed. Fixes: refreshed store + counted drops
with their mean gross; prior-closed-bar anchor + injection pin; CR1
cluster-robust t (exact table — scipy is not in the venv) + exact 2^G
sign-flip p; strict crypto basket; n_eff + leave-one-day-out; one bootstrap;
`alpha_clear()`. 12 pins, mutation 8/8 red.

**Readout (329/329 trips priced, 45 days, n_eff 9.3):** beta **0.894**
[CR1 0.64, 1.15], R² 0.385; alpha **−5.1 bps** [boot −20.3, +10.7] [CR1
−19.0, +8.9], p 0.49 — zero on every route and both baskets (1.07 / −2.5
with PAXG). **Only clear alphas are NEGATIVE:** era-9 −54 bps/trip [−83,
−22], p 0.008, 8/8 days; ARB −88 on two of three routes. LINK +43 was the
look-ahead (p 0.018 → 0.26). Second route, the 159 hedges as practised:
gross −2.5 bps, fees 80.0, net **−82.5 bps**, median hold **0.1 min**,
147/159 under a minute — hedging was pure cost. Market explains ~39% of
trip variance (BTC 96%, ETH 65%, alts 5–36%).

**Read:** the bets were the market; nothing coin-specific to hedge around;
the negative alphas are selection/exit losses a hedge would have KEPT
(strips the market part, keeps the residual). Corroborates cut #11 (hedger
off, alts out) and points at the pre-named TP-width lever, never at
re-hedging. Power ±15 bps/trip pooled. Owed: re-run at era-8 n=50/100.

## 5. Currency — resolved 2026-09-06/07
- **Runner restarted onto cut #10** at 22:10:41Z (pid 13512; boot line
  `fees=20/35bps`, resumed 2 positions). **Era-7 is accruing.** The first
  deploy tick read "already up to date" because the dev box IS the checkout —
  no fast-forward, no soft-stop; the stop was issued via `ControlChannel`
  (the auto_update mechanism) and the supervisor relaunched.
- Learning panel `fill_hazard` wall 300→900 s (measured 159 s foreground).
- Give-back WARN reads the effective arm; `momentum_bear_max` states the
  runtime's value (the literal −0.34 EXCLUDED −1/3 by rounding; the runtime
  had repaired it every boot). `4bb6f3ae`.
- **Per-era gross**: era-7 positive (CI clears 0, optimistic); **era-9 spans
  zero** (n=29). **E2**: oracle-MFE median clears fees within a day on every
  core pair — the Simons pass's null did NOT obtain; the 240 bps TP barrier
  sits above the 36 h median MFE on the majors (geometry; ALGO-5; filed).
  **E3**: null holds at n=48; harness coverage-starved (452/500 skipped).
  `docs/quant/2026-09-06_e2_horizon_curve_and_per_era_gross.md`.
- Bridge branch: merge gated and reverted on bandit B404/B603; retained.
- **47 findings verified 09-07** (wf_b1d423d4): 36 SAFE, 9 BOUNDARY, ~14
  refuted, 4 already fixed, 16 cannot-determine; 7 SAFE fixed (batch 3);
  register `docs/quant/2026-09-07_verified_findings_register_47.md`.
- Still open: 29 SAFE docketed with evidence (h16 era-blind cost tools, h63
  diode harness dark, h13 fee fallbacks in execution modules, h53
  snapshot size…); 9 BOUNDARY incl. five null/saturated SMC features
  (model-side, frozen); B7, QT-1 behind CONC-1; parquet-backed E3 re-run.
  **Done 09-07 10:09Z:** fills.csv migrated to 18 cols (1,254 rows, backup
  `preschema_1788775767`), runner relaunched pid 21840 on batch-3 code; LLVM
  on user PATH, diode tests 8 passed.

# Pages amended this session
[[synthesis/the-money-path-thesis]] (baseline callout), [[concepts/tautological-instrument]]
(fifth specimen class), [[log]] (three entries).
