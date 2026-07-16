"""tests/test_runner_wedge_guard.py — a persistently-raising cycle must stop
pretending it's healthy, AND must be recoverable.

cycle_once raising every iteration used to spin the loop forever logging
"continuing" while no stops/entries ran and status showed nothing wrong. Now
the runner counts consecutive cycle_once failures; at cycle_fail_halt it
latches a CRITICAL 'cycle_wedged' fault in the fault authority — refusing NEW
risk (op-state HALTED) while exits keep running (invariant #5) — and fires one
alert. It does NOT touch bot._halted (the persisted CATASTROPHE latch): the
wedge uses the process-scoped, RECOVERABLE fault, so a transient blip self-
heals (a sustained healthy streak, an operator clear_fault, or a restart that
re-arms the FM) instead of stranding the bot (review A1-F1). Only cycle_once
feeds the counter — telemetry failures never escalate (review A1-F2).
"""
import types

from core.fault import FaultManager, OpState
from runner import BotRunner


def _runner(halt_at=3, with_fault=True):
    r = BotRunner.__new__(BotRunner)
    r._cycle_fail_streak = 0
    r._cycle_fail_halt = halt_at
    r._wedge_alerted = False
    r._wedge_latched = False
    r._recover_streak = 0
    fired = []
    fm = FaultManager() if with_fault else None
    if fm is not None:
        fm.arm()
    r.bot = types.SimpleNamespace(
        _halted=False, fault=fm,
        alerts=types.SimpleNamespace(
            fire=lambda key, msg, **k: fired.append((key, msg))))
    r._fired = fired
    return r


def test_streak_below_threshold_does_not_latch():
    r = _runner(halt_at=3)
    assert r._note_cycle_failure() == 1
    assert r._note_cycle_failure() == 2
    assert r.bot.fault.allow_new_risk() is True and r._fired == []


def test_crossing_threshold_latches_fault_not_halted_alerts_once():
    r = _runner(halt_at=3)
    for _ in range(3):
        r._note_cycle_failure()                 # 3rd crosses
    fm = r.bot.fault
    assert fm.state is OpState.HALTED           # NEW risk refused via the FM
    assert fm.allow_new_risk() is False
    assert fm.allow_exits() is True             # exits ALWAYS allowed
    assert r.bot._halted is False               # NOT the persisted catastrophe latch
    assert len(r._fired) == 1 and r._fired[0][0] == "runner_wedged"
    r._note_cycle_failure()                     # keeps counting, no re-alert
    assert len(r._fired) == 1 and r._cycle_fail_streak == 4


def test_wedge_auto_recovers_after_a_sustained_healthy_streak():
    r = _runner(halt_at=3)
    for _ in range(3):
        r._note_cycle_failure()
    assert r.bot.fault.state is OpState.HALTED
    # one clean cycle is NOT enough (no resuming risk on one lucky cycle)
    r._note_cycle_ok()
    assert r.bot.fault.state is OpState.HALTED and r._wedge_latched is True
    # a SUSTAINED healthy streak (cycle_fail_halt clean cycles) auto-clears it
    for _ in range(2):
        r._note_cycle_ok()
    assert r.bot.fault.state is OpState.ARMED    # new risk re-enabled
    assert r._wedge_latched is False and r._cycle_fail_streak == 0


def test_a_failure_mid_recovery_resets_the_recover_streak():
    r = _runner(halt_at=3)
    for _ in range(3):
        r._note_cycle_failure()
    r._note_cycle_ok()
    r._note_cycle_ok()                          # 2 healthy...
    r._note_cycle_failure()                     # ...then a relapse
    r._note_cycle_ok()                          # recovery starts over
    assert r.bot.fault.state is OpState.HALTED and r._recover_streak == 1


def test_wedge_without_a_fault_manager_does_not_crash_either_path():
    # a bot without a fault manager (older/duck-typed) must not crash the wedge
    # OR the recovery path, and must never touch _halted.
    r = _runner(halt_at=2, with_fault=False)
    r._note_cycle_failure()
    r._note_cycle_failure()                     # crosses at 2, fm is None
    assert r.bot._halted is False and r._wedge_latched is True
    r._note_cycle_ok()                          # recovery path also safe (no crash)
    assert r._wedge_latched is True             # 1 healthy < halt 2: still latched


def test_alert_failure_never_prevents_the_fault_latch():
    r = _runner(halt_at=1)
    r.bot.alerts.fire = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bus"))
    r._note_cycle_failure()                     # crosses at 1
    assert r.bot.fault.state is OpState.HALTED  # latched despite the alert raising
