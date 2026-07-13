"""
Regression for scripts/keepalive.py, the sentinel-armed runner revival.

The relaunch path hardcoded the Windows venv layout
(.venv/Scripts/python.exe), so on macOS/Linux a revive spawned nothing
and raised FileNotFoundError - the watchdog looked armed but could not
actually revive. Pins the per-platform interpreter resolution and the
arm/liveness decision table (sentinel absent -> never relaunch; either
freshness signal -> no relaunch; both stale -> relaunch, detached).
"""
import json
import os
import sys
import time
from pathlib import Path

import scripts.keepalive as keepalive


def _outputs(root: Path, status_age=None, lock_age=None, sentinel=True):
    out = root / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    now = time.time()
    if sentinel:
        (out / "keepalive.on").write_text("armed", encoding="utf-8")
    if status_age is not None:
        (out / "status.json").write_text(
            json.dumps({"written_at": now - status_age}), encoding="utf-8")
    if lock_age is not None:
        (out / "runner.lock").write_text(
            json.dumps({"pid": 4242, "heartbeat": now - lock_age}),
            encoding="utf-8")
    return out


class _SpawnRecorder:
    def __init__(self):
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))


def _point_at(monkeypatch, tmp_path):
    # SENTINEL is derived from ROOT at import time - patch both, or the
    # test silently reads the real repo's arm state.
    monkeypatch.setattr(keepalive, "ROOT", tmp_path)
    monkeypatch.setattr(keepalive, "SENTINEL",
                        tmp_path / "outputs" / "keepalive.on")


def test_relaunch_interpreter_prefers_repo_venv():
    py = keepalive.relaunch_interpreter()
    assert py.exists()
    expected = keepalive.ROOT / (
        ".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    if expected.exists():
        assert py == expected


def test_relaunch_interpreter_falls_back_without_venv(tmp_path, monkeypatch):
    monkeypatch.setattr(keepalive, "ROOT", tmp_path)
    assert keepalive.relaunch_interpreter() == Path(sys.executable)


def test_disarmed_never_relaunches(tmp_path, monkeypatch):
    _outputs(tmp_path, status_age=99999, lock_age=99999, sentinel=False)
    rec = _SpawnRecorder()
    _point_at(monkeypatch, tmp_path)
    monkeypatch.setattr(keepalive.subprocess, "Popen", rec)
    assert keepalive.main() == 0
    assert rec.calls == []


def test_fresh_runner_not_relaunched(tmp_path, monkeypatch):
    _outputs(tmp_path, status_age=2.0, lock_age=2.0)
    rec = _SpawnRecorder()
    _point_at(monkeypatch, tmp_path)
    monkeypatch.setattr(keepalive.subprocess, "Popen", rec)
    assert keepalive.main() == 0
    assert rec.calls == []


def test_stale_runner_relaunched_detached(tmp_path, monkeypatch):
    _outputs(tmp_path, status_age=99999, lock_age=99999)
    rec = _SpawnRecorder()
    _point_at(monkeypatch, tmp_path)
    monkeypatch.setattr(keepalive.subprocess, "Popen", rec)
    assert keepalive.main() == 0
    assert len(rec.calls) == 1
    argv, kwargs = rec.calls[0]
    assert argv[1] == "runner.py"
    assert kwargs["cwd"] == str(tmp_path)
    if os.name == "nt":
        assert "creationflags" in kwargs
    else:
        assert kwargs.get("start_new_session") is True
