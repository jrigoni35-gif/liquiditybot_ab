---
title: Abstention Filters Ruled Out (meta-labeling, confidence gates)
category: concept
summary: Meta-labeling and every "confidence filter" or "quality gate" variant are ruled out on both theory and evidence — abstention cannot create edge where expected payoff is negative, and the technique has zero independent empirical validation
tags: [ruled-out, meta-labeling, abstention, binding]
sources: 2
updated: 2026-08-02
---

# Abstention Filters Ruled Out

**BINDING for future sessions** (researched 2026-08-02 after meta-labeling was recommended and
retracted twice in one session). Do not re-propose meta-labeling, "confidence filters," "quality
gates," or any abstention layer on top of the existing signal — **they are the same threshold
wearing a different name** (Franc, Prusa & Voracek, *JMLR*: the cost-based, bounded-coverage and
bounded-improvement rejection models are all equivalent to one threshold on conditional risk).

## Theory — abstention cannot create edge here
- Selective risk is a coverage-weighted average of conditional risk, so
  `sup(selective payoff) = ess sup_x pi(x)`: **if expected payoff is negative almost everywhere,
  every rule with positive coverage loses.** Under real fees this book's break-even win rate is
  p > 1 at fixed sizes ([[concepts/payoff-asymmetry]]) — abstention moves `p`, and `p` is not the
  binding term.
- Jones, Sagawa, Koh, Kumar & Liang (**ICLR 2021, Proposition 1**): selective accuracy
  *monotonically decreases* with the abstention threshold when full-coverage accuracy is below 1/2.
  *Provenance caveat:* this leg was argued at the windowed 5.5% win rate, later found to be
  computed under the refuted `position_id` grouping; at the clean per-fill win rate (57.1%
  post-quarantine, n=217) this leg weakens, but the payoff-domain argument above and the evidence
  below stand on their own.

## Evidence — there is none
- **Zero independent peer-reviewed empirical tests.** The four vendor (Hudson & Thames, JFDS)
  papers have 0/0/1/1 citations and neither citing work tests the technique.
- The independent base is six student theses. The only clean A/B design (Wölner-Hanssen 2023,
  Lund — ingested 2026-08-02 with a `raw/` snapshot: [[sources/lund-meta-labeling]]) found
  meta-labeling **worse than no meta-labeling on every axis**. The only cost-inclusive study
  (Schneider, ETH) **self-declares its findings invalid** from leakage. One reports Sharpe 13.2
  from an AUC-0.56 classifier — a leakage signature, not a result.
  *(The SSRN 4032018 fetch failed at a bot wall — marker filed in `raw/research/`; per
  [[concepts/availability-failure-mode]] it cannot be cited in either direction.)*
- **Never tested on a losing strategy.** Arzt (ETH 2021): "Four profitable trading systems are
  meta-labeled." Profitability was a precondition for inclusion.
- **Costs are the decisive gap and ours are double.** Six of seven studies exclude transaction
  costs; the one that included them (0.25%/trade) found costs consumed 38–58 percentage points of
  cumulative return, flipping one pipeline to −1.2% alpha. This bot's round trip is **0.50%**.

## The one admissible framing
If ever tried anyway: a **challenger arm only**, judged on out-of-sample Brier against the new-era
champion, with validation quarantined to new-era rows — the framing where being wrong costs
nothing. This matches [[concepts/gort-rule|the Gort Rule]] and
[[concepts/shadow-first-adoption]].

## Related
[[sources/session-20260802-digest]] · [[sources/lund-meta-labeling]] ·
[[concepts/evidence-grading-ladder]] (every rejection carries its killing citation) ·
[[synthesis/the-money-path-thesis]]
