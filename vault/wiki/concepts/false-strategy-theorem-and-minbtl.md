---
title: False Strategy Theorem and MinBTL
category: concept
summary: Under a true zero edge, the best of N tried configurations has expected Sharpe E[max SR]>0 growing in ln N; MinBTL is the minimum backtest length (years) needed merely to avoid manufacturing an in-sample Sharpe of 1 from nothing — the project's own N puts it years long against a 0.065-yr production-loaded corpus (23.73 d; the 0.137-yr figure was the raw file span)
tags: [statistics, overfit, selection, sample-size]
sources: 2
updated: 2026-09-01
status: SETTLED
---

# False Strategy Theorem and MinBTL

## Definition
Bailey & López de Prado, *The Deflated Sharpe Ratio* (J. Portfolio Mgmt 40(5), 2014), later
peer-reviewed as López de Prado & Bailey, *The False Strategy Theorem* (Amer. Math. Monthly
128(9), 2021): over **N independent trials with true Sharpe zero**, the expected maximum
observed Sharpe is

    E[max SR] ≈ (1−γ)·Z⁻¹(1−1/N) + γ·Z⁻¹(1−1/(N·e)),  γ = Euler–Mascheroni

strictly positive and unbounded in N. `sqrt(2 ln N)` is an **upper bound**, not the value
(overstates by ~36% at N=10). Bailey, Borwein, López de Prado & Zhu, *Pseudo-Mathematics and
Financial Charlatanism* (Notices AMS 61(5), 2014, Thm 3.1) turn it into **MinBTL**, the minimum
backtest length in years below which a skill-less search is EXPECTED to surface an in-sample
Sharpe of 1.0:

    MinBTL < 2·ln(N) / E[max SR]²   (years of daily data; necessary, not sufficient)

## What it says about this project (measured 2026-09-01)
Figures are the 2026-08-31 deep-research workflow's own arithmetic on the paper's Eq. 3.2, tagged
[I] (raw: `raw/research/2026-08-31_deep_research_null_expected_counterfactual_cost.md`):

| N (trials) | E[max SR] | MinBTL |
|---|---|---|
| 8 (model families only) | ~1.4 | **~2.1 yr** |
| 512 (8 families × 64 feature counts) | ~3.06 | **~9.4 yr** |

**Which span is the denominator (corrected 2026-09-01, second pass).** Three numbers were
conflated in the session that wrote this page, and only the smallest is the one the theorem
wants:

| span | value | what it is |
|---|---|---|
| raw `signal_history` file | 50.25 d = 0.138 yr (22,442 rows, 2026-07-13 →) | rows on disk — NOT what the champion is judged on |
| **production-loaded corpus** | **23.73 d = 0.065 yr** (12,066 rows, 2026-08-09T01:00Z → 09-01T18:35Z) | era exclusion + `label_era` filter; the rows `champion_skill_report.py` actually scores. Double-derived (report + `HistoryStore.load_training_data` direct). Re-derive: `python scripts/champion_skill_report.py --json` → `corpus_span_days` |
| project age | months, not days (operator, 2026-09-01) | raises N; never the denominator |

Against **0.065 yr** the sample is **~32× short of the N=8 bound and ~145× short of N=512**;
even N=2 (MinBTL ≈ 0.27 yr = 99 d) exceeds BOTH file spans. Under a true zero edge the standard
error of an annualized Sharpe over y years is ≈ 1/√y → **3.9 at 23.73 d** (2.7 at 50 d): no Sharpe
this corpus can produce is distinguishable from zero at 2σ below SR ≈ 7.8. The measured
out-of-sample skill of −0.006 ([[sources/session-20260901-edge-hunter-mirror]]) is therefore the
arithmetic of the sample, not a finding about the market. (Commit `1d751e22`'s subject cites
50.1 d — that was the raw span; the correction is of record in `docs/HANDOFF.md` EDGE-HUNTER
MIRROR item 1.)

## The direction people get wrong
- **N counts every configuration tried over the project's LIFE**, not one session's sweep. The
  operator has worked on the bot for far longer than the corpus span (correction of record
  2026-09-01) — that RAISES N and lengthens MinBTL. Longer development history makes the null
  MORE expected, never less. Never cite the corpus span as the project's age.
- **Multiple-testing bias runs upward**: the best of a search is an optimistic order statistic,
  so true skill is at or below the measured −0.006. Hold-out and k-fold do not fix this (the
  hold-out is reused across the search — Dwork et al., *Science* 349, 2015).
- **A NEGATIVE OOS number is not evidence of a "loss-maximising" mechanism.** That version was
  REFUTED 0-3 in verification; the paper's negative-OOS result needs memory in the performance
  series. Cite as "a zero-edge null is not contradicted".
- **MinBTL is necessary, not sufficient**, and 512 is a nominal ceiling on N (the 8×64 sweep is
  correlated); the effective N is lower, which shortens MinBTL but cannot close an order of
  magnitude.

## Relation to the battery
[[concepts/pbo-and-cscv]] measures the deployed selection rule's luck share; OF-5 DSR (in
[[concepts/overfit-battery]]) applies the same E[max SR] deflation per trial count. MinBTL is
the a-priori version: it says how long the record must be BEFORE any of those gates can read
"real". Do not "fix" it by lowering a row floor — [[concepts/the-method]] stage 2.

## Sources
- `raw/research/2026-08-31_deep_research_null_expected_counterfactual_cost.md` (9 confirmed /
  16 refuted claims, 3-vote adversarial; primary PDFs verified verbatim, Monte Carlo reproduced)
- [[sources/session-20260901-edge-hunter-mirror]]
