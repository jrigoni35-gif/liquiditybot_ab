# Signal alpha decay μ₀τ vs the round trip 2c: independent panel + the bot's signals (2026-10-02)

**Class: SAFE** (measurement only; no order, size, stop or fill change; no
decision-module file touched). Tool: `scripts/alpha_decay_report.py`; pins:
`tests/test_alpha_decay_report.py` (11, mutation-verified). Run
2026-10-02T00:43Z; JSON `outputs/reports/alpha_decay/alpha_decay_*.json`.
Numbers are AS-OF; re-derive with `python scripts/alpha_decay_report.py`.

## 1. Question (operator, verbatim intent)

> "Do it to institutional grade and take unbiased experiences into play. Do
> not only base this off the bot's findings because we are doing this for
> the bot."

Fixed-endpoint action argument (session 2026-10-01): a round trip pinned to
the market at entry A and exit B has positive action only if the signal's
total edge **μ₀τ exceeds the round trip 2c**, whatever the timing. This
record measures μ₀τ.

## 2. Registration (before data) and the two disclosed amendments

Registered in the tool's docstring before the first run: drift-adjusted
CAR(h) = A(1 − e^(−h/τ)), A = μ₀τ; week-block bootstrap (overlapping
windows), 2,000 reps, fit redone per rep; tradeable ⇔ CI95_low(A) > 2c =
45 bps (Kraken Tier 5, 15 + 30), both halves > 2c, Holm across the family;
sensitivity 30 / 65 bps. External priors (not the bot's): one-week TSMOM
(Liu & Tsyvinski, RFS 2021), large-cap daily momentum, BTC 1–4 h large-move
reversal, reversal after aggressive taker flow, cross-sectional momentum.
Independent panel: Binance 1h 2023-01..2026-08, the 20 largest non-stable
assets on 2023-01-01, no survivorship cut.

- **Amendment 1** (after the first smoke run, before any decision read): the
  τ grid ran to 31.6 × h_max and extrapolated A to ±2,000 bps from CARs that
  never exceeded 45 bps. τ bounded to [h_min/2, h_max]. Instrument defect.
- **Amendment 2** (after the first full run): the aligner priced each bot row
  at the close of the bar ENDING at `signal_ts`. `signal_ts` is a bar-OPEN
  stamp; the bot acts at that bar's close. The bot's own `entry_price`
  matches the close of the bar STARTING at `signal_ts` 3–6× better (median
  |gap| BTC 27.8 → 9.2, ETH 13.8 → 4.4, SOL 31.2 → 6.0 bps; all rows 11.1 →
  4.0). The first run's "+8 bps at τ 0.1 h" was look-ahead created by the
  instrument, not edge. Fixed and pinned.

## 3. Instrument controls (all before any reading)

| control | result | reading |
|---|---|---|
| GBM null, 10 reps × 5 signals | 0 / 50 upward CIs exclude 0 | conservative |
| time-shuffle null, 10 × 5 | 4 / 50 (8%) | within chance of 5% (binomial p ≈ 0.24) |
| planted A = 60 bps, τ = 24 h | Â 61.4 [47.6, 76.1], τ̂ 24.2 h | recovered |
| look-ahead | 3 mutants (quantile, rolling σ, momentum lag) each turn a pin red | pinned |
| Binance ms → µs (2025) | per-value unit normalisation, counted | pinned |
| cross-venue (bot rows) | BTC A Binance +2.4 vs Coinbase +2.3; ETH +1.1 vs +1.0 bps | venue-independent |

## 4. Independent panel — signals the bot did not make, on prices it did not record

| signal (prior) | events | weeks | A = μ₀τ (bps) | τ (h) | halves | verdict |
|---|---|---|---|---|---|---|
| tsmom_168 (+) | 609,876 | 188 | +2.3 [−55.0, +57.2] | 7.2 | +1.0 / +5.7 | NO EDGE |
| tsmom_24 (+) | 607,972 | 188 | −1.1 [−23.5, +26.5] | 1.9 | −0.6 / −1.8 | NO EDGE |
| rev_large (+) | 33,051 | 188 | −0.3 [−41.0, +28.3] | 0.5 | +3.8 / −4.4 | NO EDGE |
| flow_rev (+) | 51,790 | 188 | −41.1 [−78.1, +1.4] | 168 | −50.5 / −29.6 | NO EDGE (sign opposite to prior) |
| xs_mom_168 (+) | 376,967 | 188 | +1.8 [−21.0, +27.8] | 43.2 | +0.2 / +12.1 | NO EDGE |

Every drift-adjusted CAR is within ±5 bps through 24 h. None of the five
literature priors carries a round trip at Kraken costs over 2023–2026. The
flow-reversal prior points the wrong way (flow tends to CONTINUE over 2–7
days) but does not clear 95% — a post-hoc hypothesis, not a finding.

## 5. The bot's signals on independent prices (CS-1)

`counting CS-1: n=35442 = used=35354 + asset_not_on_binance=0 +
outside_price_data=88 + no_direction=0 [OK]`. Decision cohorts pooled on
purpose (a signal-quality measurement, not a cohort read; 34,318 legacy
rows). **13 weekly clusters only** — the bootstrap is fragile at that n.

| signal | events | A raw (bps) | halves | A market-relative (bps) | halves |
|---|---|---|---|---|---|
| B1 all candidates | 34,832 | +69.7 [+0.8, +198.4] | +1.1 / +126.6 | **+3.9 [−55.5, +90.5]** | −29.9 / +66.9 |
| B2 live (taken) | 521 | −25.2 [−78.5, +42.6] | +1.9 / −17.1 | −0.7 [−86.6, +9.4] | +6.6 / −77.9 |
| B3 top-third confidence | 11,710 | +178.7 [+1.1, +288.0] | +49.4 / +149.2 | **+38.1 [−45.1, +125.5]** | −35.6 / +101.0 |

**Reverse-engineered:** the raw edge is MARKET TIMING concentrated in one
half of a 13-week window. Subtract the equal-weight market's move at the
same bar and B1's edge falls to +2.3 bps at 24 h (raw: +35.2) — the bot is
not choosing assets that beat the market; it was long-biased (21,810 long
vs 13,632 short rows) while the market moved its way in the second half.
The taken trades (B2) show no edge either way.

Exploratory (18 feature signs, Holm within, never a decision): the large
raw A values (`ret_48_dir` +135.6, `ret_12_dir` +113.7, `imbalance_dir`
+298.5) are the same momentum/timing exposure in the same 13 weeks. The
independent panel's 3.7-year TSMOM, the out-of-window version of the
same idea, reads +2.3 bps. One regime is not evidence.

## 6. Answer

**No signal measured clears μ₀τ > 2c = 45 bps at 95%** — not the five
literature priors on 3.7 years and 20 assets, and not the bot's own
signals. The only CI that clears zero (bot raw timing) is (a) one regime,
(b) gone once the market's move is removed, and (c) its lower bound
(+0.8, +1.1 bps) is 44 bps short of a round trip. In the action language:
the force term V′ = μ − γσ²x carries no measurable μ for asset selection
at any horizon to 72 h, so the stationary path between any A and B is
flat; every trip on these signals is a paid detour.

## 7. What this means for the bot (operator decisions, nothing armed)

1. **The trip book cannot be fixed by exit timing, fee tier or band width**
   while μ₀τ < 2c — Law 2 of the fixed-endpoint argument. The levers left
   are the signal (μ₀τ) or the trip count.
2. **Register forward, do not retune:** the one candidate worth a
   pre-registered out-of-sample read is B3's TIMING component (raw), frozen
   as defined here, read on the next ≥ 13 weeks with this tool. If timing
   is the edge, the cheapest way to express it is not round trips but a
   holding tilt (`core/target_book.py`, which pays no exit toll per idea).
3. **Exploration probes are tuition, not trades:** at μ₀τ ≈ 0 each probe
   costs ≈ 2c. That is the moratorium's priced H0, now confirmed on
   independent prices.
4. **Flow continuation** (flow_rev reversed) is a post-hoc hypothesis: test
   it only on data after 2026-08 (unseen by the panel), registered first.

## 8. Limits

13 weekly clusters for the bot (fragile CIs); bot horizon capped at 72 h;
Binance USDT, not Kraken USD (cross-venue agreement to 0.1 bps on BTC/ETH
says this does not matter here); the 2023-01 top-20 list was set from
memory of the public ranking; costs exclude spread (≈1 bp on majors) and
impact (none at $60).

Sources for the priors: Liu & Tsyvinski, *Risks and Returns of
Cryptocurrency*, RFS 34(6) 2021 (https://nber.org/papers/w24877); *Up or
down? Short-term reversal, momentum, and liquidity effects in cryptocurrency
markets* (https://earsiv.medeniyet.edu.tr/items/23a96c9f-3952-4bdf-aec5-abafb3aaab70);
*Bitcoin intraday time series momentum*
(https://research.birmingham.ac.uk/en/publications/bitcoin-intraday-time-series-momentum/);
*Short-horizon mean reversion in cryptocurrency markets*
(https://arxiv.org/pdf/2608.21888).
