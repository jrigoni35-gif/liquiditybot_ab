---
title: The Certificate Hierarchy
category: concept
summary: An influence on a real-time loop is admissible only with a bound that holds before the data arrives
tags: [doctrine, real-time, design]
sources: 1
updated: 2026-08-01
---

# The Certificate Hierarchy

## The principle
> **An influence on a real-time loop is admissible only with a CERTIFICATE — a bound that holds before
> the data arrives.**

Argued from execution-time-certified control: you cannot decide after the fact whether an input was
affordable.

## The four certificates
1. **Time certificate** — advice must fit the cycle's sampling budget **by construction** (bounded
   windows and deques) or abstain. **"A late answer in a real-time loop is a wrong answer."**
2. **Evidence certificate** — an alpha claim keeps its voice only while its Wilson-bounded vindication
   beats its null. *Shipped* as the [[concepts/vindication-ledger]].
3. **Significance certificate** — any calendar or seasonal context enters only past a **shuffle-null**
   test. No significance means score zero. "Seasonality mining is the classic overfit trap — the
   shuffle-null and the warmup gate are mandatory, not optional."
4. **Asymmetry law** — layers that can never earn an evidence certificate within the decision's lifetime
   get [[concepts/asymmetry-law|veto rights, not alpha rights]].

## Status
**Design only.** Certificates 2 and 3 are shipped as mechanisms; the time certificate and the full
hierarchy remain unimplemented.

## Why it generalizes
The hierarchy is really a taxonomy of *what kind of guarantee* an input can offer — latency, evidence,
significance, or none — and it maps each to the maximum influence that guarantee can justify. That
mapping is reusable well beyond this system.
