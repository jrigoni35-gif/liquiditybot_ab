"""Task C1 (Compounder Phase C) — `book` tag + LB code family.

Threads a `book` tag ("5m" default, "long" for the Compounder long-horizon
book) through Position -> persistence -> ml/history.py's training CSV, so
a future long-book position's fills, snapshots and labeled rows can be told
apart from the existing 5m scalping flow without touching any of the 5m
training/label semantics.

Zero 5m contamination is the load-bearing property here: every existing
construction/serialization/logging call site that never heard of `book`
must keep behaving EXACTLY as before, defaulting to "5m" everywhere,
including a byte-for-byte pin on the training row (this file adds a
trailing "book" column and changes nothing else about the row shape).
"""
import csv
from datetime import datetime, timezone

import numpy as np

from core.codes import Code
from core.persistence import position_from_dict, position_to_dict
from core.state import Position
from ml.features import FEATURE_NAMES
from ml.history import HistoryStore


def _pos(**kw):
    defaults = dict(position_id="p1", symbol="ETH/USD", direction="long",
                     entry_price=100.0, size=1.0, original_size=1.0,
                     opened_at=datetime.now(timezone.utc))
    defaults.update(kw)
    return Position(**defaults)


# ---------------------------------------------------------------------
# Position.book default
# ---------------------------------------------------------------------

def test_position_book_defaults_to_5m():
    pos = _pos()
    assert pos.book == "5m"


def test_position_book_can_be_set():
    pos = _pos(book="long")
    assert pos.book == "long"


# ---------------------------------------------------------------------
# persistence round-trip
# ---------------------------------------------------------------------

def test_persistence_round_trips_long_book():
    pos = _pos(book="long")
    d = position_to_dict(pos)
    assert d["book"] == "long"
    back = position_from_dict(d)
    assert back.book == "long"


def test_persistence_defaults_book_for_legacy_snapshot_without_key():
    pos = _pos(book="long")
    d = position_to_dict(pos)
    d.pop("book")                       # pre-C snapshot format
    legacy = position_from_dict(d)
    assert legacy.book == "5m"


# ---------------------------------------------------------------------
# history schema: header, width guard, row threading
# ---------------------------------------------------------------------

def test_history_header_ends_with_book(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    assert hs._header[-1] == "book"
    assert hs._header[-2] == "candidate_id"


def test_width_guard_accepts_current_shape(tmp_path, caplog):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    hs.log_entry("ok", "ETH", "long", np.zeros(len(FEATURE_NAMES)))
    hs.log_close("ok", 5.0)
    assert hs.row_count() == 1
    assert not any("ML-013" in r.getMessage() for r in caplog.records)


def test_logged_row_carries_book_tag(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    hs.log_entry("p1", "BTC", "long", np.zeros(len(FEATURE_NAMES)),
                book="long")
    hs.log_close("p1", 5.0)
    with open(hs.path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["book"] == "long"


def test_append_row_book_param_writes_tag(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    feats = np.zeros(len(FEATURE_NAMES))
    hs._append_row("p1", "BTC", "long", feats, 1, 5.0, "live", book="long")
    with open(hs.path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["book"] == "long"


def test_append_row_book_omitted_is_byte_identical_plus_5m(tmp_path, monkeypatch):
    """Pins that adding `book` changed NOTHING about the pre-existing row
    shape/formatting for a caller that never heard of it — the new column
    is purely additive at the end, defaulting "5m"."""
    import ml.history as history_mod
    fixed_now = 1700000000.0
    monkeypatch.setattr(history_mod.time, "time", lambda: fixed_now)

    hs = HistoryStore(str(tmp_path / "h.csv"))
    feats = np.array([0.1, 0.2, -0.3] * ((len(FEATURE_NAMES) // 3) + 1)
                     )[:len(FEATURE_NAMES)]
    hs._append_row("pid-1", "BTC", "long", feats, 1, 12.34, "live",
                   signal_ts=1000.0, barrier="realized", probe="1",
                   disp="entered", candidate_id="cand-9")

    with open(hs.path, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header, row = rows[0], rows[1]

    # this is exactly the pre-C1 serialization (mirrors _append_row's
    # csv.writer(f).writerow([...]) call, verified against the in-tree
    # source before this change) with "5m" appended as the new last column
    expected = ["pid-1", "BTC", "long",
                *[f"{v:.6f}" for v in feats],
                "1", "12.34", "live",
                f"{fixed_now:.0f}", "1000", "realized", "1", "entered",
                "cand-9", "5m"]
    assert row == expected
    assert header[-1] == "book"
    assert len(row) == len(header)


# ---------------------------------------------------------------------
# LB code family — exact value pins (brief-verbatim)
# ---------------------------------------------------------------------

def test_lb_code_values_pinned():
    assert Code.LB_ADD_PLACED.value == "LB-000"
    assert Code.LB_ADD_DENIED.value == "LB-010"
    assert Code.LB_ZONE_SHIFT.value == "LB-020"
    assert Code.LB_TIER_BANK.value == "LB-030"
    assert Code.LB_THESIS_INVALIDATED.value == "LB-031"
    assert Code.LB_RUNG_UP.value == "LB-040"
    assert Code.LB_RUNG_DOWN.value == "LB-041"
    assert Code.LB_PAUSED.value == "LB-050"
