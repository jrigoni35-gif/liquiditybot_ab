---
title: The Assurance Spine
category: concept
summary: Seven modules every decision must pass through to be accountable: codes, audit, fault, clock, contracts, registry, and an offline self-test
tags: [assurance, architecture, accountability]
sources: 2
updated: 2026-08-01
---

# The Assurance Spine

## The seven modules
| Module | Role |
|---|---|
| reason-code registry | append-only; every reject/clamp/fault/deploy carries a code |
| audit trail | **hash-chained JSONL**; editing breaks the chain at the exact record |
| fault manager | **latching** faults; INIT/ARMED/DEGRADED/HALTED |
| clock | **monotonic authority** for intervals; wall time for audit stamps only |
| feature contract | versioned schema enforced at every inference and training load |
| model registry | SHA-256 identity, immutable archive, model cards, append-only lifecycle ledger |
| offline self-test | power-on built-in test, no network |

## The governing method
Modules already at assurance grade were carried forward **unchanged**: *"rewriting sound code for its
own sake adds risk, not assurance."*

## Operations doctrine
- **"DEGRADED means degraded"** — nothing auto-clears; an operator must clear the named fault.
- Audit chain and registry ledger are **append-only**.
- **"The governor can only make the bot more conservative than config."**
- The fix for a degraded model "is a better model through the deployment gate, **not a bigger knob**."
- A bounded-config trick to effectively disable screening is **refused at init**.

## The intent record
Under a legal standard where intent is **inferred from conduct**, the audit trail is the defense:
**"If a regulator asked 'why did the bot do X at time T,' the answer is a file, not a recollection."**
The independent criminology reading reaches the same conclusion and adds the instruction:
**"protect it, don't extend it."**

## The registry itself
[[entities/reason-code-registry]]

## Where reality diverges
The audit found latched fault state **not persisted** (so a CRITICAL latch is silently re-armed by a
routine restart) and several dispositions carrying **unregistered** codes despite the "every disposition
carries a code" invariant. See [[comparisons/stated-invariants-vs-audited-reality]].
