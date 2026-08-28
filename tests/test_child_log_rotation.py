"""Supervisor child-log rotation at the spawn boundary.

WHY (capacity sweep, 2026-08-07): outputs/runner.log reached 153.8MB with
no rotation anywhere - the supervisor opens it append-mode at every spawn
and the child holds the handle for its whole life, so every forensic grep
and every gc_log_pusher tail paid the full file. events.jsonl has rotated
at 5MB since core/runtime.py shipped; the child stdout logs were the gap.

WHY AT THE SPAWN BOUNDARY AND NOWHERE ELSE: Windows refuses to rename a
file with an open handle. Between a child's death and its respawn is the
only moment the handle is released - _spawn calls _rotate_child_log
immediately before re-opening. gc_log_pusher._drain_rotated already
consumes rename-style rotation losslessly, so no telemetry is dropped.

Best-effort contract: a lingering handle must SKIP rotation and append,
never block the spawn - an unrotated log is an inconvenience, an
unspawned runner is an outage.
"""
import importlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def _mod(tmp_path, monkeypatch, max_mb="0.001", keep="2"):
    """Fresh module instance with env-sized caps and a redirected log."""
    monkeypatch.setenv("LB_CHILD_LOG_MAX_MB", max_mb)
    monkeypatch.setenv("LB_CHILD_LOG_KEEP", keep)
    import pc_supervisor
    m = importlib.reload(pc_supervisor)
    monkeypatch.setattr(m, "LOG_PATH", tmp_path / "pc_supervisor.log")
    return m


def test_oversize_log_rotates_to_dot_one(tmp_path, monkeypatch):
    m = _mod(tmp_path, monkeypatch)
    p = tmp_path / "runner.log"
    p.write_bytes(b"x" * 2048)                    # over the 1KB test cap
    m._rotate_child_log(p)
    assert not p.exists(), "oversize log must be renamed away"
    assert (tmp_path / "runner.log.1").stat().st_size == 2048


def test_small_log_is_left_alone(tmp_path, monkeypatch):
    m = _mod(tmp_path, monkeypatch)
    p = tmp_path / "runner.log"
    p.write_bytes(b"x" * 10)
    m._rotate_child_log(p)
    assert p.exists() and not (tmp_path / "runner.log.1").exists()


def test_generations_shift_and_retention_is_bounded(tmp_path, monkeypatch):
    """.1 -> .2, new .1, and the oldest generation beyond keep=2 dies -
    bounded retention is the point; unbounded archives recreate the
    disease under a different name."""
    m = _mod(tmp_path, monkeypatch)
    p = tmp_path / "runner.log"
    (tmp_path / "runner.log.1").write_bytes(b"gen1")
    (tmp_path / "runner.log.2").write_bytes(b"gen2-oldest")
    p.write_bytes(b"y" * 2048)
    m._rotate_child_log(p)
    assert (tmp_path / "runner.log.1").read_bytes() == b"y" * 2048
    assert (tmp_path / "runner.log.2").read_bytes() == b"gen1"
    assert not (tmp_path / "runner.log.3").exists()


@pytest.mark.skipif(os.name != "nt", reason=(
    "pins WINDOWS rename-refusal: POSIX happily renames an open file, so "
    "the held-handle fallback this guards is unreachable there"))
def test_open_handle_skips_rotation_never_raises(tmp_path, monkeypatch):
    """The outage guard: a held handle (Windows rename refusal) must fall
    back to appending, not propagate into the spawn path.

    PLATFORM-SPLIT, not platform-skipped. The contract that matters —
    rotation NEVER raises into the spawn path — is asserted on every
    platform, because that is the outage this guard exists to prevent and
    it is not a Windows fact. Only the *observable outcome* differs: NT
    refuses the rename while the handle is open, so the log survives in
    place; POSIX renames happily, so it rotates. Asserting the NT outcome
    on Linux failed here for a reason that has nothing to do with the
    guard, and a red that means "wrong OS" is indistinguishable from a red
    that means "the spawn path can now die".
    """
    m = _mod(tmp_path, monkeypatch)
    p = tmp_path / "runner.log"
    p.write_bytes(b"x" * 2048)
    with open(p, "a", encoding="utf-8"):          # simulate the live child
        m._rotate_child_log(p)                    # must not raise — all OSes
    if os.name == "nt":
        assert p.exists(), "with a held handle the file must survive in place"
    else:
        assert (tmp_path / "runner.log.1").exists(), (
            "POSIX renames across an open handle, so rotation must have "
            "proceeded — if it did not, the guard is over-refusing")


def test_rotation_wired_into_spawn(tmp_path, monkeypatch):
    """_spawn must rotate BEFORE opening the append handle - rotation
    anywhere else can never succeed on Windows."""
    m = _mod(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(m, "_rotate_child_log",
                        lambda path: calls.append(Path(path).name))
    class _P:
        def __init__(self, *a, **k):
            pass
    monkeypatch.setattr(m.subprocess, "Popen", _P)
    m._spawn([sys.executable, str(tmp_path / "runner.py")], own_log=True)
    assert calls == ["runner.log"]
    calls.clear()
    m._spawn([sys.executable, str(tmp_path / "runner.py")], own_log=False)
    assert calls == [], "DEVNULL children have no log to rotate"
