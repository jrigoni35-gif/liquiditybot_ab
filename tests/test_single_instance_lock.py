"""SingleInstanceLock: prevents a second runner from driving the same outputs/
dir (two runners clobber status/state, race the control queue, and interleave
the audit chain — and a stuck duplicate makes status.json flap "stale"). Lock
is heartbeat-based: a live holder refuses a new acquire; a stale/crashed
holder's lock is taken over — self-healing, no OS PID probing.
"""
import json
import time

from core.runtime import SingleInstanceLock


def test_second_acquire_is_refused_while_holder_is_fresh(tmp_path):
    p = str(tmp_path / "runner.lock")
    a = SingleInstanceLock(p, stale_after_sec=30.0)
    assert a.acquire() is None                      # first wins
    b = SingleInstanceLock(p, stale_after_sec=30.0)
    b.pid = a.pid + 1                               # simulate a different process
    held = b.acquire()
    assert held is not None and held["pid"] == a.pid  # refused, names the holder


def test_stale_lock_is_taken_over(tmp_path):
    p = tmp_path / "runner.lock"
    # a crashed holder: fresh pid, but heartbeat long past the stale window
    p.write_text(json.dumps({"pid": 999999, "heartbeat": time.time() - 120}),
                 encoding="utf-8")
    lock = SingleInstanceLock(str(p), stale_after_sec=30.0)
    assert lock.acquire() is None                   # took over
    assert json.loads(p.read_text(encoding="utf-8"))["pid"] == lock.pid


def test_refresh_advances_heartbeat_and_reacquire_is_idempotent(tmp_path):
    p = tmp_path / "runner.lock"
    lock = SingleInstanceLock(str(p), stale_after_sec=30.0)
    lock.acquire()
    h0 = json.loads(p.read_text(encoding="utf-8"))["heartbeat"]
    time.sleep(0.02)
    lock.refresh()
    h1 = json.loads(p.read_text(encoding="utf-8"))["heartbeat"]
    assert h1 > h0
    assert lock.acquire() is None                   # same pid re-acquires freely


def test_release_frees_the_lock(tmp_path):
    p = tmp_path / "runner.lock"
    lock = SingleInstanceLock(str(p), stale_after_sec=30.0)
    lock.acquire()
    assert p.exists()
    lock.release()
    assert not p.exists()
    # a fresh runner can now acquire immediately, even inside the stale window
    other = SingleInstanceLock(str(p), stale_after_sec=30.0)
    other.pid = lock.pid + 1
    assert other.acquire() is None


def test_release_by_non_owner_is_a_noop(tmp_path):
    p = tmp_path / "runner.lock"
    owner = SingleInstanceLock(str(p), stale_after_sec=30.0)
    owner.acquire()
    intruder = SingleInstanceLock(str(p), stale_after_sec=30.0)
    intruder.pid = owner.pid + 1
    intruder.release()                              # must not remove owner's lock
    assert p.exists()
    assert json.loads(p.read_text(encoding="utf-8"))["pid"] == owner.pid
