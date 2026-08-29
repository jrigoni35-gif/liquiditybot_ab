"""Pins for ml/money_sense.py — the proportional-weight shadow instrument.

The operator's two teaching examples are pinned directly.
"""
import math

import pytest

from ml.money_sense import (RUIN_WEIGHT, capitalization_efficiency,
                            log_utility_weight, proportional_return,
                            ruin_distance, weigh)


def test_the_two_teaching_examples():
    """$20 lost on $100 is -20% and near-catastrophic; $100 won on $100k is
    +0.1% and (vs a 5% move) a badly missed capitalization."""
    small_loss = weigh(-20.0, 100.0)
    assert small_loss["return_frac"] == pytest.approx(-0.20)
    assert small_loss["ruin_distance"] == pytest.approx(5.0)   # 5 kills it

    big_acct_small_win = weigh(100.0, 100_000.0, achievable_frac=0.05)
    assert big_acct_small_win["return_frac"] == pytest.approx(0.001)
    # captured 0.1% of an available 5% move => 2% efficiency = 50x under-cap
    assert big_acct_small_win["capitalization_efficiency"] == pytest.approx(0.02)
    assert big_acct_small_win["ruin_distance"] is None          # a gain


def test_same_dollars_weigh_oppositely_by_account():
    """The core lesson: $20 is not $20. Same loss, wildly different weight."""
    on_100 = log_utility_weight(proportional_return(-20.0, 100.0))
    on_100k = log_utility_weight(proportional_return(-20.0, 100_000.0))
    assert on_100 < on_100k < 0.0        # -20% far heavier than -0.02%
    assert abs(on_100) > 100 * abs(on_100k)


def test_losses_weigh_more_than_symmetric_gains():
    """Asymmetry: a -20% hurts more than a +20% helps (compounding punishes
    drawdown). log(0.8) = -0.2231 vs log(1.2) = +0.1823."""
    down = log_utility_weight(-0.20)
    up = log_utility_weight(+0.20)
    assert down == pytest.approx(math.log(0.8))
    assert up == pytest.approx(math.log(1.2))
    assert abs(down) > abs(up)


def test_ruin_is_finite_not_negative_infinity():
    """A wipeout reads as a large finite penalty, not -inf that poisons sums."""
    assert log_utility_weight(-1.0) == pytest.approx(RUIN_WEIGHT)
    assert log_utility_weight(-2.0) == pytest.approx(RUIN_WEIGHT)  # worse->clamp
    assert math.isfinite(log_utility_weight(-1.0))


def test_capitalization_none_when_nothing_achievable():
    assert capitalization_efficiency(0.0, 0.0) is None
    assert capitalization_efficiency(0.02, 0.04) == pytest.approx(0.5)


def test_proportion_requires_positive_equity_context():
    """No weight from dollars alone — proportion demands the account context."""
    with pytest.raises(ValueError):
        proportional_return(50.0, 0.0)
    with pytest.raises(ValueError):
        proportional_return(50.0, -100.0)
    with pytest.raises(ValueError):
        proportional_return(float("nan"), 100.0)


def test_ruin_distance_sign():
    assert ruin_distance(-0.20) == pytest.approx(5.0)
    assert ruin_distance(-0.02) == pytest.approx(50.0)
    assert ruin_distance(0.10) is None
