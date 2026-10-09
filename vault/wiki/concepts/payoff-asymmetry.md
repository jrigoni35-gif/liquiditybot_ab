---
title: Payoff Asymmetry (the binding term)
category: concept
summary: "The average loser is ~1.8x the average winner — payoff ratio 0.561 against 0.750 needed at 57.1% win rate (n=217) — so no achievable hit rate can break even; bounded 08-02 late — exit geometry sets the bleed but cannot create edge (no surviving bracket in the pre-registered 48-combo grid). RELOCATED 2026-08-09: the asymmetry describes the SHAPE of the gross distribution, and the whole-book decomposition now measures its MEAN at ~0 (gross −11.66 before any fees vs 382.59 of fees, 32.8x) — both hold, the mean is upstream, and this page's own claim now carries its falsifier. THE MEDIAN MOVED TOO, same day: the full-book reconstruction puts median gross at −0.0303% over 394 round trips where the shipped breakeven tool reports +0.0505% over 235 — a shape argument is only interesting above a positive mean"
tags: [economics, pnl, exit-geometry, money-path, gross-vs-net]
sources: 3
updated: 2026-08-09
---

# Payoff Asymmetry (the binding term)

## The identity, and which term binds
Per-trade expectancy decomposes into win rate `p`, mean win `W`, mean loss `L`, and cost. Every
proposed fix moves exactly one term. The 2026-08-02 clean measurement
([[sources/session-20260802-digest]], n=215 per-fill, commit `f0120393`) locates the defect:

```
mean gross -0.048%   median gross +0.049%   win rate 57.5%
mean win   +0.2625%  mean loss    -0.4685%  payoff ratio 0.560
```

**Survived a second purge.** The same day's addendum found and quarantined **18 more fixture
positions (72 rows)** (commit `483f6727`; `fills.csv` now 637/637 audit-crossref CLEAN). The
post-quarantine numbers are materially unchanged:

```
n=217   mean gross -0.0501%   median gross +0.0469%
win rate 57.1%                payoff ratio 0.561 vs 0.750 needed
```

**The hit rate is fine. The sizes are wrong.** Break-even payoff at the observed win rate is
**0.750** (0.740 at the pre-quarantine 57.5%); observed is **0.561**. The average loser is
**~1.8x** the average winner — the AVERAGE loser, not a tail: post-purge the distribution is
near-symmetric (min −2.38%, max +1.87%; dropping the worst 5% moves the mean only to +0.031%).

## The decisive number
Win rate needed to break even holding sizes fixed, `p = (cost + L)/(W + L)`:
**IMPOSSIBLE (p > 1) at all three real fee schedules**, including Kraken maker/maker at 0.320%.
Only at zero fees does it become finite, at **64.1%**.

## What follows
- **Raising the hit rate cannot fix this.** Only shrinking the average loser or extending the
  average winner can — that is **exit geometry**: stop distance, target distance, time stop.
- **A better model is not the first move.** A model raises `p`, and `p` is not the binding term.
  The same applies to gates, filters, and meta-labeling
  ([[concepts/abstention-filters-ruled-out]]).
- **Cost levers are necessary and not sufficient.** Fees are the larger term (0.667% measured fee
  term against a 0.048% gross gap), but cutting them to zero still leaves −0.048% mean gross.

## Supersession chain (claimed → refuted → stands)
1. *"Plain signal underperformance"* ([[sources/goals-mindset-review]], 07-24) — refuted: per-fill
   hit rate is 57.5%.
2. *"Cost is the binding constraint — cost/sigma 0.82"*
   ([[sources/cost-to-volatility-horizon-mismatch]], 08-01) — corrected: cost is necessary, not
   sufficient; the ratio was also fed by contaminated fills.
3. *"Loses ~0.34%/trade at zero fees — an entry-edge problem"* (08-02 interim) — refuted by
   per-fill measurement; the method could not separate fees from slippage.
4. **Stands:** payoff asymmetry — 0.560 vs 0.740 needed at n=215, re-confirmed **0.561 vs 0.750
   needed at n=217** after the residual quarantine (`483f6727`). Both earlier headlines were
   computed from `position_id`-grouped fills with one position under 16 ids — the 27x error
   ([[concepts/default-path-fallback-writes]]).

## Bounded 2026-08-02 (late): exit geometry cannot create edge
The prescription above names exit geometry as the lever. The same day's **pre-registered
48-combination bracket grid** (`scripts/geometry_search.py`, commit `663434ae`, battery green,
Bonferroni-corrected z = 3.26,
replayed on real OHLC over **222 actual entries** with config fees) found **no combination
survives** — best (h=432, tp=1%, sl=2%): mean **−0.400%**, lower bound **−1.124%**. And the
**random-entry control** (n=51 vs 200 seeded matched controls each, commit `8062f46a`) found
**no entry-timing signal** (mean MFE percentile 0.516 [0.439, 0.594]).

Read together: the asymmetry correctly names *where the bleed is set* — geometry — but **no
bracket geometry converts these entries into positive expectancy.** Exit design minimizes bleed;
edge has to come from somewhere else (the cost stack, pooling, or a signal not yet
demonstrated). ([[sources/session-20260802-digest]] second addendum)

## The villain number reached the operator's screen (2026-08-05 evening)
The boards redesign (`bc198aa5`, [[sources/session-20260805-evening]]) kept **geometry economics
on the trading desk where the money is**, and changed the payoff-ratio tile to carry **its own
break-even threshold: green only at 0.75** — the measured break-even at the observed win rate and
fee stack — instead of borrowing the profit-factor scale it had been rendered against.

> **A number is only a diagnosis when it is scored against the threshold that makes it one.**
> Read against a profit-factor scale, **0.561** was just a smallish number on a dashboard; read
> against **0.750**, it is the first thing that colors red. The measurement did not change; the
> comparison did.

Nothing about the standing diagnosis moved. Two later commits the same evening are worth marking
as **not** relevant to this term, so they are not later mistaken for progress on it:
- The **haven gradient** ([[synthesis/tangible-value-doctrine]]) is a regime read. Regime reads
  can only ever raise `p` or select *when* to trade — **`p` is not the binding term**, and both
  08-02 nulls bound what selection can be worth. Gold's honest contribution is **near-zero crypto
  beta** (diversification), not edge.
- The **profit-pool skim defect** (owed item 30c: the skim ran **per exit leg on `net`** rather
  than per trade, so a **+$16 winning leg on a −$80 trade still locked ~$4.80 away**) does not
  change the payoff ratio — but it meant the book that is already losing on this term was **also
  draining trading cash into locked pools as a function of gross winning legs**, and **tiered exits
  are the normal trade shape**. Two independent bleeds on the same account.
  **FIXED the same evening (`4799bfc7`).** Sharper than filed: `net` is **gross minus that leg's
  exit fee, NOT minus the slice's pro-rata entry fees**, so the skim also ran on an **overstated
  base** — and **savings is never clawed back**. The fix **separates the fused concerns**: cash
  settles **per leg** (`skim=False` — entry fees already left cash at fill time via
  `record_entry_fee`), while the three-way split runs **ONCE per closed trade** on the fully-net
  total through new `CapitalManager.skim_trade()`, pinned by equity-conservation and
  no-double-booking tests ([[sources/session-20260805-evening]] §5).
  > **The ratio is unchanged; the second bleed is stopped.** Do not read this fix as progress on
  > the asymmetry — it removes a *separate* drain that was compounding it. **0.561 vs 0.750
  > stands.**

## RELOCATED, not refuted (2026-08-09) — the mean beneath the shape

([[sources/session-20260809-unbiased-economics]].) The all-in decomposition over the whole book —
**~250 closed positions / 438 entry fills** — reads **gross P&L before ANY fees = −11.66**
(~**−$0.05/trade**, indistinguishable from zero) against **382.59** of fees: **fees are 32.8x the
absolute gross edge, and 100% of the −394.25 all-in loss is costs.**

> **This does not refute the asymmetry; it locates it.** *0.561 vs 0.750* is a statement about the
> **SHAPE** of the gross distribution — the average loser is ~1.8x the average winner. The new
> measurement is a statement about its **MEAN** — which is **~0**. Both are true, and the mean is
> **upstream**.

Three consequences, all of which sharpen rather than weaken this page:

1. **"The hit rate is fine, the sizes are wrong" survives — but is no longer the deepest layer.**
   Fixing the sizes redistributes a gross distribution centred on zero. It removes the bleed; it
   does not manufacture a mean.
2. **The 08-02 bound is now explained, not merely observed.** The pre-registered 48-combo grid
   found no surviving bracket, and this is exactly what a null-mean population predicts — the
   search was not underpowered, it was searching a population with no measured edge to find.
   Same for the random-entry MFE control.
3. **The prescription is unchanged in direction and upgraded in urgency.** Exit geometry remains
   the named lever, and the one live lead is geometric: shadow win rate rises monotonically
   **22.3% → 30.4% → 35.4%** at 108 → 216 → 432 bars ([[comparisons/horizon-96-vs-24-bars]]), and
   `config_guard` reports a **derived entry bar of 0.990** — *"fix the geometry, the bar is only
   reporting it"* ([[entities/config-guard]]). **A required win probability of ~99% is not a
   modelling problem.**

⚠️ **A framing caution attaches to this page specifically.** "Payoff asymmetry is the binding
term" is load-bearing house vocabulary, and it must now carry its falsifier like every other:
*if the asymmetry were the binding term, correcting the geometry would produce positive
expectancy* — which the 48-combo grid already failed to demonstrate. Read that as a bound on this
page's claim, not as a footnote to it ([[concepts/unfalsifiable-explanation]]).

### The median moved too, and the tool that reports it was reading the wrong population

([[sources/session-20260809-adversarial-audits]] §4.1.) The whole-book reconstruction that
produced the second gross estimate also produces the **median gross per round trip**, and the
correction moves it across zero:

| | closed round trips | median gross |
|---|---|---|
| as `scripts/breakeven_test.py` reports it (hedge leg discarded) | 235 | **+0.0505%** |
| corrected (`purpose in {entry, hedge}`) | **394** | **−0.0303%** |

**Both the mean and the median of the gross distribution are at or below zero.** This matters to
*this* page specifically, because a shape argument is only interesting **above** a positive mean:
if the median trade's gross is negative, the asymmetry describes **how** a losing distribution
loses, not **why** a break-even distribution fails to profit.

> ⚠️ **What does NOT change:** the 08-02 pre-registered 48-combo bracket grid and the
> random-entry MFE control were independent of this tool and are **unaffected**. The retraction
> is narrow — it applies to citations of `breakeven_test.py`'s **printed verdict line**, which
> selects between two hard-coded branches on the sign of that median and has therefore been
> printing *"this is exit geometry, fixable without touching the signal"* when its own method
> says *"gross expectancy is negative"*
> ([[synthesis/open-contradictions-register]] entry 22).

## Relation to the cost-to-volatility ratio
[[concepts/cost-to-volatility-ratio]] remains a real, measured constraint on *labeling geometry*,
but it is no longer "the single ratio every symptom reduces to." The asymmetry is upstream: it
persists at zero cost, and it names the lever (exit geometry) rather than a trade-off curve.
See [[synthesis/the-money-path-thesis]].
