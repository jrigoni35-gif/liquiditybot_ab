"""Pins for ml/foundational_confidence.py — the shadow FC instrument.

Each pin guards one of the three coupled ideas: log-odds compounding, the
non-emotional attribution filter, and the anti-deadlock degradation.
"""
import math

import pytest

from ml.foundational_confidence import (DEFAULT_HALF_LIFE_S, L_CEIL, L_FLOOR,
                                        Foundation, combine, confidence_of,
                                        llr_binary)

_DAY = 86400.0


def test_prior_is_maximal_uncertainty():
    assert Foundation("f").confidence() == pytest.approx(0.5)
    assert confidence_of(0.0) == pytest.approx(0.5)


def test_validating_evidence_compounds():
    """Repeated validated observations ADD in log-odds -> confidence rises
    monotonically and compounds (the operator's compound improvement)."""
    f = Foundation("f", half_life_s=1e18)   # ~no decay, isolate compounding
    prev = 0.5
    for i in range(5):
        c = f.observe(i * _DAY, llr=0.5, attribution=1.0, independence=1.0)
        assert c > prev
        prev = c
    # 5 * 0.5 = 2.5 log-odds
    assert f.log_odds == pytest.approx(2.5)
    assert f.confidence() == pytest.approx(confidence_of(2.5))


def test_attribution_zero_does_not_move_confidence():
    """The non-emotional core: an outcome NOT caused by the foundation
    (attribution=0) leaves confidence untouched no matter the llr sign/size."""
    f = Foundation("f", half_life_s=1e18)
    f.observe(0.0, llr=-3.0, attribution=0.0, independence=1.0)  # a big 'loss'
    assert f.confidence() == pytest.approx(0.5)  # unmoved


def test_independence_scales_evidence():
    """Correlated observations (low independence) weigh less — cannot compound
    confidence out of overlapping trips (the n_eff ceiling)."""
    solo = Foundation("a", half_life_s=1e18)
    corr = Foundation("b", half_life_s=1e18)
    solo.observe(0.0, llr=1.0, attribution=1.0, independence=1.0)
    corr.observe(0.0, llr=1.0, attribution=1.0, independence=0.25)
    assert corr.log_odds == pytest.approx(0.25)
    assert solo.log_odds == pytest.approx(1.0)


def test_degradation_reverts_toward_uncertainty():
    """Anti-deadlock: absent fresh evidence, confidence decays toward 0.5. One
    half-life halves the log-odds."""
    f = Foundation("f", half_life_s=7 * _DAY)
    f.observe(0.0, llr=2.0, attribution=1.0, independence=1.0)
    assert f.log_odds == pytest.approx(2.0)
    # read 7 days later -> one half-life -> log-odds halved
    c = f.confidence(ts=7 * _DAY)
    assert f.log_odds == pytest.approx(1.0)
    assert c == pytest.approx(confidence_of(1.0))
    # far future -> reverts to ~0.5 (willing to test), never stuck
    assert f.confidence(ts=1000 * _DAY) == pytest.approx(0.5, abs=1e-3)


def test_confidence_never_reaches_the_bounds():
    """A relentless stream of one-sided evidence saturates AT the clamp, never
    past it — never certainty, never zero (both deadlock states forbidden)."""
    hi = Foundation("hi", half_life_s=1e18)
    lo = Foundation("lo", half_life_s=1e18)
    for i in range(200):
        hi.observe(i, llr=5.0, attribution=1.0, independence=1.0)
        lo.observe(i, llr=-5.0, attribution=1.0, independence=1.0)
    assert hi.log_odds == pytest.approx(L_CEIL)
    assert lo.log_odds == pytest.approx(L_FLOOR)
    assert 0.0 < lo.confidence() < hi.confidence() < 1.0


def test_llr_binary_is_unit_safe_and_contextual():
    """llr_binary maps a binary outcome to nats vs a baseline. A win the
    foundation called more likely than baseline => +llr; a loss => -llr; and
    it is finite even at p=0/1 (clamped, no certainty)."""
    assert llr_binary(0.7, 0.5, won=True) == pytest.approx(math.log(0.7 / 0.5))
    assert llr_binary(0.7, 0.5, won=False) == pytest.approx(
        math.log(0.3 / 0.5))
    # a foundation no better than baseline yields ZERO evidence either way
    assert llr_binary(0.5, 0.5, won=True) == pytest.approx(0.0)
    assert llr_binary(0.5, 0.5, won=False) == pytest.approx(0.0)
    # clamped: never infinite even at a certainty claim
    assert math.isfinite(llr_binary(1.0, 0.5, won=True))
    assert math.isfinite(llr_binary(0.0, 0.5, won=False))


def test_observe_rejects_out_of_unit_inputs():
    """Guards against putting a value into the equation without proportion:
    attribution outside [0,1], independence outside (0,1], non-finite llr."""
    f = Foundation("f")
    with pytest.raises(ValueError):
        f.observe(0.0, llr=1.0, attribution=1.5, independence=1.0)
    with pytest.raises(ValueError):
        f.observe(0.0, llr=1.0, attribution=0.5, independence=0.0)
    with pytest.raises(ValueError):
        f.observe(0.0, llr=float("inf"), attribution=0.5, independence=1.0)


def test_combine_adds_log_odds_across_foundations():
    a = Foundation("a", half_life_s=1e18)
    b = Foundation("b", half_life_s=1e18)
    a.observe(0.0, llr=1.0, attribution=1.0, independence=1.0)
    b.observe(0.0, llr=0.5, attribution=1.0, independence=1.0)
    assert combine([a, b]) == pytest.approx(confidence_of(1.5))
    assert combine([]) == pytest.approx(0.5)   # no foundation -> still testable


def test_default_half_life_is_a_week():
    assert DEFAULT_HALF_LIFE_S == pytest.approx(7 * _DAY)
