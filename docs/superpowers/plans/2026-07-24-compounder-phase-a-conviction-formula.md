# Compounder Phase A — Conviction Formula Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the deterministic, registered Conviction Formula (spec §2 of
`docs/superpowers/specs/2026-07-24-compounder-framework-design.md`) — four
conjunctive admission terms + a cadence governor — wired into the 5m entry
pipeline in **report mode** (byte-identical behavior, dispositions logged),
with the enforce flip left as a conscious operator decision.

**Architecture:** One new pure module `risk/conviction.py` (formula +
governor, fully unit-testable), a new CV-* code family in `core/codes.py`,
a `conviction` config block guarded by `core/config_guard.py`, and ONE
engine seam — `LiquidityBot._conviction_disposition(...)` — called at the
single point where a pretrade-approved non-probe entry is about to become
an order. Status exposed via `runner.build_status`.

**Tech Stack:** Python stdlib only (dataclasses, collections.deque). No new
dependencies. Tests with pytest, matching existing suite conventions.

## Global Constraints

Copied from the spec (§0) — every task's requirements implicitly include
these:

- `system.dry_run` defaults true; `force_dry` one-way; Kraken sole venue;
  withdrawal deny-list untouchable; entries limit-only; exits ALWAYS
  allowed. This program touches NONE of those paths.
- Every disposition carries a REGISTERED code (`core/codes.py`) — never a
  bare string. New codes are append-only, never renumbered.
- No fitted-looking literals in decision paths: every threshold lands in
  `config.json` with a `_doc` derivation comment and
  `core/config_guard.py` coherence checks (FATAL for incoherent combos).
- **Report mode is the shipped default.** With `mode: "report"` the entry
  pipeline's behavior is BYTE-IDENTICAL to pre-Phase-A: no entry is ever
  blocked by the formula. Enforcement (`mode: "enforce"`) exists in code
  and tests but the config flip is a conscious operator decision after
  report telemetry review + green quant-trials at 200×1200. Never widen a
  gate; never tune to a backtest peak (OF-4 / T6 precedent).
- Probes (`explored=True`) are EXEMPT from the formula — they are the
  exploration channel; the formula governs conviction flow only.
- Public interfaces stay stable: extend with defaults; `build_status`
  keys are load-bearing — extend, don't break. No Grafana board changes
  in this phase (boards stay at four; no gc_pusher metrics added).
- Full battery green before the final push: `python -m pytest tests/ -q`
  · `python scripts/smoke_test.py` · `python scripts/assurance_check.py`
  · `python scripts/overfit_check.py` · ruff (repo scope) · pyright
  (shipped scope at ZERO errors) · bandit · compileall. Use
  `.venv/bin/python`. New behavior gets tests in the same commit.
- Commit trailer (exact, both lines, every commit):
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01TgfcWLtZtVMQhbiPZCCV8h`
  after `git config user.email noreply@anthropic.com && git config
  user.name Claude`.

**Controller notes (not SDD tasks):** the Phase B research program
(fintech-quant-researcher + financial-analyst → one referenced doc in
`docs/research/`) is dispatched by the controller in parallel with this
plan's execution. Phase B and C plans are authored only after that doc
lands (spec: research freezes Phase B's details). Task #104's adoptions
fold into the Phase B plan.

**Baseline facts** (verified against the tree at `18c6ead` — implementers
trust these, reviewers may spot-check):

- Gate-stack agreement measure: `strategies/signal_gates.py:225` computes
  `confidence = sum(gates_passed.values()) / len(gates_passed)` — the
  pass-fraction IS the stack's own agreement arithmetic. Signals expose
  `gates_passed: dict` (may be `{}`); `informed_flow` signals can be
  `all_confirmed=True` with some gate values False.
- Pretrade decision fields: `execution/pretrade.py:61-62` —
  `est_cost_bps` / `est_edge_bps` (measured round-trip cost stack);
  existing any-entry bar `min_edge_cost_ratio = 1.3`
  (`execution/pretrade.py:76`, config `pretrade.min_edge_cost_ratio`).
- T4 regime evidence: pure helper `_regime_under_coverage_floor(
  regime_live, regime_floor_live)` at `main.py:248`;
  `self._regime_floor_live` read at `main.py:723` (config
  `ml.exploration.corpus_decay.regime_floor_live`, currently 60; 0
  disables); O(1) counter `ml/history.py:327`
  `regime_live_count(regime_label)`; `REGIME_LABELS` imported at
  `main.py:86`.
- Entry pipeline seam: pretrade veto `continue` at `main.py:2672-2676`;
  the conviction seam goes immediately after it, BEFORE
  `position_id = pid` (`main.py:2680`) so all three entry paths
  (algo/ladder/single) sit behind it.
- Audit pattern: `get_audit().log(source, code, tag(code, detail),
  payload)` with `tag()` bumping `core/code_stats` (`main.py:2145-2153`
  is the model).
- Stub-bot test pattern: entry-path helpers are written "self-healing
  getattr" so tests exercise them off `LiquidityBot.__new__(LiquidityBot)`
  (see `_record_probe_admission` docstring, `main.py:2102`).
- Status assembly: `runner.py:425 build_status`; `"monitor"` entry at
  `runner.py:551` is the neighborhood for the new `"conviction"` key.

---

### Task 1: CV code family + ConvictionFormula core (pure evaluate)

**Files:**
- Modify: `core/codes.py` (prefix map docstring + enum entries after the
  CG section, `core/codes.py:254-260`)
- Create: `risk/conviction.py`
- Test: `tests/test_conviction.py`

**Interfaces:**
- Consumes: `core.codes.Code` (enum), nothing else.
- Produces: `Code.CV_ADMIT/CV_AGREEMENT_LOW/CV_EV_MULTIPLE_LOW/
  CV_REGIME_UNKNOWN/CV_CONTEXT_MISALIGNED/CV_CADENCE_HIGH/CV_CADENCE_LOW`;
  `risk.conviction.ConvictionDecision` (frozen dataclass: `admitted: bool`,
  `code: Code`, `terms: dict`); `risk.conviction.ConvictionFormula` with
  `__init__(cfg: dict)`, properties `enabled: bool`, `mode: str`,
  `enforce: bool`, and
  `evaluate(*, agreement: float, est_edge_bps: float, est_cost_bps: float,
  regime_known: bool, context_aligned: Optional[bool] = None)
  -> ConvictionDecision`. Tasks 2/4 rely on these exact names.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_conviction.py`:

```python
"""tests/test_conviction.py — Phase A Conviction Formula (Compounder):
the pure admission rule's unit contract. Four conjunctive terms, fixed
evaluation order, first failure names the registered CV-* code, no
fitted weights anywhere."""
from core.codes import Code
from risk.conviction import ConvictionFormula


def _f(**over):
    cfg = {"enabled": True, "mode": "report", "agreement_floor": 0.75,
           "ev_cost_mult": 2.0, "share_window": 8, "share_min_n": 4,
           "share_lo": 0.25, "share_hi": 0.75}
    cfg.update(over)
    return ConvictionFormula(cfg)


# a clean all-terms-pass input set reused across tests
PASS = dict(agreement=1.0, est_edge_bps=100.0, est_cost_bps=20.0,
            regime_known=True)


def test_cv_codes_registered_and_stable():
    assert Code.CV_ADMIT.value == "CV-000"
    assert Code.CV_AGREEMENT_LOW.value == "CV-010"
    assert Code.CV_EV_MULTIPLE_LOW.value == "CV-020"
    assert Code.CV_REGIME_UNKNOWN.value == "CV-030"
    assert Code.CV_CONTEXT_MISALIGNED.value == "CV-040"
    assert Code.CV_CADENCE_HIGH.value == "CV-050"
    assert Code.CV_CADENCE_LOW.value == "CV-051"


def test_all_terms_pass_admits_cv000():
    d = _f().evaluate(**PASS)
    assert d.admitted and d.code == Code.CV_ADMIT


def test_agreement_below_floor_denies():
    d = _f().evaluate(**{**PASS, "agreement": 0.74})
    assert not d.admitted and d.code == Code.CV_AGREEMENT_LOW


def test_agreement_at_floor_admits():
    assert _f().evaluate(**{**PASS, "agreement": 0.75}).admitted


def test_ev_below_multiple_denies():
    # cost 20 x mult 2.0 -> 40bps edge required; 39.9 fails
    d = _f().evaluate(**{**PASS, "est_edge_bps": 39.9})
    assert not d.admitted and d.code == Code.CV_EV_MULTIPLE_LOW


def test_ev_at_multiple_admits():
    assert _f().evaluate(**{**PASS, "est_edge_bps": 40.0}).admitted


def test_regime_unknown_denies():
    d = _f().evaluate(**{**PASS, "regime_known": False})
    assert not d.admitted and d.code == Code.CV_REGIME_UNKNOWN


def test_context_none_is_not_applicable_and_passes():
    # 5m book: no context engine yet — None means the term does not apply
    assert _f().evaluate(**PASS, context_aligned=None).admitted


def test_context_misaligned_denies_cv040():
    # long-book term (Phase C wires the call site); the formula itself
    # must already honor it so Phase C is a parameter, not a code change
    d = _f().evaluate(**PASS, context_aligned=False)
    assert not d.admitted and d.code == Code.CV_CONTEXT_MISALIGNED


def test_term_order_first_failure_names_the_code():
    d = _f().evaluate(agreement=0.0, est_edge_bps=0.0, est_cost_bps=20.0,
                      regime_known=False, context_aligned=False)
    assert d.code == Code.CV_AGREEMENT_LOW


def test_evaluate_is_pure_and_deterministic():
    f = _f()
    assert f.evaluate(**PASS) == f.evaluate(**PASS)


def test_decision_terms_carry_the_evidence():
    t = _f().evaluate(**PASS).terms
    assert t["agreement"] == 1.0 and t["agreement_floor"] == 0.75
    assert t["est_edge_bps"] == 100.0 and t["est_cost_bps"] == 20.0
    assert t["ev_cost_mult"] == 2.0 and t["regime_known"] is True


def test_enforce_only_when_enabled_and_mode_enforce():
    assert not _f().enforce                          # report mode
    assert not _f(mode="enforce", enabled=False).enforce
    assert _f(mode="enforce").enforce
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_conviction.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'risk.conviction'`
(and `AttributeError: CV_ADMIT` once the module exists but codes don't).

- [ ] **Step 3: Register the CV code family**

In `core/codes.py`, add to the prefix map docstring (after the `HG` line,
keeping column alignment):

```
  CV  risk.conviction (Compounder Phase A conviction formula)
```

Append to the `Code` enum AFTER the CG section (`CG_SESSION_START`,
line ~260) and before `def tag`:

```python
    # ---- conviction formula (CV) — risk/conviction.py (Compounder A) ----
    CV_ADMIT = "CV-000"              # all terms agree: conviction admitted
    CV_AGREEMENT_LOW = "CV-010"      # gate-stack agreement below floor
    CV_EV_MULTIPLE_LOW = "CV-020"    # edge fails ev_cost_mult x the pretrade
                                     # gate's MEASURED round-trip cost stack
    CV_REGIME_UNKNOWN = "CV-030"     # current regime below the T4 live-label
                                     # coverage floor (or unmapped): no
                                     # evidence, no conviction
    CV_CONTEXT_MISALIGNED = "CV-040" # long-book context term: emitted by the
                                     # formula; no engine call site passes
                                     # context_aligned until the context
                                     # engine (Phase B) + long book (Phase C)
    CV_CADENCE_HIGH = "CV-050"       # governor: admit share above share_hi -
                                     # the formula has gone vacuous (always-on)
    CV_CADENCE_LOW = "CV-051"        # governor: admit share below share_lo -
                                     # the formula is starving conviction flow
```

- [ ] **Step 4: Write `risk/conviction.py`**

```python
"""risk/conviction.py — Phase A Conviction Formula (Compounder program,
docs/superpowers/specs/2026-07-24-compounder-framework-design.md §2).

Deterministic, registered admission rule for CONVICTION entries (the
non-probe channel). A conviction entry is admitted only when ALL terms
agree — conjunctive, no fitted weights, no blended scores; every
disposition is a registered CV-* code (core/codes.py).

Terms (fixed evaluation order; the FIRST failing term names the code):
  1 agreement    — the gate stack's own agreement measure (pass-fraction
                   of gates_passed, the same arithmetic
                   strategies/signal_gates.py uses for its confidence)
                   at/above conviction.agreement_floor
  2 ev multiple  — est_edge_bps >= ev_cost_mult x est_cost_bps, where
                   est_* are the pretrade gate's MEASURED round-trip
                   numbers for THIS entry. config_guard pins
                   ev_cost_mult >= pretrade.min_edge_cost_ratio (a
                   conviction bar under the pretrade bar is vacuous).
  3 regime known — the current regime's live-label count at/above the T4
                   coverage floor (engine-side: main.
                   _regime_under_coverage_floor over
                   history.regime_live_count). No evidence, no conviction.
  4 context      — long-book only: context_aligned=None means
                   not-applicable (the 5m book today) and auto-passes;
                   False denies with CV-040. Phase B/C wire real values.

MODES — report (shipped default) vs enforce:
  report:  every conviction attempt is evaluated and audit-logged;
           entry behavior stays BYTE-IDENTICAL (nothing is blocked).
           This is the honest threshold-derivation period: floors and
           multiples are re-derived from REPORTED dispositions.
  enforce: a denied conviction entry is skipped (registered code). The
           config flip is a CONSCIOUS operator decision after report
           telemetry review + green quant-trials adjudication at
           200x1200 — never widened to make CI pass (OF-4 / T6 law).

Cadence governor: mirror of the P3 probe throttle's rolling window —
the admit share of the last share_window conviction EVALUATIONS (global
+ per-regime). Outside [share_lo, share_hi] with >= share_min_n samples
the formula has silently become always-on/always-off: that raises a
CV-050/051 alarm on the state TRANSITION (audit + status). It never
auto-tunes a threshold. Windows are process-local, not persisted: a
restart judges nothing until share_min_n fresh samples accrue —
silence, never a false alarm, is the failure mode of a reset window.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional, Tuple

from core.codes import Code


@dataclass(frozen=True)
class ConvictionDecision:
    admitted: bool
    code: Code
    terms: Dict[str, Any]


class ConvictionFormula:
    def __init__(self, cfg: dict):
        cfg = cfg or {}
        self.enabled = bool(cfg.get("enabled", True))
        self.mode = str(cfg.get("mode", "report"))
        self.agreement_floor = float(cfg.get("agreement_floor", 0.75))
        self.ev_cost_mult = float(cfg.get("ev_cost_mult", 2.0))
        self.share_window = max(int(cfg.get("share_window", 40)), 1)
        self.share_min_n = max(int(cfg.get("share_min_n", 20)), 1)
        self.share_lo = float(cfg.get("share_lo", 0.10))
        self.share_hi = float(cfg.get("share_hi", 0.90))
        self._admits: Deque[bool] = deque(maxlen=self.share_window)
        self._regime_admits: Dict[str, Deque[bool]] = {}
        self._alarm_state: Dict[str, str] = {}
        self._evaluated = 0
        self._admitted = 0
        self._denials: Dict[str, int] = {}

    @property
    def enforce(self) -> bool:
        return self.enabled and self.mode == "enforce"

    def evaluate(self, *, agreement: float, est_edge_bps: float,
                 est_cost_bps: float, regime_known: bool,
                 context_aligned: Optional[bool] = None
                 ) -> ConvictionDecision:
        """Pure and deterministic: same inputs, same decision. The terms
        dict carries the full evidence (values + thresholds) so the audit
        payload explains every disposition without re-derivation."""
        terms: Dict[str, Any] = {
            "agreement": round(float(agreement), 4),
            "agreement_floor": self.agreement_floor,
            "est_edge_bps": round(float(est_edge_bps), 2),
            "est_cost_bps": round(float(est_cost_bps), 2),
            "ev_cost_mult": self.ev_cost_mult,
            "regime_known": bool(regime_known),
            "context_aligned": context_aligned,
        }
        if float(agreement) < self.agreement_floor:
            return ConvictionDecision(False, Code.CV_AGREEMENT_LOW, terms)
        if float(est_edge_bps) < self.ev_cost_mult * float(est_cost_bps):
            return ConvictionDecision(False, Code.CV_EV_MULTIPLE_LOW, terms)
        if not regime_known:
            return ConvictionDecision(False, Code.CV_REGIME_UNKNOWN, terms)
        if context_aligned is False:
            return ConvictionDecision(False, Code.CV_CONTEXT_MISALIGNED,
                                      terms)
        return ConvictionDecision(True, Code.CV_ADMIT, terms)
```

(The governor methods — `note`, `cadence_alarms`, `status` — are Task 2;
this task ships evaluate + the dataclass only.)

- [ ] **Step 5: Run the Task 1 tests**

Run: `.venv/bin/python -m pytest tests/test_conviction.py -q`
Expected: PASS (13 tests).

- [ ] **Step 6: Sanity — no ripple**

Run: `.venv/bin/python -m pytest tests/test_import_integrity.py -q`
Expected: PASS (new module imports in isolation).

- [ ] **Step 7: Commit**

```bash
git add core/codes.py risk/conviction.py tests/test_conviction.py
git commit -m "feat: Compounder Phase A — conviction formula core + CV code family"
```
(with the trailer lines from Global Constraints)

---

### Task 2: Cadence governor (note / cadence_alarms / status)

**Files:**
- Modify: `risk/conviction.py` (append methods to `ConvictionFormula`)
- Test: `tests/test_conviction.py` (append)

**Interfaces:**
- Consumes: Task 1's `ConvictionFormula` / `ConvictionDecision`.
- Produces (Task 4 relies on these exact names):
  `note(decision: ConvictionDecision, regime_label: str) -> None`;
  `cadence_alarms() -> List[Tuple[Code, str]]` (transition-edge only);
  `status() -> dict` with keys `enabled, mode, evaluated, admitted,
  denials, share, n, by_regime, alarm` (all JSON-serializable).

- [ ] **Step 1: Write the failing tests** (append to
  `tests/test_conviction.py`)

```python
# ---- Task 2: cadence governor ---------------------------------------

def test_governor_counts_and_status():
    f = _f()
    for _ in range(3):
        f.note(f.evaluate(**PASS), "range")
    f.note(f.evaluate(**{**PASS, "agreement": 0.0}), "trend_up")
    st = f.status()
    assert st["evaluated"] == 4 and st["admitted"] == 3
    assert st["denials"] == {"CV-010": 1}
    assert st["share"] == 0.75 and st["n"] == 4
    assert st["by_regime"]["range"] == {"share": 1.0, "n": 3}
    assert st["by_regime"]["trend_up"] == {"share": 0.0, "n": 1}


def test_cadence_alarm_suppressed_below_min_n():
    f = _f()                                  # share_min_n 4
    for _ in range(3):
        f.note(f.evaluate(**PASS), "range")
    assert f.cadence_alarms() == []


def test_cadence_alarm_high_fires_on_transition_only():
    f = _f()                                  # share_hi 0.75, window 8
    for _ in range(8):
        f.note(f.evaluate(**PASS), "range")
    alarms = f.cadence_alarms()
    assert any(c == Code.CV_CADENCE_HIGH for c, _ in alarms)
    assert f.cadence_alarms() == []           # steady state: no re-alarm
    assert f.status()["alarm"] == "high"


def test_cadence_alarm_low():
    f = _f()
    deny = {**PASS, "agreement": 0.0}
    for _ in range(8):
        f.note(f.evaluate(**deny), "range")
    assert any(c == Code.CV_CADENCE_LOW for c, _ in f.cadence_alarms())


def test_share_within_band_no_alarm():
    f = _f()                                  # band [0.25, 0.75]
    for i in range(8):
        d = f.evaluate(**(PASS if i % 2 else
                          {**PASS, "agreement": 0.0}))
        f.note(d, "range")
    assert f.cadence_alarms() == []
    assert f.status()["alarm"] == "ok"


def test_status_is_json_serializable():
    import json
    f = _f()
    f.note(f.evaluate(**PASS), "range")
    json.dumps(f.status())                    # raises on non-serializable
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_conviction.py -q`
Expected: FAIL — `AttributeError: ... has no attribute 'note'`.

- [ ] **Step 3: Implement the governor** (append inside
  `ConvictionFormula`)

```python
    # ---- cadence governor (mirror of the P3 probe-share window) -----

    def note(self, decision: ConvictionDecision, regime_label: str) -> None:
        """Feed one conviction EVALUATION (admit or deny) into the rolling
        cadence windows. Evaluations, not orders: the governor watches the
        FORMULA's selectivity, which exists in report mode too."""
        self._evaluated += 1
        if decision.admitted:
            self._admitted += 1
        else:
            self._denials[decision.code.value] = \
                self._denials.get(decision.code.value, 0) + 1
        self._admits.append(decision.admitted)
        d = self._regime_admits.get(regime_label)
        if d is None:
            d = deque(maxlen=self.share_window)
            self._regime_admits[regime_label] = d
        d.append(decision.admitted)

    @staticmethod
    def _share(d: Deque[bool]) -> float:
        return (sum(1 for a in d if a) / len(d)) if d else 0.0

    def cadence_alarms(self) -> List[Tuple[Code, str]]:
        """Transition-edge alarms only (state CHANGES, never per-cycle
        spam): for the global window and each regime window holding >=
        share_min_n samples, an admit share outside [share_lo, share_hi]
        raises CV-050/051 once, until the state changes again. The
        governor never auto-tunes a threshold — thresholds move only by
        conscious re-derivation (overfit law)."""
        out: List[Tuple[Code, str]] = []
        windows = [("all", self._admits)] + sorted(
            self._regime_admits.items())
        for key, d in windows:
            if len(d) < self.share_min_n:
                continue
            share = self._share(d)
            state = "high" if share > self.share_hi else \
                    "low" if share < self.share_lo else "ok"
            if state != self._alarm_state.get(key, "ok") and state != "ok":
                code = Code.CV_CADENCE_HIGH if state == "high" \
                    else Code.CV_CADENCE_LOW
                out.append((code,
                            f"conviction admit share {share:.0%} ({key}, "
                            f"n={len(d)}) outside [{self.share_lo:.0%}, "
                            f"{self.share_hi:.0%}]"))
            self._alarm_state[key] = state
        return out

    def status(self) -> dict:
        return {
            "enabled": self.enabled, "mode": self.mode,
            "evaluated": self._evaluated, "admitted": self._admitted,
            "denials": dict(self._denials),
            "share": round(self._share(self._admits), 3),
            "n": len(self._admits),
            "by_regime": {k: {"share": round(self._share(d), 3),
                              "n": len(d)}
                          for k, d in sorted(self._regime_admits.items())},
            "alarm": self._alarm_state.get("all", "ok"),
        }
```

- [ ] **Step 4: Run the whole file**

Run: `.venv/bin/python -m pytest tests/test_conviction.py -q`
Expected: PASS (19 tests).

- [ ] **Step 5: Commit**

```bash
git add risk/conviction.py tests/test_conviction.py
git commit -m "feat: conviction cadence governor — rolling admit-share windows + CV-050/051 transition alarms"
```

---

### Task 3: config block + config_guard coherence checks

**Files:**
- Modify: `config.json` (new top-level `"conviction"` block, placed
  directly after the `"position_sizer"` block)
- Modify: `core/config_guard.py` (new `_conviction_checks` helper +
  `extend` call inside `validate()` immediately before its return)
- Test: `tests/test_config_guard_conviction.py`

**Interfaces:**
- Consumes: `core.config_guard.validate(config) -> list[(severity, msg)]`
  and its `_f(cfg, path, default)` accessor (both exist).
- Produces: the `conviction` config block Task 4's engine init reads via
  `config.get("conviction", {})`. Every FATAL message contains the word
  `conviction` (tests filter on it).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_config_guard_conviction.py`:

```python
"""tests/test_config_guard_conviction.py — Phase A conviction block
coherence: the guard refuses configs where the formula would be vacuous
or self-contradictory (Compounder spec §2/§6)."""
from core.config_guard import validate


def _cfg(**conv):
    base = {"conviction": {"enabled": True, "mode": "report",
                           "agreement_floor": 0.75, "ev_cost_mult": 2.0,
                           "share_window": 40, "share_min_n": 20,
                           "share_lo": 0.1, "share_hi": 0.9},
            "pretrade": {"min_edge_cost_ratio": 1.3}}
    base["conviction"].update(conv)
    return base


def _fatals(cfg):
    return [m for s, m in validate(cfg)
            if s == "FATAL" and "conviction" in m]


def test_default_block_clean():
    assert _fatals(_cfg()) == []


def test_absent_block_clean():
    # module defaults apply; the guard only judges a present block
    assert _fatals({"pretrade": {"min_edge_cost_ratio": 1.3}}) == []


def test_bad_mode_fatal():
    assert _fatals(_cfg(mode="shadow"))


def test_agreement_floor_out_of_range_fatal():
    assert _fatals(_cfg(agreement_floor=1.5))
    assert _fatals(_cfg(agreement_floor=-0.1))


def test_ev_mult_below_pretrade_bar_fatal():
    # a conviction bar under the any-entry pretrade bar is vacuous
    assert _fatals(_cfg(ev_cost_mult=1.2))


def test_share_band_incoherent_fatal():
    assert _fatals(_cfg(share_lo=0.9, share_hi=0.1))
    assert _fatals(_cfg(share_lo=-0.1))
    assert _fatals(_cfg(share_hi=1.1))


def test_window_min_n_incoherent_fatal():
    assert _fatals(_cfg(share_window=10, share_min_n=20))
    assert _fatals(_cfg(share_window=0))
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_config_guard_conviction.py -q`
Expected: FAIL — the incoherent configs produce no conviction FATALs yet
(`test_bad_mode_fatal` and later asserts fail on empty lists).

- [ ] **Step 3: Add the guard helper**

In `core/config_guard.py`, add module-level (near the other check
helpers, after `_f`):

```python
def _conviction_checks(config: dict) -> list:
    """Compounder Phase A conviction block coherence (spec §2/§6):
    FATAL = the formula would be vacuous or self-contradictory. An
    absent block is clean — risk/conviction.py module defaults apply."""
    out: list = []
    conv = _f(config, "conviction")
    if not isinstance(conv, dict) or not conv:
        return out
    mode = str(conv.get("mode", "report"))
    if mode not in ("report", "enforce"):
        out.append(("FATAL", f"conviction.mode '{mode}' must be "
                    "'report' or 'enforce'"))
    floor = float(conv.get("agreement_floor", 0.75))
    if not 0.0 <= floor <= 1.0:
        out.append(("FATAL", f"conviction.agreement_floor {floor} "
                    "outside [0, 1]"))
    mult = float(conv.get("ev_cost_mult", 2.0))
    base = float(_f(config, "pretrade.min_edge_cost_ratio", 1.3))
    if mult < base:
        out.append(("FATAL", f"conviction.ev_cost_mult {mult} below "
                    f"pretrade.min_edge_cost_ratio {base} — a conviction "
                    "bar under the pretrade bar is vacuous"))
    lo = float(conv.get("share_lo", 0.1))
    hi = float(conv.get("share_hi", 0.9))
    if not (0.0 <= lo < hi <= 1.0):
        out.append(("FATAL", f"conviction share band [{lo}, {hi}] must "
                    "satisfy 0 <= lo < hi <= 1"))
    window = int(conv.get("share_window", 40))
    min_n = int(conv.get("share_min_n", 20))
    if window < 1 or not 1 <= min_n <= window:
        out.append(("FATAL", f"conviction share_window {window} / "
                    f"share_min_n {min_n} incoherent (need window >= 1, "
                    "1 <= min_n <= window)"))
    return out
```

Inside `validate()`, immediately before its final `return`, add:

```python
    issues.extend(_conviction_checks(config))
```

(match the local result-list variable name used in `validate()` — if it
is not `issues`, use the actual name; the extend goes right before the
return either way).

- [ ] **Step 4: Add the config block**

In `config.json`, directly after the `"position_sizer"` block's closing
brace, insert:

```json
"conviction": {
  "_doc": "Compounder Phase A conviction formula (risk/conviction.py, spec docs/superpowers/specs/2026-07-24-compounder-framework-design.md §2): deterministic admission for CONVICTION (non-probe) entries — all terms must agree, no fitted weights, every disposition a registered CV-* code. mode=report (shipped default) logs dispositions with BYTE-IDENTICAL entry behavior — the threshold-derivation period. mode=enforce skips denied conviction entries; the flip is a conscious operator decision after report telemetry review + green quant-trials at 200x1200 (never widen, never tune to a backtest peak).",
  "enabled": true,
  "mode": "report",
  "agreement_floor": 0.75,
  "_agreement_floor_doc": "gate-stack agreement = pass-fraction of gates_passed (the same arithmetic strategies/signal_gates.py:225 uses for its confidence). 0.75 = at least 3/4 of the evaluated stack agrees. Derivation: report-period starting default; re-derive from the reported agreement distribution before any enforce flip.",
  "ev_cost_mult": 2.0,
  "_ev_cost_mult_doc": "conviction entries must clear ev_cost_mult x the pretrade gate's MEASURED round-trip cost stack (est_cost_bps: fees + spread + impact + exit leg). 2.0 = twice full cost, vs pretrade.min_edge_cost_ratio 1.3 for ANY entry; config_guard FATALs below that bar (a conviction bar under the pretrade bar is vacuous).",
  "share_window": 40,
  "share_min_n": 20,
  "share_lo": 0.1,
  "share_hi": 0.9,
  "_cadence_doc": "governor mirror of ml.exploration.probe_share_window (40): rolling admit-share of the last share_window conviction EVALUATIONS, global + per-regime. Outside [share_lo, share_hi] with >= share_min_n samples -> CV-050/051 on the state TRANSITION only. It alarms, it never auto-tunes. share_min_n suppresses judgment on thin windows, so a restart-reset window is silent, never false-alarming."
}
```

Validate the edit: `.venv/bin/python -c "import json;
json.load(open('config.json')); print('ok')"` → `ok`.

- [ ] **Step 5: Run the guard tests + neighbors**

Run: `.venv/bin/python -m pytest tests/test_config_guard_conviction.py tests/test_config_guard_coherence.py -q`
Expected: PASS (new file green; existing coherence suite unaffected).

- [ ] **Step 6: Commit**

```bash
git add config.json core/config_guard.py tests/test_config_guard_conviction.py
git commit -m "feat: conviction config block + config_guard coherence checks"
```

---

### Task 4: engine seam + entry-site wiring + status

**Files:**
- Modify: `main.py` — import, `__init__` construction, new method
  `_conviction_disposition`, call site after the pretrade veto
- Modify: `runner.py:551` neighborhood — add `"conviction"` to
  `build_status`
- Test: `tests/test_conviction_integration.py`

**Interfaces:**
- Consumes: Task 1/2's `ConvictionFormula` (`evaluate`, `note`,
  `cadence_alarms`, `status`, `enabled`, `enforce`, `mode`); existing
  `_regime_under_coverage_floor` (`main.py:248`), `REGIME_LABELS`
  (`main.py:86` import), `history.regime_live_count`
  (`ml/history.py:327`), `get_audit()` + `tag()` audit pattern.
- Produces: `LiquidityBot._conviction_disposition(asset: str, signal,
  decision, regime_label: str, explored: bool) -> Optional[Code]`
  (None = proceed; a Code = enforce-mode skip); `build_status()["conviction"]`
  = `bot.conviction.status()`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_conviction_integration.py`:

```python
"""tests/test_conviction_integration.py — engine-seam contract for the
Phase A conviction formula (_conviction_disposition): report mode is
byte-identical (never skips), enforce mode returns the denial code,
probes are exempt, the T4 regime floor feeds term 3. Runs off a minimal
LiquidityBot.__new__() stub (the established entry-path test pattern —
see _record_probe_admission's docstring)."""
import types

from core.codes import Code
from main import LiquidityBot
from risk.conviction import ConvictionFormula


class _Hist:
    def __init__(self, live):
        self._live = live

    def regime_live_count(self, regime_label):
        return self._live


def _bot(mode="report", live=100, floor=60, enabled=True):
    bot = LiquidityBot.__new__(LiquidityBot)
    bot.conviction = ConvictionFormula(
        {"enabled": enabled, "mode": mode, "agreement_floor": 0.75,
         "ev_cost_mult": 2.0, "share_window": 8, "share_min_n": 4,
         "share_lo": 0.25, "share_hi": 0.75})
    bot._regime_floor_live = floor
    bot.history = _Hist(live)
    return bot


def _signal(gates=None):
    s = types.SimpleNamespace()
    s.gates_passed = {"g1": True, "g2": True, "g3": True,
                      "g4": True} if gates is None else gates
    return s


def _decision(edge=100.0, cost=20.0):
    return types.SimpleNamespace(est_edge_bps=edge, est_cost_bps=cost)


def test_report_mode_never_skips_even_on_denial():
    bot = _bot(mode="report")
    deny = bot._conviction_disposition(
        "BTC", _signal({"g1": False, "g2": False, "g3": False,
                        "g4": True}), _decision(), "range", False)
    assert deny is None                    # denied but report: proceed
    assert bot.conviction.status()["denials"] == {"CV-010": 1}


def test_enforce_mode_returns_denial_code():
    bot = _bot(mode="enforce")
    deny = bot._conviction_disposition(
        "BTC", _signal(), _decision(edge=10.0, cost=20.0), "range", False)
    assert deny == Code.CV_EV_MULTIPLE_LOW


def test_enforce_mode_admits_clean_entry():
    assert _bot(mode="enforce")._conviction_disposition(
        "BTC", _signal(), _decision(), "range", False) is None


def test_probe_exempt_and_unnoted():
    bot = _bot(mode="enforce")
    assert bot._conviction_disposition(
        "BTC", _signal({"g1": False}), _decision(edge=0.0), "range",
        True) is None
    assert bot.conviction.status()["evaluated"] == 0


def test_disabled_formula_is_inert():
    bot = _bot(enabled=False)
    assert bot._conviction_disposition(
        "BTC", _signal(), _decision(), "range", False) is None
    assert bot.conviction.status()["evaluated"] == 0


def test_under_covered_regime_denies_in_enforce():
    bot = _bot(mode="enforce", live=10, floor=60)
    assert bot._conviction_disposition(
        "BTC", _signal(), _decision(), "range", False) == \
        Code.CV_REGIME_UNKNOWN


def test_unmapped_regime_label_denies_in_enforce():
    # a label outside REGIME_LABELS has no evidence bucket: unknown
    bot = _bot(mode="enforce")
    assert bot._conviction_disposition(
        "BTC", _signal(), _decision(), "never_a_regime", False) == \
        Code.CV_REGIME_UNKNOWN


def test_regime_floor_zero_disables_term():
    bot = _bot(mode="enforce", live=0, floor=0)
    assert bot._conviction_disposition(
        "BTC", _signal(), _decision(), "range", False) is None


def test_empty_gates_dict_reads_as_zero_agreement():
    bot = _bot(mode="enforce")
    assert bot._conviction_disposition(
        "BTC", _signal({}), _decision(), "range", False) == \
        Code.CV_AGREEMENT_LOW


def test_missing_stub_attrs_self_heal():
    bot = LiquidityBot.__new__(LiquidityBot)   # no conviction attr at all
    assert bot._conviction_disposition(
        "BTC", _signal(), _decision(), "range", False) is None


def test_status_shape():
    bot = _bot()
    bot._conviction_disposition("BTC", _signal(), _decision(), "range",
                                False)
    st = bot.conviction.status()
    assert {"enabled", "mode", "evaluated", "admitted", "denials",
            "share", "n", "by_regime", "alarm"} <= set(st)
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_conviction_integration.py -q`
Expected: FAIL — `AttributeError: 'LiquidityBot' object has no attribute
'_conviction_disposition'`.

- [ ] **Step 3: Wire the engine**

(a) Import — in `main.py`'s import block (alongside the other `risk.`
imports):

```python
from risk.conviction import ConvictionFormula
```

(b) Construction — in `__init__`, directly after the probe-admissions
deque init (`self._probe_admissions = deque(...)`, `main.py:741-742`):

```python
        # Compounder Phase A: deterministic conviction formula
        # (risk/conviction.py). report mode (default) = dispositions
        # logged, entry behavior byte-identical; the enforce flip is a
        # conscious operator decision (see the module docstring).
        self.conviction = ConvictionFormula(
            config.get("conviction", {}) or {})
```

(c) The seam method — add to `LiquidityBot` directly after
`_probe_admission_decision` (after `main.py:2159`):

```python
    def _conviction_disposition(self, asset: str, signal, decision,
                                regime_label: str,
                                explored: bool) -> Optional[Code]:
        """Compounder Phase A conviction formula, engine seam: evaluate
        ONE pretrade-approved entry attempt. Returns the denial Code when
        the caller must SKIP the entry (enforce mode only), else None.
        Probes are exempt (they are the exploration channel; the formula
        governs CONVICTION flow). Report mode always returns None —
        dispositions + cadence alarms are logged, entry behavior stays
        byte-identical (the honest threshold-derivation period). Runs
        AFTER the pretrade gate so the EV term reads the gate's MEASURED
        est_edge_bps/est_cost_bps for THIS entry. Self-healing getattr
        (like _record_probe_admission): entry-path integration tests run
        off a minimal LiquidityBot.__new__() stub."""
        conv = getattr(self, "conviction", None)
        if conv is None or not conv.enabled or explored:
            return None
        gp = signal.gates_passed or {}
        agreement = (sum(1 for ok in gp.values() if ok) / len(gp)) \
            if gp else 0.0
        rfl = int(getattr(self, "_regime_floor_live", 0))
        regime_known = True
        if rfl > 0:
            if regime_label not in REGIME_LABELS:
                regime_known = False    # unmapped label: no evidence bucket
            else:
                regime_known = not _regime_under_coverage_floor(
                    self.history.regime_live_count(regime_label), rfl)
        cdec = conv.evaluate(
            agreement=agreement, est_edge_bps=decision.est_edge_bps,
            est_cost_bps=decision.est_cost_bps, regime_known=regime_known)
        conv.note(cdec, regime_label)
        get_audit().log(
            "conviction", cdec.code,
            tag(cdec.code,
                f"{asset} conviction "
                f"{'admitted' if cdec.admitted else 'denied'} "
                f"({conv.mode})"),
            {"asset": asset, "mode": conv.mode, **cdec.terms})
        for acode, adetail in conv.cadence_alarms():
            get_audit().log("conviction", acode, tag(acode, adetail),
                            {"asset": asset})
        if not cdec.admitted and conv.enforce:
            return cdec.code
        return None
```

(d) Call site — in the entry loop, immediately after the pretrade veto
block (`if not decision.approved: ... continue`, `main.py:2672-2676`)
and BEFORE `position_id = pid` (`main.py:2680`), so all three entry
paths (algo / ladder / single) sit behind one disposition:

```python
            # Compounder Phase A: conviction formula disposition. None ->
            # proceed (always, in report mode); a Code -> the enforce-mode
            # skip path (registered CV-*, candidate marked, no bare string).
            deny_code = self._conviction_disposition(
                asset, signal, decision, macro_state.label, explored)
            if deny_code is not None:
                self._mark_cand(asset, signal.direction, deny_code.value)
                continue
```

(e) Status — in `runner.py` `build_status`, directly after the
`"monitor": bot.monitor.status(),` line (`runner.py:551`):

```python
            "conviction": bot.conviction.status()
                if hasattr(bot, "conviction") else {},
```

- [ ] **Step 4: Run the integration tests + the entry-path neighbors**

Run: `.venv/bin/python -m pytest tests/test_conviction_integration.py tests/test_conviction.py tests/test_probe_throttle.py tests/test_probe_marker.py -q`
Expected: PASS. (Probe suites prove the exemption didn't disturb the
throttle path.)

- [ ] **Step 5: Report-mode invariance check (the load-bearing claim)**

Run: `.venv/bin/python -m pytest tests/ -q -k "e2e or journey or ladder or entry"`
Expected: PASS — the report-mode default changes no entry behavior
anywhere in the existing suites (they run with the new block active
because `config.json` now carries it).

- [ ] **Step 6: Commit**

```bash
git add main.py runner.py tests/test_conviction_integration.py
git commit -m "feat: wire conviction formula into the entry pipeline (report mode) + status section"
```

---

### Task 5: full battery + push

**Files:** none new — verification and delivery only.

- [ ] **Step 1: Full matrix, in order, all green**

```bash
.venv/bin/python -m pytest tests/ -q
.venv/bin/python scripts/smoke_test.py
.venv/bin/python scripts/assurance_check.py
.venv/bin/python scripts/overfit_check.py
.venv/bin/ruff check core data execution ml risk regime strategies sentiment api main.py runner.py tests scripts/quant_trials.py scripts/overfit_check.py
pyright core data execution ml risk regime strategies sentiment api main.py runner.py
.venv/bin/bandit -c pyproject.toml -r . -x ./.venv,./tests -q
.venv/bin/python -m compileall -q . -x '.venv'
```

Expected: pytest all passed; smoke all passed; assurance all passed;
overfit at its consciously-rebaselined state (4 passed / 4 failed —
gap[logistic/gbt/mlp] + dof, the known thin-corpus family; any NEW
failure is a stop); ruff clean; pyright 0 errors in shipped scope;
bandit no issues; compileall silent. `pyright` lives at
`/root/.local/bin/pyright` if not on PATH.

A red anywhere = fix before pushing; report-mode Phase A must not move
quant/overfit numbers (it changes no decision path) — if a number moved,
that is a bug in the wiring, not a re-baselining event.

- [ ] **Step 2: Push**

```bash
git push -u origin claude/remote-control-e3h815
```

(retry up to 4 times with 2s/4s/8s/16s backoff on network failure only).

---

## Self-review (performed at plan-write time)

- **Spec coverage (§2):** term 1 agreement (T1 S1/S3), term 2 EV multiple
  (T1), term 3 regime evidence via T4 floor (T4 S3), term 4 context
  socket honored by the formula now, wired in Phase B/C (T1
  `test_context_misaligned_denies_cv040`); cadence governor per window +
  per regime (T2); registered codes on every disposition (T1 S3, T4
  S3c); config-lifted thresholds + guard (T3); status extension (T4e).
  Deferred per spec: context inputs (Phase B), long book + CV-040 call
  site (Phase C), enforce flip (operator decision, recipe in module doc).
- **Placeholder scan:** clean — every code step carries the code.
- **Type consistency:** `ConvictionDecision`/`ConvictionFormula`
  signatures identical across Tasks 1/2/4; `_conviction_disposition`
  arg order (asset, signal, decision, regime_label, explored) matches
  every test call.
