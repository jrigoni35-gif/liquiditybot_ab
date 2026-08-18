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


def test_equal_heads_dirty_tree_is_reported_not_hidden():
    # 2026-07-27 divergence audit: equal heads used to win over dirty, so a
    # PC running locally-edited code reported "current" off-box — the ONE
    # channel that could reveal operator edits said everything matched git.
    # Nothing to pull still means no action, but the OUTCOME must tell the
    # truth: the stamp is observability, not just a deploy decision.
    assert decide("abc123", "abc123", True) == "dirty"
    assert decide("abc123", "", True) == "dirty"     # offline, still dirty
    assert "dirty" in au.OK_OUTCOMES     # visible, but never an alarm state


def test_new_commits_clean_tree_gates_on_battery():
    assert decide("abc123", "def456", False) == "test"


def test_local_ahead_of_remote_is_never_deployed():
    # live 2026-07-21: the box was deliberately on a feature-branch tip while
    # the updater compared against origin/main (an ANCESTOR). local != remote
    # -> "test" every 15 min -> full battery + a NO-OP ff + a runner bounce,
    # forever — an endless reboot loop that starved signal persistence.
    # Ahead-of-remote must be a clean no-op, and it wins over dirty (no
    # deploy is contemplated at all, so local edits are irrelevant).
    assert decide("abc123", "def456", False, remote_is_ancestor=True) == "ahead"
    assert decide("abc123", "def456", True, remote_is_ancestor=True) == "ahead"
    assert "ahead" in au.OK_OUTCOMES              # supervisor: nothing wrong


def test_diverged_histories_produce_new_outcome():
    # W1-7: PC-side commits (or an upstream force-push) can leave local and
    # remote with NEITHER an ancestor of the other. This must NOT fall
    # through to "test" - that gated the battery every 15 min forever (green
    # battery, then git merge --ff-only always fails: "ff_failed"), an
    # endless full-CPU loop that never deploys anything.
    assert decide("abc123", "def456", False,
                  remote_is_ancestor=False, local_is_ancestor=False) == "diverged"
    # dirty-or-not is irrelevant once diverged - no ff is even attemptable
    assert decide("abc123", "def456", True,
                  remote_is_ancestor=False, local_is_ancestor=False) == "diverged"


def test_diverged_is_not_an_ok_outcome():
    assert "diverged" not in au.OK_OUTCOMES


def test_local_is_ancestor_default_preserves_existing_callers():
    # every pre-existing call site omits local_is_ancestor - the default
    # must reproduce EXACT pre-fix behavior (CLAUDE.md invariant 7: extend
    # signatures without changing behavior for existing callers)
    assert decide("abc123", "def456", False) == "test"
    assert decide("abc123", "def456", True) == "dirty"


def _no_pin(monkeypatch, tmp_path):
    """Point the updater at a config with NO deploy pin (the repo's real
    config.json now ships system.deploy_branch, so tests of the lower
    fallback rungs must isolate from it) and clear the env override."""
    monkeypatch.setattr(au, "CONFIG_PATH", tmp_path / "absent_config.json")
    monkeypatch.delenv("LB_UPDATE_BRANCH", raising=False)


def test_deploy_branch_follows_checkout_and_falls_back_detached(
        monkeypatch, tmp_path):
    _no_pin(monkeypatch, tmp_path)
    monkeypatch.setattr(au, "_git",
                        lambda *a, **k: (0, "claude/some-feature"))
    assert au._deploy_branch() == "claude/some-feature"
    monkeypatch.setattr(au, "_git", lambda *a, **k: (0, "HEAD"))   # detached
    assert au._deploy_branch() == au.BRANCH
    monkeypatch.setattr(au, "_git", lambda *a, **k: (1, "boom"))
    assert au._deploy_branch() == au.BRANCH


def test_deploy_branch_config_pin_beats_checkout(monkeypatch, tmp_path):
    # the repo-declared channel wins over whatever branch the box has
    # checked out - this is the mechanism that moves the PC to main
    # without hands on the machine
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"system": {"deploy_branch": "main"}}),
                   encoding="utf-8")
    monkeypatch.setattr(au, "CONFIG_PATH", cfg)
    monkeypatch.delenv("LB_UPDATE_BRANCH", raising=False)
    monkeypatch.setattr(au, "_git",
                        lambda *a, **k: (0, "claude/remote-control-e3h815"))
    assert au._deploy_branch() == "main"


def test_deploy_branch_env_override_beats_config_pin(monkeypatch, tmp_path):
    # a box deliberately run off-channel keeps that choice via env - no
    # dirty-tree cost (editing tracked config.json would block updates)
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"system": {"deploy_branch": "main"}}),
                   encoding="utf-8")
    monkeypatch.setattr(au, "CONFIG_PATH", cfg)
    monkeypatch.setenv("LB_UPDATE_BRANCH", "release/pinned")
    monkeypatch.setattr(au, "_git", lambda *a, **k: (0, "whatever"))
    assert au._deploy_branch() == "release/pinned"


def test_deploy_branch_rejects_malformed_names(monkeypatch, tmp_path):
    # a name starting with '-' would parse as a git OPTION in the updater's
    # fixed argv; malformed env AND config pins both fall through to the
    # checkout rung rather than reaching git
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"system": {"deploy_branch": "-upload-pack"}}),
                   encoding="utf-8")
    monkeypatch.setattr(au, "CONFIG_PATH", cfg)
    monkeypatch.setenv("LB_UPDATE_BRANCH", "--force bad name")
    monkeypatch.setattr(au, "_git", lambda *a, **k: (0, "claude/checkout"))
    assert au._deploy_branch() == "claude/checkout"


def test_deploy_branch_unreadable_config_falls_through(monkeypatch, tmp_path):
    # corrupt config must never wedge the updater (fail-safe rule): broken
    # JSON == no pin
    cfg = tmp_path / "config.json"
    cfg.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(au, "CONFIG_PATH", cfg)
    monkeypatch.delenv("LB_UPDATE_BRANCH", raising=False)
    monkeypatch.setattr(au, "_git", lambda *a, **k: (0, "claude/checkout"))
    assert au._deploy_branch() == "claude/checkout"


def test_shipped_config_pins_main():
    # the repo's own config.json declares the deploy channel: main. This is
    # what makes session work merged to main auto-deploy to the PC.
    shipped = json.loads((au.ROOT / "config.json").read_text(encoding="utf-8"))
    assert shipped["system"]["deploy_branch"] == "main"


def test_update_once_ahead_never_runs_battery_or_restart(tmp_path,
                                                         monkeypatch):
    _no_pin(monkeypatch, tmp_path)     # this test pins the CHECKOUT rung
    monkeypatch.setattr(au, "OUT", tmp_path)
    calls = []

    def fake_git(*args, cwd=None, timeout=120):
        calls.append(args)
        if args[0] == "rev-parse" and args[1] == "--abbrev-ref":
            return 0, "feature"
        if args == ("rev-parse", "HEAD"):
            return 0, "tip_local"
        if args[0] == "rev-parse":
            return 0, "old_remote"                 # origin/feature is behind
        if args[0] == "merge-base":
            return 0, ""                           # remote IS our ancestor
        return 0, ""
    monkeypatch.setattr(au, "_git", fake_git)
    monkeypatch.setattr(au, "battery_passes",
                        lambda wt: (_ for _ in ()).throw(
                            AssertionError("battery must not run when ahead")))
    monkeypatch.setattr(au, "_signal_restart",
                        lambda: (_ for _ in ()).throw(
                            AssertionError("runner must not bounce when ahead")))
    assert au.update_once() == "ahead"
    assert not any(c[0] in ("worktree", "merge") for c in calls)
    # and the fetch targeted the CHECKED-OUT branch, not hardcoded main
    assert ("fetch", "origin", "feature") in calls


def test_update_once_diverged_never_runs_battery_or_ff(tmp_path, monkeypatch):
    # W1-7 end-to-end: diverged histories must short-circuit BEFORE the
    # worktree/battery/merge machinery ever runs - the whole point is to stop
    # burning a full 1200s+ battery every cadence on inputs that can never
    # change the outcome.
    monkeypatch.setattr(au, "OUT", tmp_path)
    calls = []

    def fake_git(*args, cwd=None, timeout=120):
        calls.append(args)
        if args[0] == "rev-parse" and args[1] == "--abbrev-ref":
            return 0, "main"
        if args == ("rev-parse", "HEAD"):
            return 0, "local_sha"
        if args[0] == "rev-parse":
            return 0, "remote_sha"
        if args[0] == "status":
            return 0, ""                       # clean tree
        if args[0] == "merge-base":
            return 1, ""                       # neither direction is ancestor
        return 0, ""
    monkeypatch.setattr(au, "_git", fake_git)
    monkeypatch.setattr(au, "battery_passes",
                        lambda wt: (_ for _ in ()).throw(
                            AssertionError("battery must not run when diverged")))
    monkeypatch.setattr(au, "_signal_restart",
                        lambda: (_ for _ in ()).throw(
                            AssertionError("runner must not bounce when diverged")))
    assert au.update_once() == "diverged"
    assert not any(c[0] in ("worktree", "merge") for c in calls)


def test_noop_fast_forward_never_bounces_the_runner(tmp_path, monkeypatch):
    # belt to the ancestor guard's braces: even if the deploy path is
    # reached, an "Already up to date" ff (HEAD unchanged) must not restart
    monkeypatch.setattr(au, "OUT", tmp_path)

    def fake_git(*args, cwd=None, timeout=120):
        if args[0] == "rev-parse" and args[1] == "--abbrev-ref":
            return 0, "feature"
        if args == ("rev-parse", "HEAD"):
            return 0, "same_head"                  # never moves
        if args[0] == "rev-parse":
            return 0, "different_remote"
        if args[0] == "merge-base" and args[2] == "HEAD":
            return 0, ""                           # HEAD IS ancestor of origin
                                                    # (legit ff, not diverged)
        if args[0] == "merge-base":
            return 1, ""                           # origin NOT ancestor -> deploy path
        return 0, ""
    monkeypatch.setattr(au, "_git", fake_git)
    monkeypatch.setattr(au, "battery_passes", lambda wt: True)
    monkeypatch.setattr(au, "_signal_restart",
                        lambda: (_ for _ in ()).throw(
                            AssertionError("no-op ff must not bounce the runner")))
    assert au.update_once() == "current"


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


def test_record_outcome_uses_deploy_branch_not_hardcoded_main(monkeypatch,
                                                               tmp_path):
    """W2-21: _record_outcome stamped 'remote' from origin/{BRANCH}
    (BRANCH='main') unconditionally, while the deploy path follows
    _deploy_branch(). On a branch-checked-out box the stamped remote rev
    came from a branch the box never even fetches (permanently diverging
    from the deploy observable's 'head' rev — reads off-box as a stuck
    deploy) and an unfetched origin/main returns silently empty."""
    import scripts.auto_update as au
    monkeypatch.setattr(au, "OUT", tmp_path)
    monkeypatch.setattr(au, "_deploy_branch", lambda: "claude/feature-x")

    def _fake_git(*args, **kwargs):
        if args == ("rev-parse", "--short", "HEAD"):
            return (0, "aaa1111")
        if args == ("rev-parse", "--short", "origin/claude/feature-x"):
            return (0, "bbb2222")
        if args == ("rev-parse", "--short", "origin/main"):
            return (0, "ccc3333")      # wrong branch's rev - must not be used
        return (1, "unexpected")
    monkeypatch.setattr(au, "_git", _fake_git)
    au._record_outcome("updated")
    st = json.loads((tmp_path / "auto_update_state.json").read_text())
    assert st["remote"] == "bbb2222"
    assert st.get("remote_branch") == "claude/feature-x"


# ---- the pre-deploy replay gate: targets LIVE recordings, fails safe --------
class _FakeProc:
    def __init__(self, rc, out=""):
        self.returncode, self.stdout = rc, out


def test_replay_gate_targets_live_recordings_determinism_only(monkeypatch):
    from pathlib import Path
    captured = {}

    def _fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return _FakeProc(0, "XV-001: no recordings present - gate dormant")

    monkeypatch.setattr(au.subprocess, "run", _fake_run)
    assert au._replay_gate_passes(Path("/tmp/wt"), "python") is True
    # validates the LIVE checkout's recordings (absolute path), not the worktree,
    # and skips reconcile (cross-version P&L would false-fail intentional changes)
    assert "--determinism-only" in captured["cmd"]
    rec = captured["cmd"][captured["cmd"].index("--recording-dir") + 1]
    assert rec == str((au.OUT / "recordings").resolve())


def test_replay_gate_verdict_false_on_nonzero(monkeypatch):
    # the verdict function still reports FAIL on a nonzero gate — it is now
    # consumed as ADVISORY by battery_passes (below), not as a hard veto
    from pathlib import Path
    monkeypatch.setattr(au.subprocess, "run",
                        lambda *a, **k: _FakeProc(1, "XV-010: determinism fail"))
    assert au._replay_gate_passes(Path("/tmp/wt"), "python") is False


def test_replay_gate_verdict_false_on_crash(monkeypatch):
    from pathlib import Path

    def _boom(*a, **k):
        raise OSError("subprocess spawn failed")
    monkeypatch.setattr(au.subprocess, "run", _boom)
    assert au._replay_gate_passes(Path("/tmp/wt"), "python") is False


# ---- the replay gate is ADVISORY: a FAIL must NOT block the deploy ----------
def _battery_fakes(monkeypatch, replay_rc):
    """pytest battery green; replay gate returns replay_rc. This is the exact
    shape that self-bricked the PC — battery passes, replay gate false-fails."""
    monkeypatch.setattr(au, "_venv_python", lambda: "python")

    def _fake_run(cmd, **kw):
        if any("replay_gate.py" in str(c) for c in cmd):
            return _FakeProc(replay_rc, "XV-010: determinism fail")
        return _FakeProc(0, "")                  # the pytest battery is green
    monkeypatch.setattr(au.subprocess, "run", _fake_run)


def test_advisory_replay_failure_does_not_block_battery(monkeypatch):
    from pathlib import Path
    _battery_fakes(monkeypatch, replay_rc=1)     # replay gate FAILS
    # green pytest + failed replay gate -> update PROCEEDS (advisory), the whole
    # point: a determinism false-fail / spawn crash can no longer wedge deploys
    assert au.battery_passes(Path("/tmp/wt")) is True


def test_hard_gate_env_restores_blocking(monkeypatch):
    from pathlib import Path
    monkeypatch.setenv("LB_REPLAY_GATE_HARD", "1")
    _battery_fakes(monkeypatch, replay_rc=1)
    # the escape hatch turns the advisory gate back into a hard veto
    assert au.battery_passes(Path("/tmp/wt")) is False


def test_battery_still_blocks_on_pytest_failure(monkeypatch):
    from pathlib import Path
    monkeypatch.setattr(au, "_venv_python", lambda: "python")
    monkeypatch.setattr(au.subprocess, "run",
                        lambda *a, **k: _FakeProc(1, "FAILED tests/test_x.py::t"))
    # the REAL gate (pytest) still refuses a red battery
    assert au.battery_passes(Path("/tmp/wt")) is False


# ---- deploy gate must not self-brick (2026-08-01) ---------------------------
# conftest's outputs-write guard is test hygiene, not code safety. Left hard
# in battery_passes it froze the PC for ~19 hours: a leaking test made the
# battery red, auto_update refused every update, and the commit repairing
# the leak could not deploy either. Same self-bricking shape that demoted
# the replay gate to advisory on 2026-07-21/22.
def test_battery_downgrades_the_outputs_guard_so_it_cannot_veto_a_deploy(
        monkeypatch, tmp_path):
    seen = {}

    class _P:
        returncode = 0
        stdout = "1 passed"
        stderr = ""

    def fake_run(argv, **kw):
        seen["env"] = kw.get("env") or {}
        seen["argv"] = argv
        return _P()

    monkeypatch.setattr(au.subprocess, "run", fake_run)
    monkeypatch.setattr(au, "_replay_gate_passes", lambda *a, **k: True)
    assert au.battery_passes(tmp_path) is True
    assert seen["env"].get("LB_ALLOW_OUTPUT_WRITES") == "1", (
        "the deploy battery must run with the outputs-write guard in "
        "warn mode - a test-hygiene failure must never block a deploy")
    # and it must still be the real pytest battery, not a stubbed-out gate
    assert "pytest" in " ".join(str(a) for a in seen["argv"])
