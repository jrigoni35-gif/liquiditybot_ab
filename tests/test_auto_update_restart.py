"""Deploy-restart escalation (auto_update): a graceful 'stop' asks the runner to
exit so the supervisor relaunches it on new code. Live 2026-07-21 a long-lived
runner stopped honoring 'stop', so deploys never reached the running bot — the
repo advanced but the process kept executing stale code. The escalation force-
kills ONLY that runner's pid if the soft stop is ignored past a grace window,
so the supervisor's heartbeat relaunch always lands the deploy. Targeted (one
pid, from the lock) and only after a real deploy + an ignored soft stop.
"""
import json
import time

import scripts.auto_update as au


def _clock(values):
    it = iter(values)
    return lambda: next(it)


# ---------------------------------------------------- pure escalate decision
def test_should_escalate_only_when_same_pid_survives():
    assert au._should_escalate(1234, 1234) is True    # unchanged -> stop ignored
    assert au._should_escalate(1234, 5678) is False   # new pid   -> restarted
    assert au._should_escalate(1234, None) is False    # lock gone -> restarted
    assert au._should_escalate(None, 1234) is False     # no orig  -> can't escalate


# ------------------------------------------------------- runner pid from lock
def test_runner_pid_requires_a_fresh_heartbeat(tmp_path, monkeypatch):
    # W1-8: Windows recycles PIDs. A stale heartbeat means the lock's pid is
    # a crashed/boot-looping runner that may no longer exist AT ALL - 45s
    # later (the force-kill grace window) that pid can belong to the
    # supervisor, a pusher, or an unrelated process. Mirrors
    # remote_control._runner_alive's 60s freshness bound (scripts/
    # remote_control.py:253-256) - no kill target without a live runner.
    monkeypatch.setattr(au, "OUT", tmp_path)
    stale_hb = time.time() - au._HEARTBEAT_FRESH_SEC - 5
    (tmp_path / "runner.lock").write_text(
        json.dumps({"pid": 4321, "heartbeat": stale_hb}))
    assert au._runner_pid() is None            # stale -> no kill target

    fresh_hb = time.time()
    (tmp_path / "runner.lock").write_text(
        json.dumps({"pid": 4321, "heartbeat": fresh_hb}))
    assert au._runner_pid() == 4321             # fresh -> pid returned

    (tmp_path / "runner.lock").write_text("garbage")
    assert au._runner_pid() is None
    (tmp_path / "runner.lock").unlink()
    assert au._runner_pid() is None


def test_escalation_with_stale_heartbeat_never_force_kills(tmp_path, monkeypatch):
    # end-to-end: a stale-heartbeat lock must make the WHOLE escalation path
    # a no-op - _signal_restart must never reach _force_kill (and therefore
    # never taskkill) for a pid it can no longer trust is the live runner.
    monkeypatch.setattr(au, "OUT", tmp_path)
    stale_hb = time.time() - au._HEARTBEAT_FRESH_SEC - 5
    (tmp_path / "runner.lock").write_text(
        json.dumps({"pid": 4321, "heartbeat": stale_hb}))
    kill_calls = []
    monkeypatch.setattr(au, "_force_kill", lambda pid: kill_calls.append(pid))
    monkeypatch.setattr(au, "_FORCE_KILL_AFTER_SEC", 0.01)
    monkeypatch.setattr(au, "_FORCE_KILL_POLL_SEC", 0.01)
    au._signal_restart()
    assert kill_calls == []


# --------------------------------------------------- escalation orchestration
def test_stuck_runner_is_force_killed():
    killed = []
    outcome = au._escalate_if_stuck(
        999, read_pid=lambda: 999, wait_sec=3, poll_sec=1,
        kill_fn=killed.append, sleep_fn=lambda s: None, now_fn=_clock([0, 1, 2, 3]))
    assert outcome == "force_killed" and killed == [999]


def test_clean_restart_is_not_force_killed():
    killed = []
    outcome = au._escalate_if_stuck(
        999, read_pid=lambda: 12345, wait_sec=3, poll_sec=1,   # pid changed = new runner
        kill_fn=killed.append, sleep_fn=lambda s: None, now_fn=_clock([0, 1]))
    assert outcome == "restarted" and killed == []


def test_lock_released_counts_as_restarted():
    killed = []
    outcome = au._escalate_if_stuck(
        999, read_pid=lambda: None, wait_sec=3, poll_sec=1,     # lock gone = exited
        kill_fn=killed.append, sleep_fn=lambda s: None, now_fn=_clock([0, 1]))
    assert outcome == "restarted" and killed == []


def test_no_pid_never_escalates():
    killed = []
    outcome = au._escalate_if_stuck(
        None, read_pid=lambda: 1, wait_sec=3, poll_sec=1,
        kill_fn=killed.append, sleep_fn=lambda s: None, now_fn=_clock([0]))
    assert outcome == "no_pid" and killed == []


# ------------------------------------------------------ force-kill is fail-safe
def test_force_kill_never_raises(monkeypatch):
    # a dead/bogus pid must not raise out of the deploy path
    au._force_kill(2_000_000_000)   # almost certainly not a live pid; must be quiet


# -------------------------------- W1-8: process identity before the kill ----
class _FakeProc:
    def __init__(self, rc=0, out=""):
        self.returncode, self.stdout = rc, out


def test_pid_is_runner_true_when_cmdline_matches(monkeypatch):
    monkeypatch.setattr(au.subprocess, "run",
                        lambda *a, **k: _FakeProc(0, "python runner.py --live"))
    assert au._pid_is_runner(4321) is True


def test_pid_is_runner_false_when_cmdline_does_not_match(monkeypatch):
    # a recycled pid now held by some unrelated process
    monkeypatch.setattr(au.subprocess, "run",
                        lambda *a, **k: _FakeProc(0, "some_other_process.exe"))
    assert au._pid_is_runner(4321) is False


def test_pid_is_runner_false_on_spawn_failure(monkeypatch):
    # fail-safe: identity cannot be confirmed -> treat as NOT the runner
    def _boom(*a, **k):
        raise OSError("spawn failed")
    monkeypatch.setattr(au.subprocess, "run", _boom)
    assert au._pid_is_runner(4321) is False


def test_force_kill_skips_the_kill_when_identity_unconfirmed(monkeypatch):
    # a pid that no longer identifies as runner.py must NEVER be killed, even
    # if it somehow got this far (defense-in-depth behind the heartbeat guard)
    monkeypatch.setattr(au, "_pid_is_runner", lambda pid: False)
    calls = []
    monkeypatch.setattr(au.subprocess, "run",
                        lambda *a, **k: calls.append(a) or _FakeProc(0, ""))
    au._force_kill(4321)
    assert calls == []                      # taskkill never invoked


def test_force_kill_proceeds_when_identity_confirmed(monkeypatch):
    monkeypatch.setattr(au, "_pid_is_runner", lambda pid: True)
    monkeypatch.setattr(au.os, "name", "nt")
    calls = []
    monkeypatch.setattr(au.subprocess, "run",
                        lambda *a, **k: calls.append(a) or _FakeProc(0, ""))
    au._force_kill(4321)
    assert any("taskkill" in str(c) for c in calls)
