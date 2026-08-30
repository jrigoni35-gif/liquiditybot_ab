# Reverse-cycle research — is there profit in the bot's deficiencies?

**Date:** 2026-08-29
**Class:** SAFE (measurement only — no decision/config/model/era touched; live
runner untouched; reads history, writes this doc + committed fade instrument).
**Operator question:** "Is there a REVERSE CYCLE that captures profit from the
bot's deficiencies? Anything matters. Don't assume, do research."

---

## Headline

**No. There is no profitable reverse cycle on this data.** The bot's
deficiencies are STRUCTURAL COSTS with no profitable inverse. Every apparent
reverse edge that clears the fee dies the moment it is measured at effective-n
under honest (non-overlapping / block-deflated) sampling — it is the
effective-n autocorrelation mirage, inverted, exactly as pre-named the #1 risk.

The only real edge in this system remains the **mechanical arithmetic** —
fee-tier truth (cut #8, the 40/80 correction already shipped) and tail control
— and that edge **needs no reverse**: it does not require predicting the market
or fading anything, it only requires not overpaying the rake and not eating the
tail. A manufactured reverse-edge from n_eff~20-30 would be the overfit failure
mode wearing a clever costume; three independent lenses each walked right up to
such a cell and each one dissolved on deflation.

---

## The hard arithmetic gate (respected, not evaded)

Pooled gross edge ≈ 0 (t=0.51) and it is **symmetric**. Therefore a **blanket
fade is exactly antisymmetric to follow** — fade mean = −follow mean at every
aggregation (pinned to 1e-12, `tests/test_reverse_cycle_fade.py::
test_antisymmetry`). A symmetric-zero gross minus the fee is negative on both
sides: **fading does not escape the rake.** A reverse cycle can only pay if a
CONDITIONAL structure makes the fade's gross positive by MORE than the real
Tier-3 rake. Everything below is priced at **60bps** (maker 22 / taker 38, the
un-attested 22/38 tier — provenance [I]; if the true taker rake is higher the
verdict only hardens).

## The #1 risk (the trap, and how it was disarmed)

The horizon sign-flips (va_pos +3.73@15min → −2.21@6h; imbalance_dir +2.77 →
−3.05) are the SAME effective-n autocorrelation mirage the horizon sweep
already caught at the feature level — "IC rises with horizon" was pure overlap
artifact. A fade that looks profitable on nominal n is that trap inverted.
Every lens below therefore reports **effective-n** (non-overlapping subsample,
one obs per H-length block per asset, and/or day-block bootstrap), **never
pools across disjoint `label_era`**, and **defaults any reverse claim to
SPURIOUS** unless it clears the fee at effective-n out-of-sample.

---

## Three lenses, three refutations

### Lens 1 — REVERSION FADE (horizon sign-flip) → mirage-refuted
Instrument: `scripts/reverse_cycle_fade.py` (+ `tests/test_reverse_cycle_fade.py`),
reconstruction core lifted verbatim from the mutation-killed
`horizon_edge_sweep.py`; committed `e2123a97` (SAFE), 6 pins green, 2 guard
mutations killed-and-restored (demean, non-overlap), all load-bearing cells
double-derived by an independent polars route.

- The seductive trap: raw direction-signed return grows monotonically with
  horizon and appears to clear 60bps at 72h — **follow_nom 72h = +0.0133, net
  +73bps, t=+9.61** [K]. This is two artifacts stacked: 61% long tilt × 25-day
  up-drift (beta) and forward-window overlap (nominal n=9175 not independent).
- Remove BOTH confounds (per-asset demean + non-overlapping): the long-horizon
  edge **collapses to noise — 72h t goes 9.61 → 0.16** (follow_eff_dm 72h
  = −0.0019; 48h +0.0033 t0.50; 24h +0.0003 t0.10) [K], n_eff 56/124/245.
- The only statistically real component is a **short-horizon POSITIVE timing
  edge** — follow_eff_dm 15min = +0.0010, **t=+3.60** (net −50bps), decaying to
  null by 1h. It favors **follow, not fade**, and is tiny (+10bps gross).
- The **FADE never clears the fee at any horizon.** Best cell 6h = +0.0020,
  t=+1.70, net −60bps; 72h fade +0.0019 but t0.16. No horizon reaches |t|>2 on
  the fade side; none clears +60bps net even by point estimate. n_eff 498 (6h).
- Entered-only (361 fills → 96 priced rows) is below the power floor:
  undecidable, not evidence either way. The pooled candidate population (same
  model direction calls, powered) is the decisive test.

**Verdict:** the reversion the hypothesis needs — follow turning significantly
NEGATIVE so the fade turns positive — does not exist under honest sampling.

### Lens 2 — LATENCY AS AN ASSET (late entries at reverting extremes?) → does-not-clear
Instrument: `scratchpad/latency_reversion.py` + `confirm.py` (scratchpad-only —
see reproducibility caveat). 251/523 realized entry fills matched to kraken 1h
candle path; window 2026-07-30..2026-08-29 (one ~30-day regime).

- Structure at the bot's realized entries is **CONTINUATION, not reversion**:
  corr(pre-extension, forward move) is POSITIVE at every (K,H) and rises with
  window — corr(ext6h,fwd6h)=+0.383 [K]. (Shared-p0 measurement noise biases
  this toward reversion, so the observed positive sign is conservative.)
- The **FADE loses gross at every measurable horizon** under non-overlapping
  sampling: ext3h/hold3h −0.280% (t−1.94); ext6h/hold6h −0.333% (t−2.04).
  Best case ext1h/hold6h +0.179% gross, CI upper bound **+0.44% < the +0.60%
  fee**. Every cell net(−0.60%) is −0.42% to −1.01%. 3000× day-block bootstrap
  (seed 7) agrees. n_eff 126-145.
- Market baseline (all 10,624 kraken 1h bars) is a **near-random-walk**
  (corr(past6h,next1h)=−0.019): the +0.3 continuation is the bot's own momentum
  SELECTION, not a free market property, and there is **no reversion in the tape
  to fade** either. Corroborates the adverse-selection markout≈0 at ≥1h.
- The mirage cuts the SAFE way here: the reverse edge **never even looked
  positive**, so there was no illusory edge for deflation to kill.

**Boundary (honest, undecidable-at-n):** reversion could still live strictly
SUB-HOUR, and **no sub-hour price record exists in the repo** (finest = 1h
candles). That window cannot be adjudicated with current instruments.

### Lens 3 — SPOOF FADE (fade likely-spoofed imbalance when manip_suspect high) → mirage-refuted
Instrument: `scratchpad/spoof_fade.py` over `ml.corpus` (scratchpad-only — see
caveat). Corpus `outputs/signal_history.csv` snapshot mtime 2026-08-30T04:17:27Z,
19,473 rows / 10,031 valid entry-exit [K]. Never pooled across eras.

- Across 2 eras × 3 directional features × 2 manip thresholds × 7 horizons,
  **0 of 84 high-manip fade cells** reach net@60>0 with |t_eff|≥2. Best-powered
  high-manip cells (6h, n_eff 53-89) are t +0.85..+1.19, net@60 −0.16 to −0.18%.
- The only net@60>0 fade cells are the pre-named mirage: va_pos 72h manip≥0.75
  (+2.63%, t+1.91, **n_eff 20**) — and they FAIL replication (vanishes to +0.27%
  at thr 0.90, **inverts to −2.39% t−2.00 at 48h**). Sign-unstable across the
  grid = artifact.
- The ONE genuine flow edge is **MOMENTUM, not reversion**: 15min imbalance_dir
  FOLLOW +12.8bps gross (t+3.92, n_eff 816); FADE −12.8bps (t−3.92). Even the
  real edge nets −47bps (follow) / −73bps (fade). Fading a predictive signal
  loses by construction.
- **manip_suspect cannot isolate spoofs** — splitting on it does NOT invert
  imbalance's forward sign (15min fade negative in BOTH low-manip t−3.89 and
  high-manip t−1.24/−1.85), it only drains n. This is the observational-
  equivalence type specimen made economic: the detector scores honest trend-
  chasing and true layering **byte-identically (0.949/0.949)**, so high-manip
  selects TRENDING tapes — "fade the spoof" degenerates to "fade momentum",
  which loses.

**Verdict:** no detectable-spoof fade exists; the reverse cycle adds nothing to
an already-null book (prior art: `game_theory_edge_loop.md` solid_edge_set={};
`game_theory_adverse_selection.md` symmetric zero-alpha null).

---

## Synthesis — why all three converge

Three different routes into the same deficiency (slow/late, spoofable street
book, forced-taker rake) and three refutations with the **same shape**:

1. A tempting positive cell appears at nominal n or long horizon.
2. It sits at n_eff ~20-30, |t|<2, and sign-flips across the adjacent grid.
3. Deflation (demean + non-overlap / block-bootstrap) collapses it to noise.
4. The only statistically real flow structure that survives is a **small
   short-horizon MOMENTUM edge (favoring FOLLOW), an order of magnitude below
   the 60bps fee** — so even the genuine signal cannot be traded, and its fade
   loses by construction.

The market is boring and efficient (the-method rule 6); the rake is real. The
bot's late entries are the bot's own momentum SELECTION riding continuation, not
a parking-at-an-extreme that reverts. There is no free structure a reverse cycle
can harvest. **The deficiencies are costs, and the inverse of a cost is not a
profit — it is the same cost paid on the other leg plus the fee.**

## Reproducibility caveat (stated plainly)

Asymmetric provenance across the three lenses:
- **Lens 1 (fade)** has a **committed, mutation-killed, pinned, double-derived**
  instrument (`scripts/reverse_cycle_fade.py`, commit `e2123a97`) — reproducible
  from the tree.
- **Lenses 2 and 3** ran on **scratchpad-only** instruments
  (`latency_reversion.py`, `confirm.py`, `spoof_fade.py`) that are NOT persisted
  in the repo. Their numbers are as-reported [K] from their runs but are **not
  currently re-runnable from committed code.** If either verdict is to become
  load-bearing for a future decision, the instrument must be promoted to
  `scripts/` with pins (the fade lens is the template). Both nonetheless
  converge with committed prior art (`game_theory_edge_loop.md`,
  `game_theory_adverse_selection.md`, `horizon_edge_sweep.md`).

## What the research could NOT see (honest boundaries)

- **Real-fill fade** — entered-only n=96 is below the per-asset power floor;
  undecidable. Price-path reconstruction ignores real slippage / give-back
  geometry, and a **taker fade pays MORE**, so the real-fill verdict can only be
  worse than the price-path one, never better.
- **Sub-hour reversion** — no sub-hour price record exists (finest = 1h). The
  one window where latency-reversion could still live is unmeasurable with
  current instruments.
- **Nonlinear / regime-conditional reversion** a marginal mean cannot detect.
- The **60bps rests on the un-attested 22/38 tier** [I]; `cost_truth_report` is
  the independent route if that number must be firmed up.

## Answer to the operator

- **surviving_candidates:** NONE. No reverse variant clears the real 60bps fee
  at effective-n out-of-sample. The closest cells (6h fade ~net −40 to −60bps;
  long-horizon fades at n_eff~20) are sub-significance and/or the deflated
  mirage.
- **refuted (the mirages):** (1) long-horizon follow "+73bps@72h" = beta +
  overlap (t 9.61→0.16); (2) 6h fade excursion = sub-2σ wobble; (3) latency-
  reversion = continuation, fade CI upper bound +0.44% < fee; (4) spoof-fade =
  "fade momentum" via a detector that can't tell honest from hostile flow
  (0.949/0.949); every high-manip positive cell is n_eff~20 sign-unstable.
- **next_step:** the honest **"no reverse cycle exists on this data."** The only
  new SAFE measurement that could move any verdict is **sub-hour post-fill price
  capture** (a new instrument, not a strategy change) to adjudicate the one
  undecidable window. Absent that, do NOT build a reverse/fade cycle. Continue
  the mechanical-arithmetic track (fee truth cut #8, tail control) — the only
  edge here that needs no prediction and no reverse.
