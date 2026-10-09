---
title: Priced Bleed
category: concept
summary: "Quantifying the P&L cost of a learning intervention before deciding, and treating the cost as tuition for real labels — and, as of 2026-08-09, carrying the falsifier it always lacked: 'tuition' predicts the labels TEACH something, and after 305 live labels costing ~382.59 in fees the OOF AUC is 0.43–0.48 (at/below chance), so the spend has bought no measured discrimination. A priced bleed must also be a MEASURED bleed; and 9,570 candidate rows cost zero fees"
tags: [decision-making, exploration, economics, falsifiability]
sources: 2
updated: 2026-08-09
---

# Priced Bleed

## Definition
Before adopting an intervention whose purpose is to generate evidence rather than profit, **quantify
what it will cost** and record the number in the decision.

## The instance
Exploratory probes accounted for **-$22.87 of -$31.68 net** over the measurement window. The decision to
keep admitting them under a drought floor was taken **with that number on the record**, framed as:

> It is paper mode, "so the bleed is simulated while the labels are real learning."

## Why the framing matters
It converts an ambiguous tradeoff ("probes lose money but we need data") into an explicit price
("evidence costs $22.87 per window at this rate"). That price can then be compared against alternatives
and revisited when the rate changes.

## The related honesty
The same posture appears when a horizon re-alignment shrank the training corpus from ~2,141 rows to
379: the loss is stated as an **accepted cost** with the reason — "the 2,146 rows labelled at a 96-bar
horizon answer a question the bot no longer asks" — and paired with the reassurance that the exclusion
is a **view, not a deletion**, so "the tuition already paid is recoverable as evidence."

## Generalization
Any learning investment — exploration budget, labeling spend, shadow-mode compute — should carry a
priced line in the decision that adopts it. An unpriced learning cost is an unexamined one.

## The falsifier this concept was missing (2026-08-09)

Pricing a bleed answers *"what did the evidence cost?"* It does **not** answer *"did the evidence
teach anything?"* — and for a year the second question was never asked, because **"exploration is
tuition"** reads as a complete justification on its own.

**It is not.** Stated as a falsifiable claim, *tuition* predicts **the labels are teaching
something**. Measured 2026-08-09 ([[sources/session-20260809-unbiased-economics]]):

| The prediction | The measurement | Verdict |
|---|---|---|
| the purchased labels raise discrimination | out-of-sample **AUC 0.43–0.48** across logistic/gbt/mlp — **at or below chance** — after **305** live labels; champion Brier **0.24728** vs **0.25** for predicting a coin | **NOT YET.** The tuition has bought no measured discrimination |

And the bill is now known in full: **382.59 of fees against a gross P&L of −11.66** — the
exploration programme's lifetime tuition is **32.8x** the absolute gross edge it was buying
information about.

> **The rule this page now carries:** *a priced bleed must also be a **measured** bleed.* Record
> what the spend cost **and** name the observation that would show it bought nothing. An unpriced
> learning cost is an unexamined one — and **a priced learning cost with no falsifier is
> unexamined in the more dangerous way**, because it looks rigorous.
> ([[concepts/unfalsifiable-explanation]])

**The concept is not withdrawn.** Pricing before deciding remains correct and remains adopted.
What is withdrawn is *tuition* used as a **terminal** justification — the word now owes a
second number.

### The cheap alternative it should be weighed against
**9,570 CANDIDATE rows are counterfactual and cost ZERO fees**, against **305 live rows that cost
~382.59**. Before any future decision prices a bleed and accepts it, it should first state why the
**free, 31x-larger population cannot answer the same question**. That comparison is now the
default first move for any "trade more to learn more" proposal
([[synthesis/owed-measurements]]).

## Related
[[concepts/probe-livelock]] · [[sources/livelock-f0-decision]] ·
[[concepts/honest-data-framing]] · [[concepts/unfalsifiable-explanation]] ·
[[sources/session-20260809-unbiased-economics]] · [[concepts/dof-budget]]
