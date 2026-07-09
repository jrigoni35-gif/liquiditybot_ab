# liquiditybot v2 — architecture

Data plane: OKX + Binance.US are public read-only data sources (no keys), Kraken is the sole execution venue and holds the only credentials.
v2 adds a regime brain, a competition-style execution stack, an ML sizing
layer, and a narrative-resistance filter on top of the original 5-gate signal
engine, 4-tier profit taking, and capital manager.

## Pipeline

```
                    ┌────────────── HOURLY ──────────────┐
 OKX/BinanceUS/Kraken → daily candles → MacroRegimeEngine (HMM + TSMOM + drawdown/vol)
                                  → CorrelationEngine.turbulence (Kritzman–Li)
                                  → per-regime playbook (bias/size/lev/tiers/stops)

                    ┌────────────── SLOW (30s) ──────────┐
 OKX/BinanceUS books+candles → market view → FairValueEngine (depth-weighted microprice)
                                       → VolRegimeEngine (Parkinson blend)
                                       → LiquidityRegimeEngine (spread/depth/spoof)
                                       → CorrelationEngine (EWMA fast/slow, betas)
 Google News RSS (figures) + crypto RSS + Reddit → SentimentScanner
 CoinGecko + Fear&Greed → WebDataFeed | moomoo equities (optional) → risk z
                        → NarrativeFilter (vs structural stress)

 5-gate signal → features → MetaModel P(win) → Kelly sizer ×(regime·vol·liq·sentiment)
              → Avellaneda–Stoikov quote (inventory-skewed limit price)
              → PreTradeGate (edge ≥ 1.3× fees+spread+book-walk+√impact)
              → OrderManager.submit (post-only limit)

                    ┌────────────── FAST (5s) ───────────┐
 Kraken marks/books → OrderManager.poll → FillEvents → positions (avg price, fees)
 hard stops (vol×regime scaled) → tier exits (regime tier_scale, inventory tighten)
 InventoryManager.derisk (hard caps, stale losers) → HedgeEngine (β-weighted net delta)
```

## Model pedigree

| Component | Source model |
|---|---|
| Macro regimes | Hamilton (1989) Markov regime switching — Gaussian HMM, Baum-Welch, pure numpy |
| Trend vote | Time-series momentum, Moskowitz–Ooi–Pedersen (2012), 1/3/6-month lookbacks |
| Vol targeting | Moreira–Muir (2017) volatility-managed sizing; leverage = target_vol/realized |
| Turbulence | Kritzman–Li (2010) Mahalanobis turbulence index, crisis overlay |
| Correlation | RiskMetrics EWMA covariance, fast/slow shift detection, hedge betas |
| Quoting | Avellaneda–Stoikov (2008): inventory-skewed reservation + vol-scaled spread |
| Impact | Square-root market-impact law (Almgren–Chriss family) in the pre-trade cost stack |
| Labels | López de Prado triple-barrier + meta-labeling |
| Validation | Purged walk-forward with embargo (López de Prado) |
| Sizing | Fractional Kelly (¼), payoff ratio derived from the live tier/stop config |

## Key design rules

- **Fair value first.** Nothing prices off last trade. Entries are limit
  orders at the AS quote around a depth-weighted, EMA-smoothed microprice
  blend of OKX + Binance.US + Kraken. Binance.US is spot-only, so the
  funding-rate gate and funding feature are driven by the OKX perp alone.
- **Vetoes compose.** Regime playbook → inventory caps → leverage governor →
  Kelly sizer → pre-trade gate. Any zero kills the trade. Exits are exempt
  from the edge gate (risk reduction is never blocked) but slippage-capped.
- **Inventory mean-reverts by construction.** The AS reservation skew leans
  quotes against inventory continuously; soft caps stop same-side adds;
  hard caps force reduction; stale losers with the regime against them are
  purged. Hedges are β-weighted, correlation-gated, and unwound when the
  correlation that justified them decays.
- **Spoof detection is defensive only.** Large levels that vanish young
  without price ever touching them raise the spoof score; `spoofy` regime
  blocks *new* risk and doubles quote widths. The bot never paints
  liquidity itself.
- **Sentiment is a filter, never a trigger.** Enforced structurally: the
  scanner's only consumers are the NarrativeFilter (risk multiplier
  clamped to [0.5, 1.0], confidence tilt clamped to ±0.15) and two feature
  columns. Fear without structural stress (vol/depth/funding/turbulence/
  basis) is classified `narrative_noise` and changes nothing — this is the
  media-fear-spoofing resistance.
- **Leverage is earned, never default.** `use_margin=false` ships as
  default (hard 1x). When enabled: vol-target ÷ realized vol, clamped by
  regime cap, then the 10x region cap, then margin-level scaling with a
  block at 150% (Kraken liquidates near 40% — the buffer is the point).
  Kraken pair-level maximums may be lower than 10x; the governor treats
  config as a ceiling, not an entitlement.
- **ML is honest or absent.** Cold start uses a conservative prior (0.56,
  only when all 5 gates confirm). The MLP must beat the logistic baseline
  out-of-sample in purged walk-forward to deploy. Probabilities are shrunk
  toward 0.5 so a lucky training set cannot command outsized Kelly
  fractions. Live trades are labeled from the bot's own net PnL and
  retrain via `scripts/train_meta.py`.

## Config reference (new sections)

`regime` HMM states, hysteresis, momentum lookbacks, playbook overrides ·
`vol_regime` percentile thresholds · `liquidity_regime` depth/spread floors,
spoof detector params · `correlation` EWMA lambdas, turbulence lookback ·
`market_maker` γ, k, τ, spread clamps · `pretrade` **set maker/taker to your
Kraken fee tier**, impact η, edge/cost ratio, staleness, participation ·
`order_manager` timeout, fee bps · `inventory` soft/hard caps, stale purge ·
`hedging` net-delta cap, correlation floor · `leverage` use_margin,
region_max_leverage (10), vol target, margin thresholds · `position_sizer`
Kelly fraction/cap, min p(win), cooldown · `ml` model/history paths,
prior, shrinkage · `sentiment` free multi-source scanner: tracked figures (Google News RSS),
news_feeds, subreddits, source_weights, filter thresholds — no keys ·
`webdata` CoinGecko + Fear&Greed poll · `moomoo` OpenD host/port, ticker
basket, disabled by default.

## Self-diagnosis & operator reports

- **Calibration** (ml/calibration.py): isotonic PAV fitted on out-of-fold
  walk-forward predictions, shipped inside the model JSON. Kelly gets
  probabilities that mean what they say, not just rank well.
- **Model monitor** (ml/monitor.py): rolling Brier vs a base-rate baseline
  plus calibration gap on closed trades. Ladder: healthy -> degraded
  (harder shrinkage, Kelly x0.7) -> failing (model bypassed, Kelly floored,
  retrain requested via outputs/retrain_requested.flag + CRITICAL log).
  Auto-retrain runs hourly when requested and enough new rows exist;
  champion/challenger on OOF Brier - a worse challenger never deploys.
  Recurring postmortem causes drive bounded knob nudges (cost overruns ->
  higher edge/cost bar; whipsaws -> wider stops, capped 1.5x), all logged,
  all decaying back on recovery. The monitor can only make the bot more
  conservative than config, never less.
- **Postmortems** (ml/postmortem.py): every entry records its thesis
  (p(win), expected value, expected cost, regime context). Any close that
  misses EV by >10% (or any stop-out) gets a markdown report in
  outputs/postmortems/ attributing the miss - alpha_wrong, cost_overrun,
  whipsaw (finalized 45 min after close so stop-then-recover is visible),
  regime_shift, fear_event - each with a mitigation tied to a config knob.
  Aggregates in outputs/postmortem_summary.csv.
- **Candidate labeling** (ml/history.py): every gate-confirmed signal,
  taken or vetoed, is labeled later via triple-barrier (source=
  "candidate"). Removes survivor bias and multiplies the training set.

## Limitations — read before going live

- No profitability guarantee. Regime models lag turns by construction
  (hysteresis is a feature); Kelly with a miscalibrated p(win) over-sizes;
  the impact/ADV model is a conservative heuristic.
- Paper-trade first: `dry_run: true` exercises the identical order state
  machine against real books with simulated fills.
- Sentiment/web feeds are free and keyless (Google News RSS, crypto RSS,
  Reddit JSON, CoinGecko, alternative.me). They can rate-limit or change
  format without notice; every source degrades independently to neutral.
- The moomoo feed (off by default) needs a moomoo account, the local
  OpenD gateway, and `pip install moomoo-api`. It is quote-context-only:
  the trade context is never imported, so execution through it is
  structurally impossible.
- Margin trading can lose more than the collateral committed. Leave
  `use_margin: false` until the spot behavior has earned trust.
- Bootstrap training data (EMA-cross pseudo-signals) is a weak prior, not
  evidence of edge. The meta-model only becomes meaningful as live labeled
  history accrues.
