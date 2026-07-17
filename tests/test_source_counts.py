"""tests/test_source_counts.py — HistoryStore.source_counts(): the learning-
velocity split (live vs candidate labels). Contract: column located from the
file's OWN header (never a hardcoded position), cached on (mtime,size) so the
runner's ~2s status builds don't rescan an unchanged file, and degenerate
files return {} instead of a fabricated split."""
import csv
import os

from ml.history import HistoryStore


def _write(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def test_counts_by_header_not_position(tmp_path):
    # 'source' deliberately NOT third-from-end: header lookup must win
    p = tmp_path / "h.csv"
    _write(p, ["position_id", "source", "asset", "label"],
           [["a", "live", "BTC", "1"],
            ["b", "candidate", "ETH", "0"],
            ["c", "candidate", "BTC", "1"]])
    hs = HistoryStore(str(p))
    assert hs.source_counts() == {"live": 1, "candidate": 2}


def test_cache_invalidates_on_append(tmp_path):
    p = tmp_path / "h.csv"
    _write(p, ["position_id", "asset", "source"], [["a", "BTC", "live"]])
    hs = HistoryStore(str(p))
    assert hs.source_counts() == {"live": 1}
    # append + force a distinct mtime (some filesystems have coarse stamps;
    # size change alone must also invalidate)
    with open(p, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["b", "ETH", "candidate"])
    os.utime(p)
    assert hs.source_counts() == {"live": 1, "candidate": 1}


def test_cache_hit_returns_copy(tmp_path):
    p = tmp_path / "h.csv"
    _write(p, ["position_id", "source"], [["a", "live"]])
    hs = HistoryStore(str(p))
    first = hs.source_counts()
    first["live"] = 999                       # caller mutation must not leak
    assert hs.source_counts() == {"live": 1}


def test_degenerate_files_return_empty(tmp_path):
    # missing file
    assert HistoryStore(str(tmp_path / "absent.csv")).source_counts() == {}
    # header without a 'source' column: no fabricated split
    p = tmp_path / "nosrc.csv"
    _write(p, ["position_id", "asset"], [["a", "BTC"]])
    assert HistoryStore(str(p)).source_counts() == {}
    # empty file
    p2 = tmp_path / "empty.csv"
    p2.write_text("", encoding="utf-8")
    assert HistoryStore(str(p2)).source_counts() == {}


def test_blank_source_bucketed_as_unknown(tmp_path):
    p = tmp_path / "h.csv"
    _write(p, ["position_id", "source"], [["a", ""], ["b", "live"]])
    assert HistoryStore(str(p)).source_counts() == {"unknown": 1, "live": 1}


def test_live_schema_roundtrip(tmp_path):
    # rows written by the store's own log path count correctly
    import numpy as np
    from ml.features import FEATURE_NAMES
    p = tmp_path / "h.csv"
    hs = HistoryStore(str(p))
    hs._append_row("p1", "BTC", "long", np.zeros(len(FEATURE_NAMES)), 1, 2.0,
                   source="live")
    hs._append_row("p2", "ETH", "short", np.zeros(len(FEATURE_NAMES)), 0, -1.0,
                   source="candidate")
    assert hs.source_counts() == {"live": 1, "candidate": 1}
