---
title: "Session 2026-10-01 — signed-flow screen, the within-day AUC path-overlap bias, conviction evidence by OOF p, the shadow-report join bug, and the US regulation layer"
category: source
status: SETTLED-AS-OF-RUN
summary: "New-information screen: signed tape flow reads contrarian within-day (0.44-0.48) but is mostly past return in disguise (residual 0.485, CI spans 0.5). The within-day AUC is BIASED for path-derived scores (random walk reads 0.39) - a sign-flip null is required; against it, real 1h/30m reversal survives (0.2945 vs null 0.360, p 0.016) in features the bot already has; confirmed and shown sub-cost by Kitron & Wengrowicz 2026 (1.3 bp vs 5 bp). Conviction: walk-forward OOF p ranks (win 0.33-0.39 -> 0.50) but no decile clears p* 0.564, and the top decile comes from 13 days - conviction's effective n is DAYS. shadow_policy_report join bug fixed (391 labeled rows read as unresolved). US regulation: Kraken US margin legal since 2026-05-06 via its FCM; PAXG cap 5x < config 10x; state of residence a precondition."
tags: [new-information, signed-flow, trade-tape, within-day-auc, path-overlap, sign-flip-null, mean-reversion, conviction, oof, shadow-policy, join-bug, regulation, us, kraken-margin, paxg, cohort-hold]
sources: 1
updated: 2026-10-01
---

# Session 2026-10-01 — new information, the path-overlap bias, conviction evidence

Repo: `docs/quant/2026-10-01_new_information_and_conviction_evidence.md`; `docs/research/regulation/`;
`scripts/info_screen.py`, `scripts/conviction_value_report.py`, `scripts/shadow_policy_report.py` (join fix).
Hold: cohort `6709bbc2778d` accrues untouched until the 10-12 lean (operator agreed 2026-09-30).
Corrects: [[sources/session-20260929-markov-brownian-edge]] (callout added).
Prior art respected: [[sources/session-20260901-edge-hunter-mirror]] (intensity = resolution, not direction).

## Findings (re-derive; never copy forward)

1. **Within-day AUC is biased for path-derived scores.** Rows in one day share one price path; a pure random
   walk reads within-(day, asset) AUC 0.39 (1h return). The within-day permutation null is too narrow.
   RULE: grade path-derived scores against a structure-preserving (sign-flip) null.
2. **Signed tape flow** (never tested before): contrarian within-day 0.44-0.48, decision-time cutoff 0.460,
   stable across halves - but residualised on past returns 0.485 [0.459, 0.506]: mostly the return.
3. **Sign-flip null** (real 5m returns, random signs): 1h return real 0.2945 vs null 0.360 [0.324, 0.398],
   30m 0.3332 vs 0.392; p 0.016. Real reversal beyond the artifact (~0.06-0.07 AUC), in existing features.
4. **Literature confirms direction and economics**: Kitron & Wengrowicz arXiv:2608.21888 (read verbatim):
   90% of 183 Binance pairs, after taker flow, gross 1.3 bp vs 5 bp cost - sub-cost. Bot round trip ~45 bps.
5. **Conviction** (walk-forward OOF p, blend, 20,675 rows, OOF AUC 0.574): win rises with p (0.33-0.39 ->
   ~0.50 in deciles 8-9) but no decile clears p* 0.564; top decile 0.420 from only 13 days, top 1% from 5.
   Conviction's effective sample is DAYS.
6. **shadow_policy_report join bug** (shipped 09-29): keyed candidate labels on candidate_id; the real writer
   uses position_id. 391 labeled rows read "unresolved"; promotion could never fire. Fixed + real-writer pin.
   First read: would-enter n=31, -135.3 bps, 2 day-blocks.
7. **US regulation** (`docs/research/regulation/`): Kraken US retail spot margin via NinjaTrader Clearing
   (FCM, NFA 0309379) since 2026-05-06; per-asset caps BTC 20x / ETH 10x / LINK 10x / PAXG 5x and
   liquidation at 40% verified on Kraken's own page. Config 10x > PAXG 5x. State of residence unknown
   (NY/WA/ME reported excluded). Literature: leverage without edge is pure drag (Heimer & Simsek identity).
