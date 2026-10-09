---
title: "The Self-Flattery Gradient (every distortion measured ran one direction)"
category: concept
summary: "A measurement error is a coin flip; a population of them landing on the same face is a process fact — 25 adversarial agents swept every reporting surface on 2026-08-09 and found eleven distortions, ALL of which make the bot look better than it is, and ZERO that understate it, which converts a list of unrelated bugs into a single systematic bias with a testable prediction: the honest numbers are worse than the reported ones, never better"
tags: [bias, reporting, audit, unbiased, falsifiability, telemetry]
sources: 1
updated: 2026-08-09
---

# The Self-Flattery Gradient

## The claim

**A single measurement error has no direction — it is as likely to understate as to overstate.**
**A population of measurement errors that all point the same way is not a set of bugs. It is a
bias, and the bias itself is the finding.**

On **2026-08-09** a 25-agent adversarial sweep asked one question of every reporting surface in
the repo — *"where does the bot look better than it is?"* — and returned:

> **Every distortion found runs the SAME direction: flattering.**
> **Zero instances were found of the bot understating itself.**

([[sources/session-20260809-adversarial-audits]])

## The population

| # | Surface | Distortion | Direction |
|---|---|---|---|
| 1 | `scripts/breakeven_test.py` | discards all 159 hedge round trips; median gross **+0.0505%** instead of **−0.0303%**, flipping the printed verdict | **flatters** |
| 2 | `main.py:1671` perf ledger | the entire **−325.70** hedge book invisible to expectancy / win rate / profit factor / Sharpe | **flatters** |
| 3 | `main.py:1671` circuit breaker | 159 consecutive losing hedge round trips never counted as losses | **flatters** (risk under-reported) |
| 4 | `performance.overall` | pools 91% EV-gate-bypassed probes with conviction trades → **−0.2838** vs conviction **−1.5840** | **flatters** (5.6x) |
| 5 | `scripts/cost_attribution.py` | blind to its own largest cost event; 0.668% vs blended **0.7766%** | **flatters** (1.16x) |
| 6 | Fill simulator | 22.30% per-order fill vs 11.66% calibration target — two fill chances per event | **flatters** (1.19x–1.91x) |
| 7 | `risk/position_sizer.py` | heat/inventory read as an empty book — three risk controls inert, **all permissive** | **flatters** (risk under-reported) |
| 8 | Grafana hero tile "Net P&L (all time)" | plots **−208.31** described as *"the true bottom line … hedges included"*; true **−382.34** | **flatters** |
| 9 | Both drawdown gauges | plot a cash-only start-to-now figure while the hard stop fires on peak-to-now MTM — a **−20% book reads FULL GREEN** | **flatters** |
| 10 | `state.py` P&L reporting | 49% of lifetime fees (185.94) appeared in **no** readable P&L number | **flatters** |
| 11 | `fills.csv` fee ledger | short by **6.24 (1.6%)** against `fees_paid_total` | **flatters** |

**Eleven for eleven.** Items 7 and 10 are fixed (`1fee174e`, `a6334162`); the rest are open.

## Why the direction is not a coincidence, and not (necessarily) intent

Nobody wrote a flattering ledger on purpose. The gradient is **structural**, and three mechanisms
account for most of it:

1. **The excluded population is the loss-making one.** Hedges, probes and forced closes are the
   ugly parts of the book. A filter written for a *reasonable* reason (*"count only entries"*,
   *"the ML lane is what matters"*) will preferentially remove them
   ([[concepts/uncounted-exclusion]]).
2. **Defaults resolve toward permissive.** An absent reading defaults to 0.0; 0.0 heat means *"no
   risk on"*; 0.0 drawdown means *"green"*. **The sentinel for absence sits on the safe-looking
   side of every threshold** ([[concepts/zero-is-not-a-reading]]).
3. **A number that looks bad gets investigated; a number that looks fine does not.** This is the
   asymmetry that lets the flattering defects **accumulate** while the pessimistic ones are found
   and fixed within a day. Selection pressure on bug lifetime, not on bug creation.

> Mechanism 3 means the gradient **self-reinforces**, and it is why "we would have noticed" is
> not a defence. The whole point is that the ones you notice are the other kind.

## The testable prediction

The gradient is falsifiable, which is what makes it a finding rather than an attitude:

> **Every future correction to a reported performance number will move it DOWN, not up — until
> the gradient is addressed at its source.**

**Already tested twice, on 2026-08-09 itself, in the honest direction:** two of this session's own
claims were **corrected DOWNWARD in magnitude** by verification passes
(*"hedging is 84% of the loss"* → a one-day already-fixed incident, ~7% go-forward; cost
attribution *"6.4x"* → **1.16x**). **The gradient predicts the sign of corrections to the BOT's
numbers, not to the AUDIT's** — and an audit that only ever revises its findings upward would be
exhibiting the same disease ([[concepts/adversarial-verification]]).

## What it changes about how numbers are read

1. **Treat any bot-reported performance figure as an UPPER BOUND** until its population is
   stated. This is the same discipline already applied to sim fills, generalized off the
   execution plane ([[concepts/paper-real-boundary]]).
2. **When a corrected number surprises you by being worse, that is the prior, not an anomaly.**
3. **Audit for direction, not just for defects.** The single most informative line of a 25-agent
   sweep was not any defect — it was **the tally**.
4. **A surface with no known distortion is not evidence of honesty** if nobody has asked it the
   question adversarially.

## Relationship to the neighbouring classes

- [[concepts/unfalsifiable-explanation]] — the **rhetorical** analogue. That page is about a
  vocabulary that absorbs bad results; this one is about **instruments** that soften them. Same
  net effect on the operator's picture, two different organs.
- [[concepts/uncounted-exclusion]] — supplies the single most common **mechanism** here.
- [[concepts/pooled-populations]] — supplies the second.
- [[concepts/cost-truth]] — the book-level consequence: the reported cost picture is optimistic
  at every layer simultaneously.

## The economic reading

The gradient's practical significance is that it **cannot** rescue the book. With gross P&L
before any fees measured at **−11.66** (state identity) and **−13.01** (independent full-book
reconstruction) against **382.59** of fees, every distortion pointing *toward* flattery means the
honest picture is **worse**, not better:

> **gross edge ≤ 0** ([[synthesis/the-money-path-thesis]]).

## The gradient reaches ADJUDICATIONS, not just measurements (2026-08-10)

The 08-09 sweep catalogued eleven **measurement** distortions. The closure of docket item 57
([[sources/session-20260810-fill-double-count]]) found the gradient operating one level up — on
the **adjudication** that decided a finding's fate:

| date | what happened |
|---|---|
| **08-07** | The fill-sim double-count is **correctly named**: *"the calibrated trade-through frequency is spent twice."* |
| **08-08** | It is **disposed of** as *"conservative floor, by design"* — a framing that is **backwards** (the hazard ran only inside `if book:`; it modelled nothing the snapshot could not show, and `invert_base_prob` had already solved `sf_base` so the hazard alone reproduces the crossing rate). |
| **08-10** | Derived and confirmed: `2f−f² = 21.96%` vs an `f = 11.66%` target, ledger-measured **22.30%**, **1.88x at the touch.** 08-07 was right. |

> **The distortion did not have to survive a measurement — it only had to survive a paragraph.**
> Nothing was mis-measured on 08-08; the numbers in that filing were careful enough to catch the
> author's own test-count error (8 claimed vs 7 collected). **The scrutiny went to the numbers and
> skipped the disposition** — and the disposition was written in the same section as a genuine,
> well-verified fix, by an author who had just earned the right to feel finished.

**Add this surface to the gradient's catalogue.** The eleven distortions were all *instruments
reporting*; this one is a *docket closing*. Both run the same direction, and the second is cheaper
to produce: **closing an item requires no evidence, only a sentence.**

> **Operational rule:** *a disposition that closes a docket item deserves the same adversarial pass
> as the finding that opened it — and MORE when it is written beside a fix the author is pleased
> with.* Cost of skipping it here: **two days with a 1.88x bias live**
> ([[concepts/adversarial-verification]], [[synthesis/open-contradictions-register]] entry 25).

## Related
[[concepts/uncounted-exclusion]] · [[concepts/pooled-populations]] ·
[[sources/session-20260810-fill-double-count]] · [[concepts/generosity-masks-fragility]] ·
[[concepts/zero-is-not-a-reading]] · [[concepts/unfalsifiable-explanation]] ·
[[concepts/adversarial-verification]] · [[concepts/cost-truth]] ·
[[concepts/paper-real-boundary]] · [[synthesis/the-money-path-thesis]] ·
[[sources/session-20260809-adversarial-audits]] ·
[[sources/session-20260809-unbiased-economics]]
