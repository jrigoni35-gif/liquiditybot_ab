"""One-writer rule for the training corpus + CS-1 counters (2026-09-30).

Measured defect: losing duplicate runners wrote 8 duplicate rows to
signal_history.csv (09-10, 09-18 - RT-010 at the same second) while cycling
toward forfeit. Pins: rows are HELD (not written) while the lock is lost,
FLUSHED in order when it is regained, DISCARDED on forfeit; the loader drops
an exact duplicate row (counted) but keeps a reused id with a different
signal; the two silent candidate exits and the long-book skip are counted.
"""
from __future__ import annotations

import ast
import csv
from pathlib import Path

import numpy as np

from ml.features import FEATURE_NAMES
from ml.history import CandidateLabeler, HistoryStore

ROOT = Path(__file__).resolve().parents[1]
F = np.full(len(FEATURE_NAMES), 0.5)


def _ids(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return [r["position_id"] for r in csv.DictReader(fh)]


def _cand(hs, pid, ts, label=1):
    hs._append_row(pid, "ETH", "long", F, label, 0.0, "candidate",
                   signal_ts=ts, barrier="tb_pt", disp="confirmed")


def test_held_rows_never_reach_disk_until_released_in_order(tmp_path):
    p = tmp_path / "h.csv"
    hs = HistoryStore(str(p))
    _cand(hs, "cand-a", 1000.0)
    hs.hold_writes()
    _cand(hs, "cand-b", 1300.0)
    _cand(hs, "cand-c", 1600.0)
    assert _ids(p) == ["cand-a"]                 # held: not on disk
    assert hs.release_writes() == 2
    assert _ids(p) == ["cand-a", "cand-b", "cand-c"]
    _cand(hs, "cand-d", 1900.0)                  # writing normally again
    assert _ids(p)[-1] == "cand-d" and hs.held_flushed == 2


def test_forfeit_discards_and_keeps_holding(tmp_path):
    p = tmp_path / "h.csv"
    hs = HistoryStore(str(p))
    hs.hold_writes()
    _cand(hs, "cand-x", 1000.0)
    assert hs.discard_held() == 1
    _cand(hs, "cand-y", 1300.0)                  # a duplicate keeps computing
    assert _ids(p) == []                          # ...and writes nothing
    assert hs.held_discarded == 1


def test_hold_is_idempotent_and_does_not_drop_held_rows(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    hs.hold_writes()
    _cand(hs, "cand-1", 1000.0)
    hs.hold_writes()                              # a second latch
    assert hs.release_writes() == 1


def test_loader_drops_an_exact_duplicate_and_counts_it(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    for i in range(30):
        _cand(hs, f"cand-{i:04d}", 1000.0 + 300 * i, label=i % 2)
    _cand(hs, "cand-0007", 1000.0 + 300 * 7, label=1)   # the loser's copy
    X, y, w = hs.load_training_data()
    assert len(X) == 30
    assert hs.last_load_stats["dropped_duplicate"] == 1


def test_loader_keeps_a_reused_bare_id_for_a_different_signal(tmp_path):
    # 2026-07-14 rollback: the same bare id minted for TWO distinct signals
    hs = HistoryStore(str(tmp_path / "h.csv"))
    _cand(hs, "cand-5", 1000.0)
    _cand(hs, "cand-5", 9000.0)
    X, _, _ = hs.load_training_data()
    assert len(X) == 2
    assert hs.last_load_stats["dropped_duplicate"] == 0


def test_long_book_skip_is_counted(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    _cand(hs, "cand-1", 1000.0)
    hs._append_row("long-1", "ETH", "long", F, 1, 5.0, "live", book="long")
    X, _, _ = hs.load_training_data()
    assert len(X) == 1
    assert hs.last_load_stats["long_book_skipped"] == 1


def _bars(t0, n):
    return [{"time": t0 + 300 * i, "close": 100.0, "high": 100.1,
             "low": 99.9} for i in range(n)]


def test_pool_cap_eviction_is_counted(tmp_path):
    lab = CandidateLabeler(HistoryStore(str(tmp_path / "h.csv")),
                           {"max_open_candidates": 2})
    for i in range(4):
        lab.register("ETH", "long", F, 0.002, 1000 + 300 * i)
    assert lab.evicted_pool_cap == 2
    assert len(lab._cands) == 2


def test_entry_bar_slide_drop_is_counted(tmp_path):
    lab = CandidateLabeler(HistoryStore(str(tmp_path / "h.csv")),
                           {"label_max_bars": 4})
    lab.register("ETH", "long", F, 0.002, 1000)
    # the bar cache now starts AFTER the candidate's entry bar
    lab.update_candles("ETH", _bars(100_000, 30))
    lab.poll()
    assert lab.dropped_entry_slid == 1
    assert lab._cands == []


# ---------------- runner wiring ----------------
class _FakeHistory:
    def __init__(self):
        self.calls = []

    def hold_writes(self):
        self.calls.append("hold")

    def release_writes(self):
        self.calls.append("release")
        return 3

    def discard_held(self):
        self.calls.append("discard")
        return 2


def test_runner_helpers_drive_the_store():
    import runner
    r = runner.BotRunner.__new__(runner.BotRunner)
    r.bot = type("B", (), {"history": _FakeHistory()})()
    r._hold_corpus_writes()
    r._release_corpus_writes()
    r._discard_corpus_writes()
    assert r.bot.history.calls == ["hold", "release", "discard"]


def test_runner_helpers_tolerate_a_bot_without_history():
    import runner
    r = runner.BotRunner.__new__(runner.BotRunner)
    r.bot = object()
    r._hold_corpus_writes()
    r._release_corpus_writes()
    r._discard_corpus_writes()


def _calls_in(node) -> set:
    return {n.func.attr for n in ast.walk(node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}


def test_the_lock_branches_call_hold_release_and_discard():
    """Structural pin on the CODE (docstrings are not calls): the branch
    that latches a lost lock holds, the regain branch releases, the
    forfeit branch discards before breaking out."""
    tree = ast.parse((ROOT / "runner.py").read_text(encoding="utf-8"))
    latch = regain = forfeit = False
    for n in ast.walk(tree):
        if not isinstance(n, ast.If):
            continue
        src = ast.unparse(n.test)
        body = _calls_in(ast.Module(body=n.body, type_ignores=[]))
        if src == "self._lock.lost_count == 0":
            regain = "_release_corpus_writes" in body
            orelse = _calls_in(ast.Module(body=n.orelse, type_ignores=[]))
            latch = {"_note_lock_lost", "_hold_corpus_writes"} <= orelse
        if src == "self._lock.forfeited":
            forfeit = "_discard_corpus_writes" in body
    assert latch and regain and forfeit
