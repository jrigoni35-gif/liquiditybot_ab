# Decisioning coupling / computing / organization analysis — 2026-09-19

- Scope: `execution/pretrade.py`, `risk/position_sizer.py` (anchors only — agent-17's
  coverage, not re-derived), `risk/profit_tiers.py` (856 ln, read in full),
  `execution/order_manager.py` (1412 ln, read in full), `execution/grid_ladder.py`
  (144 ln, read in full), plus their composition sites in `main.py`.
- Hard constraint honored: **no changes to entry decisioning, sizing, stops, fills,
  fees, universe, hedger, model, or heat cap.** Every recommendation below is
  organizational, computational-hygiene, or coupling-reduction; none moves a
  trading number.
- Method note: reads only + targeted greps. No code was modified.

## 1. Anchor summary (pretrade / sizer — agent-17's ground)

- `PreTradeGate.evaluate` = EV gate: `edge_bps − cost_bps − impact` with a
  Glosten-Milgrom adverse-selection proxy (`as_kappa × sigma_bar_bps`) and a
  maker p-fill EV. Single source of `est_cost_bps`, threaded onto
  `Position.est_cost_bps` at fill — the ONE good coupling in the stack.
- `PositionSizer.size` = heat-fraction sizing with inventory skew, inventory
  aggression, vol scalar, entry cooldown (`note_entry`/`in_cooldown`).
- Both are config-clamped in-module with FATAL mirrors in `core/config_guard.py`.

## 2. `risk/profit_tiers.py` — the exit-policy monolith

**Decisioning inventory** (all live in ONE class): vol-scaled tiers, tier-1
cost-multiple floor, break-even ratchet, chandelier trail, time-tightening,
give-back ratchet (static + vol-scaled arm + arm cost floor), time-stop
(PT-060), signal-decay leash, conviction leash, inventory-coupled close boost,
stop-magnet nudge, phase mutation (`set_phase` euphoria). ~12 exit levers.

**Coupling findings**

1. **Moving-target triggers (C-PT-1).** `_tier_trigger_pct` RECLAMPS every
   cycle from the CURRENT `sigma_bar_pct`. A vol spike after tier 1 fires
   inflates tiers 2–4 retroactively; the time-stop's virgin gate documents
   exactly this hazard for PT-060 but the tiers themselves still fire on a
   moving reference. Recommend: snapshot the effective trigger per tier index
   onto the Position at the moment the previous tier fires (pure bookkeeping;
   trigger semantics unchanged at fire time).
2. **Two cost sources coupled through floors (C-PT-2).** The engine's own
   `est_fee_bps` (venue worst-taker default 40 bps) drives BE/fee math, while
   tier-1/give-back floors read `Position.est_cost_bps` (pretrade's per-entry
   estimate). A config where the two diverge silently splits which floor
   governs which exit. Recommend: one fee-resolution helper that prefers
   `position.est_cost_bps` and falls back to the venue schedule, used by BOTH.
3. **Global mutable phase (C-PT-3).** `set_phase("euphoria")` mutates
   `gb_frac` on the ENGINE instance — all positions in that book share one
   give-back fraction. Per-book instances exist (5m vs long book), so the
   blast radius is bounded, but the coupling is implicit: any future third
   book instance inherits euphoria behavior by construction. Document or
   make the phase an explicit `evaluate()` input.
4. **Live/label sim divergence, one class left (C-PT-4).** The pure-helper
   pattern (`conviction_runner_params`, `time_stop_fires`, …) is excellent —
   the stop-magnet is the one lever the label sim CANNOT mirror (price-space
   vs percent-space), explicitly accepted in-code. Compositing all levers as
   pure functions (see §5) would close even this.
5. **Defensive `getattr` soup (O-PT-1).** Every position read is
   `getattr(position, "x", default)` — the Position interface is implicit and
   unversioned. A `PositionView`/protocol + one startup assertion would make
   schema drift fail loud in dev, tolerant in prod.

## 3. `execution/order_manager.py` — lifecycle + simulator + telemetry in one class

**Responsibilities stacked:** formal state machine (good), live poll path,
dry-run simulator (maker-cross, book sweep, passive hazard, queue model),
fee reconciliation, deadman's switch, firewall passthrough, venue formatting,
execution-quality ledger, terminal funnel telemetry.

**Coupling findings**

1. **Fee truth in three places, recon is report-only (C-OM-1).** OM books at
   config bps; pretrade EV-gates at config bps; the venue reports the actual
   tier. `check_fee_reconciliation` compares all three but only WARNs. The
   drift loop is never closed — deliberate (lifted-threshold discipline), but
   the seam is real. Recommend: keep runtime mutation banned, have recon emit
   a machine-readable `config.json.next` proposal for operator approval.
2. **Dry/live sim-config mirrors live-config (C-OM-2).** `sim_fill` is a
   second config block re-deriving live behavior; era boundary #4 (the
   double-count) exists precisely because the two can drift. The hazard is
   TTL-normalized now, but every future live-path change needs a paired
   sim-path review. Recommend: a single `fill_model.py` that both paths call,
   with the dry path injecting a book/queue oracle.
3. **`submit()` arity (O-OM-1).** 15+ parameters; the caller (`main`) must
   know everything about everything. A `SubmitSpec` dataclass would shrink
   every call site and make defaults explicit. Pure organization — no
   behavior change.
4. **Free-form `meta` conventions (C-OM-3).** `meta["book"]` string tags
   drive `has_open(book=...)` filtering; the convention lives in a comment.
   One `BookTag` literal/Enum removes a whole class of silent misfilter.
5. **Per-order `ttl_sec` as instance-avoidance (O-OM-2).** Added so the
   long-book's patient bids avoid a second OrderManager — a symptom that the
   class serves two lifecycles. Acceptable now; a `LifecycleProfile`
   (timeouts, reprice cadence) beats growing per-order overrides.

## 4. `execution/grid_ladder.py` — cleanest module, smallest surface

Pure planning, deterministic, fail-closed retraction, ARM/DISARM hysteresis.
Findings are minor:

1. **Armed state is in-memory only (C-GL-1).** `_armed` dies on restart; a
   post-restart ladder must re-climb the ARM bar even mid-thesis. Rungs die
   by timeout so no orphaned orders result — but behavior differs across a
   restart. Either persist `_armed` alongside Position state or document the
   re-arm as intended.
2. **Static arm bar (C-GL-2).** `p_win_arm`/`p_win_disarm` are fixed config.
   As the logistic model's calibration drifts with regime, a fixed bar
   silently loosens/tightens. A calibration-derived arm bar (or periodic
   review hook) would keep the ladder's admission semantically constant.
   (This is admission plumbing around the model, not a model change.)
3. **Plan-time spacing snapshot (C-GL-3).** Ladder spacing freezes at plan
   time; a vol regime shift mid-ladder leaves stale rung geometry (bounded —
   rungs expire). Acceptable; note only.

## 5. Cross-cutting: the coupling spine

1. **Sigma authority (X-1, computing).** One vol number drives pretrade
   impact/AS-proxy, tier triggers, chandelier, give-back arm, grid spacing,
   and the sim's passive hazard + queue drain. Units are re-converted at
   every boundary (`pct` ↔ `bps` ↔ `×100`), and each consumer must remember
   the `_measured_sigma` placeholder-guard — `main.py` call sites split
   between raw `vol_state.sigma_bar_pct` (lines ~1540/2614/3125/5001) and the
   guarded `_measured_sigma` (~3239/3262/3380/4493). Verified: `_measured_sigma`
   is a guard over the SAME estimator (returns None while `measured=False` —
   the LINK 3ea2a851 fix), not a second estimator. The defect is that the
   guard lives at CALL SITES instead of in `VolState`: `sigma_bar_pct` should
   be `Optional` and None until measured, so no consumer can accidentally
   consume the 0.05 placeholder. This is the single highest-value
   computational-hygiene change available.
2. **Inventory coupling is implemented twice (X-2).** The sizer's
   `_inventory_skew`/`_inventory_aggression` (risk side) and the tier
   engine's `inventory_coupling` close boost (exit side) both encode
   "crowded book → act" off `inv_ratio` computed inline in `main`. Two
   implementations of one concept can drift. Recommend one
   `inventory_pressure(asset) -> float` authority consumed by both.
3. **Config schema is the real API (X-3).** Every engine clamps its knobs
   AND `core/config_guard.py` FATAL-mirrors the bounds — every knob is
   maintained in two places. The pure-helper pattern (`payoff_ratio_from_config`
   shared by config_guard/scripts) proves the fix: bounds tables as data,
   one owner.
4. **Composition root weight (X-4).** `main.py` constructs all five engines,
   computes `inv_ratio`, `_measured_sigma`, drives the hourly cycle, and
   interprets every `TierAction`/`FillEvent`. The engines are pure-ish; the
   intelligence about WHAT they mean is concentrated in one 5000+ line file.
   A thin orchestration layer (per-book `DecisionPipeline` objects) would make
   the coupling graph inspectable — organizational only.

## 6. Recommendations, ranked (constraint-compliant)

| # | Item | Type | Why first |
|---|------|------|-----------|
| R1 | Move the measured-placeholder guard INTO `VolState` (Optional sigma) | computing | Kills a whole bug class at the spine; tiny diff |
| R2 | Snapshot effective tier triggers onto Position at tier fire | coupling | Stops retroactive trigger movement; bookkeeping only |
| R3 | One fee-resolution helper + recon emits `config.json.next` proposal | coupling | Closes the audible-but-unactionable drift loop |
| R4 | One `inventory_pressure()` authority for sizer + tiers | coupling | Two implementations of one concept |
| R5 | Composit exit levers as pure functions (extend the existing helper pattern) | organization | Closes the last live/label divergence class (magnet) |
| R6 | `SubmitSpec` dataclass + `BookTag` literal | organization | shrinks the widest call surface |
| R7 | Bounds tables as data shared by engines + config_guard | organization | ends double-maintenance |
| R8 | Persist or document grid-ladder armed state; calibration-aware arm bar | coupling | restart semantics + silent admission drift |

## 7. Explicitly NOT recommended (and why)

- **LLMLingua-style prompt compression or any proxy between engines**: wrong
  layer, breaks the one good coupling (`est_cost_bps` threading).
- **Auto-applying fee_recon at runtime**: lifted-threshold discipline exists
  because a venue-read fee must never silently become the gate — R3 proposes
  a proposal, not a mutation.
- **Touching any of the forbidden levers**: every item above leaves all
  trading numbers byte-identical at fire time.

---

## Appendix: verification battery (2026-09-19, worktree ffcd742e)

Full suite (5,533 collected) run in 6 chunks, -n 8/12, all evidence fresh:

| Chunk | Result |
|---|---|
| 0 | 1036 passed, 8 skipped |
| 1 | 968 passed; 2 failed — throttle burst (deterministic, fails on main 3/3) + lock-held (flaky under parallel, green serially) |
| 2 | 769 passed; 1 failed — feed_latency (identical on main). R3 outputs-guard regression found & fixed (conftest ffcd742e) |
| 3 | 883 passed; 21 failed — markout/backfill, 20 fail identically on main (pre-existing, env/tape) |
| 4 | 994 passed, 7 skipped |
| 5 | 826 passed; 3 failed — tool_versions env window (identical on main) |

Net: zero branch-introduced failures remain. ruff: clean on all 8 changed files.
pyright 1.1.414: 0 errors on all changed files.

## Appendix: CS-law audit of config.json / CLAUDE.md / main.py

- main.py: 110 functions. `__init__` 793 ln, `slow_cycle` 647, `_maybe_auto_retrain` 367, `fast_cycle` 290 — SRP/composition-root weight concentrated in 4 functions (~30% of file). Zero TODO/FIXME; 8 module globals. Discipline high; scale is the violation. NOT fixable under era-9 moratorium (main.py owns entry/sizing/exit geometry).
- config.json: 44 top-level keys; 43 referenced in code; `assurance` is a self-documented DEAD KEY (documented-not-deleted per repo precedent). No change needed.
- CLAUDE.md (439 ln) vs AGENTS.md (471 ln): section headers byte-identical; AGENTS.md is the current Kimi mirror (+ RTK block, uncommitted in main tree). No drift.
