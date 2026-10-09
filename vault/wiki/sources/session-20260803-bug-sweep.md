---
title: Bug Sweep (2026-08-03) — Duplicate Log Pusher, Benign −50bps Signature, Gate-Stats Watch, First Honest-Fills Day
category: source
summary: "Post-restart bug sweep, commit d67fd6a5 (pushed): one CONFIRMED+FIXED bug (pc_supervisor spawned a duplicate gc_log_pusher pair because it judged liveness by stdout-log mtime and the pusher printed only when shipping — every log line shipped to Grafana Cloud twice for ~22h; fixed with a 55s quiet heartbeat, self-cleaned live via _source_changed); one suspicion CLASSIFIED BENIGN (slip exactly −50.0bps = long_book add_offset_pct=0.5 resting bids by design, order_ids audit-verified — arithmetic shape alone cannot distinguish design from fixture); one watch ARMED not adjudicable (ml.gate_stats.realized_closed=0 after first post-restart closes — nearly all were old-runner entries with no gates attached; ADJUDICATED 08-04 late: loop WORKS, counter moved 0→1 on the first organic post-restart close); one EXPECTED error (ML-032 retrain request, 37% feature drift, day after the fill-regime change); and the first honest-fills day measured (~8 positions/day vs ~16, exits flowing, cohort 14/50 post-432 0 wins Wilson [0,21.5%], equity $4,930.79, fills 655 rows zero fixture signatures)"
tags: [session, bug-sweep, observability, provenance, honest-fills, cohort]
sources: 1
updated: 2026-08-04
source_path: none — session work product (see Provenance)
source_date: 2026-08
authors: [operator, claude]
ingested: 2026-08-03
---

# Bug Sweep (2026-08-03)

## Provenance
Session work product — no `raw/` snapshot. Ground truth: commit `d67fd6a5` (**pushed**;
head = remote = `d67fd6a5`, so the deploy stall recorded in
[[sources/session-20260802-digest]] is **resolved** — the deploy chain is fully live). The
duplicate-pusher evidence is in Grafana Cloud's doubled log lines for the ~22h window and the
process table before/after the fix landed.

Six findings, each with a verdict.

---

## 1. CONFIRMED + FIXED — gc_log_pusher duplicate-spawn bug

**Mechanism (named, per the [[concepts/iron-law-of-debugging]]):** `pc_supervisor` judges pusher
liveness by **stdout-log mtime** with `STALE_SEC=120`, and `gc_log_pusher` printed **only when
shipping events**. During the 2026-08-02 22:05 runner bounce no events flowed, so a healthy,
idle pusher read as stale, and the supervisor spawned a **second pair** — after which **every log
line shipped to Grafana Cloud TWICE for ~22 hours**.

- **Fix:** a **55-second quiet-heartbeat line** (safely inside the 120s staleness window), so an
  idle pusher stays visibly alive. Stdlib-only preserved — sidecar philosophy, no engine imports
  ([[entities/observability-sidecars]]).
- **Self-cleaned live via `_source_changed`:** both duplicate pairs exited when the edit landed,
  the supervisor relaunched one fixed pair — **4 processes → 1**. No manual process surgery.
- **Sibling immunity was accidental:** the other sidecars never had the bug **only because they
  print every tick**. The failure mode is now named —
  [[concepts/liveness-by-output-cadence]] — so the immunity is a checked property, not luck.
- **Blast radius:** duplicated telemetry shipping only — no engine, order, or ledger path was
  involved; the cost was doubled Grafana Cloud ingest for the window.

## 2. CLASSIFIED BENIGN — slip exactly −50.0bps is long_book design, not fixture

Entries with slip of **exactly −50.0bps** looked like a fixture signature (an exact ref×constant
shape, the same arithmetic silhouette as the `1491.018493 × (1 − 2.5bps)` fixture fill in
[[sources/session-20260802-digest]]). They are not: they are **[[entities/long-book]]
accumulation adds** — `add_offset_pct=0.5` rests bids **0.5% below mark by design**, and the
config's `_entry_doc` records the **1.5 → 0.5 collar history**. The `order_id`s were
**audit-verified** against the hash-chained `audit.jsonl` — the decisive provenance signal.

> ⚠️ **Citation hazard (filed under [[concepts/iron-law-of-debugging]]):** an exact
> ref-multiple fill can be **design** (a resting offset) or **fabrication** (a fixture). The
> arithmetic alone does not distinguish them; **the audit chain does**. Never convict on shape.

## 3. WATCH ARMED, not adjudicable — `ml.gate_stats.realized_closed` still 0

After the first post-restart closes, `ml.gate_stats.realized_closed` = **0** — this is
**tripwire #1** of the 432-hold watch list ([[synthesis/owed-measurements]] item 1b; stuck at 0
would mean the realized-outcome loop is dead again). **Not yet adjudicable:** nearly all
overnight closes were **old-runner entries with no gates attached** (nothing for the counter to
count), plus **one ambiguous ADA probe-path case**. **Discriminator:** the next few closes of
**organic post-restart entries** — if those also leave the counter at 0, the tripwire has fired;
if it climbs, the loop is alive. Verdict withheld per [[concepts/honest-null-result]] discipline.

> **ADJUDICATED 2026-08-04 late — the loop WORKS.** The discriminator resolved: an
> organically-entered post-restart position closed, `note_realized` credited it, and
> `realized_closed` moved **0 → 1** — the realized-outcome loop (`07d38a51`/`162c595c`) is
> wired end-to-end in production (gates → `order.meta` → position → close → era-keyed ledger).
> `realized_active` correctly False (1/25 toward activation). The earlier zero was old-runner
> entries carrying no gates, **exactly as hypothesized here**. The verdict-withholding was
> vindicated: the 0 was a provenance artifact, not a dead loop
> ([[synthesis/owed-measurements]] item 1b tripwire 1 — RESOLVED).

## 4. EXPECTED — the single ERROR since restart

One ERROR line since restart: **ML-032 retrain request at 37% feature drift**, the day after the
fill-regime change (`8e5455e8`). A regime change in the fill simulator *should* drift the
features; the retrain request is the system responding as designed. No action.

## 5. First honest-fills day measured

First full day on the honest-fills side of the execution-regime boundary
([[comparisons/horizon-96-vs-24-bars]], [[synthesis/risk-posture-doctrine]]):

- **~8 positions/day vs ~16 before** — the predicted sharp drop, and it is **half, not zero**:
  the paper book starves but does not die under the honest fill rate.
- **Exits flowing:** 2 stale-loser purges (including a **100h ETH** position) and `tb_time`
  verticals firing — the exit machinery works on the honest side of the boundary.
- **Cohort 14/50**; post-432 window **0 wins, Wilson [0, 21.5%]** — still unreadable, the
  verdict still refused, the hold continues.
- **Equity $4,930.79** (2026-08-03).
- **`liquiditybot_era_mix_alarm` no longer firing** (was firing unexplained on 08-02 —
  tripwire #4 stands down, cause never named).
- **`fills.csv` 655 rows, zero fixture signatures** (grown from 637 CLEAN — the
  post-quarantine ledger stays clean under live growth).

## 6. Deploy chain fully live and pushed

**head = remote = `d67fd6a5`.** The 2026-08-02 condition "all local-only until the operator
pushes — deploys stall" is resolved; `auto_update` has current code.

---

## What this supersedes
- The 08-02 digest's repo-state warning (seven local-only commits, deploys stalled) — **pushed**.
- The unqualified use of "exact ref-multiple fill" as a fixture signature — split into
  design-vs-fabrication, adjudicated only by the audit chain (finding 2).
- The `liquiditybot_era_mix_alarm` "firing, unexplained" status from 08-02 — no longer firing
  (still never explained; recorded as stood-down, not resolved).

## Related
[[sources/session-20260802-digest]] · [[entities/observability-sidecars]] ·
[[concepts/liveness-by-output-cadence]] · [[entities/long-book]] ·
[[concepts/iron-law-of-debugging]] · [[synthesis/owed-measurements]] ·
[[comparisons/horizon-96-vs-24-bars]] · [[synthesis/risk-posture-doctrine]]
