"""Execution-era provenance + the restart-replay guard (owed 62, OM-085).

TWO DEFECTS THESE PIN, both CDO-review findings on the ledger the era-4
verdict gate reads:

  1. PROVENANCE. Four execution-era boundaries deep, era membership lived
     only in a join between row timestamps and boundary constants scattered
     across config prose - a silent-misattribution risk. exec_era now
     travels WITH the row. Old files keep their own width (never a ragged
     book of record) until scripts/migrate_fills_schema.py upgrades them
     explicitly, with a backup, leaving old rows BLANK - back-filling a
     guess would manufacture provenance the rows never had.

  2. REPLAY. The ledger is fsync-durable per fill; order state is durable
     per snapshot. A kill between them restores a pre-fill order that the
     sim re-executes, appending the same fill twice - the duplicates that
     correlated 1:1 with restarts and produced the 16x/27x headline error.
     append_fill now refuses a row whose (order_id, size, price, remaining)
     already exists; remaining decreases monotonically within an order, so
     legitimate fills never collide.

Doubles: the real ManagedOrder and FillEvent (test-double-fidelity - a
double may only implement API the production object actually has).
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from core.fill_ledger import (COLS, EXEC_ERA, _seen_keys, append_fill,
                              fill_row)
from execution.order_manager import FillEvent, ManagedOrder

ROOT = Path(__file__).resolve().parents[1]

# The pre-exec_era 16-column schema, written out LITERALLY.
#
# This was `COLS[:-1]`, a DERIVED fixture, and deriving it was the bug: when
# `book` was appended on 2026-09-05 the slice silently became 17 columns
# INCLUDING exec_era, so the migration test below started writing a 17-name
# header against a 16-value row and kept passing. The fixture drifted out of
# agreement with what its own comment claimed and the tests went quiet rather
# than red - the worst failure mode a test has, because it reports green
# forever. A fixture that stands for a HISTORICAL schema must never be
# computed from the CURRENT one.
_OLD_COLS = ["ts", "order_id", "position_id", "purpose", "symbol", "side",
             "ordertype", "post_only", "attempt", "fill_size", "fill_price",
             "arrival_ref", "slip_bps", "fees_delta_usd", "remaining",
             "reason"]


def test_old_cols_fixture_has_not_drifted():
    """Guard the guard: this fixture stands for a frozen historical schema,
    so it must stay 16 columns and must NOT contain any later-appended
    field, however COLS grows."""
    assert len(_OLD_COLS) == 16
    assert "exec_era" not in _OLD_COLS and "book" not in _OLD_COLS
    assert COLS[:16] == _OLD_COLS, (
        "the shipped schema no longer starts with the historical 16 columns - "
        "either a column was inserted/reordered (which misassigns every "
        "archived row) or this fixture is wrong")


def _order(oid="o1", remaining=0.0):
    o = ManagedOrder(order_id=oid, txid=None, asset="ADA", pair="ADAUSD",
                     symbol="ADA/USD", side="buy", price=0.5, size=10.0,
                     purpose="entry", post_only=True)
    o.arrival_ref = 0.5
    o.filled = o.size - remaining
    return o


def _row(oid="o1", remaining=0.0, size=10.0, now=1000.0):
    o = _order(oid, remaining)
    ev = FillEvent(o, size, 0.5, final=remaining == 0.0)
    return fill_row(o, ev, fees_delta=0.01, now=now)


def _read(path):
    with open(path, newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        return next(rd), list(rd)


def _fresh(path):
    """The guard cache is per-process; tests simulate distinct processes by
    clearing it, exactly what a restart does."""
    _seen_keys.pop(str(path), None)


# ------------------------------------------------------------- provenance
def test_new_file_carries_exec_era():
    # APPEND-AT-END, pinned as the PROPERTY rather than as a frozen last
    # column. This used to read `COLS[-1] == "exec_era"`, which asserted the
    # opposite of the discipline its own comment named: it froze exec_era in
    # final position, so the next field appended - exactly what the discipline
    # calls for - reddened this test. Pinning the immutable PREFIX enforces
    # append-only (no insert, no reorder, no rename, no delete of a shipped
    # column) while leaving the tail free to grow, which is what keeps every
    # historical row readable: csv.DictReader assigns positionally, so a row
    # written before a column existed reads None for it - the three-way
    # ("absent" vs "" vs value) that scripts/cohort_eval.py's era provenance
    # depends on. Reordering or inserting would silently misassign every
    # archived row instead.
    _SHIPPED_PREFIX = [
        "ts", "order_id", "position_id", "purpose", "symbol", "side",
        "ordertype", "post_only", "attempt", "fill_size", "fill_price",
        "arrival_ref", "slip_bps", "fees_delta_usd", "remaining", "reason",
        "exec_era",
    ]
    assert COLS[:len(_SHIPPED_PREFIX)] == _SHIPPED_PREFIX, (
        "fills.csv columns were reordered, renamed or inserted into - every "
        "archived row would be silently misassigned by DictReader. New fields "
        "APPEND to the end only.")
    assert "exec_era" in COLS
    assert len(COLS) == len(set(COLS)), "duplicate column name in COLS"
    r = _row()
    assert r["exec_era"] == EXEC_ERA
    # Cut #7 (geometry epoch, deployed 2026-08-11T01:33:50Z): era 4 -> 7.
    # Cut #8 (fee-truth epoch, "boundary #5" on the fill-axis counter,
    # applied 2026-08-28T02:34:42Z by scripts/boundary5_stage.py --apply
    # under the 2026-08-27 operator adjudication): era 7 -> 8. The sha names
    # ca55e2ba, the commit that DEFINES the package, because a commit cannot
    # name its own hash - see core/fill_ledger.py's comment for why that is
    # the resolution that keeps the bump on the behavior commit with no debt.
    # Cut #9 (Tier-3 fee correction, applied 2026-08-30 by
    # scripts/fee_correction_stage.py --apply under operator ARM "fee
    # correction only"; cut #8 over-stated fees ~2x vs the real 22/38 tier):
    # era 8 -> 9, sha 16ec821e (the fee_tier_correction adjudication commit).
    # The assertion changing here IS the record of the bump, per convention.
    assert EXEC_ERA == "9-16ec821e", (
        "era constant must name the CURRENT era and its boundary commit - "
        "if you bumped it deliberately, this pin moves in the same commit")
    import re
    assert re.fullmatch(r"\d+-[0-9a-f]{8}", EXEC_ERA), (
        "era constant format: <era>-<8-hex boundary commit>")


def test_append_to_new_file_writes_full_schema(tmp_path):
    p = tmp_path / "fills.csv"
    append_fill(p, _row())
    hdr, rows = _read(p)
    assert hdr == COLS
    assert rows[0][hdr.index("exec_era")] == EXEC_ERA


def test_old_header_file_never_gets_ragged_rows(tmp_path):
    """An un-migrated 16-col file keeps its own width - a consumer must
    never meet a row wider than the header in the book of record."""
    p = tmp_path / "fills.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(_OLD_COLS)
    _fresh(p)
    append_fill(p, _row())
    hdr, rows = _read(p)
    assert hdr == _OLD_COLS
    assert all(len(r) == len(_OLD_COLS) for r in rows)


def test_migration_upgrades_backs_up_and_is_idempotent(tmp_path):
    p = tmp_path / "fills.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(_OLD_COLS)
        w.writerow(["1000.0", "old1", "pid1", "entry", "ADA/USD", "buy",
                    "limit", "1", "0", "10", "0.5", "0.5", "0", "0.01",
                    "0", ""])
    r = subprocess.run([sys.executable,
                        str(ROOT / "scripts" / "migrate_fills_schema.py"),
                        "--fills", str(p)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    hdr, rows = _read(p)
    assert hdr == COLS
    # old rows are BLANK, not back-filled with a guess
    assert rows[0][hdr.index("exec_era")] == ""
    assert list(tmp_path.glob("*.preschema_*")), "no backup written"
    before = p.read_bytes()
    r2 = subprocess.run([sys.executable,
                         str(ROOT / "scripts" / "migrate_fills_schema.py"),
                         "--fills", str(p)],
                        capture_output=True, text=True, timeout=60)
    assert r2.returncode == 0 and "untouched" in r2.stdout
    assert p.read_bytes() == before


# ------------------------------------------------------------ replay guard
def test_identical_row_is_refused_same_process(tmp_path):
    p = tmp_path / "fills.csv"
    append_fill(p, _row(oid="a", remaining=0.0))
    append_fill(p, _row(oid="a", remaining=0.0))       # replay
    _hdr, rows = _read(p)
    assert len(rows) == 1, "the replay row reached the book of record"


def test_identical_row_is_refused_across_restart(tmp_path):
    """The real signature: the duplicate arrives from a NEW process whose
    in-memory cache is empty - the guard must reload from disk."""
    p = tmp_path / "fills.csv"
    append_fill(p, _row(oid="a", remaining=0.0))
    _fresh(p)                                          # "restart"
    append_fill(p, _row(oid="a", remaining=0.0))
    _hdr, rows = _read(p)
    assert len(rows) == 1


def test_legitimate_partial_sequence_is_not_collateral(tmp_path):
    """Two partials of one order share size and price but never
    `remaining` - the key must let them both through."""
    p = tmp_path / "fills.csv"
    append_fill(p, _row(oid="a", remaining=7.0, size=3.0))
    append_fill(p, _row(oid="a", remaining=4.0, size=3.0))
    append_fill(p, _row(oid="b", remaining=0.0, size=10.0))
    _hdr, rows = _read(p)
    assert len(rows) == 3


def test_om085_is_a_registered_code():
    from core.codes import Code
    assert Code.OM_LEDGER_DUP_REFUSED == "OM-085"


# ------------------------------------------------------- book provenance
def test_fill_row_records_the_book(tmp_path):
    """BOOK PROVENANCE (2026-09-05). Which book opened a leg was in hand at
    the call site (main.py passes book=order.meta.get("book","5m")) but was
    never written, so every cohort reconstruction pooled long-book adds with
    5m entries and could only separate them by joining signal_history on
    position_id - a join limited to LABELED rows, hence silently partial
    exactly while a live cohort is accruing."""
    r = _row()
    assert "book" in r, "the ledger still cannot distinguish a long-book add"


def test_book_is_blank_not_guessed_when_absent():
    """A missing book must read as UNKNOWN, never as a fabricated '5m'.

    This is the control_arm ""-vs-0 lesson applied one file over: a blank
    means 'the writer had no value', a value means 'this is what it was'.
    Defaulting to "5m" here would make an unattributable leg indistinguishable
    from a real 5m entry, permanently, in the book of record."""
    import types
    order = types.SimpleNamespace(
        order_id="o1", position_id="p1", purpose="entry", symbol="ETH/USD",
        side="buy", ordertype="limit", post_only=True, remaining=0.0,
        arrival_ref=0.0, meta={})                      # no "book" key at all
    event = types.SimpleNamespace(fill_size=1.0, fill_price=100.0)
    row = fill_row(order, event, 0.0, 1788000000.0)
    assert row["book"] == "", (
        f"absent book was written as {row['book']!r} - a guessed default in "
        f"the book of record cannot be told from a real reading later")


def test_a_row_written_before_book_existed_reads_as_absent(tmp_path):
    """The append-at-END payoff: an archived 17-field row read against the
    18-column header must give book=None (writer predates the field) while
    exec_era still resolves. If this breaks, every historical row is
    misassigned."""
    import csv as _csv
    p = tmp_path / "fills.csv"
    legacy_cols = [c for c in COLS if c != "book"]
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(legacy_cols)
        w.writerow(["1788000000", "o1", "p1", "entry", "ETH/USD", "buy",
                    "limit", "1", "0", "1", "100", "", "", "0.1", "0",
                    "", "9-16ec821e"])
    # re-read under the CURRENT header, as every reader does
    with open(p, newline="", encoding="utf-8") as f:
        rows = list(_csv.DictReader(f))
    assert rows[0]["exec_era"] == "9-16ec821e", \
        "exec_era was misassigned by the schema growth - archived rows are corrupt"
    assert rows[0].get("book") is None, \
        "a pre-book row must read absent (None), not blank or a value"
