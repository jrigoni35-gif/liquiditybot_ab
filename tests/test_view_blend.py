"""core/view_blend.py - Black-Litterman views on the target basket. The
instrument must be honest before any view is trusted: no views -> the basket
exactly; an unpromoted view moves nothing; the posterior matches the
textbook's second closed form; spot constraints hold."""
import numpy as np
import pytest

from core import view_blend as vb

A = ["BTC", "ETH", "PAXG", "LINK"]
SIG = vb.shrunk_cov(np.random.default_rng(1).normal(0, 0.02, (400, 4))
                    + np.random.default_rng(2).normal(0, 0.01, (400, 1)))
WB = {a: 0.9 / 4 for a in A}


def test_no_views_returns_the_basket_exactly():
    w = vb.blend(A, WB, SIG, [], invest_frac=0.9)
    assert all(w[a] == pytest.approx(WB[a], rel=1e-9) for a in A)


def test_an_unpromoted_view_moves_nothing():
    v = vb.View("xs", {"BTC": 1, "ETH": -1}, q=0.05, confidence=0.0)
    w = vb.blend(A, WB, SIG, [v], invest_frac=0.9)
    assert all(w[a] == pytest.approx(WB[a], rel=1e-9) for a in A)


def test_posterior_matches_the_second_closed_form():
    pi = vb.implied_returns(np.array([WB[a] for a in A]), SIG, 3.0)
    v = vb.View("v", {"BTC": 1, "ETH": -1}, q=0.01, confidence=0.3)
    mu = vb.posterior(pi, SIG, A, [v])
    p = np.array([1, -1, 0, 0.0])
    ts = vb.TAU * SIG
    om = (1 / 0.3 - 1) * p @ ts @ p
    ref = pi + ts @ p * (0.01 - p @ pi) / (p @ ts @ p + om)
    assert np.allclose(mu, ref, rtol=1e-9, atol=1e-12)


def test_a_relative_view_tilts_between_assets_and_confidence_scales_it():
    q = vb.grinold_q(0.05, 0.02, 1.0)          # a realistic view: 0.1%
    lo = vb.blend(A, WB, SIG, [vb.View("x", {"BTC": 1, "ETH": -1}, q, 0.1)], 0.9)
    hi = vb.blend(A, WB, SIG, [vb.View("x", {"BTC": 1, "ETH": -1}, q, 0.4)], 0.9)
    assert hi["BTC"] > lo["BTC"] > WB["BTC"]
    assert hi["ETH"] < lo["ETH"] < WB["ETH"]


def test_absolute_views_can_lower_exposure_but_never_raise_it_past_the_cap():
    bear = vb.View("m", {a: 0.25 for a in A}, q=-0.05, confidence=0.4)
    bull = vb.View("m", {a: 0.25 for a in A}, q=+0.50, confidence=0.5)
    assert sum(vb.blend(A, WB, SIG, [bear], 0.9).values()) < 0.9 - 1e-6
    wb = vb.blend(A, WB, SIG, [bull], 0.9, cap_mult=2.0)
    assert sum(wb.values()) <= 0.9 + 1e-9
    assert all(0.0 <= wb[a] <= 2.0 * WB[a] + 1e-12 for a in A)


def test_long_only_under_a_strong_negative_view():
    v = vb.View("x", {"PAXG": -1, "BTC": 1}, q=0.5, confidence=0.5)
    w = vb.blend(A, WB, SIG, [v], 0.9)
    assert min(w.values()) >= 0.0 and w["PAXG"] < WB["PAXG"]


def test_confidence_comes_only_from_forward_promotion_and_is_capped():
    assert vb.confidence_from_status("UNDECIDED", 30.0) == 0.0
    assert vb.confidence_from_status("ELIMINATED FOR TRIPS", 30.0) == 0.0
    assert vb.confidence_from_status("LIVE", float("nan")) == 0.0
    a, b = vb.confidence_from_status("LIVE", 1.0), vb.confidence_from_status("LIVE", 2.0)
    assert 0.0 < a < b <= vb.MAX_CONFIDENCE
    assert vb.confidence_from_status("LIVE", 60.0) == vb.MAX_CONFIDENCE
    # a forward-proven edge too small for a TRIP is exactly what a view is
    assert vb.confidence_from_status("EDGE BELOW ROUND TRIP", 20.0) == \
        vb.confidence_from_status("LIVE", 20.0) > 0.0
    assert vb.confidence_from_status("ELIMINATED AS TILT", 30.0) == 0.0


def test_risk_scale_only_ever_derisks_and_missing_data_is_neutral():
    assert vb.risk_scale(None, None) == 1.0
    assert vb.risk_scale(float("nan"), float("nan")) == 1.0
    assert vb.risk_scale(1.0, 0.5) == 1.0                    # calm: untouched
    assert vb.risk_scale(3.0, None) == pytest.approx(0.5)    # floored
    assert vb.risk_scale(2.0, 4.0) == pytest.approx(0.5)
    assert 0.5 <= vb.risk_scale(1.8, -2.5) < 1.0


def test_grinold_q_is_ic_times_sigma_times_score():
    assert vb.grinold_q(0.05, 0.04, -1.5) == pytest.approx(-0.003)


def test_an_oversized_view_saturates_at_the_caps_not_beyond():
    """Mean-variance is hypersensitive: a 1% view on 2%-vol assets is a huge
    Sharpe and drives weights to the spot constraints at ANY confidence. The
    caps (0 floor, cap_mult x basket, invest_frac total) are what bound it -
    which is why views must be sized by grinold_q, never by hand."""
    w = vb.blend(A, WB, SIG, [vb.View("x", {"BTC": 1, "ETH": -1}, 0.01, 0.1)], 0.9)
    assert w["BTC"] == pytest.approx(2.0 * WB["BTC"]) and w["ETH"] == 0.0
