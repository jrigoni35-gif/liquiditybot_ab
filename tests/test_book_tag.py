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

def test_history_header_ends_with_label_era(tmp_path):
    # geometry-alignment T3 (2026-07-27) added TWO MORE trailing columns
    # after `label_era` - same additive pattern this file's own docstring
    # describes for `book` itself. gate-truth instrumentation T2
    # (2026-07-28) added 7 more sg_* columns after THOSE - pt_frac/sl_frac
    # are no longer last, but their relative order is preserved.
    hs = HistoryStore(str(tmp_path / "h.csv"))
    # tail membership BY NAME: the literal tail changes with every
    # trailing addition (price anchor 2026-08-04 made sg_conc no longer
    # last); what this test protects is the RELATIVE order, which names
    # can assert without renumbering on each bump.
    h = hs._header
    assert h.index("sg_flow") + 6 == h.index("sg_conc")
    assert h.index("label_era") < h.index("pt_frac") < h.index("sg_flow")
    # 41b (2026-08-08): the 4 avail_* bookkeeping columns trail the price
    # pair - the price anchor is no longer last, relative order preserved
    # schema 94 (2026-08-24): label_ret_pct is the new tail; the avail
    # block is one slot earlier. Same additive pattern as ever.
    # schema 95 (2026-08-27, sandbox prototype): control_arm is the new
    # tail; label_ret_pct and the avail block each shift one slot earlier.
    assert h[-1] == "control_arm"
    assert h[-2] == "label_ret_pct"
    assert h[-7:-2] == ["avail_web", "avail_equity", "avail_options",
                       "quotes_frozen", "avail_darkpool"]  # 96 (09-21, v10)
    assert h.index("entry_price") + 1 == h.index("exit_price")
    assert h.index("exit_price") + 1 == h.index("avail_web")
    assert h.index("book") + 1 == h.index("label_era")
    assert h.index("pt_frac") + 1 == h.index("sl_frac")
    assert h.index("candidate_id") + 1 == h.index("book")


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
    is purely additive at the end, defaulting "5m". Extended (label-era
    instrumentation, DEEP DIVE progress.md) to also pin the NEXT additive
    column: barrier="realized" derives label_era "exit_sim" (see
    label_era_of/_EXIT_SIM_BARRIERS in ml/history.py). Extended again
    (geometry-alignment T3, 2026-07-27) to pin the two NEWEST trailing
    columns, pt_frac/sl_frac — a caller that never heard of them (this one)
    defaults both to 0.0. Extended again (gate-truth instrumentation T2,
    2026-07-28) to pin the 7 NEWEST trailing columns, sg_flow..sg_conc —
    a caller that never heard of `gate_components` (this one) defaults
    all seven to 0.0."""
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
    # source before this change) with "5m" (book), "exit_sim" (label_era,
    # derived from barrier="realized"), "0.000000"/"0.000000" (pt_frac/
    # sl_frac defaults) and "0.0000" x7 (sg_flow..sg_conc defaults)
    # appended as the newest trailing columns
    # extended again (price anchor, 2026-08-04): entry_price/exit_price
    # trail everything; a caller that never heard of them (this one)
    # defaults both to "0" = absent.
    # extended again (41b, 2026-08-08): the 4 avail_* flags trail the
    # price pair; a caller that never heard of `avail` (this one) writes
    # all four BLANK = unknown - "" and never "0", because "0" would
    # claim the feed was measured down.
    # extended again (label_ret_pct, schema 94, 2026-08-24): the labeled
    # outcome magnitude trails everything; a caller that never heard of it
    # (this one) writes BLANK = UNKNOWN - never 0.0, because a fabricated
    # zero is indistinguishable from a genuine zero-return outcome.
    # extended again (control_arm, schema 95, 2026-08-27, sandbox
    # prototype): unlike every column above, this one is NEVER blank for a
    # new row - asset + signal_ts (1000.0 here) are always present, so
    # _append_row always computes a real "1"/"0" via _control_arm_tag. The
    # expected value is derived through the REAL function, not a hardcoded
    # hash literal - the value itself is not what this test protects; byte-
    # identical WIRING is.
    expected_arm = "1" if history_mod._control_arm_tag("BTC", 1000.0) else "0"
    expected = ["pid-1", "BTC", "long",
                *[f"{v:.6f}" for v in feats],
                "1", "12.34", "live",
                f"{fixed_now:.0f}", "1000", "realized", "1", "entered",
                "cand-9", "5m", "exit_sim", "0.000000", "0.000000",
                *(["0.0000"] * 7), "0", "0", "", "", "", "", "", "",
                expected_arm]
    assert row == expected
    assert header[-1] == "control_arm"   # schema 95
    assert header[-2] == "label_ret_pct"
    assert header[-3] == "avail_darkpool"   # schema 96 (2026-09-21, v10)
    assert header[-4] == "quotes_frozen"
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
    assert Code.LB_ADVERSE_SURVIVED.value == "LB-042"
    assert Code.LB_PAUSED.value == "LB-050"


# ---------------------------------------------------------------------
# task C5, Part 1 item 1: 5m label isolation at load
#
# ml/history.py's load_training_data is the ONE sanctioned ml/ touch
# beyond this file's own C1 column - a book=="long" filter AT LOAD, so
# the long-horizon accumulation book's realized closes (a completely
# different trading process: patient, ladder-gated, no p(win)/edge
# signal) can never leak into the 5m model's training X/y, however they
# got into signal_history.csv.
# ---------------------------------------------------------------------

def _write_5m_row(hs: HistoryStore, position_id: str, seed: float) -> None:
    feats = np.full(len(FEATURE_NAMES), seed)
    hs.log_entry(position_id, "ETH", "long", feats, book="5m")
    hs.log_close(position_id, 3.0 + seed)


def _write_long_row(hs: HistoryStore, position_id: str, seed: float) -> None:
    # book=="long" rows are written directly via _append_row (task C4's
    # own _handle_fill never threads real "features" for a long-book
    # order today - a separately-tracked gap, out of this task's scope
    # per the report), exactly like test_append_row_book_param_writes_tag
    # above already does for a bare book="long" row.
    feats = np.full(len(FEATURE_NAMES), seed)
    hs._append_row(position_id, "BTC", "long", feats, 1, 99.0, "live",
                   book="long")


def test_load_training_data_excludes_book_long_rows(tmp_path, monkeypatch):
    import ml.history as history_mod
    monkeypatch.setattr(history_mod.time, "time", lambda: 1_700_000_000.0)
    hs = HistoryStore(str(tmp_path / "h.csv"))
    for i in range(5):
        _write_5m_row(hs, f"5m-{i}", float(i))
    X, y, w = hs.load_training_data()
    assert len(X) == 5
    for i in range(5):
        _write_long_row(hs, f"long-{i}", float(100 + i))
    X2, y2, w2 = hs.load_training_data()
    assert len(X2) == 5, "long-book rows must never enter the 5m model's X/y"
    assert np.array_equal(X, X2)
    assert np.array_equal(y, y2)
    assert np.array_equal(w, w2)


def test_load_training_data_byte_identical_with_and_without_long_rows(
        tmp_path, monkeypatch):
    """The load-bearing pin: build the SAME 5m corpus twice, one CSV with
    long rows interleaved among the 5m rows, one without any long rows
    at all - X/y/w must be byte-identical (np.array_equal, not just
    same-length) either way. time.time() is pinned for the whole test
    (writes AND both loads) so the recency-decay weight column - a
    function of wall-clock `now` at LOAD time, nothing to do with the
    book filter under test - cannot introduce a confounding difference
    between the two separately-timed load_training_data() calls."""
    import ml.history as history_mod
    monkeypatch.setattr(history_mod.time, "time", lambda: 1_700_000_000.0)
    hs_clean = HistoryStore(str(tmp_path / "clean.csv"))
    hs_mixed = HistoryStore(str(tmp_path / "mixed.csv"))
    for i in range(8):
        _write_5m_row(hs_clean, f"5m-{i}", float(i) * 0.37)
        _write_5m_row(hs_mixed, f"5m-{i}", float(i) * 0.37)
        if i % 2 == 0:
            _write_long_row(hs_mixed, f"long-{i}", float(500 + i))

    Xc, yc, wc = hs_clean.load_training_data()
    Xm, ym, wm = hs_mixed.load_training_data()
    assert len(Xc) == 8
    assert len(Xm) == 8
    assert np.array_equal(Xc, Xm)
    assert np.array_equal(yc, ym)
    assert np.array_equal(wc, wm)


def test_load_training_data_long_rows_excluded_from_clash_dedup_prescan(
        tmp_path):
    """A long-book row that happens to share (asset, side, feature-vector)
    with a 5m CANDIDATE row must not spuriously mark that candidate a
    "duplicate of a live fill" - book=="long" is excluded from the
    dedup prescan too, not just the final X/y build."""
    hs = HistoryStore(str(tmp_path / "h.csv"))
    feats = np.full(len(FEATURE_NAMES), 7.0)
    # a 5m CANDIDATE row (source="candidate") with this exact vector
    hs._append_row("cand-1", "ETH", "long", feats, 1, 0.0, "candidate",
                   signal_ts=1000.0, barrier="pt", disp="confirmed")
    # a long-book LIVE row with the SAME (asset, side, feature-vector) -
    # contrived collision, proving the exclusion holds even here
    hs._append_row("long-1", "ETH", "long", feats, 1, 50.0, "live",
                   book="long")
    X, y, w = hs.load_training_data()
    assert len(X) == 1, ("the 5m candidate row must survive - the "
                         "long-book row must never count as its live twin")
    assert Code.LB_PAUSED.value == "LB-050"
