"""atomic_write_json must survive the transient Windows file lock a reader
(dashboard/monitor) holds on the destination: os.replace raises PermissionError
(WinError 5) then succeeds once the reader closes. Without the retry the whole
runner cycle errored and status.json went stale - the observed 'runner going
stale' crash (PermissionError on outputs\\status.json.tmp -> status.json).
"""
import json

import pytest

import core.runtime as rt


def test_write_succeeds_after_transient_permission_errors(tmp_path, monkeypatch):
    p = tmp_path / "status.json"
    real = rt.os.replace
    calls = {"n": 0}

    def flaky_replace(src, dst):
        calls["n"] += 1
        if calls["n"] < 3:                      # first 2 attempts locked
            raise PermissionError(5, "Access is denied")
        return real(src, dst)

    monkeypatch.setattr(rt.os, "replace", flaky_replace)
    monkeypatch.setattr(rt.time, "sleep", lambda s: None)   # no real backoff
    rt.atomic_write_json(p, {"ok": 1})
    assert calls["n"] == 3
    assert json.loads(p.read_text(encoding="utf-8")) == {"ok": 1}


def test_persistent_lock_eventually_raises(tmp_path, monkeypatch):
    p = tmp_path / "status.json"

    def always_locked(src, dst):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(rt.os, "replace", always_locked)
    monkeypatch.setattr(rt.time, "sleep", lambda s: None)
    with pytest.raises(PermissionError):
        rt.atomic_write_json(p, {"ok": 1}, _retries=3)
    # W2-20: a fully-exhausted retry must not leave its PID-scoped tmp behind
    # (the documented 476-collision storm precedent for status.json litter).
    assert not list(tmp_path.glob("*.tmp")), \
        "tmp file orphaned when os.replace retries were exhausted"


def test_json_dump_failure_mid_write_cleans_tmp(tmp_path, monkeypatch):
    """checkpoint-A reviewer note: json.dump itself raising mid-write (a
    non-serializable payload) must also leave no tmp behind, not just the
    os.replace retry-exhaustion path above."""
    p = tmp_path / "status.json"

    def boom(*a, **k):
        raise ValueError("cannot serialize payload")

    monkeypatch.setattr(rt.json, "dump", boom)
    with pytest.raises(ValueError):
        rt.atomic_write_json(p, {"ok": 1})
    assert not list(tmp_path.glob("*.tmp")), \
        "tmp file orphaned when json.dump raised mid-write"


def test_normal_write_is_unaffected(tmp_path):
    p = tmp_path / "s.json"
    rt.atomic_write_json(p, {"a": [1, 2, 3]})
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": [1, 2, 3]}


def test_tmp_path_is_pid_scoped_so_two_writers_cannot_interleave(tmp_path):
    """A fixed status.json.tmp is shared: during the single-instance-lock
    convergence window two runners open the SAME tmp -> truncate/interleave
    -> os.replace can publish a torn file a reader fails to parse. The tmp
    name must carry the writer's pid so each publish is atomic and private."""
    import os
    p = tmp_path / "status.json"
    # capture the tmp path atomic_write_json actually opens
    seen = {}
    real_open = open

    def spy_open(path, *a, **k):
        if str(path).endswith(".tmp"):
            seen["tmp"] = str(path)
        return real_open(path, *a, **k)

    import builtins
    orig = builtins.open
    builtins.open = spy_open
    try:
        rt.atomic_write_json(p, {"ok": 1})
    finally:
        builtins.open = orig
    assert str(os.getpid()) in seen["tmp"], \
        f"tmp path must be pid-scoped, got {seen['tmp']}"
    # a different pid would resolve to a different tmp -> no shared-file race
    assert seen["tmp"] != str(p.with_suffix(p.suffix + ".tmp"))
    assert json.loads(p.read_text(encoding="utf-8")) == {"ok": 1}
