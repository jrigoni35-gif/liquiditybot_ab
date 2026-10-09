---
title: Whole Code Audit (2026-07-23)
category: source
summary: Seven-domain parallel read-only audit producing 31 findings in two waves, and the only document that reports the system's invariants actually failing
tags: [audit, findings, invariants, fail-open]
sources: 1
updated: 2026-08-01
---

# Whole Code Audit (2026-07-23)

**Raw source:** `raw/audits/2026-07-23_whole_code_audit.md`

## Method
Seven read-only domain auditors (money path, state/persistence, ML loop, engine/runner, config/guards,
ops sidecars, data/signals) sweeping one commit. Prior hypotheses adjudicated as CONFIRMED /
CONFIRMED-narrow / CONFIRMED-sharpened / REFUTED-at-call-site. Every fix lands **TDD, failing repro
first**. See [[concepts/parallel-domain-audit]].

## Wave 1 — eight HIGH safety-critical findings
- **W1-1** — a deterministic raise in the hourly cycle (ordered BEFORE the fast cycle) **starves ALL
  exits indefinitely**, and the wedge alert text **claims the opposite**. Fix: isolate hourly/slow, run
  the fast cycle first.
- **W1-2** — no per-event isolation in fill application; one raising handler **discards the rest of the
  batch** (book/venue desync; dry-run loss permanent).
- **W1-3** — two unguarded restore lines **crash every boot** on a non-mapping snapshot section.
- **W1-4** — one shared try/except spans 7 subsystems, so a malformed monitor section silently skips
  circuit-breaker and loss-budget restore — **"trip laundered by reboot."**
- **W1-5** — the hedge OPEN branch has no mark-freshness gate and no new-risk authority check; it **can
  submit new hedge risk mid-catastrophe off frozen marks**.
- **W1-6** — a one-sided venue book with a healthy combined book: the spread veto reads the *combined*
  book, `p_fill` defaults to the **optimistic** value, and the participation clamp **silently no-ops at
  zero depth (skips instead of clamping)**.
- **W1-7** — the auto-updater has no "diverged" outcome, so diverged histories re-run the full battery
  every 15 min forever with **deploys silently bricked**.
- **W1-8** — force-kill escalation targets a lock file's PID with no identity check; **PID recycling
  can kill the supervisor or a user process**.

## Wave 2 — 25 correctness/robustness items
Highlights: the label sim omits live trail-tightening -> **optimism-biased labels** in a specific p_win
band; non-atomic model write races the runner; venue-book expiry lets combined-book samples **poison
imbalance/depth histories** for ~30 min; the websocket book **checksum is never validated**; negative
ages read as fresh so a backward clock step silences all cadences; **latched fault state is not
persisted, so future CRITICAL latches are silently re-armed by a routine restart**; several reason
codes are **not registered** despite the "every disposition carries a code" invariant; a frozen touch
**fabricates basis/edge during outages**.

**Config drift batch**: ~8 code defaults disagree with shipped config — most consequentially
`min_half_spread_bps` **4 vs 26**, which would not clear a 25 bps maker fee, undermining the QT-01
"passive round trip is never net-negative" guarantee.

## Findings created by the fixes
- **W2-26** — the book-walk cost returns **0.0 instead of the veto sentinel** when the walked side is
  wholly empty, so a taker entry against a one-sided book gets **zero walk cost instead of a veto**.
- **W2-27** — a **newly-introduced regression from the W1-1 fix**: a persistently raising watchdog no
  longer trips the wedge guard, so entries proceed on the **FROZEN prior `entries_blocked` value —
  failing OPEN on the entries side during the one incident that breaks the watchdog.**

## Clean-area consensus
All seven auditors independently confirmed: firewall self-validation, sizer/protocol degenerate-case
handling, audit-chain healing, position/order round-trip fidelity, sanitize boundary, **THALES
clamps**, walk-forward purging, calibration OOF discipline, evidence floors.

## Significance
This is **the only document that reports the invariants failing** — exits starvable, fault latches
lost on reboot, reason codes unregistered, optimistic maker fill probability, and two distinct
fail-open paths. See [[comparisons/stated-invariants-vs-audited-reality]].

## Related
[[entities/config-guard]] · [[entities/pretrade-gate]] · [[entities/reason-code-registry]]
