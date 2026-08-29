# TAIL-CONTROL-SIM — pre-registration (window, grid, fee truth, verdict rule)

**Date:** 2026-08-29 · **Class:** SAFE (counterfactual estimate on realized
fills; reads history, writes docs/scripts/tests only; **no config, decision,
fill-sim, fee-booking, or order-lifecycle change; mints NO execution era**) ·
**Repo HEAD:** `fb184e20` (== main at dispatch) · **Discipline:** HEDGE-SIM —
this file is committed STANDALONE **before any result is computed**. The
registration NAMES which decision becomes decidable; it never decides.

## 0. The question (frozen)

Given the established profit lead — *the bot is not edge-less; it loses to
**fat-tail losers**. At real Kraken Tier-3 fees the **median** realized era-4
trip grosses **+72.6 bps** and clears the ~60 bps round-trip rake (net +12.6
bps at the median), but the **mean** is dragged negative by a heavy left tail
(gross sd ~246 bps, left-skew)* (authorities:
`docs/quant/2026-08-29_fee_tier_correction_adjudication.md` §3 nuance 1,
`docs/quant/2026-08-29_fee_anatomy.md`,
`docs/quant/2026-08-29_game_theory_adverse_selection.md`) —

**does controlling the left-tail losers flip the equal-weighted MEAN net/trip
POSITIVE at real 60 bps, and by how much?** A SAFE estimate/sim, not a live
change. Tail control (docketed **ALGO-5**: stop widths + time-decay exit
ladder; **GB-1** give-back) is the pre-named profit lever — the OPPOSITE lever
from the fee correction.

## 1. WINDOW — the realized-trip population (exact, snapshot-stamped)

**Population = the pre-registered era-4 verdict cohort**, reconstructed by the
canonical instrument `scripts/cohort_eval.py::era4_trips(fills_path)` (entry-
opened, fully-closed round-trips, 2% size tolerance, duplicate fill-patterns
dropped, `since=None` → close-ts cut). This is the SAME population the tier-
correction adjudication used for the +72.6 bps median [K]. It is NOT the pooled
`fee_anatomy` 463-trip record (that spans ≥5 exec-eras and must not be read as
a single-era result).

- **Source:** `outputs/fills.csv` (per-fill ledger, `core/fill_ledger.py`).
  **Snapshot mtime 2026-08-29T06:27:45.096Z** (01:27:45 CDT), read this
  session. The live runner is probe-dominated, but the file **is** still
  growing — values are as-of this snapshot.
- **Frozen copy the sim runs on** (reproducibility, live file mutates):
  `scratchpad/fills_snapshot_20260829T0627Z.csv`, **sha256
  `c0747a40475432be8a1df9cfde46d3611c2ba935608a756675ff8fad5ff6d49e`**,
  185789 bytes, 1173 data rows.
- **Selection cut (inclusive):** close-ts ≥ `max(B4_TS, CAPITAL_EPOCH_TS)`
  = **1786403127.0 = 2026-08-10T23:05:27Z** (the capital-epoch reset instant;
  B4_TS 2026-08-10T11:03:35Z is earlier and not binding). `cohort_eval.py:112-124` [K].
- **Realized population extent as-of snapshot** [K, via `era4_trips`]:
  - **n = 63** entry-opened closed trips.
  - first entry-open **1786494432.204 = 2026-08-12T00:27:12Z**
  - first close **1786504480.142 = 2026-08-12T03:14:40Z**
  - last close **1787984597.022 = 2026-08-29T06:23:17Z**
  - **Inclusive ts bounds (closes): [1786504480.142, 1787984597.022] =
    [2026-08-12T03:14:40Z, 2026-08-29T06:23:17Z].**
- **n vs the tier doc's n=61:** that doc's snapshot was earlier
  (2026-08-29T06:27:45 vs its 06:27:45-stamped read of an earlier file); **2
  more trips have since closed** (n 61 → 63). Both are the same pre-registered
  selection; the sim freezes at n=63 on the sha above.
- **exec-era composition of the cohort** [K]: `7-e7d5ca1a` ×60, blank ×1,
  mixed `7-e7d5ca1a`+`8-ca55e2ba` ×1, `8-ca55e2ba` ×1. The cohort selection is
  **close-ts based, not exec-era based** — this is the pre-registered verdict
  population by design (`era4_trips` era-provenance is report-only,
  "CLASSIFIES ONLY"). Noted as a caveat, not a re-selection.

## 2. POLICY GRID (frozen — the exact set)

The **null policy** = the realized outcomes as-booked, re-priced at each fee
bracket (§3). Two ALGO-5 tail-control families:

### 2a. Hard stop-loss CAP (primary, fully estimable on fills)

For each cap `c ∈ {−0.5%, −1.0%, −1.5%, −2.0%}` **net** return: every trip
whose realized net/trip is **worse** than `c` is truncated **to** `c` (assume
the stop would have exited at the cap). `net_capped_i = max(net_i, c)`. Winners
and shallow losers are unchanged; only the left tail below the cap moves. Four
caps × three fee brackets = 12 stop-cap cells + the null.

### 2b. Time-exit ladder (SCREENING-ONLY here; quantitative estimate deferred)

Candidate time-exits **shorter than the current** deadline. **Current time
barrier = `ml.label_max_bars` 432 × 5m = 36h** (the live bracket deadline,
`config.json:635-637`); the PT-060 no-progress scratch is 36 bars = 3h
(`profit_taking.time_stop.max_bars_no_progress`). Ladder to test:
**{6h, 12h, 24h}**.

**Honest limit, pre-committed:** a fills-only ledger carries entry and exit
prices ONLY — it **cannot** recompute a trip's P&L at an earlier forced exit
without the intermediate price path. So the time-exit arm is reported here
**only as a screen** — the realized loser-vs-winner hold-duration split (does
the left tail concentrate in long holds?) — and its quantitative net-improvement
metrics are **DEFERRED to the candle-store re-sim** (§6). The screen already
observed: losers hold longer (median 7.97h) than winners (4.02h), so the ladder
is worth the heavier follow-up; but that follow-up, not this file, produces its
net numbers.

## 3. FEE BASIS (frozen)

Real account = **Kraken Tier 3** (operator screenshot 2026-08-29 14:58,
$17,482.46 30d spot volume): **maker 0.22% / taker 0.38%**. Net is re-priced by
subtracting a **flat round-trip** from each trip's gross (NOT the booked
`fees_delta_usd`, which are the stale 25/40→40/80 config schedule):

- **PRIMARY — 60 bps** = maker 22 (limit entry, OM-011 hard invariant) + taker
  38 (a stop/time exit escalates to taker; the escalation final rung is the
  natural exit for a capped trip, so 60 bps is coherent with the stop-cap
  policies). `net_i = gross_pct_i − 0.60`.
- **44 bps** = both-maker (22+22) bracket (lower bound; passive exits fill).
- **76 bps** = all-taker (38+38) bracket (upper bound; crossing entries too).

Gross per trip is `era4_trips` `gross_pct` = 100 × signed-cash / entry-notional
(fees excluded), the era-invariant half. USD conversion uses each trip's own
entry notional (`enot`).

## 4. METRICS (per policy, per fee bracket)

Reported at the primary 60 bps, with 44/76 as brackets:

1. **mean** net/trip (%), **median** net/trip (%)
2. **net-positive fraction** (share of trips with net > 0)
3. **total net USD** = Σ (net_pct_i/100 × entry_notional_i)
4. **improvement vs null**: Δmean, Δmedian, Δpos-frac, Δtotal-USD
5. **EFFECTIVE-N** via `cohort_eval.py::cohort_effective_n` (mean-uniqueness /
   concurrency deflation on the cohort's OWN trips) — reported alongside
   nominal n=63, NEVER nominal alone. Prior: n_eff=25.83 at n=61
   (tier-correction doc §6, SE ×1.54); re-computed at n=63 in the result phase.
   n_eff is a property of trip overlap and is ~policy-invariant (capping a
   return does not change when trips are open).

**Distinguishability at effective-n.** The improvement's paired SE is deflated
to n_eff: `SE_eff(Δ) = sd(Δ_i) / sqrt(n_eff)`. An improvement is
**distinguishable** iff `Δmean > 2·SE_eff(Δ)`. (A nominal-n Wilson/SE is
12–16× too tight per the stream audit; the era-4 n_eff was 9.92 in WHY-1,
25.83 here — the deflation is load-bearing and applies to the numbers we LIKE
at the same rate as those we doubt.)

## 5. VERDICT RULE (frozen — outcome → decision class)

Evaluated on the equal-weighted **mean net/trip at the primary 60 bps bracket**
(the registered gate is equal-weighted; the dollar-weighted total is reported
but does not set the verdict — the dollar-vs-equal-weight sign-flip hazard is
known, tier doc §3 nuance 2):

- **TAIL-CONTROL-PAYS** — **∃** a registered stop-cap policy with **mean net > 0**
  AND its improvement over null **distinguishable at effective-n**
  (`Δmean > 2·SE_eff(Δ)`). Tail control flips the sign AND the flip survives the
  concurrency deflation.
- **DOESNT-PAY** — **∀** registered policies, **mean net ≤ 0** (no cap clears
  zero at the point estimate). Truncating the left tail cannot flip the sign at
  all; the bleed is not tail-driven at the resolvable level.
- **UNDECIDABLE-AT-N** — **∃** a policy with **mean net > 0** at the point
  estimate, but **no** such policy's improvement is distinguishable at
  effective-n (positive but inside the n_eff noise band). The lever points the
  right way; n cannot confirm it.

(The three are disjoint and exhaustive over the {any-positive?, any-positive-
and-distinguishable?} outcome space.) The verdict is named at readout; this
registration does not pre-judge which fires.

## 6. HONEST HAZARD (pre-committed)

- **The cap assumes the stop WOULD have filled AT the cap — no gap-through.** A
  candle that jumps past the stop level fills the exit **worse** than `c`; those
  gap-through losers are the **uncontrollable floor** the stop cannot cap. So
  the stop-cap estimate is an **UPPER BOUND** on the benefit (best-case, zero
  slippage / no gaps). The realized fills do not record whether the cap level
  was touched intra-trip.
- **The cap also assumes the stop would not have exited a would-be WINNER
  early.** Because the cap only truncates trips whose *realized* net was below
  `c`, it cannot see a trip that dipped below `c` intra-hold and then recovered
  to a realized win — such a trip would have been stopped out for a loss under a
  live stop, but is left as a win here. This biases the estimate **optimistic**
  in the same direction as the no-gap-through assumption. Both are resolved only
  by the price path.
- **The time-exit arm is un-estimable on fills alone** (§2b) — screened, not
  scored, here.
- **The heavier follow-up, if this estimate is promising:** a full exit-geometry
  re-sim over the **candle store price paths** (`data/candle_store`,
  `docs/quant/2026-08-29_candle_store_coverage.md`) that (a) checks whether each
  cap level was actually touched before the realized exit, (b) prices gap-
  through at the next available bar, and (c) recomputes P&L at each time-exit
  rung — turning both upper-bound hazards above into measured effects.
- **Venue truth:** 22/38 is [I] from the operator screenshot; OM-080 fee-recon
  has fired **n=0** — no `TradeVolume` read corroborates the tier (FEE-3). Every
  net number inherits that one unproven assumption.
- **Effective-n:** n=63 is nominal; the cohort overlaps (n_eff≈25.8). No net or
  improvement number is read at nominal n.

## 7. CLASSIFICATION

**SAFE.** This registration, the estimate it authorizes, its helper script, and
its pins read history and write docs/scripts/tests only. They alter no config,
no decision path, no fill simulator, no fee booking, no order lifecycle, and
mint no execution era. The ALGO-5 config change this estimate *informs* is
COHORT-RESETTING and remains an operator adjudication — this file does not ship
it.

---

*Filed SAFE, standalone, before any result. Result doc + `scripts/` harness +
`tests/` pins follow in a separate commit.*
