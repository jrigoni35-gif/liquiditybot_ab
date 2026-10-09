---
title: Cost-to-Volatility Horizon Mismatch (2026-08-01)
category: source
summary: With the new 24-bar era in place the barriers measure 3.39 horizon-sigma against a literature norm of ~0.8, because round-trip cost is 82% of one 2-hour standard deviation
tags: [cost, volatility, labeling, economics, money-path]
sources: 2
updated: 2026-08-16
---

# Cost-to-Volatility Horizon Mismatch (2026-08-01)

**Raw source:** `raw/quant/2026-08-01_cost_to_volatility_horizon_mismatch.md`

**Status: MEASURED, nothing shipped** at the time of writing. This is the money-path document.

> ⚠️ **Superseded in part, 2026-08-02** ([[sources/session-20260802-digest]]):
> (1) "The three options, none taken" lasted one day — option 1 shipped 2026-08-01 as the 432-bar
> migration (commit `7566ea88`), pre-registered to n=50 and holding at 6/50.
> (2) The headline "no signal survives 82%" is corrected: clean per-fill measurement shows the
> book loses even at zero fees (mean gross −0.0501%, post-quarantine n=217); the binding term is
> [[concepts/payoff-asymmetry]], and the fills this document's P&L context rested on carried 64
> fabricated rows. The corpus-side geometry measurements below (barrier width in horizon-sigma,
> outcome mix, cost floor binding) are label-corpus facts and stand.

## The measurement
Era `triple_barrier_h24`, 606 rows (599 candidate, 7 live), horizon 24 bars = 2 hours.
PT median **2.058%** (min 2.000%); SL median **1.543%** (min 1.500%); `sigma_bar_pct` median
**0.1241%**; horizon sigma = **0.608%**.

- **PT / horizon-sigma = 3.39**; SL / horizon-sigma = 2.54.
- Outcome mix **87.8% time / 8.6% SL / 3.6% PT**.
- Literature places barriers at roughly **0.8-1.0 horizon-sigma** with balanced outcome mixes
  (a crypto study reports 36.16% time / 34.89% PT / 28.95% SL). **"We are at 3.39 sigma and 87.8%
  time-outs. Four times too wide."**

The minima sit exactly on the cost floor, so **the floor binds on essentially every row: the geometry
is cost-scaled, not volatility-scaled — the opposite of what the method assumes.**

## The finding underneath the finding
Round-trip cost **0.50%** vs 2-hour sigma **0.61%** -> **cost/sigma = 0.82**.

> "We pay 82% of one standard deviation in fees per round trip. No signal survives that. Every
> downstream symptom — the degenerate labels, the low win rate, the negative edge, the model losing
> to a base-rate null — is this ratio expressed in a different unit."

See [[concepts/cost-to-volatility-ratio]].

## The cost floor is the messenger, not the villain
It exists because sigma-scaled barriers at 5m vol would put PT *inside* the cost band. "What it
reveals is that at a 2-hour horizon, on these pairs, at these fees, there is no profitable bracket to
label."

## Solving for a workable horizon
cost/sigma 0.82 -> 24 bars (today) | 0.20 -> **405 bars (~34h)** | 0.10 -> 1,622 bars (~5.6 days).
~~At **10 bps/side instead of 25**, cost/sigma 0.2 needs only **65 bars (5.4 hours)** — fee tier and
horizon trade off directly.~~

> [!error] **RETRACTED 2026-08-16 — THE 10 BPS TIER DOES NOT EXIST**
> The source doc's parenthetical *"(a Kraken volume tier)"* was **uncited** and is false at every
> volume. True schedule, triple-confirmed 2026-08-07 by three independent fetches
> ([[sources/session-20260807-institutional-review]] §C; [[concepts/cost-truth]] has carried it
> correctly since): **Tier 1 ($0+) 40/80 · Tier 2 30/60 · Tier 3 22/38 · Tier 5 ~15/30 is the
> DEEPEST row.** No 10 bps row exists.
>
> **The correction runs the WRONG WAY.** An **$800 book is Tier 1**, so `config.json`'s 25/40
> **UNDERSTATES** fees and every cost/sigma figure above is **optimistic**:
>
> | premise | round trip | cost/sigma | breakeven hit |
> |---|---:|---:|---:|
> | 25 bps maker/maker (as configured) | 0.50% | 0.82 | 0.567 |
> | **Tier 1 maker/maker (40 bps)** | **0.80%** | **1.31** | **0.650** |
> | **Tier 1 @ observed 60.6% taker** | **1.285%** | **2.11** | **0.784** |
> | zero fees | 0.00% | 0.00 | 0.4286 |
>
> **The "cut fees to reach a 5.4-hour hold" lever does not exist.** This page's *"fee tier and
> horizon trade off directly"* framing survives only in the direction that makes the problem
> WORSE. *(The 2026-08-16 correction pass landed on `concepts/cost-to-volatility-ratio` and on the
> repo doc, but NOT on this page — caught and closed by the 08-12..16 catch-up,
> [[sources/session-20260816-catchup-08-12-to-08-16]].)*

## Is the labeled bet worse than chance?
> [!error] RETRACTED 2026-08-16 — WRONG NULL, and the artifact exceeds the effect
> `b/(a+b)` is the first-passage probability for an **unbounded-time** walk. These labels are
> **censored at a vertical barrier**, and the profit target sits FARTHER out (a/b = 1.333) so it
> takes longer to reach — censoring removes PT-bound paths **preferentially**. Conditioning on
> resolution manufactures the negative sign.
> Correct driftless null by exact lattice DP (converges to 0.4286 at ~0% censoring, validating the
> method): 48.6% censoring → **0.3758**; **86.4% censoring → 0.2351**.
> This sample was **87.8% censored**, so against ~0.235 the observed **29.7% is ABOVE chance** and
> z flips from −2.28 to roughly **+1.7**. With the project's own effective-n standard applied, the
> pooled statistic across both horizons is **z = −0.63, p = 0.53**.
> **The labeled bet is indistinguishable from chance, not worse than it.** A residual h432 negative
> drift may exist (z = −1.47 at effective n) but is not significant, is measured on the fee-free
> candidate stream, and has never been shown to transfer to the live book. See
> [[concepts/tautological-instrument]] — this is the same class: a statistic that could not have
> come out any other way, because the conditioning produced it.

~~Gambler's-ruin baseline for a driftless walk: `P(PT first) = 1.543/3.601 = 42.9%`. Observed among the
74 resolved rows: **22 PT / 52 SL = 29.7% (z = -2.28, p ~ 0.02)**~~ — "the signal selection is
anti-predictive at this geometry rather than merely uninformative." **Scope stated precisely**: all 74
are candidate (simulated); the 7 live rows have zero resolutions. "It is one test at n=74 on a
selected sample; it is a flag, not a verdict."

## Caveat the doc imposes on itself
Under a Gaussian walk, 3.39-sigma barriers would give a PT-touch rate near 0.07%; observed 3.6%,
**~50x higher** — so `sigma_bar_pct` understates distance actually travelled. The *ratio* comparisons
are unaffected. **"Do not quote the Gaussian touch probability as a prediction."**

## Three options, none taken
1. Lengthen horizon to ~400 bars — **makes this a swing strategy**.
2. Cut the cost stack (maker-only, fee tier, tighter spread gating) so barriers come in to ~0.6%.
3. Select for volatility — only trade names/regimes where sigma_bar is high enough.

"(2)+(3) together are roughly equivalent to (1)." Explicit non-claims: the triple-barrier method is
not wrong (the parameterization is outside the informative range); do not just widen `label_max_bars`
and move on ("2 hours -> 1.5 days changes what strategy this is — an operator product decision, not a
tuning knob"); the 07-31 horizon change is **not** to blame (at 96 bars the ratio was 1.69 — better,
still 2x the literature, and it carried the clock inversion; **neither setting was in range**).

## Related
[[entities/kraken]] (fee tiers are the direct lever) · [[comparisons/horizon-96-vs-24-bars]] ·
[[synthesis/the-money-path-thesis]]
