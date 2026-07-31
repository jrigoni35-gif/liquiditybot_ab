# 2026-07-31 — the live-label era deadlock (why learning is stuck on logistic)

**Status:** root-caused, verified end-to-end, FIX NOT YET CHOSEN (debate).
**Severity:** this is the standing "slow learning" root cause. SPB-R's
extra probe volume currently converts to **zero** usable live evidence.

## The chain (every link verified on the live corpus, 2026-07-31)

1. `ml.label_mode = "triple_barrier"` (since 2026-07-26). Barrier
   geometry is cost-floored: PT >= `label_pt_cost_mult` (4.0) x
   `label_round_trip_cost_pct` (0.5%) = **2.00% floor**; shipped rows
   carry `pt_frac ~= 0.0278` (**2.78%**), `max_bars=96` (8h).
2. **The barriers are unreachable by this strategy.** Over the last 60
   live closes (`postmortem_summary.csv`): median MFE **+0.156%**, p90
   **+0.423%**, **max +0.723%**. Trades reaching the 2.00% PT: **0/60**.
   Trades reaching the -2.10% SL: **0/60**. Realized outcome clusters at
   **-0.697% median** ~= the round-trip cost stack.
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
