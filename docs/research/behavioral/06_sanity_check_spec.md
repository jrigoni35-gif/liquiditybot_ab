# 06 — Sanity-check spec: injection tests against OUR artifacts

**THE DELIVERABLE.** Every test below is era-4 class **SAFE
(measurement-plane only)** — no test alters which orders are placed or how
they fill. Nothing here may be promoted into decisioning under the
2026-08-10 model freeze; the feature-candidates table at the end is
PRE-REGISTERED for boundary adjudication only and **explicitly NOT to be
implemented under the freeze.**

## Named artifacts (the corpus every test runs on)

- `outputs/signal_history.csv` — ~18k candidate rows: veto codes, labels,
  `label_era`.
- Fill ledger — schema owned by `core/fill_ledger.py`; era-4 closed trips
  n=54 (WHY-1: gross +$8.23, true fees $13.59, net -$5.36; probes n=49 net
  -1.05%/trip).
- `outputs/equity.csv` — current-epoch lens per session_digest.
- Postmortems (docs/quant/, docs/HANDOFF.md WHY-1/ATTR-1/ATTR-2).
- OKX-swap + Binance.US-spot read-only feeds (`data/okx_feed.py`,
  `data/ccxt_feed.py`, ws layer) + Kraken candles/books.
- `sentiment/scanner.py` — **known-defective instrument**: ATTR-1 read
  0.002-flat through the 2026-08-20 policy melt-up. Any sentiment test must
  verify the instrument FIRST (vault `concepts/the-method`: the instrument
  is the first suspect).

## Standards binding every test

- Cost bar: **43 bps (distinguishable) / 118 bps (point-estimate) round
  trip** per `docs/quant/2026-08-22_walkforward_resampling_tranche2.md`. A
  "pass" that nets under 43 bps is a detection curiosity, not P&L.
- Effective n, not row count, on overlapping/concurrent windows
  (gate_truth_report standard; SE on nominal n is optimistic by
  sqrt(n/n_eff)).
- Shuffle nulls follow the OF-2 pattern; nothing is judged by argmax
  (OF-4 discipline).
- One number from one tool is a hypothesis — cross-derive load-bearing
  counts (USAGE.md rule e).

---

## Tests runnable NOW

### T1 — adverse-selection decomposition of our fills [retail-adverse-selection-1, retail-base-rate-2]
**Hypothesis:** Our resting fills hit during attention/volatility spikes show
worse short-horizon post-fill drift than fills on quiet tape (we are
sometimes the picked-off stale order, per Linnainmaa, not always the
harvesting maker).
**Measurement:** From the fill ledger (core/fill_ledger.py schema), tag each
era-4 entry fill with tape state at fill (realized-range z and taker-volume z
from stored candles/books); compare post-fill drift at 5m/30m/2h between
spike-tagged and quiet-tagged fills. n=54 closed trips — report effective n;
sign only, no magnitude claims.
**Pass/fail:** Sign check only. If spike-tagged fills drift adversely by more
than the 43 bps bar relative to quiet fills, the amended claim's ~27%
harvestable-pool model is live for us; if not distinguishable at n=54, record
UNDERPOWERED, not null.
**Class:** SAFE.

### T2 — maker fraction and counterfactual taker cost [gov-fee-1, gov-fee-2]
**Hypothesis:** OM-011 limit-entry-only keeps our realized fee tier at/below
40 bps maker; the counterfactual taker book at 80 bps would deepen the WHY-1
deficit.
**Measurement:** Fill-ledger maker/taker flags; recompute era-4 fee total at
80 bps taker counterfactual via scripts/cost_attribution.py output (instrument
caveat: cost_attribution.py once hard-coded a struck fee schedule — verify
its tier table against the live 40/80 bps reality before trusting output;
the-method).
**Pass/fail:** Maker fraction ≥ target implied by OM-011 (entries 100% maker
by construction — any taker-flagged entry is a defect finding, not a tuning
input). Counterfactual delta reported in bps against the 43/118 bar.
**Class:** SAFE.

### T3 — wash-trading instruments on our read-only venues [gov-wash-1]
**Hypothesis:** OKX/Binance.US trade prints deviate from Benford
first-significant-digit and trade-size clustering/roundness norms relative to
Kraken as regulated baseline (Cong et al. 2023 instruments).
**Measurement:** Benford first-digit chi-square, round-size clustering share,
power-law tail exponent on stored trade prints per venue; Kraken = control.
**Pass/fail:** Not a P&L bar — an instrument-trust result: a venue failing
the tests gets its book/volume features tagged lower-trust (scope note for
regime/liquidity_regime.py imbalance features; also gov-pfof-1's
depth-understatement caveat). No decisioning change.
**Class:** SAFE.

### T4 — Kraken listing event study [gov-list-1]
**Hypothesis:** Newly listed pairs (SUI/ARB/MINA/FLOW have stored Kraken
candle history) show positive day-0 abnormal return then fade below the
post-listing pump (lit: +5.7% day-0, +9.2% -3/+3; 98% later trade below
pump).
**Measurement:** Event study on listing dates vs stored candles; abnormal
return vs matched non-event windows; n is tiny (4 events) — report as
anecdote-grade, effective n stated.
**Pass/fail:** Day-0 move > 118 bps would nominally clear the point-estimate
bar, BUT chasing it is taker behavior the invariants forbid — record the
number, tag NOT executable under OM-011.
**Class:** SAFE.

### T5 — price-chasing flow proxy [retail-crypto-lossrate-3]
**Hypothesis:** Taker volume on our feeds is a lagging function of trailing
return sign (retail entry chases price).
**Measurement:** Cross-correlate Kraken/Binance.US volume (and our
candidate-flow density from outputs/signal_history.csv, ~18k rows) with
trailing k-bar return sign; lead-lag profile.
**Pass/fail:** Positive lag-side correlation with lead-side ~0 confirms the
shape. Context claim only — no bps bar applies; feeds no gate.
**Class:** SAFE.

### T6 — MAX-decile lottery spread on our universe [retail-lottery-skew-5]
**Hypothesis:** Sign dispute (weekly +3.03% vs intraday -4.3 bps/sd) resolves
on our universe at our horizons — likely UNDERPOWERED, which is itself the
finding.
**Measurement:** Rank tradeable universe by trailing-month MAX; next-week
return spread high-minus-low; single-digit cross-section — effective n
reported per gate_truth_report standard.
**Pass/fail:** Only a spread whose CI clears 43 bps/week net of 40/80 fees
counts as monetizable; the intraday 4.3 bps effect is pre-tagged NOT
monetizable. Expected outcome: UNDERPOWERED — record it, do not tune on it.
**Class:** SAFE.

### T7 — mechanical disposition ratio re-run [retail-geometric-vs-psych-8]
**Hypothesis:** The behavioral-isomorphism result (58.3% win rate, 0.670
payoff ratio, 2.20x disposition, zero emotion machinery) is stable under
cut-#7 geometry.
**Measurement:** Re-run the replay-A/B harness on the current era-4 recording
(gotchas documented in memory rev5-adaptive-layer); recompute the disposition
ratio.
**Pass/fail:** Ratio within the prior measurement's spread = isomorphism
holds; a large shift = geometry change moved the signature (expected per the
cut-#7 lesson) — file to vault behavioral-isomorphism either way.
**Class:** SAFE (replay only).

### T8 — regime-conditioned magnet-touch behavior [retail-crypto-disposition-9]
**Hypothesis:** In bear-regime windows, price-magnet touches (stale-inventory
capitulation zones) show different resolution than in bull windows
(regime-flipped disposition).
**Measurement:** Regime-tag stored candles (existing regime layer);
conditional forward return/range after magnet touches from book snapshots.
**Pass/fail:** Detection-target result only — cascade-adjacent harvesting
needs ATTR-2 to time; no bps pass possible yet. Record conditional
distributions.
**Class:** SAFE.

### T9 — round-number stop-cluster event study, AMENDED sign structure [stop-cluster-1]
**Hypothesis:** Kraken spot 1m candles show (a) bounce/stall ON round numbers
(take-profit clustering) and (b) acceleration just BEYOND them (stop
clustering: sells below, buys above) — the amended placement asymmetry, at
HOURLY horizons per SR150.
**Measurement:** Conditional forward return / range expansion at x.00/x.50
levels per asset tick regime vs matched non-round levels; OF-2 shuffle null;
effective n on overlapping windows; validate under scripts/overfit_check.py
battery (read the corpus line — synthetic substitution tell).
**Pass/fail:** Breach-side move must net > 43 bps after 40/80 fees at a
resting-limit-reachable entry to be monetizable; anything smaller = detection
result feeding TH-013 context only. **Any entry-placement change from this is
COHORT-RESETTING — operator adjudication required.**
**Class:** SAFE as measurement; acting on it is NOT.

### T10 — taker-flow variance compression [cascade-ews-1]
**Hypothesis:** Rolling variance of taker-proxy flow (event-based OFI,
ml/features.py:100-101) compresses before large realized-range expansions on
our spot feeds (6/7-event regularity, Kendall-tau -0.13 to -0.44 in the
source).
**Measurement:** Rolling OFI variance on recorded Kraken/Binance.US books;
Kendall-tau of variance trend pre-onset vs 300-onset placebo set (paper's
own placebo design); note exogenous-shock events carry no precursor by
construction.
**Pass/fail:** Shadow-detector standard, not bps: replicated compression at
placebo-beating significance earns a THALES-style shadow slot
(shade-down/stand-aside semantics only, never entry). Full replication needs
perp taker + OI (ATTR-2).
**Class:** SAFE (shadow only).

### T11 — wick-termination beyond swing extremes, mechanical form only [stophunt-folklore-1]
**Hypothesis (mechanical, non-intent):** Kraken spot wicks disproportionately
terminate just beyond prior swing extremes then revert, vs shuffle null.
**Measurement:** Wick-extreme distances to prior swing highs/lows; reversion
incidence; OF-2-style shuffle null. Intent attribution is NOT testable with
any feed we can add (TH-017 identifiability wall) — do not attempt it.
**Pass/fail:** Reversion after beyond-extreme termination must net > 43 bps
to matter; otherwise files as a D-grade folklore partial-corroboration.
Detection-only per compliance fence.
**Class:** SAFE.

### T12 — funding extremes vs forward spot returns [carry-decay-1, funding-cond-1, gov-fund-1]
**Hypothesis:** Recorded OKX funding extremes (crowded-side proxy) precede
adverse forward Kraken spot returns at 1h-24h horizons (slight
mean-reversion direction per industry backtests; no peer-reviewed effect size
exists — we are producing the first number we can trust).
**Measurement:** Recorded funding_rate history (okx_feed.py:168-201;
funding_dir already in the vector, ml/features.py:384) vs forward returns,
effective-n corrected; LS-1-style importance verification before any
promotion talk.
**Pass/fail:** Conditional return delta must clear 43 bps at our holding
horizon to be more than a stand-aside flag. **Any gate_4 threshold retune is
gate-widening territory: full overfit battery + quant-trial G3/G5, and
likely COHORT-RESETTING.**
**Class:** SAFE as measurement.

### T13 — funding cross-venue instrument check [funding-structure-1]
**Hypothesis:** OKX funding is representative of market-wide positioning
(two-tier structure: deep venues lead).
**Measurement:** Correlate OKX funding vs a second read-only venue's funding
via data/ccxt_feed.py for a bounded sample. Instrument verification per
the-method — runs BEFORE trusting T12.
**Pass/fail:** High correlation validates single-source design; low
correlation quarantines every funding-conditioned result above. Also file
the named quiet degrade: gate_4 fail-open on venue outage reads as "no
funding constraint" — owed a telemetry counter (measurement-plane).
**Class:** SAFE.

### T14 — post-cascade reversion measurement [postcascade-rev-1, liq-asym-1, gov-liq-2]
**Hypothesis:** Extreme down-range bars (forced-flow proxy without a
liquidation feed) are followed by positive forward returns exceeding costs —
the only cascade-linked edge our venue can execute.
**Measurement:** SAFE-class script: z-scored range + volume identifies
extreme down bars in recorded Kraken candles; event-study forward returns at
15m/1h/4h/24h; OF-2 shuffle null; effective n on overlapping windows.
**Pass/fail:** Mean bounce must clear **43 bps (distinguishable) / 118 bps
(point-estimate)** net of 40/80 fees at the horizon a resting bid can
realistically capture. Under 43 bps = detection curiosity (WHY-1 cost-bound
lesson). Trigger fidelity upgrade needs ATTR-2. **Acting on it =
COHORT-RESETTING, operator-adjudicated.**
**Class:** SAFE as measurement.

### T15 — sentiment: instrument first, then signal [attr1-design-1, sent-ret-1, sent-ret-2]
**T15a (instrument):** Replay the 2026-08-20 archived headlines through
sentiment/lexicon.py score_text; inspect per_source/volume_z
(scanner.py:57-63). Separates "lexicon blind to policy vocabulary" from
"feeds returned nothing" — currently the SAME OBSERVATION; establish which.
**T15b (signal, only after 15a):** Lagged IC / daily OOS R² of recorded
SentimentSnapshot.score (scanner.py:54-64) vs forward returns, judged vs the
simplicity ladder + OF-2 shuffle null, never argmax.
**Pass/fail:** A null in 15b indicts OUR instrument, not the hypothesis (our
RSS/HN proxy is not the platform-native channel any study measured).
Amended-claim priors: best-replicated horizon is <=15 min (Guegan & Renault
2021) and post-bubble regimes show lag-2 reversal (S_t-2 = -0.2031, p=0.008)
— test the reversal sign, not just level prediction. Deployment path (if
ever) requires OF-1..7 green with real corpus + the 43-118 bps bar + the
freeze lifted.
**Class:** SAFE.

### T16 — divergence flag vs pump-aftermath reversion [pnd-wealth-1]
**Hypothesis:** Firings of the cross-venue divergence flag (main.py:292-313)
coincide with transient distortions that subsequently revert (pump-aftermath
shape on thin alts).
**Measurement:** Correlate recorded flag firings with subsequent reversion
magnitude/half-life in recorded feeds.
**Pass/fail:** Reversion net of fees vs 43 bps bar; sub-bar results file as
detector validation only (the flag becomes a corroborated instrument even if
untradeable).
**Class:** SAFE.

### T17 — euphoria_spike vs subsequent adverse selection [enforce-1]
**Hypothesis:** euphoria_spike (scanner.py:60) events coincide with
subsequent adverse selection on our fills (attention spike preceding
distribution — the influencer/pump signature's spot shadow).
**Measurement:** Join euphoria_spike timestamps against fill-ledger post-fill
drift; note the instrument caveat (same defective scanner as ATTR-1 — T15a
gates this test too).
**Pass/fail:** Sign-only at current n; any effect is a shade-down candidate,
never entry. No bps pass available at n=54.
**Class:** SAFE.

### T18 — manipulation base-rate trend [gov-enforce-1]
**Hypothesis:** Rational-choice prediction: post-2024 enforcement retreat ->
rising manipulation footprint -> manip_suspect composite and SZ-045 refusal
rate (454 stamped as of 2026-08-21) trend UP across eras.
**Measurement:** Era-bucketed trend of manip_suspect and SZ-045 rate from
outputs/signal_history.csv veto codes + audit trail. **Instrument caveat is
binding:** manip_suspect has no smoothing (lag-1 autocorr 0.06; a single
read was once taken for a trend that measured rho=+0.007) — add smoothing to
the READER, never the signal.
**Pass/fail:** Monotone era-over-era rise beyond the smoothed series' noise
band = RCT prediction corroborated; flat/down = filed against the criminology
lens. Context only; no bps bar.
**Class:** SAFE.

### T19 — counterparty-pool stationarity [retail-learning-failure-4]
**Hypothesis:** The re-supplied loser pool's aggregate behavior is stationary
on our corpus: adverse-selection markers on our fills (T1) and THALES
lazy-bot footprint rates are stable across era boundaries rather than
decaying.
**Measurement:** Era-bucketed T1 markers + THALES shadow-record footprint
rates (vault entities/thales-engine.md) across label_era buckets in
signal_history.csv.
**Pass/fail:** Stability = the load-bearing patient-capital assumption holds
on our sample; decay = the 2026-crypto stationarity transfer (grade D in the
amended claim) is failing and the who-loses-to-us durability page gets a
same-session callout, both sides.
**Class:** SAFE.

### T20 — attention->volatility leg, bot-free proxy [bot-flow-1]
**Hypothesis:** HN story-volume z (scanner.py:22-24) — a bot-free attention
proxy — leads realized volatility on our recorded feeds (tests the
attention->volatility leg of the PNAS bridge only; the bot leg needs a
platform feed).
**Measurement:** Lead-lag of HN volume z vs realized range on stored candles.
**Pass/fail:** Context claim; no bps bar. A positive lead corroborates the
bridge's carrying leg on our corpus; null is uninformative about bots
(proxy limitation stated up front).
**Class:** SAFE.

---

## OWED DATA — claims not testable with current data

The dominant gap is **ATTR-2 (docs/HANDOFF.md lines 97-116): zero
liquidation / open-interest awareness.** One feed adoption tests many claims.

| Missing feed | Unblocks claims | Candidate source | Notes |
|---|---|---|---|
| Liquidation events + OI (perps) | gov-offshore-1, gov-mica-1, gov-liq-1, gov-liq-2, liq-asym-1, retail-leverage-drain-6, funding-cond-1 (OI interaction), postcascade-rev-1 (trigger fidelity), retail-crypto-disposition-9 (capitulation timing) | OKX read-only public liquidation-orders + OI endpoints beside get_funding_rate (data/okx_feed.py:168-201); CoinGlass-class aggregate as secondary | SAFE-class ingest; already a read-only venue; the single highest-leverage adoption in this folder |
| Insurance-fund balance series | gov-liq-1 | BitMEX publishes daily fund balances | Read-only context feed |
| Platform-native sentiment (X/StockTwits/Telegram) with bullishness ratio + bot-share filter | bot-prev-1, retail-attention-buying-7, sent-ret-1/2 (proper test), bot-flow-1 (bot leg), pnas-shape-1, attr1-design-1 (the fix) | Per the design claim: platform-native text, hourly-to-2-day, validated against known attention events (2026-08-20 melt-up as first fixture) before any gate consumes it | Extends ATTR-1; feed upgrade is SAFE until it touches sizing |
| ETF net-flow daily calendar | gov-etf-1; partially patches ATTR-1 news blindness | Public daily spot-ETF flow data | Context-calendar input |
| Stablecoin issuance/reserves | gov-stablecoin-1 | None planned; USDT/USD Kraken basis as weak stress proxy only | Fiscal claim untestable on our corpus |
| Social graph / bot classification | pnas-shape-1 hub-targeting leg | None planned | Owed literature pass first |
| Exchange account panels (counterparty P&L, learning curves) | retail-base-rate-2, retail-learning-failure-4 direct form, gov-retail-1 | **Never available to us** | Permanently indirect — proxies T1/T19 only |
| On-chain flows | retail-crypto-disposition-9 on-chain form | None planned | — |
| Political-finance / licensing / adoption feeds | gov-lobby-1, gov-mica-1 economics, retail-crypto-lossrate-3 direct | Out of scope for the trading loop | Context only |

---

## PRE-REGISTERED FEATURE CANDIDATES — boundary adjudication docket

**FORBIDDEN to implement under the 2026-08-10 freeze. Registered here so the
next execution-era boundary adjudication has a pre-named menu instead of a
tuning session. Every candidate that shapes entries/exits/sizing is
COHORT-RESETTING by definition.**

| Feature candidate | Source claims | Expected sign | Cost-bar note |
|---|---|---|---|
| Post-cascade reversion accumulation (resting bids after extreme forced-flow bars, exits via ProfitTierEngine) | postcascade-rev-1, liq-asym-1, gov-liq-2, retail-leverage-drain-6 | Long after down-flush; bounce positive at 15m-24h | Must measure > 43 bps (distinguishable) net at T14 before docketing; 118 bps for point-estimate confidence |
| Round-number cluster-aware entry placement (rest just beyond stop clusters, per amended placement asymmetry) | stop-cluster-1 | Acceleration through breached clusters; bounce ON round levels | Hourly-horizon effect; T9 must clear 43 bps at a reachable resting price; COHORT-RESETTING |
| OFI variance-compression shade-down (THALES-style shadow detector -> stand-aside semantics) | cascade-ews-1 | Compression precedes range expansion; NO directional content; misses exogenous shocks by construction | Defensive — no bps bar; promotion needs shadow evidence per THALES ladder |
| Funding-extreme crowding flag (stand-aside / shade, OI-conditional once ATTR-2 lands) | funding-cond-1, carry-decay-1, gov-fund-1, funding-structure-1 | Extreme positive funding -> crowded longs -> adverse/volatile forward window | Effect likely < 43 bps directionally; value is risk-shading, not entry; gate_4 retune = full battery + G3/G5 |
| Offshore-cascade precursor context (OKX liquidation/OI burst precedes Kraken spot dislocation) | gov-offshore-1, gov-mica-1, liq-asym-1 | Offshore burst leads onshore dislocation | Only dislocations > 43-118 bps count as tradable endpoints; feed adoption itself is SAFE |
| Pre-pump accumulation detector (volume/quote anomalies before news; detection-only) | pnd-anatomy-1, pnd-wealth-1 | Anomalous accumulation precedes announcement spike | NOT monetizable (18 s window « our cadence, thin non-Kraken alts); THALES shadow slot only |
| Venue-trust discount on book/volume features (wash-trading instrument scores) | gov-wash-1, gov-pfof-1 | Failing venue -> lower feature trust | No bps bar; measurement-trust weighting, not a signal |
| Platform-native sentiment feature, reversal-aware (post-bubble lag-2 reversal sign) | sent-ret-1, sent-ret-2, attr1-design-1, bot-flow-1 | Post-bubble regime: sentiment spike -> lag-2 reversal (fade, not follow) | D-grade at our horizon (best-replicated <=15 min); requires ATTR-1 feed fix + T15 + OF-1..7 before docketing |
| Attention-contagion detector (major-coin news -> thin-alt volume, piggyback shape) | pnas-shape-1, retail-attention-buying-7 | Cross-asset attention burst precedes thin-alt flow | Partial-reversal caveat: fading indiscriminately is negative-EV; admission via priced adverse selection only |

**Standing close:** every green above is only as big as its corpus (n=54
closed trips, ~18k candidate rows, single 2026 regime). What these tests
cannot see: counterparty identity, perp-side state (until ATTR-2),
platform-native sentiment (until ATTR-1 fix), and any multi-week narrative
structure (corpus too small — narrative-1). Degraded gates get said out
loud, not floored over.
