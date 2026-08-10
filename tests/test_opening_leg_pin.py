"""A HEDGE IS AN OPENING LEG - pinned across every fills-reading tool.

THE BUG THIS EXISTS TO PREVENT. Five separate report scripts reconstructed
round trips from outputs/fills.csv by testing `purpose == "entry"` for the
opening side. A position opened by a HEDGE leg therefore had entry_size == 0
and was discarded as "partial or malformed". On the live ledger that dropped
159 of 400 round trips - 40% of the book and 77% of every fee ever paid - out
of scripts/breakeven_test.py, the single tool that answers "does this strategy
have an edge before costs". The exclusion INVERTED its printed prescription:

    entry-only : 235 trips, median gross +0.0505%, "not 'no edge' - fix exit
                 geometry, cost is the binding constraint"
    corrected  : 394 trips, median gross -0.0305%, "gross is negative with
                 fees zeroed; no execution or selection change fixes it"

The class recurred five times because each script re-derived the same rule
independently, so this pins all of them at once. Two layers:

  1. an AST pin - no fills-reading script may compare a `purpose` value to
     the bare string "entry". The pin PARSES rather than greps, because a
     substring check matches these modules' own prose explaining the bug
     (the identical trap caught tests/test_heat_reads_the_book.py's first
     draft).
  2. a behavioural pin - a synthetic hedge-opened round trip must survive
     reconstruction and carry its P&L, which no amount of constant-renaming
     can satisfy vacuously.
"""
from __future__ import annotations

import ast
import csv
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

# Every script that reconstructs positions from fills.csv. If a new one is
# added it belongs here; the roster is asserted non-empty so an accidental
# rename cannot silently empty the whole pin.
FILLS_READERS = (
    "breakeven_test.py",
    "cohort_eval.py",           # era-4 gate reconstruction (2026-08-10)
    "cost_attribution.py",
    "cost_truth_report.py",
    "geometry_search.py",
    "random_entry_control.py",
)


def _load(name: str):
    path = SCRIPTS / name
    sys.path.insert(0, str(SCRIPTS))
    # The module MUST be registered in sys.modules before exec_module:
    # @dataclass resolves its own module via sys.modules[cls.__module__],
    # so an unregistered module raises AttributeError on NoneType
    # (cost_truth_report.py hits this).
    prior = sys.modules.get(path.stem)
    try:
        spec = importlib.util.spec_from_file_location(path.stem, path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(SCRIPTS))
        if prior is not None:
            sys.modules[path.stem] = prior
        else:
            sys.modules.pop(path.stem, None)


def test_roster_is_not_empty_and_all_exist():
    """A pin over a vanished roster passes vacuously - forbid that."""
    assert FILLS_READERS, "roster emptied"
    for name in FILLS_READERS:
        assert (SCRIPTS / name).exists(), f"{name} missing - update the roster"


@pytest.mark.parametrize("name", FILLS_READERS)
def test_no_bare_entry_comparison_in_fills_readers(name):
    """AST pin: `purpose == "entry"` (in either operand order) is forbidden.

    Parsing, not grepping: every one of these modules contains the string
    'purpose == "entry"' inside the docstring that explains this very bug.
    """
    tree = ast.parse((SCRIPTS / name).read_text(encoding="utf-8"))

    def _is_purpose(node: ast.AST) -> bool:
        # r.get("purpose") / r["purpose"] / purpose
        if isinstance(node, ast.Call):
            fn = node.func
            return (isinstance(fn, ast.Attribute) and fn.attr == "get"
                    and bool(node.args)
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == "purpose")
        if isinstance(node, ast.Subscript):
            return (isinstance(node.slice, ast.Constant)
                    and node.slice.value == "purpose")
        if isinstance(node, ast.Name):
            return node.id == "purpose"
        return False

    def _is_entry_str(node: ast.AST) -> bool:
        return isinstance(node, ast.Constant) and node.value == "entry"

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            continue
        if not isinstance(node.ops[0], (ast.Eq, ast.NotEq)):
            continue
        left, right = node.left, node.comparators[0]
        # str(...) wrappers are transparent for this purpose
        for a, b in ((left, right), (right, left)):
            if _is_purpose(a) and _is_entry_str(b):
                offenders.append(getattr(node, "lineno", -1))
    assert not offenders, (
        f"{name}: compares a purpose to the bare string 'entry' at line(s) "
        f"{offenders}. A hedge is an OPENING leg - use _OPEN_PURPOSES, or "
        f"this silently drops every hedge-opened round trip.")


@pytest.mark.parametrize("name", FILLS_READERS)
def test_open_purposes_constant_covers_hedge(name):
    """Whatever the roster member calls it, hedge must be an opening leg."""
    mod = _load(name)
    const = getattr(mod, "_OPEN_PURPOSES", None)
    assert const is not None, f"{name} defines no _OPEN_PURPOSES"
    assert "entry" in const and "hedge" in const, (
        f"{name}._OPEN_PURPOSES={const!r} must contain both 'entry' and "
        f"'hedge'")
    assert "exit" not in const, (
        f"{name}._OPEN_PURPOSES={const!r} must NOT contain 'exit' - an exit "
        f"closes risk; counting it as an opening leg double-counts notional")


def _write_fills(path: Path, rows):
    cols = ["ts", "order_id", "position_id", "purpose", "symbol", "side",
            "ordertype", "post_only", "attempt", "fill_size", "fill_price",
            "arrival_ref", "slip_bps", "fees_delta_usd", "remaining", "reason"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=cols)
        wr.writeheader()
        for r in rows:
            wr.writerow({c: r.get(c, "") for c in cols})


def _round_trip(pid, purpose, t0, px_in, px_out, size=1.0, fee=0.10):
    """One opening leg + one exit leg, as fills.csv stores them."""
    return [
        {"ts": t0, "order_id": pid + "a", "position_id": pid,
         "purpose": purpose, "symbol": "ADA/USD", "side": "buy",
         "ordertype": "limit", "post_only": "1", "attempt": "0",
         "fill_size": size, "fill_price": px_in, "arrival_ref": px_in,
         "slip_bps": "0", "fees_delta_usd": fee, "remaining": "0"},
        {"ts": t0 + 60, "order_id": pid + "b", "position_id": pid,
         "purpose": "exit", "symbol": "ADA/USD", "side": "sell",
         "ordertype": "limit", "post_only": "1", "attempt": "0",
         "fill_size": size, "fill_price": px_out, "arrival_ref": px_out,
         "slip_bps": "0", "fees_delta_usd": fee, "remaining": "0"},
    ]


def test_hedge_opened_round_trip_is_reconstructed(tmp_path):
    """The behavioural pin: a hedge-opened trip must COUNT, with its P&L.

    Constructed so the two populations disagree in sign. If hedge-opened
    trips are dropped the tool reports a WINNER; counting them it reports a
    loser - exactly the inversion that occurred on the live ledger.
    """
    rows = []
    # one entry-opened winner: +10.0 gross
    rows += _round_trip("p-entry", "entry", 1_700_000_000, 100.0, 110.0)
    # three hedge-opened losers summing to -15.0. Their exit prices must
    # DIFFER: these tools key identity on the fill pattern, so three
    # byte-identical trips are correctly collapsed to one by the dedupe.
    for i, px_out in enumerate((94.0, 95.0, 96.0)):
        rows += _round_trip(f"p-hedge{i}", "hedge",
                            1_700_000_100 + i * 1000, 100.0, px_out)
    p = tmp_path / "fills.csv"
    _write_fills(p, rows)

    ca = _load("cost_attribution.py")
    trades, skipped = ca.load(str(p))

    assert len(trades) == 4, (
        f"expected 4 round trips, got {len(trades)}; skipped={dict(skipped)}. "
        f"Hedge-opened trips are being discarded.")
    assert skipped.get("no_opening_leg", 0) == 0

    total_gross = sum(t["gross"] for t in trades)
    assert total_gross == pytest.approx(10.0 - 15.0), (
        "hedge-opened P&L is missing from the total")
    assert total_gross < 0, (
        "sign inversion: dropping the hedge population turns a losing book "
        "into a winning one - the exact live defect")


def test_skip_counter_names_the_reason(tmp_path):
    """A pooled 'skipped' total is what let a 40% exclusion look routine."""
    rows = []
    rows += _round_trip("good", "entry", 1_700_000_000, 100.0, 110.0)
    # an opening leg with no exit -> still_open, NOT 'malformed'
    rows.append(
        {"ts": 1_700_001_000, "order_id": "o1", "position_id": "open-only",
         "purpose": "entry", "symbol": "ADA/USD", "side": "buy",
         "ordertype": "limit", "post_only": "1", "attempt": "0",
         "fill_size": 1.0, "fill_price": 100.0, "arrival_ref": 100.0,
         "slip_bps": "0", "fees_delta_usd": 0.1, "remaining": "0"})
    p = tmp_path / "fills.csv"
    _write_fills(p, rows)

    ca = _load("cost_attribution.py")
    trades, skipped = ca.load(str(p))
    assert len(trades) == 1
    assert skipped["still_open"] == 1, dict(skipped)
    assert sum(skipped.values()) == 1
    # the reason must be distinguishable, not lumped under a generic bucket
    assert skipped.get("malformed_row", 0) == 0
    assert skipped.get("no_opening_leg", 0) == 0
