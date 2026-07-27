# Geometry Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One bet from label to fill — model-lane entries trade the
label's cost-floored bracket, sized on that same bracket's payoff.

**Architecture:** A shared `barrier_geometry()` helper becomes the single
source of truth consumed by BOTH the candidate labeler and the live exit
engine; the sizer gains an optional per-trade bracket; live bracket
closes emit the label's own `tb_*` barrier vocabulary so live rows join
the triple_barrier training era; a report-only comparator proves
labeled-vs-realized agreement.

**Tech Stack:** Python 3.11, stdlib + numpy only (no new deps). Windows
is the target runtime.

**Spec:** `docs/superpowers/specs/2026-07-27-geometry-alignment-design.md`
— read it FIRST; its "Operator decisions" section is binding.

## Global Constraints

- CLAUDE.md hard invariants bind every task: dry_run road-to-live,
  Kraken-only execution, withdrawal deny-list, limit-only entries
  (OM-011; the exit-escalation final rung is the sole market-order
  exception), exits ALWAYS allowed, hash-chained audit + registered
  reason codes only, public interfaces extend-with-defaults.
- `barrier_geometry` floor: `sigma_eff = max(sigma_bar,
  pt_cost_mult * (cost_pct/100) / pt_mult)`; new knob
  `ml.label_pt_cost_mult` ships **4.0**; ratio 8:6 NEVER retuned.
- Sizer bracket path: `b_net_trade = (pt_pct − rt_cost_pct) /
  (sl_pct + rt_cost_pct)`; notional `usd = equity × f ×
  (stop_loss_pct / sl_pct)`; default `bracket=None` is byte-identical
  legacy behavior.
- Config ships `bracket_exits: {"enabled": true}`; guard FATALs
  `bracket_exits.enabled` with `ml.label_mode != "triple_barrier"`.
- Worst-case floored-bracket bar today = 0.614; probe synthetic p 0.64
  must keep ≥0.005 clearance (guard WARN below).
- Every NEW test runs 10+ times before it counts. Mutation-check
  load-bearing branches. NEVER `git checkout --` over uncommitted work
  (scratchpad-copy restore only). Tests that commit files and assert on
  blob bytes pin `* -text` or set autocrlf explicitly (Windows battery).
- Full battery per task-commit: `python -m pytest tests/ -q` ·
  `python scripts/smoke_test.py` · `python scripts/assurance_check.py` ·
  ruff repo scope · pyright shipped scope (0 errors) · bandit ·
  compileall. `scripts/overfit_check.py` baseline 5 passed / 3 failed —
  report movement, never compensate. Task 8 additionally runs
  `scripts/quant_trials.py` (re-baseline at 200×1200 consciously if a
  legitimate change moves G-numbers; never widen a gate).
- Commit per task; do NOT push and do NOT touch main (the controller
  owns push/ff after review).

---

### Task 1: V1 — era-mapping verification + tb realized reasons

**Files:**
- Modify: `ml/history.py` (the `_TRIPLE_BARRIER_BARRIERS` frozenset and
  the `label_era_of` docstring ONLY if the test proves a gap)
- Test: `tests/test_label_eras.py` (extend — file exists)
- Create: `docs/quant/2026-07-27_live_row_era_gap.md`

**Interfaces:**
- Consumes: `ml.history.label_era_of(barrier)`,
  `LABEL_ERA_TRIPLE_BARRIER`, the corpus CSV `outputs/signal_history.csv`.
- Produces: the guarantee later tasks rely on — `label_era_of("tb_pt") ==
  label_era_of("tb_sl") == label_era_of("tb_time") ==
  LABEL_ERA_TRIPLE_BARRIER` for LIVE rows too (the function is source-
  agnostic; verify, don't assume), and a measured count of live rows
  currently excluded by era exclusion.

- [ ] **Step 1: Write the verification tests** (append to
  `tests/test_label_eras.py`, mirroring its existing style):

```python
def test_tb_realized_reasons_join_the_triple_barrier_era():
    # Task 5 will make live bracket closes emit the label's own
    # vocabulary; the era map must already route those rows into
    # tb-era training regardless of row source (live or candidate).
    from ml.history import LABEL_ERA_TRIPLE_BARRIER, label_era_of
    for b in ("tb_pt", "tb_sl", "tb_time"):
        assert label_era_of(b) == LABEL_ERA_TRIPLE_BARRIER


def test_tier_policy_realized_reasons_stay_out_of_the_tb_era():
    # the V1 hole, pinned: today's tier-exit live rows are OLD-era by
    # definition of the era map — this is the exclusion Task 5 closes
    # by changing what live closes EMIT, never by bending the map.
    from ml.history import LABEL_ERA_TRIPLE_BARRIER, label_era_of
    for b in ("tier", "trail", "floor", "realized", "time_stop"):
        assert label_era_of(b) != LABEL_ERA_TRIPLE_BARRIER
```

- [ ] **Step 2: Run them** — `pytest tests/test_label_eras.py -q`.
  Expected: both PASS immediately (the map already routes by barrier
  string). If the first FAILS, the map has a real gap: fix
  `_TRIPLE_BARRIER_BARRIERS`/`label_era_of` minimally and note it in
  the report; do not touch any other era.
- [ ] **Step 3: Quantify the live-row gap** (one-off, run and record —
  do not commit the script):

```bash
.venv/bin/python - <<'EOF'
import csv
from ml.history import LABEL_ERA_TRIPLE_BARRIER, label_era_of
rows = list(csv.DictReader(open("outputs/signal_history.csv",
                                encoding="utf-8")))
live = [r for r in rows if r.get("source") == "live"]
excl = [r for r in live
        if label_era_of(r.get("barrier") or "") != LABEL_ERA_TRIPLE_BARRIER]
print(f"live rows: {len(live)}; excluded from tb-era training: {len(excl)}")
from collections import Counter
print(Counter((r.get('barrier') or 'blank') for r in excl).most_common(8))
EOF
```

- [ ] **Step 4: Write `docs/quant/2026-07-27_live_row_era_gap.md`** —
  the measured counts, the mechanism (realized tier-policy reasons →
  exit_sim era → excluded while era exclusion is active), and the
  closure route (Task 5 emits `tb_*` from bracket closes). Cite spec §D6.
- [ ] **Step 5: Run the tests 10×, then commit**
  `docs + tests: V1 era-mapping verification (geometry alignment T1)`.

---

### Task 2: `barrier_geometry()` — one source of truth, cost-floored

**Files:**
- Modify: `ml/labeling.py` (new function, top-level, after the
  dataclasses), `ml/history.py` (CandidateLabeler `_label` call site
  ~:1714 and shadow-horizon site ~:1746 — anchor by content), and
  `config.json` (`ml.label_pt_cost_mult`), `core/config_guard.py`.
- Test: `tests/test_barrier_geometry.py` (create).

**Interfaces:**
- Produces: `barrier_geometry(sigma_bar: float, cost_pct: float,
  pt_mult: float, sl_mult: float, pt_cost_mult: float) ->
  tuple[float, float]` returning `(pt_frac, sl_frac)` — FRACTIONS of
  entry price. Pure, no config reads inside (callers pass their knobs).
- Consumed by: Task 5's engine bracket computation and the labeler
  (this task wires the labeler).

- [ ] **Step 1: Write the failing tests** (`tests/test_barrier_geometry.py`):

```python
"""The label's barriers, cost-floored (spec D2): sigma_eff floors the
SIGMA INPUT so pt and sl scale together and the 8:6 ratio is preserved
by construction — a single knob, no per-barrier distortion."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.labeling import barrier_geometry  # noqa: E402


def test_high_vol_is_pure_sigma_scaling():
    # sigma above the floor: identical to legacy 8σ/6σ
    pt, sl = barrier_geometry(0.005, 0.5, 8.0, 6.0, 4.0)
    assert abs(pt - 0.04) < 1e-12 and abs(sl - 0.03) < 1e-12


def test_low_vol_hits_the_cost_floor_ratio_preserved():
    # floor: sigma_eff = 4.0 * 0.005 / 8 = 0.0025 -> pt 2%, sl 1.5%
    pt, sl = barrier_geometry(0.0005, 0.5, 8.0, 6.0, 4.0)
    assert abs(pt - 0.02) < 1e-12 and abs(sl - 0.015) < 1e-12
    assert abs(pt / sl - 8.0 / 6.0) < 1e-9


def test_floor_boundary_is_continuous():
    boundary = 4.0 * (0.5 / 100.0) / 8.0
    lo = barrier_geometry(boundary * 0.999, 0.5, 8.0, 6.0, 4.0)
    hi = barrier_geometry(boundary * 1.001, 0.5, 8.0, 6.0, 4.0)
    assert abs(lo[0] - hi[0]) < 1e-4


def test_zero_cost_mult_disables_the_floor():
    pt, sl = barrier_geometry(0.0005, 0.5, 8.0, 6.0, 0.0)
    assert abs(pt - 0.004) < 1e-12          # bare 8σ, legacy
```

- [ ] **Step 2: Run — expect ImportError.**
- [ ] **Step 3: Implement in `ml/labeling.py`:**

```python
def barrier_geometry(sigma_bar: float, cost_pct: float, pt_mult: float,
                     sl_mult: float, pt_cost_mult: float) -> tuple:
    """(pt_frac, sl_frac) for the triple-barrier bet, cost-floored.

    WHY the floor (spec D2, 2026-07-27): sigma-scaled barriers at
    typical 5m vol put the profit target ~1% out while the round-trip
    cost is ~0.5% — costs eat half the profit distance and the AVERAGE
    bracket bet is EV-negative regardless of signal. Flooring the SIGMA
    INPUT (never the distances) keeps pt:sl at its configured ratio by
    construction: sigma_eff = max(sigma_bar,
    pt_cost_mult * cost_frac / pt_mult), so at the floor the profit
    distance is exactly pt_cost_mult round-trip costs. pt_cost_mult=0
    disables the floor (legacy behavior). Pure function — BOTH the
    candidate labeler and the live bracket-exit engine call this, which
    is what makes the label's bet and the traded bet the same bet."""
    sigma_eff = sigma_bar
    if pt_cost_mult > 0.0 and pt_mult > 0.0:
        sigma_eff = max(sigma_bar, pt_cost_mult * (cost_pct / 100.0)
                        / pt_mult)
    return pt_mult * sigma_eff, sl_mult * sigma_eff
```

- [ ] **Step 4: Wire the labeler** (`ml/history.py`): in
  `CandidateLabeler.__init__` (anchor: `self.pt = float(cfg.get(`) add
  `self.pt_cost_mult = float(cfg.get("label_pt_cost_mult", 0.0))`
  (code default 0.0 = legacy; config.json ships 4.0). At BOTH
  `triple_barrier(` call sites, compute the floored sigma via the
  helper and pass it through — the labeler function signature does not
  change; replace the raw `sigma_bar`/`cand["sigma_bar"]` argument:

```python
from ml.labeling import barrier_geometry
pt_frac, _sl_frac = barrier_geometry(sigma_bar, cost, self.pt, self.sl,
                                     self.pt_cost_mult)
sigma_eff = pt_frac / self.pt if self.pt > 0 else sigma_bar
out = triple_barrier(closes, highs, lows, i, side, sigma_eff,
                     self.pt, self.sl, self.horizon, cost_pct=cost)
```

  (The exit_policy branch is untouched.) Add config.json key
  `"label_pt_cost_mult": 4.0` beside `label_sl_vol_mult` with a `_doc`
  citing spec D2 and the floor derivation.
- [ ] **Step 5: Guard** (`core/config_guard.py`, near the existing
  label-mode checks): FATAL `ml.label_pt_cost_mult` outside [0, 20];
  WARN in (0, 2) ("costs above 50% of the profit distance — the bet the
  floor exists to prevent"). Guard tests go in
  `tests/test_config_guard_min_pwin.py`'s file or a sibling — follow
  the `_sev` helper idiom there.
- [ ] **Step 6: Labeler-level test** (append to
  `tests/test_barrier_geometry.py`): build a tiny synthetic price path
  where the floored barrier does NOT resolve but the unfloored one
  would — assert the emitted label's barrier is `tb_time` with the
  floor on and `tb_pt` with `label_pt_cost_mult=0` (proves the wire
  reaches the label). Use the CandidateLabeler test idiom from
  `tests/test_label_signal_quality.py` (frozen clock if weights are
  asserted).
- [ ] **Step 7: 10× runs, full battery, commit**
  `feat(ml): cost-floored barrier geometry, one source of truth (T2)`.

---

### Task 3: schema bump — self-describing rows (`pt_frac`, `sl_frac`)

**Files:**
- Modify: `ml/history.py` (HEADER ~:1391, `_append_row`, schema
  version constant + migration map — anchor by content: the existing
  migration machinery that padded features on past bumps),
  `scripts/migrate_history.py` if it carries a column map.
- Test: `tests/test_history_migration.py` (extend existing migration
  tests; find them via `grep -l migrate tests/`).

**Interfaces:**
- Produces: every NEW row records the barrier distances it was labeled
  under (`pt_frac`, `sl_frac`, floats; 0.0 = unknown/legacy). Task 6's
  comparator reads them.
- Consumes: Task 2's `barrier_geometry` values at label time.

- [ ] **Step 1: RED test** — a legacy-header CSV round-trips through
  the migration with the two new columns appended and 0.0 defaults;
  new rows carry real values; `load_training_data` is unaffected
  (columns are metadata, never features — assert the feature matrix
  width is unchanged).
- [ ] **Step 2: Implement** following the exact pattern of the last
  schema bump (read that commit first: `git log --oneline --
  ml/history.py | grep -i schema`). Thread the labeler's computed
  `(pt_frac, sl_frac)` into `_emit_label` → `_append_row`.
- [ ] **Step 3: Migration proof** — run
  `.venv/bin/python scripts/migrate_history.py --src outputs/signal_history.csv --dest /tmp/mig_check.csv`
  and assert row count unchanged, new columns present. 10× tests,
  battery, commit `feat(ml): schema bump — rows carry their barrier
  geometry (T3)`.

---

### Task 4: sizer bracket path

**Files:**
- Modify: `risk/position_sizer.py` (`size()` signature + bar/Kelly
  block).
- Test: `tests/test_sizer_derived_bar.py` (extend).

**Interfaces:**
- Produces: `size(..., bracket: "tuple[float, float] | None" = None)`
  — `(pt_pct, sl_pct)` in PERCENT. When None: byte-identical legacy.
  When set: per-trade `b_net_trade=(pt_pct−rt)/(sl_pct+rt)`, bar =
  `max(1/(1+b_net_trade)+p_bar_edge_margin, min_p_win)` (+counter-trend
  bonus), Kelly f* on `b_net_trade`, and post-Kelly notional scaled by
  `stop_loss_pct / sl_pct`. `SizeDecision.payoff_b` reports the bracket
  b when present.
- Consumed by: Task 5's entry paths.

- [ ] **Step 1: RED tests** (extend `tests/test_sizer_derived_bar.py`,
  reuse its `_sizer`/`_size` helpers — add a `bracket=` passthrough):

```python
def test_bracket_overrides_the_global_bar_per_trade():
    s = _sizer(p_bar_mode="derived")
    # wide bracket (pt 4%, sl 3%): b=(4-.65)/(3+.65)=0.918, bar 0.521
    d = _size(s, 0.55, bracket=(4.0, 3.0))
    assert not any("SZ-023" in r for r in d.reasons)   # clears 0.521
    d2 = _size(s, 0.50, bracket=(4.0, 3.0))
    assert any("SZ-023" in r for r in d2.reasons)      # below it


def test_bracket_notional_scales_dollar_risk_to_the_stop():
    s = _sizer(p_bar_mode="derived")
    d_legacy_like = _size(s, 0.80, bracket=(2.667, 2.0))  # sl == 2%
    d_wide = _size(s, 0.80, bracket=(5.334, 4.0))         # sl 2x wider
    assert d_legacy_like.approved and d_wide.approved
    # same p, same b (ratio equal) -> same f; notional halves as sl doubles
    assert abs(d_wide.usd - d_legacy_like.usd / 2.0) < max(
        0.02 * d_legacy_like.usd, 1.0)


def test_no_bracket_is_byte_identical_legacy():
    s = _sizer(p_bar_mode="derived")
    a = _size(s, 0.70)
    b = _size(s, 0.70, bracket=None)
    assert (a.usd, a.kelly_f, a.reasons) == (b.usd, b.kelly_f, b.reasons)
```

- [ ] **Step 2: Implement** in `size()`: at the top of the bar block
  (anchor: `p_bar = self.p_bar_base`):

```python
        b_net = self.b_net
        if bracket is not None:
            pt_pct, sl_pct = float(bracket[0]), float(bracket[1])
            if not (_fin(pt_pct) and _fin(sl_pct) and pt_pct > EPS
                    and sl_pct > EPS):
                d.reasons.append(tag(Code.SZ_INVALID_INPUT,
                                     f"bracket={bracket!r}"))
                return d
            # the bet being sized IS the labeled bracket (spec D3):
            # worst-case costs, per-trade breakeven, and dollar-risk
            # normalized to the legacy 2%-stop scale (risk lives in
            # SIZE — operator decision, sl is never capped).
            b_net = max((pt_pct - self.rt_cost_pct)
                        / max(sl_pct + self.rt_cost_pct, EPS), EPS)
        p_bar = (max(1.0 / (1.0 + b_net) + self.p_bar_edge_margin,
                     self.min_p_win)
                 if (bracket is not None and self.p_bar_mode == "derived")
                 else self.p_bar_base)
```

  then use `b_net` (not `self.b_net`) in the Kelly block of this call,
  and immediately after `usd = equity * f` scale
  `if bracket is not None: usd *= (self.stop_loss_pct_ref / sl_pct)`
  where `self.stop_loss_pct_ref = float((risk_cfg or {}).get(
  "stop_loss_pct", 2.0))` is captured in `__init__`. Set
  `d.payoff_b = b_net`. Keep every downstream multiplier/cap untouched.
- [ ] **Step 3: Mutation check** — force `b_net = self.b_net` ignoring
  the bracket (scratchpad-copy restore, never git checkout): the first
  test must go RED. Restore.
- [ ] **Step 4: 10× runs, battery, commit**
  `feat(sizer): per-trade bracket bar + risk-in-size notional (T4)`.

---

### Task 5: engine — bracket entries, bracket exits, tb_* live reasons

The largest task. READ FIRST: `main.py`'s entry path around the
`self.sizer.size(` call (~:3093), the exploration/probe path, the
per-position exit evaluation seam (isolated fast_cycle exit function),
and how exit closes record their reason string into postmortems/live
labels (grep `"trail"`, `"tier"`, `barrier=` in main.py + postmortem
flow). Follow existing patterns exactly.

**Files:**
- Modify: `core/state.py` (Position: `bracket_pt_frac: float = 0.0`,
  `bracket_sl_frac: float = 0.0`, `bracket_deadline_ts: float = 0.0` —
  defaulted, legacy-inert, serialized like every other field),
  `main.py` (entry paths + exit evaluation + close-reason threading),
  `config.json` (`bracket_exits: {"enabled": true}` + `_doc`),
  `core/config_guard.py` (coherence FATALs + probe-clearance WARN
  extension per spec D5).
- Test: `tests/test_bracket_exits.py` (create).

**Interfaces:**
- Consumes: `barrier_geometry` (T2), `size(bracket=)` (T4).
- Produces: model-lane positions carrying bracket fields; closes with
  reasons `tb_pt` / `tb_sl` / `tb_time`; overlay exits keep their own
  reasons. Task 6 consumes the closes.

**Binding behaviors (each gets a test):**
1. Entry (conviction AND probe) with `bracket_exits.enabled`: compute
   `(pt_frac, sl_frac)` via `barrier_geometry(sigma_bar,
   est_cost_pct, ml.label_pt_vol_mult, ml.label_sl_vol_mult,
   ml.label_pt_cost_mult)` using the SAME cost the pretrade decision
   estimated (`est_cost_bps / 100`); pass
   `bracket=(pt_frac*100, sl_frac*100)` to `size()`; stamp the three
   Position fields (`deadline_ts = entry_ts + label_max_bars *
   bar_seconds`, bar_seconds = 300, the 5m cadence — reuse the
   constant main already derives label spans from, grep
   `label_max_bars` in main.py).
2. Exit evaluation for a bracket position REPLACES the tier engine for
   that position (never both): pt leg → maker-first profit exit at
   `entry*(1±pt_frac)`; sl leg → the existing protective-stop path at
   `entry*(1∓sl_frac)`; deadline passed → full close via the normal
   exit ladder, reason `tb_time`. Overlays (ratchet, hard-stop DD,
   flatten, force_dry, manip, watchdog) remain senior and keep their
   own reasons — assert at least ratchet still fires on a bracket
   position.
3. Close-reason strings thread into the live-label/postmortem path
   verbatim (`tb_pt`/`tb_sl`/`tb_time`) — assert a closed bracket
   position produces a live row whose `label_era_of(barrier)` is
   `LABEL_ERA_TRIPLE_BARRIER` (this is V1's closure).
4. `bracket_exits.enabled=false` → byte-identical legacy behavior
   (tier exits, no bracket fields stamped).
5. Guards: FATAL enabled+`label_mode != "triple_barrier"`; probe
   clearance WARN extended to the worst-case floored-bracket bar
   (0.614 today — compute from config, don't hardcode; the test pins
   the shipped-config number).

- [ ] Steps: RED tests for behaviors 1–5 (use the injected-feed
  deterministic engine harness from `tests/test_e2e_learn_loop.py` /
  `tests/test_governor_recovery.py` idioms — build the bot with
  synthetic feeds, drive `cycle_once`), implement, 10× runs, mutation
  check on the enabled/disabled branch, battery, commit
  `feat(engine): model-lane bracket exits — the traded bet is the
  labeled bet (T5)`.

---

### Task 6: comparator ML-082 + telemetry

**Files:**
- Modify: `core/codes.py` (`ML_BRACKET_DIVERGENCE = "ML-082"`),
  `ml/history.py` or `ml/postmortem.py` (wherever live closes are
  recorded — the comparator computes at close time),
  `scripts/gc_pusher.py` (gauge, fresh-branch only, honest absence),
  `scripts/build_trading_dashboard.py` (one stat panel, execution
  board era row) + regenerate shipped JSONs,
  `tests/test_trading_dashboard.py` `_SYNTH_STATUS`.
- Test: `tests/test_bracket_divergence.py` (create) + dashboard tests.

**Interfaces:**
- Consumes: T3's `pt_frac`/`sl_frac` row columns, T5's tb_* closes.
- Produces: `status["ml"]["bracket_divergence"] = {"n": int,
  "agree_rate": float, "mean_abs_ret_delta_pct": float}` over a rolling
  window (reuse the postmortem summary window machinery); gauge
  `liquiditybot_bracket_divergence_rate` (+`_n`); DL-6 discipline: only
  in the fresh branch, nothing when absent, clamped labels n/a (no
  labels).

- [ ] Steps: RED tests (fixture status with/without the block — mirror
  the era-gauge tests from the grafana-era work; comparator unit: a
  close whose realized ret matches the labeled counterfactual within
  tolerance counts agree, outside counts disagree; report-only — assert
  no decision path imports it), implement, regenerate boards, dashboard
  suite green (check 3 exercises the new gauge via `_SYNTH_STATUS`),
  10× runs, battery, commit `feat(telemetry): labeled-vs-realized
  bracket comparator ML-082 (T6)`.

---

### Task 7: cost honesty — measured, conscious

**Files:**
- Create: `scripts/cost_truth_report.py` (report-only; reads
  `outputs/postmortem_summary.csv` fees/slippage columns + any
  fee_recon OM-080 audit records; prints measured round-trip bps vs
  configured 25/40).
- Test: `tests/test_cost_truth_report.py` (synthetic postmortem CSV →
  known measured bps; report never mutates config).

- [ ] Steps: RED test, implement (no config edits in code — the report
  PRINTS; a config change, if the evidence supports one, is the
  controller/operator's own commit per spec D4), run against the real
  outputs and record findings in the task report, 10× runs, battery,
  commit `feat(scripts): measured round-trip cost truth report (T7)`.

---

### Task 8: whole-feature battery + quant adjudication + rollout notes

- [ ] Full battery (Global Constraints list) — everything green.
- [ ] `.venv/bin/python scripts/quant_trials.py` at the CI-bound config
  AND, if any G-number moved, the full 200×1200 with a conscious
  re-baseline note in `docs/quant/` (never widen a gate).
- [ ] `scripts/overfit_check.py` — report vs the 5/3 baseline.
- [ ] Update `docs/superpowers/specs/2026-07-27-geometry-alignment-design.md`
  status line to "implemented @ <sha>"; append the ledger entry
  (`.superpowers/sdd/progress.md`) with measured facts (bar numbers,
  probe clearance, era-gap counts from T1, cost-truth findings from T7).
- [ ] Commit `feat: geometry alignment complete — battery + adjudication
  (T8)`. Controller then reviews whole-branch, pushes, ffs main; the PC
  deploys via the test-gated updater; watch era panels + divergence
  stat + drought clock per spec Rollout.
