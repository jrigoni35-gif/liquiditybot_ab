"""Pins for scripts/ledger_continuity.py.

This check exists because a one-time structural argument ("the hole predates
the boundary, so it cannot bias the gate") was true when it was made and
would have been quietly wrong the moment a hole landed on the other side.
The tests therefore pin the CONTRADICTION, not the reassurance:

  * a hole after the boundary MUST flag contaminating   <- the whole point
  * a hole before it must NOT                            <- no crying wolf
  * the boundary must be IMPORTED, never written here    <- staleness pin
  * an unrunnable check must NOT read as clean           <- 0-findings != safe
"""
from __future__ import annotations

import csv
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "scripts" / "ledger_continuity.py"


def _load():
    spec = importlib.util.spec_from_file_location("ledger_continuity", _SRC)
    if spec is None or spec.loader is None:  # pragma: no cover
        pytest.skip("ledger_continuity.py not importable")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ledger_continuity"] = mod
    spec.loader.exec_module(mod)
    return mod


lc = _load()

COLS = ["ts", "order_id", "position_id", "purpose", "symbol", "side",
        "ordertype", "post_only", "attempt", "fill_size", "fill_price",
        "arrival_ref", "slip_bps", "fees_delta_usd", "remaining", "reason",
        "exec_era"]


def _row(oid, ts, size="1.0", price="4000", fee="1.6"):
    r = dict.fromkeys(COLS, "")
    r.update({"ts": str(ts), "order_id": oid, "purpose": "entry",
              "symbol": "ETH/USD", "side": "buy", "fill_size": size,
              "fill_price": price, "fees_delta_usd": fee})
    return r


def _write(p: Path, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _boundary():
    b, why = lc._boundary()
    if b is None:
        pytest.skip(f"cohort boundary unavailable: {why}")
    return b


# --- the contradiction the tool exists to keep testing -------------------

def test_orphan_after_the_boundary_is_contaminating(tmp_path):
    b = _boundary()
    out = tmp_path / "outputs"
    _write(out / "fills.csv", [_row("live1", b - 5000)])
    _write(out / "fills.csv.bak_1",
           [_row("live1", b - 5000), _row("INSIDE", b + 3600)])
    res = lc.scan(out)
    assert res["ok"] is True
    assert res["orphans_inside_cohort"] == 1
    assert res["contaminating"] is True


def test_orphan_before_the_boundary_is_not_contaminating(tmp_path):
    b = _boundary()
    out = tmp_path / "outputs"
    _write(out / "fills.csv", [_row("live1", b - 5000)])
    _write(out / "fills.csv.bak_1",
           [_row("live1", b - 5000), _row("OLD", b - 99999)])
    res = lc.scan(out)
    assert res["orphans_total"] == 1
    assert res["orphans_inside_cohort"] == 0
    assert res["contaminating"] is False


def test_whole_ledger_reports_no_orphans(tmp_path):
    b = _boundary()
    out = tmp_path / "outputs"
    rows = [_row("a", b - 5000), _row("c", b + 10)]
    _write(out / "fills.csv", rows)
    _write(out / "fills.csv.bak_1", rows)
    res = lc.scan(out)
    assert res["orphans_total"] == 0
    assert res["contaminating"] is False


# --- staleness: the boundary must never be copied into this file ---------

def test_boundary_is_imported_not_hardcoded():
    """A date copied to a second place WILL disagree with the first place.
    The cohort has already been re-fenced once (cut #7, the geometry epoch);
    this check has to follow automatically."""
    src = _SRC.read_text(encoding="utf-8")
    code = "\n".join(
        ln for ln in src.splitlines()
        if not ln.lstrip().startswith("#"))
    code = re.sub(r'""".*?"""', "", code, flags=re.S)
    assert not re.search(r"\b2026-\d{2}-\d{2}\b", code), (
        "a literal date leaked into executable code - the boundary must come "
        "from cohort_eval, not from this file")
    assert "CAPITAL_EPOCH_TS" in src


def test_boundary_matches_cohort_eval_exactly():
    b = _boundary()
    spec = importlib.util.spec_from_file_location(
        "ce", Path(__file__).resolve().parents[1] / "scripts" / "cohort_eval.py")
    ce = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ce)
    assert b == float(ce.CAPITAL_EPOCH_TS)


# --- an unrunnable check must never read as clean ------------------------

def test_missing_ledger_is_not_clean(tmp_path):
    out = tmp_path / "outputs"
    out.mkdir()
    res = lc.scan(out)
    assert res["ok"] is False
    assert "why" in res


def test_empty_ledger_is_not_clean(tmp_path):
    out = tmp_path / "outputs"
    _write(out / "fills.csv", [])
    res = lc.scan(out)
    assert res["ok"] is False


# --- the continuous half -------------------------------------------------

def test_history_appends_one_line_per_run(tmp_path):
    b = _boundary()
    out = tmp_path / "outputs"
    _write(out / "fills.csv", [_row("a", b - 5000)])
    for _ in range(3):
        lc.append_history(out, lc.scan(out))
    lines = (out / "ledger_continuity.jsonl").read_text(
        encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    rec = json.loads(lines[0])
    assert "contaminating" in rec and "orphans_inside_cohort" in rec
    assert "read_at" in rec


def test_history_records_the_contaminating_verdict(tmp_path):
    b = _boundary()
    out = tmp_path / "outputs"
    _write(out / "fills.csv", [_row("live1", b - 5000)])
    _write(out / "fills.csv.bak_1",
           [_row("live1", b - 5000), _row("INSIDE", b + 3600)])
    lc.append_history(out, lc.scan(out))
    rec = json.loads((out / "ledger_continuity.jsonl").read_text(
        encoding="utf-8").strip())
    assert rec["contaminating"] is True
    assert rec["orphans_inside_cohort"] == 1
