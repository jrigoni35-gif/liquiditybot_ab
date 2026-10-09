---
title: Deploy-Gate Worktree Incident (2026-08-04) — Location-Variant Test, Other-Session Integration, Corpus 87→89
category: source
summary: "The PC deploy gate rejected the first externally-pushed commits (4d56d0e0 price anchors, c66fa836 dependency hygiene) twice, deterministically, on test_trajectory_metrics_exist_in_exporter — root cause a collision of two reasonable choices (battery worktree at outputs/_update_wt_<pid> per audit C-F11 × a substring path filter '\"outputs\" not in str(f)') that made the test green in every dev checkout and red exactly where deploys are decided; fixed 242568fb (path-component exclusion relative to ROOT, verified two-sided, 15/15 green in a simulated outputs-nested worktree). Other session's claims verified against live state: price anchors sound, corpus migration NOT yet true on the production box until the idempotent migrator ran (9,358 rows, 87→89 cols, entry_price/exit_price at tail, zero features padded), battery gap closed GREEN on the merged tree (3292/1, smoke 219, assurance 49). Design QA: enumerated codes are the discipline half; the 136 fixture fills carried perfectly VALID codes — enumeration validates form, not origin. Deploy confirmed: runner pid 9212 live on 242568fb, dirty stamp transient (uncommitted-fix window), equity $4,931.69, honest-fills regime continues; price anchors live on every new labeled row (legacy 9,358 rows padded 0 = absent-forever, bookkeeping never a feature). New citation hazard: a location-variant test is invisible until the first external push — single-writer repos never exercise their own gate. Late-day micro-update: tripwire #1 RESOLVED — realized_closed 0→1 on the first organic post-restart close, realized-outcome loop proven end-to-end in production (realized_active correctly False, 1/25); price anchors proven live (27 new rows with real entry/exit prices, corpus 9,385); cohort 15/50, equity $4,932.05"
tags: [session, deploy-gate, incident, tests, integration, provenance]
sources: 1
updated: 2026-08-04
source_path: none — session work product (see Provenance)
source_date: 2026-08
authors: [operator, claude]
ingested: 2026-08-04
---

# Deploy-Gate Worktree Incident (2026-08-04)

## Provenance
Session work product — no `raw/` snapshot. Ground truth: commit `242568fb` (**pushed**;
main local == origin). The incident evidence is the gate's own reject log (two deterministic
rejections of the same commits) and the two-sided reproduction described below.

---

## 1. INCIDENT — root-caused and FIXED (`242568fb`)

The PC deploy gate ([[entities/auto-update]]) rejected the externally-pushed commits
`4d56d0e0` (price anchors) and `c66fa836` (dependency hygiene) **twice, deterministically**, on
`test_trajectory_metrics_exist_in_exporter`.

**Mechanism (named, per the [[concepts/iron-law-of-debugging]]):** a collision of two
individually reasonable choices —

1. `auto_update` builds its battery worktree at **`outputs/_update_wt_<pid>`** — *inside*
   `outputs/`, chosen for audit **C-F11** reclaimability.
2. The HIG test excluded scan files by **substring on the absolute path**
   (`"outputs" not in str(f)`).

In the gate worktree **every path contains `"outputs"`** — the scan saw an empty repo, every
metric read missing. The test was **green in every dev checkout and red exactly where deploys
are decided** — the worst possible polarity: a test defect presenting as a deploy blocker.

**Why it surfaced only now:** this box always commits locally, and the gate battery **never
runs for local-ahead commits** — these were the **first outside-pushed commits since the HIG
tests landed**.

> ⚠️ **Citation hazard (new, filed with [[synthesis/open-contradictions-register]] and
> [[concepts/iron-law-of-debugging]]):** a test that passes everywhere except the deploy
> gate's worktree is **invisible until the first EXTERNAL push** — a single-writer repo
> **never exercises its own gate**. "Battery green" on a dev checkout does not certify the
> gate environment; only a remote-ahead cycle does.

**Fix:** path-**COMPONENT** exclusion relative to ROOT. **Verified two-sided** in a simulated
outputs-nested worktree: the old filter **reproduces the exact gate red**; the fixed filter is
**15/15 green in the same location**.

**Defect class (third instance this week):** substring matching where **identity** was
required — `position_id` grouping ([[synthesis/open-contradictions-register]] #2b), the
round-number error, now paths. Named and filed as
[[concepts/location-invariant-tests]]: *the deploy-gate worktree location is part of the test
contract — any test filtering by path must be location-invariant.*

## 2. Other session's claims — verified against live state

- **Price-anchor commits landed and are sound.** `test_dependency_hygiene` audited clean —
  **explicit directory enumeration, location-invariant by construction** (the positive example
  of the new contract).
- **Corpus-migration claim was NOT yet true on the production box** — the corpus was still
  **87 cols** when checked. It *became* true when the **idempotent migrator** ran post-battery:
  **9,358 rows, 87 → 89 cols, `entry_price`/`exit_price` at the tail, zero features padded**
  ([[entities/historystore]]). Pattern preserved per the vault's retraction rule:
  *claimed → checked false on live state → made true, with the discrepancy recorded.*
- **The other session's disclosed full-battery-pre-rebase-only gap is closed:** its full
  battery ran **pre-rebase only** — the gate rejection was **exactly the disclosed risk
  materializing** — and the gap is now closed: the full battery ran **GREEN on the TRUE merged
  tree** — **3292 passed / 1 skipped, smoke 219, assurance 49, ruff, compileall** — before the
  `242568fb` commit.

## 2b. Corpus price anchors LIVE from this deploy

From `242568fb` onward **every new labeled row carries its `entry_price`/`exit_price`
anchors** ([[entities/historystore]]). The **9,358 legacy rows are padded 0 = absent-forever**
— the pad is a *bookkeeping marker*, and the anchor columns are **bookkeeping, never a
feature** (raw price levels are non-stationary; they exist so future analyses can recompute
per-trade economics, not so a model can fit them).

## 3. Deploy state — confirmed live

Main at **`242568fb`**, local == origin == deployed. Runner **relaunched, pid 9212 live on
`242568fb`** — the earlier "watcher confirmation pending" is resolved. The `auto_update`
**dirty stamp seen during the incident was transient** — exactly the uncommitted-fix window,
not a second defect. The **15-minute reject loop** is ended. Equity **$4,931.69**
(2026-08-04); the honest-fills regime continues.

## 4. Design QA — enumerated codes (operator question)

Filed to [[entities/reason-code-registry]]:

- **Codes are the discipline half** — exact category and lineage, O(1) filtering, drift
  auditable. The `exit_reason`/label **separation** is what made the **25.1% cost wedge**
  findable ([[sources/session-20260802-digest]]).
- **The confidence half** is elsewhere: **continuous companion fields** plus an **independent
  provenance spine** (the hash-chained `audit.jsonl`) to crossref.
- The decisive example: the **136 quarantined fixture fills carried perfectly VALID enumerated
  codes** — **enumeration validates form, not origin; the audit chain convicted them.**

## 5. Housekeeping

- Review worktrees removed.
- `ml.gate_stats.realized_closed` tripwire ~~**still armed**, awaiting organic post-restart
  closes ([[synthesis/owed-measurements]] item 1b, tripwire 1 — status unchanged from
  [[sources/session-20260803-bug-sweep]])~~ — **RESOLVED late the same day, see §6.**

## 6. Late-day micro-update (2026-08-04 late)

**Tripwire #1 RESOLVED — the realized-outcome loop WORKS.** `ml.gate_stats.realized_closed`
moved **0 → 1**: an **organically-entered post-restart position closed and `note_realized`
credited it**, proving the loop (`07d38a51`/`162c595c`) wired **end-to-end in production** —
gates → `order.meta` → position → close → era-keyed ledger. `realized_active` is **correctly
False** (**1/25 toward activation**). The 08-03 watch item ("not yet adjudicable") is now
adjudicated: the loop works; the earlier zero was **old-runner entries carrying no gates,
exactly as hypothesized** ([[sources/session-20260803-bug-sweep]] finding 3,
[[synthesis/owed-measurements]] item 1b).

**Price anchors PROVEN LIVE, not just deployed:** **27 new corpus rows carry real
`entry_price`/`exit_price`** (newest **0.8442 → 0.8636**); the corpus stands at **9,385 rows
and growing anchored** ([[entities/historystore]]) — §2b's "live from this deploy" claim is
now backed by data on disk, not just code inspection.

**Status rollup:** cohort **15/50**; deploy chain current at **`242568fb`**; equity
**$4,932.05**; honest-fills cadence continues (**~5 fill rows since morning**).

---

## What this supersedes
- Nothing retracted. Adds the **location-invariance test contract**
  ([[concepts/location-invariant-tests]]).
- Corrects the *timing* of the other session's corpus-migration claim: not true on the
  production box until the migrator ran on 2026-08-04 (then true, verified).

## Related
[[entities/auto-update]] · [[concepts/location-invariant-tests]] ·
[[concepts/iron-law-of-debugging]] · [[entities/historystore]] ·
[[entities/reason-code-registry]] · [[sources/session-20260803-bug-sweep]] ·
[[sources/session-20260802-digest]] · [[sources/test-suite-outputs-contamination]]
