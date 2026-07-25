# Learning-Acceleration Phase 1: Drought-Scoped Probe Floor (F0b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Break the SZ-047×SZ-030 entry livelock with a drought-scoped, deterministic probe floor that is byte-identical outside droughts.

**Architecture:** The rolling probe-share cap (`_probe_share_would_deny`, main.py:2390) currently fails closed forever when no admissions flow (the window only advances on admissions). The fix adds ONE new branch at the single throttle decision point (`_probe_admission_decision`, main.py:2416): when the share cap is the binding denial AND the ML-073 drought clock (`_last_entry_admit_ts`, engine-time, replay-deterministic) shows no admissions of any kind for ≥ a configured span, a rate-bounded floor admission fires instead of the SZ-047 denial, tagged with a NEW code SZ-048 and recorded into the window like any admission. Conviction entries remain untouchable by construction (the method still takes no sizing argument).

**Tech Stack:** Pure Python/numpy repo; pytest; config.json + core/config_guard.py; core/codes.py registry; scripts/build_trading_dashboard.py CODE_LABELS.

## Global Constraints

- CLAUDE.md hard invariants 1–7 untouched; dry-run hard gate on exploration (`main.py:2344-2345`) stays first.
- Non-drought behavior BYTE-IDENTICAL — pinned by test (mutation direction: with the floor disabled or no drought, every existing test in tests/test_probe_throttle.py passes unchanged).
- Engine time (`now`, injected) only — `time.time()` in this path is a defect (replay determinism).
- New behavior = registered code SZ-048 in core/codes.py + CODE_LABELS entry + regenerated dashboard JSONs in the SAME commit (tests/test_trading_dashboard.py::test_reason_codes_decoded_on_panels enforces full-family coverage and WILL fail otherwise).
- Every knob in config.json `ml.exploration.drought_floor` with core/config_guard.py checks (FATAL incoherence), derivation documented against the 8h label horizon.
- Conviction never throttled: `_probe_admission_decision` signature unchanged (no p_win/size argument) — existing pins in tests/test_probe_throttle.py must stay green.
- Full battery per commit: `.venv/bin/python -m pytest tests/ -q` · `scripts/smoke_test.py` · `scripts/assurance_check.py` · `scripts/overfit_check.py` (conscious-baseline protocol on shift) · ruff (repo scope) · pyright (shipped scope, 0 errors) · bandit · compileall.
- Run all commands synchronously in the foreground; never background pytest, never wait on Monitors.

---

### Task 1: SZ-048 registration + config block + guard checks + dashboard decode

**Files:**
- Modify: `core/codes.py` (SZ family, after `SZ_PROBE_THROTTLED = "SZ-047"`, main region ~line 126)
- Modify: `config.json` (inside the existing `ml.exploration` object, after `probe_share_window` ~line 574)
- Modify: `core/config_guard.py` (exploration checks region ~line 896)
- Modify: `scripts/build_trading_dashboard.py` (CODE_LABELS dict)
- Test: `tests/test_config_guard_probe_throttle.py` (extend)
- Regenerate: `docs/grafana/*.json` via `scripts/build_trading_dashboard.py`

**Interfaces:**
- Produces: `Code.SZ_PROBE_FLOOR = "SZ-048"`; config keys `ml.exploration.drought_floor.{enabled,drought_hours,min_spacing_hours}` (defaults: true, 8.0, 2.0); guard rules below. Task 2 consumes all three.

- [ ] **Step 1: Write the failing guard tests** — append to `tests/test_config_guard_probe_throttle.py` (follow the file's existing fixture pattern for building a config dict and collecting fatals/warnings; read the file's helpers first and reuse them):

```python
def test_drought_floor_hours_below_one_is_fatal(base_config, run_guard):
    base_config["ml"]["exploration"]["drought_floor"] = {
        "enabled": True, "drought_hours": 0.5, "min_spacing_hours": 2.0}
    fatals = run_guard(base_config)
    assert any("drought_floor.drought_hours" in f for f in fatals)


def test_drought_floor_spacing_below_half_hour_is_fatal(base_config, run_guard):
    base_config["ml"]["exploration"]["drought_floor"] = {
        "enabled": True, "drought_hours": 8.0, "min_spacing_hours": 0.1}
    fatals = run_guard(base_config)
    assert any("drought_floor.min_spacing_hours" in f for f in fatals)


def test_drought_floor_rate_exceeding_label_horizon_is_fatal(base_config, run_guard):
    # derivation: floor admits at most drought_hours/min_spacing_hours probes
    # per drought span; spacing shorter than horizon/8 would exceed the
    # <= K-per-8h-label-horizon bound the C2 verdict requires (K=4 default
    # -> spacing >= 2.0h when horizon is 8h)
    base_config["ml"]["exploration"]["drought_floor"] = {
        "enabled": True, "drought_hours": 8.0, "min_spacing_hours": 0.9}
    fatals = run_guard(base_config)
    assert any("min_spacing_hours" in f for f in fatals)


def test_drought_floor_defaults_are_coherent(base_config, run_guard):
    # the shipped defaults must produce zero fatals/warnings on this block
    fatals = run_guard(base_config)
    assert not [f for f in fatals if "drought_floor" in f]
```

If the existing file uses a different fixture idiom (e.g. builds `Config` objects and calls `check_config` capturing a report), adapt these four tests to that idiom exactly — assert the same four behaviors.

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_config_guard_probe_throttle.py -q -k drought`
Expected: FAIL (guard raises no drought_floor fatals — checks don't exist yet)

- [ ] **Step 3: Register the code** — in `core/codes.py`, directly after the `SZ_PROBE_THROTTLED` line:

```python
    SZ_PROBE_FLOOR = "SZ-048"        # F0b (2026-07-25 livelock repair): drought-
                                     # scoped floor admission - the share cap was
                                     # the binding denial AND no admissions of any
                                     # kind flowed for >= drought_hours, so one
                                     # rate-bounded probe is admitted instead of
                                     # starving the label stream (grill C2)
```

- [ ] **Step 4: Add the config block** — in `config.json` inside `ml.exploration`, after `"probe_share_window": 40,`:

```json
      "drought_floor": {
        "enabled": true,
        "drought_hours": 8.0,
        "min_spacing_hours": 2.0
      },
      "_drought_floor_doc": "F0b livelock repair (grill C2 CONFIRMED, operator decision docs/quant/2026-07-25_livelock_f0_decision.md): the share cap's window advances only on admissions, so zero flow freezes it closed forever (SZ-047xSZ-030 deadlock, 2026-07-24/25 drought). When the share cap is the BINDING denial and the ML-073 drought clock (engine-time _last_entry_admit_ts, admissions of ANY kind) shows >= drought_hours of zero admissions, one probe is admitted per min_spacing_hours, tagged SZ-048, recorded into the window. Derivation: drought_hours = the 8h label horizon; min_spacing_hours = horizon/4 -> at most 4 floor probes per horizon. Outside droughts the branch is unreachable - behavior byte-identical to P3. config_guard: drought_hours FATAL < 1.0; min_spacing_hours FATAL < 0.5; FATAL if min_spacing_hours < drought_hours/8 (rate would exceed the K-per-horizon bound).",
```

- [ ] **Step 5: Add guard checks** — in `core/config_guard.py`, in the exploration-checks region (after the existing `max_probe_share` / `probe_share_window` checks, ~line 900), following the file's `_f`/`fatal` idiom:

```python
    # F0b drought floor (grill C2): floor must stay a trickle, never a hose
    dfh = float(_f(config, "ml.exploration.drought_floor.drought_hours", 8.0))
    dfs = float(_f(config,
                   "ml.exploration.drought_floor.min_spacing_hours", 2.0))
    if dfh < 1.0:
        fatal(f"ml.exploration.drought_floor.drought_hours ({dfh}) must be "
              ">= 1.0 - a sub-hour 'drought' would fire the floor on "
              "ordinary quiet spells, not deadlocks")
    if dfs < 0.5:
        fatal(f"ml.exploration.drought_floor.min_spacing_hours ({dfs}) must "
              "be >= 0.5 - the floor is a trickle, not a stream")
    if dfs < dfh / 8.0:
        fatal(f"ml.exploration.drought_floor.min_spacing_hours ({dfs}) must "
              f"be >= drought_hours/8 ({dfh / 8.0:.2f}) - more than 8 floor "
              "probes per drought span exceeds the label-horizon bound "
              "(C2: <= K probes per 8h horizon)")
```

- [ ] **Step 6: Add the decode label** — in `scripts/build_trading_dashboard.py` CODE_LABELS, after the `"SZ-047"` entry:

```python
    "SZ-048": "SZ-048 · drought floor probe",
```

- [ ] **Step 7: Regenerate dashboards + run the affected suites**

Run: `.venv/bin/python scripts/build_trading_dashboard.py && .venv/bin/python -m pytest tests/test_config_guard_probe_throttle.py tests/test_trading_dashboard.py tests/test_glass_suite.py -q`
Expected: ALL PASS (drought guard tests now green; decode coverage green with SZ-048 labeled)

- [ ] **Step 8: Commit**

```bash
git add core/codes.py config.json core/config_guard.py scripts/build_trading_dashboard.py docs/grafana/ tests/test_config_guard_probe_throttle.py
git commit -m "feat(explore): register SZ-048 drought-floor code + config + guards

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01TgfcWLtZtVMQhbiPZCCV8h"
```

---

### Task 2: The drought-floor mechanism + wiring + persistence

**Files:**
- Modify: `main.py` — `__init__` exploration-config region (~line 780-825, where `_probe_max_share`/`_probe_share_window` are read), `_probe_admission_decision` (~line 2416-2459), new helper directly above `_probe_share_would_deny` (~line 2390)
- Modify: `core/persistence.py` — `_restore_probe_admissions_section` (~line 170-186) and the matching snapshot-write site (grep `probe_admissions` in the save path)
- Test: `tests/test_probe_throttle.py` (extend — read the file first; it has 35 tests whose harness builds a minimal bot object; reuse its builder)

**Interfaces:**
- Consumes: `Code.SZ_PROBE_FLOOR`, config keys from Task 1.
- Produces: `LiquidityBot._drought_floor_admit(now: float) -> bool` (pure predicate, no side effects); attributes `_drought_floor_enabled: bool`, `_drought_min_sec: float`, `_floor_spacing_sec: float`, `_last_floor_admit_ts: Optional[float]` (persisted). Task 3 consumes the persistence shape.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_probe_throttle.py`, reusing its existing minimal-bot builder and monkeypatch idioms (READ the existing tests first; mirror how they set `_probe_admissions`, `_probe_share_window`, `_probe_max_share`, and how they stub `_exploration_active` to force the roll True):

```python
# ---- F0b drought floor (SZ-048) ------------------------------------------

def _floor_bot(builder, *, window_probes=14, drought_sec=9 * 3600.0):
    """Bot with a FROZEN window (>= 14/40 probes) and a stale drought
    clock - the exact livelock state. builder = the file's existing
    minimal-bot factory."""
    bot = builder()
    bot._probe_share_window = 40
    bot._probe_max_share = 0.35
    bot._probe_admissions.clear()
    bot._probe_admissions.extend([True] * window_probes
                                 + [False] * (40 - window_probes))
    bot._drought_floor_enabled = True
    bot._drought_min_sec = 8 * 3600.0
    bot._floor_spacing_sec = 2 * 3600.0
    bot._last_floor_admit_ts = None
    bot._last_entry_admit_ts = 1_000_000.0
    bot._now_probe = 1_000_000.0 + drought_sec
    return bot


def test_floor_fires_only_under_drought_and_binding_cap(probe_bot_builder):
    bot = _floor_bot(probe_bot_builder)
    assert bot._probe_share_would_deny()          # cap IS binding
    assert bot._drought_floor_admit(bot._now_probe) is True


def test_floor_silent_without_drought(probe_bot_builder):
    bot = _floor_bot(probe_bot_builder, drought_sec=3600.0)  # 1h < 8h
    assert bot._drought_floor_admit(bot._now_probe) is False


def test_floor_rate_bounded_by_spacing(probe_bot_builder):
    bot = _floor_bot(probe_bot_builder)
    now = bot._now_probe
    assert bot._drought_floor_admit(now) is True
    bot._last_floor_admit_ts = now                # a floor probe just fired
    assert bot._drought_floor_admit(now + 3600.0) is False   # 1h < 2h spacing
    assert bot._drought_floor_admit(now + 7201.0) is True    # spacing elapsed


def test_floor_disabled_is_byte_identical(probe_bot_builder):
    bot = _floor_bot(probe_bot_builder)
    bot._drought_floor_enabled = False
    assert bot._drought_floor_admit(bot._now_probe) is False


def test_floor_never_fires_with_unseeded_clock(probe_bot_builder):
    bot = _floor_bot(probe_bot_builder)
    bot._last_entry_admit_ts = None
    assert bot._drought_floor_admit(bot._now_probe) is False


def test_admission_decision_admits_via_floor_with_sz048(probe_bot_builder,
                                                        monkeypatch, caplog):
    bot = _floor_bot(probe_bot_builder)
    monkeypatch.setattr(type(bot), "_exploration_active",
                        lambda self, now, asset=None, regime_label=None: True)
    admitted = bot._probe_admission_decision(bot._now_probe, "BTC")
    assert admitted is True
    # the floor admission is RECORDED into the window like any admission
    assert bot._probe_admissions[-1] is True
    assert bot._last_floor_admit_ts == bot._now_probe


def test_admission_decision_denies_sz047_when_no_drought(probe_bot_builder,
                                                         monkeypatch):
    bot = _floor_bot(probe_bot_builder, drought_sec=60.0)
    monkeypatch.setattr(type(bot), "_exploration_active",
                        lambda self, now, asset=None, regime_label=None: True)
    assert bot._probe_admission_decision(bot._now_probe, "BTC") is False


def test_floor_is_engine_time_only(probe_bot_builder, monkeypatch):
    # replay determinism: wall clock must never enter the decision
    import time as _time
    bot = _floor_bot(probe_bot_builder)
    monkeypatch.setattr(_time, "time",
                        lambda: (_ for _ in ()).throw(AssertionError(
                            "wall clock read in drought-floor path")))
    assert bot._drought_floor_admit(bot._now_probe) is True


def test_floor_state_round_trips(probe_bot_builder):
    from core.persistence import snapshot_bot_state, restore_bot_state
    bot = _floor_bot(probe_bot_builder)
    bot._last_floor_admit_ts = 1_234_567.0
    data = snapshot_bot_state(bot)
    bot2 = _floor_bot(probe_bot_builder)
    bot2._last_floor_admit_ts = None
    restore_bot_state(bot2, data)
    assert bot2._last_floor_admit_ts == 1_234_567.0
```

Adapt fixture names (`probe_bot_builder`) and the persistence entry points to what tests/test_probe_throttle.py and core/persistence.py actually export — read both files first; assert the same nine behaviors. If `_probe_admission_decision`'s SZ-047 branch calls `get_audit()`, follow the file's existing audit-stub idiom.

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_probe_throttle.py -q -k floor`
Expected: FAIL with AttributeError (`_drought_floor_admit` not defined)

- [ ] **Step 3: Implement** — in `main.py`:

(a) `__init__`, next to where `_probe_max_share`/`_probe_share_window` are read from `_ex` (the `ml.exploration` sub-dict, ~line 788-792):

```python
        _dfl = _ex.get("drought_floor", {}) or {}
        # F0b (grill C2): drought-scoped floor - see _drought_floor_admit
        self._drought_floor_enabled = bool(_dfl.get("enabled", True))
        self._drought_min_sec = max(
            float(_dfl.get("drought_hours", 8.0)), 0.0) * 3600.0
        self._floor_spacing_sec = max(
            float(_dfl.get("min_spacing_hours", 2.0)), 0.0) * 3600.0
        self._last_floor_admit_ts: Optional[float] = None
```

(b) New helper directly ABOVE `_probe_share_would_deny`:

```python
    def _drought_floor_admit(self, now: float) -> bool:
        """F0b livelock repair (grill C2 CONFIRMED): may ONE rate-bounded
        floor probe be admitted despite the share cap? True only when
        (a) the floor is enabled, (b) the ML-073 drought clock
        (_last_entry_admit_ts - engine time, set on admissions of ANY
        kind at main.py:1147, seeded W2-18) shows >= drought_hours with
        zero admissions, and (c) the previous floor admission is >=
        min_spacing_hours old. Pure predicate - no side effects; the
        caller records the admission. Unreachable outside a drought, so
        non-drought behavior is byte-identical to P3 (test-pinned).
        Engine `now` only - wall clock here would break replay
        determinism."""
        if not getattr(self, "_drought_floor_enabled", False):
            return False
        last = getattr(self, "_last_entry_admit_ts", None)
        if last is None:
            return False            # clock unseeded: cannot prove a drought
        if (now - last) < getattr(self, "_drought_min_sec", float("inf")):
            return False            # entries flowed recently: no drought
        prev = getattr(self, "_last_floor_admit_ts", None)
        if prev is not None and \
                (now - prev) < getattr(self, "_floor_spacing_sec", 0.0):
            return False            # trickle bound: one per spacing span
        return True
```

(c) In `_probe_admission_decision`, replace the body of the `if self._probe_share_would_deny():` branch so the floor is consulted FIRST (the cap is, by position, the binding denial here — `_exploration_active` already rolled True):

```python
        if self._probe_share_would_deny():
            if self._drought_floor_admit(now):
                detail = tag(
                    Code.SZ_PROBE_FLOOR,
                    f"drought floor probe {asset}: no admissions for >= "
                    f"{self._drought_min_sec / 3600.0:.1f}h with the share "
                    f"cap binding - one rate-bounded probe admitted")
                get_audit().log(
                    "exploration", Code.SZ_PROBE_FLOOR, detail,
                    {"asset": asset,
                     "drought_hours": self._drought_min_sec / 3600.0,
                     "spacing_hours": self._floor_spacing_sec / 3600.0})
                log.info("[%s] drought floor: probe admitted under SZ-048 "
                         "(share cap was binding, drought >= %.1fh)", asset,
                         self._drought_min_sec / 3600.0)
                self._last_floor_admit_ts = now
                self._record_probe_admission(True)
                return True
            detail = tag(
                Code.SZ_PROBE_THROTTLED,
                f"probe throttled {asset}: rolling share cap "
                f"({self._probe_max_share:.0%} of last "
                f"{self._probe_share_window} admissions) would be exceeded")
            get_audit().log(
                "exploration", Code.SZ_PROBE_THROTTLED, detail,
                {"asset": asset, "window": self._probe_share_window,
                 "max_share": self._probe_max_share})
            log.info("[%s] probe THROTTLED: rolling share cap (%.0f%% of "
                     "last %d admissions) - falling through as an ordinary "
                     "(conviction) entry attempt", asset,
                     self._probe_max_share * 100, self._probe_share_window)
            return False
        return True
```

CAUTION: the normal (non-floor) admission path does NOT call `_record_probe_admission` here — it is recorded at the submit sites (main.py:1147 area). The floor admission records immediately because its submit may still be vetoed downstream (min-ticket, manip, SZ-046); recording at decision time keeps the window honest about floor USE and self-bounds repeat fires. Document this asymmetry in the helper docstring if the reviewer flags it; do NOT move the normal path's recording.

(d) In `core/persistence.py`: extend `_restore_probe_admissions_section` to also restore `_last_floor_admit_ts` (float-or-None, same isolated-section error handling), and add the field beside `probe_admissions` in the snapshot-write site.

- [ ] **Step 4: Run the new tests + the WHOLE probe suite**

Run: `.venv/bin/python -m pytest tests/test_probe_throttle.py tests/test_persistence.py -q`
Expected: ALL PASS (35 pre-existing + 9 new; persistence suite green)

- [ ] **Step 5: Mutation proof (two-sided, throwaway — do not commit the mutations)**
  - Comment out the `self._drought_floor_admit(now)` branch → `test_admission_decision_admits_via_floor_with_sz048` must FAIL. Restore.
  - Hardcode `_drought_floor_admit` to return True → `test_admission_decision_denies_sz047_when_no_drought` and `test_floor_silent_without_drought` must FAIL. Restore.
  - Record both outcomes in the task report.

- [ ] **Step 6: Commit**

```bash
git add main.py core/persistence.py tests/test_probe_throttle.py
git commit -m "feat(explore): SZ-048 drought-scoped probe floor breaks the entry livelock

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01TgfcWLtZtVMQhbiPZCCV8h"
```

---

### Task 3: Snapshot semantics — pre-P3 restore documented + pinned

**Files:**
- Modify: `core/persistence.py` (docstring of `_restore_probe_admissions_section` only)
- Modify: `README.md` (the exploration/probe section — grep `probe` for the right anchor)
- Test: `tests/test_probe_throttle.py` (extend)

**Interfaces:**
- Consumes: Task 2's persistence shape. Produces: nothing new — this task pins CHOSEN semantics.

Chosen semantics (T1.3 decision): a snapshot WITHOUT the probe-admissions section (pre-P3) restores to an EMPTY window — up to 14 unthrottled probes then re-cap. This is ACCEPTED, not closed: the window refills within 14 admissions, the corpus decay + asset taper + manip gate still bound each probe, and with the Task-2 floor in place the empty-window shortcut is no longer the only road out of a drought (so nobody is tempted to "restart to unstick"). Document, don't engineer.

- [ ] **Step 1: Write the failing test**

```python
def test_pre_p3_snapshot_restores_empty_window_documented(probe_bot_builder):
    """CHOSEN semantics (plan Task 3): a snapshot lacking the
    probe_admissions section restores an EMPTY window (14 free probes,
    then the cap re-binds). Deliberate - see persistence docstring."""
    from core.persistence import restore_bot_state
    bot = probe_bot_builder()
    bot._probe_admissions.extend([True] * 14)
    restore_bot_state(bot, {})            # pre-P3 snapshot: no section
    assert list(bot._probe_admissions) == []
    assert bot._last_floor_admit_ts is None
```

Adapt the restore entry point/arg shape to the real API (read `_restore_probe_admissions_section`'s caller). If restore-from-empty currently PRESERVES the deque instead of clearing it, that is the actual current semantics — then pin THAT (assert the deque is preserved) and update the docstring/README wording to match reality. The deliverable is a pinned, documented truth, whichever it is.

- [ ] **Step 2: Run to verify it fails or reveals current truth**

Run: `.venv/bin/python -m pytest tests/test_probe_throttle.py -q -k pre_p3`
Expected: FAIL (test new) — then adjust per the observed semantics as instructed above.

- [ ] **Step 3: Document** — extend the `_restore_probe_admissions_section` docstring with the chosen semantics (3-4 lines, citing this plan + the F0 decision memo), and add two sentences to README.md's probe/exploration paragraph: old snapshots restore an empty probe window by design; the drought floor (SZ-048) is the sanctioned road out of a freeze.

- [ ] **Step 4: Run + commit**

Run: `.venv/bin/python -m pytest tests/test_probe_throttle.py -q`
Expected: ALL PASS

```bash
git add core/persistence.py README.md tests/test_probe_throttle.py
git commit -m "docs(explore): pin pre-P3 snapshot window semantics

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01TgfcWLtZtVMQhbiPZCCV8h"
```

---

### Task 4: Audit hygiene — test-harness SZ-047 events out of production audit

**Files:**
- Investigate: `tests/test_probe_throttle.py` + any test calling `_probe_admission_decision` end-to-end (grep `SZ_PROBE_THROTTLED\|_probe_admission_decision` in tests/)
- Modify: the offending test fixture(s) and/or `tests/conftest.py`
- Test: extension of the offending test file

**Interfaces:** none — fixture isolation only. Production code untouched (verify with `git diff --stat` at commit: tests/ only).

Background: `outputs/audit.jsonl` contains an SZ-047 event stamped `{"window": 10, "max_share": 0.3}` — values no production config ever had; a test exercised the real `get_audit()` singleton pointed at the production path.

- [ ] **Step 1: Reproduce** — locate the writer:

Run: `.venv/bin/python -m pytest tests/ -q -k "probe" 2>/dev/null; rtk grep -n '"window": 10' outputs/audit.jsonl | head -2`
Then grep tests for a `window.*10\|0\.3` probe configuration and identify which test lacks audit redirection (compare against how other audit-touching tests redirect — grep `get_audit\|audit_path\|AuditTrail(` in tests/conftest.py and tests/test_audit*.py for the sanctioned idiom).

- [ ] **Step 2: Write the failing guard test** — in the offending file:

```python
def test_probe_tests_never_touch_production_audit(tmp_path):
    """The audit singleton used by probe tests must point inside pytest's
    tmp tree, never the repo's outputs/ (a test SZ-047 event with
    window=10/0.3 polluted the production trail - plan Task 4)."""
    from core.audit import get_audit
    p = str(getattr(get_audit(), "path", ""))
    assert "outputs" not in p or "tmp" in p or "pytest" in p
```

Adapt the attribute (`path`) to the real AuditTrail API (read core/audit.py first) — assert the singleton's destination is NOT the repo `outputs/` during this test module's run.

- [ ] **Step 3: Fix** — apply the sanctioned redirection idiom (autouse fixture in the offending module or conftest) so every probe test's audit writes under `tmp_path`. Do NOT change production code.

- [ ] **Step 4: Verify + clean the trail + commit**

Run: `.venv/bin/python -m pytest tests/test_probe_throttle.py -q` → ALL PASS; confirm `rtk grep -c '"window": 10' outputs/audit.jsonl` gains no NEW entries after a full probe-suite run (the historical entry stays — the chain is append-only and hash-linked; document it as a known benign artifact in the task report instead of editing history).

```bash
git add tests/
git commit -m "test(audit): isolate probe-suite audit writes from production trail

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01TgfcWLtZtVMQhbiPZCCV8h"
```

---

### Task 5: Full battery + telemetry check + push

**Files:** none new — verification task.

- [ ] **Step 1: Full battery, foreground, in order**

```bash
.venv/bin/python -m pytest tests/ -q
.venv/bin/python scripts/smoke_test.py
.venv/bin/python scripts/assurance_check.py
.venv/bin/python scripts/overfit_check.py
.venv/bin/python -m ruff check core data execution ml risk regime strategies sentiment api main.py runner.py tests scripts/quant_trials.py scripts/overfit_check.py
/root/.local/bin/pyright core data execution ml risk regime strategies sentiment api main.py runner.py
.venv/bin/python -m bandit -c pyproject.toml -r . -x ./.venv,./tests
.venv/bin/python -m compileall -q . -x '.venv'
```

Expected: pytest all pass · smoke 219 · assurance 47 · ruff clean · pyright 0 · bandit clean · compileall OK. Overfit: compare against the current conscious baseline in docs/quant/2026-07-24_of3_pbo_data_shift.md — if the pass/fail split moved, STOP and run the inertness experiment (scratch worktree at the pre-plan commit × current corpus) before re-baselining; this plan's diff touches no ml/ code, so any shift must prove data-driven.

- [ ] **Step 2: Quant trials sanity** — the diff touches the exploration path, which feeds sim flows:

Run: `.venv/bin/python -m pytest tests/test_quant_trials.py tests/test_long_trials.py -q`
Expected: PASS (G1–G5 + G-L pins unchanged; if a pin moves, STOP — that is a behavior change outside the byte-identity promise and must be diagnosed, never re-baselined silently)

- [ ] **Step 3: Push**

```bash
git push -u origin claude/remote-control-e3h815
```

(Retry per repo git rules on network failure. Do NOT fast-forward main — that happens after the whole-phase review.)

---

## Self-review notes (author)

- Spec coverage: T1.2→Tasks 1-2, T1.3→Task 3, T1.4→Task 4, battery→Task 5. The eight C2 conditions: drought-of-any-kind clock (Task 2b via `_last_entry_admit_ts`), binding-denial-only (floor consulted inside the `would_deny` branch after the epsilon roll), span/count-engine-time (Task 2 determinism test), config+guard derivation (Task 1), new SZ code recorded into window (Task 2c), byte-identical non-drought (floor branch unreachable without drought + disabled test + full pre-existing suite), conviction untouched (signature unchanged; existing pins), existing probe bounds intact (floor sits AFTER `_exploration_active`, and its admission still passes the downstream min-ticket/manip/SZ-046 stack at submit).
- Placeholders: fixture names (`probe_bot_builder`, restore entry points, audit path attribute) are deliberately marked ADAPT-to-file — the implementer must read the target files first (session standing rule); each such step names the exact file and the behavior to assert, which is the requirement.
- Type consistency: `_drought_floor_admit(now: float) -> bool` used identically in Tasks 2-3; config keys identical across Tasks 1-2.
