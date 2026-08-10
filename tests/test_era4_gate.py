"""The era-4 pre-registered gate (scripts/cohort_eval.py, 2026-08-10).

Registered at n=1 - before the cohort exists - which is the only honest
moment to write a stopping rule. These tests pin the registration itself:
the boundary instant, the n=50 refusal, the population rules (entry-opened
only, complete, post-boundary only), and the three readout outcomes. If any
of these change after the cohort accrues, that is not a refactor - it is the
thing pre-registration exists to prevent, and the test failing is the point.
"""
from __future__ import annotations

import csv
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "cohort_eval.py"
    sys.path.insert(0, str(ROOT / "scripts"))
    prior = sys.modules.get("cohort_eval")
    try:
        spec = importlib.util.spec_from_file_location("cohort_eval", path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules["cohort_eval"] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(ROOT / "scripts"))
        if prior is not None:
            sys.modules["cohort_eval"] = prior
        else:
            sys.modules.pop("cohort_eval", None)


CE = _load()


def test_registration_constants_are_pinned():
    """The boundary is aeeaae36's UTC instant - not a local date, which is
    the error class that mis-stamped it the first time."""
    assert CE.B4_TS == datetime(2026, 8, 10, 11, 3, 35,
                                tzinfo=timezone.utc).timestamp()
    assert CE.ERA4_MIN_N == 50
    assert CE._PREREG_ERA4 == "2026-08-10"
    # the original 2026-08-02 registration must be untouched by the addition
    assert CE.MIGRATION_TS == 1785634028
    assert CE.MIN_COHORT_N == 50
    assert CE._PREREG == "2026-08-02"


# ---------------------------------------------------------------- population
_COLS = ["ts", "order_id", "position_id", "purpose", "symbol", "side",
         "ordertype", "post_only", "attempt", "fill_size", "fill_price",
         "arrival_ref", "slip_bps", "fees_delta_usd", "remaining", "reason"]


def _trip(pid, purpose, t0, px_in, px_out, size=1.0, fee=0.10):
    mk = lambda ts, oid, pp, side, px: {  # noqa: E731
        "ts": ts, "order_id": oid, "position_id": pid, "purpose": pp,
        "symbol": "ADA/USD", "side": side, "ordertype": "limit",
        "post_only": "1", "attempt": "0", "fill_size": size,
        "fill_price": px, "arrival_ref": px, "slip_bps": "0",
        "fees_delta_usd": fee, "remaining": "0"}
    return [mk(t0, pid + "a", purpose, "buy", px_in),
            mk(t0 + 60, pid + "b", "exit", "sell", px_out)]


def _write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=_COLS)
        wr.writeheader()
        for r in rows:
            wr.writerow({c: r.get(c, "") for c in _COLS})


def test_population_rules(tmp_path):
    """Entry-opened + fully-closed + post-boundary ONLY. A hedge-opened trip
    is reconstructable (hedge IS an opening leg) but is not the strategy's
    trade; a pre-boundary close belongs to the inflated-fill eras."""
    b4 = CE.B4_TS
    rows = []
    rows += _trip("in-era4", "entry", b4 + 1000, 100.0, 110.0)     # counted
    rows += _trip("hedge4", "hedge", b4 + 2000, 100.0, 95.0)       # excluded
    rows += _trip("pre-b4", "entry", b4 - 5000, 100.0, 120.0)      # excluded
    # still-open: opening leg only
    rows.append({"ts": b4 + 3000, "order_id": "x", "position_id": "open",
                 "purpose": "entry", "symbol": "ADA/USD", "side": "buy",
                 "ordertype": "limit", "post_only": "1", "attempt": "0",
                 "fill_size": 1.0, "fill_price": 100.0,
                 "arrival_ref": 100.0, "slip_bps": "0",
                 "fees_delta_usd": 0.1, "remaining": "0"})
    p = tmp_path / "fills.csv"
    _write(p, rows)
    trips = CE.era4_trips(str(p))
    assert len(trips) == 1
    assert trips[0]["gross_pct"] == pytest.approx(10.0)
    assert trips[0]["net_pct"] == pytest.approx(10.0 - 0.2)


def test_duplicate_fill_patterns_are_dropped(tmp_path):
    """position_id is not the identity - the 16x re-log class."""
    b4 = CE.B4_TS
    rows = _trip("a", "entry", b4 + 1000, 100.0, 110.0) \
        + _trip("b", "entry", b4 + 1000, 100.0, 110.0)   # identical pattern
    p = tmp_path / "fills.csv"
    _write(p, rows)
    assert len(CE.era4_trips(str(p))) == 1


# ------------------------------------------------------------------ readout
def _mk(gross_net):
    return [{"t": 0.0, "gross_pct": g, "net_pct": n} for g, n in gross_net]


def test_refuses_verdict_below_n50():
    s = CE.era4_section(_mk([(1.0, 0.5)] * 49))
    assert s["readout"] == "ACCRUING"
    assert s["verdict_available"] is False
    assert s["progress"] == "49/50"


def test_no_gross_edge_readout():
    s = CE.era4_section(_mk([(-0.1, -0.4)] * 50))
    assert s["verdict_available"] is True
    assert s["readout"] == "NO_GROSS_EDGE"


def test_cost_bound_readout():
    s = CE.era4_section(_mk([(0.5, -0.2)] * 50))
    assert s["readout"] == "COST_BOUND"


def test_continue_readout():
    s = CE.era4_section(_mk([(0.8, 0.2)] * 50))
    assert s["readout"] == "CONTINUE"


def test_empty_cohort_is_accruing_not_a_crash():
    s = CE.era4_section([])
    assert s["readout"] == "ACCRUING"
    assert s["n"] == 0
