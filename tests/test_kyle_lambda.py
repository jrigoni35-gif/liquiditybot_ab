"""Pins for scripts/kyle_lambda.py.

The bug this file exists to prevent was made ONCE already, on the first run:
slip_bps is ALREADY side-normalised by core/fill_ledger.py:89-90 (positive =
adverse, for buys and sells alike), and the first cut signed the notional on
top of it. Applying the sign twice split the sample into two mirror halves
and produced a SIGNIFICANT NEGATIVE lambda for ADA (t=-4.12) - "bigger orders
got better prices" - which is an artefact, not a market fact.

So the sign convention is pinned directly: a synthetic corpus with a KNOWN
positive impact must recover a POSITIVE lambda from both buys and sells.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "scripts" / "kyle_lambda.py"


def _load():
    spec = importlib.util.spec_from_file_location("kyle_lambda", _SRC)
    if spec is None or spec.loader is None:  # pragma: no cover
        pytest.skip("kyle_lambda.py not importable")
    m = importlib.util.module_from_spec(spec)
    sys.modules["kyle_lambda"] = m
    spec.loader.exec_module(m)
    return m


kl = _load()


def _fill(symbol, side, size, price, slip, post_only=0):
    return {"symbol": symbol, "side": side, "fill_size": str(size),
            "fill_price": str(price), "slip_bps": str(slip),
            "post_only": str(post_only)}


def _planted(side: str, lam_per_1k: float, n: int = 60):
    """size sweep with slip = lam * notional/1000, i.e. a KNOWN lambda."""
    rows = []
    for i in range(n):
        size = 1.0 + i          # price 100 -> notional 100..
        notional = size * 100.0
        rows.append(_fill("X/USD", side, size, 100.0,
                          lam_per_1k * notional / 1000.0))
    return rows


def _cell(res, kind="taker"):
    return next(c for c in res["cells"] if c["kind"] == kind)


# --- the sign convention: the bug that was actually made ----------------

def test_positive_impact_recovers_positive_lambda_on_buys():
    res = kl.estimate(_planted("buy", 5.0), min_n=10)
    assert _cell(res)["lambda_bps_per_1k"] == pytest.approx(5.0, rel=1e-6)


def test_positive_impact_recovers_positive_lambda_on_SELLS_too():
    """slip_bps is already side-normalised, so a sell with adverse slip must
    give the SAME positive lambda. Re-signing the notional would flip it."""
    res = kl.estimate(_planted("sell", 5.0), min_n=10)
    assert _cell(res)["lambda_bps_per_1k"] == pytest.approx(5.0, rel=1e-6)


def test_buys_and_sells_pool_without_cancelling():
    """The double-sign bug made mixed buy/sell samples cancel toward zero or
    go negative. Pooled, they must still recover the planted lambda."""
    rows = _planted("buy", 5.0, 40) + _planted("sell", 5.0, 40)
    res = kl.estimate(rows, min_n=10)
    c = _cell(res)
    assert c["n"] == 80
    assert c["lambda_bps_per_1k"] == pytest.approx(5.0, rel=1e-6)
    assert c["lambda_bps_per_1k"] > 0


def test_zero_impact_recovers_zero_lambda():
    rows = [_fill("X/USD", "buy", 1.0 + i, 100.0, 0.0) for i in range(40)]
    res = kl.estimate(rows, min_n=10)
    assert _cell(res)["lambda_bps_per_1k"] == pytest.approx(0.0, abs=1e-9)


# --- maker and taker must never be pooled -------------------------------

def test_maker_and_taker_are_separate_cells():
    rows = _planted("buy", 5.0, 40)
    rows += [_fill("X/USD", "buy", 1.0 + i, 100.0, 0.0, post_only=1)
             for i in range(40)]
    res = kl.estimate(rows, min_n=10)
    kinds = {c["kind"] for c in res["cells"]}
    assert kinds == {"taker", "maker"}
    assert _cell(res, "taker")["lambda_bps_per_1k"] == pytest.approx(5.0,
                                                                    rel=1e-6)
    assert _cell(res, "maker")["lambda_bps_per_1k"] == pytest.approx(0.0,
                                                                     abs=1e-9)


# --- thin cells must be flagged, never silently reported ----------------

def test_thin_cell_is_flagged_below_floor():
    res = kl.estimate(_planted("buy", 5.0, 12), min_n=30)
    assert _cell(res)["below_floor"] is True


def test_no_size_variation_is_insufficient_not_a_lambda():
    rows = [_fill("X/USD", "buy", 2.0, 100.0, 3.0) for _ in range(40)]
    res = kl.estimate(rows, min_n=10)
    assert _cell(res).get("insufficient") is True


def test_unusable_rows_are_counted_not_silently_dropped():
    rows = _planted("buy", 5.0, 30)
    rows.append(_fill("X/USD", "buy", 0.0, 100.0, 1.0))     # zero size
    rows.append(_fill("X/USD", "sideways", 1.0, 100.0, 1.0))  # bad side
    res = kl.estimate(rows, min_n=10)
    assert res["skipped_rows"] == 2
