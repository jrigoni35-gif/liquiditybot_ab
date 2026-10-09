# Literature-to-implementation estimator audit — 2026-07-29

Operator-directed follow-up to the same-day unit-coherence audit: eight
of the bot's estimator formulas checked against their canonical
peer-reviewed treatments (citations verified in-session; two flagged
unverifiable and marked as such). Operating point: 5m bars,
sigma_bar ~0.3%, ES budget 1%, horizon 24 bars, ~250 live trades.

## Verdicts

| # | Topic | Source | Verdict |
|---|-------|--------|---------|
| 1 | sqrt(h) ES scaling | Danielsson & Zigrand 2006 (JBF); McNeil-Frey-Embrechts QRM | CONFORMS at 2h horizon (fat-tail overstatement dominates, protective). BOUNDARY: do not extend cv_horizon multi-day without an overlapping-window direct-horizon ES check. |
| 2 | Realized vol vs sampling freq | Zhang-Mykland-Ait-Sahalia 2005 (JASA); Bandi-Russell 2008 (REStud) | vol_regime 5m cc CONFORMS (optimal band). calibrate_fills 5s mids: ACTIONABLE (noise variance amplified x60 by the bar rescale; up to tens of % sigma overstatement on thin alts) -> FIXED same day: sparse 60s subsample-and-average. |
| 3 | Parkinson estimator | Parkinson 1980; Garman-Klass 1980; Rogers-Satchell 1991 | ACTIONABLE: mean taken in VOL domain, not variance domain -> exact -4.2% bias on the pk leg (E[|hl|]/sqrt(4ln2) = 1.5958/1.6651). FIXED same day: RMS (variance-domain mean). Residual: discrete-trading understatement on thin alts (GK), direction protective on percentile. |
| 4 | Sharpe under non-iid + DSR | Lo 2002 (FAJ); Bailey-Lopez de Prado 2012/2014 | Variance formula CONFORMS exactly; Lo pitfall structurally avoided (no sqrt-annualization of per-trade SR). Expected-max term ACTIONABLE: sqrt(2 ln N) asymptotics overstate SR0 +12-17% at N=10-100 (+67% at N=2) -> FIXED same day: exact inverse-normal quantiles (bisection over _norm_cdf). USD-PnL Sharpe caveat stays documented. |
| 5 | Avellaneda-Stoikov spread | A-S 2008 (Quant Finance); Gueant-Lehalle-Fernandez-Tapia 2013 (MAFE) | KNOWN-DEVIATION-DOCUMENTED: linear-sigma is the GLFT stationary normalization (right for perpetual quoting; raw A-S collapses as T-t->0); sqrt(tau) envelope is documented discretion; sigma-multiplied intensity = re-parameterizing kappa_AS = k/sigma (docstring sentence added). Above sigma_bar ~0.29% the max-half-spread clamp binds anyway. |
| 6 | Fill probability per-lifetime | Cont-Stoikov-Talreja 2010 (OR); Huang-Lehalle-Rosenbaum 2015 (JASA) | Gate one-shot p CONFORMS vs the diffusive-touch benchmark (2*Phi(-d/(sigma*sqrt(tau))) ~ 0.25 at d=10bps/25s vs gate 0.32); the SIM is the outlier (~3.5x optimistic: per-bar hazard compounded per 5s poll). DEFERRED follow-up (label-distribution change, full battery + conscious re-baseline): p_poll = 1-(1-p_bar)^(dt/300) or enable MP-7 queue gate after re-baseline. Moallemi-Yuan citation in order_manager could not be verified as peer-reviewed (working paper) - annotated in code. |
| 7 | Fractional Kelly | MacLean-Thorp-Ziemba 2010 (Quant Finance) / 2011 handbook | CONFORMS at floor-dominated scale. Quantified caveat: flat 0.25 is ~4x the error-math shrinkage optimum in the marginal band p_hat in [breakeven, 0.65] at n=250 (SE(f*) ~ 0.08 >= f*). WATCH: when Kelly sizing leaves the min-ticket floor, adopt measured shrink c = f*^2/(f*^2 + ((1+b)/b)^2 p(1-p)/n_live), config-gated, guard-checked, re-baselined. |
| 8 | Triple-barrier + uniqueness + purge | Lopez de Prado, AFML 2018 ch.4/7 | CONFORMS: average uniqueness = exact eq. 4.2-4.3 (per-asset key = conscious multi-asset generalization), mass-preserving rescale, time/resolution purge STRICTER than the book, embargo correctly scoped no-op under expanding windows. Sequential bootstrap (sec. 4.5) deliberately skipped - now documented in-code; second-order at n~1000, only touches bagged families. |

## Same-day fixes shipped
- calibrate_fills: ZMA-style sparse 60s subsample-and-average sigma (#2)
- vol_regime: Parkinson RMS (variance-domain mean) (#3)
- overfit: exact inverse-normal quantiles in DSR expected-max (#4)
- doc corrections: GLFT mapping sentence (market_maker), sequential-
  bootstrap omission note (history), Moallemi-Yuan unverified annotation
  (order_manager)

## Deferred (conscious, evidence-gated)
- Sim per-poll hazard time-consistency (Topic 6) - changes the dry-run
  label distribution; needs spec + full battery + quant re-baseline.
- Kelly measured-shrinkage (Topic 7) - inert while floor-dominated;
  revisit when sizing leaves the floor.
- cv_horizon multi-day extension boundary (Topic 1) - flagged, not planned.

Full agent report with worked numbers and source links: see the session
record (2026-07-29). Citations verified via web search in-session.
