---
name: meta-labeling-unvalidated
description: Meta-labeling and selective/abstention filters are ruled out for this bot on both theory and evidence - do not propose them as a fix
metadata: 
  node_type: memory
  type: reference
  originSessionId: 63d8f842-8108-448c-b2d9-fa9a4c8a2da4
  modified: 2026-08-02T14:14:15.422Z
---

Researched 2026-08-02 after I recommended meta-labeling and had to retract it
twice. Do not re-propose it without reading this.

**Theory — abstention cannot create edge, and here it actively degrades.**
Selective risk is a coverage-weighted average of conditional risk, so
`sup(selective payoff) = ess sup_x pi(x)`: if expected payoff is negative
almost everywhere, every rule with positive coverage loses. Worse, Jones,
Sagawa, Koh, Kumar & Liang (**ICLR 2021, Proposition 1**) prove selective
accuracy *monotonically decreases* with the abstention threshold when
full-coverage accuracy is below 1/2. This bot's realized win rate is **5.5%**.
Franc, Prusa & Voracek (JMLR) further show the cost-based, bounded-coverage
and bounded-improvement rejection models are all **equivalent to one
threshold on conditional risk** — meta-labeling is not a distinct mechanism,
and a secondary model adds nothing unless its ranking beats the primary's own
confidence at tracking realized conditional risk.

**Evidence — there is none.** Zero independent peer-reviewed empirical tests
exist. The four vendor (Hudson & Thames, JFDS) papers have 0/0/1/1 citations
and neither citing work tests the technique. The whole independent base is six
student theses: the only clean A/B design (Wolner-Hanssen 2023, Lund
bachelor) found meta-labeling **worse than no meta-labeling** on every axis;
the only cost-inclusive study (Schneider, ETH) **self-declares its findings
invalid** from leakage; one reports Sharpe 13.2 from an AUC-0.56 classifier
(a leakage signature, not a result).

**It has never been tested on a losing strategy.** Arzt (ETH 2021) states the
selection criterion outright: *"Four profitable trading systems are
meta-labeled."* Profitability was a precondition for inclusion.

**Costs are the decisive gap and ours are double.** Six of seven studies
exclude transaction costs. The one that included them used 0.25%/trade and
found costs consumed 38-58 percentage points of cumulative return, flipping
one pipeline to -1.2% alpha. **This bot's round trip is 0.50%.**

**If it is ever tried anyway**, it goes in only as a challenger arm judged on
out-of-sample Brier against the new-era champion, with validation quarantined
to new-era rows. That is the one framing where being wrong costs nothing.

Also ruled out on the same reasoning: any "confidence filter", "quality gate",
or abstention layer added on top of the existing signal. They are the same
threshold wearing a different name.

Related: [[432-migration-hold]]
