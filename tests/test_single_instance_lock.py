"""SingleInstanceLock: prevents a second runner from driving the same outputs/
dir (two runners clobber status/state, race the control queue, and interleave
the audit chain — and a stuck duplicate makes status.json flap "stale"). Lock
is heartbeat-based: a live holder refuses a new acquire; a stale/crashed
holder's lock is taken over — self-healing, no OS PID probing.
"""
import json
import time
import types

from core.runtime import SingleInstanceLock
from runner import BotRunner


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


# ---------------------------------------------------------------------------
class _RecordingLock:
    """Duck-typed lock stub: counts refreshes so the test can prove liveness
    was signalled per loop iteration, independent of wall-clock timing."""

    def __init__(self):
        self.refreshes = 0
        self.released = False

    def refresh(self):
        self.refreshes += 1

    def release(self):
        self.released = True


def _fake_bot():
    """Minimal duck-typed bot: just the attributes BotRunner touches on the
    startup line, the loop's error path, and the shutdown path (dry run)."""
    return types.SimpleNamespace(
        dry_run=True,
        poll_sec=0.0,
        snapshot_sec=10_000.0,
        _last_snapshot=time.time(),
        _resumed=False,
        _equity=lambda: 10_000.0,
        state=types.SimpleNamespace(starting_capital=10_000.0),
        orders=types.SimpleNamespace(deadman_sec=0, maker_fee_bps=16.0,
                                     taker_fee_bps=26.0),
        store=types.SimpleNamespace(snapshot=lambda b: True,
                                    path="outputs/state.json"),
        moomoo=types.SimpleNamespace(close=lambda: None),
    )


def test_heartbeat_refreshes_even_when_every_cycle_raises(tmp_path, monkeypatch):
    """A runner stuck in a cycle-error loop is still ALIVE: the heartbeat must
    refresh every iteration regardless of cycle outcome, or the lock goes
    stale and a second launch takes over - recreating the exact duplicate the
    lock exists to prevent."""
    monkeypatch.chdir(tmp_path)                     # outputs/ lands in tmp
    bot = _fake_bot()
    lock = _RecordingLock()
    # test doubles standing in for LiquidityBot/SingleInstanceLock: the
    # runner only touches the attributes both fakes provide
    runner = BotRunner({}, bot=bot, lock=lock)  # type: ignore[arg-type]
    n = {"calls": 0}

    def exploding_cycle(now):
        n["calls"] += 1
        if n["calls"] >= 3:
            runner._stop = True                     # exit after 3 iterations
        raise RuntimeError("feed outage")

    bot.cycle_once = exploding_cycle
    runner.run()
    assert n["calls"] == 3                          # every cycle raised...
    assert lock.refreshes >= 3                      # ...liveness never lapsed
    assert lock.released                            # clean shutdown freed it
