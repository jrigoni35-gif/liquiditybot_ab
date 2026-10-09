---
title: Triple-Barrier Labeling
category: concept
summary: Labeling a signal by which of three market- or horizon-determined barriers is hit first: profit target, stop, or vertical
tags: [labeling, afml, ml]
sources: 5
updated: 2026-08-01
---

# Triple-Barrier Labeling

## Definition
A signal is labeled by which of three barriers it touches first — the **profit target**, the **stop**,
or the **vertical (time) barrier** — net of cost. All three are market- or horizon-determined; **no
policy exit reason may enter the label.**

## Why it replaced exit-policy replay
The superseded scheme replayed the live exit engine, so the label recorded **which exit fired** rather
than whether the signal was good. Evidence: label rate by exit reason spanned **100x**, and
**barrier-alone AUC (0.769) beat the full 62-feature model (0.597)**.

> "A time-stop is a RISK CONTROL ('we chose not to wait'), not an OUTCOME ('the signal was wrong')."

## The canonical warrant
Fixed-time-horizon labeling is listed as a documented pitfall, with the triple-barrier method as the
prescribed remedy; corroborated by two independent peer-reviewed trend-labeling studies.

## What it does not fix
The **parameterization**. With barriers floored by cost rather than scaled by volatility, the method's
own assumption is violated and outcomes degenerate to 87.8% time-outs — see
[[concepts/cost-to-volatility-ratio]]. The document making this point is explicit: **it does not say
the method is wrong; it says the parameterization is outside the informative range.**

## Origin
[[entities/lopez-de-prado]]

## Companion machinery
[[concepts/average-uniqueness-and-ess]] for the non-IID overlap; purged walk-forward with embargo for
validation; a barrier-provenance column distinguishing a no-touch expiry from a stop-out.
