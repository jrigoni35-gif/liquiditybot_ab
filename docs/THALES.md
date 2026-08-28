# THALES — the lazy-bot insecurity model

> **Registry (2026-08-27):** exploitable-mistake entries and their
> incorporation lifecycle now live in `docs/thales/REGISTRY.md` under
> the anti-rot contract `docs/thales/README.md`. This doctrine file
> stays at its legacy path (in-code references point here).

> Thales of Miletus, mocked as a penniless stargazer, used his foresight
> to reserve every olive press in Miletus and Chios one winter for
> almost nothing, then rented them back at harvest on his own terms
> (Aristotle, *Politics* I.11, 1259a). The first recorded trade built
> entirely on other participants' predictable complacency. That is this
> model: we do not out-speed anyone, we out-*notice* them.

## Thesis

Most deployed retail/prosumer trading bots run on lazy defaults: they
act on clocks instead of events, park orders at obvious levels, trust
their own single feed, and never validate their pipelines. **This
repo's own pre-audit history is the design template** — we shipped
every one of these sins ourselves before the audits caught them:

| Our past sin (fixed) | The market-wide archetype it exemplifies |
| --- | --- |
| Imbalance unit-mixing (OKX swap + Binance spot concat, 22–112×) | bots that never sanity-check feature units |
| Whiplash 0.55 silent veto (size_mult=0, no log) | bots with dead code paths silently steering size |
| Untuned config defaults running in prod (rollback gate on defaults) | bots trading vendor defaults verbatim |
| Trusting moomoo SDK to fail fast (it blocked forever) | bots that hang/misbehave when a dependency flakes |
| Duplicate runners clobbering state | bots with no operational hygiene |

A population of bots with those habits leaves **detectable, recurring
footprints in public market data**. THALES is a bank of detectors for
those footprints plus a bounded advice channel to profit from them.

## Insecurity catalogue (v1: four detectors)

### TH-010 `grid_ladder` — the Procrustes insecurity

**Archetype:** grid bots (Pionex/3Commas/Bitsgap/Crypto.com style) place
ladders of buy/sell limits at *fixed, evenly spaced* price levels and
mechanically re-arm each rung.
**Detection (kraken L2, 5s snapshots):** evenly spaced resting levels
with uniform sizes that *persist* across snapshots (real ladders rest;
MM churn doesn't). Score = spacing regularity × size uniformity ×
persistence, EWMA-smoothed.
**Exploit:** grids are short-gamma on trends — they sell into rallies
and buy into crashes, providing cheap continuation liquidity. High
grid score + trending macro regime ⇒ shade continuation-entry
confidence up. High grid score + ranging regime ⇒ ladder edges are
defended; range fades gain edge.
**Failure mode:** icebergs/genuine passive interest mimic ladders —
persistence gate helps but cannot fully separate; hence bounded shading
only, never a standalone trigger.

### TH-011 `metronome_mm` — the Metronome insecurity

**Archetype:** Hummingbot pure-market-making defaults: quotes refreshed
every `order_refresh_time` seconds with `order_refresh_tolerance_pct=0`
(cancel/replace on a clock even when nothing moved), `max_order_age`
1800s hard replacement, `price_source=current_market` (self-referential
mid, no external anchor). Deterministic, clock-based quoting.
**Detection:** autocorrelation of top-of-book replacement events across
5s snapshots — a dominant fixed-lag peak = timer-driven quoting.
Symmetric bid/ask distances while mid drifts corroborate.
**Exploit:** clock-quoters are stale immediately after fast moves (they
reprice on their next tick, not on the move). High metronome score ⇒
urgency-driven taker entries carry extra realized edge (stale quotes
subsidize entry); passive/post-only patience is worth less (we'd be
quoting next to snipeable flow). Shade urgency-aligned confidence up
within clamps.
**Failure mode:** exchange-side batching can alias cadence; require
the autocorrelation peak to clear a noise floor.

### TH-012 `clockwork_flow` — the Sisyphus insecurity

**Archetype:** DCA bots and naive TWAP slicers execute at fixed
timestamps (top of hour/day), documented intraday algo seasonality in
crypto (arXiv 2009.04200).
**Detection:** bucketed time-of-day/hour flow stats from rolling candle
history, **activated only if the bucket effect beats a shuffled null**
(same discipline as OF-2). No significance ⇒ score stays 0. Needs ≥ 2
days of history to arm.
**Exploit:** entries aligned with an imminent, statistically confirmed
recurring flow window get a timing shade up; exits scheduled just
before a favorable window get patience.
**Failure mode:** seasonality mining is the classic overfit trap — the
built-in shuffle-null and the warmup gate are mandatory, not optional.

### TH-013 `stop_herding` — the Lemming insecurity

**Archetype:** stops cluster at round numbers (~10% of FX orders end in
"00" — Osler's classic result, reproduced across retail crypto) and at
obvious swing highs/lows; sweep-and-revert is the documented signature
(cluster magnet → burst through → snapback once consumed).
**Detection:** proximity of mark to round-number grid (price-scaled)
and N-bar swing extremes, weighted by book thinness (existing
`liq.depth_ratio`); post-hoc sweep event = bar pierces the zone then
closes back inside.
**Exploit — two-sided:**
(a) *defensive (our own laziness, fixed):* entries whose protective
stop would land inside a hot cluster zone get shaded down — we stop
being the lemming;
(b) *offensive:* a confirmed sweep-and-revert event shades
mean-reversion confidence up opposite the sweep for a short decay
window.
**Failure mode:** genuine breakouts look like sweeps at first — the
close-back-inside confirmation and decay window bound the damage.

### TH-014 `feed_integrity` — the hostile-venue insecurity

**Archetype:** the *data itself* is the attack surface. A venue (or an
adversary in front of one) can screw a bot through the values it returns:
unsorted books that hide the true touch, crossed/garbage books, physically
impossible OHLC, `Infinity`/`NaN` numeric fields that inject phantom fills
or infinite entry prices. Those are all **rejected at the sanitize
boundary** (`core/sanitize`, fail-closed) — that is the correct layer and
where the 2026-07-12 hardening lives. THALES's complementary role is to
notice the *pattern*: an asset whose feed keeps failing integrity is a
hostile-or-unreliable venue, and our signal on it deserves less trust.
**Detection:** per-asset rolling clean-rate of the fast-cycle book (1 =
a clean book arrived, 0 = missing or sanitize-rejected). Dirty fraction
past `dirty_frac_thr`, once `min_obs` samples exist, engages the shade.
**Exploit — defensive only:** shade that asset's entry confidence DOWN,
proportional to the dirty fraction; never up, never a direction. It is
the *soft* per-asset complement to the watchdog's *hard* staleness block
(watchdog halts new risk on full staleness; TH-014 quietly distrusts an
asset that is merely flaky-or-manipulated below that threshold).
**Failure mode:** a transient network blip raises the dirty rate without
malice — bounded by `min_obs` (needs sustained failure) and the shade
clamp, and it is only ever conservative (trades smaller / not at all).
**Note:** this is the one session-hardening theme that genuinely belongs
in THALES. The rest (dead code, type gaps, schema-loss, the sanitize
fixes themselves) are boundary/code faults fixed at their own layer — not
forced into a market-behaviour model.

### TH-016 `observation_lapse` — the Rip-van-Winkle insecurity

**Archetype:** a bot that sleeps through a gap and wakes believing no
time has passed. We LIVED this one from the inside on 2026-07-14: a
container restart restored a day-old snapshot, proxy outages punched
hours-long holes in the observation stream, processes died with nothing
to relaunch them — and every layer that survived kept treating its
pre-gap memory as current. State built before the hole advised after
the hole at full confidence; nothing self-reported the degradation.
Every lazily-operated bot has this failure mode; ours did too. The
first, most honest integration is **detector-of-self**: make THALES
aware of its OWN observation gaps before hunting anyone else's.
**Detection (self):** per-asset timestamp of the last clean fast
observation (the engine only observes when a clean book actually
arrived, so call cadence IS data arrival). A gap above
`lapse.fast_gap_sec` — or a clock regression beyond
`clock_skew_tol_sec`, the counter-rollback we also lived — is a lapse.
On the candle stream, a hole above `bar_gap_bars` × the observed bar
spacing (venue halt/maintenance) fences swing/sweep context the same
way. Clockwork buckets survive fences: time-of-day statistics are keyed
by bucket and gap-immune by construction.
**Response — hygiene only:** reset every piece of continuity-dependent
memory (metronome event deque and score, grid/barclose prev-snapshots,
pending sweep, marks) so no detector ever compares a post-gap snapshot
against pre-gap memory; then mute the advice channel — neutral in BOTH
modes, gates and exits untouched — for `warmup_sec` while the bank
re-accumulates live footprints, and report `lapses` +
`lapse_warmup_sec` per asset in status so the dashboard shows the
degradation instead of hiding it.
**Failure mode:** an over-eager gap threshold turns routine flaps into
permanent warmup — a silent self-disable. Bounded by the config guard
(FATAL at `fast_gap_sec<=0`, warn below 60s) and by the mute being
purely conservative: a muted THALES is exactly the pre-THALES bot.
**v2 candidate (evidence first):** the same lapse signature in OTHERS —
mass same-instant level revivals after a frozen book, re-quotes at
stale price levels after shared-infra events. Deferred until we can
measure those footprints without fooling ourselves (TH-017, not built).

## Activation ladder (build the concept over time)

1. **shadow** *(default, ships now)* — detectors run, scores land in
   `status.json` under `thales` and in event logs. Zero influence on
   any decision. Collect hit-rate telemetry against realized outcomes.
2. **advise** *(config flip, after shadow evidence)* — bounded
   confidence shading applied after GateStats, `conf_mult` clamped to
   `[1/max_shade, max_shade]` (default 1.15). Never touches direction,
   `all_confirmed`, or any risk-stack clamp. Every shade carries
   TH-020 in the signal notes.
3. **future rungs** *(explicitly not in v1)* — sizer coupling,
   exit-timing coupling, per-detector learned weights (GateStats
   pattern). Each promotion requires: shadow hit-rate beats null, OF
   battery green, quant-trial gates G1–G5 green.

## V2 — the vindication loop (evidence-weighted gains)

V1's detectors carried FIXED config gains: hand-crafted priors that
nothing ever validated. V2 closes the counterfactual loop:

- Every advise-mode entry records which detectors shaded it and in
  which direction (`ThalesShade.fired`, carried in order meta →
  position → close).
- At close, `note_outcome` grades each: "up" advice is vindicated by a
  win, "down" advice by a loss.
- Each detector's gain is scaled by `w = max(0, 2·WilsonLCB90 − 1)`:
  - below `reliability.min_fired` grades → `w = 1.0` (the prior rules
    cold start; behavior is EXACTLY V1);
  - a detector that cannot beat a coin flip at the 90% lower bound is
    muted (`w = 0`), and a muted detector is not re-fired (no ledger
    churn from a dead voice);
  - weights ATTENUATE only — a proven detector approaches but never
    exceeds its configured gain. Amplification is knob-tuning and
    belongs to the gated tuning pass, not a live feedback loop.
- `feed_integrity` is EXEMPT: it guards data quality, not an alpha
  thesis. Grading it by trade outcomes would let a lucky win on dirty
  data teach the engine to trust dirty feeds.
- The ledger (and open positions' fired maps) persist across restarts;
  detector OBSERVATION state still does not (TH-016).
- Shadow mode still reports `fired` at the engine level, but main.py
  only stashes it for advise-mode entries: shadow advice never
  influenced the trade, so it must never train the ledger.

## V3 concept — the certificate hierarchy (design, NOT implemented)

Argued against arXiv 2306.15079 (Wu & Braatz: execution-time-certified
MPC — iteration count data-independent, exact, dimension-only). Their
thesis generalizes: an influence on a real-time loop is admissible only
with a CERTIFICATE — a bound that holds before the data arrives.

1. **Time certificate** (from the paper): advice must fit the cycle's
   sampling budget by construction (bounded windows/deques — already
   true), or abstain. A late answer in a real-time loop is a wrong
   answer.
2. **Evidence certificate** (V2, shipped): an alpha claim keeps its
   voice only while its Wilson-bounded vindication beats a coin.
3. **Significance certificate** (clockwork z-gate, generalized): any
   calendar/seasonal context — session-of-day, day-of-week, yearly
   cycles — enters only past a shuffle-null significance test (OF-2
   discipline), never as a raw belief.
4. **Asymmetry law** (psychology of loss): context layers whose natural
   cadence is too slow to ever earn an evidence certificate inside the
   book's lifetime (yearly trends, geopolitical regimes) may only shade
   DOWN (risk-off), never boost. A false shade costs opportunity; a
   false boost costs money. Slow layers get veto rights, not alpha
   rights.

## Hard boundaries

- **Detect and react only.** No spoofing, no layering, no orders placed
  to trigger anyone's stops, no wash activity. We read public data and
  position our own (limit-order, firewall-gated) entries. The existing
  execution invariants (OM-011 limit-only entries, exit ladder, venue
  gate) are untouched.
- All thresholds live in `config.json → thales` with `config_guard`
  coherence checks (FATAL on nonsense).
- Shadow default: enabling detectors is not enabling influence.
- Every disposition carries a registered TH-xxx code.

## Evidence concentration (shadow, 2026-07-19)

The fused informed-flow evidence `E = Σ wᵢ·sᵢ` is a weighted **sum**, so a
diffuse 5-of-weak scores like a 2-of-screaming. That is the "base the
decision on everything / all averages" failure mode: a signal assembled by
averaging many small factors is treated the same as a pinpointed,
accumulating setup where one or two factors dominate.

`SignalResult.evidence_concentration` (0..1, normalized Herfindahl of the
signed component contributions `|wᵢ·sᵢ|`) measures which it is: 0 = perfectly
diffuse, 1 = one factor carries the signal. It is **shadow only** — it
changes no decision today — and is logged on every `IF3 scan`/`IF3 signal`
line. Promotion path (data-first, never hardcoded): shadow → confidence
shade that attenuates diffuse-but-marginal signals (the averaging trap) while
leaving concentrated conviction untouched → optional gate, only if
`quant_trials` G3/G5 and the out-of-sample simplicity-ladder confirm it pays.
This is "process of elimination that never loses the bigger picture": the
`evidence_threshold` still owns the bigger picture (is there enough total
signal at all); concentration adds *how* that signal is composed.

**Status (TH-021, wired):** the promotion mechanism now exists as a bounded,
DOWN-only confidence shade (`concentration_conf_mult`, applied after the THALES
footprint shade) that trims a signal only when it is BOTH diffuse
(`concentration < conc_pivot`) AND marginal (`floor_conf ≤ conf < marginal_conf`);
concentrated conviction and already-strong signals are untouched. It is
**config-gated and disabled by default** (`thales.evidence_concentration.enabled`)
— enabling it is the gated promotion step, taken only once shadow hit-rate beats
null and the OF/quant battery stays green. Off, behavior is byte-identical.

## Lessons folded in from this session's errors

- **NaN/inf never reaches the corpus** (ML-015): `float('nan')` parses
  silently, so a single bad feature once NaN'd an entire retrain. Finiteness
  is now enforced at the store boundary (write) with a load-time backstop —
  clean ground truth by construction, not by later cleanup.
- **Complexity is earned on ground truth, not proxies** (ML-016): the
  walk-forward ladder now admits gbt/blend/mlp/adaptive_gbt only when the
  LIVE label count clears a floor; below it the brain trains logistic alone.
  Trying every learner on a proxy-heavy corpus only manufactures an
  overfit winner (and inflates PBO).
- **Calibration must not rescue complexity**: selecting on isotonic-calibrated
  Brier let a complex model win a *pure-linear* world (isotonic hid its
  miscalibration). Selection stays on raw Brier (the stricter bar that
  penalizes miscalibration); calibration is reported per candidate and applied
  as the final deploy check only.

## Sources

- Aristotle, *Politics* I.11 (Thales and the olive presses)
- Hummingbot pure-MM docs: order refresh mechanics and defaults —
  <https://hummingbot.org/strategies/v1-strategies/pure-market-making/>
- Grid bot mechanics: <https://www.coinbase.com/learn/advanced-trading/what-is-a-grid-trading-bot-and-how-does-it-work> ,
  <https://bitsgap.com/crypto-trading-bot/grid-bot>
- Stale-quote sniping / adverse selection: Aquilina, Budish, O'Neill
  "Quantifying the High-Frequency Trading Arms Race"; crypto framing —
  <https://multicoin.capital/2026/02/17/adverse-selection-rules-everything-around-me/>
- Round-number stop clustering: C. Osler, "Currency Orders and Exchange
  Rate Dynamics" (JF 2003); practitioner reproduction —
  <https://www.tradingview.com/chart/GOLD/R0q3tkr1-Stop-Loss-Basics-Why-Round-Numbers-Get-Your-Stop-Hunted/>
- Liquidation cascades / sweep-revert:
  <https://www.bit.com/insights/knowledge-hub/cascade-liquidation> ,
  <https://chartinglens.com/blog/liquidity-sweeps-trading-guide>
- Intraday algo seasonality in crypto: arXiv 2009.04200 "Rise of the
  Machines? Intraday High-Frequency Trading Patterns of Cryptocurrencies"
