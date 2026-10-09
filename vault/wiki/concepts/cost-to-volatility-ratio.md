---
title: Cost-to-Volatility Ratio
category: concept
summary: "Round-trip cost divided by horizon sigma; a real constraint on labeling geometry — but demoted 2026-08-02 from 'the single ratio every symptom reduces to'. REALIZED FORM ADDED 2026-08-09: measured on trades that actually closed rather than on barriers that might have, the median WINNER is held 0.91h against a 0.71% round-trip cost — a horizon/cost mismatch of an order of magnitude, corroborated by MFE median 0.18%/p90 0.55% and by a per-trade gross edge of −0.0019% at t=−0.332 with fees 368x |edge| in percent space, and complicated by 60.6% TAKER fills on a book whose cost thesis is passive execution. Corroborated and further demoted at once: the wedge is real, and closing it converts a loss into a smaller loss rather than into a profit"
tags: [economics, cost, money-path, labeling, execution]
sources: 4
updated: 2026-08-09
---

# Cost-to-Volatility Ratio

> ⚠️ **Demoted 2026-08-02** ([[sources/session-20260802-digest]]): the ratio remains a real,
> measured constraint on labeling geometry, but the "no signal survives that / every symptom
> reduces to it" reading is corrected. At zero fees the book still loses 0.0501% mean gross
> per fill (post-quarantine n=217); the binding term is [[concepts/payoff-asymmetry]] — the average
> loser is 1.8x the average winner. Cost levers are necessary, not sufficient. The P&L rows that
> supported the strong reading were contaminated ([[concepts/default-path-fallback-writes]]);
> the corpus-side measurements below (barrier width, outcome mix) stand.

## Definition
`cost / sigma_horizon` where `sigma_horizon = sigma_bar * sqrt(H)`. It measures how much of one
standard deviation of price movement is consumed by trading costs over the labelled horizon.

## The measurement
Round-trip cost **0.50%** vs 2-hour sigma **0.61%** -> **cost/sigma = 0.82**.

> "**We pay 82% of one standard deviation in fees per round trip. No signal survives that.** Every
> downstream symptom — the degenerate labels, the low win rate, the negative edge, the model losing to
> a base-rate null — is this ratio expressed in a different unit."

## What it explains
- **Barrier width in horizon-sigma units** — PT sits at **3.39 sigma** against a literature norm of
  ~0.8-1.0, giving an **87.8% time-out rate**. Four times too wide.
- **Cost-scaled vs volatility-scaled geometry** — the cost floor binds on essentially every row, so
  barrier width no longer tracks volatility, **violating the triple-barrier method's own assumption**.
- The negative simulated edge (SL hit 1.9x more often than PT) and every model rung losing to a
  constant ([[concepts/null-model-floor]]).

## The horizon solution curve
cost/sigma 0.82 -> 24 bars (today) | 0.20 -> **405 bars (~34h)** | 0.10 -> ~5.6 days.
> [!error] CORRECTION 2026-08-16 — THE 10 BPS TIER DOES NOT EXIST
> This page previously read: *"At 10 bps/side instead of 25, cost/sigma 0.2
> needs only 65 bars (5.4 hours)."* **That tier was invented.** It entered
> from `docs/quant/2026-08-01_cost_to_volatility_horizon_mismatch.md`, where
> it was written as "(a Kraken volume tier)" **with no citation**, and was
> filed here as settled knowledge.
>
> [[sources/session-20260807-institutional-review]] §C already held the
> triple-confirmed schedule when this was written: **Tier 1 ($0+) 40/80**,
> Tier 2 ($2.5k+) 30/60, Tier 3 ($10k+) 22/38, **Tier 5 ($50k+) ~15/30 is
> the DEEPEST row**. Recall-before-derive would have caught it; the vault
> was not consulted.
>
> **The correction runs the wrong way.** The operator's $800 book is
> **Tier 1 = 40/80**, so the config's 25/40 UNDERSTATES fees and every
> cost/sigma on this page is optimistic:
>
> | premise | round trip | cost/sigma | breakeven hit |
> |---|---|---|---|
> | page's old 25bps maker/maker | 0.50% | 0.82 | 0.567 |
> | **Tier 1 maker/maker (40bps)** | **0.80%** | **1.31** | 0.650 |
> | **Tier 1 @ observed 60.6% taker** | **1.285%** | **2.11** | 0.784 |
>
> Fee tier and horizon still trade off directly - but the fee lever is
> roughly HALF the size this page claimed, and it points the other way.
> See [[concepts/cost-truth]], which had this right since 2026-08-07.

## The cost wedge, quantified (2026-08-02 late)
The ratio's label-space expression now has an exact number: **25.1% of winning PT touches** in
`horizon_shadow` still label 0 **because the touch fails the cost stack**. Pooled first-touch
**P(PT) = 0.418**, statistically at the geometric null **0.429** (= sl/(pt+sl) = 6/14 from the
8:6 barrier config), while the **label rate ≈ 0.31** sits below both — the wedge is the gap.
The funnel doc's 42.9% and the label rate are **different quantities**; conflating them is a
standing citation hazard ([[synthesis/open-contradictions-register]] #16) — one that bit
`geometry_search`'s own section 2 (label-space vs touch-space), corrected before commit; the
`663434ae` commit message records the wrong-quantity mistake.
([[sources/session-20260802-digest]] second addendum + final micro-addendum)

## The reframing
**"The cost floor is the messenger, not the villain."** It exists because sigma-scaled barriers at 5m
vol would put the profit target *inside* the cost band. "What it reveals is that at a 2-hour horizon,
on these pairs, at these fees, **there is no profitable bracket to label**."

## The REALIZED-holding-period form (2026-08-09) — the ratio measured on actual trades

Everything above is **label-space**: the ratio applied to the *intended* bracket. An algorithmic
reading of the actual ledger supplies the **realized** form
([[sources/session-20260809-turing-test-hedge-verdict]] §1.3,
[[comparisons/bot-vs-discretionary-vs-algo-trader]]):

```
median WINNER hold   :  0.91 h
round-trip cost      :  0.71%
```

> **A trade held under an hour must clear 0.71% to break even.** The move required in that window
> is roughly **an order of magnitude larger** than the move the holding period is designed to
> capture — the same wedge as above, now measured on trades that actually closed rather than on
> barriers that might have.

**Two independent confirmations that the wedge is fatal rather than tight:**

- **MFE median 0.18% / p90 0.55%** against the same **~0.65–0.71%** cost — *the median trade never
  moved far enough in its favour, at its single best moment, to cover its own costs*
  ([[sources/session-20260809-unbiased-economics]]).
- **Per-trade gross edge −0.0019% at t = −0.332**, with fees **368x** the absolute edge in percent
  space.

**And the execution is not the version the ratio assumes.** **60.6% of fills are TAKER** on a book
whose entire cost thesis is passive/maker execution — so the realized cost stack is not the one the
label-space ratio was computed against.

> **What this does to the ratio's standing.** It is **corroborated and further demoted at the same
> time.** Corroborated because the realized numbers reproduce the wedge exactly. Demoted because
> the ratio describes a **cost problem inside a book with no measured gross edge** (`t = −0.332`):
> fixing the cost/horizon mismatch converts a loss into a smaller loss, **not into a profit**.
> Cost work is **necessary and provably insufficient** ([[synthesis/the-money-path-thesis]]).

## Why this is the money path
Choosing among lengthen-horizon / cut-cost / select-for-volatility "changes what strategy this is — an
operator product decision, not a tuning knob." See [[synthesis/the-money-path-thesis]].

## Related
[[synthesis/the-money-path-thesis]] · [[concepts/payoff-asymmetry]] ·
[[concepts/behavioral-isomorphism]] · [[concepts/cost-truth]] · [[concepts/priced-bleed]] ·
[[concepts/ratio-aggregation-bias]] · [[concepts/paper-real-boundary]] ·
[[comparisons/bot-vs-discretionary-vs-algo-trader]] ·
[[comparisons/horizon-96-vs-24-bars]] ·
[[sources/session-20260809-turing-test-hedge-verdict]] ·
[[sources/session-20260809-unbiased-economics]] ·
[[sources/cost-to-volatility-horizon-mismatch]]
