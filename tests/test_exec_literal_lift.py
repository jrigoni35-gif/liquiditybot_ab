"""tests/test_exec_literal_lift.py — §C/§D guessing-code lifts are behavior-
preserving: the router's depth-shortfall penalty defaults to the old 25 bps
constant (and steers when configured); pretrade was audited clean (impact_eta,
min_edge_cost_ratio, miss_cost_bps were already config-backed)."""
import pytest

from execution.routing import SmartOrderRouter, VenueQuote


def _quote(depth_usd, ts):
    return VenueQuote(venue="kraken", best_bid=100.0, best_ask=100.02,
                      depth_usd=depth_usd, ts=ts, taker_fee_bps=40.0,
                      maker_fee_bps=25.0)


def test_depth_penalty_default_equals_old_constant():
    r = SmartOrderRouter({})
    assert r.depth_penalty_bps == 25.0
    # half cover -> half the penalty, weighted by w_depth (0.6 default)
    score_full, _ = r._score(_quote(2000.0, ts=1000.0), "buy", 1000.0,
                             now=1000.0)
    score_half, _ = r._score(_quote(500.0, ts=1000.0), "buy", 1000.0,
                             now=1000.0)
    assert score_half - score_full == pytest.approx(0.6 * 0.5 * 25.0)


def test_depth_penalty_steers():
    r = SmartOrderRouter({"depth_penalty_bps": 50.0})
    s_full, _ = r._score(_quote(2000.0, ts=1.0), "buy", 1000.0, now=1.0)
    s_zero, _ = r._score(_quote(0.0, ts=1.0), "buy", 1000.0, now=1.0)
    assert s_zero - s_full == pytest.approx(0.6 * 50.0)
    # hostile negative clamps to zero penalty, never a depth BONUS
    assert SmartOrderRouter({"depth_penalty_bps": -5}).depth_penalty_bps == 0.0
