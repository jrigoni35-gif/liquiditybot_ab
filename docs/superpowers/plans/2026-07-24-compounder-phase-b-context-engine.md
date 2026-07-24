# Compounder Phase B — Context Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the cycle/macro Context Engine (spec §3) — halving phase
clock, structural stress dial, institutional-flow dial, event-calendar
state — as a read-only slow-cadence feed with honest `unknown`
degradation and point-in-time snapshots, TELEMETRY-ONLY in this phase
(no decision path consumes it until Phase C wires the long book).

**Architecture:** One new feed module `data/context_engine.py` mirroring
the `WebDataFeed` pattern (injectable fetch, `maybe_poll(now)`,
availability grace), pure deterministic primitives at module level
(halving clock, calendar rules, fixed-clip dials), a shipped calendar
data file, CX-* codes, a `context` config block with guard coherence, a
`"context"` status section, gc_pusher metrics + a Command-board context
row, plus the offline lessons digest (TA-A1 + FinMem retention tiers)
and the #123 local-ledger contamination fix.

**Tech Stack:** Python stdlib only (urllib via the existing feed
pattern, csv, json, datetime). No new dependencies. pytest fixtures for
ALL parser tests — no network in tests, ever.

## Global Constraints

Binding, copied from the spec (§0, §3) and the evidence doc (both
passes — `docs/research/2026-07-24_compounder_context_evidence.md`):

- **ZERO new 5m model features.** The evidence doc's §0 conclusion and
  the pass-2 DoF ledger both bind: slow context enters as structural
  state for gates and the (future) long book, never the 5m feature
  matrix. `ml/features.py` is NOT touched by this phase. Any diff to
  `ml/` is a spec violation.
- **Telemetry-only phase.** No entry/exit/sizing/gate path may read the
  context state in this phase. The ONLY consumers are status, audit
  logs, and gc_pusher. Report-first, exactly like Phase A's conviction
  formula. Behavior of the trading pipeline stays byte-identical.
- **Honest unknown.** Every source can go dark; a dark source degrades
  its component to `known=False` — a STATE, never a guess, never a
  stale value presented as fresh (grace window = 3× poll cadence,
  mirroring `data/webdata_feed.py:132-133`). Absent sources never
  fabricate values.
- **Phase buckets are labeled CONVENTIONS** (n=3 halvings — no
  statistical claim); the `_doc` must say so verbatim-in-spirit and
  cite the evidence doc. Direction is never signed from calendar or
  cycle inputs.
- **COT joint-read constraint (pass-2 §1.3c, BINDING):** the COT term
  is a crowding/fragility dial documented for joint reading with
  `basis_bps`; never a signed directional input; exactly ONE COT
  series (leveraged-funds net), no more.
- **PIT discipline (pass-2 §2.1):** every successful poll appends the
  as-observed snapshot to `outputs/context_history.jsonl`; any future
  label join or replay reads THAT file, never re-fetches. Test-pinned.
- Free/keyless endpoints only (FRED fredgraph.csv, CFTC dea CSV,
  DefiLlama stablecoins, chain constants, shipped FOMC file). No keys,
  no scraping of keyed/HTML-only sources.
- Registered codes only (new CX-* family, append-only, after the CV
  block in `core/codes.py`); config-lifted thresholds with
  `core/config_guard.py` FATAL coherence checks and `_doc` derivations;
  status schema extended never broken; boards stay at exactly FOUR.
- Full battery green before the final push (pytest · smoke · assurance
  · overfit at its consciously-rebaselined 3-passed/5-failed state, any
  NEW failure = stop + worktree inertness experiment per
  `docs/quant/2026-07-24_of3_pbo_data_shift.md` · ruff · pyright ZERO
  shipped scope · bandit · compileall). `.venv/bin/python` everywhere.
- Commits: `git config user.email noreply@anthropic.com && git config
  user.name Claude`; every message ends with the two trailer lines
  (exact):
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01TgfcWLtZtVMQhbiPZCCV8h`
- Implementers run every command SYNCHRONOUSLY in the foreground —
  never background a test run, never wait on a Monitor.

**Baseline facts (verified in-tree at `82577bb`):**
- Feed pattern to mirror: `data/webdata_feed.py` — `WebDataFeed.__init__
  (config, fetch=_default_fetch)`, `poll_sec` from config,
  `maybe_poll(now) -> Snapshot` early-returns inside cadence,
  availability = got_any or within 3× grace (`webdata_feed.py:55-133`).
- Poll site: `main.py` `slow_cycle` polls feeds via
  `self.webdata.maybe_poll(now)` etc. (main.py, directly after
  `self._maybe_realize_mature_label(now)` — the sentiment/web/risk
  poll cluster).
- Status assembly: `runner.py` `build_status` — `"webdata"` entry is
  the shape model; add `"context"` after it.
- Codes: CV block ends at `CV_CADENCE_LOW = "CV-051"`
  (`core/codes.py:277`); CX block goes after it, before `def tag`.
- Config: `conviction` block sits after `position_sizer`; `context`
  goes directly after `conviction`. Guard: `_conviction_checks` +
  `findings.extend(...)` before `validate()`'s single return — mirror
  with `_context_checks`.
- gc_pusher + board pattern: #120's conviction export/row (commit
  `82577bb`) is the template — synth-status extension in
  `tests/test_trading_dashboard.py` `_SYNTH_STATUS`, absent-safe
  export, native panels only, every queried metric emitted.
- Halving dates (chain history): 2012-11-28, 2016-07-09, 2020-05-11,
  2024-04-20. The NEXT halving is an ESTIMATE (block clock) — it ships
  in config as `next_halving_date: "2028-04-17"` with a `_doc` saying
  estimate, refresh when the epoch approaches.

---

### Task B1: CX code family + deterministic context primitives + calendar file

**Files:**
- Modify: `core/codes.py` (prefix map line + CX block after CV)
- Create: `data/context_engine.py` (module header + pure primitives)
- Create: `data/context_calendar.json`
- Test: `tests/test_context_primitives.py`

**Interfaces (later tasks rely on exact names):**
- `Code.CX_POLL_OK = "CX-000"`, `Code.CX_SOURCE_DARK = "CX-010"`,
  `Code.CX_STATE_CHANGE = "CX-020"` (comment reserves CX-030 for the
  Phase C add-block disposition).
- `data/context_engine.py` module-level:
  - `HALVING_DATES: tuple[str, ...]` (the four ISO dates above)
  - `halving_clock(now_ts: float, next_halving_iso: str) ->
    tuple[int, int]` — (days_since_last, days_to_next), pure UTC-date
    math; days_to_next from the config-supplied estimate.
  - `phase_bucket(days_since: int, buckets: dict) -> str` — buckets is
    `{"accumulation": 180, "expansion": 540, "euphoria": 900,
    "contraction": 1460}` meaning upper-bound-days in that order;
    days beyond the last bound wrap to `"accumulation"`? NO — clamp to
    `"contraction"` (a late cycle stays late until the next halving
    resets days_since; the wrap happens naturally at the halving).
    Order and monotonicity guard-checked in B3.
  - `clip_z(value: float, center: float, scale: float, clip: float) ->
    float` — `max(-clip, min(clip, (value-center)/scale))`, scale<=0
    returns 0.0.
  - `cme_expiry_utc(year: int, month: int) -> float` — timestamp of the
    last Friday of the month at 15:00 UTC (16:00 London BRR is 15:00
    UTC in summer, 16:00 in winter — use a fixed 15:30 UTC midpoint
    with a `_doc` note: the window half-width in config absorbs the
    DST hour; precision to the hour is irrelevant for a pause window).
  - `in_event_window(now_ts: float, event_ts: float, pre_h: float,
    post_h: float) -> bool`.
  - `load_calendar(path: Path) -> dict | None` — parses
    `data/context_calendar.json`; returns None on missing/invalid
    (calendar component then reads unknown).
- `data/context_calendar.json`:

```json
{
  "_doc": "Shipped event calendar (spec §3.4): FOMC decision dates published by the Federal Reserve; refresh yearly. CME expiry needs no table (deterministic last-Friday rule in data/context_engine.py). Halvings live in code constants + config estimate.",
  "fomc": ["2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
           "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09"]
}
```

  (Implementer: VERIFY the 2026 FOMC dates against the Federal
  Reserve's published calendar with one WebFetch/curl of
  federalreserve.gov before committing — if any date differs, use the
  published one and note it in the report.)

- [ ] **Step 1: failing tests** — `tests/test_context_primitives.py`
  covering: CX code values pinned (CX-000/010/020); halving_clock on
  known anchors (e.g. 2026-07-24 → days_since(2024-04-20)=825,
  days_to_next(2028-04-17)=633); phase_bucket boundaries (0→
  accumulation, 180→expansion at the bound [first bucket is
  `< 180`], 540→euphoria, 900→contraction, 2000→contraction clamp);
  clip_z (center/scale/clip math, scale=0 safe); cme_expiry_utc for a
  known month (2026-07 → Friday 2026-07-31) and that it lands on
  weekday 4; in_event_window edges; load_calendar happy/missing/garbage
  (garbage file → None, no raise). Write exact asserts with these
  numbers (verify the two date-arithmetic values with Python before
  pinning them — if your computed value differs, pin YOUR computed
  value and say so in the report).
- [ ] **Step 2: run to fail** — `.venv/bin/python -m pytest
  tests/test_context_primitives.py -q` → import error.
- [ ] **Step 3: implement** — CX block in codes.py (prefix-map line
  `CX  data.context_engine (Compounder Phase B context feed)`), the
  module with a docstring stating the telemetry-only + unknown +
  conventions constraints (cite spec §3 + evidence doc), the calendar
  JSON.
- [ ] **Step 4: run to pass**, plus
  `tests/test_import_integrity.py -q`.
- [ ] **Step 5: commit** `feat: Compounder Phase B — CX codes + context primitives + calendar file`.

---

### Task B2: source parsers + dial math (fixture-driven)

**Files:**
- Modify: `data/context_engine.py` (append parsers + dials)
- Create: `tests/fixtures/context/` (one REAL fetched sample per
  source + malformed variants)
- Test: `tests/test_context_parsers.py`

**Interfaces:**
- `parse_fred_csv(text: str) -> Optional[float]` — LAST numeric
  observation of the single-series `fredgraph.csv?id=X` format
  (`DATE,<ID>` header; "." = missing, skip); None on
  empty/garbage/no-numeric.
- `parse_stablecoin_total(json_text: str) -> Optional[float]` — total
  circulating USD from DefiLlama `GET
  https://stablecoins.llama.fi/stablecoins?includePrices=false`: sum
  over `peggedAssets[].circulating.peggedUSD` (tolerant: skip entries
  missing the key); None on parse failure.
- `parse_cot_btc_lev_net(text: str) -> Optional[float]` — from the
  CFTC Traders-in-Financial-Futures futures-only CSV
  (`https://www.cftc.gov/dea/newcot/FinFutWk.txt`), the row whose
  market name contains "BITCOIN" and exchange "CHICAGO MERCANTILE"
  (take the FIRST such row = standard BTC contract): leveraged-funds
  net = Lev_Money_Positions_Long_All − Lev_Money_Positions_Short_All
  (columns located BY HEADER NAME, never by index; if the file has no
  header row in the dea format, locate by the documented column
  positions ONLY after verifying them against the real fetched
  fixture, and say which you did in the report); None when no BTC row
  or malformed.
- `stress_dial(dff_delta_90d, t10y2y, vix, cfg) -> Optional[float]` —
  mean of three `clip_z` terms with config-lifted anchors (defaults:
  dff_delta center 0.0 scale 0.5; t10y2y center 0.0 scale 0.5 SIGN
  FLIPPED so inversion = stress; vix center 20.0 scale 10.0; clip 2.0
  each); any input None → None (unknown propagates, never partial).
- `flow_dials(cot_net_now, cot_net_prev, stable_now, stable_prev,
  cfg) -> tuple[Optional[float], Optional[float]]` — (cot_delta_z via
  clip_z(cot_now − cot_prev, 0, cfg scale default 5000.0, clip 2.0),
  stable_wk_pct = 100×(now−prev)/prev with prev<=0 → None). Missing
  prev (first poll) → that dial None.
- All numeric anchors are CONVENTIONS in the config block (B3) with
  `_doc`s; the parser layer takes them as arguments, never hardcodes.

- [ ] **Step 1: fetch real fixtures** (network IS available in this
  container; go through the proxy transparently): curl each endpoint
  once, save verbatim under `tests/fixtures/context/` as `fred_dff.csv`,
  `fred_t10y2y.csv`, `fred_vixcls.csv`, `stablecoins.json`,
  `cot_finfut.txt`; also craft `*_malformed` variants (truncated,
  empty, HTML error page). Commit fixtures with the tests. If any
  endpoint is unreachable from this container, STOP and report
  BLOCKED naming the endpoint — do not fabricate a fixture.
- [ ] **Step 2: failing tests** — each parser: real fixture → a
  plausible typed value (assert type/range, e.g. VIX between 5 and
  150, stablecoin total between 5e10 and 5e12, COT net is a finite
  float — do NOT pin exact market values, they change); each
  malformed/empty → None, NO exception; dials: exact-math cases with
  synthetic inputs + None-propagation cases.
- [ ] **Step 3: run to fail. Step 4: implement. Step 5: run to pass**
  (+ ruff on the touched files).
- [ ] **Step 6: commit** `feat: context source parsers + dial math (fixture-driven, keyless)`.

---

### Task B3: ContextFeed class + config block + guard

**Files:**
- Modify: `data/context_engine.py` (append `ContextState`,
  `ContextFeed`)
- Modify: `config.json` (new `context` block after `conviction`)
- Modify: `core/config_guard.py` (`_context_checks` + extend call
  beside `_conviction_checks`'s)
- Test: `tests/test_context_feed.py`, `tests/test_config_guard_context.py`

**Interfaces:**
- `@dataclass ContextState`: `halving_phase: str`, `days_since: int`,
  `days_to_next: int`, `stress: Optional[float]`, `stress_known: bool`,
  `cot_z: Optional[float]`, `stable_wk_pct: Optional[float]`,
  `flow_known: bool`, `in_event_window: bool`, `next_event: str`,
  `calendar_known: bool`, `ts: float`. Plus
  `status() -> dict` on the feed (JSON-safe, includes per-source
  ok/dark map and `last_poll_age_sec`).
- `ContextFeed(config: dict, fetch=_default_fetch)`:
  `maybe_poll(now) -> ContextState` — cadence `poll_hours` (default
  6.0, min 1.0 guard); per-source availability with 3× grace exactly
  like WebDataFeed; halving/calendar components are LOCAL (always
  known when calendar file loads; calendar unknown only if file
  missing/invalid); prev-values for the flow deltas persist across
  polls in-memory AND seed from the last line of
  `outputs/context_history.jsonl` at init (so a restart does not blank
  the weekly deltas — PIT file doubles as warm-start, read-only).
- PIT: each successful poll appends one JSON line
  `{"ts":..., "state": {...}, "raw": {"dff":..., "t10y2y":...,
  "vix":..., "cot_net":..., "stable_total":...}}` to
  `outputs/context_history.jsonl` (append-only, io errors swallowed
  with a log line — telemetry must not wedge the poll).
- Audit: source ok→dark transition logs `tag(Code.CX_SOURCE_DARK,
  "<src> dark ...")`; dark→ok and phase/window changes log
  `CX_STATE_CHANGE`; steady state silent. First successful poll logs
  `CX_POLL_OK` once per process.
- Config block (defaults; ALL `_doc`'d as conventions/estimates):

```json
"context": {
  "_doc": "Compounder Phase B context engine (data/context_engine.py, spec §3; evidence doc 2026-07-24 both passes). TELEMETRY-ONLY this phase: no decision path reads it until Phase C wires the long book. Slow structure = gates/context, never 5m model features (evidence doc §0). Every source degrades to unknown - a state, not a guess.",
  "enabled": true,
  "poll_hours": 6.0,
  "next_halving_date": "2028-04-17",
  "_next_halving_doc": "block-clock ESTIMATE; refresh as the epoch approaches. Past halvings are code constants (chain history).",
  "phase_bucket_days": {"accumulation": 180, "expansion": 540, "euphoria": 900, "contraction": 1460},
  "_phase_doc": "labeled CONVENTIONS over n=3 halvings - descriptive, no statistical claim (evidence doc pass 1 §1); consumers may only tighten on late phases, never boost.",
  "stress": {"dff_center": 0.0, "dff_scale": 0.5, "t10y2y_center": 0.0, "t10y2y_scale": 0.5, "vix_center": 20.0, "vix_scale": 10.0, "clip": 2.0},
  "_stress_doc": "fixed-clip z conventions (equity_risk_z pattern, no fitted weights); STRONG-graded as a risk dial only, never alpha (evidence doc pass 1 §3). 10y-2y is the first term to drop if budget tightens.",
  "flow": {"cot_scale": 5000.0, "stable_scale_pct": 2.0, "clip": 2.0},
  "_flow_doc": "COT leveraged-funds net delta is a CROWDING dial read jointly with basis_bps - post-ETF net-short is carry, not direction (pass 2 §1.3c, BINDING); stablecoin weekly supply delta per Ante et al. FRL 2021. Never signed direction.",
  "event_window": {"fomc_pre_h": 24.0, "fomc_post_h": 6.0, "expiry_pre_h": 8.0, "expiry_post_h": 2.0},
  "_event_doc": "cadence-pause windows only - direction evidence is contradictory (pass 1 §4); consumed by the long book in Phase C, nothing in Phase B.",
  "urls": {
    "fred_dff": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFF",
    "fred_t10y2y": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y",
    "fred_vix": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS",
    "cot_finfut": "https://www.cftc.gov/dea/newcot/FinFutWk.txt",
    "stablecoins": "https://stablecoins.llama.fi/stablecoins?includePrices=false"
  }
}
```

- Guard `_context_checks` (every FATAL contains "context"): poll_hours
  >= 1; phase_bucket_days present with the four keys, values strictly
  increasing; stress/flow scales > 0, clip > 0; event window hours
  >= 0; urls all https. Absent block clean.

- [ ] Steps: failing tests (feed cadence/early-return; per-source dark
  → component unknown + CX-010 on transition only; grace window keeps
  known within 3×; PIT line appended per successful poll + warm-start
  seeds prev-values; status shape + JSON-safe; guard coherence table
  incl. non-monotonic buckets FATAL, http url FATAL, absent clean) →
  fail → implement → pass → `ruff` clean → commit
  `feat: ContextFeed + context config block + guard coherence`.

---

### Task B4: engine/runner integration + status (telemetry-only)

**Files:**
- Modify: `main.py` (init `self.context = ContextFeed(config)` beside
  the other feeds; in `slow_cycle`, poll
  `self._context_state = self.context.maybe_poll(now)` in the
  sentiment/web/risk poll cluster)
- Modify: `runner.py` (`"context": bot.context.status() if
  hasattr(bot, "context") else {},` after the `"webdata"` entry)
- Test: `tests/test_context_integration.py`

**Requirements:** stub-bot integration tests (`LiquidityBot.__new__`
pattern) proving: poll called on cadence from slow_cycle's cluster
(monkeypatched feed records calls); trading pipeline reads NOTHING
from context (grep-style assertion: no reference to `_context_state`
or `self.context` outside the poll line + init in main.py — a source
test in the same spirit as the repo's existing source pins); status
section present + serializable; a dark-everything feed leaves
cycle_once/slow_cycle behavior identical (smoke-level: run the
injected-feed e2e path with context enabled and fetch=lambda *a: None
and assert no new exceptions and no behavioral deltas in placed
orders vs context disabled).
- [ ] failing tests → wire → pass → run
  `tests/ -q -k "e2e or journey or context"` → commit
  `feat: wire context feed into slow-cycle polls + status (telemetry-only)`.

---

### Task B5: lessons digest (TA-A1 + FinMem retention tiers) + #123 ledger fix

**Files:**
- Create: `scripts/lessons_digest.py`
- Test: `tests/test_lessons_digest.py`
- Modify: whatever seam `core/goals.py`'s ledger writer needs for the
  #123 fix (investigate first — smallest change that routes test/smoke
  writes away from `outputs/*_ledger.csv`)
- Test: regression pin that a pytest run does not mutate the repo's
  real ledger CSVs.

**Requirements:**
- Digest: offline, deterministic, stdlib-only; reads
  `outputs/postmortem_summary.csv` + goals ledgers + (if present)
  `outputs/session_digest.json`; emits `outputs/lessons_digest.md`
  with three retention tiers per asset AND per regime: (1) last-N
  postmortems verbatim (N default 10), (2) trailing-quarter aggregate
  (dominant cause, hit rate, net), (3) all-time archive line (counts +
  net). Tier sizes are constants at the top of the script with a
  conventions docstring (reporting layer, not a decision path). NO
  engine imports; missing inputs → section says "no data" (never
  raises). Deterministic templates — same inputs, byte-same output
  (no timestamps beyond the newest input row's own).
- #123: read `core/goals.py` first; implement the smallest honest fix
  (e.g. writer honors an output-dir override that conftest sets to
  tmp_path, or smoke/tests construct goals with a tmp dir). The live
  runner's path behavior must be UNCHANGED. Regression test: snapshot
  `outputs/weekly_ledger.csv` bytes (if file exists) at test start in
  a dedicated test that runs a goals-ledger write via the test seam
  and asserts the repo file is untouched.
- [ ] TDD as usual; run the digest against the repo's real outputs/
  once and include the first 20 lines in the report (sanity, not a
  test); commit
  `feat: lessons digest (retention tiers) + route test ledger writes out of repo outputs (#123)`.

---

### Task B6: gc_pusher context metrics + Command-board context row

**Files:**
- Modify: `scripts/gc_pusher.py`, `scripts/build_trading_dashboard.py`
- Regenerate: `docs/grafana/*.json` (generator only — never hand-edit)
- Test: extend `tests/test_incident_metrics.py` (gc_pusher tests live
  here) + `tests/test_trading_dashboard.py` (`_SYNTH_STATUS` gets a
  `context` section; board pin test)

**Requirements:** mirror #120's conviction pattern exactly (commit
`82577bb` is the template): absent-safe export of
`liquiditybot_context_stress`, `liquiditybot_context_cot_z`,
`liquiditybot_context_stable_wk_pct`, `liquiditybot_context_days_since_halving`,
`liquiditybot_context_days_to_next_halving`,
`liquiditybot_context_event_window` (0/1),
`liquiditybot_context_source_ok{source=...}` (0/1), and a phase
one-hot `liquiditybot_context_phase{phase=...}` (1 on the active
bucket). Command board gets ONE context row (halving phase + days
stats, stress dial gauge [-2..2], flow stats, event-window state
tile, sources-ok bargauge) honoring every glass contract (transparent,
no value_and_name, basic bargauges, native panels only, no hardcoded
lookbacks). Family stays FOUR boards. Import with
`GRAFANA_SA_TOKEN=$(cat ~/.liquiditybot/grafana-sa-token)` env-only,
never argv/echo/commit. TDD; full targeted suites + full pytest before
commit; commit `feat(grafana): context engine row on Command board + exporter metrics`.

---

### Task B7: full battery + push + whole-phase review + merge

Controller-run: full matrix per Global Constraints (overfit judged
against the 3-passed/5-failed conscious baseline; ANY new failure →
stop + the worktree inertness experiment). Push branch; dispatch the
whole-phase review (most capable model) over merge-base..HEAD focusing
on: telemetry-only invariance (the load-bearing claim — nothing in the
decision pipeline reads context), unknown-degradation honesty, PIT
append-only correctness, fixture honesty (real fetched samples, not
fabricated), zero `ml/` diffs, board/exporter contracts. On READY:
fast-forward main.

## Self-review (performed at plan-write time)

- Spec §3 coverage: four inputs ✓ (halving B1, stress B2/B3, flow
  B2/B3, calendar B1/B3); unknown degradation ✓ (B3/B4); research-doc
  adjudications honored ✓ (keyless set, COT constraint, conventions
  docs, zero model features); PIT ✓ (B3 + warm-start); THALES
  candidates correctly NOT in scope (recorded = acceptance).
- No placeholders: parser tasks are fixture-driven with explicit
  contracts and BLOCKED rules instead of fabricated sample data —
  deliberate, stated, and testable.
- Type consistency: ContextState/ContextFeed names match across
  B3/B4/B6; CX codes pinned once in B1 and referenced thereafter.
