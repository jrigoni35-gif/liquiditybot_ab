# Flow investment review — what makes it different from the others

**Date:** 2026-08-29 · **Class:** SAFE (measurement/report, no decision-path
or config change) · **Scope:** review-only synthesis of committed session
docs + adversarial read of the flow producers. Live runner was RUNNING;
`outputs/` read-only. Nothing here recommends a code change (flow is
model-frozen 2026-08-10).

## The operator's question

Review ALL aspects of the FLOW investment and find what makes it DIFFERENT
from the OTHER investments. "Investment" = engineering effort + capital-
allocation bet on a signal/approach. FLOW = the order-flow / microstructure /
liquidity-footprint family (`ofi_dir`, `ofi_event`, `flow_tox`,
`imbalance_dir`, `imbalance_delta_dir`, `book_touch_share`, `depth_ratio`,
`venue_disloc_dir`, `liq_pocket_pull`, `fvg_pull`, `fvg_liq_confluence`,
`poc_dist`, `va_pos`, `manip_suspect`, THALES `th_grid/th_stopzone/
th_metronome/th_clockwork/th_barclose`). Producers: `strategies/
liquidity_model.py`, `execution/fair_value.py`, `strategies/informed_flow.py`,
`sentiment/`, `ml/features.py`.

## THE DIFFERENCE, in one line

**Flow is the only investment whose edge is a RACE.** Every other durable
investment is arithmetic the bot performs on its own book, which no
competitor can contest. Flow's edge — where it exists at all — lives on the
**SPEED axis**, the single axis where this bot is structurally weakest, and
it is contested by the players best-equipped to win it (co-located market
makers / HFT). The other durable investments (fee-truth booking, tail-control
geometry, SZ-030 cost-aware rejection) live on the **MECHANICAL / ARITHMETIC
axis** where the bot holds a structural advantage: unilateral decisions about
its own book that no counterparty can act against. You cannot arbitrage away
another party's decision to pay less fee, cut its own loss tail, or not trade.
That axis split IS the difference.

## The axis framework (the sort is the answer)

An edge is a *sound* investment for this bot only if there is a **structural
reason a rational competitor cannot arb it away FROM this bot**. Sort every
investment onto its competitive axis and ask whether the bot can win THAT
axis. The bot is: slow, REST-polled (~6.2s cycle, Kraken rate-limited 3/s),
~95% I/O-wait, 83–86% of latency venue-side, Kraken-only, ~$800, dry-run
(perf-latency-work memory [K]).

| Investment | Axis | Bot on that axis | Edge measured? |
|---|---|---|---|
| **Fee-truth booking** (cut #8: book real 40/80 not understated 25/40) | MECHANICAL/arithmetic | **ADVANTAGE** — unilateral, latency-immune | Correction is exact by construction |
| **SZ-030 net-Kelly cost-aware rejection** (f\*≤0) | MECHANICAL/arithmetic | **ADVANTAGE** — no counterparty to a *don't-trade* decision | **YES, regime-invariant** — held 0.060 [0.040,0.089] through the 08-20 melt-up |
| **Tail-control / ALGO-5 stop geometry + give-back** | MECHANICAL/arithmetic (risk-geometry) | **ADVANTAGE** — no one races you to cap your own loss | Aimed right; net prize unproven (CI spans zero) |
| **Fee-tier CORRECTION** (book true tier) | MECHANICAL/arithmetic | ADVANTAGE — pure arithmetic | Exact; rests on un-attested 22/38 input |
| **Fee-tier REDUCTION** (lower the tier) | CAPITAL/SCALE | **DISADVANTAGE** — tier set by 30d USD volume; $0 dry-run venue volume → permanently Tier-1 | Out of code's reach |
| Directional / momentum / regime signals | CONTESTED-PREDICTION | DISADVANTAGE — no informational moat | No — `solid_edge_set={}` |
| ML model families | CONTESTED-PREDICTION | DISADVANTAGE — already frozen 2026-08-10 | No — edge-refuted on OOF Brier |
| **FLOW** | **SPEED (contested-prediction, extreme case)** | **DISADVANTAGE — the bot's single weakest axis, and uniquely its INPUTS are speed-starved too** | No — null 15min–72h |

Two families emerge, and flow is the extreme corner of the losing one:

- **CONTESTED-PREDICTION axes** (flow, directional/momentum, regime, ML): the
  bot competes against informed traders / co-located HFT for a forecast.
  Every family here measures edgeless — `game_theory_edge_loop.md`
  `solid_edge_set={}`, max |z_eff|=1.44 across 10 contrasts (= chance);
  models lose to null on OOF Brier (OF-1); regime edge sits ±0.11% of zero;
  horizon sweep null 15min–72h. The operator already conceded this axis with
  the 2026-08-10 model freeze. **Flow is the extreme case:** the seconds-
  timescale, most-arbitraged, most-co-lo-dominated corner, and the ONLY
  family whose raw INPUTS are also speed-starved at the data layer.
- **MECHANICAL / ARITHMETIC axes** (fee-truth, tail-control, maker-first exit,
  SZ-030): no racing counterparty exists. The bot's latency is irrelevant to
  booking its own fees, placing its own stop, or resting its own exit. The
  single regime-invariant edge on record lives here.

## Why flow loses on BOTH horizons (the two-horizon trap)

The operator's own refutation — "multi-day whale accumulation is not a speed
race; the whale-thesis was multi-day" — is the right instinct, but it fails on
two independent routes, so flow loses at both horizons for structurally
distinct reasons.

**Horizon 1 — intraday/seconds, where flow features DO carry deflated IC:**
the bot is structurally incapable of harvesting it. `va_pos` z=+3.73 at 15min,
`imbalance_dir` z=+2.77 — but the edge is **sign-unstable across horizons**
(`va_pos` +3.73 → −2.21 by 6h; `imbalance_dir` +2.77 → −3.05) and **never
clears the 120bps fee floor** (horizon_edge_sweep.md finding 3 [K]). That
sign-unstable, intraday-only, sub-fee-floor signature is the fingerprint of
**microstructure mean-reversion noise** — the residue left after faster
players have taken the real edge before this bot's ~6.2s REST cadence can act.
The bot samples the book seconds-to-minutes late and never sees order-by-order
flow at all.

**Horizon 2 — multi-day accumulation, where the bot is NOT speed-
disadvantaged:** there is no measurable footprint edge, and the corpus cannot
power the test. The horizon sweep tested 24–72h forward edge from every flow
feature: **UNDECIDABLE at n_eff=40** (24.7 priced days, ~40× underpowered vs
the ~1,600 needed to detect IC≈0.05), and the seductive "IC rises with
horizon" is a **pure effective-n autocorrelation mirage** — every monotone
nominal climb (`flow_tox`, `liq_pocket_pull`, `th_grid`, `footprint_block`,
`venue_disloc_dir`) collapses or flips sign under non-overlapping sampling
(horizon_edge_sweep.md findings 1–2 [K]). So at days-scale flow is lost not to
a speed race but to (a) no measurable footprint edge and (b) a corpus that
cannot power the test.

**The equipment prong closes the escape hatch regardless of whether the slow
edge exists.** The bot's flow features are **differenced REST-poll snapshots**,
not an order-event stream. `_ofi_event` (liquidity_model.py:36-59) computes
Cont-Kukanov-Stoikov OFI — *defined on the tick event stream* — from two
**consecutive polls'** top-of-book; every cancel/add/fill between the two
polls is aliased into one net-displacement number. The producer is disciplined
about wall-time normalization (`/ds/dt*60`, line 278) and stale-resets to 0.0
(line 281), but **no normalization recovers unobserved samples**. A multi-day
flow-*accumulation* signal is the aggregation of exactly those missed seconds-
scale events, so **the multi-day thesis never leaves the speed axis — its raw
material is speed-starved at the DATA layer.** `informed_flow.py:85`
(`deque(maxlen=imb_maxlen)` + EWMA) confirms the family is EWMAs of per-cycle
book-imbalance snapshots. This data-layer speed dependency is one NO other
investment carries: a fee constant, a realized fill, and a stop distance are
exact regardless of latency.

## The triple strike (flow_verdict)

Flow is the worst-matched bet in the book because it fails three ways at once,
each independently disqualifying for THIS bot:

1. **Most-competed.** Order-flow is the most-arbitraged edge in markets,
   competed on speed, and this bot is the slowest possible participant facing
   the best-equipped possible competitor (co-located makers).
2. **No solid edge.** `solid_edge_set={}` (game_theory_edge_loop.md); null at
   every horizon 15min–72h (horizon_edge_sweep.md); THALES `th_*` max
   |z_eff|=1.44 = chance. The measured signature is exactly the noise residue a
   slow player fishing a fast pool is left holding.
3. **Most attacker-controllable.** `imbalance_dir/ofi_dir/venue_disloc_dir` are
   built from the OKX + Binance.US **street** books (liquidity_model.py:
   293-356), NOT Kraken. An adversary layering those read-only venues moves the
   ml feature vector with ZERO execution risk on the venue the bot trades. And
   the one cross-venue defense has a hole aligned with the cheapest attack:
   `manip_suspect = MAX(spoof, whiplash, divergence)` (main.py:370-391), but
   `spoof`/`whiplash` read ONLY the Kraken execution book (liquidity_regime.py:
   281), so a street-book paint produces spoof=0 AND whiplash=0 — only the
   blunt `divergence` term reacts. Separately the detector is
   observationally-equivalent: honest maker and layering attacker score
   byte-identically (HANDOFF RECENTLY-SETTLED; deleting the gate cost only
   ~−$0.51; 99.6% of vetoes are FLOW+MINA, BTC zero — an asset filter wearing
   a security label). A speed-disadvantaged reader of an adversary-controllable
   signal competes **late AND blind** — the worst possible position on the
   speed axis.

## refutation_survives: does the slow whale-flow edge survive?

**No — not as a decidable investment on this bot's current data, though it
survives as an unfalsified hypothesis.** The multi-day whale-accumulation flow
was the right *instinct* — it is the one flow variant that would sit on a
non-speed axis the bot could plausibly contest — but two things block it:

- **Existence prong: UNDECIDABLE, not confirmed.** The design-horizon test is
  ~40× underpowered (n_eff=40 vs ~1,600), and the only apparent slow-horizon
  support is the autocorrelation artifact. "Cannot rule out" is not an
  investment thesis; there is no *positive* evidence a slow accumulation edge
  exists.
- **Equipment prong: the bot cannot capture it even if it exists.** The live
  flow features are instantaneous book snapshots, not multi-day flow-integrals;
  the multi-day price paths (`candle_journal.py`) were first built this session
  and are imported by NOTHING in the live decision path; the 2026-08-10 model
  freeze forbids adding the slow feature that would be needed. A slow-flow edge,
  if real, describes a **different signal** than the one the flow investment
  shipped.

**What it would take to test it:** the still-owed **candle-store months-of-
history re-sim** — a denser, clock-sampled (not signal-triggered) multi-day
price series per asset, lifting 72h n_eff from ~40 toward ~1,000+. Two measured
obstacles at the trade venue: Kraken 1h reaches only 30 days and the oldest
36.1% of the corpus is permanently unreachable (candle_store_coverage.md §4),
and the Binance.US backfill built this session has a NAMED TRAP — ARB/PAXG/FLOW
serve 2023 delisted-pair data with HTTP 200 (§5), so a study that reads the
FLOW lane by row count instead of `t_max_s` gets three-year-old prices labeled
"recent" (the confident-wrong-instrument shape). Testing the whale-thesis
honestly is owed measurement on data the bot **cannot yet decide**, not a
result in hand.

## One action item (SAFE, operator's attention)

Nothing here is a decision-path change. The one item worth flagging: the
shadow-purity of `ofi_dir/basis_mom_dir` (v9 SHADOW, feed only the ml vector)
is enforced by a **grep test** (`tests/test_ofi_feature.py`), not the type
system (liquidity_model.py:120-124, 334-340). A new consumer that reads
`view['ofi_event']` silently promotes a shadow feature to live with no gate,
no config, no reason code — structurally weaker than the attribute-enforced
`VenueAdapter.execution_eligible` gate. Promoting that invariant from a
test-convention to a structural gate is the only flow-side hardening worth an
operator's time; it is measurement/guard hygiene, not a cohort-resetting change.

## Honest caveats

- Every number is [K] carried from a committed session doc at effective-n; I
  re-ran no heavy measurement. The nominal flow edge is the mirage, not the
  finding.
- The verdict rests on the **equipment prong** [K] (differenced REST snapshots
  cannot observe sub-poll flow), which holds independently of the
  underpowered/UNDECIDABLE existence prong.
- Soundest-by-AXIS ≠ proven-by-prize even for the mechanical winners: the
  tail-control net CI still spans zero on fills-only (z=1.44), and the honest
  ceiling at $800/Tier-3/liquid-Kraken may be "a bot telling the truth about a
  game it cannot beat at this size" rather than P&L. The candle-store re-sim is
  the arbiter for the tail as well.
- What I could not see: whether a slow-flow edge exists at n larger than the
  corpus provides (structurally unobtainable at 1h on the trade venue), and any
  nonlinear/regime-conditional footprint a marginal Spearman/quintile method
  cannot detect (pursuing it would require new features the freeze forbids).

## Sources (all committed)

- `docs/quant/2026-08-29_game_theory_edge_loop.md` — solid_edge_set={}, durable
  edge is execution-side cost-discipline, SZ-030 held through melt-up
- `docs/quant/2026-08-29_horizon_edge_sweep.md` — null 15min–72h; n_eff=40 40×
  short; IC-rise is overlap artifact; intraday-only sign-unstable, sub-120bps
- `docs/quant/2026-08-29_fee_dominance_diagnosis.md` — fee-dominated every mode;
  only in-fence lever is GB-1/ALGO-5 tail geometry; tier locked by volume
- `docs/quant/2026-08-29_fee_tier_correction_adjudication.md` — 22/38 vs config
  40/80 [I from screenshot]; correction is arithmetic; reduction is capital
- `docs/quant/2026-08-29_tail_control_sim_results.md` — tail controllable-class;
  net z=1.44 CI spans zero
- `docs/quant/2026-08-29_game_theory_adverse_selection.md` — bot neutral, not
  adversely selected (−7.6bps, t=−0.72)
- `docs/quant/2026-08-29_candle_store_coverage.md` — Kraken 1h=30d, oldest 36.1%
  unreachable; ARB/PAXG/FLOW binanceus 2023 frozen-tail trap (HTTP 200)
- `docs/HANDOFF.md` RECENTLY-SETTLED — manip detector observational-equivalence
- Producers: `strategies/liquidity_model.py:36-59,229,278,281,293-356`;
  `strategies/informed_flow.py:85`; `ml/features.py:377,415,428,461,463`;
  `execution/fair_value.py:47`; `main.py:370-391`;
  `regime/liquidity_regime.py:281,286`
- perf-latency-work memory — cycle ~95% I/O-wait, Kraken 3/s wall, 83–86%
  latency venue-side, book-ws unbuilt
