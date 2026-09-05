"""A HUNG GATE AND A MISSING TOOL ARE NOT THE SAME OBSERVATION.

Two defects in the deploy plane, failing in OPPOSITE directions, both found
2026-09-05 by injection and both confirmed against the real code here.

DEFECT 1 — FAIL-OPEN. `_run_gate` catches every exception, including
subprocess.TimeoutExpired, and returns could_not_run=True. Its own docstring
says "could_not_run is NEVER a rejection". So a DoD gate that HANGS - smoke,
assurance, overfit, ruff, pyright - is treated exactly like a gate whose tool
is not installed, and the deploy is ADMITTED. "The tool is absent" is a
legitimate could-not-run on a machine that lacks it; "the tool ran and never
finished" is a gate that did not pass, and the only automated admission path to
the live trading PC must not confuse them.

DEFECT 2 — FAIL-CLOSED, and it is a bricking risk. The incoming-code battery
runs `pytest tests/` under a 1200s wall and treats a timeout as "refusing the
update". Measured on this box 2026-09-05 across SIX runs: 608, 623, 686, 736,
745, 810s. The worst observed is 67.5% of the wall, and the suite grew ~50
tests in one session. Once it crosses 1200s on the PC, auto_update rejects
EVERY update - including the one-line commit that would raise the wall.
Recovery needs physical access to the PC.

That is CLAUDE.md's own durable law: "a gate's release condition must never
depend on the thing it blocks", which the file records as having produced four
separate incidents. This is a fifth, in the deploy gate itself.

The fix for defect 2 is NOT just a bigger number - that only moves the cliff.
The margin has to be OBSERVABLE before it is hit, so the battery logs its
duration and warns while there is still room to act.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "auto_update_timeout_uut", ROOT / "scripts" / "auto_update.py")
au = importlib.util.module_from_spec(_spec)
sys.modules["auto_update_timeout_uut"] = au
_spec.loader.exec_module(au)


# ------------------------------------------------ defect 1: hung != missing
def test_a_timed_out_gate_is_NOT_could_not_run(monkeypatch, tmp_path):
    """A gate that hung did not pass. Only a genuinely absent tool is a
    could-not-run, because that is the case a machine can legitimately be in."""
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=1)
    monkeypatch.setattr(au.subprocess, "run", boom)

    rc, tail, could_not_run = au._run_gate(
        tmp_path, sys.executable, ["-c", "pass"], {}, 1)

    assert could_not_run is False, (
        "a HUNG gate was classified could_not_run, and _run_gate's contract "
        "says could_not_run is NEVER a rejection - so a gate that spins "
        "forever ADMITS the deploy to the live trading PC")
    assert rc != 0, "a timed-out gate must not report success"
    assert "timeout" in tail.lower() or "timed out" in tail.lower(), (
        f"the tail must name the timeout so an operator can tell it from a "
        f"red suite; got {tail!r}")


def test_a_missing_tool_IS_still_could_not_run(monkeypatch, tmp_path):
    """ANTI-RUBBER-STAMP, and the behaviour that must be preserved: a machine
    without ruff installed is not a machine with a failing gate. If this
    reddens, the fix broke every box that lacks an optional tool."""
    def boom(*a, **k):
        raise FileNotFoundError("ruff: command not found")
    monkeypatch.setattr(au.subprocess, "run", boom)

    _rc, _tail, could_not_run = au._run_gate(
        tmp_path, sys.executable, ["-c", "pass"], {}, 5)
    assert could_not_run is True


def test_a_gate_that_runs_and_fails_is_a_rejection(monkeypatch, tmp_path):
    """The ordinary red path must be untouched by the timeout change."""
    class P:
        returncode = 1
        stdout = "FAILED tests/test_x.py::test_y"
        stderr = ""
    monkeypatch.setattr(au.subprocess, "run", lambda *a, **k: P())
    rc, _tail, could_not_run = au._run_gate(
        tmp_path, sys.executable, ["-c", "pass"], {}, 5)
    assert rc == 1 and could_not_run is False


# ------------------------------------- defect 2: the wall must not brick us
def test_wall_covers_today_with_margin(monkeypatch, tmp_path):
    """With no history, the floor must already clear the measured suite. Worst
    of six runs on 2026-09-05: 810s."""
    monkeypatch.delenv("LB_BATTERY_TIMEOUT_SEC", raising=False)
    monkeypatch.setattr(au, "OUT", tmp_path)          # no state file
    assert au.battery_timeout_sec() >= 2400
    assert au.BATTERY_TIMEOUT_MIN > 810 * 2


def test_a_GROWING_suite_raises_its_own_wall(monkeypatch, tmp_path):
    """THE ANTI-BRICK PROPERTY, and the reason a bigger constant is not enough.

    A fixed wall is a cliff the suite walks toward: once crossed, auto_update
    rejects EVERY update including the commit that would raise the wall, and
    recovery needs physical access to the PC. Deriving the wall from the last
    COMPLETED battery means gradual growth carries its own ceiling with it, so
    the channel can never be blocked by the thing it is measuring."""
    monkeypatch.delenv("LB_BATTERY_TIMEOUT_SEC", raising=False)
    monkeypatch.setattr(au, "OUT", tmp_path)
    import json as _j
    for observed, expect_at_least in [(810, 2400), (1500, 4500), (3000, 4800)]:
        (tmp_path / "auto_update_state.json").write_text(
            _j.dumps({"last_battery_sec": observed}), encoding="utf-8")
        wall = au.battery_timeout_sec()
        assert wall >= expect_at_least, (
            f"suite at {observed}s got a {wall}s wall - it must scale with the "
            f"suite, not stay put while the suite grows into it")
        assert wall > observed, "the wall must always exceed the observed run"


def test_a_genuine_HANG_is_still_caught(monkeypatch, tmp_path):
    """ANTI-RUBBER-STAMP. If the wall simply tracked whatever it saw, it would
    stop being a gate. A hang must still exceed it."""
    monkeypatch.delenv("LB_BATTERY_TIMEOUT_SEC", raising=False)
    monkeypatch.setattr(au, "OUT", tmp_path)
    import json as _j
    (tmp_path / "auto_update_state.json").write_text(
        _j.dumps({"last_battery_sec": 800}), encoding="utf-8")
    wall = au.battery_timeout_sec()
    assert wall <= au.BATTERY_TIMEOUT_MAX
    assert wall < 800 * au.BATTERY_TIMEOUT_GROWTH_K + 1


def test_the_operator_escape_does_not_need_a_deploy(monkeypatch, tmp_path):
    """THE SECOND ANTI-BRICK PROPERTY. The recovery path for a blocked deploy
    channel must not itself require a deploy. An env var set on the box is
    outside the channel; a constant in this file is not."""
    monkeypatch.setattr(au, "OUT", tmp_path)
    monkeypatch.setenv("LB_BATTERY_TIMEOUT_SEC", "9000")
    assert au.battery_timeout_sec() == 9000, (
        "the operator override was clamped - a box already stuck at the wall "
        "could not unblock itself without deploying, which is the trap")
    monkeypatch.setenv("LB_BATTERY_TIMEOUT_SEC", "garbage")
    assert au.battery_timeout_sec() >= 2400, "a bad override must not wedge it"
    monkeypatch.setenv("LB_BATTERY_TIMEOUT_SEC", "-5")
    assert au.battery_timeout_sec() >= 2400


def test_a_completed_battery_records_its_duration(monkeypatch, tmp_path):
    """The wall can only track the suite if something writes the sample, and it
    must survive _record_outcome's later whole-dict write."""
    monkeypatch.setattr(au, "OUT", tmp_path)
    au._record_battery_sec(1234.5)
    import json as _j
    st = _j.loads((tmp_path / "auto_update_state.json").read_text(encoding="utf-8"))
    assert st["last_battery_sec"] == 1234.5
    # a pre-existing stamp must be merged, not clobbered
    (tmp_path / "auto_update_state.json").write_text(
        _j.dumps({"outcome": "current", "head": "abc"}), encoding="utf-8")
    au._record_battery_sec(777.0)
    st = _j.loads((tmp_path / "auto_update_state.json").read_text(encoding="utf-8"))
    assert st["last_battery_sec"] == 777.0 and st["outcome"] == "current"


def test_the_margin_is_observable_before_the_cliff():
    """A wall that self-raises still needs to say so: the operator must learn
    the suite is growing while there is room to act."""
    assert 0.0 < au.BATTERY_WARN_FRACTION < 1.0
    assert au.BATTERY_TIMEOUT_MIN * au.BATTERY_WARN_FRACTION > 810, (
        "the warning would fire on every healthy run and be tuned out")


def test_lock_stale_outlives_the_WHOLE_in_lock_ceiling():
    """The real invariant is against the TOTAL, not one leg: battery_passes
    chains the pytest wall AND the replay gate. Pinning one leg is how raising
    a constant quietly puts a healthy battery under a stale lock, which lets a
    second updater reclaim mid-run and sweep the live worktree."""
    ceiling = au.BATTERY_TIMEOUT_MAX + 1200
    assert au.LOCK_STALE_SEC > ceiling, (
        f"LOCK_STALE_SEC={au.LOCK_STALE_SEC} does not outlive the in-lock "
        f"ceiling {ceiling}s (battery max {au.BATTERY_TIMEOUT_MAX} + replay 1200)")


def test_a_trivially_fast_battery_is_not_a_timing_sample(monkeypatch, tmp_path):
    """A run that finished in under a minute did not execute the suite - it hit
    a stub, a collection error or an immediate refusal. Recording it would drag
    the derived wall down toward the floor on exactly the runs that tell you
    least, and (measured) it also made every existing battery test write into
    the production outputs/ tree."""
    monkeypatch.setattr(au, "OUT", tmp_path)
    assert au.BATTERY_SAMPLE_MIN_SEC >= 60
    # the state file must not appear from a sub-floor run
    assert not (tmp_path / "auto_update_state.json").exists()
