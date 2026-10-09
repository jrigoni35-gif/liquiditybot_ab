---
title: Session 2026-08-16 — The Fee Wedge Binds at Every Tier, and the Loss Was Never Entry Selection
category: source
summary: "A 5-agent pass (1 finder, 3 hostile refuters, 1 measurement) on the question 'where do the losses concentrate', ending in a feasibility verdict: the pre-epoch closed book (−$391.43; 401 trips, close-ts < 2026-08-10T23:05:27Z) decomposes into the already-fixed ADA hedge-churn incident (159 trips, −$325.70, 96.9% fees, all 2026-08-07) plus a fee wedge on a zero-gross entry book (242 trips, gross −0.0187%/trip, z_eff −0.273 at eff_n 77.0 — CONFIRMED under nominal, AFML and Kish treatments; the one crack, a +0.0513% median with 57.9% gross win rate at sign-test p=0.0172 nominal, closes at eff-n p=0.17 and is 13× below the wedge either way). The decomposition verified by THREE routes including the runtime's own PT-061 audit book: 216/216 covered trips agree within $0.01, hedge book exact to 4dp. NO pre-trade axis concentrates: the refuter ran the full 87-bucket scan the finder only claimed (~100 claimed, 9 actually run — five buckets DO exceed the bar and all five are outcome-conditioned tautologies, stop_hit z=−27.4 proving the instrument can fire; pre-trade max is AVAX +2.92 at n=3; BTC's 0/33 net wins is p≈0.10 at eff_n and BTC wins 45% on GROSS — a fee phenomenon). THE DECIDER: Kraken Tier-1 spot is 40/80 bps (fresh fetch this session, agreeing with the 08-07 triple fetch; the sim's 25/40 constants re-confirmed as config-restated tautology by 708-leg enumeration), and the round-trip wedge BINDS AT EVERY ROW OF THE LADDER — booked 0.6694% = 5.7× the gross UCB (+0.1182%), true Tier-1 1.2610% = 10.7×, and the extreme corner (maker-only at the $1M+ tier) is 1.02× = parity, not profit. COST_BOUND is decided in feasibility terms on this corpus regardless of the schedule dispute; the era-4 gate remains sole formal arbiter. PROVENANCE RESOLVED on two carried numbers: 'z=−4.14 at h432' was the LABEL-SPACE anti-predictive statistic (boardroom brief, candidate rows, P(tb_pt|resolved) vs gambler's-ruin null) — never a trade-book z, and RETRACTED the same day it was filed (ea259ca5, wrong null for a censored sample; corrected −1.47 ns); '0.8% time-outs at h432' is UNFINDABLE garble (real value 209/476 = 43.9%, rising as rows mature; probable source: '0.8–1.0σ' barrier width adjacent to '87.8% time-out' in cost-to-volatility-ratio). SAME SESSION, the label-capacity fix landed in a worktree (d10c1a91, unpushed): max_open_candidates 200→1200 with a Little's-law config_guard FATAL, after the fix agent REFUTED this session's own prior estimate (not 29.2/h × 14.54h — residence is structurally the FULL 36h under multi_horizon shadow retention, label latency was measured instead of residence; sizing basis is the exact 659-registration peak 36h window, 18.3/h) and measured the cost of the 200-cap era: 84% of registrations produced no labeled row (upper bound, eviction/re-mint/stale-feed not separable). Three defects found and deliberately not fixed: zombie slot squatting (32/187 slots held by candidates whose entry bar left a stale cache — DOT 156h stale, a dead feed squats forever), restore() never truncates to a shrunk cap, and the DOT/SOL feed staleness itself. One unresolved reconciliation: the RP-070 weekly ledger matches NEITHER book at weekly grain (known confounds: hedges excluded at main.py:1671, RP-041 sweep false-loss)."
tags: [fee-wedge, cost-bound, era-4, adversarial-verification, closed-book, provenance, label-capacity, feasibility]
sources: 1
source_path: raw/quant/2026-08-16_fee_wedge_feasibility.md; worktree commit d10c1a91 (label capacity)
source_date: 2026-08-16
authors: [session-55a25968]
ingested: 2026-08-16
updated: 2026-08-16
---

# The Fee Wedge Binds at Every Tier, and the Loss Was Never Entry Selection

Primary artifact: `raw/quant/2026-08-16_fee_wedge_feasibility.md` — full tables,
three-route verification detail, per-leg fee distribution, scope limits, and
the scratchpad code inventory. This page is the map; the raw file is the
territory.

## What was asked and what was answered

The question walked in as "the bot's edge is negative (z=−4.14) and it
survived the geometry fix — find where the losses concentrate in entry
selection." Both premises failed:

1. **The −4.14 was never a trade statistic.** It is the label-space
   anti-predictive z from the boardroom brief (candidate rows,
   P(tb_pt|resolved)=0.258 vs gambler's-ruin 0.429), already retracted in
   `ea259ca5` — wrong null for a vertical-barrier-censored sample; corrected
   h432 value −1.47, nonsignificant. See [[synthesis/comparability-boundaries]]
   (standing blind spot: the source file is gitignored and grows; the exact
   snapshot is unrecoverable in principle).
2. **The losses do not concentrate in entry selection because there is no
   gross loss mass to concentrate.** Entry-book gross is −0.0187%/trip,
   z_eff −0.273 (eff_n 77.0), stable under every overlap treatment tried.
   The realized −$391.43 is [[sources/session-20260808-budget-reanchor|the
   ADA churn incident's]] −$325.70 (fixed, `cf454d5`) plus a 0.6694%-of-notional
   round-trip fee wedge on a statistically-zero book — converging with
   [[synthesis/the-money-path-thesis]] from an independent route.

## The feasibility verdict

With Kraken Tier-1 confirmed at 40/80 bps ([[concepts/cost-truth]]; fresh
fetch this session), the wedge exceeds the entry book's best-case gross
(+0.1182% at 2·SE_eff) at **every row of Kraken's spot fee ladder**: 5.7× as
booked, 10.7× at true Tier-1, 2.2× even at the $1M+ tier, 1.02× at the
absolute corner (maker-only, $1M+). Nothing on the venue's price list makes
this book net-positive at this gross. **COST_BOUND in feasibility terms** —
the era-4 gate ([[sources/session-20260816-catchup-08-12-to-08-16]]) remains
the sole formal arbiter, and this measurement deliberately says nothing about
the accruing cohort.

Corollary the operator must adjudicate: correcting the shipped 25/40 fee
constants to the true 40/80 is FEE BOOKING — a pre-named COHORT-RESETTING
class under the era-4 moratorium. Not shippable without adjudication.

## Verification discipline notes

- The finder's headline survived three hostile lenses, but two
  characterizations required amendment (median-vs-mean asymmetry; "~100
  comparisons" was 9 — the full 87-bucket scan then CONFIRMED the null more
  strongly, with tautological buckets proving the scan can fire).
- The fix agent refuted this session's own queue arithmetic (29.2/h ×
  14.54h) and re-derived the 1200 cap from the exact 659-peak window —
  recall-vs-re-derive working as designed, twice in one evening, both times
  against the session's own numbers.

## Owed / open (see [[synthesis/owed-measurements]])

- RP-070 weekly ledger reconciles with neither book at weekly grain —
  **RESOLVED same session** (see owed 87's resolution note: unit difference,
  the hedge-exclusion confound was wrong for RP-070; W30 +$0.41 remains).
- Zombie slot squatting (32/187 slots, dead-feed candidates never dropped).
- restore() cap-shrink truncation gap.
- DOT (156h) / SOL (35h) bars-cache staleness — data-layer incident.
