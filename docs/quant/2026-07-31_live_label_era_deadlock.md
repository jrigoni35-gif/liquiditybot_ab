# 2026-07-31 — the live-label era deadlock (why learning is stuck on logistic)

**Status:** root-caused, verified end-to-end, FIX NOT YET CHOSEN (debate).
**Severity:** this is the standing "slow learning" root cause. SPB-R's
extra probe volume currently converts to **zero** usable live evidence.

## The chain (every link verified on the live corpus, 2026-07-31)

1. `ml.label_mode = "triple_barrier"` (since 2026-07-26). Barrier
   geometry is cost-floored: PT >= `label_pt_cost_mult` (4.0) x
   `label_round_trip_cost_pct` (0.5%) = **2.00% floor**; shipped rows
   carry `pt_frac ~= 0.0278` (**2.78%**), `max_bars=96` (8h).
2. ~~**The barriers are unreachable by this strategy.**~~ **RETRACTED —
   see the CORRECTION section below.** The barriers ARE reachable; live
   positions are simply closed ~3x earlier than the label's horizon.
   (Original, wrong reasoning: over the last 60 live closes median MFE
   was +0.156%, max +0.723%, 0/60 reaching either leg — measured over the
   ACTUAL short holding window, not the label's 96-bar horizon, which is
   the comparison that matters.)
3. `_finalize_position` stamps `barrier = close_reason if close_reason in
   ("tb_pt","tb_sl","tb_time") else "realized"`. Since no barrier is ever
   touched, and the overlays (PT-060 36-bar no-progress scratch at 3h,
   give-back ratchet, trail) close the position long before the 96-bar
   (8h) vertical, **every live close lands `realized`**.
   Corpus: 256 live rows, `tb_*` = **0**, `realized` = 209, blank = 47.
4. A `realized` live row cannot belong to the `triple_barrier` label era.
   Era census: `triple_barrier` 2,132 rows — **all candidate, zero live**.
   All 251 clean live rows sit in `exit_sim` (204) + `legacy` (47).
5. Era exclusion (ML-081) is **armed and ACTIVE** (2,132 new-era rows >=
   `min_new_era_rows` 150) and therefore excludes 4,859 rows — **including
   all 251 live labels**. Load with `era_cfg`: `rows 2132, live_clean 0`.
6. Evidence gate consumes exactly that number
   (`overfit_check.py:198`, `main.py:5685` both read `live_clean`):
   `admissible_families(0, ...) -> ['logistic']`. The gbt / blend / mlp /
   adaptive_gbt rungs are unreachable **forever** on this path, because
   step 2 guarantees step 3 guarantees step 5.

## Consequences

- The bot cannot graduate past the linear baseline no matter how many
  probes it buys. **SPB-R makes the bleed worse, not the learning better**:
  every admitted probe pays ~0.65% round trip and yields an
  era-excluded row.
- `live_clean = 0` on the dashboard was NOT a display bug and NOT the
  give-back arming issue fixed in 381e870.
- **Correction to the record:** the give-back cost floor (381e870) was
  reported here as having "unblocked the tb_* label stream". It did not.
  It fixed a real, separate defect (arming inside the cost band), but the
  tb_* stream was never gated on give-back — it is gated on barrier
  reachability (step 2).

## No data was lost

Era exclusion is a **load-time view**, not a destructive filter. All 251
live rows are intact in `signal_history.csv` and become usable the moment
the era/label policy changes. The tuition already paid is recoverable as
evidence.

## Option space (for adjudication — NOT yet decided)

- **A. Live rows are era-exempt.** Era exclusion exists because the
  *simulated* label's meaning changed when the labeler changed; a live
  row's label ("did this trade net money") means the same thing in every
  era. Applies exclusion to candidates only. Cheapest, unlocks 251 rows
  immediately. Risk: live labels DO carry an implicit exit-policy era
  (a 3h scratch and an 8h bracket ride are different experiments).
- **B. Let bracket probes ride to the vertical.** Suppress the early
  overlays for probe positions so they close `tb_time` and enter the
  current era legitimately. Produces era-valid live rows with real
  (not constant) labels. Costs: capital held up to 8h, and it partially
  reverts the PT-060 seniority fix.
- **C. Re-align the barriers to reachable distances.** Rejected on its
  face: labeling a "win" inside the cost stack is exactly the trap the
  P1 tier-1 cost floor closed. Only viable together with an entry-side
  change that makes >=2x-cost moves the target.
- **D. Entry selectivity (the profit answer, C7's conclusion).** The
  measured expected move is smaller than the 65bps round trip
  (1/60 trades expected to clear cost). Fixing the label plumbing does
  not create edge; only entering when a >=1.3% move is plausible does.

A and B are learning-plumbing fixes; D is the profit fix. They are not
mutually exclusive and should be adjudicated on that basis.

---

## CORRECTION (same day, adversarial review of this document)

The skeptic arm of the debate refuted step 2 above, and re-measurement on
the corpus confirms the refutation. Corrected facts:

**C1 — the barriers are REACHABLE.** Of 2,137 candidate rows carrying a
`tb_*` barrier: **PT 17.9%** (383), **SL 34.5%** (738), **TIME 47.5%**
(1,016). Over half of simulated positions touch a horizontal barrier.
The original MFE argument compared excursions over the ACTUAL (short)
holding window against a barrier defined over a 96-bar horizon — an
apples-to-oranges comparison. Retracted.

**C2 — the real mechanism is a HORIZON mismatch, not barrier distance.**
Median hold: **live 13.6 bars vs candidate 43.2 bars**; share reaching
the 96-bar vertical: **live 9.3% vs candidate 33.8%**. Live positions are
closed by exit overlays roughly 3x sooner than the label's own horizon,
so they neither touch a barrier nor reach the vertical -> `realized` ->
old era -> excluded. Steps 3-6 of the chain above stand unchanged; only
the *reason* live rows never carry a `tb_*` barrier is corrected.

**C3 — the strategy's simulated edge at this geometry is NEGATIVE.**
SL 34.5% vs PT 17.9% = the stop is hit **1.9x more often** than the
target. This is the most consequential number in the document and it is
not a plumbing defect: at the labeled geometry the strategy loses.

**C4 — live entries collapsed a week ago.** Entries/day from the audit:
07-20 27, 07-21 26, 07-22 87, 07-23 48, then **07-24 0**, 07-25 3,
07-26 8, 07-27 4, 07-28 5, 07-29 2, 07-30 4, 07-31 11. A ~90% collapse
beginning 07-24, coincident with the probe-throttle rollout (SZ-047
2,630 that day). The skeptic attributes the conviction-side share to
SZ-030 (net-Kelly f* <= 0) / SZ-023 (p below the derived bar) — the
entry bar pinned at net-Kelly breakeven 0.5635, which after 0.35
shrinkage needs raw p >= 0.598 from a model whose AUC is 0.586 on a
0.27 base rate. **Not independently verified here** (those codes do not
appear in the audit trail; they are gate-path counters) — verify before
acting on the attribution.

**C5 — unlocking the live rows would HURT, on measurement.** The
skeptic's in-process diagnostic: the tb-trained model scores the 251 live
rows at Brier **0.2124 vs 0.1393 for a base-rate-only constant** (worse
than predicting the mean), AUC 0.586, over-forecasting 1.94x; a
live-only model scores OOS AUC **0.4375** (worse than random). Option A
therefore fails on evidence, not on principle.

**Standing conclusion.** The label/era plumbing is a real deadlock and
worth fixing, but it is the *second* problem. The first is that the bot
has no demonstrated post-cost edge (C3) and has effectively stopped
trading (C4). Fixing the plumbing without C3/C4 would buy a faster path
to a better-measured loss.
