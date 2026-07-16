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


def test_cold_start_claim_is_atomic_and_durable(tmp_path):
    # the winner's record is written AND fsync'd into the file before acquire()
    # returns None, so a racing second launch that reads the file sees a real
    # holder (not an empty file) and refuses.
    p = tmp_path / "runner.lock"
    a = SingleInstanceLock(str(p), stale_after_sec=30.0)
    a.pid = 111
    assert a.acquire() is None
    rec = json.loads(p.read_text(encoding="utf-8"))
    assert rec["pid"] == 111 and rec["heartbeat"] > 0
    b = SingleInstanceLock(str(p), stale_after_sec=30.0)
    b.pid = 222
    assert b.acquire()["pid"] == 111               # O_EXCL create fails -> refuse


def test_cold_start_race_does_not_let_every_racer_win(tmp_path):
    # the OLD read-then-write let EVERY simultaneous launch win (both wrote
    # their pid and returned None, then drove cycle_once for up to LOST_LIMIT
    # cycles). The atomic O_CREAT|O_EXCL claim must let far fewer than N win.
    # Threaded to actually exercise the syscall-level race, with a barrier so
    # all racers hit acquire() together.
    import threading
    p = str(tmp_path / "runner.lock")
    barrier = threading.Barrier(8)
    results, guard = [], threading.Lock()

    def worker(i):
        lk = SingleInstanceLock(p, stale_after_sec=30.0)
        lk.pid = 1000 + i
        barrier.wait()
        r = lk.acquire()
        with guard:
            results.append(r)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    winners = [r for r in results if r is None]
    assert 1 <= len(winners) < 8, \
        f"atomic claim must not let every racer win (won: {len(winners)}/8)"


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
        self.forfeited = False      # interface parity with SingleInstanceLock

    def refresh(self):
        self.refreshes += 1
        return True                 # this stub always owns the lock

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


# --- ownership-aware refresh (RT-010): duplicates must lose, then exit ----

def test_refresh_never_overwrites_fresh_foreign_lock(tmp_path):
    """Two live runners used to flip-flop the lockfile every cycle (each
    unconditionally rewriting {pid, heartbeat}), so both believed they
    held it and the duplicate ran forever - observed live 2026-07-14 as
    THREE coexisting runners. A fresh foreign record must be sacred."""
    from core.runtime import SingleInstanceLock
    a = SingleInstanceLock(str(tmp_path / "r.lock"), stale_after_sec=30)
    b = SingleInstanceLock(str(tmp_path / "r.lock"), stale_after_sec=30)
    a.pid, b.pid = 111, 222
    assert a.acquire() is None                  # A owns
    assert a.refresh() is True
    assert b.refresh() is False                 # B must NOT steal
    import json
    holder = json.load(open(tmp_path / "r.lock"))
    assert holder["pid"] == 111, "foreign fresh lock was overwritten"
    assert a.refresh() is True                  # A unaffected


def test_duplicate_forfeits_after_consecutive_losses(tmp_path):
    from core.runtime import SingleInstanceLock
    a = SingleInstanceLock(str(tmp_path / "r.lock"), stale_after_sec=30)
    b = SingleInstanceLock(str(tmp_path / "r.lock"), stale_after_sec=30)
    a.pid, b.pid = 111, 222
    a.acquire()
    for i in range(SingleInstanceLock.LOST_LIMIT):
        assert not b.forfeited or i == SingleInstanceLock.LOST_LIMIT
        b.refresh()
    assert b.forfeited, "duplicate must forfeit after LOST_LIMIT losses"
    assert not a.forfeited
    # one successful refresh (e.g. after the peer died) resets the count
    import json
    import time
    json.dump({"pid": 111, "heartbeat": time.time() - 999},
              open(tmp_path / "r.lock", "w"))    # peer went stale
    assert b.refresh() is True
    assert b.lost_count == 0 and not b.forfeited


def test_stale_takeover_still_works(tmp_path):
    import json
    import time
    from core.runtime import SingleInstanceLock
    lockfile = tmp_path / "r.lock"
    json.dump({"pid": 999, "heartbeat": time.time() - 120},
              open(lockfile, "w"))
    b = SingleInstanceLock(str(lockfile), stale_after_sec=30)
    b.pid = 222
    assert b.acquire() is None, "stale holder must be replaceable"
    assert json.load(open(lockfile))["pid"] == 222
