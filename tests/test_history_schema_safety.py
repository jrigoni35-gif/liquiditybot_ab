"""Regressions for HistoryStore schema handling, from the 2026-07-11
training-data loss:

1. Schema rotation lived in __init__, so merely CONSTRUCTING a HistoryStore
   (overfit_check's load_dataset, or any QA script on the default path)
   rotated the production CSV as a side effect. After the SMC schema bump
   (36 -> 43 features), the first read-only QA run swept the bot's entire
   accumulated live training set (~87 rows) into a .bak that was later
   lost. Reads must never mutate the file.

2. Appends never re-checked the on-disk header, so a long-lived runner
   holding the OLD schema in memory appended 43-column rows under the new
   50-column header - all three flatten-close labels written 2026-07-11
   were misaligned. An append into a file with a different header must
   rotate it (preserving the data) and write its own consistent header.
"""
import csv

import numpy as np

from ml.features import FEATURE_NAMES
from ml.history import HistoryStore


def _feats():
    return np.zeros(len(FEATURE_NAMES))


def _old_schema_file(path, n_rows=2):
    header = ["position_id", "asset", "side", "old_feat_a", "old_feat_b",
              "label", "net_pnl_usd", "source", "ts"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for i in range(n_rows):
            w.writerow([f"p{i}", "BTC", "long", "0.1", "0.2",
                        "1", "5.00", "live", "1700000000"])
    return header


def test_construct_and_read_never_touch_mismatched_file(tmp_path):
    path = tmp_path / "hist.csv"
    _old_schema_file(path, n_rows=3)
    before = path.read_bytes()

    store = HistoryStore(str(path))                 # construction: no-op
    assert store.row_count() == 3                   # reads work
    X, y, w = store.load_training_data()            # unusable rows skipped
    assert len(X) == 0

    assert path.read_bytes() == before              # file byte-identical
    assert list(tmp_path.glob("*.bak_*")) == []     # nothing rotated


def test_construct_does_not_create_missing_file(tmp_path):
    path = tmp_path / "hist.csv"
    store = HistoryStore(str(path))
    assert not path.exists()
    assert store.row_count() == 0
    X, y, w = store.load_training_data()
    assert len(X) == 0
    assert not path.exists()


def test_append_rotates_mismatched_file_and_writes_consistent_row(tmp_path):
    path = tmp_path / "hist.csv"
    _old_schema_file(path, n_rows=2)
    store = HistoryStore(str(path))

    store._append_row("pid-new", "ETH", "long", _feats(), 1, 2.5, "live")

    baks = list(tmp_path.glob("*.bak_*"))
    assert len(baks) == 1                           # old data preserved
    with open(baks[0], encoding="utf-8") as f:
        assert sum(1 for _ in f) == 3               # header + 2 old rows

    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == store._header                 # fresh correct header
    assert len(rows) == 2                           # header + the new row
    assert len(rows[1]) == len(store._header)       # row width == header

    X, y, w = store.load_training_data()            # and it round-trips
    assert len(X) == 1 and y[0] == 1.0


def test_append_to_matching_file_does_not_rotate(tmp_path):
    path = tmp_path / "hist.csv"
    store = HistoryStore(str(path))
    store._append_row("a", "BTC", "long", _feats(), 1, 1.0, "live")
    store._append_row("b", "BTC", "short", _feats(), 0, -1.0, "live")

    assert list(tmp_path.glob("*.bak_*")) == []
    assert store.row_count() == 2
    X, y, w = store.load_training_data()
    assert len(X) == 2


def test_stale_process_cannot_corrupt_newer_schema_file(tmp_path):
    """The exact live failure: a process whose in-memory header differs
    from the on-disk one appends. It must rotate first, never interleave."""
    path = tmp_path / "hist.csv"
    store_new = HistoryStore(str(path))
    store_new._append_row("n1", "BTC", "long", _feats(), 1, 1.0, "live")

    stale = HistoryStore(str(path))
    stale._header = ["position_id", "asset", "side", "f1", "f2",
                     "label", "net_pnl_usd", "source", "ts"]
    stale._append_row("s1", "ETH", "short", np.zeros(2), 0, -2.0, "live")

    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == stale._header                 # stale got its own file
    assert all(len(r) == len(rows[0]) for r in rows)   # no misaligned rows
    baks = list(tmp_path.glob("*.bak_*"))
    assert len(baks) == 1                           # new-schema row kept
    with open(baks[0], newline="", encoding="utf-8") as f:
        bak_rows = list(csv.reader(f))
    assert bak_rows[0] == store_new._header
    assert all(len(r) == len(bak_rows[0]) for r in bak_rows)
