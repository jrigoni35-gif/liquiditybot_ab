"""Pins for the markout decomposition (execution/markout.py, 2026-08-23).

WHY IT EXISTS. markout_bps is the SUM of captured spread and alpha, and for a
PASSIVE fill the spread term dominates. Measured in a synthetic market with
provably zero alpha (driftless walk, 6000 paths), the shipped crossing rule
reported -0.484 bps at t=-36.7 and a price-time-priority rule reported +0.451
at t=+11.0 - both exactly -/+ the half-spread, in a market where there was no
alpha to find. Reading markout_bps as an edge is therefore reading the spread.

WHAT IS PINNED, AND WHAT DELIBERATELY IS NOT.
  * the identity, the geometry, backward compatibility, persistence
  * NOT "alpha is fill-rule invariant" - that was measured FALSE (planting
    +0.06 bps/step, true 0.360 at h=6 came back 0.275 under one rule and
    0.740 under the other). Alpha removes the spread term exactly; it does
    not remove fill-time selection. A pin asserting invariance would be
    asserting something known to be untrue.
"""
from __future__ import annotations

from execution.markout import MarkoutTracker


def _one(side="buy", price=100.0, mid0=100.5, mark=101.0):
    m = MarkoutTracker({"horizons_sec": [1.0], "window": 50})
    m.record_fill("ETH/USD", "ETH", side, price, 0.0, mid_at_fill=mid0)
    m.poll({"ETH/USD": mark}, 2.0)
    return m.snapshot()["by_asset"]["ETH"]["1"]


def test_identity_markout_equals_spread_capture_plus_alpha():
    c = _one()
    assert abs(c["markout_bps"]
               - (c["spread_capture_bps"] + c["alpha_bps"])) < 0.6


def test_spread_capture_is_the_fill_geometry_not_a_forecast():
    """A buy filled BELOW the mid has captured spread, by construction, with
    no forward information involved. mark is irrelevant to that term."""
    a = _one(mark=101.0)
    b = _one(mark=99.0)          # opposite forward move
    assert a["spread_capture_bps"] == b["spread_capture_bps"]
    assert a["alpha_bps"] != b["alpha_bps"]


def test_a_maker_buy_at_the_bid_shows_positive_capture():
    c = _one(side="buy", price=100.0, mid0=100.5)
    assert c["spread_capture_bps"] > 0


def test_sell_side_capture_is_signed_the_same_way():
    """A sell filled ABOVE the mid also CAPTURED spread: positive."""
    c = _one(side="sell", price=100.0, mid0=99.5, mark=99.0)
    assert c["spread_capture_bps"] > 0


def test_alpha_is_zero_when_the_mark_does_not_move_from_the_fill_mid():
    c = _one(mid0=100.5, mark=100.5)
    assert abs(c["alpha_bps"]) < 1e-6
    assert c["spread_capture_bps"] > 0      # capture survives; alpha does not


# --- the degraded paths must degrade, not fabricate ---------------------

def test_no_mid_means_no_decomposition_not_a_guessed_one():
    m = MarkoutTracker({"horizons_sec": [1.0]})
    m.record_fill("ETH/USD", "ETH", "buy", 100.0, 0.0)      # OLD signature
    m.poll({"ETH/USD": 101.0}, 2.0)
    c = m.snapshot()["by_asset"]["ETH"]["1"]
    assert c["markout_bps"] == 100.0        # unchanged behaviour
    assert "alpha_bps" not in c
    assert "spread_capture_bps" not in c


def test_nonpositive_mid_is_rejected_rather_than_used():
    for bad in (0.0, -1.0, float("nan")):
        m = MarkoutTracker({"horizons_sec": [1.0]})
        m.record_fill("ETH/USD", "ETH", "buy", 100.0, 0.0, mid_at_fill=bad)
        m.poll({"ETH/USD": 101.0}, 2.0)
        c = m.snapshot()["by_asset"]["ETH"]["1"]
        assert "alpha_bps" not in c, f"accepted a bad mid: {bad}"


def test_persistence_roundtrip_carries_the_fill_mid():
    m = MarkoutTracker({"horizons_sec": [5.0]})
    m.record_fill("ETH/USD", "ETH", "buy", 100.0, 0.0, mid_at_fill=100.5)
    m2 = MarkoutTracker({"horizons_sec": [5.0]})
    m2.restore(m.to_dict())
    m2.poll({"ETH/USD": 101.0}, 10.0)
    c = m2.snapshot()["by_asset"]["ETH"]["5"]
    assert "alpha_bps" in c, "mid0 lost across a restart"


def test_snapshot_written_before_the_decomposition_still_restores():
    """An old persisted file has no mid0 key; it must restore clean and
    simply produce no alpha for those in-flight fills."""
    old = {"pending": [{"symbol": "ETH/USD", "asset": "ETH", "sgn": 1.0,
                        "price": 100.0, "t0": 0.0, "done": []}],
           "obs": {}}
    m = MarkoutTracker({"horizons_sec": [5.0]})
    m.restore(old)
    m.poll({"ETH/USD": 101.0}, 10.0)
    c = m.snapshot()["by_asset"]["ETH"]["5"]
    assert c["markout_bps"] == 100.0
    assert "alpha_bps" not in c
