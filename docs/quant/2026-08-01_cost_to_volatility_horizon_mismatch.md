# The barriers are 4x too wide for the horizon — and the cost floor forces it

**Date:** 2026-08-01 · **Status:** MEASURED, no change shipped yet
**Class:** strategy economics (TANK C4/C5 — labeling verdict) · **Trigger:**
operator ask, "look at peer-reviewed examples and the improvement timeline"

---

## The measurement

Current era `triple_barrier_h24`, 606 rows (599 candidate, 7 live):

| quantity | value |
|---|---|
| horizon | 24 bars x 5 min = **2 hours** |
| PT distance (median) | **2.058%** (min 2.000%) |
| SL distance (median) | **1.543%** (min 1.500%) |
| `sigma_bar_pct` (median) | 0.1241% |
| horizon sigma = `sigma_bar * sqrt(24)` | **0.608%** |
| **PT / horizon-sigma** | **3.39** |
| **SL / horizon-sigma** | **2.54** |
| outcome mix | **87.8% time · 8.6% SL · 3.6% PT** |

The minima (2.000 / 1.500) sit exactly on the cost floor, so the floor is
binding on essentially every row: the geometry is **cost-scaled, not
volatility-scaled**, which is the opposite of what the method assumes.

`barrier_geometry()` (`ml/labeling.py:33`) floors the sigma INPUT at
`label_pt_cost_mult * cost / pt_mult` = `4.0 * 0.5% / 1.0` = **2.0%**.
Config: `ml.label_pt_cost_mult = 4.0`, `ml.label_round_trip_cost_pct = 0.5`.

## Comparison to the literature

Peer-reviewed triple-barrier work that reports usable label balance places
the barriers at **roughly 0.8-1.0 horizon-sigma**:

- **Korean markets, arXiv 2504.02249** — 29-day window, 9% barrier width,
  parameters explicitly optimized *for balanced label proportions*. At ~2%
  daily vol, 9 / (2*sqrt(29)) = **0.83 sigma**.
- **Financial Innovation 11(1), 2025** (crypto, BTC/ETH, information-driven
  bars) — reports **36.16% time / 34.89% PT / 28.95% SL**, and calls the
  balance "crucial for training robust models."

We are at **3.39 sigma** and **87.8% time-outs**. Four times too wide.

## The finding underneath the finding

This is not a labeling bug. Put the two numbers side by side:

```
round-trip cost      0.50%   (maker 25bps x 2; config pretrade/order_manager)
2-hour sigma         0.61%
cost / sigma         0.82
```

**We pay 82% of one standard deviation in fees per round trip.** No signal
survives that. Every downstream symptom — the degenerate labels, the low
win rate, the negative edge, the model losing to a base-rate null — is
this ratio expressed in a different unit.

The cost floor is not the villain; it is the messenger. It exists because
sigma-scaled barriers at 5m vol would put PT *inside* the cost band, making
the average bet EV-negative regardless of signal (spec D2, 2026-07-27). The
floor correctly refuses to label an unprofitable bet as winnable. What it
reveals is that **at a 2-hour horizon, on these pairs, at these fees, there
is no profitable bracket to label.**

Solving for the horizon where costs stop dominating:

| target cost/sigma | required H | holding period |
|---|---|---|
| 0.82 (today) | 24 bars | 2 hours |
| 0.20 | 405 bars | **~34 hours** |
| 0.10 | 1,622 bars | **~5.6 days** |

> **CORRECTION 2026-08-16 — this paragraph was wrong, and it propagated.**
> It originally read: *"At 10bps/side instead of 25 (a Kraken volume tier),
> cost/sigma = 0.2 needs only H = 65 bars (5.4 hours)."* **No 10bps Kraken
> tier exists.** The parenthetical asserted one with no citation and was
> later filed into the vault as knowledge.
>
> The schedule was already triple-confirmed in the vault on 2026-08-07
> (`sources/session-20260807-institutional-review` §C): Tier 1 ($0+)
> **40/80**, Tier 2 30/60, Tier 3 22/38, **Tier 5 ($50k+) ~15/30 is the
> deepest row.** At an $800 book the operator is **Tier 1**, so this
> document's 0.50% round trip UNDERSTATES the real cost: Tier 1
> maker/maker is 0.80% (cost/sigma **1.31**) and at the observed 60.6%
> taker share 1.285% (cost/sigma **2.11**).
>
> The fee lever is real but roughly HALF the size claimed here, and every
> horizon figure below is correspondingly optimistic.

## Is the labeled bet worse than chance?

For a driftless walk with barriers at +a / -b, gambler's ruin gives
P(hit PT first) = b/(a+b) = 1.543/3.601 = **42.9%**.

Observed among the 74 **resolved** rows: 22 PT / 52 SL = **29.7%**
(z = -2.28, p ~ 0.02).

**Scope, stated precisely:** all 74 resolved rows are *candidate*
(simulated) rows. The 7 live rows in this era have **zero** resolutions —
every one timed out. So this measures the **labeled bet**, not live
execution, and it says the signal selection is anti-predictive at this
geometry rather than merely uninformative. It is one test at n=74 on a
selected sample; it is a flag, not a verdict.

## Caveat on the sigma estimate

Under a Gaussian walk, barriers at 3.39 sigma would produce a PT-touch rate
near 0.07%; we observe 3.6%, ~50x higher. So `sigma_bar_pct` understates the
distance actually travelled — expected, since barriers are touched by
intrabar highs/lows and crypto returns are fat-tailed. The **ratio**
comparisons above (3.39 vs ~0.8 literature; cost/sigma 0.82) are unaffected
in direction, and the 87.8% time-out rate is a direct observation that needs
no model at all. Do not quote the Gaussian touch probability as a prediction.

## What this does NOT say

- It does not say the triple-barrier method is wrong. The method is fine;
  our parameterization is outside the range where it produces information.
- It does not say to widen `label_max_bars` and move on. Lengthening the
  horizon changes what strategy this is (2 hours -> 1.5 days), which is an
  operator decision about the product, not a tuning knob.
- It does not blame the 07-31 horizon change (96 -> 24). At 96 bars the
  ratio was 2.058 / (0.1241*sqrt(96)) = **1.69** — better, still 2x the
  literature, and it carried the clock-inversion deadlock. Neither setting
  was in range.

## The three real options

1. **Lengthen the horizon** to ~400 bars (~34h) and keep the current
   barriers. Makes this a swing strategy; label rate falls; corpus growth
   slows further.
2. **Cut the cost stack** — maker-only entries and exits, fee-tier work,
   tighter spread gating — so the floor drops and barriers can come in to
   ~0.6%. Preserves the intraday character; hardest to execute.
3. **Select for volatility** — only trade names/regimes where `sigma_bar`
   is high enough that a 2h horizon clears the floor. `sigma_bar` p90 is
   0.2242%, which gives a 2h sigma of 1.10% and cost/sigma of 0.46 —
   better, still not good.

These are not exclusive, and (2)+(3) together are roughly equivalent to (1)
in effect. **This needs the argue/debate/vote the operator asked for before
anything ships** — it is the money path and it redefines the product.

## Sources

- Gârleanu & Pedersen, "Dynamic Trading with Predictable Returns and
  Transaction Costs," *Journal of Finance* 68(6), 2013, 2309-2340 —
  optimal trading intensity is set by the cost-to-risk ratio; "aim in front
  of the target, trade partially toward the aim."
- "Stock Price Prediction Using Triple Barrier Labeling and Raw OHLCV
  Data: Evidence from Korean Markets," arXiv:2504.02249.
- "Algorithmic crypto trading using information-driven bars, triple barrier
  labeling and deep learning," *Financial Innovation* 11(1), 2025.
- López de Prado, *Advances in Financial Machine Learning*, ch. 3
  (triple-barrier, meta-labeling), ch. 4 (uniqueness) — already the basis
  of this repo's labeler.
