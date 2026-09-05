"""LOAD-PATH PARSE GUARD — a torn tail must not kill every training load.

THE DEFECT (measured 2026-09-04, sweep §3 CRITICAL-latent). The per-row parse
in SignalHistory.load_training_data() catches only (KeyError, ValueError):

    try:
        xr = [float(row[n]) for n in FEATURE_NAMES]
        yr = float(row["label"])
        ...
    except (KeyError, ValueError):
        continue

`csv.DictReader` is constructed with NO `restval`, so a SHORT row - the shape a
torn/truncated append leaves behind - yields **None** for every missing trailing
field. `float(None)` raises **TypeError**, which is absent from that tuple, so
it escapes load_training_data entirely and propagates out of every caller.

Why that is permanent rather than transient: `durable_append` isolates the torn
fragment in place, so the bad line is re-read on every subsequent load. Every
training-corpus consumer dies until a human hand-edits the CSV -
scripts/overfit_check.py (a DEFINITION-OF-DONE gate), train_meta, the learning
curve, feature stability and the interpret report.

The sibling finiteness guard 20 lines below is fully instrumented (dropped_dirty
+ ML-015). The parse path had no counter and no log line, so rows that DID get
dropped legitimately (an empty cell -> ValueError, which IS caught) vanished
from the corpus with nothing accounting for them.

These pins assert the PROPERTY - the load completes and the drop is counted -
not the pattern, so a future refactor that keeps the behaviour stays green.
"""
from __future__ import annotations

import csv

import pytest

pytest.importorskip("numpy")

import numpy as np                             # noqa: E402

from core.codes import Code                    # noqa: E402
from ml.features import FEATURE_NAMES          # noqa: E402
from ml.history import HistoryStore            # noqa: E402


def _seed(tmp_path, rows=6):
    """A real corpus written through the real entry/close append path."""
    h = HistoryStore(path=str(tmp_path / "signal_history.csv"))
    for i in range(rows):
        pid = f"pos{i:04d}"
        h.log_entry(position_id=pid, asset="ETH/USD", direction="long",
                    features=np.full(len(FEATURE_NAMES), 0.5, dtype=float))
        h.log_close(position_id=pid,
                    net_pnl_usd=1.0 if i % 2 else -1.0,
                    barrier="tb_pt" if i % 2 else "tb_sl",
                    entry_usd=100.0)
    return h


def _tear_last_row(path, keep_fields=30):
    """Truncate the final record ON A FIELD BOUNDARY - every surviving value
    intact, the trailing fields simply ABSENT. That is what makes DictReader
    hand back None (restval) rather than an empty string, and None is the
    TypeError path.

    This distinction is the whole point and it is easy to get wrong: cutting
    mid-FIELD leaves a partial value ("0.00341" -> "0.003"), which either
    parses fine or raises ValueError - and ValueError was ALREADY caught, so
    a mid-field tear exercises nothing. An earlier version of this helper cut
    at 40% of the record's bytes and was VACUOUS for exactly that reason:
    it stayed green with the fix removed. Verified by mutation, not by eye.

    keep_fields=30 is < the 68 columns the parse block reads (64 features up
    to header index 66, then `label` at 67), so at least one feature is
    guaranteed absent. A buffered append flushing a whole number of fields is
    a real shape, not a contrived one.
    """
    rows = list(csv.reader(path.open("r", encoding="utf-8", newline="")))
    header, body = rows[0], rows[1:]
    assert len(header) > keep_fields, "fixture assumption: schema wider than the cut"
    body[-1] = body[-1][:keep_fields]
    with path.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows([header, *body])


def test_torn_tail_does_not_kill_the_load(tmp_path):
    """THE REGRESSION. Against the old except-tuple this raises TypeError and
    the whole training corpus is unreadable until a human edits the file."""
    h = _seed(tmp_path)
    path = tmp_path / "signal_history.csv"
    _tear_last_row(path)

    # must NOT raise
    X, y, w = h.load_training_data()[:3]

    assert len(X) >= 4, (
        f"the load returned only {len(X)} rows - a single torn tail row must "
        f"cost exactly that row, not the corpus")
    assert len(X) == len(y) == len(w), (
        "parallel lists desynchronised - the atomic-per-row contract broke")


def test_the_torn_row_is_counted_not_silently_dropped(tmp_path):
    """A dropped row with no counter is indistinguishable from a row that was
    never written. The finiteness path has had dropped_dirty + ML-015 since
    2026-07; the parse path must account for its drops the same way."""
    h = _seed(tmp_path)
    _tear_last_row(tmp_path / "signal_history.csv")
    h.load_training_data()

    stats = h.last_load_stats
    assert "dropped_parse" in stats, (
        "last_load_stats has no dropped_parse key - the parse drop is "
        "unaccounted; a silent drop reads exactly like a row never written")
    assert stats["dropped_parse"] >= 1, (
        f"dropped_parse={stats.get('dropped_parse')} but a row WAS dropped")


def test_short_row_is_a_parse_drop_not_an_exception(tmp_path):
    """Injection at the precise mechanism: a DictReader short row yields None
    for the missing trailing fields, and float(None) is a TypeError."""
    h = _seed(tmp_path)
    path = tmp_path / "signal_history.csv"

    with path.open("r", encoding="utf-8", newline="") as fh:
        header = next(csv.reader(fh))
    # a row with only the first 3 of N columns -> None for all the rest
    with path.open("a", encoding="utf-8", newline="") as fh:
        fh.write(",".join(["ETH/USD", "0.5", "0.5"]) + "\n")

    assert len(header) > 3, "fixture assumption: the schema is wider than 3"
    X = h.load_training_data()[0]
    assert len(X) >= 4, "the short row must be dropped, not fatal"
    assert h.last_load_stats.get("dropped_parse", 0) >= 1


def test_parse_drop_code_is_registered(tmp_path):
    """CLAUDE.md invariant 6: new behaviour gets a REGISTERED code, never a
    bare string."""
    assert hasattr(Code, "ML_UNPARSEABLE_ROW"), \
        "the parse-drop disposition needs a registered code in core/codes.py"
    assert Code.ML_UNPARSEABLE_ROW.value.startswith("ML-")


def test_clean_corpus_reports_zero_parse_drops(tmp_path):
    """ANTI-RUBBER-STAMP. The counter must be able to read zero, or a green
    above proves nothing about whether it can distinguish the two cases."""
    h = _seed(tmp_path)
    h.load_training_data()
    assert h.last_load_stats.get("dropped_parse", 0) == 0, (
        "a clean corpus reported a parse drop - the counter is firing on "
        "healthy rows and every other assertion here is meaningless")


# ------------------------------------------------- C2: torn tail vs schema break
def test_one_torn_row_warns_but_a_broken_schema_ESCALATES(tmp_path, caplog):
    """ONE TORN ROW AND A BROKEN SCHEMA ARE NOT THE SAME EVENT.

    Catching TypeError turns a systematic cause - a schema change leaving a
    feature column absent for EVERY row - from a loud crash into an empty
    corpus. An empty corpus is not loud either: overfit_check substitutes its
    planted-signal SYNTHETIC benchmark below len(FEATURE_NAMES)*10 rows and
    prints a green. Trading a crash for a green definition-of-done gate would
    be strictly worse than the bug being fixed, so the SHARE must escalate.
    """
    import logging

    # (a) one torn row -> WARNING, and a small share
    h = _seed(tmp_path, rows=12)
    _tear_last_row(tmp_path / "signal_history.csv")
    with caplog.at_level(logging.WARNING):
        h.load_training_data()
    assert h.last_load_stats["dropped_parse"] == 1
    assert h.last_load_stats["parse_drop_share"] < 0.2
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR], \
        "a single torn tail row escalated to ERROR - that will cry wolf"

    # (b) every row short -> ERROR, naming it as a schema signature
    h2 = _seed(tmp_path / "b", rows=12)
    p2 = tmp_path / "b" / "signal_history.csv"
    rows = list(csv.reader(p2.open("r", encoding="utf-8", newline="")))
    header, body = rows[0], rows[1:]
    with p2.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows([header, *[r[:30] for r in body]])
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        h2.load_training_data()
    assert h2.last_load_stats["parse_drop_share"] == 1.0
    errs = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errs, (
        "every row failed to parse and it logged only a WARNING - "
        "indistinguishable from a torn tail, and the empty corpus that "
        "results makes overfit_check print a synthetic green")
    assert "SCHEMA" in errs[0].getMessage().upper()
