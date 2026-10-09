---
title: Parallel Domain Audit
category: concept
summary: N read-only auditors partitioned by subsystem sweeping one commit, with prior hypotheses explicitly adjudicated
tags: [audit, method, quality]
sources: 1
updated: 2026-08-01
---

# Parallel Domain Audit

## Method
Partition the system by **domain** (money path, state/persistence, ML loop, engine/runner,
config/guards, ops sidecars, data/signals) and run one **read-only** auditor per domain against a single
pinned commit. Findings are then triaged into severity waves.

## Seed adjudication
Prior sessions' unresolved hypotheses are carried in as explicit "seeds" and each is resolved with a
verdict: **CONFIRMED / CONFIRMED-narrow / CONFIRMED-sharpened / REFUTED-at-call-site**. This prevents a
backlog of half-remembered suspicions and forces each one to a conclusion.

## Fix discipline
Every fix lands **TDD, failing repro first**, under systematic-debugging discipline — no fix without a
test that fails before it.

## The two outputs that matter most
1. **Clean-area consensus** — where all auditors independently agree a subsystem is sound. This is
   evidence that is otherwise very hard to produce, and it is what makes the negative findings
   credible.
2. **Findings created by the fix wave** — including a **newly-introduced regression from a Wave-1 fix**,
   where isolating a raising component meant a broken watchdog no longer tripped the wedge guard, so
   entries proceeded on a **frozen** prior value — failing OPEN during the one incident that breaks the
   watchdog. Fixing a fail-closed bug created a fail-open one.

## Why it is the corpus's most valuable audit
It is **the only document that reports the system's own invariants failing** — exits starvable, latched
faults lost to reboot, unregistered reason codes, an optimistic default fill probability, and two
distinct fail-open paths. See [[comparisons/stated-invariants-vs-audited-reality]].

## The conscious re-decision marker
One finding is tagged as requiring a **CONSCIOUS RE-DECISION** rather than a fix — an existing behavior
that may be right or wrong, pinned by test as intended, and flagged for a human to rule on. A useful
third category beyond bug and non-bug.
