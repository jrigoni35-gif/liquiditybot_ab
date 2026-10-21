"""pc_supervisor single-instance lock — one supervisor per outputs/ dir,
without stranding the machine supervisor-less.

Round 1 (2026-07-22 02:00): TWO full supervisor+runner stacks. Task
Scheduler's IgnoreNew only dedups instances IT started; the source-change
handoff spawned a detached copy the task could not see. Fix: the supervisor
holds the same heartbeat lock the runner uses.

Round 2 (2026-07-21 22:02 PC time): the lock's exit-on-sight refusal had a
liveness hole — a force-killed supervisor leaves a FROZEN-but-recent
heartbeat, so every relaunch inside the stale window refused with rc 0,
Task Scheduler read the clean exit as success, and NO supervisor ran at
all. And because spawned children inherited the task's JOB OBJECT, the
task instance read "Running" while any runner/pusher lived, so IgnoreNew
dropped every Start request. This suite pins the full contract:

  * a peer whose heartbeat ADVANCES is genuinely alive -> back off;
  * a frozen-but-recent heartbeat is a DEAD holder -> wait it out, take over;
  * a stale lock is reclaimed immediately; release on exit is ownership-aware;
  * the source-change handoff releases the lock BEFORE spawning;
  * child spawns request CREATE_BREAKAWAY_FROM_JOB (with in-job fallback);
  * a booting child is spawned at most once per boot-grace window.
"""
import json
import os
import sys
import threading
import time

import pytest

import scripts.pc_supervisor as sup


def _wire(monkeypatch, tmp_path):
    """Point the supervisor at an isolated outputs/ and neuter every side
    effect except the lock + spawn logic under test."""
    monkeypatch.setattr(sup, "OUT", tmp_path)
    monkeypatch.setattr(sup, "_materialise_token", lambda: None)
    monkeypatch.setattr(sup, "_telemetry_ready", lambda: False)
    monkeypatch.setattr(sup, "_maybe_launch_opend", lambda: "disabled")
    monkeypatch.setattr(sup, "_auto_update_due", lambda: False)
    monkeypatch.setattr(sup, "_stamp_due", lambda *a, **k: False)
    monkeypatch.setattr(sup, "_fresh", lambda *a, **k: True)   # runner alive
    monkeypatch.setattr(sup, "IS_WIN", False)                  # skip 5b/5c
    # fast lock timing so the wait-and-verify paths run in ~1s
    monkeypatch.setattr(sup, "STALE_SEC", 0.6)
    monkeypatch.setattr(sup, "LOCK_POLL_SEC", 0.05)


# ---- wait-and-verify acquisition -------------------------------------------

# timing: the beater thread must land a heartbeat every 0.05s to stay
# under the 0.6s staleness horizon - a saturated battery can starve it
# past 0.6s and the live peer reads as stale (falsely acquirable).
@pytest.mark.timing
def test_advancing_heartbeat_means_live_peer_and_refusal(monkeypatch,
                                                         tmp_path):
    _wire(monkeypatch, tmp_path)
    lockfile = tmp_path / "pc_supervisor.lock"
    lockfile.write_text(json.dumps({"pid": 999999,
                                    "heartbeat": time.time()}),
                        encoding="utf-8")
    stop = threading.Event()

    def _peer_beats():
        while not stop.is_set():          # a live peer refreshes its lock
            lockfile.write_text(json.dumps({"pid": 999999,
                                            "heartbeat": time.time()}),
                                encoding="utf-8")
            time.sleep(0.05)
    t = threading.Thread(target=_peer_beats, daemon=True)
    t.start()
    try:
        lock = sup.SingleInstanceLock(path=str(lockfile),
                                      stale_after_sec=0.6)
        assert sup._acquire_or_wait(lock, poll_sec=0.05) is False
    finally:
        stop.set()
        t.join(timeout=2.0)
    peer = json.loads(lockfile.read_text())
    assert peer["pid"] == 999999          # live peer's lock never touched


def test_frozen_recent_heartbeat_is_a_dead_holder_taken_over(monkeypatch,
                                                             tmp_path):
    # the force-kill window: heartbeat is RECENT but never advances (holder
    # was killed). Exit-on-sight refused here and stranded the box; the
    # wait-and-verify path must out-wait the freeze and take over.
    _wire(monkeypatch, tmp_path)
    lockfile = tmp_path / "pc_supervisor.lock"
    lockfile.write_text(json.dumps({"pid": 999999,
                                    "heartbeat": time.time()}),
                        encoding="utf-8")
    lock = sup.SingleInstanceLock(path=str(lockfile), stale_after_sec=0.6)
    assert sup._acquire_or_wait(lock, poll_sec=0.05) is True
    cur = json.loads(lockfile.read_text())
    assert cur["pid"] == sup.os.getpid()  # we own it now


# timing: UPPER-bounds the reclaim at 0.5s of wall clock.
@pytest.mark.timing
def test_stale_lock_is_reclaimed_immediately(monkeypatch, tmp_path):
    _wire(monkeypatch, tmp_path)
    lockfile = tmp_path / "pc_supervisor.lock"
    lockfile.write_text(json.dumps({"pid": 999999,
                                    "heartbeat": time.time() - 999.0}),
                        encoding="utf-8")
    lock = sup.SingleInstanceLock(path=str(lockfile), stale_after_sec=0.6)
    t0 = time.time()
    assert sup._acquire_or_wait(lock, poll_sec=0.05) is True
    assert time.time() - t0 < 0.5         # no pointless waiting on stale


def test_main_releases_lock_on_exit(monkeypatch, tmp_path):
    _wire(monkeypatch, tmp_path)

    def _one_tick():
        cur = json.loads((tmp_path / "pc_supervisor.lock").read_text())
        assert cur["pid"] == sup.os.getpid()
        raise SystemExit(0)
    monkeypatch.setattr(sup, "tick", _one_tick)
    with pytest.raises(SystemExit):
        sup.main()
    assert not (tmp_path / "pc_supervisor.lock").exists()


def test_handoff_releases_lock_before_spawning_replacement(monkeypatch,
                                                           tmp_path):
    _wire(monkeypatch, tmp_path)
    order = []
    lock = sup.SingleInstanceLock(path=str(tmp_path / "pc_supervisor.lock"),
                                  stale_after_sec=0.6)
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


# ---- job-object escape + boot-grace throttle --------------------------------

def test_spawn_requests_breakaway_from_job_with_fallback():
    # Task Scheduler tracks the task via a job object every child inherits;
    # without breakaway the instance reads "Running" while any child lives
    # and IgnoreNew drops every Start. The spawn must TRY breakaway
    # (0x01000000) and fall back to in-job when the job forbids it.
    src = (sup.ROOT / "scripts" / "pc_supervisor.py").read_text(
        encoding="utf-8")
    assert "0x01000000" in src
    assert src.index("| 0x01000000") < src.index(", base)")   # tried FIRST


def test_spawn_gated_once_per_boot_grace_window(monkeypatch, tmp_path):
    _wire(monkeypatch, tmp_path)
    monkeypatch.setattr(sup, "BOOT_GRACE_SEC", 100.0)
    monkeypatch.setattr(sup, "_last_spawn", {})
    spawned = []
    monkeypatch.setattr(sup, "_spawn", lambda argv, own_log=True:
                        spawned.append(argv[1]))
    assert sup._spawn_gated("runner", ["py", "runner.py"]) is True
    assert sup._spawn_gated("runner", ["py", "runner.py"]) is False
    assert spawned == ["runner.py"]                # one spawn, not two
    # a different child has its own window
    assert sup._spawn_gated("gc_pusher", ["py", "gc_pusher.py"]) is True
    # window expiry re-arms the child
    sup._last_spawn["runner"] = time.time() - 101.0
    assert sup._spawn_gated("runner", ["py", "runner.py"]) is True


def test_tick_respawns_stale_runner_at_most_once_per_window(monkeypatch,
                                                            tmp_path):
    # the live failure: a booting runner's heartbeat stays stale for minutes
    # and the old tick spawned another copy every 30s (2x runner observed)
    _wire(monkeypatch, tmp_path)
    monkeypatch.setattr(sup, "_fresh", lambda *a, **k: False)  # always stale
    monkeypatch.setattr(sup, "_source_changed", lambda: False)
    monkeypatch.setattr(sup, "BOOT_GRACE_SEC", 100.0)
    monkeypatch.setattr(sup, "_last_spawn", {})
    spawned = []
    monkeypatch.setattr(sup, "_spawn", lambda argv, own_log=True:
                        spawned.append(argv[1]))
    sup.tick()
    sup.tick()                                     # 30s later, still booting
    assert spawned.count("runner.py") == 1         # gated, not doubled


def _stale_runner_tick(monkeypatch, tmp_path, holder_pid, status_age):
    """One tick with status.json `status_age` seconds old and runner.lock
    held by `holder_pid`; returns the children spawned."""
    _wire(monkeypatch, tmp_path)
    monkeypatch.setattr(sup, "_fresh", lambda *a, **k: False)
    monkeypatch.setattr(sup, "_source_changed", lambda: False)
    monkeypatch.setattr(sup, "_last_spawn", {})
    monkeypatch.setattr(sup, "_slow_logged_at", 0.0)
    (tmp_path / "status.json").write_text(json.dumps(
        {"written_at": time.time() - status_age}), encoding="utf-8")
    (tmp_path / "runner.lock").write_text(json.dumps(
        {"pid": holder_pid, "heartbeat": time.time() - status_age}),
        encoding="utf-8")
    spawned = []
    monkeypatch.setattr(sup, "_spawn", lambda argv, own_log=True:
                        spawned.append(argv[1]))
    sup.tick()
    return spawned


def _dead_pid():
    import subprocess
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def test_pid_alive_probe_is_truthful_and_never_kills():
    # os.kill(pid, 0) on Windows TERMINATES the target; the probe must not
    # (this test process surviving its own probe is the pin)
    assert sup._pid_alive(os.getpid()) is True
    assert sup._pid_alive(_dead_pid()) is False
    assert sup._pid_alive(0) is False


def test_tick_waits_out_a_slow_but_live_runner(monkeypatch, tmp_path):
    # 2026-10-20: saturated disk, live runner wrote status.json late, and a
    # duplicate booted every ~3 min (lock contention + audit-chain fork)
    assert _stale_runner_tick(monkeypatch, tmp_path, os.getpid(),
                              status_age=200.0) == []


def test_tick_relaunches_past_the_wedge_ceiling(monkeypatch, tmp_path):
    # alive pid but stale beyond RUNNER_WEDGE_SEC (wedged, or a reused pid)
    assert _stale_runner_tick(
        monkeypatch, tmp_path, os.getpid(),
        status_age=sup.RUNNER_WEDGE_SEC + 60.0) == ["runner.py"]


def test_tick_relaunches_when_lock_holder_is_dead(monkeypatch, tmp_path):
    assert _stale_runner_tick(monkeypatch, tmp_path, _dead_pid(),
                              status_age=200.0) == ["runner.py"]


def test_tick_relaunches_on_sentinel_lock(monkeypatch, tmp_path):
    # core/runtime.py's {"pid": "initializing"} carries no real pid
    assert _stale_runner_tick(monkeypatch, tmp_path, "initializing",
                              status_age=200.0) == ["runner.py"]


def test_tick_relaunches_with_no_lock_file(monkeypatch, tmp_path):
    _stale_runner_tick(monkeypatch, tmp_path, os.getpid(), status_age=200.0)
    (tmp_path / "runner.lock").unlink()
    monkeypatch.setattr(sup, "_last_spawn", {})
    spawned = []
    monkeypatch.setattr(sup, "_spawn", lambda argv, own_log=True:
                        spawned.append(argv[1]))
    sup.tick()
    assert spawned == ["runner.py"]


def test_lock_stale_window_exceeds_tick_cadence():
    # the heartbeat refreshes once per CHECK_SEC tick; a stale window at or
    # below the cadence would let a healthy supervisor's own lock expire
    # between ticks and invite a takeover — the doubling this lock prevents
    assert sup.STALE_SEC > 2 * sup.CHECK_SEC
