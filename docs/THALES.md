# THALES — the lazy-bot insecurity model

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
