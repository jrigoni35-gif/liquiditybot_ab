"""pc_supervisor spawns the two forward-data jobs (2026-10-02): the paper
target book hourly and the forward reads weekly, each stamp-gated, each with
its own kill switch, and neither ever touching the runner."""
from __future__ import annotations

import pytest

import scripts.pc_supervisor as sup

PAPER, FWD = "scripts/target_book_paper.py", "scripts/forward_reads.py"


def _tick(monkeypatch, tmp_path, *, fresh=(), kill=()):
    calls: list = []
    monkeypatch.setattr(sup, "_spawn", lambda argv, own_log=True: calls.append(argv))
    monkeypatch.setattr(sup, "_fresh", lambda *a, **k: True)
    monkeypatch.setattr(sup, "_maybe_launch_opend", lambda: None)
    monkeypatch.setattr(sup, "_auto_update_due", lambda: False)
    monkeypatch.setattr(sup, "_source_changed", lambda: False)
    monkeypatch.setattr(sup, "OUT", tmp_path)
    monkeypatch.setattr(sup, "_CORPUS_ROTATION_MARKER", tmp_path / ".none")
    for name in ("_TELEM_BACKUP_STAMP", "_REMOTE_CMD_STAMP", "_STATUS_PUSH_STAMP",
                 "_UPDATE_STAMP", "_CORPUS_SYNC_STAMP", "_VAULT_GUARD_STAMP",
                 "_CANDLE_COLLECT_STAMP", "_TARGET_PAPER_STAMP", "_FORWARD_READ_STAMP"):
        st = tmp_path / f"{name}.stamp"
        if name in fresh:
            st.touch()
        monkeypatch.setattr(sup, name, st)
    for env in ("LB_NO_TARGET_PAPER", "LB_NO_FORWARD_READS"):
        if env in kill:
            monkeypatch.setenv(env, "1")
        else:
            monkeypatch.delenv(env, raising=False)
    sup.tick()
    return calls


def test_both_jobs_spawn_when_due_with_once(monkeypatch, tmp_path):
    calls = _tick(monkeypatch, tmp_path)
    got = {c[-2]: c for c in calls if c[-2] in (PAPER, FWD)}
    assert set(got) == {PAPER, FWD} and all(c[-1] == "--once" for c in got.values())


def test_fresh_stamps_and_kill_switches_hold_them(monkeypatch, tmp_path):
    calls = _tick(monkeypatch, tmp_path,
                  fresh=("_TARGET_PAPER_STAMP", "_FORWARD_READ_STAMP"))
    assert not [c for c in calls if PAPER in c or FWD in c]
    b = tmp_path / "b"
    b.mkdir()
    calls = _tick(monkeypatch, b, kill=("LB_NO_TARGET_PAPER", "LB_NO_FORWARD_READS"))
    assert not [c for c in calls if PAPER in c or FWD in c]


def test_cadences():
    assert sup.TARGET_PAPER_SEC == pytest.approx(3600.0)     # inside one 4h bar
    assert sup.FORWARD_READ_SEC == pytest.approx(604800.0)   # one weekly block


def test_stamps_are_redirected_in_tests():
    from tests.conftest import _REDIRECTED_PATH_ATTRS
    assert {"_TARGET_PAPER_STAMP", "_FORWARD_READ_STAMP"} <= set(_REDIRECTED_PATH_ATTRS)
