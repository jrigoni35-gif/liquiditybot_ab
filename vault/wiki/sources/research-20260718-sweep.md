---
title: Research Sweep 2026-07-18
category: source
summary: Six-lane peer-reviewed literature sweep naming, per lane, the canon, the one mechanism adopted, and the failure mode that bounded it
tags: [literature, research-sweep, inventory, adverse-selection, kelly]
sources: 1
updated: 2026-08-01
---

# Research Sweep 2026-07-18

**Raw source:** `raw/architecture/RESEARCH-20260718.md`

## Method
A deep-research harness: parallel search -> fetch -> **3-vote adversarial verify**. Standard template
per lane: **canon -> one mechanism -> the bounding failure mode**. Every new mechanism defaults to
[[concepts/shadow-first-adoption]].

## Lane 1 — Inventory management (ADOPTED, shadow)
Avellaneda-Stoikov 2008; Gueant-Lehalle-Fernandez-Tapia 2013; Ho-Stoll 1981. Verified 3-0. The
reservation price `r = s - q*gamma*sigma^2*(T-t)`; spread width separates from center; the hard bound
stops inventory-increasing quotes while exits stay allowed — **"exactly our invariant-5 philosophy,
independently derived."** A-S Table 1: inventory skew costs ~6% expected profit for **>2x lower P&L
variance**. gamma stays a config knob under the gated tuning pass, **never learned live**.

## Lane 2 — Adverse selection: markouts over VPIN
**VPIN is CONTESTED in its home market — "do not build on it"** (the refutation finds no early warning
pre flash crash; predictive content is a mechanical volume artifact). Markouts are the uncontested
practitioner standard and already recorded. A per-asset **markout-toxicity monitor** is designed —
**not built**.

## Lane 3 — Manipulation security (ADOPTED -> TH-017 spoof flicker)
A level >= `big_ratio` x median top depth that vanishes >= `drop_frac` **while the mid never crossed
it (pulled, not consumed)**; per-side EWMA; entries in the baited direction shaded down. **SAFETY
shade: exempt from reliability grading — "a failed spoofer must not teach the ledger to ignore
spoofing."**

## Lane 4 — Long-run growth math (validated the stack)
Breiman; Algoet-Cover; MacLean-Thorp-Ziemba (2x Kelly -> zero excess growth); Busseti-Ryu-Boyd
(drawdown-constrained Kelly dominates naive fractional Kelly); Moreira-Muir vs Cederburg et al.
**The contested vol-timing ALPHA claim is NOT adopted.** Overbetting bound: `kelly_fraction <= 0.5`
stays a review tripwire.

## Lane 5 — Execution realism (designed, deferred)
Moallemi-Yuan; Huang-Lehalle-Rosenbaum. **State-independent Poisson fill models OVERESTIMATE passive
fill probability.** Honest rule: an artificial resting order fills only when subsequent traded volume
at its price exceeds the depth ahead of it at placement. Adopt the **volume-drain accounting only**,
not the full Markov model. Until then, candidate labels carry an optimistic-fill bias.

## Lane 6 — "SIP feeds": none exists
BTC liquidity is materially fragmented with no native consolidated tape. The Coin Metrics Community
API is **REJECTED** as a dependency — 7-point history, tight rate limit, and a **non-commercial
license clause that is a compliance failure mode for a for-profit bot**. Verdict: Kraken(exec) + OKX +
Binance.US read-only aggregation **IS** the crypto SIP-equivalent at our scale.

## Related
[[entities/avellaneda-stoikov]] · [[entities/lopez-de-prado]] · [[entities/read-only-venues]]
