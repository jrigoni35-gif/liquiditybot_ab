---
title: Wrong-Null Calibration
category: concept
summary: Comparing a proportion measured in outcome-base-rate units against a fair-coin threshold, so skilled signals mute and unskilled ones keep their voice
tags: [statistics, calibration, defect-class]
sources: 2
updated: 2026-08-05
---

# Wrong-Null Calibration

## Definition
A defect class in which a statistic is compared against a **null that does not describe the population
it was measured on**. Specifically: grading a vindication proportion — measured in the units of the
system's realized outcome base rate — against a **0.5 coin-flip** threshold.

## The instance
Realized live base win rate: **15.8% (40/253)**. Vindication weight graded against 0.5. At n=20:

| Detector | k | Wilson LCB | weight | correct? |
|---|---|---|---|---|
| no-skill "up" | 3 | 0.075 | 0.000 | yes |
| **"up" with a 2x win-rate lift (32%)** | 6 | 0.188 | **0.000** | **WRONG — muted** |
| "up" needing any voice at all | 14 | 0.558 | 0.116 | requires a 70% win rate in a 16%-win regime |
| **no-skill "down"** | 17 | 0.722 | **0.443** | **WRONG — keeps voice** |

## Why it is asymmetric
In a low-base-rate regime, "down" advice is vindicated by a loss — and losses are the common outcome.
So a null-hypothesis threshold set at 0.5 is trivially cleared by down-advice and nearly unreachable by
up-advice. **The null must be the base rate, not the coin.**

## The compounding failure
Once weight hits zero the detector is dropped from the fired set, so it accrues no further grades and
can never recover — see [[concepts/dead-mute-trap]].

## The second instance (2026-08-05): a null the model could not have beaten
The ML governor's `_judge` scored `baseline_brier` against a constant equal to **the window's own
realized mean** — an **in-window oracle**. Same shape as the instance above, one turn worse: there
the null was merely *wrong for the population*; here the null **already knew the outcomes**. An
all-loss 15-close window handed the baseline a clairvoyant **0.05** and convicted an
honestly-calibrated model on its **first** evaluation.

Fixed in commit `4799bfc7` ([[synthesis/owed-measurements]] item 30b) with `_prior_base_rate()` —
computed from rows **predating** the window only, neutral **0.5** at cold start. Note the direction
of the correction: the replacement is a **weaker** baseline, therefore **slower to convict**. When
the cost of a false positive is **killing a working model**, the null should be easy to beat, not
hard ([[entities/ml-governor]]).

> **State the null's information set, not just its value.** "Base rate" is under-specified until you
> say *whose rows, over what window*. The first instance got the units wrong; the second got the
> **time** wrong.

## Generalization
Any evidence gate must state **what null it is testing against**, and that null must be measured on the
same population as the statistic. The same shape appears in [[concepts/ghost-badge]] (a Brier compared
across base rates) and in [[concepts/null-model-floor]] (models never compared to a base-rate constant).
