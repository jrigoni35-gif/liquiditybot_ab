"""Hardened fill-model calibration estimator (core/fill_calibration.py).

The estimator recommends the dry-run passive-fill base probability
(order_manager sim_fill.passive_base_prob) from OBSERVED market
trade-through, by INVERTING the forward per-order fill model
    per-poll  p = sf_base * exp(-d_bar)
    per-order F = 1 - (1 - p)^n_bar
It must, by contract:
  * refuse (DEFERRED) on an underpowered sample — never recommend from noise;
  * quantify uncertainty (Wilson band) and say NO_CHANGE when the current
    value already sits inside that band;
  * be numerically bomb-proof — no NaN/inf/div-by-zero escapes, output in [0,1];
  * recover a known sf_base from data the forward model generated (round-trip);
  * flag MODEL-MISSPECIFICATION when per-distance buckets disagree.

These tests pin that contract before the implementation exists.
"""
import math

from core.fill_calibration import (
    CalibrationResult,
    buckets_agree,
    calibrate,
    invert_base_prob,
    wilson_interval,
)


# --------------------------------------------------------------- Wilson band
def test_wilson_interval_stays_off_the_boundaries():
    # zero successes must NOT claim certainty of never-filling: center > 0
    c, lo, hi = wilson_interval(0, 40)
    assert 0.0 < c < 0.2
    assert lo >= 0.0 and lo < c < hi and hi <= 1.0
    # all successes must NOT claim certainty of always-filling: center < 1
    c2, lo2, hi2 = wilson_interval(40, 40)
    assert 0.8 < c2 < 1.0
    assert lo2 < c2 < hi2 and hi2 <= 1.0


def test_wilson_interval_known_value():
    # k=50, n=100: symmetric, center exactly 0.5, half-width ~0.096
    c, lo, hi = wilson_interval(50, 100)
    assert abs(c - 0.5) < 1e-9
    assert abs((hi - lo) / 2 - 0.096) < 0.01


# ------------------------------------------------------------ forward inverse
def test_invert_base_prob_is_monotone_and_clamped():
    g_lo = invert_base_prob(0.10, 1.0, 5.0)
    g_hi = invert_base_prob(0.50, 1.0, 5.0)
    assert 0.0 <= g_lo < g_hi <= 1.0
    assert invert_base_prob(0.0, 1.0, 5.0) == 0.0          # no fills -> zero base
    assert invert_base_prob(0.5, 50.0, 5.0) == 1.0         # huge d_bar -> clamps to 1


def test_forward_inverse_round_trip_recovers_sf_base():
    # Build the exact per-order fill rate F a known sf_base produces, then
    # confirm the inverter recovers sf_base from F (the estimator's core claim).
    for sf_true, d_bar, n_bar in ((0.45, 1.0, 5.0), (0.30, 0.5, 5.0),
                                  (0.70, 2.0, 3.0)):
        p_poll = sf_true * math.exp(-d_bar)
        F = 1.0 - (1.0 - p_poll) ** n_bar
        assert abs(invert_base_prob(F, d_bar, n_bar) - sf_true) < 1e-9


# ------------------------------------------------------------- the power gate
def test_calibrate_defers_on_small_sample():
    r = calibrate(k=5, n=20, d_bar=1.0, n_bar=5.0, sf_base_current=0.45)
    assert isinstance(r, CalibrationResult)
    assert r.status == "DEFERRED" and r.sf_base_star is None


def test_calibrate_defers_when_either_tail_is_thin():
    # n large but only 3 successes -> success tail below E_min
    assert calibrate(k=3, n=200, d_bar=1.0, n_bar=5.0,
                     sf_base_current=0.45).status == "DEFERRED"
    # n large but only 3 failures -> failure tail below E_min
    assert calibrate(k=197, n=200, d_bar=1.0, n_bar=5.0,
                     sf_base_current=0.45).status == "DEFERRED"


def test_calibrate_defers_when_not_near_touch():
    # d_bar beyond D_MAX: inversion amplification too large, not identifiable
    r = calibrate(k=90, n=200, d_bar=3.5, n_bar=5.0, sf_base_current=0.45)
    assert r.status == "DEFERRED"


# ------------------------------------------------- recommendation vs no-change
def test_calibrate_says_no_change_when_current_in_band():
    sf_true, d_bar, n_bar = 0.45, 1.0, 5.0
    p_poll = sf_true * math.exp(-d_bar)
    F = 1.0 - (1.0 - p_poll) ** n_bar
    n = 120
    k = round(F * n)
    r = calibrate(k=k, n=n, d_bar=d_bar, n_bar=n_bar, sf_base_current=0.45)
    assert r.status == "NO_CHANGE"
    assert r.band is not None and r.band[0] <= 0.45 <= r.band[1]


def test_calibrate_recommends_lower_when_current_too_optimistic():
    # sample says fills are far RARER than the current 0.90 base implies
    sf_true, d_bar, n_bar = 0.30, 1.0, 5.0
    p_poll = sf_true * math.exp(-d_bar)
    F = 1.0 - (1.0 - p_poll) ** n_bar
    n = 200
    k = round(F * n)
    r = calibrate(k=k, n=n, d_bar=d_bar, n_bar=n_bar, sf_base_current=0.90)
    assert r.status == "OK"
    assert r.sf_base_star is not None and r.sf_base_star < 0.90
    assert abs(r.sf_base_star - sf_true) < 0.08            # recovers ~true


# ---------------------------------------------------------- degenerate inputs
def test_calibrate_guards_degenerate_inputs():
    # n_bar < 1 clamps to 1 attempt, never crashes
    assert calibrate(k=15, n=100, d_bar=1.0, n_bar=0.0,
                     sf_base_current=0.45).status in ("OK", "NO_CHANGE")
    # empty sample -> DEFERRED, not a division by zero
    assert calibrate(k=0, n=0, d_bar=1.0, n_bar=5.0,
                     sf_base_current=0.45).status == "DEFERRED"
    # non-finite input -> fail closed to DEFERRED, never NaN out
    assert calibrate(k=15, n=100, d_bar=float("nan"), n_bar=5.0,
                     sf_base_current=0.45).status == "DEFERRED"
    assert calibrate(k=15, n=100, d_bar=1.0, n_bar=float("inf"),
                     sf_base_current=0.45).status == "DEFERRED"


# ------------------------------------------------------- model-adequacy check
def _res(lo, hi):
    return CalibrationResult(status="OK", sf_base_star=(lo + hi) / 2,
                             band=(lo, hi), n=200, k=100, f_hat=0.5,
                             d_bar=1.0, n_bar=5.0, reason="")


def test_buckets_agree_detects_band_overlap():
    assert buckets_agree([_res(0.30, 0.45), _res(0.40, 0.55)]) is True   # overlap
    assert buckets_agree([_res(0.20, 0.30), _res(0.50, 0.60)]) is False  # disjoint
    assert buckets_agree([_res(0.30, 0.45)]) is True                     # single
    assert buckets_agree([]) is True                                     # vacuous
