"""ml/history.py: HistoryStore.regime_live_count (Task 4, #103
regime-coverage hold).

Per-regime LIVE label counts: rows with source=='live' whose regime
one-hot marks the queried label. O(1) at admission time - a load-time
full-CSV scan happens at most once per process (or when the file changes
under it, mtime/size-cached exactly like source_counts), and every
live-row append folds straight into the in-memory counter incrementally
- NEVER a per-admission re-scan.

Persistence: the counter is a PURE DERIVED CACHE, never snapshotted -
the CSV is the durable source of truth, and a cold process (restart,
deploy) rebuilds it lazily on first use, exactly like
source_counts/asset_counts/row_count. "Round trip" for this design means
a fresh HistoryStore pointed at the same path reproduces the same counts,
not a JSON snapshot key.
"""
from unittest import mock

import numpy as np

from ml.features import FEATURE_NAMES
from ml.history import HistoryStore

_REGIME_FEATURE = {
    "bull_quiet": "regime_bull_quiet",
    "bull_volatile": "regime_bull_vol",
    "range": "regime_range",
    "bear": "regime_bear",
    "crisis": "regime_crisis",
}


def _feats(label: "str | None") -> np.ndarray:
    f = np.zeros(len(FEATURE_NAMES))
    if label is not None:
        f[FEATURE_NAMES.index(_REGIME_FEATURE[label])] = 1.0
    return f


def _live_row(hs: HistoryStore, pid: str, label: str, asset="ETH"):
    hs.log_entry(pid, asset, "long", _feats(label))
    hs.log_close(pid, 1.0)


def test_zero_on_a_fresh_store_with_no_file(tmp_path):
    hs = HistoryStore(str(tmp_path / "missing" / "h.csv"))
    assert hs.regime_live_count("range") == 0


def test_counts_only_live_rows_by_their_regime_one_hot(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    _live_row(hs, "p1", "range")
    _live_row(hs, "p2", "range")
    _live_row(hs, "p3", "bear")
    # a candidate row (source='candidate') must NOT count toward any
    # regime's LIVE total, even though its one-hot marks one
    hs._append_row("cand-1", "ETH", "long", _feats("crisis"), 1, 0.0,
                   "candidate")
    assert hs.regime_live_count("range") == 2
    assert hs.regime_live_count("bear") == 1
    assert hs.regime_live_count("crisis") == 0
    assert hs.regime_live_count("bull_quiet") == 0


def test_row_with_no_regime_one_hot_set_counts_toward_no_regime(tmp_path):
    # a legacy/padded row (schema migration, or written before the regime
    # one-hot existed) marks nothing - it must not inflate any bucket
    hs = HistoryStore(str(tmp_path / "h.csv"))
    _live_row(hs, "p1", None)
    assert sum(hs.regime_live_count(r) for r in _REGIME_FEATURE) == 0


def test_incremental_append_updates_the_counter_without_a_rescan(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    _live_row(hs, "p1", "bear")
    assert hs.regime_live_count("bear") == 1     # triggers the load-time scan
    _live_row(hs, "p2", "bear")                  # incremental, post-load
    assert hs.regime_live_count("bear") == 2


def test_fresh_store_rebuilds_the_same_counts_after_a_restart(tmp_path):
    # "persistence round-trip" for this design: no snapshot key is ever
    # written for this counter - a NEW HistoryStore pointed at the same
    # CSV (simulating a process restart) must rebuild identical counts
    # via its own load-time scan.
    path = str(tmp_path / "h.csv")
    hs = HistoryStore(path)
    _live_row(hs, "p1", "range")
    _live_row(hs, "p2", "range")
    _live_row(hs, "p3", "bear")

    revived = HistoryStore(path)
    assert revived.regime_live_count("range") == 2
    assert revived.regime_live_count("bear") == 1


def test_counter_never_rescans_the_csv_per_admission_call(tmp_path):
    """The O(1)-at-admission contract: once loaded, repeated
    regime_live_count() calls against an UNCHANGED file must never
    re-open it - only a cheap stat() to confirm nothing changed."""
    path = tmp_path / "h.csv"
    hs = HistoryStore(str(path))
    _live_row(hs, "p1", "range")
    hs.regime_live_count("range")          # pays the one load-time scan

    real_open = open
    opens = {"n": 0}

    def _spy_open(file, *a, **k):
        if str(file) == str(path):
            opens["n"] += 1
        return real_open(file, *a, **k)

    with mock.patch("builtins.open", _spy_open):
        for _ in range(50):
            hs.regime_live_count("range")
    assert opens["n"] == 0


def test_counter_rescans_when_the_file_changes_under_the_process(tmp_path):
    """An EXTERNAL rewrite (another process, a migration script) must be
    picked up - the mtime/size cache invalidates, unlike a naive
    load-once-forever cache that would silently go stale."""
    path = str(tmp_path / "h.csv")
    hs = HistoryStore(path)
    _live_row(hs, "p1", "range")
    assert hs.regime_live_count("range") == 1

    # a second, independent store instance appends behind hs's back
    other = HistoryStore(path)
    _live_row(other, "p2", "range")

    assert hs.regime_live_count("range") == 2


def test_candidate_only_rows_never_trigger_the_incremental_hook(tmp_path):
    # _append_row's incremental branch is gated on source=='live'; a
    # candidate-only corpus must report zero for every regime without
    # ever having run the (never-invoked-here) live-row increment path
    hs = HistoryStore(str(tmp_path / "h.csv"))
    for i, label in enumerate(("range", "bear", "crisis")):
        hs._append_row(f"cand-{i}", "ETH", "long", _feats(label), 1, 0.0,
                       "candidate")
    assert all(hs.regime_live_count(r) == 0 for r in _REGIME_FEATURE)
