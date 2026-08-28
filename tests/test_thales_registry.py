"""docs/thales/REGISTRY.md contract enforcement (docs/thales/README.md).

The registry is a MEASUREMENT STANDARD for idea lifecycle, not a tunable:
these pins exist so an entry cannot silently rot (the forbidden chain:
add -> never incorporate -> conclude failed -> be forgot). An incomplete
entry, an unknown status, or a non-terminal entry whose review stamp
predates the declared last execution-era boundary is a red suite, not a
style nit. Loosening a pin here is the same move as lowering a gate
floor — don't.
"""
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs" / "thales" / "REGISTRY.md"

STATUSES = {"REGISTERED", "EVIDENCED", "STAGED", "INCORPORATED",
            "DORMANT", "REJECTED"}
TERMINAL = {"REJECTED"}
ID_RE = re.compile(r"^TH-R-\d{3}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DETAIL_FIELDS = ("Footprint:", "Capture:", "Evidence:", "Falsifier:")


def _read() -> str:
    return REGISTRY.read_text(encoding="utf-8")


def _rows(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        if line.startswith("| TH-R-"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows.append(cells)
    return rows


def _parse_date(s: str) -> date:
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d))


def test_registry_exists_with_boundary_stamp():
    text = _read()
    m = re.search(r"last_boundary:\s*(\d{4}-\d{2}-\d{2})", text)
    assert m, "REGISTRY.md must declare 'last_boundary: YYYY-MM-DD'"
    _parse_date(m.group(1))


def test_rows_complete_and_statuses_legal():
    rows = _rows(_read())
    assert rows, "registry summary table has no TH-R rows"
    seen = set()
    for cells in rows:
        assert len(cells) == 5, f"row must have 5 cells: {cells}"
        rid, mistake, status, trigger, reviewed = cells
        assert ID_RE.match(rid), f"bad id {rid!r}"
        assert rid not in seen, f"duplicate id {rid}"
        seen.add(rid)
        assert mistake, f"{rid}: empty mistake"
        assert status in STATUSES, f"{rid}: unknown status {status!r}"
        assert DATE_RE.match(reviewed), f"{rid}: bad reviewed {reviewed!r}"
        if status not in TERMINAL:
            assert trigger and trigger.upper() != "TBD", \
                f"{rid}: non-terminal entry needs a real trigger"


def test_no_silent_aging_past_boundary():
    text = _read()
    boundary = _parse_date(
        re.search(r"last_boundary:\s*(\d{4}-\d{2}-\d{2})", text).group(1))
    for cells in _rows(text):
        rid, _, status, _, reviewed = cells
        if status in TERMINAL:
            continue
        assert _parse_date(reviewed) >= boundary, (
            f"{rid}: reviewed {reviewed} predates last_boundary "
            f"{boundary} — advance, re-stamp, or reject it")


def test_detail_blocks_match_table_bijectively():
    text = _read()
    table_ids = {c[0] for c in _rows(text)}
    blocks = re.split(r"^#### ", text, flags=re.M)[1:]
    block_ids = set()
    for block in blocks:
        rid = block.split()[0]
        assert ID_RE.match(rid), f"detail header lacks an id: {block[:40]!r}"
        block_ids.add(rid)
        for field in DETAIL_FIELDS:
            m = re.search(re.escape(field) + r"\s*(\S+)", block)
            assert m, f"{rid}: detail block missing non-empty '{field}'"
    assert block_ids == table_ids, (
        f"table/detail mismatch: only-in-table={table_ids - block_ids} "
        f"only-in-detail={block_ids - table_ids}")
