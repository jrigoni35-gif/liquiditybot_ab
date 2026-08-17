"""pc_supervisor never-dies-silently contract (2026-08-16 incident).

pid 15160, spawned at logon by Task Scheduler, exited 1 about five minutes
in with NOTHING in its own log; the task's job object then took the runner
and all three pushers down inside one heartbeat, and the expired KeepAlive
task revived nothing: the stack was dark 50 minutes. Under pythonw there
is no console - an unhandled traceback ceases to exist. The only unguarded
per-cycle surface was `_LOCK.refresh()` (it sat OUTSIDE the tick try), and
`read_json` raised UnicodeDecodeError through it on non-UTF8 bytes despite
its "never raises" docstring. This suite pins every guard that makes a
repeat impossible to miss:

  * a raising tick() logs its FULL traceback and the loop continues;
  * a raising lock refresh does the same (the incident's escape hatch);
  * the source-change handoff's SystemExit still propagates untouched;
  * a forfeited lock still exits cleanly (the one legitimate loop exit);
  * the top-level wrapper logs FATAL + traceback for anything that still
    escapes, preserving the exit-code contract (unhandled -> 1, ^C -> 0);
  * the in-job spawn fallback is LOUD (the silent fallback is why the
    incident forensics could not say whether children sat in the job);
  * exit forensics: an atexit hook writes a 'process exit' line to the
    log path captured at arm time - so a dead supervisor with NO exit
    line now provably died from OUTSIDE python;
  * read_json returns None (never raises) on non-UTF8 bytes;
  * a garbage heartbeat in a lock file reads as stale, never as a raise.
"""
import json

import pytest

import scripts.pc_supervisor as sup
from core.runtime import SingleInstanceLock, read_json


class _StubLock:
    """Minimal stand-in for the module-global _LOCK."""

    def __init__(self, refresh_ok=True, forfeited=False, exc=None):
        self._refresh_ok = refresh_ok
        self._forfeited = forfeited
        self._exc = exc

    def refresh(self):
        if self._exc is not None:
            raise self._exc
        return self._refresh_ok

    @property
    def forfeited(self):
        return self._forfeited

    def release(self):
        pass


def _logged(tmp_path, monkeypatch):
    p = tmp_path / "sup_guard_test.log"
    monkeypatch.setattr(sup, "LOG_PATH", p)
    return p


# ---- per-cycle guards -------------------------------------------------------

def test_raising_tick_logs_traceback_and_survives(monkeypatch, tmp_path):
    p = _logged(tmp_path, monkeypatch)

    def _boom():
        raise ValueError("planted-tick-defect")
    monkeypatch.setattr(sup, "tick", _boom)
    monkeypatch.setattr(sup, "_LOCK", _StubLock())
    assert sup._guarded_iteration() is True          # survived
    text = p.read_text(encoding="utf-8")
    assert "tick error (continuing)" in text
    assert "planted-tick-defect" in text
    assert "Traceback" in text                       # full traceback, not str(e)


def test_raising_refresh_logs_traceback_and_survives(monkeypatch, tmp_path):
    # THE incident-shaped escape: the old loop ran refresh() outside the
    # try, so this exact raise was a silent exit-1 and a dead stack.
    p = _logged(tmp_path, monkeypatch)
    monkeypatch.setattr(sup, "tick", lambda: None)
    monkeypatch.setattr(
        sup, "_LOCK", _StubLock(exc=RuntimeError("planted-refresh-defect")))
    assert sup._guarded_iteration() is True          # survived
    text = p.read_text(encoding="utf-8")
    assert "lock refresh error (continuing)" in text
    assert "planted-refresh-defect" in text
    assert "Traceback" in text


def test_handoff_systemexit_propagates(monkeypatch, tmp_path):
    _logged(tmp_path, monkeypatch)

    def _handoff():
        raise SystemExit(0)
    monkeypatch.setattr(sup, "tick", _handoff)
    monkeypatch.setattr(sup, "_LOCK", _StubLock())
    with pytest.raises(SystemExit):
        sup._guarded_iteration()


def test_forfeited_lock_exits_cleanly(monkeypatch, tmp_path):
    p = _logged(tmp_path, monkeypatch)
    monkeypatch.setattr(sup, "tick", lambda: None)
    monkeypatch.setattr(sup, "_LOCK",
                        _StubLock(refresh_ok=False, forfeited=True))
    assert sup._guarded_iteration() is False         # the one clean loop exit
    assert "lost the supervisor lock" in p.read_text(encoding="utf-8")


# ---- top-level wrapper ------------------------------------------------------

def test_main_guarded_logs_fatal_traceback_and_returns_1(monkeypatch,
                                                         tmp_path):
    p = _logged(tmp_path, monkeypatch)
    monkeypatch.setattr(sup, "_EXIT_HOOKS_ARMED", True)   # skip real atexit

    def _die():
        raise RuntimeError("planted-fatal-defect")
    monkeypatch.setattr(sup, "main", _die)
    assert sup._main_guarded() == 1
    text = p.read_text(encoding="utf-8")
    assert "FATAL" in text
    assert "planted-fatal-defect" in text
    assert "Traceback" in text


def test_main_guarded_exit_code_contract(monkeypatch, tmp_path):
    _logged(tmp_path, monkeypatch)
    monkeypatch.setattr(sup, "_EXIT_HOOKS_ARMED", True)

    monkeypatch.setattr(sup, "main", lambda: None)
    assert sup._main_guarded() == 0                  # clean return

    def _ctrl_c():
        raise KeyboardInterrupt()
    monkeypatch.setattr(sup, "main", _ctrl_c)
    assert sup._main_guarded() == 0                  # ^C stays rc 0

    def _handoff():
        raise SystemExit(0)
    monkeypatch.setattr(sup, "main", _handoff)
    assert sup._main_guarded() == 0                  # handoff stays rc 0

    def _exit_3():
        raise SystemExit(3)
    monkeypatch.setattr(sup, "main", _exit_3)
    assert sup._main_guarded() == 3                  # explicit codes preserved


def test_exit_forensics_registers_hook_bound_to_armtime_path(monkeypatch,
                                                             tmp_path):
    # The atexit hook must write to the path captured when armed - not to
    # whatever LOG_PATH points at when the interpreter finally exits (in a
    # test process that would be the operator's REAL log after monkeypatch
    # teardown). Capture the registered callable and fire it by hand.
    p = _logged(tmp_path, monkeypatch)
    monkeypatch.setattr(sup, "_EXIT_HOOKS_ARMED", False)
    registered = []
    monkeypatch.setattr(sup.atexit, "register", registered.append)
    import faulthandler
    monkeypatch.setattr(faulthandler, "enable", lambda *a, **k: None)
    sup._arm_exit_forensics()
    assert len(registered) == 1
    monkeypatch.setattr(sup, "LOG_PATH", tmp_path / "elsewhere.log")
    registered[0]()                                   # simulate process exit
    assert "process exit" in p.read_text(encoding="utf-8")
    assert not (tmp_path / "elsewhere.log").exists()  # arm-time path won
    # re-arming is a no-op (one hook per process, however often main runs)
    sup._arm_exit_forensics()
    assert len(registered) == 1


# ---- loud in-job spawn fallback ---------------------------------------------

def test_spawn_in_job_fallback_is_loud(monkeypatch, tmp_path):
    p = _logged(tmp_path, monkeypatch)
    monkeypatch.setattr(sup, "IS_WIN", True)
    spawned = []

    def _popen(argv, **kw):
        if kw.get("creationflags", 0) & 0x01000000:  # breakaway requested
            raise PermissionError(5, "job denies breakaway")
        spawned.append(kw.get("creationflags"))

    monkeypatch.setattr(sup.subprocess, "Popen", _popen)
    sup._spawn(["py", "runner.py"], own_log=False)
    assert spawned                                    # fell back, in-job
    text = p.read_text(encoding="utf-8")
    assert "IN the task job" in text                  # and said so out loud


def test_spawn_total_failure_names_the_error(monkeypatch, tmp_path):
    p = _logged(tmp_path, monkeypatch)
    monkeypatch.setattr(sup, "IS_WIN", True)

    def _popen(argv, **kw):
        raise OSError(1455, "planted-spawn-error")
    monkeypatch.setattr(sup.subprocess, "Popen", _popen)
    sup._spawn(["py", "runner.py"], own_log=False)    # must not raise
    text = p.read_text(encoding="utf-8")
    assert "spawn failed" in text
    assert "planted-spawn-error" in text              # error no longer eaten


def test_job_status_never_raises_and_says_something():
    s = sup._job_status()
    assert isinstance(s, str) and s


# ---- runtime lock hardening (the incident's only in-process escape) ---------

def test_read_json_non_utf8_returns_none(tmp_path):
    p = tmp_path / "lock.json"
    p.write_bytes(b'{"pid": 1, "heartbeat": \xff\xfe garbage')
    assert read_json(p) is None                       # was: UnicodeDecodeError


def test_refresh_survives_non_utf8_lock(tmp_path):
    lock = SingleInstanceLock(path=str(tmp_path / "l.lock"),
                              stale_after_sec=30.0)
    (tmp_path / "l.lock").write_bytes(b"\xff\xfe\x00garbage")
    assert lock.refresh() is True                     # reclaimed, no raise
    cur = json.loads((tmp_path / "l.lock").read_text(encoding="utf-8"))
    assert cur["pid"] == lock.pid


def test_refresh_survives_garbage_heartbeat(tmp_path):
    lock = SingleInstanceLock(path=str(tmp_path / "l.lock"),
                              stale_after_sec=30.0)
    (tmp_path / "l.lock").write_text(
        json.dumps({"pid": 424242, "heartbeat": "not-a-number"}),
        encoding="utf-8")
    assert lock.refresh() is True                     # garbage reads as stale
    cur = json.loads((tmp_path / "l.lock").read_text(encoding="utf-8"))
    assert cur["pid"] == lock.pid                     # and gets rewritten
