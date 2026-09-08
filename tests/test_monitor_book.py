"""Tests for monitor/book.py — order-book structure (pure functions)."""

from __future__ import annotations

import pytest

from monitor import book

# A stylised FLOWUSD book: mid 0.02865, bracket walls at -1.9% / +1.2%.
BIDS = [
    (0.0286, 5_000),
    (0.0285, 190_000),
    (0.0284, 14_000),
    (0.0282, 130_000),
    (0.0281, 1_937_000),
    (0.0209, 150_000),
]
ASKS = [
    (0.0287, 83_000),
    (0.0288, 133_000),
    (0.0290, 1_231_000),
    (0.0291, 247_000),
    (0.0350, 240_000),
    (6.5, 10_000),
]


def test_mid_and_usd():
    assert book.mid_price(BIDS, ASKS) == pytest.approx(0.02865)
    assert book.usd([(2.0, 3.0), (1.0, 4.0)]) == 10.0


def test_depth_bands_partition_the_book():
    bands = book.depth_bands(BIDS, ASKS)
    total_b = sum(b["bid_usd"] for b in bands)
    total_a = sum(b["ask_usd"] for b in bands)
    mid = book.mid_price(BIDS, ASKS)
    assert total_b == pytest.approx(book.usd([x for x in BIDS if x[0] >= mid * 0.75]))
    assert total_a == pytest.approx(book.usd([x for x in ASKS if x[0] <= mid * 1.25]))
    assert all(-1 <= b["imbalance"] <= 1 for b in bands)


def test_cumulative_ratio():
    c = book.cumulative(BIDS, ASKS, 3)
    assert c["bid_usd"] == pytest.approx(book.usd(BIDS[:5]))
    assert c["ask_usd"] == pytest.approx(book.usd(ASKS[:4]))
    assert c["ratio"] == pytest.approx(c["bid_usd"] / c["ask_usd"])


def test_walls_threshold():
    assert [p for p, _ in book.walls(BIDS)] == [0.0285, 0.0282, 0.0281, 0.0209]
    assert book.walls(BIDS, min_usd=50_000) == [(0.0281, 1_937_000)]


def test_slippage_walks_levels_and_reports_worst():
    s = book.slippage(ASKS, 5_000)
    assert s is not None
    assert s["worst"] == 0.0288  # $2,382 at 0.0287 then the rest at 0.0288
    assert s["avg"] == pytest.approx(
        5_000 / (83_000 + (5_000 - 0.0287 * 83_000) / 0.0288)
    )
    assert book.slippage([(1.0, 1.0)], 10.0) is None


def test_exit_estimate_fees_and_pnl():
    e = book.exit_estimate(BIDS, 74_693.88, 0.02937, taker_fee=0.0038)
    assert e is not None
    assert e["worst"] == 0.0285
    gross = 0.0286 * 5_000 + 0.0285 * (74_693.88 - 5_000)
    assert e["proceeds"] == pytest.approx(gross * (1 - 0.0038))
    assert e["pnl"] == pytest.approx(e["proceeds"] - 74_693.88 * 0.02937)
    assert book.exit_estimate([(0.03, 10)], 100, 0.03) is None


def test_wall_dynamics_tags():
    before = [
        (0.0291, 1_152_000),
        (0.0292, 307_000),
        (0.0288, 133_151),
        (0.0300, 133_145),
    ]
    after = [
        (0.0290, 1_231_000),
        (0.0291, 247_000),
        (0.0288, 133_105),
        (0.0300, 133_145),
    ]
    d = {x["price"]: x["change"] for x in book.wall_dynamics(before, after)}
    assert d == {
        0.0288: "held",
        0.0290: "new",
        0.0291: "shrank",
        0.0292: "pulled",
        0.0300: "held",
    }


def test_report_includes_dynamics_and_exit_when_asked():
    rep = book.report(BIDS, ASKS, prev=(BIDS, ASKS), exit_units=1000.0, avg_cost=0.0290)
    assert rep["exit"]["pnl"] < 0
    assert all(x["change"] == "held" for x in rep["bid_dynamics"])
    assert rep["far_ask_usd"] == pytest.approx(6.5 * 10_000)
    assert 6.5 not in [
        p for p, _ in rep["ask_walls"]
    ]  # >25% away excluded from near walls
    assert 0.0350 in [p for p, _ in rep["ask_walls"]]  # +22% is still "near"


def test_get_refuses_non_kraken_host(monkeypatch):
    monkeypatch.setattr(book, "KRAKEN", "https://evil.example/0/public")
    with pytest.raises(ValueError):
        book._get("Depth", "pair=FLOWUSD")
