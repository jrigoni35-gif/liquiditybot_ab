# Boundary #5 adjudication package — fee truth (owed 88), prepared at n=48

**Status: STAGED, NOT APPLIED.** The gate is 2 closes from its pre-registered
n=50 readout. Owed-88's standing adjudication is BATCH AT READOUT; minting
boundary #5 before the readout discards 48 accrued closes for nothing. This
package exists so the cut can land the moment the readout prints, with every
consequence measured in advance instead of discovered after.

Apply with `python scripts/boundary5_stage.py --apply` (dry-run by default),
then restart. The stamp mints `exec_era` boundary #5 automatically via the
normal deploy path.

## What the readout will say (measured 2026-08-25, n=48)

Exact per-trip repricing via `scripts/fee_reprice.py` (reproduction gate
passed; each fill priced by its own `post_only` flag):

| constant | mean net/trade | band | t on effective n=19.1 |
|---|---|---|---|
| booked 25/40 | **−0.049%** | INCONCLUSIVE | −0.05 |
| true 40/80 | **−0.631%** | INCONCLUSIVE | −0.99 |

Gross +0.6205% (SE 0.3694 nominal, 0.586 on effective n). 95% CI on net at
true fees: [−1.73, +0.57].

**The earlier controversy is gone.** At n=40 the constant flipped the band
(booked CONTINUE / true INCONCLUSIVE). The last 8 closes pulled booked net
under zero: both constants now read INCONCLUSIVE. The fee correction no
longer changes the verdict band — it changes the magnitude, the EV gate, the
entry bar, and the geometry. That removes the strongest argument for delay.

**Power, stated plainly:** a *significant* CONTINUE at true fees (t≥2 on
effective-n SE) needs gross ≥ **2.37%/trade**. Observed gross runs
+0.62–0.73%. The next era needs either ~3–4× the gross edge or materially
wider geometry (ALGO-5) — there is no constant to tune that manufactures
this.

## The package (keys, verified against `core/config_guard.validate`)

| key | from | to | why |
|---|---|---|---|
| `pretrade.maker_fee_bps` / `taker_fee_bps` | 25 / 40 | **40 / 80** | first-party Kraken Tier 1, fetched 2026-08-22, `cost_attribution.py:82-90` |
| `order_manager.maker_fee_bps` / `taker_fee_bps` | 25 / 40 | **40 / 80** | booking must match pricing |
| `profit_taking.est_fee_bps` | 40 | **80** | BE floor = 2·fee+buffer must clear TRUE exit cost |
| `ml.label_round_trip_cost_pct` | 0.5 | **1.2** | maker-in/taker-out; labels minted at true cost |
| `ml.exploration.p_win` | 0.70 | **0.85** | see FATAL below |

Guard result, measured by running `validate()` on the candidate:
* true fees alone → **1 FATAL** (`exploration.p_win 0.700 ≤ breakeven 0.833`)
  plus the probe-clearance WARN.
* with `p_win 0.85` → **0 FATAL**. Two standing WARNs remain and are
  consequences, not bugs (below).

## The three consequences the operator is choosing, not just a constant

**1. The derived entry bar rises to 0.8335.** `p_bar_mode=derived` pins the
sizer's p(win) bar at net-Kelly breakeven: `payoff_ratio_from_config` gives
b_net 0.4488 → **0.1998** at true cost, breakeven 0.690 → **0.8335**. Model
confidences run 0.60–0.77. **Conviction entries effectively stop; the book
becomes probe-only** until geometry widens or the edge improves. This is not
a malfunction — it is the strategy's true position at true costs, and the
gate reporting it honestly. `exploration.p_win=0.85` is a synthetic sizing
ticket (its documented role), not a claim probes win 85%.

**2. Label geometry doubles if the cost floor's intent is kept.** The pt
floor is `pt_cost_mult(4.0) × cost`: at 0.5% → 2% targets; at 1.2% → **4.8%
targets**, labeled and traded identically (the helper is shared with the
live bracket engine). Fewer resolutions inside h432, longer holds, bigger
wins — the ALGO-5 territory that owed-88 already batches with this boundary.
The alternative (cutting `pt_cost_mult` to ~1.67 to keep 2% targets) keeps
today's behavior but concedes costs at 60% of a gross win — the floor's
25%-intent broken knowingly. **Package keeps 4.0 (intent preserved); dissent
by editing the stager before --apply.**

**3. The give-back ratchet arms inside fee noise** (WARN: arm at 0.6% vs
166bps BE buffer). Left as shipped — exits are never gated — but the ratchet
will lock shares of moves that are fee noise at true cost; retune candidate
for the next era, not this cut.

## What this package deliberately does NOT do

* Does not touch the pre-registered gate, its bands, or `cohort_eval.py`.
* Does not apply anything at stage time — `--apply` + restart is the cut.
* Does not relabel history. Rows before 2026-08-24 kept only their sign
  (the destroyed-magnitude defect, fixed in `8a9cc087`); rows since carry
  `label_ret_pct` and CAN be repriced. The old corpus cannot, ever.

## Provenance

Fee truth: first-party fetch 2026-08-22 (`cost_attribution.py:82-90`), fills
mix ×1.979 measured (`fee_reprice.py`, reproduction-gated). Breakevens: the
real `payoff_ratio_from_config`, this session. Guard sweep: the real
`config_guard.validate`, this session. Cohort numbers: `cohort_eval.py` +
`fee_reprice.py` at n=48, 2026-08-25. Re-derive all of it with those tools;
none of these numbers should be quoted from this file after the cut.
