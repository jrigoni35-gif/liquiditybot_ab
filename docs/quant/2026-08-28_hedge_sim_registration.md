# HEDGE-SIM pre-registration — 2026-08-28

**Status: REGISTERED. Committed before any grid cell was computed.**
**Class: SAFE** (measurement only: reads history, writes a docs/ report;
no change to entry decisioning, sizing, stop/exit geometry, fill sim,
fee booking, or order lifecycle; `scripts/cohort_eval.py` untouched;
model freeze untouched). Era-5 accrual is unaffected: nothing here is
pooled with era-5 (or era-4 cohort) gate numbers.

## Hypothesis under test (operator, verbatim intent)

"The discipline is counteracting when it is beneficial to hedge
aggressively" — equity has been flat; would a more aggressive hedge
policy have netted positive AFTER true (era-8, Kraken Tier-1) fees?

## Inventory result the registration is built on (Phase-1, measured)

Reconstructable from on-disk history [K]:

- **159 complete ADA/USD short-hedge round-trips** — every hedge
  round-trip the system has ever completed with recorded sizes. Source:
  `outputs/fills.csv` (schema: ts, order_id, position_id, purpose,
  symbol, side, ordertype, post_only, attempt, fill_size, fill_price,
  arrival_ref, slip_bps, fees_delta_usd, remaining, reason, exec_era).
  Selectors (the named needles): open leg = rows with
  `purpose == "hedge"`; unwind leg = rows with `purpose == "exit"` and
  `reason` starting with `"hedge unwind"`; legs matched by
  `position_id`. All 159 opens and 159 unwinds lie in the inclusive
  window **ts 1786064980.459 (2026-08-07T01:09:40.459Z) through
  ts 1786102531.553 (2026-08-07T11:35:31.553Z)** — the ADA churn
  incident. All 318 legs have `post_only == 0` (marketable → taker).
- **Independent second route** for per-round-trip net PnL: audit
  `PT-061` close records (`outputs/audit.jsonl`, needle
  `"code": "PT-061"` with `close_reason` starting `"hedge unwind"`),
  `data.net_usd` keyed by `position_id`; 159 records,
  2026-08-07T01:09:45.935Z–11:35:31.687Z inclusive.
- **Third corroboration route** (order-of-magnitude only): audit
  `RP-042` (2026-08-08T18:13:10.778Z) cites "~USD303 of simulated fees
  in ISO week 2026-W32" for the churn class.
- **60 blocked hedge opens**: audit `FW-040` lines containing `hedge`
  (px and size in msg), inclusive window ts 1786067483.927
  (2026-08-07T01:51:23.927Z) through ts 1786067778.626
  (2026-08-07T01:56:18.626Z).
- **Equity path**: `outputs/equity.csv` (ts, equity, daily_pnl, ~15s
  cadence, first row ts 1783670016 = 2026-07-10T07:53:36Z; live file —
  results must snapshot-stamp the read).
- **Zero hedge opens after 2026-08-07T11:31:02.005Z** — established by
  a FULL-RANGE scan of `outputs/audit.jsonl` (69,582 lines at scan time
  2026-08-29T00:17Z read; needle `hedge` case-insensitive, then
  `data.purpose == "hedge"` on OM-000 fills), not a tail sample. The
  audit window scanned: ts 1783939764.991 (2026-07-13T10:49:24.991Z)
  through the snapshot read.

NOT reconstructable (register the gap, do not fake it):

- **Per-cycle net-delta / exposure paths** — persisted nowhere (state
  snapshots are current-only; telemetry export has no exposure
  history). Point values exist only inside fill `reason` strings at the
  moments hedges actually fired.
- **Correlation/beta EWMA paths** — same: point values in reason
  strings only.
- **Continuous price paths** — no OHLC store on disk for the window.
- Therefore **trigger-threshold-relaxation counterfactuals are OUT OF
  SCOPE**: what a laxer discipline (lower `min_hedge_correlation`,
  higher caps, no churn latch, no cooldown) would have opened at
  moments no hedge fired CANNOT be reconstructed, and neither can
  counterfactual unwind timing. The post-2026-08-07T11:31:02Z
  suppression period (churn guards active, zero opens) is registered
  **UNRECONSTRUCTABLE** — the verdict rule below is scoped away from
  it. Also excluded: **4 ARB/USD hedge open fills**
  (2026-07-15T03:32:56.006Z–04:11:59.610Z inclusive, audit OM-000):
  no recorded sizes, no traceable unwind; reported as a coverage gap,
  not simulated.

## Data window (inclusive, verbatim)

- Round-trip universe: `outputs/fills.csv` rows with
  `1786064980.459 <= ts <= 1786102531.553`, selected by the needles
  above. Expected n = 159 open legs + 159 unwind legs; the harness
  FAILS (does not degrade) if the pairing is not exactly 1:1 on
  `position_id` with equal leg sizes.
- Equity context / drawdown-delta window:
  `1786060800 <= ts <= 1786147200`
  (2026-08-07T00:00:00Z through 2026-08-08T00:00:00Z inclusive) —
  brackets the episode, deliberately ends before the 2026-08-08 RP-042
  budget re-anchor.

## Policy grid

Sizing multipliers applied to every recorded round-trip:
`k ∈ {0.0, 0.5, 1.0, 1.5, 2.0}` — k=1.0 is the deployed policy
(control); k=0.0 is "never hedge"; k>1 is "hedge more aggressively on
the same triggers". Crossed with fee model
`M ∈ {booked, era8_truth}`.

**Stated up front: every metric is LINEAR in k** (fills are simulated
limit crosses; no impact model exists to make it nonlinear; the FW-040
notional cap is deliberately NOT re-applied at k>1 — that overstates
what aggression could execute, and the overstatement is in the
hypothesis's favor). The grid is presentational; the sign of the k=1
truth-fee net decides everything the grid can decide. Writing the grid
anyway so the report is legible.

## Fee model = era-8 truth

- `booked`: `fees_delta_usd` exactly as recorded per leg.
- `era8_truth`: notional × **80 bps taker** per leg for `post_only==0`
  legs, 40 bps maker otherwise (Kraken Tier-1 40/80, cut #8,
  `exec_era 8-ca55e2ba`); applied to **both legs of every round-trip
  (open AND unwind)**. All 318 legs in the universe are `post_only==0`,
  so the truth model prices every leg at 80 bps.
- The harness must VERIFY (not assume) the booked rate by computing
  `fees_delta_usd / (fill_size × fill_price)` per leg and reporting the
  distribution; the Phase-1 samples read ≈40 bps.
- Re-pricing pre-era-8 executions at era-8 fees is an explicit
  counterfactual ("what these round-trips cost at venue-true fees"),
  never a restatement of what was booked.

## Metrics (all reported per grid cell (k, M))

1. `net_pnl(k,M) = k × (G − F_M)` where `G` = Σ gross price-leg PnL
   over the 159 round-trips (short: (open_px − close_px) × size),
   `F_M` = Σ fees both legs under M.
2. `delta_vs_deployed(k,M) = net_pnl(k,M) − net_pnl(1,booked)`.
3. `fee_drag(k,M) = k × F_M`.
4. `round_trips = 159` (count; k does not change it).
5. `max_drawdown_delta(k,M)`: counterfactual equity
   `eq_k,M(t) = eq(t) − CumNet_booked(t) + k × CumNet_M(t)` with the
   cumulative sums stepping at unwind timestamps; max drawdown over
   the equity window above, minus actual max drawdown over the same
   window.

Double-derivation requirement: `net_pnl(1,booked)` per round-trip from
fills legs MUST be compared against audit PT-061 `net_usd` per
`position_id`; both totals reported; disagreement > $0.01/trip or
> $1 aggregate is reported as a finding, not silently reconciled.

Blocked-opens descriptive block (NOT verdict-bearing): count = 60,
total blocked notional from the FW-040 msgs, and the fee-only cost
they would have added at era-8 truth (2 legs × 80 bps × notional).
No PnL is imputed to them (no unwind timing exists).

Equity-flatness context block (NOT verdict-bearing): equity.csv first/
last values over the full file with read timestamp, plus the RP-042
re-anchor caveat.

## Effective-n treatment

The 159 round-trips sit inside one 10.5-hour incident: they are NOT
independent. Episodes are defined by gaps > 1800 s between consecutive
open-leg timestamps; nominal n (159) and episode count are both
reported, and ALL sign/uncertainty statements operate on per-episode
nets. If episode count ≥ 5: 10,000-resample cluster bootstrap over
episodes, 95% CI on `net_pnl(1, era8_truth)`. If episode count < 5
(expected): no bootstrap is pretended; the verdict uses the
all-episode-sign rule below and the readout carries "n_episodes = <x>"
in the verdict line.

## Verdict rule (mapping computed outcomes → readout; fixed BEFORE
computation)

Let `N = net_pnl(1, era8_truth)` and `e_i` = per-episode nets under
era8_truth.

- **HEDGE_COSTS_MORE**: `N < 0` AND every `e_i ≤ 0` (or, if
  episode count ≥ 5, bootstrap 95% CI entirely < 0). By linearity
  every k > 1 is then strictly more negative: aggression on the
  recorded triggers loses more at true fees.
- **HEDGE_PAYS**: `N > 0` AND every `e_i ≥ 0` (or CI entirely > 0).
- **UNDECIDABLE-AT-N**: anything else (mixed episode signs, CI
  crossing zero, or pairing/verification failures in the harness).

**Scope clause, binding**: the verdict speaks ONLY to the recorded
trigger window (2026-08-07T01:09:40.459Z–11:35:31.553Z inclusive) and
ONLY to sizing aggression on the triggers that actually fired. It is
constitutionally silent on whether hedging would have paid during the
suppression period after 2026-08-07T11:31:02.005Z, because the
exposure/correlation paths needed to decide that were never persisted.
If the operator hypothesis is really about THAT period, the readout
for it is UNRECONSTRUCTABLE-FROM-HISTORY regardless of the grid, and
the only forward path is prospective (start persisting per-cycle
net-delta/corr telemetry — itself a SAFE-class change, docketable
separately). The registration names which decision becomes decidable;
it never decides.

## Harness contract

`scripts/hedge_sim.py`: reads `outputs/fills.csv`, `outputs/audit.jsonl`
(streamed, never whole-file into memory), `outputs/equity.csv`
(windowed); writes ONLY a markdown report to a caller-named path under
`docs/quant/` (default `docs/quant/2026-08-28_hedge_sim_results.md`)
and stdout. No writes under `outputs/`. Tests ship in the same commit
with at least one planted-defect (injection) check, including: a
fee-free run must beat the fee'd run by exactly the fee stack.
