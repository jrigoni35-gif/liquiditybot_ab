---
title: "The Bot vs a Discretionary Trader vs an Algo Trader — Two Panels, Opposite Answers"
category: comparison
summary: "Given only the trade ledger, a professional discretionary trader identifies the machine INSTANTLY on mechanics (modal ticket exactly $18.00 x51, after-win/after-loss ratio 1.000, 0.0% round-number landing, 8-decimal sizes, 100% limit 1019/1019, 59 holds at exactly 5.000s, chi2 137.8 with zero empty hours) but finds its ECONOMICS indistinguishable from an unprofitable retail human (58.3% win rate on 0.670 payoff, disposition effect 2.20x); an algorithmic trader skips the identification question entirely and returns a colder verdict on the only question that matters — gross edge -0.0019% at t=-0.332, fees 368x |edge| in percent space, a 0.91h median winner against 0.71% round-trip cost, and 60.6% taker fills on a book whose thesis is maker execution"
tags: [turing-test, behavioral, comparison, economics, execution, disposition-effect]
sources: 1
updated: 2026-08-09
---

# The Bot vs a Discretionary Trader vs an Algo Trader

> **Paper/real boundary** ([[concepts/paper-real-boundary]]). Mechanical tells are **repo-side**
> — properties of the order stream the code generates. Economic tells are **sim-side** and inherit
> every optimism of the fill simulator. Source: [[sources/session-20260809-turing-test-hedge-verdict]].

## The setup

One ledger, two professional readers, one question each:

| Reader | Question they actually ask |
|---|---|
| **Discretionary trader** | *"Is there a person behind this?"* |
| **Algorithmic trader** | *"Is this worth running?"* |

They disagree about almost everything except the conclusion.

## Panel 1 — the discretionary trader: machine, instantly

| Tell | Reading |
|---|---|
| Modal ticket | **exactly $18.00, x51** |
| After-win / after-loss size ratio | **1.000** |
| Round-number landing | **0.0%** |
| Size precision | **8 decimals**, 31 dust legs to **1.17e-09 ETH** |
| Order type | **100% limit — 1019/1019** |
| Hold time | **59 trips at exactly 5.000s** |
| Hour coverage | all **24** hours, chi2 **137.8**, **zero empty hours** |

**No economic analysis was required.** The identification is made on order mechanics alone, and
the strongest single tell is the one a quant would least expect: **after-win/after-loss size ratio
= 1.000.** Human sizing after a loss is *never* identical to sizing after a win. Emotional
invariance is the machine's fingerprint.

> **The chi2 is the instructive one.** chi2 **137.8** rejects a uniform hour distribution — the
> bot's hours are *uneven*, which superficially looks human. **Zero empty hours** is what
> convicts. A person's ledger has a sleep hole. *Uneven with no hole* = a schedule, not a routine.

## Panel 2 — the same trader on the economics: a losing retail human

| Signature | Bot | The retail analogue |
|---|---|---|
| Win rate | **58.3%** | wins often |
| Payoff ratio | **0.670** (needs ~**0.715** at that win rate) | loses more when it loses |
| Disposition effect | **2.20x** — losers **2.00h**, winners **0.91h** | cuts winners, rides losers |

**The panel cannot tell this book from an unprofitable retail account.** Not "similar to" —
**indistinguishable on the economic axes that define the profile.**

The resolution is [[concepts/behavioral-isomorphism]]: the bot has **no** psychology, so the
disposition effect here is produced by **bracket geometry**, not emotion. Near take-profit + far
stop ⇒ winners resolve sooner **by arithmetic**.

⚠️ **Citation hazard.** The corpus behind **58.3% / 0.670** was not stated at filing. It is a
**third** payoff derivation alongside the 0.561-vs-0.750 pair at n=217 in
[[synthesis/open-contradictions-register]] entry **6**, and does **not** supersede it.

## Panel 3 — the algo trader: the identification question is uninteresting

```
gross edge (per trade)       :  -0.0019%
t-statistic                  :  -0.332
fees / |edge| (percent space):   368x
median WINNER hold           :   0.91 h
round-trip cost              :   0.71%
taker fill share             :   60.6%
```

Four objections, each independently fatal:

1. **No edge exists to trade.** `t = -0.332` — indistinguishable from zero. The book is **flat on
   selection, losing on cost**, which is the same conclusion the state-identity decomposition and
   the full-book fills reconstruction reached by unrelated methods
   ([[sources/session-20260809-unbiased-economics]]).
2. **Cost exceeds signal by 368x.** Not a tuning problem.
3. **Horizon/cost mismatch of an order of magnitude.** A **0.91h** winner must clear **0.71%**
   round trip ([[concepts/cost-to-volatility-ratio]]).
4. **60.6% taker fills** on a design whose entire premise is passive execution — the execution
   contradicts the strategy statement.

> **368x vs 32.8x are not in conflict.** 368x is *percent space, per trade*; 32.8x is *dollar
> space, whole book* (382.59 fees / 11.66 gross). Different spaces
> ([[concepts/ratio-aggregation-bias]]).

## What the disagreement is actually about

| | Discretionary panel | Algo panel |
|---|---|---|
| Verdict on **identity** | machine, instantly, on mechanics | irrelevant question |
| Verdict on **economics** | *looks exactly like losing retail* | *no measurable edge, at any horizon* |
| Implied fix | "stop trading like a retail human" | **there is nothing to fix at the execution layer** |

**They converge where it counts.** The discretionary reader diagnoses the *symptom* the corpus has
been chasing for a week (bad payoff geometry, held losers). The algo reader diagnoses the *cause*
and rules the symptom out as a lever: **selection is flat, so no exit-geometry, holding-period,
gate or filter change creates expectancy that is not in the entries** — the same sentence the
corrected `breakeven_test` now prints ([[synthesis/the-money-path-thesis]]).

> **The most useful single line from the pair:** *the bot is mechanically inhuman and economically
> a retail loser* — and the second half is the one that costs money.

## Related

[[concepts/behavioral-isomorphism]] · [[concepts/cost-to-volatility-ratio]] ·
[[concepts/payoff-asymmetry]] · [[concepts/ratio-aggregation-bias]] ·
[[concepts/paper-real-boundary]] · [[concepts/who-loses-to-us]] ·
[[comparisons/tradingagents-vs-liquiditybot]] ·
[[sources/session-20260809-turing-test-hedge-verdict]] ·
[[sources/session-20260809-unbiased-economics]] ·
[[synthesis/the-money-path-thesis]] · [[entities/liquiditybot]]
