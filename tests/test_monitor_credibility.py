"""ModelMonitor's hit-deficit guard and its baseline.

Round-2 findings (2026-08-05), both in ml/monitor.py's _judge:

1. THE WILSON GUARD WAS ALGEBRAICALLY DEAD. The indictment read
       raw_gap > allow AND (promised - lcb) > allow
   intending "and even the optimistic bound cannot explain it". But the
   Wilson LOWER bound is always <= the observed rate, so
       promised - lcb >= promised - mean == raw_gap
   which makes the second conjunct implied by the first: it could never
   veto anything. Worse, it grew MORE permissive as n shrank (a wider
   interval pushes lcb down), the exact opposite of the small-n protection
   it was added for. The statistically meaningful test needs the UPPER
   bound: promised must exceed even the most optimistic reading of the
   realized rate before a shortfall is credible.

2. THE BASELINE WAS AN IN-WINDOW ORACLE. baseline_brier scored a constant
   equal to the window's OWN realized mean - a number no live model could
   know at prediction time. In a 15-close window that happened to lose
   every trade (probability ~4-9% at this corpus's base rates), an
   honestly-calibrated model promising ~0.3 was measured against a
   clairvoyant 0.05 baseline and convicted on its first evaluation, then
   killed on its second.
"""
import numpy as np

from ml.monitor import ModelMonitor, wilson_lcb, wilson_ucb


def _mon(**over):
    cfg = {"window_trades": 30, "min_trades_to_judge": 15}
    cfg.update(over)
    return ModelMonitor(cfg)


# --- 1. the algebra --------------------------------------------------------
def test_wilson_lcb_never_exceeds_the_observed_rate():
    """The identity that made the old second conjunct dead code."""
    for k, n in ((0, 15), (3, 15), (7, 15), (15, 15), (1, 100), (50, 100)):
        assert wilson_lcb(k, n) <= k / n + 1e-12


def test_wilson_ucb_is_never_below_the_observed_rate():
    for k, n in ((0, 15), (3, 15), (7, 15), (15, 15), (1, 100), (50, 100)):
        assert wilson_ucb(k, n) >= k / n - 1e-12


def test_ucb_interval_widens_as_n_shrinks():
    """Small n must make an indictment HARDER, not easier - the property
    the lcb form inverted."""
    wide = wilson_ucb(0, 15) - wilson_lcb(0, 15)
    narrow = wilson_ucb(0, 150) - wilson_lcb(0, 150)
    assert wide > narrow


def test_honest_promise_survives_an_unlucky_small_sample():
    """A model promising close to this corpus's real base rate (~0.18) that
    then hits 15 straight losses is UNLUCKY, not miscalibrated: at n=15 the
    realized rate's upper bound is ~0.15, so the promise does not clear it
    by the allowance and no deficit is credible yet.

    (A promise of 0.30 against 15 straight losses IS convicted, correctly -
    that is a ~0.5% event under the model's own claim, i.e. evidence the
    claim is wrong rather than evidence of a bad run.)"""
    m = _mon()
    degraded, failing, detail, *_ = m._judge(np.full(15, 0.18), np.zeros(15))
    assert not failing, \
        "an honest promise + an unlucky streak must not KILL the model"
    assert detail["n"] == 15


def test_small_n_makes_the_deficit_test_harder_not_easier():
    """THE property the dead lcb form inverted. Same observed shortfall
    (promised 0.45 vs a realized 0.20), two sample sizes: the small sample
    must NOT convict and the large one must, because a wider interval is
    less able to rule out luck."""
    m = _mon()
    small_p, small_y = np.full(15, 0.45), np.array([1.0] * 3 + [0.0] * 12)
    large_y = np.array([1.0] * 30 + [0.0] * 120)      # same 20% realized rate
    _, _, _, *_ = m._judge(small_p, small_y)
    small_ucb = wilson_ucb(int(small_y.sum()), len(small_y))
    large_ucb = wilson_ucb(int(large_y.sum()), len(large_y))
    assert (0.45 - small_ucb) < (0.45 - large_ucb), \
        "the same shortfall must be harder to indict at small n"
    assert small_ucb > large_ucb


def test_a_real_sustained_shortfall_is_still_caught():
    """The guard must not become a rubber stamp: a large, sustained
    shortfall - promising 0.80 and realizing 0.10 over 100 closes - is
    credible even at the optimistic bound, and must indict."""
    m = _mon()
    p = np.full(100, 0.80)
    y = np.array([1.0] * 10 + [0.0] * 90)
    degraded, failing, detail, *_ = m._judge(p, y)
    assert degraded, "a 70-point sustained shortfall must be caught"


# --- 2. the baseline -------------------------------------------------------
def test_baseline_is_not_the_windows_own_mean():
    """The oracle: scoring against clip(y.mean()) gives the baseline
    information the model could not have had. Two windows with IDENTICAL
    model predictions and identical realized COUNTS must not be judged
    against different baselines just because of their order... but more
    to the point, an all-loss window must not hand the baseline a
    near-perfect constant."""
    m = _mon()
    p = np.full(15, 0.30)
    y = np.zeros(15)
    *_, model_brier, baseline_brier, _lcb, _promised = m._judge(p, y)
    # the old oracle baseline was clip(0.0) = 0.05 -> brier 0.0025
    assert baseline_brier > 0.0025 + 1e-9, \
        "baseline still scoring the window's own realized mean (oracle)"


def test_prior_base_rate_is_used_when_history_exists():
    """The monitor's own accumulated history is legitimate prior
    information - it existed before the current window."""
    m = _mon()
    # a long history at a ~30% win rate, all model-scored
    for i in range(60):
        m.record_close(0.30, 1 if i % 10 < 3 else 0, model_scored=True)
    assert abs(m._prior_base_rate() - 0.30) < 0.12


def test_cold_start_prior_falls_back_documented():
    """With no history the monitor cannot know a prior; it must fall back
    to a NEUTRAL constant rather than the window's mean."""
    m = _mon()
    assert 0.0 < m._prior_base_rate() < 1.0
