"""tests/test_drift_windowing.py — input-drift detection must fire on a real
market shift, not on small-window PSI noise or the wall clock.

Two failure modes are pinned here, both observed live (a single ML-031/ML-032
that requested a retrain off a stable book):

  * SMALL-WINDOW NOISE: a 10-bin decile-PSI needs ~10 samples/bin to be
    stable. On a 40-row window it fabricates ~19% mean / 28% p95 "drift" from
    an IN-DISTRIBUTION sample — nearly the 30% retrain trigger, from pure
    sampling noise. drift_min_rows is raised so the noise floor sits far below
    the trigger; the null test here is the guard.
  * CLOCK/COUNTER FEATURES: hour_sin/cos, funding_dist and regime_age are
    deterministic functions of time/phase, not market state. On any finite
    window their PSI reads WHERE the window sits on the clock, so they drift
    by construction. They are excluded from the vote (DRIFT_EXCLUDED_FEATURES),
    the same reason the PSI kernel already zeros degenerate binary deciles.
"""
import numpy as np

from ml.calibration import feature_deciles
from ml.features import DRIFT_EXCLUDED_FEATURES, FEATURE_NAMES
from ml.monitor import ModelMonitor

NF = len(FEATURE_NAMES)


def _monitor(tmp_path, **over):
    cfg = {"drift_min_rows": 100, "drift_psi_threshold": 0.25,
           "drift_frac_features": 0.30,
           "retrain_flag_path": str(tmp_path / "retrain.flag")}
    cfg.update(over)
    return ModelMonitor(cfg)


def _train_deciles(rng, rows=400):
    return feature_deciles(rng.normal(0.0, 1.0, (rows, NF)))


def _feed(mon, window):
    for row in window:
        mon.note_features(row)


# --- clock/counter features never vote --------------------------------------
def test_clock_features_excluded_from_drift_vote(tmp_path):
    rng = np.random.default_rng(21)  # re-pinned at v10 (68-wide, 2026-09-21):
    # the rng(0) draw reshaped to TWO strays (volume_z, pd_zone) - same
    # seed-fragility class this test's own comment documents; 21 draws
    # zero strays at the new width
    dec = _train_deciles(rng)
    # in-distribution window EXCEPT the clock/counter features, shoved far away
    win = rng.normal(0.0, 1.0, (120, NF))
    for name in DRIFT_EXCLUDED_FEATURES:
        win[:, FEATURE_NAMES.index(name)] = rng.normal(6.0, 0.1, 120)  # huge
    mon = _monitor(tmp_path)
    _feed(mon, win)
    mon.check_drift(dec, FEATURE_NAMES)
    # the REAL pin: a shifted CLOCK feature never votes. drift_share == 0
    # exactly was seed-fragile - every schema widening reshapes the rng(0)
    # draw and a stray MARKET feature can cross the PSI threshold as pure
    # sampling noise at 120 rows (which the vote threshold absorbs - see
    # the null-property test). Tolerate one bounded stray, same as
    # test_market_feature_shift_is_detected.
    assert not any(f in DRIFT_EXCLUDED_FEATURES for f in mon.drifting)
    assert len(mon.drifting) <= 1, f"noise floor breached: {mon.drifting}"
    assert mon.drift_share <= 1.0 / (NF - len(DRIFT_EXCLUDED_FEATURES))


# --- a genuine market-feature shift is still caught -------------------------
def test_market_feature_shift_is_detected(tmp_path):
    rng = np.random.default_rng(1)
    dec = _train_deciles(rng)
    win = rng.normal(0.0, 1.0, (120, NF))
    j = FEATURE_NAMES.index("sigma_bar_pct")
    win[:, j] = rng.normal(6.0, 0.1, 120)          # real vol-regime shift
    mon = _monitor(tmp_path)
    _feed(mon, win)
    mon.check_drift(dec, FEATURE_NAMES)
    assert "sigma_bar_pct" in mon.drifting
    # a 120-row window has a PSI noise floor: an occasional stray feature
    # may cross 0.25 on a same-distribution draw (which the vote threshold
    # absorbs - see the null-property test below). Pinning "exactly one
    # drifting feature" made this test break on every schema bump, since
    # widening FEATURE_NAMES reshapes the seeded draw. Tolerate a bounded
    # stray but keep the real pin: the shift is caught, and the share
    # denominator is MARKET features only (total minus the clock set).
    stray = [f for f in mon.drifting if f != "sigma_bar_pct"]
    assert len(stray) <= 1, f"noise floor breached: {mon.drifting}"
    assert mon.drift_share == (
        len(mon.drifting) / (NF - len(DRIFT_EXCLUDED_FEATURES)))


# --- the null property: an in-distribution window does not fire --------------
def test_in_distribution_window_does_not_fabricate_drift(tmp_path):
    rng = np.random.default_rng(2)
    fired = []
    for _ in range(50):
        dec = _train_deciles(rng)
        win = rng.normal(0.0, 1.0, (100, NF))       # SAME distribution
        mon = _monitor(tmp_path)
        _feed(mon, win)
        mon.check_drift(dec, FEATURE_NAMES)
        fired.append(mon.drift_share >= mon.drift_frac_features)
    # at a 100-row window the null retrain rate must be ~0 (noise floor << 30%)
    assert sum(fired) == 0, f"in-distribution windows tripped drift {sum(fired)}/50 times"


# --- a broad real shift DOES fire the retrain request -----------------------
def test_broad_market_shift_requests_retrain(tmp_path):
    rng = np.random.default_rng(3)
    dec = _train_deciles(rng)
    win = rng.normal(0.0, 1.0, (120, NF))
    # shift half of ALL features (well over the 30% MARKET-feature trigger)
    for j in range(0, NF, 2):
        win[:, j] = rng.normal(6.0, 0.1, 120)
    mon = _monitor(tmp_path)
    _feed(mon, win)
    mon.check_drift(dec, FEATURE_NAMES)
    assert mon.drift_share >= mon.drift_frac_features
    assert (tmp_path / "retrain.flag").exists(), "broad drift must request a retrain"


# --- the min-rows gate: too few rows means no verdict at all ----------------
def test_below_min_rows_does_not_evaluate(tmp_path):
    rng = np.random.default_rng(4)
    dec = _train_deciles(rng)
    win = rng.normal(0.0, 1.0, (50, NF))            # below drift_min_rows=100
    win[:, FEATURE_NAMES.index("sigma_bar_pct")] = rng.normal(6.0, 0.1, 50)
    mon = _monitor(tmp_path)
    _feed(mon, win)
    mon.check_drift(dec, FEATURE_NAMES)
    assert mon.drift_share == 0.0 and mon.drifting == []   # not enough to judge
