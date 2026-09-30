"""The 5m candle collector rides pc_supervisor's always-on loop (2026-09-30).

It had never been scheduled: the intraday candle lanes ended 2026-09-01..09-07
and every unrun day is 5m path the bot's ring discards for good. An S4U task
needs an elevated registration, so tick() spawns it on a 6h stamp instead.
"""
from __future__ import annotations

import os
import time

import pytest

import scripts.pc_supervisor as sup

COLLECT = "scripts/candle_collect.py"


def _tick(monkeypatch, tmp_path, *, stamp_fresh, kill=False):
    calls: list = []
    monkeypatch.setattr(sup, "_spawn",
                        lambda argv, own_log=True: calls.append(argv))
    monkeypatch.setattr(sup, "_fresh", lambda *a, **k: True)
    monkeypatch.setattr(sup, "_maybe_launch_opend", lambda: None)
    monkeypatch.setattr(sup, "_auto_update_due", lambda: False)
    monkeypatch.setattr(sup, "_source_changed", lambda: False)
    monkeypatch.setattr(sup, "OUT", tmp_path)
    for name in ("_TELEM_BACKUP_STAMP", "_REMOTE_CMD_STAMP",
                 "_STATUS_PUSH_STAMP", "_UPDATE_STAMP", "_CORPUS_SYNC_STAMP",
                 "_VAULT_GUARD_STAMP"):
        monkeypatch.setattr(sup, name, tmp_path / f"{name}.stamp")
    monkeypatch.setattr(sup, "_CORPUS_ROTATION_MARKER", tmp_path / ".none")
    stamp = tmp_path / ".cc_stamp"
    if stamp_fresh:
        stamp.touch()
    monkeypatch.setattr(sup, "_CANDLE_COLLECT_STAMP", stamp)
    if kill:
        monkeypatch.setenv("LB_NO_CANDLE_COLLECT", "1")
    else:
        monkeypatch.delenv("LB_NO_CANDLE_COLLECT", raising=False)
    sup.tick()
    return [c for c in calls if COLLECT in c], stamp


def test_due_collector_is_spawned_once_with_once(monkeypatch, tmp_path):
    got, stamp = _tick(monkeypatch, tmp_path, stamp_fresh=False)
    assert len(got) == 1 and got[0][-2:] == [COLLECT, "--once"]
    assert stamp.exists()                        # cadence stamp armed


def test_fresh_stamp_means_not_due(monkeypatch, tmp_path):
    got, _ = _tick(monkeypatch, tmp_path, stamp_fresh=True)
    assert got == []


def test_kill_switch_disables_it(monkeypatch, tmp_path):
    got, stamp = _tick(monkeypatch, tmp_path, stamp_fresh=False, kill=True)
    assert got == [] and not stamp.exists()


def test_an_old_stamp_is_due_again(monkeypatch, tmp_path):
    stamp = tmp_path / ".cc_stamp"
    stamp.touch()
    old = time.time() - sup.CANDLE_COLLECT_SEC - 60
    os.utime(stamp, (old, old))
    got, _ = _tick(monkeypatch, tmp_path, stamp_fresh=False)
    assert len(got) == 1


def test_cadence_is_far_inside_the_ring_depth():
    # the ring keeps label_max_bars * 5 bars of 5m = ~7.5 days at 432
    assert sup.CANDLE_COLLECT_SEC <= 24 * 3600
    assert sup.CANDLE_COLLECT_SEC == pytest.approx(21600.0)


def test_the_stamp_is_redirected_in_tests():
    from tests.conftest import _REDIRECTED_PATH_ATTRS
    assert "_CANDLE_COLLECT_STAMP" in _REDIRECTED_PATH_ATTRS
