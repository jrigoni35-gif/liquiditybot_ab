# Game-theoretic edge loop — is there SOLID directional edge in the rows we have?

**Date:** 2026-08-29 · **Class:** SAFE (pure measurement / synthesis; reads
`outputs/signal_history.csv` + `outputs/fills.csv` + read-only candle store via
`ml.corpus`; writes only docs; no decision path, feature, veto, sizing rule,
fill sim, fee booking or order lifecycle touched or imported — model freeze
2026-08-10 respected, no new signal invented) · **Repo HEAD:** `98f6d32b` ·
**Interpreter:** `./.venv/Scripts/python.exe`.

## The frame (why this loop exists, and what it is NOT)

This loop **VALIDATES existing signals for SOLID edge; it does not fabricate
edge.** The model freeze (2026-08-10) forbids new features/families/
meta-labeling, so the question is never "what new pattern can we mine" — that
is the exact overfitting the OF-battery / PBO / DSR exist to catch on
n_eff-collapsed rows. The question is the separation one: **of the signals,
vetoes and styles we ALREADY ship, which carry edge that survives adversarial
scrutiny at real cost, within era, at effective-n — and which are noise?**

A loop that returns many "edges" from n_eff≈30 rows is overfitting and must be
distrusted. The honest prior for this book is **thin**, and the honest finding
is allowed to be a NULL. A NULL that survives is the valuable, shippable
result: it keeps SANITY from admitting on noise.

## The one-line answer

**SOLID directional edge in the rows we have: NONE. `solid_edge_set = {}`.**

Four candidate families were run to the like-for-like bar (contemporaneous,
same-window, within `label_era`, realized-label gross via
`ml.corpus.gross_ret_pct`, net of the operator's **real Tier-3 ≈60 bps**
round-trip, de Prado effective-n). Every one reads NULL or is CONFOUNDED. The
one robust, regime-invariant fact this session has is **EXECUTION-side and it
points the wrong way** — it is a cost, not an edge.

## What was tested, and how each died

Ground truth: real Tier-3 = 22/38 = **~60 bps** round-trip (operator
screenshot), NOT the config 120 bps. Eras never pooled. All figures [K] off the
corpus snapshots named per family.

### 1. The vetoes — SZ-021 regime/crisis, SZ-022 direction, SZ-023 p_win bar

Control-arm question: do vetoed candidates underperform admitted ones at 60 bps,
within era, at effective-n? **No veto survives as a net edge.** Strongest honest
statement is a NULL:

- **SZ-021 (crisis block):** at the only admissible comparator
  (contemporaneous, same-window, like-for-like `triple_barrier_h432`) the
  separation is **+0.7 pp [z_eff +0.03, p≈0.98]**; the blocked cohort's own net
  expectancy at cost is **+0.10%/trip [t_eff +0.14]** — equally consistent with
  harmless, mildly-helpful, and useless; NOT with a demonstrated edge.
- The seductive "anti-selective at significance" glass read (vetoed 0.509
  [0.439,0.580] vs baseline 0.265, n=2,032/n_eff 189) is an **ARTIFACT of a
  frozen era-disjoint baseline**: SZ-021's rows are 100% `triple_barrier_h432`,
  **zero `label_era` overlap** with the 2026-07-20 blank-disp baseline (84%
  legacy). `gate_efficacy_report.py` now refuses it
  (`comparison=CONFOUNDED_BASELINE`, injection-pinned
  `test_disjoint_label_era_yields_confounded_verdict`). This is the
  era-confound recurrence the-method warns about.
- **SZ-023 (p_win bar):** pooled sits AT baseline (0.278, n_eff 1,721) but is
  ALSO confounded (0.8% weighted era overlap).
- **SZ-022 (direction block):** no standalone measured counterfactual exists.

**Persistence: none, and there is a structural reason.** SZ-021's trigger is a
rank within a rolling 250-return window (fires ~7% by construction on
stationary noise) measuring co-movement **atypicality, not stress** — inverted
vs its crash-guard purpose (12 assets crashing together reads 80 and never
fires; one asset decoupling blacks out the book — the TURB-1 defect). A
public-shaped, mechanically-firing regime label carries no informational moat;
any apparent uplift is **compositional** (being long in a rising tape), which
arbitrages away the instant the tape turns. No rational counterparty leaves a
simple regime/direction/p_win veto standing as directional edge, and the data
confirms the market does not.

### 2. THALES footprint detectors — th_grid / th_metronome / th_clockwork / th_stopzone / th_barclose

Outcome-shading signals, measured on the realized-label route
(`ml.corpus.gross_ret_pct`, net 60 bps, within era, de Prado n_eff). Corpus
snapshot `outputs/signal_history.csv` **2026-08-29T20:57:13Z, 19,353 rows;
9,913 closed** (both legs priced). **No detector survives as a SOLID edge.**

- Dominant era (`triple_barrier_h432`, n=8,998 closed): fired-vs-not contrast is
  NULL for four of five — th_stopzone z_eff **+0.05**, th_barclose **−0.26**,
  th_grid **−0.46** (and th_grid is 95%-on → no real contrast arm),
  th_metronome **UNESTIMABLE** (53 fired, n_eff 19.5 — confirms the pre-flagged
  n≈4 family).
- Only non-null thread — **th_clockwork:** fired mean gross **+0.619%** vs
  **+0.140%** not-fired (contrast +0.479%), trim-robust, spread over 15 assets
  (10/15 positive). But **z_eff is only +1.44** (not significant), it **FLIPS
  sign** in the other era (`triple_barrier`: −0.178% fired vs +0.015%), and net
  of 60 bps the fired subset is **breakeven (+0.019%, z_level +0.07)**.
- Across 5 detectors × 2 eras = **10 contrasts, max |z_eff| = 1.44** — exactly
  the expected max of 10 N(0,1) draws. **Nothing clears chance.**

**Persistence: none that holds.** A footprint edge persists only if the target
algo keeps running its pattern un-adapted; nothing evidences th_clockwork's
periodic-bot counterparty is still live or static, and the era sign-flip is the
signature of a NON-persisting pattern. The road is also closed structurally:
model freeze forbids adding/reweighting these features, the shade channel is
frozen at `shadow` (`out.mult=1.0`) with an unresolved p_win double-count
hazard, and a ~$18 median ticket cannot pay 134 bps true fees. This is the
realized-label complement to the 2026-08-29 horizon sweep's forward-price null
and the ladder analysis' inert-shade-channel finding.

### 3. Execution styles — maker/taker, probe/conviction, hold-duration (realized fills)

463–464 dedup'd closed trips, `outputs/fills.csv` snapshot mtime
**2026-08-28T14:48:36Z**, cross-checked vs live-entered `signal_history.csv`
rows and `docs/quant/2026-08-29_fee_anatomy.md`. **NONE survives as a positive
edge — and the handed "median clears the rake at 60 bps, loss is fat-tail"
framing is REFUTED by its own instrument.**

- Re-derived two ways: **median realized gross = −0.0282% [K]** (does not clear
  ZERO, let alone a rake); mean gross **+0.0254%** but day-clustered **t=0.39
  (G=36)** — indistinguishable from zero, sign flips to −0.044% on dropping 5 of
  464 trades.
- Mean > median ⇒ skew is **RIGHT** (fat WINNER tail, payoff ratio 1.444): the
  typical trade is a small loser and the book loses **not to a fat left tail but
  to fees deterministically subtracted from a zero-edge distribution.** net =
  gross(~0) − fee in every fee world (mean net **−0.575%** at 60 bps, **−1.17%**
  at 120 bps); break-even is IMPOSSIBLE at payoff 1.444 for any fee above ~zero.
- Only solid, persistent execution fact is a **COST DISADVANTAGE:** exits are
  **96.3% taker**, 95.3% of fee dollars are taker, and that share is
  **STRUCTURAL** (stops must be allowed out per invariant #5; hedge unwinds never
  gated). Capturable maker-conversion prize ≈ **$24 over the whole
  40-day/463-trip history (~$0.05/trip)** — two orders of magnitude below the
  ~−1%/trip bleed. Probes net −1.05%/trip at true fees; conviction cohort is
  **n=5**.

**Persistence: the honest inversion.** No "pay-less-to-trade" edge to harvest,
because the bot is a liquidity TAKER on 96% of exit notional by construction — a
directional predictor, not a two-sided maker. What IS structurally persistent is
the DISADVANTAGE: the taker-exit cost is self-imposed by hard invariants (a
rational counterparty need do nothing), and the fee tier is pinned (dry-run books
Tier-1 permanently at $0 venue volume; the real account is Tier-3, neither
reducible by trading at this scale). This corroborates the sibling
`2026-08-29_game_theory_adverse_selection.md`: a symmetric efficient-market
null (entry alpha −7.6 bps n_eff 80 t=−0.72, sign flips across eras), **not**
adverse selection — the loss is the rake, and the rake is 2.5–4.4× a typical
holding-window move.

### 4. Regime conditioning — 5 one-hot regimes × side, within era, at 60 bps

**None survives.** The apparent regime-conditioned edge is the **long/short beta
confound**, not edge. At 60 bps only crisis-long (+0.43% net) and bear-long
(+0.14% net) look positive, and both are **pure long-side beta of the single
08-20 melt-up window**. Removing market direction (per-asset
(long_mean+short_mean)/2), every regime's drift-neutral gross edge sits within
**±0.11% of zero** — all far below the 0.60% round-trip cost, so net
drift-neutral is **−0.50% to −0.82% in ALL five regimes.** No regime×side cell
is solid.

**Persistence: none — both prongs fail.** The drift-removed edge is already ~0
gross (nothing to persist); the positive cells are the long side of a rising
tape (crisis rows are exactly the operator-adjudicated 08-20 melt-up OUTLIER,
historical N=1). And the conditioning variable is not reliably identifiable —
the crisis/turbulence trigger is the TURB-1 defect (fires ~7% on stationary
noise, measures co-movement not stress). A 36h directional bet inside a "crisis"
label is priced beta, not alpha.

## The answer to the operator

**Is there SOLID edge in the rows we have? No — `solid_edge_set = {}`.** Across
four families and both live eras, the maximum effective-n-corrected separation
is th_clockwork at z_eff +1.44 (chance-level for 10 draws), and it flips sign
across eras and clears the real rake by ~0.02%. Everything else is NULL or
CONFOUNDED (era-disjoint baselines the hardened `gate_efficacy_report.py`
correctly refuses).

**This is the correct answer, not a failure to find one.** The loop VALIDATES
edge; there is none here to validate. It is the realized-label, control-arm
convergence of the whole session: models lose to null on OOF Brier; horizon
sweep UNDECIDABLE; gross ≈ 0 pooled; and the *only* robust, regime-invariant
thread is EXECUTION-side (SZ-030 cost-aware rejection held 0.060 [0.040,0.089]
through the 08-20 melt-up while every admission-side number moved with the tape)
— and even that clean read was walked back to PARTIAL_OVERLAP (weighted 0.159)
under the hardened guard. The durable edge, such as it is, is **not a veto and
not a signal — it is the cost rake itself, and it currently bleeds us.**

## How this loop couples to the other planes (the "neural network")

This edge-validation loop is one plane in a coupled system; its output gates the
others rather than acting alone:

- **→ SANITY (admission gate):** it feeds the gate **only edge that SURVIVED
  adversarial scrutiny.** With `solid_edge_set = {}`, the honest signal it hands
  forward is *admit on cost-discipline, not on directional conviction* — which
  is precisely cut #8's probe-dominated 0.8335 entry bar (conviction entries
  effectively stop). SANITY admitting on any of the four NULL families would be
  admitting on noise.
- **⊣ EXECUTION (converts what it is handed):** this loop **bounds** what
  EXECUTION can convert. There is no directional edge for EXECUTION to harvest;
  the capturable maker-conversion prize is ~$0.05/trip, two orders below the
  bleed. So EXECUTION's job is not "convert edge better" but "stop paying the
  rake" — and the only route to a *persistent positive* execution edge is
  architectural (run the present Avellaneda–Stoikov engine two-sided to EARN the
  spread), which is a **COHORT-RESETTING** change, out of scope for this SAFE
  loop and owed to operator adjudication.
- **← LEARNING (kept honest):** by refusing to promote noise to "edge," the loop
  keeps LEARNING from emitting **false-precise probabilities.** A NULL reported
  as a NULL prevents the retrain loop (which continues by design) from
  over-fitting confidence to n_eff≈30 rows. The effective-n and era-confound
  deflations apply to the claims we like at the same rate as the claims we doubt.

The coupling is the point: a plane that manufactured edge would corrupt all
three downstream. This loop's discipline IS the signal.

## Honest caveats (ruthless)

- **This loop cannot manufacture edge that isn't there.** If the rows carry no
  separable directional signal at real cost, the correct output is `{}` — and
  mining harder (more cuts, more conditioning cells, more horizons) only inflates
  the multiple-comparisons surface the OF-battery exists to punish. A loop that
  returned many edges from these n_eff would be the overfit failure mode, not a
  success.
- **The most likely durable edge is EXECUTION-side, not directional** — and if
  so, "more solid edge" comes from the **execution plane** (cheaper trading,
  tail-control, two-sided making), **not from mining the rows harder.** That is a
  different plane's work and a COHORT-RESETTING architecture decision, not a
  signal to be separated from noise in the existing data.
- **Scope of the green:** figures are within-era, at real 60 bps, at de Prado
  n_eff; nominal Wilson is 12–16× too tight per the stream audit. Cross-era
  pooling is refused by construction. `fills.csv` pools ≥5 execution eras (the
  `fee_anatomy` caveat carries here). Snapshots are as-of their stamped mtimes;
  the live runner is RUNNING and its files are read-only. No forward-price claim
  is made from a sampled tail.
- **What this did NOT see:** it cannot rule out edge in signals we do not yet
  ship (model freeze forbids adding them anyway), nor edge that only appears at
  larger n than era-5 has accrued. It measures the rows we have; the era-5 gate
  (`scripts/cohort_eval.py`) remains the forward authority and is untouched.

---

*Complements: `docs/quant/2026-08-29_game_theory_adverse_selection.md`
(symmetric null, not picked off), `2026-08-29_fee_anatomy.md` (gross≈0, rake
dominates), `2026-08-29_horizon_edge_sweep.md` (forward-price null),
`2026-08-29_fee_dominance_diagnosis.md` (spread too tight to earn maker rebate).
Sibling concurrent work — `2026-08-29_tail_control_sim_registration.md` and
`2026-08-29_profit_balance_three_planes.md` — NOT touched by this doc.*
