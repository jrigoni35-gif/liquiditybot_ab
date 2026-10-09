---
title: "Debugging Deep-Dive (2026-08-05) — 8 Ranked Findings, the 8th QA-Redirect Instance, Stale State Write, Candidate-Pool Saturation (report-only)"
category: source
summary: "Read-only python-expert sweep of the full engine at b824a854: 2 high / 3 medium / 3 low ranked findings with named mechanisms and file:line evidence, 3 near-misses verified OK, HTML/timezone/sim-fill surfaces explicitly clean — adjudicated SAME DAY: 7 of 8 fixed in two battery-green commits (e7ebbf60 + b409a24b), 29d deferred per the 432 hold"
tags: [debugging, audit, report-only, defect-docket, contamination, data-hygiene]
sources: 2
source_path: session transcript 63d8f842 (task-notification, agent a3858b19f9de22ae8)
source_date: 2026-08
ingested: 2026-08-05
updated: 2026-08-05
---

# Debugging Deep-Dive (2026-08-05) — report-only

**Method:** read-only debugging sweep by a dispatched python-expert agent (task
`a3858b19f9de22ae8`, completed 2026-08-05 ~21:35 UTC) over the working checkout
`liquiditybot_ab` at head **`b824a854`** — the deployed head at sweep time. **26 files read**
(runner, main [targeted ~1,100 lines], core/{runtime, audit, fill_ledger, persistence, state,
precision}, risk/capital_manager, execution/{order_manager, risk_firewall}, ml/{labeling,
history}, scripts/{pc_supervisor, auto_update, replay, sweep, replay_gate, train_meta,
smoke_test, gc_pusher, gc_log_pusher, gc_trace_pusher, grafana_import}, api/{rest_server,
grpc_server}, tests/test_qa_isolation, config.json).

**Status as filed: REPORT-ONLY.** No fixes applied; the operator had **not yet been asked**
which fixes to apply. Confidence grades below (**confirmed / probable / possible**) are the
sweep's own, from code inspection — the fix adjudication was owed as
[[synthesis/owed-measurements]] item 29.

**RESOLVED same day** — all decisions made and shipped: **7 of 8 FIXED** in two battery-green
commits (`e7ebbf60` = 29a/29b, `b409a24b` = 29c/29e/29f/29g/29h), **29d DEFERRED** per the
standing 432-migration hold. See the fix-disposition section at the end of this page.

**Filing provenance:** second of the two held 2026-08-05 items the operator approved for filing
(the first was [[sources/telemetry-stack-audit]]).

## Ranked findings

### 1. HIGH · confirmed — replay/sweep/replay_gate QA redirect omits 4 production write paths (the 8th instance of the class)
`scripts/replay.py:64-82` (shared by `scripts/sweep.py` and `scripts/replay_gate.py`).
`run_replay`'s **hand-rolled** redirect covers state/weekly/monthly/history/postmortem/
retrain-flag but NOT:
- **(a) `system.fills_ledger_path`** — config.json sets no such key, so every simulated replay
  fill appends a synthetic row to production `outputs/fills.csv` via `main.py:1663`'s default
  (`append_fill(...fills_ledger_path", "outputs/fills.csv"))`, called unconditionally from
  `_handle_fill`, main.py:1922/1938) — **the exact contamination mechanism behind the
  historical 27x mean-gross error**;
- **(b) `ml.multi_horizon.shadow_path`** — `multi_horizon.enabled: true`, so completed shadow
  horizons append to production `outputs/horizon_shadow.csv` (main.py:789-790), the
  **23,826-row evidence base cited for the in-flight 432-bar migration**;
- **(c) `ml.model_path`** (`outputs/meta_model.json`) — a monitor-flagged retrain during a
  long replay **deploys a replay-trained champion into production**;
- **(d) the `ml/retrain_log` module path** — such a retrain also appends to the real retrain
  history (the file measured 305/306-contaminated on 2026-07-31).

`qa_redirect_paths` (smoke_test.py:101-121) fixes all four for smoke/overfit/debug_cycle;
**sweep.py and replay_gate.py never call it**, and replay.py's own list **predates these
paths**. The sweep reports the gap is **invisible to CI**: for these entrypoints
`tests/test_qa_isolation.py` checks only `configure_audit`/`configure_registry` string
presence. See [[concepts/default-path-fallback-writes]] — the enumeration was refuted again,
this time by an enumeration that never joined the fixed one.

### 2. HIGH · confirmed — train_meta.py unguarded stale read-modify-write of live state.json
`scripts/train_meta.py:73` and `:140-142`. The CLI retrain is documented to run **beside a
LIVE runner** (its own header, lines 36-42): `store.load_raw()` at gate time → minutes of
training → `state_data["monitor"] = ...; store.write_raw(state_data)` — publishing the
**entire minutes-stale snapshot** (positions, open orders, balances, pending labels) as the
primary generation and rotating the runner's newest good snapshot to `.bak`. The **model file
race got a CAS guard** (W2-2, `expect_prior_sha256`) but **state.json got none** — no re-read,
no CAS, no runner-alive check (contrast `scripts/reset_paper_capital.py`, which stops the
runner first). Masked only if the runner survives to its next 30s snapshot; if it dies
uncleanly inside the window (auto_update's `taskkill /F` escalation, auto_update.py:319-326,
or power loss), the restart restores the stale book: **positions closed during training
resurrect as open, fills executed in between vanish from balances** — violating the
"never lose an executed fill" property the snapshot layer was hardened for.

> **Accuracy correction (found during the same-day fix, `e7ebbf60`):** the "minutes of
> training" staleness window above is **wrong** — `load_raw` happens **post-training**, so
> the actual stale window was the **seconds of rescore+gate+save**, not minutes. The
> mechanism and the clobber are real (that window still races the runner's 30s snapshot
> cadence); the magnitude was overstated. The rest of the finding stands as written.

### 3. MEDIUM · probable — week/month close not crash-atomic: double reserve refill
`core/state.py:251-252` (+ main.py:2347-2366, risk/capital_manager.py:107-109).
`maybe_close_week` advances `_last_week_key` and zeroes `weekly_realized_pnl` **in memory
only**; persistence waits for the next 30s-cadence snapshot. A crash/kill in that ≤30s
post-boundary window restores the old week key + old weekly P&L, so the close **replays**:
duplicate `RP_WEEK_CLOSED` audit record, duplicate `weekly_ledger.csv` row, and — after a
losing week — `weekly_rollover` moves `min(reserve, -week_net)` from reserve into cash a
**second time** for the same loss. Book-of-record cash/reserve wrong by up to the week's
loss. Monthly close has the same shape (reporting-only: ledger/audit dupes).

### 4. MEDIUM · probable — 432-bar × 200-slot candidate-pool saturation evicts the newest signal
`ml/history.py:2075-2081` and `:2211-2218`. With `multi_horizon.enabled: true` (horizons
`[108,216,432]`), a DECIDED (early-labeled) candidate is deliberately retained in `_cands`
until the **full** horizon so shadows complete (`if not self.horizons: self._cands.remove(cand)`
— early removal only when no horizons configured). Under the old 24-bar vertical that
retention was ~2h; under 432 bars it is **36h — an 18x retention increase against a fixed
`max_open_candidates: 200`**. Once saturated, `register()` evicts the **NEWEST** pending
candidate (`self._cands.pop()`) before appending — so sustained-signal periods yield roughly
one surviving new candidate per pool-drain event (**ceiling ≈ 200/36h ≈ 5.5/h**), and label
sourcing inverts to exactly the **quiet-hour bias** the pop()-newest choice was built to avoid
(correct when eviction was rare; at 36h retention eviction is the steady state). This is a
**distinct, seemingly unpriced mechanism** from the documented 18x live-label slowdown — it
throttles **candidate** labels, the dataset multiplier. Per the standing hold: **report only,
do not retune the migration** ([[comparisons/horizon-96-vs-24-bars]]).

### 5. MEDIUM · possible — SingleInstanceLock stale-reclaim TOCTOU
`core/runtime.py:266-271`. A crashed runner leaves a stale-readable lock; supervisor relaunch
races an operator `start.bat`. Both read the stale record and take the reclaim path: A unlinks,
O_EXCL-creates, writes its record; B — descheduled between its read and its unlink — then
**unlinks A's FRESH lock**, retries the create, wins O_EXCL, and also returns None. **Both
runners drive the same outputs/** until `refresh()`'s ownership check accumulates
`LOST_LIMIT=3` failures (~15s at the 5s heartbeat): interleaved hash-chain writer seams and
double control-command execution — the historical `audit.jsonl.forked_*` failure mode. The
in-code comments cover the empty-file create-before-write window (lines 253-265) but **not
unlink-after-recreate**; the unlink is unconditional once a stale record was read, with no
re-verification that the file is still the observed stale record.

### 6. LOW · possible — a firewall-rejected exit never escalates: ladder stalls at rung 0
`execution/risk_firewall.py:331-335` (+ main.py:2163-2164). If an asset's mark, book mid, and
fair value are **all** absent/non-finite (total feed poisoning) while the computed exit limit
price is non-finite, `_validate` rejects the exit outright (`FW_INVALID_PRICE ... no valid
reference to substitute`). Back in `_submit_exit`: `if order is None: return  # rejected
orders never escalate` — `_exit_attempts` is **not** incremented, so the position can never
reach the `esc_market_after` MARKET rung **through this path**; the escape stays blocked
exactly as long as the data stays poisoned. Contradicts stated invariant #5 ("exits are
ALWAYS allowed") in the one corner where it matters most — a dark, dislocated feed.
Reachability is low (upstream sanitizers guard most NaN paths), hence *possible* — but it is
a real exit-blocking code path, and no-escalation-on-reject is what turns one bad cycle into
a standing block. Filed in [[comparisons/stated-invariants-vs-audited-reality]].

### 7. LOW · confirmed — events.jsonl rotation permanently drops the unshipped tail from Loki
`scripts/gc_log_pusher.py:120-123` (+ core/runtime.py:146-147). `JsonlLogHandler._maybe_rotate`
renames `events.jsonl` → `events.jsonl.1` at 5MB. The pusher tracks only `cfg["events"]`; on
the next tick the inode differs, so `offset = 0` **on the new file** — every line appended to
the old file after the pusher's previous tick (up to one 10s poll period; **more during a push
outage**, since a failed push never advances the offset) is never shipped and never will be
(the `.1` file is never read). **Loki has a silent gap at every rotation** — an operator
querying "all CRITICAL overnight" can miss records that exist on disk.

### 8. LOW · confirmed — fills.csv has no torn-row recovery
`core/fill_ledger.py:51-64`. `append_fill` is a plain buffered `csv.writer` append — no
flush/fsync, no adoption/truncation logic (contrast `core/audit.py`'s `_adopt_tail`). A
process kill mid-append (the auto-updater's `taskkill /F`, power loss) leaves a partial final
line; the next fill appends onto it, **permanently fusing two rows into one malformed
record**. Downstream csv-parsers (`breakeven_test.py`, `cost_attribution.py`,
`calibrate_fills.py`, `provenance_audit.py`) either drop both fills or mis-bind columns — a
small silent hole in exactly the ledger that was previously the source of a **27x** aggregate
error. Finding 1 aggravates this by adding a second concurrent appender process.

## Near-misses — investigated, verified OK
1. **gc_trace_pusher vs audit torn-tail truncation** (gc_trace_pusher.py:152-153 +
   core/audit.py:101-103). AuditTrail truncates a torn final line at boot, shrinking the file
   — looked like it could trip `stat.st_size < offset` and re-ship the multi-month audit trail
   as duplicate spans. **Safe:** the pusher never advances its offset past a line lacking
   `\n`, so its saved offset equals the truncation point exactly (`<` never fires) and
   subsequent appends only grow the file.
2. **pc_supervisor._spawn log-handle "leak"** (pc_supervisor.py:220-222). The parent opens the
   child's stdout log and never explicitly closes it. **Safe:** the file object's only
   reference is the local `out`; CPython closes it on function return (Popen keeps the fd only
   in the child) — no accumulation.
3. **Sibling instances of the fixed gc_log_pusher duplicate-pair bug** (gc_pusher.py:945-949,
   gc_trace_pusher.py:203-207). **Safe:** both print unconditionally every tick, and worst-case
   tick spacing (60s period + 30s urlopen timeout) stays inside the supervisor's 120s
   staleness window — a quiet market cannot make a live pusher read as dead
   ([[concepts/liveness-by-output-cadence]]).

## Explicit negatives — searched, nothing real found
- **HTML/web surface** — `ui/` contains no code; REST (`rest_server.py`) and gRPC
  (`grpc_server.py`) are disabled by default, loopback-bound, JSON-only with sound CSRF
  posture, no template/interpolation surface; `grafana_import.py` enforces https + the
  token-file pattern.
- **Numeric/timezone** — all P&L datetimes are timezone-aware UTC; day/week/month rollovers
  are UTC-keyed (DST-immune); venue price/volume formatting uses `decimal` with side-aware
  directional rounding. No float-vs-Decimal defect with a demonstrable wrong outcome found.
- **Sim-fill** — `_sim_maker_cross`/`_poll_dry`/queue model internally consistent; no
  oversell, no fee double-book (the historical `=` vs `+=` fee bug is fixed and commented).

## What this sweep changes elsewhere in the wiki
- **Finding 1 is the 8th instance** of [[concepts/default-path-fallback-writes]] — and the
  first found *before* it corrupted a result rather than after.
- **Finding 1(b)** gives the `horizon_shadow.csv` "58.8% proven clean, rest undecidable"
  assessment a **still-open candidate writer** (replay/sweep were never isolated on that
  path); finding 1(c) touches the **unassessed `meta_model.json`** status in owed item 23.
- **Finding 4** is a new, unpriced throughput cost inside the 432-bar hold —
  filed on [[comparisons/horizon-96-vs-24-bars]]; the hold itself is unchanged.
- **Finding 6** joins [[comparisons/stated-invariants-vs-audited-reality]] (invariant #5).
- **Fix adjudication for all 8** was owed as [[synthesis/owed-measurements]] item 29 —
  **discharged same day**, see below.

## Fix disposition (same day, 2026-08-05) — two battery-green commits

All decisions made and shipped; head = remote = **`b409a24b`**. 8 new tests
(`test_period_close_durability`, `test_exit_ladder_reject`, `test_fill_ledger_durability`,
rotation/drain pair in `test_gc_log_pusher`, TOCTOU recheck in `test_single_instance_lock`,
plus the replay-family additions to `test_qa_isolation.py`) — **all written red-first**
against the unfixed code. Battery **3310 passed / 1 skipped**, smoke 219, assurance 49,
ruff + compileall clean.

**Commit `e7ebbf60` — the two HIGHs:**
- **1 / 29a FIXED — the class fix, not a line-item.** `run_replay` now prepares its config
  via new `prepare_replay_config` → the canonical `qa_redirect_paths` (**one list, never
  two**; the hand-rolled replay list is gone), and `sweep.py` gained the
  `configure_audit`/`configure_registry` isolation it **never had** — until this fix a
  sweep run appended replayed dispositions to the **production audit trail and model
  registry**. New replay-family tests walk the real config through the real replay
  preparation and pin all five known-leak keys plus the retrain rebind; the module
  docstring now records **EIGHT** instances. The 8th instance of
  [[concepts/default-path-fallback-writes]] is **CLOSED — the first caught before it
  corrupted a result**.
- **2 / 29b FIXED.** `train_meta.py` `_deploy_challenger` re-reads the **freshest**
  `state.json` at persist time and mutates **only the monitor section**; exposure shrinks
  from the whole gate window to one read-write pair, and the runner's next snapshot
  supersedes even that. Carries the accuracy correction noted inline above: the true
  window was seconds (rescore+gate+save), not minutes.

**Commit `b409a24b` — the five remaining fixables:**
- **3 / 29c FIXED.** The fast_cycle close-out block factored **verbatim** into
  `_close_periods`, which **snapshots the moment a week/month boundary fires** — close +
  rollover land on disk together; the double-reserve-refill replay window is gone;
  mid-period cycles snapshot nothing extra.
- **5 / 29e FIXED.** The stale-reclaim path **re-reads the lock record immediately before
  the unlink and backs off on ANY change** — unlink-after-recreate is closed.
- **6 / 29f FIXED.** Two guards: a rejected exit **counts an escalation attempt** (the
  ladder cannot freeze at rung 0), and a non-finite computed exit price **falls back
  mark → ref → entry**, making `FW_INVALID_PRICE` unreachable for exits. Invariant #5
  restored in the poisoned-feed corner
  ([[comparisons/stated-invariants-vs-audited-reality]]).
- **7 / 29g FIXED.** `tick()` **drains the rotated `events.jsonl.1` tail before the offset
  reset**, provenance-checked via the saved inode (a foreign `.1` is never guessed at);
  the at-least-once contract is unchanged — state advances under the old inode only after
  a successful push.
- **8 / 29h FIXED.** `append_fill` **heals a torn tail** (terminating the fragment so it
  isolates as one junk row csv consumers skip) and **fsyncs each row** — the torn window
  is now the single row being written, not everything since the last OS flush.

**Deferred — 4 / 29d, the docket's only open residue.** Candidate-pool saturation is a
property of the in-flight 432 migration, and the standing order on that experiment is
**hold, do not retune** — it stays a report-only watch item on
[[comparisons/horizon-96-vs-24-bars]]; the fix-vs-accept decision re-opens post-cohort.

## Adversarial re-review the same evening — the round-1 verdict, and two residual edges

An adversarial pass over `e7ebbf60`, `b409a24b` (and `bc198aa5`) ran the same evening —
**hostile eyes on code written hours earlier** ([[sources/session-20260805-evening]],
commit `46cdc19a`).

> **Verdict on round 1: all seven fixes HOLD under adversarial review.**

It nonetheless found **two residual edges on this docket's own fixes**, each **narrower than the
bug it neighbors**, and both fixed in `46cdc19a`:

- **On 29h (`core/fill_ledger.py`) — the ledger could still be born HEADERLESS.** The heal covers
  a **torn final row**; it does not cover the **create-to-first-flush window**. A kill there
  leaves a **0-byte file**, and the next append saw `path.exists() == True`, skipped the header,
  and wrote a **data row first**. `csv.DictReader` then silently **adopts that FILL as the
  header** — and every consumer (`breakeven_test`, `cost_attribution`, `calibrate_fills`,
  `provenance_audit`, `random_entry_control`, `geometry_search`) misparses the **whole ledger**
  with **no error raised**. Same book of record as the **27x** error, a different way to lose it
  ([[concepts/default-path-fallback-writes]]). Fixed: `new_file` counts **size 0 as new**.
- **On 29g (`scripts/gc_log_pusher.py`) — new-generation offsets saved under the OLD inode.**
  `tick()` stat'd the file once, then the new `_drain_rotated` spends **seconds of network time**
  before the main file is opened; a rotation inside that window persisted the offsets against the
  **previous** inode, so the **next** tick's drain seeked `.1` at a **foreign offset and skipped
  its head**. A smaller instance of the very hole 29g closed — and **invisible to 29g's own
  provenance check**, which is the interesting part. Fixed: provenance now comes from
  `os.fstat` on the **opened handle**, not from a prior `stat` of the path.

> **The lesson to carry:** a fix's **neighborhood** is where the next bug lives. Both edges sit
> one window or one handle away from a fix that was itself correct, and neither was reachable by
> re-reading the original finding — only by attacking the new code. Round 2's own five HIGH
> findings ([[sources/session-20260805-evening]]) came from the same sitting.

## Related
[[sources/test-suite-outputs-contamination]] · [[concepts/default-path-fallback-writes]] ·
[[concepts/iron-law-of-debugging]] · [[sources/telemetry-stack-audit]] ·
[[sources/session-20260805-evening]] · [[concepts/adversarial-verification]] ·
[[entities/liquiditybot]] · [[entities/historystore]] · [[entities/observability-sidecars]]
