"""29h — fills.csv torn-row durability.

A process kill mid-append (auto_update's taskkill escalation, power loss)
leaves a partial final line in outputs/fills.csv with no newline. The next
append then FUSED the new fill onto the torn fragment, permanently welding
two records into one malformed row in the P&L book of record — the same
ledger whose contamination once produced a 27x aggregate error. The
appender must heal a torn tail by terminating it first, so the fragment
isolates as one junk row that csv consumers skip, and every real fill stays
parseable in its own row.
"""
import csv

from core.fill_ledger import append_fill


def _read_rows(path):
    return list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))


def test_torn_tail_is_healed_not_fused(tmp_path):
    path = tmp_path / "fills.csv"
    append_fill(path, {"ts": 1, "order_id": "A", "fill_price": "100"})
    # crash mid-append: a partial row with no terminating newline
    path.write_bytes(path.read_bytes() + b"2,torn-partial")
    append_fill(path, {"ts": 3, "order_id": "B", "fill_price": "200"})

    by_id = {r["order_id"]: r for r in _read_rows(path) if r.get("order_id")}
    assert "A" in by_id, "the intact pre-crash fill must survive"
    assert "B" in by_id, \
        "the post-crash fill must land in its own row, not fuse onto the torn tail"
    assert by_id["B"]["fill_price"] == "200"   # columns still aligned


def test_normal_appends_are_untouched(tmp_path):
    path = tmp_path / "fills.csv"
    append_fill(path, {"ts": 1, "order_id": "A", "fill_price": "100"})
    append_fill(path, {"ts": 2, "order_id": "B", "fill_price": "200"})
    rows = _read_rows(path)
    assert [r["order_id"] for r in rows] == ["A", "B"]
