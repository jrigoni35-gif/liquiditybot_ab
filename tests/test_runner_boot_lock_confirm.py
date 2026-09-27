"""A runner that loses outputs/runner.lock at boot writes ZERO audit records
(2026-09-27).

The PC trail carries off-main-chain CG-000/FT-020 rows from spawns that got
None back from acquire() yet were not the owner. runner.main() now re-checks
ownership after a settle, BEFORE the engine (the first audit writer) exists.

These tests drive the real runner.main() in a tmp cwd with the engine stubbed
by a BotRunner double that does what the real boot does first - write CG-000
through the audit singleton - so "zero records" is measured on a trail, not
inferred from a code path. The winner case is the anti-rubber-stamp: the same
harness with no peer MUST reach the engine and write.
"""
import json
import logging
import time
from pathlib import Path

import pytest

import core.audit as audit_mod
import runner
from core.audit import AuditTrail
from core.codes import Code
from core.runtime import SingleInstanceLock

REPO = Path(__file__).resolve().parents[1]
PEER_PID = 999_999_999


class _EngineDouble:
    built = 0

    def __init__(self, config, start_paused=False, resume=True, lock=None):
        type(self).built += 1
        audit_mod.get_audit().log("startup", Code.CG_SESSION_START,
                                  "session start: config fingerprint", {})

    def run(self):
        return None


def _plant_peer(lock_path: Path):
    lock_path.write_text(json.dumps({"pid": PEER_PID,
                                     "heartbeat": time.time()}),
                         encoding="utf-8")


@pytest.fixture
def boot(tmp_path, monkeypatch):
    """runner.main() confined to tmp_path; returns (trail_path, run)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runner.os, "chdir", lambda _p: None)
    monkeypatch.setattr(runner, "FORCE_DRY_SENTINEL",
                        tmp_path / "outputs" / "force_dry.on")
    monkeypatch.setattr(runner, "BotRunner", _EngineDouble)
    _EngineDouble.built = 0
    trail = tmp_path / "trail.jsonl"
    monkeypatch.setattr(audit_mod, "_AUDIT", AuditTrail(str(trail),
                                                        fsync=False))
    monkeypatch.setattr(runner.sys, "argv",
                        ["runner.py", "--config", str(REPO / "config.json")])
    root = logging.getLogger()
    saved = list(root.handlers)

    def run(settle_hook):
        monkeypatch.setattr(runner, "_LOCK_SETTLE_SLEEP", settle_hook)
        try:
            runner.main()
            return 0
        except SystemExit as e:
            return e.code
        finally:
            for h in list(root.handlers):
                if h not in saved:
                    root.removeHandler(h)

    return trail, tmp_path / "outputs" / "runner.lock", run


def _records(trail: Path) -> int:
    if not trail.exists():
        return 0
    return sum(1 for x in trail.read_text(encoding="utf-8").splitlines()
               if x.strip())


def test_losing_instance_writes_zero_audit_records(boot):
    trail, lock_path, run = boot
    code = run(lambda _s: _plant_peer(lock_path))   # peer claims mid-settle
    assert code == 3
    assert _EngineDouble.built == 0, "the engine must not be built"
    assert _records(trail) == 0, "a losing peer wrote to the audit trail"
    # the peer's claim survives: the loser did not overwrite or release it
    assert json.loads(lock_path.read_text(encoding="utf-8"))["pid"] == PEER_PID


def test_winning_instance_still_boots_and_writes(boot):
    trail, lock_path, run = boot
    code = run(lambda _s: None)                     # no peer
    assert code == 0
    assert _EngineDouble.built == 1
    assert _records(trail) == 1
    assert json.loads(lock_path.read_text(encoding="utf-8"))["pid"] != PEER_PID


def test_confirm_counts_a_peer_but_not_a_write_failure(tmp_path, monkeypatch):
    lk = SingleInstanceLock(str(tmp_path / "runner.lock"))
    assert lk.acquire() is None
    monkeypatch.setattr(runner, "_LOCK_SETTLE_SLEEP", lambda _s: None)
    assert runner.confirm_lock_ownership(lk, 0.0) is True

    def _boom(*_a, **_k):
        raise OSError("disk")
    monkeypatch.setattr("core.runtime.atomic_write_json", _boom)
    assert runner.confirm_lock_ownership(lk, 0.0) is True   # not a peer

    monkeypatch.setattr(runner, "_LOCK_SETTLE_SLEEP",
                        lambda _s: _plant_peer(lk.path))
    assert runner.confirm_lock_ownership(lk, 0.0) is False


def test_settle_is_derived_and_clamped():
    f = runner.lock_confirm_settle_sec
    assert f({"system": {"polling_interval_sec": 5}}, 30.0) == 10.0
    assert f({"system": {"polling_interval_sec": 60}}, 30.0) == 15.0
    assert f({"system": {"polling_interval_sec": 0}}, 30.0) == 1.0
    assert f({"system": {"lock_confirm_settle_sec": 3}}, 30.0) == 3.0
    assert f({"system": {"lock_confirm_settle_sec": "nan"}}, 30.0) == 10.0
    assert f({}, 30.0) == 10.0
