"""A FAILED HEARTBEAT WRITE MUST NOT REPORT AS A LIVE ONE.

SingleInstanceLock.refresh() swallowed OSError, then reset lost_count to 0 and
returned True:

    try:
        atomic_write_json(self.path, {...})
    except OSError:
        pass                                # lock is advisory; never fatal
    self.lost_count = 0
    return True

"Advisory, never fatal" is right - a lockfile write failure must not kill the
runner. Reporting SUCCESS is not. The heartbeat stops advancing while every
reader is told it is healthy, so the single-instance guarantee degrades to a
coin flip with no observable signal.

WHY THAT MATTERS HERE. The lock is read out-of-process against a 30s stale
window. Once the on-disk heartbeat stops advancing, a peer eventually reads the
record as stale and claims the directory - and two runners then share one
outputs/ tree, interleaving appends into the hash-chained audit (the documented
audit.jsonl fork class). The process that caused it believes it still holds the
lock, because refresh() told it so.

WHAT THIS FIX MUST NOT DO. `forfeited` means "a LIVE PEER owns the directory,
this runner must exit". A disk error is not a peer. Feeding write failures into
lost_count would make transient I/O terminate the runner - a worse failure than
the one being fixed. So write failures are counted SEPARATELY and never reach
forfeited.

Both callers that read the return value are safe under it, checked before the
change: pc_supervisor gates its exit on `not refresh() AND forfeited`, and
runtime's own acquire path honours a False by reporting CONTENDED - which is
strictly more honest than claiming ownership on a write that did not land.
"""
from __future__ import annotations

import core.runtime as rt
from core.runtime import SingleInstanceLock


def _lock(tmp_path):
    return SingleInstanceLock(tmp_path / "runner.lock")


def test_a_failed_write_does_not_report_success(tmp_path, monkeypatch):
    """THE REGRESSION."""
    lk = _lock(tmp_path)
    lk.acquire()
    monkeypatch.setattr(rt, "atomic_write_json",
                        lambda *a, **k: (_ for _ in ()).throw(
                            PermissionError(5, "denied")))
    assert lk.refresh() is False, (
        "refresh() returned True after the heartbeat write raised - every "
        "reader is now told the lock is live while it silently ages out")


def test_a_failed_write_is_counted_and_observable(tmp_path, monkeypatch):
    """A silent drop is indistinguishable from a healthy run. Count it."""
    lk = _lock(tmp_path)
    lk.acquire()
    monkeypatch.setattr(rt, "atomic_write_json",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("io")))
    for _ in range(3):
        lk.refresh()
    assert getattr(lk, "write_failures", 0) == 3, (
        "failed heartbeat writes are not counted anywhere - the condition is "
        "invisible to every reader and to the operator")


def test_write_failures_do_NOT_forfeit_the_lock(tmp_path, monkeypatch):
    """THE LOAD-BEARING SAFETY PIN. forfeited means a LIVE PEER owns the dir
    and this runner must exit. A disk error is not a peer, and routing write
    failures into it would let transient I/O terminate the runner - strictly
    worse than the defect being fixed."""
    lk = _lock(tmp_path)
    lk.acquire()
    monkeypatch.setattr(rt, "atomic_write_json",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("io")))
    for _ in range(lk.LOST_LIMIT * 3):
        lk.refresh()
    assert lk.forfeited is False, (
        "repeated write failures forfeited the lock - a transient disk error "
        "now kills the runner")


def test_a_successful_write_still_returns_True_and_clears_losses(tmp_path):
    """ANTI-RUBBER-STAMP: the healthy path must be untouched, or the pins
    above are satisfied by a refresh() that never succeeds."""
    lk = _lock(tmp_path)
    lk.acquire()
    lk.lost_count = 2
    assert lk.refresh() is True
    assert lk.lost_count == 0
    assert getattr(lk, "write_failures", 0) == 0


def test_recovery_after_a_transient_failure(tmp_path, monkeypatch):
    """The counter must not latch: an I/O blip that clears should leave the
    lock healthy, not permanently marked."""
    lk = _lock(tmp_path)
    lk.acquire()
    monkeypatch.setattr(rt, "atomic_write_json",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("io")))
    assert lk.refresh() is False
    monkeypatch.undo()
    assert lk.refresh() is True
    assert lk.forfeited is False


def test_a_live_peer_still_loses_the_refresh(tmp_path):
    """The pre-existing peer-detection behaviour is unchanged: a fresh FOREIGN
    record still makes refresh() return False and increments lost_count."""
    import json
    import time
    lk = _lock(tmp_path)
    lk.acquire()
    (tmp_path / "runner.lock").write_text(
        json.dumps({"pid": lk.pid + 1, "heartbeat": time.time()}),
        encoding="utf-8")
    before = lk.lost_count
    assert lk.refresh() is False
    assert lk.lost_count == before + 1, \
        "peer-loss must still feed lost_count - that is what forfeited is for"
