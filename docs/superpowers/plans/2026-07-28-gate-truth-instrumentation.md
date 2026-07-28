# Gate-Truth Instrumentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the informed-flow gate's five component scores (+fused
evidence, +concentration) on every training row and add a report that
grades each component against realized triple-barrier outcomes — so the
gate weights become measurable instead of static numbers.

**Architecture:** Capture at the signal (`SignalResult.components`),
thread through BOTH row paths (candidate registry → labeler; entry
order.meta → pending tuple → live close), persist as 7 trailing
telemetry columns (T3/pt_frac pattern — bookkeeping, never features),
grade offline in `scripts/gate_truth_report.py` with XV-040/041/042
verdicts.

**Tech Stack:** Python 3.11, numpy, csv, pytest. No new dependencies.

## Global Constraints (spec: docs/superpowers/specs/2026-07-28-gate-truth-instrumentation.md)

- Column names, EXACT order, appended after `sl_frac`: `sg_flow`,
  `sg_delta`, `sg_accum`, `sg_burst`, `sg_trend`, `sg_evidence`, `sg_conc`.
- Component dict keys, EXACT: `flow`, `delta`, `accum`, `burst`, `trend`,
  `evidence`, `conc` (module constant `SG_COMPONENT_KEYS` in ml/history.py,
  that 7-tuple in that order; columns are `"sg_" + key`).
- Defaults 0.0 = pre-instrumentation/unknown; cells written `%.4f`.
- Non-finite component values sanitize to 0.0 — telemetry NEVER drops a
  row (unlike pnl/pt_frac which stay label-bearing and still refuse).
- FEATURE_NAMES untouched. Model dimensionality unchanged. No config
  knobs added. five_gate legacy engine untouched. NO weight changes.
- Trailing-meta column count moves 13 → 20 exactly once (ml/history.py
  `_append_row` width assert + its comment).
- Rows store RAW signed scores (positive = long evidence); direction
  alignment (`s_i × direction`) is derived at READ time in the report.
- Report verdict codes, EXACT: XV-040 aligned, XV-041 misaligned,
  XV-042 insufficient (< 100 instrumented era rows; module constant
  `SG_MIN_ROWS = 100`).
- Committer discipline: `git -c user.email=noreply@anthropic.com -c
  user.name=Claude commit`; trailers exactly
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01TgfcWLtZtVMQhbiPZCCV8h`.
- Every pytest run FOREGROUND (never background). New test files get a
  10-run stability loop before the task is done.

---

### Task 1: SignalResult.components + informed_flow capture

**Files:**
- Modify: `strategies/signal_gates.py:65-79` (SignalResult dataclass)
- Modify: `strategies/informed_flow.py:454-459` (final SignalResult return)
- Test: `tests/test_gate_components.py` (create)

**Interfaces:**
- Consumes: existing `SignalResult` dataclass; informed_flow `_evaluate`
  locals `s_flow, s_delta, s_accum, s_burst, s_trend, evidence,
  concentration` (all floats, already computed).
- Produces: `SignalResult.components: dict` — `{}` default; populated by
  informed_flow with the 7 keys from Global Constraints. Tasks 3/4 read
  `signal.components`.

- [ ] **Step 1: Write the failing tests**

```python
"""Gate-truth instrumentation T1: the informed-flow engine exposes its
component scores on the SignalResult so the realization path can grade
them (2026-07-28 audit: components were computed and discarded — the
weights were unfalsifiable)."""
import math
import types

from strategies.signal_gates import SignalResult


def test_signalresult_components_defaults_empty():
    r = SignalResult(symbol="ETH/USD", direction=None, confidence=0.0,
                     size=0.0, all_confirmed=False)
    assert r.components == {}


def _view(n_bars=40, imb=1.4):
    candles = []
    px = 100.0
    for i in range(n_bars):
        px *= 1.003
        candles.append({"time": 1000 + i * 300, "open": px * 0.999,
                        "high": px * 1.002, "low": px * 0.997,
                        "close": px, "volume": 50.0 + (i % 5)})
    return {"kraken_symbol": "ETH/USD", "candles": candles,
            "imbalance_ratio": imb, "funding_rate": 0.0,
            "funding_available": True}


def test_informed_flow_populates_all_seven_keys():
    from strategies.informed_flow import InformedFlowEngine
    eng = InformedFlowEngine({})
    view = _view()
    for _ in range(6):                      # feed the EWMAs/persistence
        r = eng.evaluate_asset("ETH", view)
    assert set(r.components) == {"flow", "delta", "accum", "burst",
                                 "trend", "evidence", "conc"}
    assert all(isinstance(v, float) and math.isfinite(v)
               for v in r.components.values())
    # evidence is the fused sum the confirmation thresholds on — the
    # persisted value must be the same quantity (raw, signed)
    w = eng.w
    fused = sum(w[k] * r.components[k]
                for k in ("flow", "delta", "accum", "burst", "trend"))
    assert abs(fused - r.components["evidence"]) < 1e-9
    assert 0.0 <= r.components["conc"] <= 1.0


def test_warmup_return_has_empty_components():
    from strategies.informed_flow import InformedFlowEngine
    eng = InformedFlowEngine({})
    r = eng.evaluate_asset("ETH", _view(n_bars=3))     # < min_bars
    assert r.components == {}


def test_fault_path_has_empty_components():
    from strategies.informed_flow import InformedFlowEngine
    eng = InformedFlowEngine({})
    r = eng.evaluate_asset("ETH", {"candles": [{"close": "not-a-number"}]})
    assert r.components == {}
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_gate_components.py -v`
Expected: FAIL — `SignalResult.__init__` has no `components` /
`AttributeError: components`.

- [ ] **Step 3: Implement**

`strategies/signal_gates.py` — append to the SignalResult dataclass after
`evidence_concentration`:

```python
    # gate-truth instrumentation (2026-07-28 audit): the informed-flow
    # engine's RAW signed component scores {flow, delta, accum, burst,
    # trend} plus the fused "evidence" (Σ w·s) and "conc" (normalized-HHI
    # concentration). Persisted per row (sg_* columns, ml/history.py) so
    # realized outcomes can grade WHICH evidence was right — the weights
    # stop being unfalsifiable. {} = legacy engine / warmup / fault path;
    # downstream writes zeros. TELEMETRY ONLY — never a feature, never a
    # decision input.
    components: dict = field(default_factory=dict)
```

`strategies/informed_flow.py` — replace the final return (lines 454-459)
with:

```python
        def _fin(v: float) -> float:
            return float(v) if math.isfinite(float(v)) else 0.0

        return SignalResult(
            symbol=symbol,
            direction=direction if all_confirmed else None,
            confidence=confidence, size=0.0,
            all_confirmed=all_confirmed, gates_passed=gates,
            urgency=urgency, evidence_concentration=round(concentration, 3),
            components={"flow": _fin(s_flow), "delta": _fin(s_delta),
                        "accum": _fin(s_accum), "burst": _fin(s_burst),
                        "trend": _fin(s_trend), "evidence": _fin(evidence),
                        "conc": _fin(concentration)})
```

(`math` is already imported at module top. The warmup return at ~:337 and
the fail-closed return in `evaluate_asset` are NOT modified — they keep
the dataclass default `{}`.)

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/bin/python -m pytest tests/test_gate_components.py tests/test_rev3.py -v`
Expected: all PASS (test_rev3 guards the engine's existing contract).

- [ ] **Step 5: Stability + commit**

Run the new file 10×; then:
```bash
git add strategies/signal_gates.py strategies/informed_flow.py tests/test_gate_components.py
git -c user.email=noreply@anthropic.com -c user.name=Claude commit -m "feat(gates): SignalResult carries its component scores (gate-truth T1)"
```
(trailers per Global Constraints)

---

### Task 2: history schema +7 sg_* telemetry columns

**Files:**
- Modify: `ml/history.py:654-657` (_header), `:701-715` (column comment
  block — append sg_* paragraph), `:753-761` (log_entry), `:763-813`
  (_append_row), `:832-890` (log_close)
- Test: `tests/test_gate_components.py` (extend)

**Interfaces:**
- Consumes: nothing from T1 at runtime (dict shape only).
- Produces: `SG_COMPONENT_KEYS = ("flow", "delta", "accum", "burst",
  "trend", "evidence", "conc")` module constant in ml/history.py;
  `_append_row(..., gate_components: "dict | None" = None)`;
  `log_entry(..., gate_components: "dict | None" = None)`;
  `log_close` unchanged signature (reads the pending tuple). Task 5's
  report imports `SG_COMPONENT_KEYS`.

- [ ] **Step 1: Write the failing tests** (append to tests/test_gate_components.py)

```python
import csv

import numpy as np


def _mk_store(tmp_path):
    from ml.history import HistoryStore
    return HistoryStore(str(tmp_path / "hist.csv"))


def _feats():
    from ml.features import FEATURE_NAMES
    return np.zeros(len(FEATURE_NAMES))


SG = {"flow": 0.5, "delta": -0.25, "accum": 0.1, "burst": 0.0,
      "trend": 0.33, "evidence": 0.91, "conc": 0.4}


def test_header_gains_seven_sg_columns_last(tmp_path):
    hs = _mk_store(tmp_path)
    assert hs._header[-7:] == ["sg_flow", "sg_delta", "sg_accum",
                               "sg_burst", "sg_trend", "sg_evidence",
                               "sg_conc"]
    assert hs._header[-9:-7] == ["pt_frac", "sl_frac"]   # order preserved


def test_append_row_writes_components_and_defaults_zero(tmp_path):
    hs = _mk_store(tmp_path)
    hs._append_row("p1", "ETH", "long", _feats(), 1, 0.0, "candidate",
                   gate_components=SG)
    hs._append_row("p2", "ETH", "long", _feats(), 0, 0.0, "candidate")
    rows = list(csv.DictReader(open(hs.path, encoding="utf-8")))
    assert rows[0]["sg_flow"] == "0.5000"
    assert rows[0]["sg_delta"] == "-0.2500"
    assert rows[0]["sg_evidence"] == "0.9100"
    assert rows[1]["sg_flow"] == "0.0000"          # default: uninstrumented


def test_nonfinite_component_sanitizes_never_drops(tmp_path):
    hs = _mk_store(tmp_path)
    bad = dict(SG, flow=float("nan"), conc=float("inf"))
    hs._append_row("p3", "ETH", "long", _feats(), 1, 0.0, "candidate",
                   gate_components=bad)
    rows = list(csv.DictReader(open(hs.path, encoding="utf-8")))
    assert len(rows) == 1                          # row kept
    assert rows[0]["sg_flow"] == "0.0000"
    assert rows[0]["sg_conc"] == "0.0000"
    assert rows[0]["sg_delta"] == "-0.2500"        # good keys survive


def test_live_row_carries_components_via_pending_tuple(tmp_path):
    hs = _mk_store(tmp_path)
    hs.log_entry("pos9", "ETH", "short", _feats(), probe=True,
                 candidate_id="cand-1", book="5m", gate_components=SG)
    hs.log_close("pos9", -1.25, barrier="tb_sl")
    rows = list(csv.DictReader(open(hs.path, encoding="utf-8")))
    assert rows[0]["source"] == "live" and rows[0]["barrier"] == "tb_sl"
    assert rows[0]["sg_flow"] == "0.5000"
    assert rows[0]["sg_trend"] == "0.3300"


def test_legacy_pending_tuple_shapes_still_close(tmp_path):
    # a pre-instrumentation snapshot restores 7-element pending tuples —
    # closing one must still write a row (sg_* all zero)
    hs = _mk_store(tmp_path)
    hs._pending["old1"] = ("ETH", "long", _feats(), 123.0, False, "", "5m")
    hs.log_close("old1", 2.0)
    rows = list(csv.DictReader(open(hs.path, encoding="utf-8")))
    assert len(rows) == 1 and rows[0]["sg_flow"] == "0.0000"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_gate_components.py -v`
Expected: new tests FAIL (`sg_flow` not in header / unexpected kwarg).

- [ ] **Step 3: Implement in ml/history.py**

3a. Module-level constant near `LABEL_ERA_*` definitions:

```python
# gate-truth instrumentation (2026-07-28): the informed-flow component
# vocabulary, ONE source of truth for capture (SignalResult.components),
# persistence (the sg_* trailing columns below) and the offline grader
# (scripts/gate_truth_report.py). Order IS the column order.
SG_COMPONENT_KEYS = ("flow", "delta", "accum", "burst", "trend",
                     "evidence", "conc")
```

3b. `_header` (line 654-657) becomes:

```python
        self._header = ["position_id", "asset", "side", *FEATURE_NAMES,
                        "label", "net_pnl_usd", "source", "ts", "signal_ts",
                        "barrier", "probe", "disp", "candidate_id", "book",
                        "label_era", "pt_frac", "sl_frac",
                        *[f"sg_{k}" for k in SG_COMPONENT_KEYS]]
```

3c. Append to the trailing-column comment block (after the pt_frac/sl_frac
paragraph, line ~715):

```python
        # sg_flow..sg_conc (gate-truth instrumentation, 2026-07-28): the
        # informed-flow engine's RAW signed component scores at signal
        # time (positive = long evidence), the fused evidence Σw·s and
        # the normalized-HHI concentration — SG_COMPONENT_KEYS order.
        # 0.0 = pre-instrumentation row / legacy five_gate engine /
        # warmup. Direction alignment is derived at READ time
        # (scripts/gate_truth_report.py: s_i × direction), never baked
        # in. Non-finite values sanitize to 0.0 at append — telemetry
        # never drops a row. LAST seven columns so every existing
        # row/consumer is untouched. BOOKKEEPING ONLY — never a feature.
```

3d. `_append_row`: signature gains `gate_components: "dict | None" = None`
(after `sl_frac`). Width assert (line 776-783) — comment and both
literals move 13 → 20:

```python
        # 20 trailing meta columns (label..label_era, pt_frac, sl_frac,
        # sg_flow..sg_conc - gate-truth instrumentation added the last 7).
        if 3 + len(feats) + 20 != len(self._header):
            log.warning(
                f"{Code.ML_SCHEMA_MISMATCH.value}: refusing to append row "
                f"{position_id[:12]} ({asset}): {len(feats)} features vs "
                f"schema {len(self._header) - 20} - stale pre-rotation "
                f"vector, row would misalign under the current header")
            return
```

Before the `with open(...)` write, sanitize:

```python
        sg = {}
        src_sg = gate_components if isinstance(gate_components, dict) else {}
        for k in SG_COMPONENT_KEYS:
            try:
                v = float(src_sg.get(k, 0.0))
            except (TypeError, ValueError):
                v = 0.0
            sg[k] = v if np.isfinite(v) else 0.0
```

and extend the writerow list (after the pt_frac/sl_frac cells):

```python
                                    f"{pt_frac:.6f}", f"{sl_frac:.6f}",
                                    *[f"{sg[k]:.4f}" for k in
                                      SG_COMPONENT_KEYS]])
```

3e. `log_entry`: signature gains `gate_components: "dict | None" = None`;
the pending tuple gains an 8th element:

```python
        self._pending[position_id] = (asset, direction, features.copy(),
                                      time.time(), bool(probe),
                                      candidate_id or "", book,
                                      dict(gate_components or {}))
```

3f. `log_close`: add the len==8 unpack FIRST (above len==7), default
`gate_comp = None` before the chain, and thread it:

```python
        gate_comp = None
        if len(entry) == 8:
            (asset, direction, feats, sig_ts, probe, cand_id, book,
             gate_comp) = entry
        elif len(entry) == 7:
            asset, direction, feats, sig_ts, probe, cand_id, book = entry
        ...
        self._append_row(..., pt_frac=pt_frac, sl_frac=sl_frac,
                        gate_components=gate_comp)
```

- [ ] **Step 4: Run the schema-sensitive suites**

Run: `.venv/bin/python -m pytest tests/test_gate_components.py tests/test_history_migration.py tests/test_migrate_history.py tests/test_session_import_migrate.py tests/test_v8_batch.py tests/test_side_relative.py tests/test_feature_trio.py tests/test_bracket_exits.py tests/test_bracket_divergence.py -v`
Expected: PASS. If a test pins the old trailing-13 geometry, update THAT
test's expectation to 20 / the new tail — never weaken the assert.

- [ ] **Step 5: Stability + commit**

10× loop on tests/test_gate_components.py, then commit
(`feat(ml): rows carry gate component scores — sg_* schema bump (gate-truth T2)`).

---

### Task 3: candidate-path threading

**Files:**
- Modify: `ml/history.py:1692-1738` (CandidateTracker.register),
  `:1901-1916` (_emit_label)
- Modify: `main.py:3324-3329` (the one register call site)
- Test: `tests/test_gate_components.py` (extend)

**Interfaces:**
- Consumes: T1 `signal.components` (dict); T2 `_append_row(...,
  gate_components=...)` and `SG_COMPONENT_KEYS`.
- Produces: `CandidateTracker.register(..., gate_components: "dict |
  None" = None)`; candidate dict key `"gate_components"`.

- [ ] **Step 1: Write the failing test** (append to tests/test_gate_components.py)

```python
def test_candidate_row_carries_components_through_labeler(tmp_path):
    """register(gate_components=...) -> poll() -> the persisted candidate
    row carries the scores; a candidate registered without them writes
    zeros. Uses the real CandidateLabeler machinery, minimal bars."""
    from ml.history import HistoryStore
    hs = HistoryStore(str(tmp_path / "hist.csv"))
    lab = hs.labeler                      # CandidateTracker instance
    lab.register("ETH", "long", _feats(), 0.01, 1000,
                 gates_passed={"g": True}, gate_components=SG)
    lab.register("SOL", "short", _feats(), 0.01, 1000)
    for cand in lab._cands:
        cand["disp"] = "confirmed"
    # feed enough closed bars past the horizon that both label at poll()
    n = lab.horizon + 5
    for c in lab._cands:
        c["bar_time"] = 0
    closes = [100.0 * (1.0 + 0.001 * i) for i in range(n)]
    lab._bars = {"ETH": [{"time": i * 300, "close": px, "high": px * 1.001,
                          "low": px * 0.999} for i, px in enumerate(closes)],
                 "SOL": [{"time": i * 300, "close": px, "high": px * 1.001,
                          "low": px * 0.999} for i, px in enumerate(closes)]}
    wrote = lab.poll()
    assert wrote >= 1
    rows = list(csv.DictReader(open(hs.path, encoding="utf-8")))
    by_asset = {r["asset"]: r for r in rows}
    assert by_asset["ETH"]["sg_flow"] == "0.5000"
    assert by_asset["ETH"]["sg_conc"] == "0.4000"
    if "SOL" in by_asset:
        assert by_asset["SOL"]["sg_flow"] == "0.0000"
```

NOTE for the implementer: the exact candle-feeding mechanics above are a
sketch of INTENT — mirror how existing CandidateLabeler tests (grep
`register(` in tests/, e.g. the eviction/label tests) drive `poll()` to
a real labeled append, and assert the sg_* cells exactly as shown. If
the tracker attribute isn't `hs.labeler`, use the same construction the
existing labeler tests use. The assertion contract (ETH row "0.5000" /
"0.4000", unregistered row "0.0000") is BINDING; the plumbing to get a
labeled row is whatever the existing tests already do.

- [ ] **Step 2: Run to verify failure** (unexpected kwarg `gate_components`)

- [ ] **Step 3: Implement**

3a. `CandidateTracker.register`: signature gains
`gate_components: "dict | None" = None` (after `confidence`); the
candidate dict gains (after the `"gates"` entry):

```python
                            # gate-truth instrumentation: the RAW signed
                            # component scores at signal time — persisted
                            # onto this candidate's labeled row so the
                            # realization path can grade the weights.
                            "gate_components": (dict(gate_components)
                                                if isinstance(
                                                    gate_components, dict)
                                                else None),
```

3b. `_emit_label`: the `_append_row` call gains
`gate_components=cand.get("gate_components"),` (after `sl_frac=...`).

3c. `main.py` register call (line ~3324) gains one argument:

```python
                if self.candidates.register(asset, signal.direction, feats,
                                        vol_state.sigma_bar_pct / 100.0,
                                        v["candles"][-1]["time"],
                                        gates_passed=signal.gates_passed,
                                        spread_bps=liq_state.spread_bps,
                                        confidence=model_p,  # W2-1: honest p(win)
                                        gate_components=signal.components):
```

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_gate_components.py tests/test_v8_batch.py -v` — PASS.

- [ ] **Step 5: Stability + commit** (`feat(ml): candidate rows carry gate components (gate-truth T3)`).

---

### Task 4: live-path threading (entry meta → fill → close)

**Files:**
- Modify: `main.py` — direct-submit meta (~:3575-3582), ladder rung meta
  (~:4454-4470 in `_place_ladder`), algo parent meta (~:3496-3507),
  `_handle_fill`'s log_entry call (~:1487-1493)
- Test: `tests/test_gate_components.py` (extend)

**Interfaces:**
- Consumes: T1 `signal.components`; T2 `log_entry(...,
  gate_components=...)`.
- Produces: `order.meta["gate_components"]` on every entry path;
  `_algo_meta[parent_id]["gate_components"]` for algo children (thread
  wherever the algo child's order meta is assembled from `_algo_meta` —
  grep `_algo_meta[` in main.py and mirror how `"features"` flows).

- [ ] **Step 1: Write the failing source-contract test** (append)

```python
def test_all_three_entry_paths_thread_gate_components():
    """Source contract (same idiom as test_label_realize's): every entry
    meta block and the fill->log_entry handoff thread the components."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "main.py").read_text(
        encoding="utf-8")
    # 3 entry meta blocks (direct, ladder, algo) name the key
    assert src.count('"gate_components": ') >= 3
    # the fill handoff passes it into the pending tuple
    assert 'gate_components=order.meta.get("gate_components")' in src
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement** — add to each of the three meta dicts:

```python
                    "gate_components": dict(signal.components or {}),
```

(direct :3575 block after `"thales_fired"`; ladder :4454 block after
`"thales_fired"`; algo `_algo_meta` block after `"bracket_deadline_ts"`).
For the algo path, ALSO thread from `_algo_meta` into the child order's
meta exactly where `"features"` already flows (grep `_algo_meta` /
`_submit_algo_child`). Then `_handle_fill`:

```python
                    self.history.log_entry(position_id, self._asset_of(pos.symbol),
                                        pos.direction, order.meta["features"],
                                        probe=pos.is_probe,
                                        candidate_id=order.meta.get(
                                            "candidate_id"),
                                        book=pos.book,
                                        gate_components=order.meta.get(
                                            "gate_components"))
```

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_gate_components.py tests/test_e2e_happy_path.py -v` — PASS (e2e proves the full live loop still runs; if the e2e harness asserts row column counts, update per T2).

- [ ] **Step 5: Stability + commit** (`feat(engine): entry paths thread gate components to live rows (gate-truth T4)`).

---

### Task 5: gate-truth report + XV codes

**Files:**
- Create: `scripts/gate_truth_report.py`
- Modify: `core/codes.py` (XV block, after XV-033)
- Test: `tests/test_gate_truth_report.py` (create)

**Interfaces:**
- Consumes: T2 `SG_COMPONENT_KEYS` (import from ml.history); corpus CSV
  columns `sg_*`, `label`, `label_era`, `direction` (the FEATURE column,
  ±1), `gate_confidence` (FEATURE column), `source`.
- Produces: `build_report(history_path: str, config_path: str) -> str`;
  `classify_alignment(weights: dict, aucs: dict, n: int) -> tuple[str, str]`
  returning (code_value, human_line); CLI `python scripts/gate_truth_report.py`.

- [ ] **Step 1: codes** — in `core/codes.py` after `XV_COST_TRUTH_*`
(grep XV-033), add:

```python
    XV_GATE_TRUTH_ALIGNED = "XV-040"     # gate weights rank-agree with realized component AUCs
    XV_GATE_TRUTH_MISALIGNED = "XV-041"  # weight order contradicts measured discrimination
    XV_GATE_TRUTH_THIN = "XV-042"        # < SG_MIN_ROWS instrumented era rows — no verdict
```

and mention gate truth in the XV family header comment.

- [ ] **Step 2: Write the failing tests**

```python
"""Gate-truth report: grades the informed-flow components against
realized triple-barrier outcomes from the persisted sg_* telemetry."""
import csv

from ml.features import FEATURE_NAMES
from ml.history import SG_COMPONENT_KEYS
from scripts.gate_truth_report import (SG_MIN_ROWS, _rank_auc,
                                       build_report, classify_alignment)


def test_rank_auc_basics():
    assert abs(_rank_auc([1, 2, 3, 4], [0, 0, 1, 1]) - 1.0) < 1e-9
    assert abs(_rank_auc([4, 3, 2, 1], [0, 0, 1, 1]) - 0.0) < 1e-9
    assert abs(_rank_auc([1, 2, 3, 4], [1, 0, 1, 0]) - 0.5) < 1e-9


def test_classify_thin_below_floor():
    code, _ = classify_alignment({"flow": 1.0}, {"flow": 0.6},
                                 n=SG_MIN_ROWS - 1)
    assert code == "XV-042"


def test_classify_aligned_and_misaligned():
    w = {"flow": 1.0, "delta": 0.6, "accum": 0.9, "burst": 0.8,
         "trend": 0.7}
    aligned_aucs = {"flow": 0.60, "delta": 0.52, "accum": 0.58,
                    "burst": 0.55, "trend": 0.53}
    code, _ = classify_alignment(w, aligned_aucs, n=500)
    assert code == "XV-040"
    inverted = {"flow": 0.45, "delta": 0.60, "accum": 0.47,
                "burst": 0.55, "trend": 0.58}
    code, _ = classify_alignment(w, inverted, n=500)
    assert code == "XV-041"


def _write_corpus(path, rows):
    from ml.history import HistoryStore
    hs = HistoryStore(str(path))
    hs._ensure_schema()
    header = hs._header
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in rows:
            w.writerow([r.get(c, "0") for c in header])


def test_build_report_end_to_end(tmp_path):
    """20 instrumented winners with positive aligned flow + 20 losers
    with negative aligned flow -> flow AUC 1.0 in the report text; below
    the floor -> XV-042 verdict line present."""
    p = tmp_path / "hist.csv"
    rows = []
    for i in range(40):
        win = i < 20
        rows.append({"position_id": f"p{i}", "asset": "ETH", "side": "long",
                     "direction": "1.000000", "label": "1" if win else "0",
                     "source": "candidate", "barrier": "tb_pt" if win
                     else "tb_sl", "label_era": "triple_barrier",
                     "ts": str(1000 + i), "signal_ts": str(1000 + i),
                     "sg_flow": "0.8000" if win else "-0.8000",
                     "sg_delta": "0.1000", "sg_evidence": "1.2000",
                     "sg_conc": "0.3000"})
    _write_corpus(p, rows)
    text = build_report(str(p), "config.json")
    assert "flow" in text and "1.000" in text
    assert "XV-042" in text            # 40 < SG_MIN_ROWS: verdict is THIN


def test_report_ignores_uninstrumented_and_old_era(tmp_path):
    p = tmp_path / "hist.csv"
    rows = [{"position_id": "z", "asset": "ETH", "side": "long",
             "direction": "1.000000", "label": "1", "source": "candidate",
             "barrier": "trail", "label_era": "exit_sim",
             "sg_flow": "0.9000", "ts": "1", "signal_ts": "1"},
            {"position_id": "y", "asset": "ETH", "side": "long",
             "direction": "1.000000", "label": "1", "source": "candidate",
             "barrier": "tb_pt", "label_era": "triple_barrier",
             "sg_flow": "0.0000", "ts": "2", "signal_ts": "2"}]
    _write_corpus(p, rows)
    text = build_report(str(p), "config.json")
    assert "instrumented era rows: 0" in text
```

- [ ] **Step 3: Run to verify failure** (module not found)

- [ ] **Step 4: Implement `scripts/gate_truth_report.py`**

```python
"""Gate-truth report: grade the informed-flow gate's component evidence
against realized triple-barrier outcomes (gate-truth instrumentation,
spec docs/superpowers/specs/2026-07-28-gate-truth-instrumentation.md).

Report-only — reads outputs/signal_history.csv, mutates nothing.
Sample: rows with label_era == "triple_barrier" AND any |sg_*| > 0
(instrumented). Direction alignment derived here: aligned_i = s_i × the
row's `direction` feature (±1) — rows store RAW signed scores.

SG_MIN_ROWS (=100): below this the verdict is XV-042 (thin) — the same
documented-floor approach as cost_truth_report's both-legs floor, never
a config knob (this is a measurement standard, not a tunable).
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.codes import Code                                # noqa: E402
from ml.history import SG_COMPONENT_KEYS                   # noqa: E402

SG_MIN_ROWS = 100
_WEIGHT_KEYS = ("flow", "delta", "accum", "burst", "trend")
_DEFAULT_W = {"flow": 1.0, "delta": 0.6, "accum": 0.9, "burst": 0.8,
              "trend": 0.7}


def _f(v, d=0.0):
    try:
        x = float(v)
        return x if x == x and abs(x) != float("inf") else d
    except (TypeError, ValueError):
        return d


def _rank_auc(x, y):
    """Mann-Whitney rank AUC of score x for binary y (ties: midrank)."""
    pairs = sorted(zip(x, y), key=lambda t: t[0])
    ranks, i = {}, 0
    while i < len(pairs):
        j = i
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        mid = (i + j + 1) / 2.0
        for k in range(i, j):
            ranks[k] = mid
        i = j
    n1 = sum(1 for _, yy in pairs if yy)
    n0 = len(pairs) - n1
    if not n1 or not n0:
        return float("nan")
    rsum = sum(ranks[k] for k, (_, yy) in enumerate(pairs) if yy)
    return (rsum - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def _spearman(a, b):
    """Spearman rho of two equal-length lists (ranks, no ties expected
    for 5 distinct weights; midrank if any)."""
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, i in enumerate(order):
            r[i] = pos + 1.0
        return r
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    ma = sum(ra) / n
    mb = sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** 0.5
    db = sum((y - mb) ** 2 for y in rb) ** 0.5
    return num / (da * db) if da and db else 0.0


def classify_alignment(weights, aucs, n):
    """(code_value, human_line) for the weight-vs-data verdict."""
    if n < SG_MIN_ROWS:
        return (Code.XV_GATE_TRUTH_THIN.value,
                f"{Code.XV_GATE_TRUTH_THIN.value}: only {n} instrumented "
                f"era rows (< {SG_MIN_ROWS}) - no verdict yet, keep "
                f"accruing")
    keys = [k for k in _WEIGHT_KEYS if k in weights and k in aucs]
    rho = _spearman([weights[k] for k in keys], [aucs[k] for k in keys])
    if rho >= 0.0:
        return (Code.XV_GATE_TRUTH_ALIGNED.value,
                f"{Code.XV_GATE_TRUTH_ALIGNED.value}: weight order "
                f"rank-agrees with realized AUCs (spearman {rho:+.2f}, "
                f"n={n})")
    return (Code.XV_GATE_TRUTH_MISALIGNED.value,
            f"{Code.XV_GATE_TRUTH_MISALIGNED.value}: weight order "
            f"CONTRADICTS realized discrimination (spearman {rho:+.2f}, "
            f"n={n}) - re-weight decision needs the full gate battery, "
            f"never a blind tune")


def build_report(history_path="outputs/signal_history.csv",
                 config_path="config.json"):
    try:
        cfg = json.load(open(config_path, encoding="utf-8"))
    except OSError:
        cfg = {}
    wcfg = ((cfg.get("strategies") or {}).get("weights") or {})
    weights = {k: _f(wcfg.get(k, _DEFAULT_W[k]), _DEFAULT_W[k])
               for k in _WEIGHT_KEYS}

    rows = list(csv.DictReader(open(history_path, encoding="utf-8")))
    era = [r for r in rows if (r.get("label_era") or "") == "triple_barrier"]
    inst = [r for r in era if any(abs(_f(r.get(f"sg_{k}"))) > 0.0
                                  for k in SG_COMPONENT_KEYS)]
    out = ["GATE TRUTH REPORT", "=" * 60,
           f"corpus rows: {len(rows)}  era rows: {len(era)}  "
           f"instrumented era rows: {len(inst)}", ""]

    y = [1.0 if r.get("label") == "1" else 0.0 for r in inst]
    aucs = {}
    out.append("[1] per-component realized discrimination "
               "(aligned = s_i x direction)")
    for k in _WEIGHT_KEYS:
        a = [_f(r.get(f"sg_{k}")) * _f(r.get("direction"), 1.0)
             for r in inst]
        auc = _rank_auc(a, y) if inst else float("nan")
        aucs[k] = auc
        n_pos = sum(1 for v in a if v > 0)
        out.append(f"  {k:6s} w={weights[k]:.2f}  AUC={auc:.3f}  "
                   f"aligned_n={n_pos}/{len(a)}")
    out.append("")

    out.append("[2] evidence strength + concentration")
    for k in ("evidence", "conc"):
        a = [_f(r.get(f"sg_{k}")) for r in inst]
        # evidence is signed long/short: align it too; conc is unsigned
        if k == "evidence":
            a = [v * _f(r.get("direction"), 1.0)
                 for v, r in zip(a, inst)]
        out.append(f"  {k:8s} AUC={_rank_auc(a, y) if inst else float('nan'):.3f}")
    out.append("")

    code, line = classify_alignment(weights, aucs, len(inst))
    out += ["[3] verdict", f"  {line}", ""]
    return "\n".join(out)


def main():
    print(build_report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run** `.venv/bin/python -m pytest tests/test_gate_truth_report.py -v` — PASS; then run the CLI once against the real corpus (`.venv/bin/python scripts/gate_truth_report.py`) and confirm it prints `instrumented era rows: 0` + XV-042 (no instrumented rows exist yet — correct).

- [ ] **Step 6: Stability + commit** (`feat(scripts): gate-truth report — components graded on realized outcomes (gate-truth T5)`).

---

### Task 6: full battery + ledger + deploy (controller task — not a subagent)

- [ ] Run the complete CLAUDE.md matrix (pytest, smoke, assurance,
  overfit_check, ruff, pyright, bandit, compileall). Overfit baseline:
  4 passed/3 failed at ~836+ era rows — investigate any regression, never
  compensate.
- [ ] Confirm the real-corpus report runs clean (XV-042 expected).
- [ ] Ledger entry in `.superpowers/sdd/progress.md`.
- [ ] Commit docs (spec+plan), push branch, fast-forward main.
- [ ] Final whole-branch review (requesting-code-review, most capable
  model) over merge-base..HEAD.

## Self-Review (done at authoring)

- Spec coverage: D1→T1, D2→T2, D3→T3, D4→T4, D5+D6→T5, D7 enforced by
  Global Constraints. ✓
- Placeholders: T3 Step 1 marks its candle-feeding sketch as intent with
  a binding assertion contract — deliberate (the labeler-test idiom
  already exists in-tree and is the single source of truth for that
  plumbing). No TBDs. ✓
- Type consistency: `components: dict` (T1) → `gate_components:
  "dict | None"` kwargs (T2/T3/T4) → `SG_COMPONENT_KEYS` consumed in T5.
  Column names identical everywhere. ✓
