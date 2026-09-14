# 2026-09-13 — Refactor plan, phase 1 (template conformance)

**Status:** DRAFT synthesized from six package inventories at HEAD `78d88376`
(== origin/main, 2026-09-13). Companion: `CODEBASE_TEMPLATE.md` (same directory).
**Law:** CLAUDE.md hard invariants 1–7; era-9 accrual moratorium (cut #12,
`12-10d4d0c2`). Every item below is classed SAFE or BOUNDARY by that moratorium's own
list — entry decisioning, position sizing, stop/exit geometry, fill simulator, fee
booking, order lifecycle, universe, hedger, probe ticket, heat cap — as the inventory
agent read it. **No SAFE item may change which orders are placed or how they fill.**
**Standard:** `docs/INSTRUMENT_VERIFICATION_STANDARD.md` — read by path. Check 2 (green
tests are not evidence until shown to fail) is UNMET for every pin cited below: no test
body was opened, no mutation was run. Every "pinned by" is an import-grep, not a proof.

**Inputs not received (see §e first):** refuter verdicts (0 rcvd — nothing below is
second-route verified); scripts census; 9 of 13 strategies+regime blocks; main.py,
runner.py, api/, sentiment/ never inventoried.

---

## (a) The module template contract

Every module under core/ data/ execution/ ml/ risk/ strategies/ regime/ conforms to
this once phase 1 lands. Adding the header is SAFE everywhere; the *code* idioms (A3,
A4) are SAFE only for MEASUREMENT/INFRA modules and BOUNDARY for DECISION/MIXED modules
(see §c).

### A1. Header docstring — fixed fields, fixed order

```
"""<one-line purpose>

LAYER: <core|data|execution|ml|risk|strategy|regime|runtime|measurement|infra>
CLASS: <DECISION|MEASUREMENT|INFRA|MIXED>   # per CODEBASE_TEMPLATE.md; MIXED names the split
ON-LIVE-PATH: <yes|no|indirect: <via what>>  # yes = an order/size/stop/fill changes if this file changes
CONFIG: <SECTION <name>|FULL|NONE>            # the SHAPE the constructor receives (main.py:<line>)
  keys: <k1@line, k2@line, ...>               # every key read, with its code default if any
CODES: <CODE-nnn via tag()@line, ...>|none    # only registered core/codes.py members; "none" is a claim
INVARIANTS: <one line each, with @line>
PINNED-BY: <tests/test_x.py, ...>             # files that import this module; NOT proof of coverage
KNOWN-DEAD: <symbol@line (0 callers by needle '<regex>'), ...>|none
"""
```
Rules: no fee tier, no era number, no count, no `main.py:NNNN` line reference inside the
docstring (six modules carry stale ones today: risk/capital_manager:162,
position_sizer:69/106, long_book:605/637/671, ml/history:479/481/2129/2149/2168/2175/2848,
ml/labeling:118/127/184/427/434, ml/overfit:82/624, ml/monitor:817). Cite SYMBOLS.
A volatile number goes as "re-derive from config.json:<key>" (CLAUDE.md working-style 4).

### A2. Logger line
`log = logging.getLogger("liquiditybot.<pkg>.<module>")` — the explicit dotted name six
risk modules already use; NOT `__name__` (risk/protocols.py:56) and not absent
(ml/calibration, risk/conviction, risk/stop_placement). Pure modules may omit it.

### A3. Config-access idiom (one, not three)
- Constructor receives a **SECTION** dict; main.py resolves `config.get("<section>", {})`.
  Verified correct for every engine-constructed module in execution/ (main:760-1283),
  ml/ (main:958-1014), risk/ (main:762-1214). Exceptions today, each a phase-1 item:
  `core/watch_lane` (FULL, runner:302), `core/session_digest` (FULL .get chains
  @527-532), `strategies/liquidity_model` (FULL, main:739), `risk/capital_manager`
  (dual-accept @21), `data/ws_feed` Kraken manager (synthesized 2-key dict main:1309-1313).
- FULL config is legal ONLY for `core/config_guard.validate` and
  `ml/labeling.ExitPolicy.from_config` (both must see cross-section keys).
- Read each key ONCE into a typed attribute with ONE default, at `__init__`. No re-reads
  with a second default (config_guard carries three defaults for
  `pretrade.maker_fee_bps`, two for `capital_management.max_concurrent_positions`, two
  for `ml.label_max_bars`; session_digest 25.0 vs config_guard 15 for `min_ticket_usd`).
- Safe-float coercion is `core.sanitize.safe_float`, imported under its own name.
  `_f` is banned as an alias: it means a dotted-path walker in core/config_guard.py:160
  and `safe_float` in seven modules (session_digest:70, skimmer:49, data/ccxt_feed:33,
  execution/algos:52, execution/routing:33, risk/profit_tiers:72,
  strategies/informed_flow:52) and a *different-default* safe_float in
  strategies/signal_gates.py:18 — the documented root of the M8 defect
  (informed_flow:384-386).

### A4. Code registration + emission (invariant 6)
- Every disposition string that starts `XX-NNN` is a `Code` member in core/codes.py and
  is emitted through `core.codes.tag(Code.X, detail)` (bumps code_stats) or
  `get_audit().log(src, Code.X, ...)`. Bare f-strings of a registered value are a
  defect (11 sites: core/fill_ledger:310,317 OM-085; execution/fair_value:265 FV-020;
  ml/contracts:97,100,105,111,136 ML-010/013; ml/meta_model:98,118,219,232
  ML-011/013/020; ml/registry:247,277,309 ML-060/011).
- Unregistered families are either registered or demoted to plain log text with no
  code-shaped prefix: EX-ALGO-* (execution/algos ×5 + main:1597,1606), SOR-*
  (routing:80,130), FIX-* (fix_codec ×10), CCXT-001..005 (data/ccxt_feed:50,78,89,94,155).
- The prefix map in core/codes.py:16-36 lists every family with a member (EN is missing
  today, @680-689) — pin it with a test that diffs the map against the enum prefixes.
- Audit `src` label = module name (order_manager.py:637 says "execution").

### A5. Public-surface declaration
- `__all__` on every module (risk/stop_placement.py:48 is the model). Names outside
  `__all__` are private; a script importing an underscore name is a defect
  (scripts/candle_store.py:165,238,239; candle_store_resolve.py:67-68,109;
  walkforward_lab.py:64; runner.py:1006 `sizer._open_heat_frac`;
  execution/risk_firewall.py:47 `core.audit._REGISTERED_CODES`).
- Invariant 7: a public name with zero callers is DEPRECATED (docstring + warning), not
  deleted, for one cut; deletion is its own commit with the caller grep in the message.

### A6. No copy-paste helpers
One home per helper (§b B3 lists the concrete moves). Test pin: a needle test that fails
when a second `def <name>(` appears outside the home module (pattern already used by
tests/test_candle_store_safe_class.py and test_ofi_feature.py purity greps).

---

## (b) SAFE batch — phase 1 (concrete, each with evidence + pin)

Ordering: B1 doc-only → B2 dead code → B3 helper lifts → B4 observability → B5 header
sweep → B6 plumbing. Each item lands as its own small commit with the test named. Nothing
here alters an order, a size, a stop, a fill, a fee, or the universe; where a lift touches
a DECISION file, the lift is limited to a byte-identical helper extraction proven by the
harness in §d (H2 mutation pin) BEFORE merge.

### B1. Stale claims in permanent files (docstring/comment only)

| # | file:line | claim | contradicted by | pin |
|---|---|---|---|---|
| B1.1 | core/config_guard.py:13-14 | bottom tier 25/40 | @39-72 derives 40/80 from venue_fees | new: tests/test_docstring_currency.py greps banned literals `25/40`, `40/80`, `1.2%` in module headers |
| B1.2 | core/config_guard.py:1572-1581 | "ZERO in-repo imports at module level" | @35 regime.vol_regime, @69-70 core.venue_fees | same test: AST-count top-level repo imports vs the claim string |
| B1.3 | core/watch_lane.py:70 | "SHIPS DISABLED" | config.json watch_lane.enabled=true, 11 pairs (read 2026-09-13) | reword to "code default False; shipped config enables"; pin: test reads config.json and the docstring together |
| B1.4 | core/watch_lane.py:47-56 | spliced paragraph | editing artifact | none (prose) |
| B1.5 | core/fill_ledger.py:188-191 | fills.csv feeds P&L→sizing | grep: no runtime reader; @9-10 correct | reconcile to @9-10; pin: needle test `fills.csv\|fill_ledger\|fills_path` over main/runner/risk/execution/ml/data/core finds writer only |
| B1.6 | core/codes.py:16-36 | prefix map complete | EN family @680-689 absent | add EN; pin: tests/test_code_registry.py diff map vs enum prefixes (extends existing file, body UNREAD) |
| B1.7 | core/state.py:5-7 | reader "executor" | no such module [I] | fix list |
| B1.8 | data/context_engine.py:4-11,444-448,466-467 | "TELEMETRY ONLY" | main:5350-5368; risk/long_book:619-668 gates 3/4/6; CX-030 codes:584 | rewrite naming long-book consumers; pin: needle `_context_state` in main.py ≥1 hit |
| B1.9 | data/candle_journal.py:18, :980 | "era-5 (8-ca55e2ba)"; "five-way" | law era-9; @74 six-way | fix |
| B1.10 | data/replay.py:14-16 | private methods never called | ws/REST fallback threads may | soften |
| B1.11 | data/venue_adapters — execution/venue_adapters.py:24-27 | creds via core.security | @116-118 os.environ | fix |
| B1.12 | execution/algos.py:35 | "reason-coded EX-ALGO-*" | no EX- family in codes.py | reword or register (B4.3) |
| B1.13 | execution/fair_value.py:13-14; pretrade.py:6-7,80-85; order_manager.py:183-190 | 40/80 cut-#8 premise as current | config.json:347-348,377-378 = 15/30; allow_sub_floor_fees config:370 | replace with "re-derive from config.json:pretrade.*"; B1.1 test |
| B1.14 | execution/hedging.py:83 | "(FW-060)" | latch is FW-070 @110 | fix |
| B1.15 | execution/risk_firewall.py:13-15,480 | recovery "until reset_fault()" | 0 callers → recovery = restart | reword (wiring a command is BOUNDARY-adjacent, §c) |
| B1.16 | ml/history.py:2384-2386 | label_round_trip_cost_pct = 1.2% (cut #8) | config.json 0.45 (read 2026-09-13) | purge figure, pointer to config; B1.1 test |
| B1.17 | ml/history.py:479,481,2848,2129,2149,2168,2175; ml/labeling.py:118,127,184,427,434; ml/overfit.py:82,624; ml/monitor.py:817 | stale `file:line` refs | verified against files read | replace with symbol names; pin: test bans `main\.py:\d+` in docstrings |
| B1.18 | ml/history.py:950-956 | three eras | @272-277,519-540 four+ | fix |
| B1.19 | ml/event_sampler.py:28-32,44-51 | "in-memory only" | to_dict/from_dict @63-88; persistence:536,1005 | fix |
| B1.20 | ml/models.py:443, :15-17, :6-14 | max_depth default 3; torch_model.py; 2 families | @502 max_depth=2; `git ls-files` 0; six families | fix |
| B1.21 | ml/walkforward.py:13-15 | three candidates | _LADDER @46 four + @61 two opt-in | fix |
| B1.22 | ml/labeling.py:117-121 | est_fee_bps 0.0 "matches live CODE default" | risk/profit_tiers:245 `_WORST_TAKER_BPS` | comment fix ONLY (the default itself is §c C-ML3) |
| B1.23 | risk/__init__.py:1-2 | 6 of 9 modules | ls-files 10 | fix |
| B1.24 | risk/capital_manager.py:162; position_sizer.py:5,69,106; long_book.py:605,637,671 | stale refs / 25/40 era text | reads listed in template | B1.17 test |
| B1.25 | risk/profit_tiers.py:78-79, :243-244 | fallback 40.0; "production never reaches this default" | worst_row()[1]=80.0 (venue_fees:64-65,181-183); long book DOES reach it (§c C-R1) | comment fix now; value = §c |
| B1.26 | risk/protocols.py:5-9 | quant_trials vectorizes these functions | scripts/quant_trials.py:47 imports the class only (needle 0 hits) | fix |
| B1.27 | strategies/informed_flow.py — none stale found; data/_http.py header absent | — | — | B5 |

### B2. Dead code (zero callers by the inventory's stated needle; DEPRECATE first, per A5)

| # | symbol | evidence (needle, globs) | action | pin |
|---|---|---|---|---|
| B2.1 | core/runtime.tail_events @261 | `tail_events(` → scripts/smoke_test.py:1378 only | move to scripts/ or delete after smoke_test edit | test_import_integrity unchanged; needle test |
| B2.2 | core/sanitize.cap_text @126 | `cap_text(` → smoke_test:1744 only | delete or wire into data/_http (docstring @127 claims fetch wrappers use it) | needle test |
| B2.3 | core/audit.AuditTrail.verify @300 | `\.verify\(\)` → assurance_check:68,77 | keep (live) — record as thin wrapper | — |
| B2.4 | core/fill_ledger dedup_disarmed/fields_dropped @164,167 | src=[] | export into runner status block (B4.5) rather than delete | test_fill_ledger_durability (body UNREAD) |
| B2.5 | data/kraken_feed.get_open_orders @451 | `get_open_orders` 0 hits repo-wide | deprecate | needle test |
| B2.6 | data/kraken_feed.get_trade_fee_tiers @525 | test-only (test_kraken_fee_schedule:97,176,220) | deprecate note | — |
| B2.7 | data/ws_feed.LiveMarketCache.age @131 | `\.age\(` 0 hits incl. tests | deprecate | — |
| B2.8 | data/ws_feed update_trade @82 / get_mark @778 | test-only | mark reserved | — |
| B2.9 | data/replay.FeedPlayer.calls @100,103 | 0 readers (scripts/replay.py) | expose in load_session `_meta` or drop | test_recording |
| B2.10 | execution/algos.active_parent_for @333 | `\.active_parent_for\(` 0 | deprecate | — |
| B2.11 | execution/markout.worst_asset_markout @190 | test-only (test_markout:83) | surface in snapshot() or delete | test_markout |
| B2.12 | execution/order_manager max_reprices@180 reprice_slip_bps@181 min_fill_ratio@182; ManagedOrder.reprices @128 | assignments + config_guard:2429-2434 only; reprices never increments | delete attrs AND retire the guard checks in the SAME commit; leave config keys + persistence field (schema key load-bearing) | test_order_manager_lifecycle (UNREAD); config_guard tests |
| B2.13 | execution/risk_firewall.reset_fault @159 | 0 callers | keep + B1.15 doc; wiring = §c | — |
| B2.14 | execution/routing.SmartOrderRouter (main:768 construct, never read) | `self\.router\|router\.route\(` → main:768 only; pinned dead by test_hard_invariants:13 | delete construction at main:768 (unread object) — DO NOT wire | test_hard_invariants (UNREAD; may pin construction — read before editing) |
| B2.15 | execution/venue_adapters._TRANSPORTS @44-45 | definition only | delete | test_hard_invariants |
| B2.16 | execution/fair_value FVState.fair_value_raw/innovation_bps @54,61 | 0 readers outside | keep fields (persisted? [UNKNOWN]) — document | — |
| B2.17 | ml/registry.ModelRegistry.history @334 | `\.history(` filtered → none | delete | test_registry_chain |
| B2.18 | ml/meta_model.min_train_rows @45 | assignment only; train_meta reads config key @198 | delete attr | test_model_schema_guard |
| B2.19 | ml/walkforward purged_walk_forward embargo_frac @158-161 | documented no-op | keep (API stability) — header KNOWN-DEAD | — |
| B2.20 | risk/capital_manager.calculate_position_size @65 + max_position_size_pct @34 | def + 3 comments calling it dead (position_sizer:108, config_guard:2163, test_config_guard_informed_flow:9) | deprecate | test_capital_manager |
| B2.21 | risk/leverage LeverageDecision.reasons | never read (main grep 0) | wire into SZ-041 detail (B4.7) | test_leverage_floor |
| B2.22 | strategies/informed_flow clv_min @111 | sole occurrence | delete read | test_signal_literal_lift (UNREAD) |
| B2.23 | strategies/liquidity_model gate_1_config @102 | root-level read of a signal_gates key → always {} ; 0 readers | delete | test_signal_pipeline |
| B2.24 | ml/foundational_confidence, ml/money_sense | 0 production importers by directive | ADD purity pin (B4.9), do not delete | new test |

### B3. Copy-paste helpers → one home (MEASUREMENT/INFRA copies only)

| # | helper | copies (file:line) | home | SAFE scope | pin |
|---|---|---|---|---|---|
| B3.1 | Wilson interval | core/fill_calibration:74, core/performance:24, ml/corpus:233, scripts/cohort_eval:149, label_transfer_filter:73, order_chain_report:103, random_entry_control:60, reason_chain_report:94 | new `core/stats.py` (two-sided; explicit n<=0 semantics) | these 8 only. **NOT** ml/history:75 (ML-077 stat, alias only), ml/monitor:67/79 (one-sided, kill/degrade input — BOUNDARY), strategies/signal_gates:246, strategies/thales:216 (gate/detector — BOUNDARY) | differential test: each retired copy vs home on a fixed (k,n) grid incl. n=0,k=0,k=n; note corpus (0,0) vs history (0,1) at n<=0 — preserve per caller |
| B3.2 | `read_json` | core/runtime:183 (None) vs core/session_digest:155 ({}), core/skimmer:164-166,189-190 inline | core/runtime.read_json | session_digest, skimmer | golden: same file → same dict; missing file → caller's documented sentinel |
| B3.3 | `durable_append` | core/runtime:116 vs core/fill_ledger:267-379 inlined | core/runtime | fill_ledger append_fill (row bytes must be identical) | byte-diff of fills.csv after N appends incl. torn tail + size-0 + width-drop cases (test_fill_ledger_durability, UNREAD) |
| B3.4 | book metrics `_spread_bps/_imbalance` | core/skimmer:76-94 vs core/watch_lane:281-299 | core/skimmer (or core/book.py) | both MEASUREMENT (skimmer disabled) | equality on 20 recorded books |
| B3.5 | `_default_fetch` + `_UA` | data/webdata_feed:33,47-52 vs data/context_engine:396,419-439 | data/_http | preserve timeout tuple per caller | equality of request kwargs via injected session |
| B3.6 | recording stem strip | data/recording:79-82 vs :134-136 | session_id() | — | test_recording |
| B3.7 | moomoo z-score | data/moomoo_feed:309-311 vs :418-426 | `_zscore(hist,value,min_n=8,clip=4)` | append gating stays at call sites | mutation: change clip, both sites move |
| B3.8 | okx candle row map | data/okx_feed:100-108 vs :151-156 | `_rows_to_candles` | — | equality |
| B3.9 | `_asset_of` | execution/inventory:67, hedging:136, main:1610 ([I] body unread) | core (string op) | read main:1610 first; if identical → SAFE | equality on all trading_pairs + hedge symbols |
| B3.10 | `EXECUTION_INVARIANT_VENUE` | execution/routing:37, venue_adapters:41 | one definition | dead path | test_hard_invariants |
| B3.11 | brier | ml/calibration:23 vs ml/interpret:199 | ml/calibration | interpret is report-only | equality |
| B3.12 | `row_era` / `_row_label_era` | ml/corpus:58 vs ml/history:582 | expose from ml/history | corpus read-only | equality on corpus rows |
| B3.13 | `_num` | scripts/gc_pusher:82, glass_console:73, markout_report:186, ml/corpus:189 | ml/corpus or core/stats | scripts | equality |
| B3.14 | fold class-balance predicate | ml/overfit:106,167,721,989,1034; ml/walkforward:294 | `ml/walkforward.viable_folds` | overfit copies SAFE; walkforward:294 is the deployed rule — extract ONLY with H2 identity pin | test_evidence_gate, test_time_purge (UNREAD) |
| B3.15 | `_FAMILIES` | ml/retrain_log:26 vs ml/walkforward._COMPLEXITY:61 | derive from walkforward | adds gbt_mono key | test_model_lineage |
| B3.16 | dd-throttle formula | risk/position_sizer:523-526 vs runner:1009-1013 | `PositionSizer.dd_throttle_mult(dd_pct)` pure method; runner calls it | extraction inside a DECISION file → H2 mutation pin mandatory (plant a different exponent, both readers move) | new test |
| B3.17 | private reach-ins | runner:1006 `_open_heat_frac`; scripts/candle_store*, walkforward_lab; risk_firewall:47 `_REGISTERED_CODES` | public aliases with identical body | — | test_import_integrity |
| B3.18 | cause vocabulary | ml/postmortem:350-372 bare vs ml/monitor:464,471 | shared constants module | string values unchanged | test_governor_and_excursions |
| B3.19 | `_hour_frac`/gmtime ×3 | ml/features:398-400 | locals | inside DECISION file (features) → H1 byte-identical vector pin | new: vector equality on 1000 rows |

### B4. Observability / code registration (no disposition changes)

| # | item | file:line | pin |
|---|---|---|---|
| B4.1 | emit OM-085 via tag(Code.OM_LEDGER_DUP_REFUSED) | core/fill_ledger:310,317 | test_fill_ledger_provenance:233 (references the Code; body UNREAD) + code_stats snapshot shows OM-085 after a planted dup |
| B4.2 | emit FV-020 via tag; emit FV-010 on the no-vote path | execution/fair_value:265, :241-244 | code_stats assertion |
| B4.3 | register or demote EX-ALGO-*, SOR-*, FIX-*, CCXT-*; register ML-010/011/013/020/060 emission via tag | algos, routing, fix_codec, ccxt_feed, ml/contracts, ml/meta_model, ml/registry (lines in A4) | tests/test_code_registry extension: no `"[A-Z]{2,4}-\d{3}` literal outside codes.py that is not `Code.X.value` |
| B4.4 | register codes for bare disposition lines | risk/capital_manager:50,57,198; risk/leverage:53-83; risk/circuit_breaker:53; risk/profit_tiers:813,850,650 (+ TierAction.reason_code populated); data/kraken_feed:250,254 (deny-list fire; grep `Withdraw` in codes.py FIRST — [UNKNOWN] whether a code exists); data/ws_feed:333,667,683; strategies/informed_flow:456,309 | code_stats assertions per event |
| B4.5 | export fill_ledger.dedup_disarmed/fields_dropped and FeedPlayer.calls into status | runner status block | test_rp_status pattern |
| B4.6 | ML-030/031/032/075/076 bare log dups → tag | ml/monitor:344,405,517,559,745,768 | code_stats == audit count |
| B4.7 | append LeverageDecision.reasons to SZ-041 detail | risk/position_sizer:612-615 | audit row contains margin cause |
| B4.8 | log the swallowed exceptions | risk/position_sizer:316,335 (keep return 0.0); risk/protocols:272-273 (keep no-raise) | injection: raise inside loop → warning emitted, value unchanged |
| B4.9 | shadow-purity pins | ml/foundational_confidence, ml/money_sense (mirror test_ofi_feature grep) | new test |
| B4.10 | `_warned_no_book` per-instance | risk/position_sizer:254 | two instances each warn once |
| B4.11 | CircuitBreaker.snapshot() pure | risk/circuit_breaker:69-71,90-92 | same veto on next is_tripped; snapshot does not mutate |
| B4.12 | `assert` → `raise ValueError` | risk/long_book:706; risk/position_sizer:505 | test under `python -O` still refuses |
| B4.13 | alerts: https scheme check + unit test | core/alerts:22,54 (mirror venue_fees:246) | new test_alerts.py: disabled path, rate limit, http:// refused |
| B4.14 | market_maker test pin (none in tests/) | QT-010 floor; bid≤reservation≤ask | new test_market_maker.py |
| B4.15 | okx get_market_data: check order_book None first | data/okx_feed:189-196 (only REST call count changes) | call-count assertion |
| B4.16 | audit src label "execution" → "order_manager" | execution/order_manager:637 — grep scripts/ for `source=="execution"` filters FIRST [UNKNOWN] | — |

### B5. Header sweep (A1/A2/A5) — MEASUREMENT + INFRA modules first
core: __init__, alerts, audit, code_stats, codes, config_guard, runtime, fill_calibration,
fill_ledger, goals, performance, precision, replay_gate, session_digest, watch_lane.
data: all 13 (kraken_feed header only — no code). execution: __init__, fix_codec, routing,
venue_adapters, markout. ml: __init__, corpus, event_sampler, foundational_confidence,
interpret, linkage, money_sense, overfit, retrain_log. risk: __init__.
strategies/regime: __init__ files; the rest UNREAD → header only after their inventory.
Pin: `tests/test_module_headers.py` parses each header's fixed fields and fails on a
missing field, a `main.py:NNN` ref, or a fee/era literal.

### B6. Plumbing (behaviour-preserving, non-decision)
- config_guard: split `validate()` (3,250 lines, pyright skips @534-535) into
  `_<block>_checks` in the SAME order as today's six hoists (@173-769); route the five raw
  `findings.append(('WARN',…))` @3723,3730,3787,3814,3837 through `warn()`; hoist repeated
  `_f(config, KEY, default)` reads to one local per key. Pin: golden test — the full
  finding list (severity, message, order) on the shipped config.json and on each
  test fixture is byte-identical before/after (standard check 1: second route =
  the old function kept in the test as oracle for one cut).
- persistence: registry table of (section, getter, restorer) replacing the two
  hand-mirrored lists @443-670 / @849-1058. Pin: golden snapshot round-trip on a
  recorded state.json — identical JSON keys and values; restore-then-snapshot idempotent.
  (WHAT is restored is BOUNDARY, §c C-CORE3; the table must reproduce today's keys exactly.)
- config_guard: resolve `watchdog.max_equity_drift_pct` reader (needle repo-wide;
  [UNKNOWN] today) — move guard beside consumer or drop phantom key.
- moomoo.options block, risk_protocols.cvar.bar_sec (300), ml.retrain_history_path,
  ml.postmortem.paths_path: write the code default into config.json so the read idiom is
  one section (values identical). Pin: config_guard accepts; module attrs unchanged.
- long_book.thesis_stop_pct: lift caller-side literal 12.0 (main:2082-2083,2184-2185)
  into EngineConfig.from_dict with the identical default. Pin: EngineConfig.thesis_stop_pct
  == 12.0 on shipped config; stop price identical on 3 fixtures.
- ws: `_last_success` initialised in `__init__` (data/webdata_feed:131-133).
- risk_firewall: `_shadow=True` ctor path replacing `__new__` stuffing @493-502.
- ml/interpret: `margin(X)` method on GBT/Logistic instead of `type(model)._node_out`.
- ml/overfit feature_dof_report: define `m` on one path (@1036-1067).
- ml/postmortem: memoise `_excursions` per thesis (@347,406,421).
- ml/__init__: drop eager sub-imports or document the unused re-export.
- config keys unread by any feed (exchanges.okx/binanceus api_key/secret/passphrase/
  read_only/role; context.flow.stable_scale_pct guarded at config_guard:260 but unread):
  document as inert or delete key+guard together.

---

## (c) BOUNDARY items — held for operator adjudication

Every item touches a DECISION/MIXED module's decision half. Listed with the moratorium
axis it hits. None ships in phase 1. Where an item is "identity in intent", it still
needs §d H1 replay determinism before/after AND the adjudication record.

| # | item | file:line | moratorium axis (why cohort-resetting) |
|---|---|---|---|
| C-CORE1 | fault latch/clear/severity order, RECOVERABLE_FAULTS | core/fault:131-134,161-162; persistence:1025-1030 | entry decisioning (allow_new_risk) |
| C-CORE2 | fill_ledger EXEC_ERA / _dup_key / refuse semantics / COLS order | core/fill_ledger:133,145-150,25-26 | era stamp = cohort boundary; dedup key alters cohort_eval's book of record |
| C-CORE3 | persistence: WHAT is restored (orders, positions, probe budget, risk_protocols anchors, paper/live gate) | core/persistence:841-847,903-925,298-309,1053-1057 | the book the next decision runs on |
| C-CORE4 | sanitize clean_book / clean_candles / drop_forming_candles semantics | core/sanitize:136-168,171-197,214-240 | inputs to pretrade, stops, σ, labels |
| C-CORE5 | skimmer weights/thresholds/hysteresis | core/skimmer:55,259-297; runner:95 | universe (disabled today, still the axis) |
| C-CORE6 | PortfolioState accounting (pools, fee legs, equity identity, period closes) | core/state:225-244,190-202,343-353 | sizing, heat, loss budget, hard stop |
| C-CORE7 | venue_fees schedule rows / AoP tiers | core/venue_fees:64-90; profit_tiers:81-82; config_guard:72 | fee re-book adjudication |
| C-CORE8 | watchdog thresholds/semantics | core/watchdog:140-153,205,85-125 | entries_blocked; stop quarantine timing |
| C-DATA1 | ccxt int-seconds candle timestamps | data/ccxt_feed:111 | candle input path (disabled) |
| C-DATA2 | context_engine dial-parameter rename (dff_center→dff_delta_center etc.) | data/context_engine:484-492,527-540 | long-book add gates share the heat cap |
| C-DATA3 | kraken _alias_variants → AssetPairs map | data/kraken_feed:305-324 vs 599-602 | mark resolution for exits (main:2790) |
| C-DATA4 | propagate websockets.stable_connect_sec to Kraken WS manager | main:1309-1313; ws_feed:707-709,738 | data-freshness of the book fast_cycle stops/fills read |
| C-EXEC1 | `_depth_usd` unification (fair_value:121 vs liquidity_regime:94 different bodies) | — | liquidity label → PT-022 + grid retraction (rename alone is SAFE) |
| C-EXEC2 | fee-booking helper (3 maker sites + 1 taker) | order_manager:539-541,1229,1266,1375-1376 | fee booking (SAFE only after H2 proves identical fees_usd at all 4 sites) |
| C-EXEC3 | segment-price helper | order_manager:527-530 vs 1393-1397 | FillEvent.fill_price → entry basis/stops |
| C-EXEC4 | top-of-book shared helper (5 sites, degenerate cases differ) | tactics:90-97; fair_value:209-216; pretrade:170-178; order_manager:1345-1350; routing:91-94 | which entries are refused on malformed books |
| C-EXEC5 | market_maker 16.0/25.0 literals | market_maker:85,101 | quote width (document only in phase 1) |
| C-EXEC6 | implement repricing (if B2.12 chooses implement over delete) | order_manager:180-182 | order lifecycle |
| C-EXEC7 | wire reset_fault to a control command | risk_firewall:159 | re-enables entries after FAULT — runner control change |
| C-EXEC8 | pretrade fee fallback literals (25/40 vs 40/80 vs 40/80) — the VALUES | main:880-881; pretrade:85-86; order_manager:189-190 | EV gate cost / fee booking (routing OM's pair from the PreTradeGate instance is SAFE — B6 candidate — because config always carries the keys; changing any literal is not) |
| C-ML1 | `_RANGES` derived from a shared bounds table | ml/contracts:38-69 vs features:370-467 | which live vectors get the prior → sizing |
| C-ML2 | any clip bound / neutral / order / width in features.py | ml/features | FEATURE_SCHEMA_VERSION bump + model freeze |
| C-ML3 | ExitPolicy.est_fee_bps default 0.0 → `_WORST_TAKER_BPS` | ml/labeling:191; profit_tiers:245 | label geometry default (inert: config has 30) |
| C-ML4 | BarrierOutcome.ret_pct one convention | ml/labeling:70-74; history:2844-2848 | persisted label_ret_pct semantics |
| C-ML5 | split ml/history.py into store / labeler / era modules | ml/history:34-37 | label pipeline import-time effects; invariant 7 |
| C-ML6 | collapse log_close 7-arity tuple ladder | ml/history:1294-1310; persistence restore [I] | old snapshots could turn a close into ML-084 — corpus/snapshot scan first |
| C-ML7 | `_fit_weights` helper in models.fit ×4 | ml/models:94-97,207-209,224-225,655-659,740-744 | champion reproducibility — needs bit-identity on a saved artifact |
| C-ML8 | load_model fail-CLOSED on unknown kind | ml/models:412-430; meta_model:155-191 | which artifacts can become champion |
| C-ML9 | wilson_lcb/ucb merge | ml/monitor:277,289-295 | kill/degrade statistic |
| C-ML10 | lift postmortem literals 10.0/0.5/0.3 to config | ml/postmortem:362-364 → monitor:461-477 → main:1686,4889 | cause→governor→entry bar/stop width (lift with identical default still needs a guard + adjudication) |
| C-ML11 | _LADDER / BRIER_MARGIN / fold predicate / purge | ml/walkforward:46-62,294,350-354 | the deployed selection rule PBO certifies (OF-3 re-baseline) |
| C-ML12 | registry `_record_hash` shared with core/audit | ml/registry:64-70 | any byte change invalidates the live ledger chain → ML-011 fail-closed on every load |
| C-RISK1 | **long_book.profit_taking.est_fee_bps absent → 80.0** (BE floor 166 bps vs 66) | config.json (read 2026-09-13); config_guard:883-887; main:909-910; profit_tiers:245,713 | exit geometry on the long book (enabled=true). Operator decides the value; even pinning 80.0 explicitly is a config change on a decision path. Owed first: audit-trail scan — has the long-book BE floor ever engaged live? [UNKNOWN] |
| C-RISK2 | three Osler lattices/nudges → one | long_book:513-544; profit_tiers:508-544; stop_placement:51-94; thales:64 | stop and bid placement |
| C-RISK3 | leverage vs sizer gross-exposure convention (abs vs signed) | leverage:94-96; position_sizer:305-317 | headroom = sizing; Position.size sign for shorts [UNKNOWN] — measure first |
| C-RISK4 | `_BAR_MINUTES` literal → shared bar-length source | profit_tiers:91,413; protocols:175 | identical value, but `_bars_in_trade` is time-stop input — needs H2 identity pin; listed here because it is exit geometry input |
| C-STRAT1 | anything in informed_flow.evaluate_asset, liquidity_model.build_view merge rules, swing_points.MIN_BARS | strategies/* | entry decisioning; universe (pair map @316-319) |
| C-UNREAD | strategies/signal_gates, smc, thales; regime/* | UNINVENTORIED | cannot be classed; treated as BOUNDARY by default until inventoried |

---

## (d) Behaviour-preservation harness — REQUIRED before any DECISION-module edit

Nothing in §c, and no §b item that touches a DECISION/MIXED file (B3.9, B3.14 walkforward
copy, B3.16, B3.19, B6 persistence table, B6 config_guard split), merges without H1+H2
green on the SAME commit, with the tables in the commit message.

### H1. Replay determinism A/B (standard check 1 — second route)
- Instrument: `main.LiquidityBot.cycle_once(now)` driven by `data/replay.FeedPlayer`
  over recorded sessions (`data/recording.discover_sessions`; parts via
  `session_part_files`), audit via `core.audit.configure_audit(tmp, fsync=False)`,
  registry via `ml.registry.configure_registry(tmp)`, state via a fresh
  `core.persistence.StateStore(tmp)`. Existing pieces: `core/replay_gate.determinism_ok`
  (6 summary keys @36) and `scripts/replay.py` — [UNKNOWN] whether scripts/replay.py
  already exposes a per-record audit diff; read it before building.
- Procedure: (1) checkout BEFORE, replay N recordings → `audit_before.jsonl`,
  `fills_before.csv`, `state_before.json`; (2) checkout AFTER, same recordings, same
  seed (OrderManager seed=42 @171), same `now` stream → the AFTER trio; (3) compare
  **byte-identical** on: every audit record's (src, code, data) with `ts` and `seq`
  stripped, every fills.csv row, final PortfolioState (`core/state` fields), open
  `ManagedOrder` list. The 6-key summary of `determinism_ok` is NOT sufficient — it is a
  summary; the standard's check 5 applies to it.
- Corpus: `recordings` under `system.recording_dir` — count and span [UNKNOWN] here;
  report both. If zero recordings exist the gate SKIPs (replay_gate:128-129) and the
  edit does NOT proceed — a SKIP is not a green.
- Null arm (check 4): run BEFORE vs BEFORE first; a non-empty diff means the harness is
  non-deterministic (wall-clock reads: algos.status():345 `time.time()`,
  inventory.derisk_actions:128 fallback; `_last_success` lazy attr) and must be fixed
  before any A/B is read.
- Placebo (check 4): plant ONE known decision change (e.g. pretrade `min_order_usd`
  +1) and confirm the diff is non-empty and lands where expected; restore byte-identical.

### H2. Mutation-verified pins (standard check 2)
For every pin cited in §b/§c: plant a defect chosen by someone other than the pin's
author, run only that test file, record RED, restore byte-identically (memory
`session-harness-discipline`: `sys.executable` + try/finally restore; a crash left a
mutant on disk 2026-09-07), record GREEN. Table columns: pin file · mutant (file:line,
one-line diff) · expected RED assertion · observed · restore sha. A pin that stays GREEN
under its mutant is not a pin and the item does not ship.
Mandatory mutants already named: B3.16 (exponent), B3.7 (clip), B4.8 (raise inside
loop), B4.12 (`python -O`), C-EXEC2 (fee bps at one site), B6 config_guard (flip one
threshold → finding list differs).

### H3. Provenance in the commit
Commit message carries: HEAD before, recordings used (ids, span), H1 diff = 0 bytes
(or the explained delta), H2 table, and the moratorium class. A claim without the table
is a claim not run (CLAUDE.md working-style 4).

### H4. Zero-findings vs broken-scan
Every needle test added in §b prints its match count on a planted positive (e.g. a
temporary second `def wilson_interval`) in the same PR so "0 hits" is distinguishable
from "regex never matched".

---

## (e) What this inventory could not see

| gap | scope | consequence |
|---|---|---|
| Refuter verdicts | 0 received (inputs absent) | every `[K]` above is single-route; no claim is REFUTED or CONFIRMED; count of refuted claims = [UNKNOWN] |
| Scripts census | not delivered | §7 of the template is reconstructed from cross-references; purpose/writes mostly [UNKNOWN]; scripts not cited by any package are unlisted |
| strategies+regime | 4 of 13 blocks delivered; liquidity_model truncated mid-`duplication_or_dead` (read_status [UNKNOWN]); signal_gates, smc, thales, regime/{__init__,correlation,haven,liquidity_regime,macro_regime,vol_regime} UNREAD | the entry engine's gate layer and every regime engine are unclassified; treated as BOUNDARY by default |
| main.py, runner.py | never inventoried; cited only by windowed reads/grep lines from package agents | config-shape wiring claims rest on those windows; `_asset_of` main:1610 body unread; call-site args for derisk_actions (:3031), record_fill (:2222), ladder.plan (:5910) unread |
| api/, sentiment/ | no inventory | UNREAD |
| tests/*.py bodies | none opened by any agent | "pinned by" = import presence; assertions unverified; standard check 2 unmet everywhere |
| dynamic dispatch | greps are regex; one alias (`_mk` for markout) was caught and corrected; others may hide callers | "dead" = dead-by-needle over stated globs |
| config values | read from the WORKTREE's config.json 2026-09-13 (snapshot); live deploy checkout may differ [I]; websockets enabled/kraken_enabled VALUES not read | every "shipped X=true/false" is as-of that read |
| CANNOT_DETERMINE / [UNKNOWN] items carried | watchdog.max_equity_drift_pct reader; sanitize.is_finite copies; webdata fear_greed_yesterday consumer; CircuitBreaker thread model; Position.size sign for shorts; long-book BE floor ever engaged; scripts/replay.py audit-diff capability; whether a Withdraw code exists in codes.py; audit-source filters on "execution"; config_guard coverage of cvar.bar_sec; whether test_hard_invariants pins router construction | each is a TASK (find the reference), not a fact |
| runtime behaviour | no pytest/smoke/assurance/overfit/mutation run (forbidden this session) | every "invariant enforced" is a static reading; per the standard it is unverified until a planted defect reddens its pin |

---

## (f) Addendum — the one claim re-derived by a second route (2026-09-13 21:45)

Section (e) states that 0 refuter verdicts were delivered, so every `[K]` in
this plan and in `CODEBASE_TEMPLATE.md` is the inventory agent's single read.
That limitation stands for everything except the item below, which I
re-derived myself, in the worktree, four ways. It is recorded here so the
document does not read as uniformly unverified.

**C-R1 / B1.25 — the long book prices its fees at the venue's zero-volume row.
CONFIRMED [K].**

| route | evidence |
|---|---|
| construction | `main.py:910` builds `self.long_tier_engine = ProfitTierEngine(lb_cfg.get("profit_taking", {}))` — the long book's engine sees `long_book.profit_taking` and nothing else |
| config | `long_book.profit_taking` has no `est_fee_bps` key; top-level `profit_taking.est_fee_bps` is 30 |
| code default | `risk/profit_tiers.py:245` falls back to `_WORST_TAKER_BPS`, which is `core.venue_fees.worst_row()[1]` = `KRAKEN_SPOT_SCHEDULE[0][2]` = **80.0**, Kraken's Tier 1 zero-volume taker |
| runtime | instantiating both engines from the live `config.json` prints `est_fee_bps` 30.0 for the 5 m book and **80.0** for the long book |

**Consequence, quantified from the runtime rather than asserted.** Both books
arm the break-even ratchet after tier 1 (`be_after_tier=1`), and both take
`be_buffer_bps` 6.0 by code default. `risk/profit_tiers.py:713` computes the
ratchet as `2·est_fee_bps + be_buffer_bps`:

| book | est_fee_bps | break-even ratchet |
|---|---|---|
| 5 m | 30.0 | 66.0 bps (0.66%) |
| long | 80.0 | **166.0 bps (1.66%)** |

**RETRACTED 2026-09-13 22:55 after a red-team panel.** This paragraph read:
"The second live consumer is `_estimate_realized_pnl` at `:393`, which books
`est_fee_bps` against the closed notional, so every long-book partial close
reports its realized P&L understated by 50 bps of that notional." **Nothing
reports it.** `TierAction.realized_pnl` has exactly TWO attribute reads
repo-wide (`tests/test_profit_tier_guards.py:85`, `tests/test_rev3.py:179`),
both tests; the value is constructed and discarded. `state.realized_pnl_total`
is a different attribute fed from fills, and `est_fee_bps` appears nowhere in
`core/state.py`, `execution/order_manager.py` or the capital layer. The
"CONFIRMED four ways" banner above verified the PREMISE (80.0), never this
consequence — and the clause had already been copied into four other places.

**Direction — CORRECTED 2026-09-13 22:55, and it is NOT fail-conservative.**
The original text here claimed a wider buffer "holds an exit open longer and
never tightens it", echoing the `:77` docstring. **A red-team panel refuted it
and an independent enumeration confirms the refutation.** 960 states (entry
100, long, tier_closed × high_water × price × sigma): **224 install a DIFFERENT
stop**, and stepping the path one tick makes that a different EXIT in **6 of 8**
probes. At price 101.0 with tier 1 closed, the corrected engine arms a
break-even floor at 100.66 and exits on a tick back to 100.65; the shipped
engine, whose floor sits at 101.66, **arms nothing at all** and holds. So the
80 bps figure does not hold a *protected* position longer — it leaves the
position UNPROTECTED through a band the booked tier would have closed at
break-even. "Never tighter" is false as a general statement, and it is false in
SHIPPED COMMENTS at `risk/profit_tiers.py:77` and `:241-242`, not only here.
No invariant-5 issue: give-back, trail and the 12% thesis stop are untouched
and no exit is *gated*; one protective floor fails to arm. Whether this has
engaged in live trading is still the [UNKNOWN] section (e) lists.

**The guard's own claim is false for this path.** `core/config_guard.py:883`
FATALs on an absent `profit_taking.est_fee_bps` and its comment says "this
FATAL means production never reaches ANY default". The list at `:884-888`
holds five dotted paths, all top-level; `long_book.profit_taking.est_fee_bps`
is not among them. Production does reach the default, on the long book.

**Not fixed here, deliberately.** Fee booking and stop/exit geometry are both
named cohort-resetting in CLAUDE.md's era-9 moratorium. Correcting this is an
operator adjudication, and it is now on the HANDOFF docket. Note that the
"obvious" fix of adding `est_fee_bps: 30` under `long_book.profit_taking`
narrows a live stop geometry on a book holding 2 of 5 slots — it is a
BOUNDARY change even though it only restores the account's true fee tier.
