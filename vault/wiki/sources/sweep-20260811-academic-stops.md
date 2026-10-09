---
title: "Academic sweep (Grand Synthesis input 1) — stops, turns, carry, labels: established / contested / folklore"
category: source
summary: "The AFML-skeptical literature sweep the Grand Synthesis trigger required, graded per the evidence-grading ladder: Kaminski-Lo 2014 is THE load-bearing result (stops are regime-conditional — add value under momentum, pure tax under random walk); Han-Zhou-Zhu found TIGHT stops doubled momentum Sharpe (direction CONTRADICTS widen-in-high-vol); Osler JIMF 2005 is the peer-reviewed kernel under stop-hunt folklore; Goulding-Harvey-Mazzoleni four-state slow/fast disagreement is THE peer-reviewed turn-detection answer; widen-stops-in-high-vol has NO direct crypto-intraday test and the lean is AGAINST; MAE-boundary placement, ICT/liquidity-sweep, ATR-multiplier optimality, funding-flip timing, and cross-regime label purging are FOLKLORE; and the one gap the literature cannot answer — triple-barrier label-distribution shift across regimes — is decidable only locally (ALGO-2)"
tags: [literature, sweep, stops, momentum, regime, carry, grand-synthesis, evidence-grades]
sources: 1
source_path: agent report tasks/a91471ffaee6a3505.output (NOT accessible at wiki filing — verdicts and citations filed as relayed by the executing session; flagged per the honesty convention)
source_date: 2026-08
authors: [academic-sweep agent (deep-research), filed by the Grand Synthesis session]
ingested: 2026-08-10
updated: 2026-08-10
---

# Academic sweep — Grand Synthesis input 1 (2026-08-11 session)

**What this is.** The academic literature sweep required by the Grand Synthesis trigger
([[sources/directive-20260811-grand-synthesis]], trigger input 1; [[synthesis/owed-measurements]]
item 66): stops under shakeout, turn detection, carry/positioning, labels across regime shift —
**AFML-skeptical** per the vault's standing posture. Every claim graded on the
[[concepts/evidence-grading-ladder]] (this is the ladder's **second full-scale application**,
after the 2026-08-08 institutional-data adjudication).

**Provenance honesty** (ladder honesty convention): the underlying agent report
(`tasks/a91471ffaee6a3505.output`) was **not accessible at this filing** — the verdicts below are
filed **as relayed by the executing session**, citations preserved as stated. Where a page below
needs the full bibliographic record, the revisit term is: recover the agent report or re-verify
the citation before treating any *individual* citation as search-verified.

**Boundary statement** (governance rule 13): everything below is **literature-side** — no number
here is a measurement of this book. Where a verdict licenses local work, the work is named
(ALGO-n, [[synthesis/grand-synthesis-algorithm-package]]).

## ESTABLISHED

1. **Kaminski & Lo (Journal of Financial Markets, 2014) — stops are REGIME-CONDITIONAL.**
   Stop-loss rules **add value under momentum dynamics and are a pure tax under a random
   walk**. **THE load-bearing result of the sweep**: it converts every stop-design question
   into a regime question, which is why [[synthesis/grand-synthesis-algorithm-package|ALGO-1]]
   (regime tape) precedes any geometry change, and why a stop rule with no regime conditioning
   has no peer-reviewed leg to stand on.
2. **Han, Zhou & Zhu — TIGHT stops doubled momentum-strategy Sharpe via crash truncation.**
   The direction of the result **contradicts widen-in-high-vol**: the value came from
   truncating the left tail, not from giving trades more room.
3. **Lei & Li — stops are variance reduction, not expectancy improvement.** Consistent with
   this book's own two nulls: exit design minimizes bleed, it does not create edge
   ([[synthesis/the-money-path-thesis]]).
4. **Osler (Journal of International Money and Finance, 2005) — stop clustering at round
   numbers + stop cascades.** **The peer-reviewed kernel under the stop-hunt folklore**: the
   folklore corpus (ICT etc.) is graded folklore below, but THIS mechanism — clustered stops
   at round numbers generating self-reinforcing cascades — is established, and it is the
   evidence base for [[synthesis/grand-synthesis-algorithm-package|ALGO-7]]'s
   avoid-round-number placement. See [[entities/osler]].
5. **BitMEX / liquidation-cascade studies — crypto adverse spikes are ENDOGENOUS,
   leverage-driven, and fatter than sigma estimates.** A stop distance derived from a sigma
   estimate understates crypto adverse excursions because the excursions are liquidation
   mechanics, not diffusion.
6. **Moreira & Muir — volatility-managed sizing** (scale exposure down when vol is high) is
   established as published — **and CONTESTED by the Cederburg et al. 103-strategy
   replication**, which found the result fragile out of the original design. Filed with both
   halves; graded established-with-live-contest, adopt nothing on it without local measurement.
7. **Goulding, Harvey & Mazzoleni — four-state trend taxonomy from slow/fast trend
   DISAGREEMENT (Bull / Correction / Bear / Rebound) — THE peer-reviewed turn-detection
   answer.** The method is to **measure disagreement between two trend speeds, never to add
   one faster filter**. Direct design input to
   [[synthesis/grand-synthesis-algorithm-package|ALGO-1]] (432/96 is the native slow/fast
   pair; **Rebound is the surprise-bull state** the bull-readiness thread asked about).
8. **Schmeling, Schrimpf & Todorov — Crypto Carry: basis/funding as POSITIONING PRESSURE.**
   The peer-reviewed backbone of the 2026-08-08 basis/funding adoption
   ([[sources/session-20260808-institutional-data-adjudication]]) — carry measures crowded
   positioning, not direction, consistent with the asymmetric-veto encoding already shipped.
9. **ETF flows explain ~21% of daily return variance — but Granger causality is
   BIDIRECTIONAL.** Flows are **reactive contamination as a leading indicator**: the variance
   share is real, the lead is not clean. Confirms the 2026-08-08 adoption's report-only
   posture and blocks any promotion of flows to a signed entry input.
10. **Crypto TSMOM is horizon- and size-conditional, NOT settled** (FMPM 2025 fat-tail
    caveat). Time-series momentum in crypto exists in some horizon/size cells and not others;
    no citation licenses a blanket TSMOM assumption.

## CONTESTED

- **Widen-stops-in-high-vol** — the practitioner default — has **NO direct crypto-intraday
  test anywhere in the swept literature, and the indirect evidence LEANS AGAINST** (Han-Zhou-Zhu
  tight-stop result; Kaminski-Lo regime conditioning). This is exactly why
  [[synthesis/grand-synthesis-algorithm-package|ALGO-5]] (counterfactual stop replay on this
  book's own uncensored paths) exists: the question is decidable **locally, not from the
  library**. Evidence lean at filing: **NOT widen**.
- **Time stops** — weakly supported: one 11/13-month single-market working paper in favor vs
  the Davey 567k-backtest counter. Neither side is crypto-intraday. ALGO-6's time-decay
  ladder therefore takes its parameters **from ALGO-5's replay, not from this literature**.

## FOLKLORE (graded, with the one legitimate residue each)

- **MAE-boundary stop placement** ("place the stop at the MAE boundary of winners") —
  **tautological as a placement rule** (winners are defined by not having hit the stop;
  fitting the stop to their MAE is selection on the label), **legitimate as a diagnostic**
  (the winners' MAE envelope is a real distribution worth knowing — which is what the
  uncensored trade-path ledger measures without turning it into a rule).
- **ICT / liquidity-sweep corpus** — folklore; its one real kernel is Osler's established
  clustering/cascade mechanism above.
- **ATR-multiplier optimality** (any claim that k×ATR is the right stop for some k) — no
  peer-reviewed support for any particular multiplier; regime conditioning (Kaminski-Lo)
  dominates the question.
- **Funding-flip bottom timing** (funding sign flip as a bottom signal) — folklore; the
  established funding result is positioning pressure (Schmeling-Schrimpf-Todorov), not
  timing.
- **Cross-regime label purging** (purge training labels across regime boundaries) — a
  **category error with zero evidence**: purging exists to kill leakage from overlapping
  label windows (AFML), not to slice regimes; no study supports deleting cross-regime rows.
  ([[synthesis/evidence-closed-register]] — filed as NOT-ADOPTED.)

## The gap the literature CANNOT answer

**Triple-barrier label-distribution shift across regimes has NO peer-reviewed
quantification.** Nobody has published how the (upper, lower, vertical) hit-rate mix of
triple-barrier labels moves when the regime moves. **Decidable only locally** — which is
[[synthesis/grand-synthesis-algorithm-package|ALGO-2]] (regime-stamped labels): stamp every
label row with the ALGO-1 regime state and measure the shift on this book's own corpus.

## AFML external replication note

A 2025 arXiv **100-seed replication of sequential bootstrap** found that **claims holding at
3 seeds fail at 100** — the external literature now matches this project's internal experience
with AFML technique ([[concepts/pbo-and-cscv]], [[concepts/average-uniqueness-and-ess]], the
vault's standing AFML-skeptical posture). Received technique is audited, not adopted.

## Related

[[sources/directive-20260811-grand-synthesis]] ·
[[synthesis/grand-synthesis-algorithm-package]] ·
[[sources/sweep-20260811-engineering-precedents]] · [[concepts/evidence-grading-ladder]] ·
[[synthesis/evidence-closed-register]] · [[entities/osler]] ·
[[sources/session-20260808-institutional-data-adjudication]] ·
[[synthesis/the-money-path-thesis]] · [[concepts/behavioral-isomorphism]]
