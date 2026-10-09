---
title: Adoption Ledger
category: concept
summary: A four-bucket adjudication of an external system — ADOPT, ADAPT, REJECT, ALREADY AHEAD — plus a self-check derived from their bug reports
tags: [method, external-systems, adjudication]
sources: 3
updated: 2026-08-04
---

# Adoption Ledger

## Structure
Every candidate from an external system is sorted into exactly one of:
- **ADOPT** — take it, with the shape it must have under our law
- **ADAPT** — take the *concept*, not the implementation
- **REJECT** — with the specific reason
- **ALREADY AHEAD** — do not envy this

Plus a fifth section that is the real payload: **"their bug classes -> ours"**, a read-only self-check
list derived from the external project's own issue tracker.

## The reusable pattern
> **Adopt other people's failures, refuse their successes.**

Headline performance numbers are treated as inadmissible when produced without purging, null tests, or
selection-bias correction. Bug reports, negative results, and self-disclaimers are treated as the
valuable content. One external system's finding that LLM agents' decisions vary by underlying model is
filed as **"negative evidence FOR us"** — external validation of our own boundary.

## "Shape under our law"
Every ADOPT carries a compliance clause: read-only, zero engine state, zero new reason code, never
imported by the decision cycle, same trust tier as the offline check scripts, no degrees-of-freedom
cost. An adoption that cannot state its shape is not an adoption.

## The discriminator used
**"Produces numbers vs produces text."** Any mechanism that yields a number we already compute
deterministically is not an adoption candidate; the only genuinely missing thing was a human-legible
per-decision outcome narrative — **and only offline, never in the engine**.

## The worked cases
1. [[entities/tradingagents]] · [[comparisons/tradingagents-vs-liquiditybot]] — an LLM
   scaffold producing text; 4 ADOPTs confined to offline reporting, 12 REJECTs.
2. [[entities/mythos-router]] ([[sources/session-20260804-mythos-router]]) — an external
   write-discipline tool: **ADOPT** its SWD receipts (tooling-only MCP, under a blocking
   write policy — "shape under our law" made literal as `.mythos/policy.json`), **REJECT**
   its memory system (the vault is the sole brain — a third memory store would fragment
   truth) and its NVIDIA distillation blueprint (addresses neither geometry nor corpus;
   YAGNI). The case also added a new ledger discipline: **adjudicate the scanner too** — the
   pre-install security audit's FAIL verdict was itself adjudicated finding-by-finding
   (36/36 false positives, [[concepts/iron-law-of-debugging]]).

## Durability
Rejections are **binding on future sessions**: "future sessions must not re-propose them without new
evidence." See [[concepts/evidence-grading-ladder]].
