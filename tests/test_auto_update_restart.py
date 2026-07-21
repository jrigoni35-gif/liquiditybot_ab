"""Deploy-restart escalation (auto_update): a graceful 'stop' asks the runner to
exit so the supervisor relaunches it on new code. Live 2026-07-21 a long-lived
runner stopped honoring 'stop', so deploys never reached the running bot — the
repo advanced but the process kept executing stale code. The escalation force-
kills ONLY that runner's pid if the soft stop is ignored past a grace window,
so the supervisor's heartbeat relaunch always lands the deploy. Targeted (one
pid, from the lock) and only after a real deploy + an ignored soft stop.
"""
import json

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
def test_runner_pid_reads_the_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(au, "OUT", tmp_path)
    (tmp_path / "runner.lock").write_text(json.dumps({"pid": 4321, "heartbeat": 1.0}))
    assert au._runner_pid() == 4321
    (tmp_path / "runner.lock").write_text("garbage")
    assert au._runner_pid() is None
    (tmp_path / "runner.lock").unlink()
    assert au._runner_pid() is None


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
