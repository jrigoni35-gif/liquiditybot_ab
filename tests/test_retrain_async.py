"""C5 (2026-09-28): the auto-retrain's heavy half runs off the engine thread.

Measured before: the in-process retrain held the per-position stop loop for
21-28 s every time it ran (n=20). These pins hold the properties that make the
off-thread version safe: launch returns at once, the deploy half runs on the
ENGINE thread, never two jobs, worker errors are counted exactly like the
synchronous path, and the synchronous fallback still works.
"""
import threading
import time
from types import SimpleNamespace

from main import LiquidityBot


def _bot(config=None, compute=None, gate=True):
    b = LiquidityBot.__new__(LiquidityBot)
    b.config = config or {"ml": {}}
    b.history = SimpleNamespace(row_count=lambda: 500)
    b._retrain_failures = 0
    b.gate_calls = 0
    b.applied = []

    def _gate(rows):
        b.gate_calls += 1
        return gate
    b._retrain_gate = _gate
    b._retrain_compute = compute or (lambda rows: {"rows": rows})
    b._retrain_apply = lambda job: b.applied.append(
        (job, threading.current_thread().name))
    return b


def _drain(b, timeout=5.0):
    t = b._retrain_thread
    if t is not None:
        t.join(timeout)
    b._poll_auto_retrain()


def test_launch_returns_immediately_and_applies_on_the_engine_thread():
    release = threading.Event()

    def slow(rows):
        release.wait(5.0)                # the "21-28 s" walk-forward, held
        return {"rows": rows}
    b = _bot(compute=slow)
    t0 = time.monotonic()
    b._launch_auto_retrain()
    assert time.monotonic() - t0 < 0.5, "launch blocked the engine thread"
    b._poll_auto_retrain()               # still training: nothing applied
    assert b.applied == []
    release.set()
    _drain(b)
    assert b.applied == [({"rows": 500}, threading.current_thread().name)]
    assert b._retrain_thread is None


def test_never_two_jobs_in_flight():
    release = threading.Event()
    b = _bot(compute=lambda rows: release.wait(5.0) and {"rows": rows})
    b._launch_auto_retrain()
    b._launch_auto_retrain()             # second hourly while the first runs
    assert b.gate_calls == 1, "a second job was gated while one was running"
    release.set()
    _drain(b)


def test_worker_error_is_counted_not_raised():
    def boom(rows):
        raise RuntimeError("walk-forward exploded")
    b = _bot(compute=boom)
    b._launch_auto_retrain()
    _drain(b)                            # must not raise into cycle_once
    assert b._retrain_failures == 1 and b.applied == []


def test_nothing_to_gate_applies_nothing():
    b = _bot(compute=lambda rows: None)  # too few rows / unscoreable
    b._launch_auto_retrain()
    _drain(b)
    assert b.applied == [] and b._retrain_failures == 0


def test_closed_gate_starts_no_worker():
    b = _bot(gate=False)
    b._launch_auto_retrain()
    assert getattr(b, "_retrain_thread", None) is None


def test_async_off_falls_back_to_the_synchronous_path():
    b = _bot(config={"ml": {"auto_retrain_async": False}})
    calls = []
    b._maybe_auto_retrain = lambda: calls.append("sync")
    b._launch_auto_retrain()
    assert calls == ["sync"] and getattr(b, "_retrain_thread", None) is None


def test_poll_with_no_job_is_a_no_op():
    b = _bot()
    b._poll_auto_retrain()
    assert b.applied == [] and b._retrain_failures == 0


def test_the_worker_is_a_daemon():
    """A `stop` must never wait for training to finish."""
    release = threading.Event()
    b = _bot(compute=lambda rows: release.wait(5.0) and {"rows": rows})
    b._launch_auto_retrain()
    assert b._retrain_thread.daemon
    release.set()
    _drain(b)


def test_cycle_once_polls_after_the_stop_loop(tmp_path, monkeypatch):
    """The async path is dead unless cycle_once polls - and it must poll
    AFTER fast_cycle so this cycle's stops always run first."""
    from test_decision_events import _bot as real_bot
    monkeypatch.chdir(tmp_path)
    b = real_bot(tmp_path)
    order = []
    monkeypatch.setattr(b, "fast_cycle", lambda now: order.append("stops"))
    monkeypatch.setattr(b, "_poll_auto_retrain",
                        lambda: order.append("poll"))
    b._last_macro = 1e18                 # skip the hourly branch
    b.cycle_once(1_700_000_000.0)
    assert order[:2] == ["stops", "poll"]
