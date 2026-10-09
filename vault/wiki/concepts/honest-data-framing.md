---
title: Honest Data Framing
category: concept
summary: Distinguishing a defect in collecting from a defect in counting: the data was fine, the pipeline was weighting it wrong
tags: [labeling, framing, diagnosis]
sources: 1
updated: 2026-08-01
---

# Honest Data Framing

## The framing
> **"Nothing was mislabeled and nothing needed deleting" — the defect is in counting, not collecting.**

A quiet weekend produced ~200 rows that were ~97% negative labels. The instinct is to suspect the data.
The finding was the opposite: the batch was **honest data from a correctly-functioning pipeline**, and
the defect was that the pipeline **counted** it as ~200 independent facts when it was worth about one.

## Why the distinction is load-bearing
It determines the entire remedy:
- *Collecting* defect -> filter, delete, or fix the source.
- *Counting* defect -> **reweight**, and leave every row in place.

Choosing the second preserves the corpus. And the correction chosen was **mass-preserving** — it
redistributes weight rather than removing it, so the total regularization balance is unchanged.

## The same principle, later and larger
When [[concepts/era-exclusion]] removed thousands of rows from the training view, the same framing
applied: **exclusion is a load-time view, not a destructive filter** — "no data was lost, the tuition
already paid is recoverable as evidence." Every row stays byte-for-byte on disk.

## The generalized rule
**Never delete a row to fix a statistic.** Reweight it, or filter it at read time, and keep the record
complete. This is the corpus's most consistently-honored data principle — and it is why the entire era
saga was reversible.
