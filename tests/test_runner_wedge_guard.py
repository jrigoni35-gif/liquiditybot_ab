"""tests/test_runner_wedge_guard.py — a persistently-raising cycle must stop
pretending it's healthy.

Before: cycle_once raising every iteration spun the runner loop forever
logging "continuing", refreshing its lock heartbeat so no standby could take
over, while no stops/entries ran and status.json showed nothing wrong. Now
the runner counts consecutive whole-cycle failures; at cycle_fail_halt it
latches a NEW-RISK halt and fires ONE loud alert. Exits still run every cycle
(invariant #5): the guard never auto-flattens (a transient feed blip must not
dump the book) and never self-terminates (a deterministic fault would
relaunch-storm). Recovery clears the streak but NOT the latch — an operator
resume does that.
"""
import types

from runner import BotRunner


def _runner(halt_at=3):
    r = BotRunner.__new__(BotRunner)
    r._cycle_fail_streak = 0
    r._cycle_fail_halt = halt_at
    r._wedge_alerted = False
    fired = []
    r.bot = types.SimpleNamespace(
        _halted=False,
        alerts=types.SimpleNamespace(
            fire=lambda key, msg, **k: fired.append((key, msg))))
    r._fired = fired
    return r


def test_streak_below_threshold_does_not_halt():
    r = _runner(halt_at=3)
    assert r._note_cycle_failure() == 1
    assert r._note_cycle_failure() == 2
    assert r.bot._halted is False and r._fired == []


def test_crossing_threshold_halts_new_risk_and_alerts_once():
    r = _runner(halt_at=3)
    r._note_cycle_failure()
    r._note_cycle_failure()
    r._note_cycle_failure()                 # 3rd -> crosses
    assert r.bot._halted is True            # NEW risk halted
    assert len(r._fired) == 1 and r._fired[0][0] == "runner_wedged"
    # further failures do not re-alert (no spam) but keep counting
    r._note_cycle_failure()
    assert len(r._fired) == 1 and r._cycle_fail_streak == 4


def test_clean_pass_clears_streak_but_not_the_halt_latch():
    r = _runner(halt_at=3)
    for _ in range(3):
        r._note_cycle_failure()
    assert r.bot._halted is True
    r._note_cycle_ok()
    # streak + alert re-arm, but the halt is a latch (operator clears it)
    assert r._cycle_fail_streak == 0 and r._wedge_alerted is False
    assert r.bot._halted is True
    # a fresh streak can alert again once it re-crosses
    for _ in range(3):
        r._note_cycle_failure()
    assert len(r._fired) == 2


def test_alert_failure_never_prevents_the_halt():
    r = _runner(halt_at=1)

    def boom(*a, **k):
        raise RuntimeError("alert bus down")
    r.bot.alerts.fire = boom
    r._note_cycle_failure()                 # crosses at 1
    assert r.bot._halted is True            # halt set despite the alert raising
