# PROFIT BALANCE — the three planes, one division of labor

**Date:** 2026-08-29 · **Class:** SAFE (design synthesis — reads code + the
2026-08-29 fee/game-theory/stream docs, writes THIS doc only; **no config,
decision, gate, exit-geometry, fill-sim, fee-booking, order-lifecycle, or
model change; mints NO execution era**) · **Repo HEAD:** `fb184e20` (== main
at dispatch) · **Discipline:** this is the BALANCED PLAN + bundle spec for the
operator's single ARM decision — **not the act.** The operator has said do NOT
mint an era unilaterally; nothing here does.

Authorities integrated (numbers CITED, not re-derived):
`2026-08-29_fee_tier_correction_adjudication.md`,
`2026-08-29_fee_anatomy.md`, `2026-08-29_game_theory_adverse_selection.md`,
`2026-08-29_stream_data_quality_audit.md`,
`2026-08-29_fee_dominance_diagnosis.md`,
`2026-08-29_tail_control_sim_registration.md` (results PENDING — deferred to,
not pre-empted). Provenance tags: [K] read · [I] inferred · [UNKNOWN].

---

## THE BALANCE (headline)

**EXECUTION is the profit DRIVER. SANITY is its intake valve. LEARNING is a
support instrument. The model is not, and cannot be, the profit source.**

The established thesis fixes each plane's job precisely. The bot has **no
measurable directional edge** — entry alpha is indistinguishable from zero,
sign-flips era-to-era, and the models lose to the analytic null on OOF Brier
(`fee_dominance_diagnosis.md` Phase-3 Mode-1, `game_theory_adverse_selection.md`
§1) — and the model side is **FROZEN** (2026-08-10, CLAUDE.md). So profit
cannot come from *picking better*. It can only come from the one asymmetry the
fee correction exposed: at the account's **real** Kraken Tier-3 fees
(maker 22 / taker 38 ≈ **60 bps** round-trip, operator screenshot 2026-08-29),
the **median** era-4 trip grosses **+72.6 bps** and clears the rake (net **+12.6
bps** at the median), while the **mean** is dragged negative by a heavy left
tail (gross sd ~246 bps, left-skew — `tail_control_sim_registration.md` §0
citing `fee_tier_correction_adjudication.md` §3 nuance 1). **The median already
wins; the tail is what loses.**

That single fact assigns the labor:

- **EXECUTION owns the prize.** Only exit geometry converts a median that
  clears the rake into realized dollars — by cutting the fat left-tail losers
  before they overwhelm the median (ALGO-5 stop widths + the PT-060 time-decay
  ladder) and by amortizing the fixed rake over the right-tail winners
  (give-back ratchet / hold-winners). The precise size of that prize is being
  measured by the running tail-control sim and is deferred to it.
- **SANITY feeds EXECUTION the right population.** Its job is to admit the
  median-clearing trades and veto only what honestly hurts — calibrated to the
  fee EXECUTION actually PAYS (~60 bps), not a phantom, and never suppressing
  on false precision. In a no-edge rake game the dominant strategy is "play
  less, only where a move can clear the rake" — but that is correct **only at
  the true rake**; at a phantom 2× rake it degrades into "don't play the trades
  you would win."
- **LEARNING supports with honest probabilities.** Its one profit contribution
  is *negative-avoidance*: by attaching its own imprecision (n_eff, not nominal
  n) it stops SANITY from over-trusting a point confidence and mis-admitting.
  It de-stales calibration as the base rate moves — that is real and the
  retrain loop earns it — but it does not and will not manufacture edge.

**Where the planes pull AGAINST each other today — one constant, three
detunings.** The entire mistune is a single fee constant applied in two places.
EXECUTION's fee booking (`profit_taking.est_fee_bps=80`; pretrade
`est_cost_bps` ≈ 120 bps round-trip) is read by (a) the pretrade EV cost stack,
which drives SANITY's derived entry bar to **0.8335**, and (b) EXECUTION's own
give-back cost-floor and break-even buffer. One doubled constant therefore
pulls the planes apart *in the same direction*:

- **SANITY over-suppresses the exact trades EXECUTION exists to work on.** The
  derived bar `p_bar_base = 1/(1+b_net)` (`risk/position_sizer.py:191-193`);
  b_net collapses **0.4766 → 0.1998** at 40/80 vs real 22/38, moving the bar
  **0.6772 → 0.8335** (double-derived, R1==R2, [K]
  `fee_tier_correction_adjudication.md` §2, lines 103-104). At 40/80 the bar
  sits **above the entire live model-confidence band 0.60–0.77**, so conviction
  entries stop by construction and the book goes probe-only (HANDOFF cut-#8
  consequence #1). The gate is starving the driver of its population.
- **EXECUTION simultaneously disarms the geometry that would convert those same
  trades.** At booked ~120 bps the give-back ratchet arms at `cost_pct/(1-frac)`
  = 1.2/0.6 = **2.0%** — above the honest mover envelope (MFE p90 = 0.72%,
  config `_arm_doc`, n=55) — so GB-1 is effectively inert
  (`profit_tiers.py:611-613`, [K]). The break-even floor buffer computes
  (2·80+6) = **166 bps** instead of the real-taker (2·38+6) = **82 bps**
  (`profit_tiers.py:685,218`, [K]), so a winner peaking in the 82–166 bps band
  — the median band — gets no break-even lock.
- **SANITY over-trusts LEARNING beyond its n_eff.** The bar is a HARD threshold
  applied to `ml/meta_model.p_win` as a POINT estimate, with
  `p_bar_edge_margin` shipping **0.0** (`position_sizer.py:190`, [K]). But that
  probability is per-style noise: n_eff-collapsed **12–16.5×** below nominal
  (`stream_data_quality_audit.md` F1) and beta-confounded (F2 — the "long edge
  R²=0.75" is the sign that was true for one melt-up week). A hard bar on a
  false-precision input mis-admits and mis-rejects on both sides.

They cannot self-detect this because decision-side and booking-side read the
**same** constant — the loop-alignment finding (`2026-08-22_loop_alignment_audit.md`,
HANDOFF LOOP ALIGNMENT). Correcting the anchor to the real ~60 bps **re-couples**
all three: SANITY admits the median-clearing trades (bar 0.6772, back inside
the band), EXECUTION protects them (give-back arm 1.0%, BE floor 82 bps), and
LEARNING's honest imprecision keeps SANITY from over-trusting the confidence it
now compares against.

**The coupling that makes this ONE adjudication, not several.** b_net — hence
the bar — is derived from the stop geometry (`position_sizer.py` payoff from
`stop_loss_pct`). So a wider ALGO-5 stop changes b_net, which changes the bar by
the same arithmetic. **Tuning exit geometry silently re-breaks the entry bar
unless both move in one boundary.** That is why the fee correction, the bar, the
label round-trip cost, the ALGO-5 tail-control geometry, and the give-back
re-arm must be minted **together** — the cut-#8 "full bundle" pattern — or the
loop tears itself again.

---

## TRAJECTORY (ordered; each step class-tagged AS SHIPPED)

**SAFE-now items ship immediately and independently. They make the bot
TRUTHFUL and build the instruments the era-mint bundle needs to be armed
responsibly. None of them alters which orders are placed or how they fill.**

### Phase A — SAFE-now (ship freely, no era)

1. **[SAFE · LEARNING] n_eff-honest probability grading.** Home a shared
   `mean_uniqueness`/`n_eff` helper in `ml/corpus.py` (stdlib-legal:
   uniqueness-integral math, no polars/numpy — fits the engine-scope
   dependency gate) as the authority the `scripts/gate_truth_report.py:109`
   fast-lane mirrors; add a **per-execution-style** cut (side/regime/THALES/
   probe) to `gate_efficacy_report.py` behind its existing `neff()`/`_stat()`
   effective-n Wilson. **Never render a nominal-n CI.** Pin in
   `tests/test_corpus_accessor.py`. *Why:* per-style probabilities are
   optimistic 12–16.5× (`stream_data_quality_audit.md` F1, audit remediation
   #1); a nominal CI "crisis 0.528 [0.507,0.549]" is ~12× too tight and
   actually straddles 0.5. This is the honesty SANITY must consume before its
   bar can trust a confidence.

2. **[SAFE · LEARNING] beta-confound correction in per-style reads.** Per-style
   gross reads compare each style against a **contemporaneous, direction-matched**
   baseline — reuse the `ERA_OVERLAP_*` machinery `gate_efficacy_report.py`
   already runs; constrain gross estimation to the h432 era via
   `ml.corpus.read_rows(era=...)`; exclude pre-2026-08-04 rows (no gross
   outcome — never impute). *Why:* the corpus's biggest, straightest signal is
   **market beta masquerading as edge** and it sign-flips quarter-to-quarter
   (F2). Prevents LEARNING from feeding SANITY a false directional bias.

3. **[SAFE · LEARNING] confidence-shading effective-n telemetry.** Report each
   `th_*` shading channel's n_eff separation so the operator can SEE which
   confidence inputs cannot clear their own interval near the bar
   (`stream_data_quality_audit.md` F3: th_metronome n_eff 3.1 UNESTIMABLE,
   th_clockwork n_eff 22.3 noise). **Measurement only.** The tempting "prune
   the dead channels" is a FEATURE change and is FORBIDDEN by the 2026-08-10
   freeze — name it, do not do it.

4. **[SAFE · EXECUTION] exit-attribution report.** Build a per-close report:
   MAE, MFE-at-close, give-back-armed?, exit `reason_code`, maker/taker,
   realized net **at real (60 bps) vs booked (120 bps) fees**. *Why:* nothing
   currently reports whether the plane's levers fire — this shows GB-1 is dead
   at booked fees and gives ALGO-5 / the tail-sim the fat-tail-vs-median
   decomposition they need. **Register any new `outputs/` path in
   `tests/conftest.py::_REDIRECTED_PATH_ATTRS` in the same commit** (10 known
   leak instances — do not become #11).

5. **[SAFE · EXECUTION/SANITY] give-back + BE buffer recomputed at real fees as
   a REPORT.** Publish, without changing config, what the give-back arm (2.0% →
   1.0%) and the BE buffer (166 bps → 82 bps) *would* be at 22/38, alongside
   the mover envelope (MFE p50 0.30 / p75 0.45 / p90 0.72%). This is the
   evidence the operator reads before arming the bundle; it touches no
   decision.

6. **[SAFE · SANITY] REG-8 v2 Phase-0 observability.** Turbulence into
   `status.json`, silent-stale-hold fix, config_guard coverage — the SAFE half
   of the crisis-gate dissolution (`2026-08-22_REG8_crisis_predicate_algorithm.md`).
   The predicate/veto-geometry change itself is COHORT-RESETTING (Phase B).

7. **[SAFE · deferred-to] tail-control sim result.** The running sim
   (`tail_control_sim_registration.md`, results PENDING — not yet in this
   clone) returns the left-tail prize: ALGO-5 stop width + decay schedule, and
   whether non-urgent protective exits can rest maker-first. **This is the
   gating input for Phase B** — do not hand-fit the geometry; take it from the
   sim. Its verdict NAMES which geometry becomes decidable; it does not decide.

### Phase B — ERA-MINT bundle (COHORT-RESETTING · operator ARM only · adjudicate as ONE)

*Inadmissible mid-era. Do not ship any piece piecemeal — each alters b_net, the
bar, or fills, and they are arithmetically coupled. Arm together or not at all.*

8. The fee-truth + geometry bundle (spec in ERA_MINT_BUNDLE below), armed after
   Phase A instruments and the tail-sim result are in hand.

### Phase C — after the bundle's era reads out (measure-first, still gated)

9. **[measure-first · SANITY] CTRL-2 live in-era veto comparator.** Feed
   `gate_efficacy_report` its second, era-current baseline arm from the
   control-arm minority rows (schema 95, `CONTROL_ARM_FRACTION` 5%, already
   WRITTEN and never read). The era-current arm must clear `ERA_OVERLAP_MAJORITY`
   by construction and route through the two-vocabulary verdict function
   (`gate_efficacy_report.py:228-237`) or it reintroduces the F1 inversion
   `0084c16d` killed. Needs ~usable n=30 live rows (~0.85–1.6 d). *Why:* the
   only route out of the universal CONFOUNDED_BASELINE state — without it SANITY
   can never show a veto earns its keep for profit. Consumer build is SAFE; the
   *decision* to act on its output is not.

10. **[measure-first · SANITY] LS-2 uncertainty-aware bar.** Carry an n_eff-aware
    margin on the bar (honest widening when the per-style posterior is thin)
    instead of `p_bar_edge_margin=0.0`. Spec-on-paper + measurement are SAFE;
    **wiring the term into the sizer is COHORT-RESETTING** (changes which trades
    clear) — belongs to a later boundary, not this one.

11. **[measure-first · LEARNING] corpus observability of the profit plane.**
    Persist the fill's maker/taker (`post_only`) disposition at the
    `ml/history.py::_append_row` choke point, bookkeeping-only — but this is a
    **write-path schema rotation (2026-07-11 incident class), COHORT-RESETTING**,
    its own adjudication + conftest leak-registration. Until then LEARNING reads
    live edge via `net_pnl_usd` **explicitly labelled booked/understated**
    (FEE-1), never as venue truth.

---

## ERA_MINT_BUNDLE — the exact coherent set for the operator's single ARM

*Mint the era ONCE, coherently. Every item moves b_net, the bar, or fills;
config_guard's fee↔b_net↔breakeven↔p_win loop (`config_guard.py:3377-3394`)
FATALs if they move apart — which is the proof they are one decision.*

| # | change | from → to | plane | authority |
|---|---|---|---|---|
| B1 | pretrade + order_manager fee booking, moved TOGETHER (mismatch FATALs) | 40/80 → **22/38 bps** | EXEC→SANITY | operator screenshot; `fee_tier_correction_adjudication.md` §2 |
| B2 | `allow_sub_floor_fees` (22/38 is legitimately below `KRAKEN_SPOT_FLOOR`; **do NOT move the floor tripwire**) | false → **true** | EXEC | §2 |
| B3 | derived entry bar (follows B1 by arithmetic, not a free knob) | 0.8335 → **0.6772** | SANITY | `position_sizer.py:191-193`, R1==R2 [K] |
| B4 | `ml.label_round_trip_cost_pct` | 1.2 → **0.6%** | LEARNING | §2 |
| B5 | `exploration.p_win` stays clean at real fees (0.85 ≫ 0.6772, no FATAL) — **verify, do not re-cut** | 0.85 (unchanged) | SANITY | §2 line 140-141 |
| B6 | **ALGO-5** unconditional MAE-based left-tail stop + time-decay ladder (fires on the never-favorable trade WITHOUT the 40h PT-060 leash); width + schedule **from the tail-sim, not hand-fit** | new geometry | EXEC | CLAUDE.md pre-named; `tail_control_sim_registration.md` |
| B7 | **GB-1** give-back cost-floor re-anchored to real round-trip (arm 2.0% → **1.0%**); recognize the amortization band is structurally thin (arm 1.0% still > mover p90 0.72%) — value is in left-tail control, not arm-tuning | 2.0% → 1.0% | EXEC | `profit_tiers.py:611-613`; DOCKET GB-1 |
| B8 | break-even buffer (follows B1: `2·est_fee_bps+be_buffer`) | 166 → **82 bps** | EXEC | `profit_tiers.py:685,218` [K] |
| B9 | **arm OM-080** read-only `TradeVolume` so the tier is MEASURED not ASSUMED — turns the anchor [I]→[K] and the next tier drift into an alarm | n=0 → measured | EXEC | `order_manager.py:767`; DOCKET FEE-3 |
| B10 | **REG-8 v2** predicate change: DELETE the turbulence clause (predicates 2→1), route turbulence → `shrinkage` governor, breadth+absolute-stress → `RiskProtocolStack` (zero new gates) | dissolve crisis gate | SANITY | `2026-08-22_REG8_crisis_predicate_algorithm.md`; TURB-1 |

**Bundling note:** B1–B5 are the FEE-1/FEE-2 pair (already docketed, SHIPPED-at-cut-#8
now being *corrected downward* to the real tier). B6–B8 are the ALGO-5 + GB-1
geometry pair the DOCKET already pre-names for one adjudication. B9 makes the
anchor measured. B10 (REG-8 v2) removes a defective, anti-profit veto (crisis
block costs +0.7pp vs a fair control, `2026-08-22_crisis_block_synthesis.md`).
All ten share the arithmetic coupling; splitting them re-tears the loop. This
is the operator's ONE ARM.

---

## HONEST CAVEAT (ruthless)

**This balance makes the bot TRUTHFUL and gives the median edge a chance to
survive the tail. It does NOT invent edge the model does not have.**

- The fee correction removes a **confidently-negative config artifact** (a
  phantom 2× rake) and buys an honest readout. It does **not** flip era-4 to a
  winner: gross decayed **118 → 41 bps** as the cohort completed, so at real 60
  bps the NET point estimate stays **negative at n=61**, and the CI still spans
  zero — **n_eff 25.83, P(net≤0) ≈ 0.733** (`fee_tier_correction_adjudication.md`).
  "The median clears the rake" is a statement about the *median trip*, not about
  *the account's realized P&L*, which the left tail still owns.

- The whole prize is **contingent on the tail-control sim** (results PENDING).
  If the left tail is **gap-through-dominated** — losers that jump past any stop
  before it can fire — then ALGO-5 cannot cut them, GB-1's amortization band is
  structurally thin anyway (median 72.6 bps barely clears 60 bps rake), and
  **even this fully-coherent balance nets ~zero.** The sim is the arbiter of
  whether the prize exists; do not arm the geometry (B6–B8) until it reports.

- **LEARNING will not save it.** The model is edge-refuted on OOF Brier and
  frozen. Every roadmap item that expects the model to find edge (new families,
  features, meta-labeling) is both refuted and freeze-forbidden — spending
  governance budget on the plane that provably cannot pay.

- **At $800 / Tier-1 / liquid-Kraken scale, the deliverable may remain the
  machinery, not the P&L** (`fee_dominance_diagnosis.md` Phase-4.5). Median
  ticket ~$18 sits on an unbeatable fee floor (HANDOFF WHY-1). The honest
  outcome of this balance may be *a bot that is finally telling the truth about
  a game it cannot beat at this size* — which is itself the correct result to
  ship, because the alternative is a bot losing confidently on a fee it does not
  pay.

**What this plan could NOT see:** the tail shape (deferred to the running sim);
whether real fills rest maker-first at an acceptable adverse-selection cost
(B6/exit-leg question, sim-gated); and whether any veto earns its keep — every
current grade reads CONFOUNDED_BASELINE / PARTIAL_OVERLAP until CTRL-2's live
comparator accrues (weighted era overlap ≤ 0.159 today, HANDOFF REG-6 CAVEAT).
A green here is only as big as its corpus, and the corpus is n_eff-collapsed.
