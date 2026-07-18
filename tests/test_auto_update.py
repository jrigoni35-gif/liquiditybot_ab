"""tests/test_auto_update.py — the test-gated self-updater's decision core.

decide() is the whole safety gate expressed as pure logic, so it is the piece
worth pinning: a bad branch here is the difference between "protect the
operator's local config edits" and "silently clobber them," or between "only
touch the live checkout after the incoming code is battery-green" and "pull
blindly." The subprocess/worktree plumbing is exercised live on the PC; this
locks the branch table.

Also pinned: the single-updater lock (the supervisor's 15-min cadence plus a
manual run must never stack two batteries or race the fast-forward) and the
fast default cadence itself.
"""
import json
import time

import scripts.auto_update as au
from scripts.auto_update import decide


def test_no_remote_is_current():
    # offline / failed rev-parse -> empty remote -> never act
    assert decide("abc123", "", False) == "current"


def test_equal_heads_is_current():
    assert decide("abc123", "abc123", False) == "current"


def test_equal_heads_current_even_when_dirty():
    # nothing to pull -> local edits are irrelevant, no action
    assert decide("abc123", "abc123", True) == "current"


def test_new_commits_clean_tree_gates_on_battery():
    assert decide("abc123", "def456", False) == "test"


def test_new_commits_dirty_tree_is_skipped():
    # operator has uncommitted edits (e.g. the debug flag) -> protect them
    assert decide("abc123", "def456", True) == "dirty"


def test_dirty_probe_ignores_untracked_files(tmp_path, monkeypatch):
    # live 2026-07-17: an untracked .claude/skills/ dir made every update
    # refuse as 'dirty' — and git stash can't clear untracked, so the
    # operator was deadlocked. Only TRACKED modifications may block.
    monkeypatch.setattr(au, "OUT", tmp_path)
    calls = []

    def fake_git(*args, cwd=None, timeout=120):
        calls.append(args)
        if args[0] == "fetch":
            return 0, ""
        if args[0] == "rev-parse":
            return 0, "same"                    # local == remote -> current
        if args[0] == "status":
            return 0, ""
        return 0, ""
    monkeypatch.setattr(au, "_git", fake_git)
    assert au.update_once() == "current"
    status_calls = [c for c in calls if c[0] == "status"]
    assert status_calls and "--untracked-files=no" in status_calls[0]


# ---------------- single-updater lock ----------------

def test_live_peer_lock_means_busy_and_no_git(tmp_path, monkeypatch):
    # a fresh foreign lock (another updater mid-battery) -> refuse, and never
    # even fetch — busy must be a pure no-op
    monkeypatch.setattr(au, "OUT", tmp_path)
    (tmp_path / "auto_update.lock").write_text(
        json.dumps({"pid": 999999, "heartbeat": time.time()}),
        encoding="utf-8")

    def _boom(*a, **k):
        raise AssertionError("git must not run while another updater holds "
                             "the lock")
    monkeypatch.setattr(au, "_git", _boom)
    assert au.update_once() == "busy"
    # the peer's lock is untouched (release is ownership-aware)
    assert (tmp_path / "auto_update.lock").exists()


def test_stale_lock_is_broken_and_released(tmp_path, monkeypatch):
    # a crashed updater's lock (heartbeat older than LOCK_STALE_SEC) must not
    # wedge updates forever: it is reclaimed, the body runs, and the lock is
    # released afterwards even on an early-return path
    monkeypatch.setattr(au, "OUT", tmp_path)
    (tmp_path / "auto_update.lock").write_text(
        json.dumps({"pid": 999999,
                    "heartbeat": time.time() - au.LOCK_STALE_SEC - 60}),
        encoding="utf-8")
    monkeypatch.setattr(au, "_git", lambda *a, **k: (1, "offline"))
    assert au.update_once() == "fetch_failed"
    assert not (tmp_path / "auto_update.lock").exists()


def test_busy_is_a_clean_exit():
    # the supervisor treats busy as "nothing wrong", not a failed update
    assert "busy" in au.OK_OUTCOMES


def test_lock_staleness_outlives_battery():
    # the battery may run up to 1200s; a lock declared stale before a healthy
    # battery finishes would let a second updater stack on the first
    assert au.LOCK_STALE_SEC > 1200


def test_supervisor_default_cadence_is_fast(monkeypatch):
    # the whole point of the fast cadence: a push self-deploys in minutes.
    # (env override still honoured; only the default is pinned here)
    import importlib

    import scripts.pc_supervisor as sup
    monkeypatch.delenv("LB_AUTO_UPDATE_SEC", raising=False)
    sup = importlib.reload(sup)
    assert sup.UPDATE_SEC == 900.0


def test_outcome_stamp_written_and_fail_safe(monkeypatch, tmp_path):
    """2026-07-18: the updater failed silently for 6+ hours with no
    off-box observable saying WHICH outcome it kept hitting. Every
    attempt must stamp outputs/auto_update_state.json; a stamp failure
    must never break the update itself."""
    import scripts.auto_update as au
    monkeypatch.setattr(au, "OUT", tmp_path)
    monkeypatch.setattr(au, "_git", lambda *a, **k: (0, "abc1234"))
    au._record_outcome("rejected")
    import json
    st = json.loads((tmp_path / "auto_update_state.json").read_text())
    assert st["outcome"] == "rejected" and st["head"] == "abc1234"
    assert st["ts"] > 0
    # stamp failure is swallowed (update result still returned by caller)
    monkeypatch.setattr(au, "OUT", tmp_path / "nope" / "deeper")
    au._record_outcome("current")            # must not raise
