---
title: Marcos Lopez de Prado
category: entity
summary: The methodological authority behind the labeling, weighting, validation and overfit machinery
tags: [person, external, literature]
sources: 6
updated: 2026-08-01
---

# Marcos Lopez de Prado

The single most load-bearing external authority in this corpus, appearing in **two distinct roles**.

## As the labeling and validation authority
*Advances in Financial Machine Learning* supplies:
- **Triple-barrier labeling** (ch.3) as the prescribed remedy for fixed-time-horizon labeling, which is
  itself listed as a documented pitfall.
- **Overlapping-label machinery** (ch.4) — concurrency, average uniqueness, sequential bootstrap. The
  non-IID quote is used verbatim as the warrant for the weighting fix.
- **Purged cross-validation with embargo**; the repo's implementation is noted as **stricter than the
  book**.
- **Clustered feature importance**, the basis for block-permuting correlated features.

## As a co-author of contested work
Also co-author of the flow-toxicity metric that the research sweep **explicitly declines to build on**:
"VPIN is CONTESTED in its home market — do not build on it," citing a refutation finding no early
warning and a mechanical volume artifact. The corpus cites the same author as authority in one domain
and declines his metric in another — a good example of source-level rather than author-level trust.

## The deflation lineage
Deflated Sharpe and the backtest-overfitting probability both trace to this line of work, and both are
implemented as hard gates (OF-5, OF-3).

## Related
[[concepts/triple-barrier-labeling]] · [[concepts/average-uniqueness-and-ess]] ·
[[concepts/pbo-and-cscv]] · [[concepts/overfit-battery]]
