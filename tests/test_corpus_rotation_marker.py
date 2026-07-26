"""tests/test_corpus_rotation_marker.py — rollout-hazard fast path
(task-rotation-report.md).

ml/history.py's _ensure_schema rotates the corpus into a fresh .bak_<ts>
the instant it sees an old-header production file under new code, leaving
the live file near-empty until scripts/corpus_sync.py's
recover_local_baks() merges the stranded rows back in. Before this task,
that recovery only ran when the supervisor's hourly corpus-sync cadence
(pc_supervisor._stamp_due(_CORPUS_SYNC_STAMP, CORPUS_SYNC_SEC)) came due -
up to an hour away, during which the evidence gate, a scheduled retrain,
and status.json's row count all read a near-empty corpus.

HistoryStore._mark_rotated() now drops a one-way marker
(outputs/.corpus_rotated) next to the corpus on rotation;
pc_supervisor._corpus_sync_due() treats its presence as "run corpus_sync
NOW" and clears it. This file pins:
  1. write side (ml/history.py): the marker fires on an actual rotation,
     never on a fresh/first-ever file creation, and a write failure there
     never blocks the rotation itself.
  2. read/clear side (pc_supervisor._corpus_sync_due): a marker forces an
     immediate sync even with a fresh cadence stamp, is consumed exactly
     once (no tight loop from a stale marker), never suppresses the
     normal hourly cadence when absent, and is left untouched by the
     LB_NO_CORPUS_SYNC kill switch rather than silently eaten.
  3. end-to-end wiring through pc_supervisor.tick().
"""
import csv
import time
from pathlib import Path

import numpy as np

import scripts.pc_supervisor as sup
from ml.features import FEATURE_NAMES
from ml.history import CORPUS_ROTATION_MARKER_NAME, HistoryStore

# ---------------------------------------------------------------------
# 1. write side — ml/history.py._mark_rotated via _ensure_schema
# ---------------------------------------------------------------------


def test_fresh_corpus_creation_does_not_drop_marker(tmp_path):
    """Constructing a HistoryStore against a not-yet-existing file is a
    CREATE, never a ROTATE — nothing was stranded, so the fast-path
    marker must not fire (it would otherwise force a needless sync on
    every fresh-checkout first boot)."""
    hs = HistoryStore(str(tmp_path / "signal_history.csv"))
    hs._append_row("p1", "BTC", "long", np.zeros(len(FEATURE_NAMES)), 1, 1.0,
                   "live")
    assert not (tmp_path / CORPUS_ROTATION_MARKER_NAME).exists()


def test_schema_mismatch_rotation_drops_marker(tmp_path):
    dest = tmp_path / "signal_history.csv"
    hs = HistoryStore(str(dest))
    dest.write_text(",".join(hs._header[:-1]) + "\n", encoding="utf-8")
    hs._append_row("p1", "BTC", "long", np.zeros(len(FEATURE_NAMES)), 1, 1.0,
                   "live")
    assert (tmp_path / CORPUS_ROTATION_MARKER_NAME).exists()
    assert list(tmp_path.glob("signal_history.bak_*"))


def test_second_rotation_leaves_marker_present_not_doubled(tmp_path):
    """Repeated rotations are still just "presence" - touching an
    existing marker is a no-op signal, never a counter/queue."""
    dest = tmp_path / "signal_history.csv"
    hs = HistoryStore(str(dest))
    dest.write_text(",".join(hs._header[:-1]) + "\n", encoding="utf-8")
    hs._append_row("p1", "BTC", "long", np.zeros(len(FEATURE_NAMES)), 1, 1.0,
                   "live")
    marker = tmp_path / CORPUS_ROTATION_MARKER_NAME
    assert marker.exists()
    # a SECOND independent process instance rotates again (old header
    # reappeared somehow) - the marker is still just "present", not "2"
    dest.write_text(",".join(hs._header[:-1]) + "\n", encoding="utf-8")
    hs._append_row("p2", "BTC", "long", np.zeros(len(FEATURE_NAMES)), 1, 1.0,
                   "live")
    assert marker.exists()


def test_marker_write_failure_never_blocks_the_rotation_itself(
        tmp_path, monkeypatch):
    """An unwritable outputs/ (ACL drift, disk full) must never block the
    rotation/re-header that protects the corpus from interleaved-format
    corruption - only the fast-path marker is lost; recovery still lands
    on the normal hourly cadence."""
    dest = tmp_path / "signal_history.csv"
    hs = HistoryStore(str(dest))
    dest.write_text(",".join(hs._header[:-1]) + "\n", encoding="utf-8")

    def _boom(self, *a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(Path, "touch", _boom)

    hs._append_row("p1", "BTC", "long", np.zeros(len(FEATURE_NAMES)), 1, 1.0,
                   "live")               # must not raise
    with open(dest, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1 and rows[0]["position_id"] == "p1"
    assert list(tmp_path.glob("signal_history.bak_*"))
    assert not (tmp_path / CORPUS_ROTATION_MARKER_NAME).exists()


# ---------------------------------------------------------------------
# 2. read/clear side — pc_supervisor._corpus_sync_due
# ---------------------------------------------------------------------


def test_marker_forces_sync_even_when_cadence_stamp_is_fresh(
        tmp_path, monkeypatch):
    marker = tmp_path / ".corpus_rotated"
    stamp = tmp_path / ".corpus_sync_stamp"
    stamp.touch()                       # cadence just ran -> NOT due
    marker.touch()                      # but a rotation just happened
    monkeypatch.setattr(sup, "_CORPUS_ROTATION_MARKER", marker)
    monkeypatch.setattr(sup, "_CORPUS_SYNC_STAMP", stamp)
    monkeypatch.setattr(sup, "OUT", tmp_path)

    assert sup._corpus_sync_due() is True
    assert not marker.exists()                          # consumed
    # re-touched so the natural hourly mark doesn't ALSO fire right after
    assert abs(stamp.stat().st_mtime - time.time()) < 5.0


def test_marker_absent_and_cadence_fresh_is_not_due(tmp_path, monkeypatch):
    marker = tmp_path / ".corpus_rotated"      # never created
    stamp = tmp_path / ".corpus_sync_stamp"
    stamp.touch()                              # cadence fresh -> not due
    monkeypatch.setattr(sup, "_CORPUS_ROTATION_MARKER", marker)
    monkeypatch.setattr(sup, "_CORPUS_SYNC_STAMP", stamp)
    monkeypatch.setattr(sup, "OUT", tmp_path)

    assert sup._corpus_sync_due() is False
    assert not marker.exists()


def test_marker_absent_normal_cadence_still_fires_when_due(
        tmp_path, monkeypatch):
    """A MISSING marker must never suppress the ordinary hourly cadence -
    the two conditions are OR'd, not coupled."""
    marker = tmp_path / ".corpus_rotated"
    stamp = tmp_path / ".corpus_sync_stamp"    # absent -> due
    monkeypatch.setattr(sup, "_CORPUS_ROTATION_MARKER", marker)
    monkeypatch.setattr(sup, "_CORPUS_SYNC_STAMP", stamp)
    monkeypatch.setattr(sup, "OUT", tmp_path)

    assert sup._corpus_sync_due() is True
    assert stamp.exists()                      # touched by the normal path


def test_stale_marker_is_consumed_once_never_a_tight_loop(
        tmp_path, monkeypatch):
    marker = tmp_path / ".corpus_rotated"
    stamp = tmp_path / ".corpus_sync_stamp"
    marker.touch()
    stamp.touch()
    monkeypatch.setattr(sup, "_CORPUS_ROTATION_MARKER", marker)
    monkeypatch.setattr(sup, "_CORPUS_SYNC_STAMP", stamp)
    monkeypatch.setattr(sup, "OUT", tmp_path)

    assert sup._corpus_sync_due() is True       # first tick: consumed
    assert not marker.exists()
    # second tick: marker gone, cadence stamp freshly re-touched -> quiet
    assert sup._corpus_sync_due() is False


def test_kill_switch_check_at_the_caller_leaves_marker_uncleared(
        tmp_path, monkeypatch):
    """_corpus_sync_due itself has no kill-switch knowledge - tick() must
    short-circuit AROUND it (never call it) when LB_NO_CORPUS_SYNC is set,
    so a pending marker sits untouched rather than being silently eaten."""
    marker = tmp_path / ".corpus_rotated"
    marker.touch()
    monkeypatch.setattr(sup, "_CORPUS_ROTATION_MARKER", marker)
    monkeypatch.setattr(sup, "_CORPUS_SYNC_STAMP", tmp_path / ".cs_stamp")
    monkeypatch.setattr(sup, "OUT", tmp_path)
    monkeypatch.setenv("LB_NO_CORPUS_SYNC", "1")

    called = (not sup.os.environ.get("LB_NO_CORPUS_SYNC")
             and sup._corpus_sync_due())
    assert called is False
    assert marker.exists()                      # never consumed


# ---------------------------------------------------------------------
# 3. end-to-end wiring via pc_supervisor.tick()
# ---------------------------------------------------------------------

def _tick_env(monkeypatch, tmp_path, *, corpus_stamp_fresh, marker_present,
             kill_switch=False):
    calls: list = []
    monkeypatch.setattr(sup, "_spawn",
                        lambda argv, own_log=True: calls.append(argv))
    monkeypatch.setattr(sup, "_fresh", lambda *a, **k: True)   # runner alive
    monkeypatch.setattr(sup, "_maybe_launch_opend", lambda: None)
    monkeypatch.setattr(sup, "_auto_update_due", lambda: False)
    monkeypatch.setattr(sup, "_source_changed", lambda: False)
    if kill_switch:
        monkeypatch.setenv("LB_NO_CORPUS_SYNC", "1")
    else:
        monkeypatch.delenv("LB_NO_CORPUS_SYNC", raising=False)
    for var in ("LB_NO_REMOTE_CMD", "LB_NO_STATUS_PUSH", "LB_NO_TELEM_BACKUP"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(sup, "OUT", tmp_path)
    monkeypatch.setattr(sup, "_TELEM_BACKUP_STAMP", tmp_path / ".tb_stamp")
    monkeypatch.setattr(sup, "_REMOTE_CMD_STAMP", tmp_path / ".rc_stamp")
    monkeypatch.setattr(sup, "_STATUS_PUSH_STAMP", tmp_path / ".sp_stamp")
    monkeypatch.setattr(sup, "_UPDATE_STAMP", tmp_path / ".up_stamp")
    stamp = tmp_path / ".cs_stamp"
    if corpus_stamp_fresh:
        stamp.touch()
    monkeypatch.setattr(sup, "_CORPUS_SYNC_STAMP", stamp)
    marker = tmp_path / ".corpus_rotated"
    if marker_present:
        marker.touch()
    monkeypatch.setattr(sup, "_CORPUS_ROTATION_MARKER", marker)
    return calls, stamp, marker


def test_tick_spawns_corpus_sync_immediately_on_marker(monkeypatch, tmp_path):
    """The actual rollout-hazard fix: a rotation marker fires
    corpus_sync.py THIS tick even though the hourly cadence stamp is
    fresh."""
    calls, _stamp, marker = _tick_env(monkeypatch, tmp_path,
                                      corpus_stamp_fresh=True,
                                      marker_present=True)
    sup.tick()
    corpus_calls = [c for c in calls if "scripts/corpus_sync.py" in c]
    assert len(corpus_calls) == 1
    assert not marker.exists()


def test_tick_does_not_spawn_corpus_sync_when_neither_due(
        monkeypatch, tmp_path):
    calls, _stamp, _marker = _tick_env(monkeypatch, tmp_path,
                                       corpus_stamp_fresh=True,
                                       marker_present=False)
    sup.tick()
    assert not any("scripts/corpus_sync.py" in c for c in calls)


def test_tick_still_spawns_on_normal_cadence_with_no_marker(
        monkeypatch, tmp_path):
    calls, stamp, _marker = _tick_env(monkeypatch, tmp_path,
                                      corpus_stamp_fresh=False,
                                      marker_present=False)
    sup.tick()
    assert any("scripts/corpus_sync.py" in c for c in calls)
    assert stamp.exists()


def test_tick_kill_switch_leaves_marker_uncleared(monkeypatch, tmp_path):
    calls, _stamp, marker = _tick_env(monkeypatch, tmp_path,
                                      corpus_stamp_fresh=True,
                                      marker_present=True, kill_switch=True)
    sup.tick()
    assert not any("scripts/corpus_sync.py" in c for c in calls)
    assert marker.exists()             # still pending for when the switch lifts
