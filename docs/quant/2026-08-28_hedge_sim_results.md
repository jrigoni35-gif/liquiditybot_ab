# HEDGE-SIM results — 2026-08-28

Registration: docs/quant/2026-08-28_hedge_sim_registration.md (commit 67bdcdac). Computed after the registration was committed; nothing in it was amended.
Snapshot stamp (live files read at): 2026-08-29T00:48:21.486725+00:00
Sources: fills=C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\fills.csv audit=C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\audit.jsonl equity=C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\equity.csv

## REGISTERED VERDICT: **UNDECIDABLE-AT-N** (harness-failure arm)

The registered strict selector FAILED as registered it must: `leg sizes differ for cc0dc0fc-70f4-4085-88a7-bddadf1d9634: 6237.569616 vs 3471.269838`. The registration's assumption that every unwind is a single exit leg with reason 'hedge unwind' was contradicted by the data (split close). The registration is NOT amended. Everything below is the POST-HOC SUPPLEMENT (documented deviation: close = ALL exit legs of hedge-opened positions, aggregated), applying the otherwise-identical registered computation.

## SUPPLEMENTARY verdict (post-hoc selector): **HEDGE_COSTS_MORE**

- net_pnl(k=1, era8_truth) = -641.42 USD  [K: fills legs, truth fees]
- n_nominal = 159 round-trips; n_episodes = 4 (gap > 1800s); per-episode truth nets = [-625.5, -7.67, -2.08, -6.17]
- 95% CI: not computed (n_episodes < 5; registered all-sign rule used)

Scope (registered, binding): this verdict covers ONLY the recorded trigger window 2026-08-07T01:09:40.459000Z–2026-08-07T11:35:31.553000Z inclusive and sizing aggression on triggers that actually fired. The post-2026-08-07T11:31:02.005000Z suppression period is UNRECONSTRUCTABLE-FROM-HISTORY (no persisted exposure/correlation paths).

## Grid (net USD | delta vs deployed | fee drag)

| k | fee model | net_pnl | delta_vs_deployed | fee_drag | max_dd_delta |
|---|-----------|---------|-------------------|----------|--------------|
| 0.0 | booked | -0.00 | +325.70 | 0.00 | -312.66 |
| 0.5 | booked | -162.85 | +162.85 | 157.86 | -159.66 |
| 1.0 | booked | -325.70 | +0.00 | 315.72 | +0.00 |
| 1.5 | booked | -488.54 | -162.85 | 473.58 | +160.30 |
| 2.0 | booked | -651.39 | -325.70 | 631.44 | +321.87 |
| 0.0 | era8_truth | -0.00 | +325.70 | 0.00 | -312.66 |
| 0.5 | era8_truth | -320.71 | +4.99 | 315.72 | -6.42 |
| 1.0 | era8_truth | -641.42 | -315.72 | 631.44 | +311.89 |
| 1.5 | era8_truth | -962.13 | -636.43 | 947.17 | +632.60 |
| 2.0 | era8_truth | -1282.84 | -957.14 | 1262.89 | +953.31 |

Gross (price legs only): -9.97 USD. All metrics linear in k as registered; the grid is presentational.

## Verification blocks

- Booked per-leg fee rate (318 legs): min 40.00 / median 40.00 / max 40.00 bps  [K]
- Double-derive (fills booked net vs audit PT-061 net_usd): fills -325.70 vs audit -325.70; per-trip max |diff| 0.0000; missing in audit: 0; ok=True
- Last hedge open fill in audit (FULL-range scan, needle '"purpose": "hedge"'): 2026-08-07T11:31:02.005000Z  [K]

## Blocked opens (descriptive, NOT verdict-bearing)

- FW-040 hedge rejects: 60; total blocked notional 115465.36 USD; fee-only round-trip cost at era-8 truth 1847.45 USD. No PnL imputed (no unwind timing exists).

## Equity context (descriptive, NOT verdict-bearing)

- equity.csv full span: 2026-07-10T07:53:36Z = 25000.00 → 2026-08-29T00:48:10Z = 798.25 (as-of 2026-08-29T00:48:21.486725+00:00; capital sweeps/re-anchors, e.g. RP-042 2026-08-08, change the basis — span is NOT a PnL claim).
- Actual max drawdown in registered equity window 2026-08-07T00:00:00Z–2026-08-08T00:00:00Z: 326.75 USD.

## Analyst addendum (hand-written; generated content above untouched)

**Harness commits**: ed32fba7 (strict harness + pins), 074e4714
(post-hoc supplement selector + tied-close-ts fix). Regenerate with:
`./.venv/Scripts/python.exe scripts/hedge_sim.py --out <docs path>`.

**Reading the numbers.** Across every hedge round-trip the system has
ever completed with recorded sizes (159, all ADA/USD shorts, all inside
the 2026-08-07 churn incident), the price legs were a wash: gross
-9.97 USD on 39,460.30 USD of open notional (double-derived: Σ size×px
= 39,460.30 = Σ open fees/0.0040; both legs traded ≈ 78,930 USD =
truth fee drag 631.44/0.0080). The entire realized cost was
fees — 315.72 USD booked at 40 bps taker, 631.44 USD at era-8 truth
(80 bps taker, both legs). Hedging aggression on the triggers that
actually fired scales that loss linearly: k=2 at truth fees loses
1282.84 USD. All 4 episodes negative. This is the fee-truth restatement
of the already-settled churn diagnosis, now quantified at venue-true
cost — and it independently corroborates audit RP-042's "~USD303 of
simulated fees in ISO week 2026-W32" (our booked fee drag: 315.72 USD;
the ~4% difference plausibly RP-042's rounding/"~" and week-window
scope; both routes reported per contract).

**On the operator's hypothesis.** The hypothesis has two halves and the
record can only test one:

1. *"When the hedger did act, would acting bigger have paid?"* — NO,
   decisively (supplementary HEDGE_COSTS_MORE): the hedges captured no
   gross edge, so every extra unit of aggression was pure fee burn at
   double the booked rate under fee truth.
2. *"Is the post-churn discipline suppressing hedges that would now
   pay?"* — UNRECONSTRUCTABLE-FROM-HISTORY. Zero hedge opens since
   2026-08-07T11:31:02.005Z (full-range audit scan), and the per-cycle
   net-delta/correlation paths a counterfactual would need were never
   persisted. Nothing in this sim supports OR refutes that half. If it
   matters, the forward path is prospective telemetry (persist
   per-cycle net delta, corr, and would-have-hedged flags — SAFE
   class, docketable), not retrodiction.

**What the sim could not see** (beyond the scope clause): the 4 ARB/USD
hedge opens of 2026-07-15 (no recorded sizes, no traceable unwind —
excluded; ~USD 153.93 notional inferred as Σ audit fees_usd/0.0040 [I]); market impact of
counterfactual sizes (none modeled; linearity is exact only for the
recorded fills); the blocked FW-040 opens' PnL (fee floor alone would
have been 1,847.45 USD at truth on 115,465 USD notional); and any
hedge value realized as avoided drawdown OUTSIDE the registered equity
window.
