---
title: Literature Estimator Audit (2026-07-29)
category: source
summary: Eight estimator formulas checked against canonical treatments at the bot's operating point; four fixes shipped, three evidence-gated deferrals
tags: [estimators, literature, volatility, kelly, fill-model]
sources: 1
updated: 2026-08-01
---

# Literature Estimator Audit (2026-07-29)

**Raw source:** `raw/quant/2026-07-29_literature_estimator_audit.md`

## Operating point
5m bars, sigma_bar ~0.3%, ES budget 1%, horizon 24 bars, ~250 live trades. Citations verified
in-session; two flagged unverifiable.

## The eight checks
1. **sqrt(h) ES scaling** (Danielsson & Zigrand; McNeil-Frey-Embrechts) — CONFORMS at 2h. BOUNDARY:
   do not extend `cv_horizon` multi-day without a direct-horizon ES check.
2. **Realized vol vs sampling frequency** (Zhang-Mykland-Ait-Sahalia; Bandi-Russell) — `vol_regime`
   CONFORMS. `calibrate_fills` 5s mids **ACTIONABLE — noise variance amplified x60 by the bar
   rescale** -> FIXED with a ZMA-style sparse 60s subsample-and-average.
3. **Parkinson estimator** (Parkinson 1980; Garman-Klass; Rogers-Satchell) — ACTIONABLE: mean taken
   in the **vol domain, not the variance domain** -> exact **-4.2% bias** -> FIXED with RMS. See
   [[concepts/variance-domain-averaging]].
4. **Sharpe under non-iid + DSR** (Lo 2002; Bailey-Lopez de Prado) — variance formula CONFORMS.
   Expected-max term ACTIONABLE: **sqrt(2 ln N) overstates SR0 by +12-17% at N=10-100 (+67% at N=2)**
   -> FIXED with exact inverse-normal quantiles.
5. **Avellaneda-Stoikov spread** (A-S 2008; Gueant-Lehalle-Fernandez-Tapia) —
   KNOWN-DEVIATION-DOCUMENTED: linear-sigma is the GLFT stationary normalization, right for perpetual
   quoting. Above sigma_bar ~0.29% the max-half-spread clamp binds anyway.
6. **Fill probability per lifetime** (Cont-Stoikov-Talreja; Huang-Lehalle-Rosenbaum) — the **gate's**
   one-shot p CONFORMS (0.32 vs a 0.25 diffusive benchmark); **the SIM is the outlier, ~3.5x
   optimistic** (per-bar hazard compounded per 5s poll). DEFERRED — the attempted measurement is
   [[sources/fill-hazard-l1]], which returns INSUFFICIENT_EVIDENCE.
7. **Fractional Kelly** (MacLean-Thorp-Ziemba) — CONFORMS at floor-dominated scale. Quantified
   caveat: flat 0.25 is **~4x the error-math shrinkage optimum** in the marginal band at n=250.
   WATCH: adopt measured shrink when sizing leaves the min-ticket floor.
8. **Triple-barrier + uniqueness + purge** (AFML ch.4/7) — CONFORMS. Average uniqueness is exact
   eq. 4.2-4.3; time/resolution purge **stricter than the book**. Sequential bootstrap deliberately
   skipped, now documented in-code.

## Doc corrections shipped
GLFT mapping sentence in `market_maker`; sequential-bootstrap omission note in `history`;
Moallemi-Yuan annotated as an unverified working paper in `order_manager`.
