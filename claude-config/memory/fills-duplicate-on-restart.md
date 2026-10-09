---
name: fills-duplicate-on-restart
description: "FIXED (858c8d71; 8th instance e7ebbf60 2026-08-05) - QA harnesses wrote fixture fills into production outputs/. The recurring bug class, its root cause, and the tests that now pin it"
metadata: 
  node_type: memory
  type: project
  originSessionId: 63d8f842-8108-448c-b2d9-fa9a4c8a2da4
  modified: 2026-08-05T22:33:45.874Z
---

**Root cause found and fixed 2026-08-02, commit 858c8d71.** The filename says
"on restart" because that was my first (wrong) theory — kept only so existing
links resolve.

**What actually happened.** `scripts/debug_cycle.py` builds the **real**
`LiquidityBot` from the **real** `config.json` on mocked feeds priced
`ETH=2000.0 / BTC=60000.0`. It redirected the audit trail and ml paths but not
`system.fills_ledger_path`, so every simulated fill appended to the live
`outputs/fills.csv` via `main.py:1652 _ledger_fill`. The "impossible" ETH price
was **fixture data**: `arrival_ref = 2000.000000` is the mock, and the
1490.645739 stop fill is `1491.018493 × (1 − 2.5bps)` — the fill simulator was
correct, its reference price was fake.

**I was wrong for four hours** that this was fills being re-logged on position
restore, and that wrong read drove a diagnosis. What refutes it: identical
intra-block offsets (entry, then exits at +20/+25/+85 seconds) with identical
prices to 10 significant figures and fresh `order_id`s. A restore cannot
reproduce that and would not re-enter. `append_fill` has exactly **one** caller
and nothing in the restore path writes fills. **Lesson: "same data twice" is
not evidence of re-logging; check whether the timing is deterministic.**

**THE BUG CLASS — this was the seventh occurrence**, each found only after it
corrupted a result, each previously "fixed" by adding a line to
`qa_redirect_paths` plus a comment claiming completeness: `state.json` (deleted
three real open positions), postmortem summaries, retrain flags,
`context_history.jsonl` (100+ rows), `audit.jsonl`, `retrain_history.jsonl`
(305 of 306 records were fixtures), `fills.csv` (64 rows → P&L wrong by 27×).

**Why the last two were invisible, and the transferable lesson:** `config.json`
sets **no** `system.fills_ledger_path` and no retrain-history key. The engine
falls back to a hardcoded default that IS the production file, so grepping
config for the key finds nothing. **Absence of a key is not absence of a
write.**

**Now pinned by `tests/test_qa_isolation.py`** (10 cases). The load-bearing one
walks the real config through the real redirect and fails on any `*_path`/
`*_dir` still resolving under `outputs/`. Asserting the *invariant* rather than
the known cases immediately found two more — including a real one: seven of
eight QA entrypoints called `configure_registry()`; `debug_cycle.py` did not,
so it wrote the production model registry too.

**Assessment complete (483f6727, `scripts/provenance_audit.py`).** Two
corrections to the paragraph that used to be here:

- **Attribution:** the writer was the **battery's smoke runs and
  `debug_cycle` alike** — the 16 identical blocks track battery invocations,
  not bot restarts. Any QA entry that builds a bot could leak, pre-fix.
- **The first quarantine was incomplete.** A *variant* fixture scenario
  (tier-2 exits instead of the stop) left 18 more positions / 72 rows,
  including one full stop-pattern block written by a **pre-fix battery run on
  2026-08-02** — one breakeven run away from re-poisoning the stats with a
  fresh −18.39% fake. All quarantined (backup `fills.csv.bak_1785710849`);
  committed stats were provably never contaminated.

**Decisive signal, use this first next time:** a fills `order_id` absent from
the hash-chained `outputs/audit.jsonl` cannot be a live order — QA always
redirected the audit singleton even while leaking fills. `fills.csv` is now
**637/637 audit-verified CLEAN**. Second lesson: **repetition is not evidence;
timing structure is** — `rows=2141 ×6` in retrain_history had ~3603s gaps (the
live hourly cadence; corpus frozen by era exclusion), while the real fixture
group burst at ~548s median. My first heuristic convicted the wrong one.

Remaining honest gaps: `horizon_shadow.csv` is 58.8% proven clean (asset
whitelist), rest UNDECIDABLE — no order_id column to crossref; registry is
97/129 fixture by artifact path, **filter at read time, never rewrite** (hash
chain). `calibrate_fills.py` fed on contaminated fills before the cleanups;
re-run it before trusting fill-sim parameters.

**EIGHTH instance — found AND fixed 2026-08-05 (e7ebbf60), the first caught
BEFORE it corrupted a result.** `scripts/replay.py` kept its own hand-rolled
redirect list predating four canonical paths (fills ledger, horizon shadow,
model_path, retrain history), so every replay/sweep/replay_gate run would have
appended synthetic fills to production — invisible to `test_qa_isolation.py`
because its tests only exercised `qa_redirect_paths`. Also: `sweep.py` NEVER
had audit/registry isolation (sweeps appended replayed dispositions to the
production audit trail + model registry). Fix: the family routes through
`prepare_replay_config` → the ONE canonical list; the invariant tests now walk
the replay entry path too. **Meta-lesson: a second hand-rolled copy of a
safety list is where the class re-grows — fix by routing through the one
chokepoint, never by syncing two lists.**

**Still true regardless:** never group fills by `position_id` — key on the fill
pattern. See [[cost-is-the-binding-constraint]] for what the clean numbers say.

Related: [[432-migration-hold]]
