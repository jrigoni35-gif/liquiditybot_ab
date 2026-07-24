# Compounder Phase C — Long-Horizon Book Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the long-horizon accumulation book (spec §4–5) as a new
position class inside the existing engines — evidence-laddered sizing
ceilings, context-gated admission through the Conviction Formula's
term 4, patient maker accumulation with TH-013 ladder hygiene,
thesis-invalidation stops, cycle-phase-tightened give-back, book-tagged
labels into the shared corpus, own quant gates — paper from day one.

**Architecture:** ONE new module `risk/long_book.py` (EvidenceLadder
state machine + LongBookEngine decision logic, both pure/injectable),
a `book` tag threaded through Position/persistence/history, second
INSTANCES of the existing ProfitTierEngine + PositionSizer with
long-book config blocks (engines parameterized, never duplicated —
spec §4), one engine call site `_long_book_cycle(now)` in slow_cycle,
LB-* codes + the reserved CX-030 emitter, own quant-gate harness, and
a Command-board row. The 5m book's machinery is UNTOUCHED except the
explicitly named seams.

**Tech Stack:** Python stdlib only. pytest; fixtures/injection — no
network in tests.

## Global Constraints

Binding (spec §0/§4/§5, evidence docs, and the session's law):

- Every §0 invariant: dry_run default; Kraken-only; deny-list;
  **entries limit-only** (long-book adds are post_only maker bids,
  never taker); **exits ALWAYS allowed** (thesis stop, tiers, ratchet,
  disarm-driven flatten all fire regardless of any pause/gate); kill
  switches/faults/watchdog gate long-book ADDS exactly as they gate 5m
  entries (new risk), never exits.
- **Long-only accumulation. No shorts** (spec §5: a future spec must
  earn them). A short/sell-side long-book add is a Critical defect.
- **One growing position per asset per book**: long-book adds AVERAGE
  into the existing long-book position (main.py:1255's averaging path)
  — never a second same-book position on one asset.
- **Combined envelope**: the SHARED PortfolioState/InventoryManager/
  RiskProtocolStack bound both books together (heat, soft/hard USD
  caps, budgets). The long book adds its own ceiling INSIDE that; it
  never gets its own separate risk stack instance.
- **Evidence ladder is the ceiling**: rung 0 = paper only (the book
  trades whenever the system runs; in live mode rung ceilings bound
  it, and rung 1+ additionally requires the ladder's own gates).
  Downgrade on drawdown breach is IMMEDIATE and automatic; upgrades
  are manual-free but gate on realized book-tagged track record.
  Ceilings are config-lifted, guard-checked monotonic and ≤ the heat
  cap.
- **Context before conviction**: a long-book add requires
  `context_aligned=True` through ConvictionFormula term 4
  (CV-040 denial); context UNKNOWN blocks the add with the reserved
  CX-030 (emit it now — its comment in core/codes.py says exactly
  this). Calendar event windows and contraction phase slow/pause add
  CADENCE only (down-only, never boost, never direction).
- **Registered codes only**: new LB-* family (append after CX, before
  `def tag`); every disposition coded; no bare strings.
- **Zero 5m contamination, test-pinned**: `book` tag defaults `"5m"`
  everywhere; history rows carry it; 5m training/label flows are
  byte-identical for book=="5m" rows; `ml/` is touched ONLY in
  ml/history.py for the column threading (any other ml/ diff is a
  violation). G1–G5 stay pinned — the long book gets its OWN harness
  function + OWN test file (quant_trials.py:60-69's T6 warning binds).
- Config-lifted thresholds with `_doc` derivations (defaults below are
  labeled conventions/planning defaults, re-derived from paper
  telemetry before any live rung); config_guard FATAL coherence.
- Full battery green per landing; overfit judged vs the documented
  3-passed/5-failed baseline (any NEW failure → stop + worktree
  inertness experiment); status schema extended never broken; boards
  stay FOUR.
- Commits: `git config user.email noreply@anthropic.com && git config
  user.name Claude`; every message ends with the two exact trailers:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01TgfcWLtZtVMQhbiPZCCV8h`
- Implementers: every command SYNCHRONOUS foreground; never background
  a run; never wait on Monitors. Do NOT push (controller pushes).

**Interface anchors (verified in-tree at 7301a81 by a read-only scout;
implementers trust these, reviewers may spot-check):**

- Position dataclass: core/state.py:14 (fields incl. is_probe,
  confidence, est_cost_bps; `unrealized_pnl_pct` :45). Persistence:
  position_to_dict core/persistence.py:45 / position_from_dict :69
  (follow the est_cost_bps `d.get(...)` pattern at :90).
- Fill open: main._handle_fill main.py:1213 (Position built :1220-1236
  from order.meta; averaging add :1255-1260). Close:
  _finalize_position main.py:1154 (history.log_close :1161, postmortem
  :1179). Exit submit: _submit_exit main.py:1336.
- History schema: ml/history.py:94-96 header = 3 + FEATURE_NAMES + 9
  trailing; _append_row :154 with width guard at :166 — **the literal
  9 becomes 10** when `book` is added; log_entry :144, log_close :215;
  _ensure_schema :121 auto-rotates the CSV on header change (one-time
  .bak — expected, note it in the report when it happens).
- ProfitTierEngine: risk/profit_tiers.py:209, __init__(config dict =
  a profit_taking-shaped block) :210; evaluate(position, current_price,
  sigma_bar_pct=None, signal_alive=None, inventory_pressure=0.0,
  now=None) -> TierAction :668; TierAction :188. Stateless across
  instances except log-dedup sets; per-position state lives ON the
  Position. Shared geometry helpers :79-185 (labeling mirrors them).
- PositionSizer: risk/position_sizer.py:303 size(asset, direction,
  price, p_win, equity, state, macro_state, vol_state, liq_state,
  sent_risk_mult, inventory_mgr, lev_decision, marks, now=None,
  risk_scale=1.0, symbol=None, floor_to_min=False) -> SizeDecision
  (:43, approved property :52). __init__(config, profit_cfg, risk_cfg,
  pretrade_cfg=None, capital_cfg=None, protocols=None) :82.
- InventoryManager: execution/inventory.py:56; can_add(state, asset,
  direction, order_usd, equity, marks) -> AddDecision :90 (same-side
  count cap :96, soft :109, hard headroom :115-122);
  inventory_ratio :81.
- RiskProtocolStack: risk/protocols.py:133; entry_multiplier(
  proposed_frac, equity, sigma_ann_pct, asset_symbol, open_heat_frac,
  now=None) -> (mult, reasons) :224; heat helpers :111.
- OrderManager.submit: execution/order_manager.py:630 (purpose
  "entry"; post_only=True; market refused for non-exit :652; `book`
  PARAM AT :634 IS AN ORDER-BOOK DICT — the strategy-book tag goes in
  `meta`, never that param).
- TH-013 zones: strategies/thales.py `_stop_zones` :508; the
  round-number grid math is INLINE at :543-548 (steps {1,2.5,5,10,25,
  50}·10^k within 0.3–3% of price) + swing extremes :549-552; private
  + state-mutating — C3 extracts the grid math into a pure module
  function (behavior-preserving, _refresh_market_state precedent).
- Conviction seam: risk/conviction.py evaluate :84 (context_aligned
  None=N/A auto-pass, False→CV-040); main._conviction_disposition
  main.py:2175 currently omits context_aligned (:2203-2205) — the
  exact Phase C extension point.
- quant harness: scripts/quant_trials.py run_trials :229, gates built
  :265-277; tests/test_quant_trials.py iterates the returned gates
  list generically → Phase C builds a SEPARATE function + SEPARATE
  test file, never appends to the shared list.
- codes.py: CX block is last before `def tag`; CX-030 reserved
  comment exists. persistence snapshot: new top-level dicts go in
  PersistenceManager.snapshot's data block (pattern :259-261) +
  restore branch (:569-649 region).
- ContextFeed status/state: data/context_engine.py ContextState
  (stress/stress_known, in_event_window, halving_phase, calendar_known
  etc.); main holds `self._context_state` (main.py:2415, telemetry
  var — C4 is the phase that legitimately promotes it to a consumer,
  RETIRING the B4 source-pin test's exclusivity clause consciously:
  update that test to allow exactly the new long-book read sites, and
  say so in the commit).

---

### Task C1: `book` tag + LB code family

**Files:** Modify core/state.py, core/persistence.py, ml/history.py,
main.py (log_entry/log_close threading only), core/codes.py.
Test: tests/test_book_tag.py

**Interfaces produced:** `Position.book: str = "5m"`;
`HistoryStore.log_entry(..., book="5m")` / `_append_row(..., book="5m")`
with header column `book` appended LAST (after candidate_id) and the
width-guard literal 9→10; persistence round-trips book with default
"5m" for old snapshots; codes:

```python
    # ---- long-horizon book (LB) — risk/long_book.py (Compounder C) ----
    LB_ADD_PLACED = "LB-000"         # accumulation add order placed (paper/live)
    LB_ADD_DENIED = "LB-010"         # add refused (detail names the gate:
                                     # conviction/ladder/inventory/sizer/risk)
    LB_ZONE_SHIFT = "LB-020"         # bid shifted off a TH-013 magnet zone
                                     # (ladder hygiene; price only ever moves
                                     # AWAY from the magnet, deeper)
    LB_TIER_BANK = "LB-030"          # long-book tier take (partial bank)
    LB_THESIS_INVALIDATED = "LB-031" # structural stop hit: full close
    LB_RUNG_UP = "LB-040"            # evidence ladder rung upgrade (gated)
    LB_RUNG_DOWN = "LB-041"          # instant downgrade (dd breach)
    LB_PAUSED = "LB-050"             # add cadence paused (event window /
                                     # contraction phase / context unknown -
                                     # CX-030 rides along for the unknown case)
```

Steps: failing tests (book field default + persistence round-trip old
and new snapshots + history header/width/row-threading + LB code value
pins + 5m rows byte-identical when book omitted) → implement →
targeted + `tests/test_history*` + `tests/test_import_integrity.py`
green → note the one-time CSV .bak rotation in the report → commit
`feat: book tag through position/persistence/history + LB code family`.

---

### Task C2: long_book config block + guard + EvidenceLadder

**Files:** Create risk/long_book.py (EvidenceLadder + config dataclass
part). Modify config.json (block after `context`), core/config_guard.py
(_long_book_checks + extend). Test: tests/test_evidence_ladder.py,
tests/test_config_guard_long_book.py.

**Config block (defaults are PLANNING CONVENTIONS, `_doc`'d as such —
re-derived from paper telemetry before any live rung):**

```json
"long_book": {
  "_doc": "Compounder Phase C long-horizon accumulation book (risk/long_book.py, spec §4-5). PAPER-FIRST: rung 0 binds until realized book-tagged track record earns rung 1+. Engines are parameterized instances of the existing tier/sizer machinery - never duplicates. All thresholds below are planning conventions pending paper re-derivation.",
  "enabled": true,
  "assets": ["BTC", "ETH"],
  "_assets_doc": "majors only at start - thin alts are the pump-and-dump surface (evidence doc pass 2 §1.1d); extend consciously.",
  "add_usd_frac_of_ceiling": 0.2,
  "add_min_spacing_hours": 24.0,
  "add_offset_pct": 1.5,
  "_entry_doc": "post_only maker bid add_offset_pct below mark, one growing position per asset (averaging adds), spacing throttles cadence; TH-013 zone hygiene shifts bids AWAY from magnets (LB-020).",
  "thesis_stop_pct": 12.0,
  "_thesis_doc": "structural invalidation full-close (LB-031), NOT a volatility stop; wide by design - the tier/give-back machinery handles profit protection.",
  "context": {"stress_max_for_add": 1.0, "require_known": true,
              "pause_in_event_window": true,
              "contraction_spacing_mult": 2.0},
  "_context_doc": "term-4 alignment: adds need context known + stress dial <= stress_max_for_add; event windows pause adds (LB-050); contraction phase doubles spacing (down-only cadence, never direction; phase buckets are labeled conventions).",
  "ladder": {
    "r1": {"ceiling_frac": 0.10, "min_closed_paper": 10},
    "r2": {"ceiling_frac": 0.20, "min_closed_live": 15, "pf_floor": 1.2},
    "r3": {"ceiling_frac": 0.30, "min_closed_live": 30,
           "adverse_transitions_survived": 1},
    "dd_downgrade_pct": 6.0
  },
  "_ladder_doc": "evidence buys size (spec §5): rung 0 = paper only; r1-r3 ceilings as equity fractions unlocked by realized BOOK-TAGGED closes; breach dd_downgrade_pct on the book's own equity-curve peak -> INSTANT one-rung drop (LB-041; de-risk fast, re-earn slowly). Live arming remains the global config+restart+ARM LIVE road regardless of rung.",
  "profit_taking": {
    "tier_1": {"trigger_pct_gain": 8.0, "close_pct_of_position": 20},
    "tier_2": {"trigger_pct_gain": 15.0, "close_pct_of_position": 20},
    "tier_3": {"trigger_pct_gain": 25.0, "close_pct_of_position": 25},
    "tier_4": {"trigger_pct_gain": 40.0, "close_pct_of_position": 25},
    "vol_scaled": false,
    "trailing_stop": {"enabled": true, "activate_after_tier": 2,
                      "trail_pct": 8.0},
    "give_back": {"enabled": true, "arm_gain_pct": 5.0,
                  "giveback_frac": 0.35,
                  "euphoria_giveback_frac": 0.25},
    "time_stop": {"enabled": false},
    "min_trigger_cost_mult": 3.0
  },
  "_profit_doc": "long-horizon tier geometry (wider, absolute pct - vol_scaled off); euphoria phase tightens give-back to euphoria_giveback_frac (down-only per the disposition-effect inversion, evidence pass 2 §1.1a); PT-060 time-stop OFF by design (patience IS the strategy)."
}
```

**EvidenceLadder** (pure, injectable clock-free):
`EvidenceLadder(cfg)` with `note_close(net_usd, is_live: bool, book_equity_peak_frac_dd: float)`,
`rung() -> int` (0-3), `ceiling_frac() -> float` (rung 0 → 0.0 in LIVE
mode / configured r1 ceiling applies to PAPER sizing so paper behaves
like rung 1 for realism — expose both `paper_ceiling_frac()` and
`live_ceiling_frac()` and let the engine pick by dry_run),
`maybe_downgrade(dd_frac) -> bool` (instant, one rung, LB-041 logged
by caller), counters `closed_paper/closed_live/pf_live`, and
`to_dict()/from_dict()` for persistence. Adverse-transition survival:
incremented by the engine when a risk-off context episode (stress
dial > stress_max sustained per config) starts and ends while the
book held exposure and dd stayed under the downgrade line — engine
computes, ladder stores.

Guard checks (all FATALs contain "long_book"): ladder ceilings
strictly increasing and each ≤ risk_protocols.max_portfolio_heat_frac;
dd_downgrade_pct > 0; thesis_stop_pct > tier_4 trigger is FATAL
(a thesis stop inside the tier run is incoherent — must be beyond);
spacing/offset/fracs positive; assets non-empty subset of configured
symbols; time_stop.enabled must be false (design pin); shorts have no
knob to enable (no direction key exists — document).

Steps: TDD as usual; commit `feat: long_book config + guard + evidence ladder state machine`.

---

### Task C3: pure zone-grid extraction + LongBookEngine decision core

**Files:** Modify strategies/thales.py (extract the :543-548 grid math
into module-level `round_number_grid(mark: float) -> list[float]`,
called by _stop_zones — behavior-identical, _refresh_market_state
precedent; existing TH-013 tests must stay green untouched). Extend
risk/long_book.py with LongBookEngine. Test: tests/test_long_book_engine.py
+ a thales regression run.

**LongBookEngine** (pure decision core, all dependencies injected):
`decide_add(*, now, asset, mark, sigma_bar_pct, context_state,
ladder, position, last_add_ts, dry_run, halted, entries_enabled)
-> AddPlan | DenyReason` — applies, in order: global new-risk gates →
one-position/averaging rule → spacing (phase-scaled) → event-window
pause (LB-050) → context known (CX-030) + stress alignment (feeds
conviction term 4; the actual CV evaluation happens engine-side in C4
where est_edge/cost exist) → ceiling headroom (ladder × equity vs
current book exposure) → bid price = mark×(1−offset), then
`shift_off_magnets(price, grid, tol_pct, buffer_pct)` moving the bid
DEEPER only (LB-020). Exits: `decide_exits` delegates entirely to the
long ProfitTierEngine instance + thesis-stop check (stop_price set at
add-averaging time to avg_entry×(1−thesis_stop_pct)); no engine-side
duplication of tier logic. Every deny returns a typed reason the
caller logs with LB-010 + detail.

Steps: TDD (grid extraction pinned by comparing old/new zone outputs
on synthetic candles; engine decision table incl. long-only assertion,
pause/unknown/misaligned/ceiling/spacing branches, magnet shift
direction) → commit `feat: long-book decision core + pure TH-013 grid extraction`.

---

### Task C4: engine integration (the only main.py task)

**Files:** Modify main.py (init block: long tier engine + long sizer
instances + EvidenceLadder + LongBookEngine; `_long_book_cycle(now)`
called from slow_cycle after the 5m entry loop; exit-path routing:
positions with book=="long" evaluated by the long tier engine and
thesis stop, 5m positions byte-identical; _conviction_disposition
gains `context_aligned: Optional[bool] = None` param passed through
to evaluate — 5m call sites unchanged (None), long-book admission
passes the computed alignment; fill path stamps book="long" from
order.meta into Position + history threading), core/persistence.py
(ladder to_dict/from_dict in snapshot/restore), runner.py
("long_book" status section after "conviction"). Update
tests/test_context_integration.py's source pin CONSCIOUSLY (allow the
enumerated new _context_state read sites; commit message says so).
Test: tests/test_long_book_integration.py (stub-bot pattern).

Contracts: adds submit via orders.submit(purpose="entry",
post_only=True, meta={"book": "long", ...standard entry meta});
sizing via the LONG sizer instance with risk_scale bounded by
ladder ceiling headroom; InventoryManager.can_add consulted (shared);
RiskProtocolStack multiplier applied (shared instance — combined
envelope); denial paths coded; exits always allowed (thesis stop and
tier exits run even when halted/paused — pin with a test);
status: {enabled, rung, ceiling_frac, book_exposure_usd, positions,
adds_placed, last_add_age_h, paused_reason, closed_paper, closed_live,
pf_live, context_aligned_last}.

Steps: TDD; run e2e/journey + conviction + context + long-book suites
+ FULL suite; commit `feat: wire long book into engine (paper-first, combined envelope)`.

---

### Task C5: long-book label flow + own quant gates

**Files:** Verify/extend history threading end-to-end (book="long"
rows land with source="live" on close — mostly done in C1/C4; add the
contamination pin: training loads for the 5m model EXCLUDE book=="long"
rows — read ml/history.py's load path and add the filter AT LOAD with
a test proving 5m X/y identical with and without long rows present;
this is the ONE sanctioned ml/ touch beyond the column). Create
`run_long_trials(paths, bars, seed)` in scripts/quant_trials.py as a
SEPARATE function with its own gates list: G-L1 ladder+thesis-stop
accumulation vs plain periodic-buy baseline dd_p95 not worse ×1.0;
G-L2 ruin == 0; G-L3 terminal capture ≥ 0.9× baseline (patience must
not destroy upside). Consciously baseline at a fixed seed and CI-bind
in NEW tests/test_long_trials.py (fixed-seed determinism + all-gates
pass, generic iteration like the G1-G5 pin). G1–G5 and their test are
NOT touched.

Steps: TDD; run BOTH harness tests + full suite; if a G-L gate fails
at the planning geometry, STOP — report the numbers, do NOT tune the
gate; the controller adjudicates (T6 precedent). Commit
`feat: long-book label isolation + own quant gate set (G-L1..3)`.

---

### Task C6: gc_pusher + Command-board long-book row

Mirror B6/#120 exactly: absent-safe export
(`liquiditybot_longbook_rung/ceiling_frac/exposure_usd/adds_placed/
closed{track}/pf_live/paused` + context_aligned 0/1), ONE long-book
row on the Command board (rung stat with mappings, ceiling gauge,
exposure stat, adds/paused tiles, pf stat), glass contracts, FOUR
boards, `_SYNTH_STATUS` extension first, TDD, full targeted + full
suite, import with env-only token, commit
`feat(grafana): long-book row on Command board + exporter metrics`.

---

### Task C7: full battery + whole-phase review + merge

Controller-run battery (overfit vs the documented conscious baseline;
NEW failure → worktree inertness experiment first). Push; whole-phase
review on the most capable model over the C merge-base..HEAD with the
carried-Minors triage (incl. B's deferred: warm-start staleness bound,
context.history_path config-lift, next_event export — implement in C4
ONLY if the reviewer grades them blocking; else re-ledger); scrutiny
list: long-only invariance, exits-always-allowed under every gate
combination, combined-envelope math, 5m byte-identity (label loads +
entry pipeline), ladder downgrade instantness, source-pin conscious
retirement, §0 sweep. On READY: fast-forward main.

## Self-review (plan-write time)

- Spec §4 coverage: accumulation entry style ✓C3/C4, evidence-ladder
  ceiling ✓C2/C4, long-horizon tiers + euphoria ratchet ✓C2 config +
  tier instance, thesis stop ✓C2/C3/C4, cost-first execution ✓
  (post_only, min_trigger_cost_mult), model-head socket stays dark ✓
  (nothing in this plan trains on long rows — C5 EXCLUDES them from
  the 5m model; activation gate is spec §5's, untouched), composition
  ✓ (shared state/inventory/protocols), THALES both books ✓ (zone
  hygiene C3; detectors stay recorded candidates per §8 acceptance).
- Spec §5: label pipeline ✓C1/C5 (book tag, zero contamination
  test-pinned), ladder numbers config-lifted ✓C2, financial-analyst
  accounting — thesis/expected-path/variance-at-close rides the
  EXISTING postmortem TradeThesis flow which long positions enter
  automatically via _finalize_position (postmortem register happens at
  entry in the 5m path — C4 must register a TradeThesis for long adds
  too; ADDED to C4's contract here: register_entry with the long
  thesis fields at first add, expected path = tier geometry).
- No placeholders: every task carries contracts + exact anchors;
  code-level freedom is bounded by named files/signatures.
- Type consistency: EvidenceLadder/LongBookEngine names consistent
  C2→C4; book default "5m" everywhere; LB codes pinned once in C1.
