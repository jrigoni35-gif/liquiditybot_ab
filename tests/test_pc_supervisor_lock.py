"""pc_supervisor single-instance lock — one supervisor per outputs/ dir.

Observed live 2026-07-22: TWO full supervisor+runner stacks on the PC.
Task Scheduler's IgnoreNew only dedups instances IT started; the source-change
handoff spawns a detached copy the task cannot see, so RestartOnFailure /
Start-ScheduledTask / logon each added another stack — the source of the
audit trail's "concurrent-writer seam" forks. The fix is the same hardened
heartbeat lock the runner uses, held by the supervisor itself, so NO launch
path (task, restart.bat, handoff, manual) can ever double it. This pins:

  * a second supervisor against a LIVE foreign lock refuses and exits
    without running a single tick;
  * the source-change handoff releases the lock BEFORE spawning the
    replacement (else the new copy would refuse against its parent's lock);
  * a normal exit releases the lock (ownership-aware).
"""
import json
import time

import pytest

import scripts.pc_supervisor as sup


def _wire(monkeypatch, tmp_path):
    """Point the supervisor at an isolated outputs/ and neuter every side
    effect except the lock + handoff logic under test."""
    monkeypatch.setattr(sup, "OUT", tmp_path)
    monkeypatch.setattr(sup, "_materialise_token", lambda: None)
    monkeypatch.setattr(sup, "_telemetry_ready", lambda: False)
    monkeypatch.setattr(sup, "_maybe_launch_opend", lambda: "disabled")
    monkeypatch.setattr(sup, "_auto_update_due", lambda: False)
    monkeypatch.setattr(sup, "_stamp_due", lambda *a, **k: False)
    monkeypatch.setattr(sup, "_fresh", lambda *a, **k: True)   # runner alive
    monkeypatch.setattr(sup, "IS_WIN", False)                  # skip 5b/5c


def test_second_supervisor_refuses_against_live_lock(monkeypatch, tmp_path):
    _wire(monkeypatch, tmp_path)
    (tmp_path / "pc_supervisor.lock").write_text(
        json.dumps({"pid": 999999, "heartbeat": time.time()}), encoding="utf-8")

    def _no_tick():
        raise AssertionError("a refused supervisor must never tick")
    monkeypatch.setattr(sup, "tick", _no_tick)
    monkeypatch.setattr(sup.time, "sleep",
                        lambda s: (_ for _ in ()).throw(
                            AssertionError("must not reach the loop")))
    sup.main()                                     # returns, no raise
    peer = json.loads((tmp_path / "pc_supervisor.lock").read_text())
    assert peer["pid"] == 999999                   # peer's lock untouched


def test_stale_lock_is_reclaimed_and_released_on_exit(monkeypatch, tmp_path):
    _wire(monkeypatch, tmp_path)
    (tmp_path / "pc_supervisor.lock").write_text(
        json.dumps({"pid": 999999,
                    "heartbeat": time.time() - sup.STALE_SEC - 60}),
        encoding="utf-8")

    def _one_tick():
        # by now the stale foreign lock must be OURS
        cur = json.loads((tmp_path / "pc_supervisor.lock").read_text())
        assert cur["pid"] == sup.os.getpid()
        raise SystemExit(0)                        # end the loop
    monkeypatch.setattr(sup, "tick", _one_tick)
    with pytest.raises(SystemExit):
        sup.main()
    # the finally released our lock on the way out
    assert not (tmp_path / "pc_supervisor.lock").exists()


def test_handoff_releases_lock_before_spawning_replacement(monkeypatch,
                                                           tmp_path):
    _wire(monkeypatch, tmp_path)
    order = []
    lock = sup.SingleInstanceLock(path=str(tmp_path / "pc_supervisor.lock"),
                                  stale_after_sec=sup.STALE_SEC)
    assert lock.acquire() is None
    monkeypatch.setattr(sup, "_LOCK", lock)
    monkeypatch.setattr(sup, "_source_changed", lambda: True)

    real_release = lock.release
    monkeypatch.setattr(lock, "release",
                        lambda: (order.append("release"), real_release())[0])
    monkeypatch.setattr(sup, "_spawn",
                        lambda *a, **k: order.append("spawn"))
    with pytest.raises(SystemExit):
        sup.tick()
    assert order == ["release", "spawn"]           # release strictly first
    assert not (tmp_path / "pc_supervisor.lock").exists()


def test_lock_stale_window_exceeds_tick_cadence():
    # the heartbeat refreshes once per CHECK_SEC tick; a stale window at or
    # below the cadence would let a healthy supervisor's own lock expire
    # between ticks and invite a takeover — the doubling this lock prevents
    assert sup.STALE_SEC > 2 * sup.CHECK_SEC
