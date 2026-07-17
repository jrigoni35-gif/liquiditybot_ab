"""tests/test_sizer_literal_lift.py — the §A guessing-code lift is
BEHAVIOR-PRESERVING: with default config the sizer computes byte-identical
b/b_net and vol scalars to the old hardcoded formulas, and the lifted knobs
actually steer when configured. The one deliberate change: non-finite sigma
now degrades to the scalar FLOOR (unknown vol = high vol) instead of
propagating NaN into the ticket."""
import pytest

from risk.position_sizer import PositionSizer, payoff_ratio_from_config

_PROFIT = {f"tier_{i}": {"trigger_pct_gain": t, "close_pct_of_position": 25}
           for i, t in ((1, 1.0), (2, 2.0), (3, 3.5), (4, 5.0))}
_RISK = {"stop_loss_pct": 2.0}


def _old_payoff(rt_cost_pct=0.0):
    """The pre-lift formula, verbatim (hardcoded 0.65 reach decay)."""
    reach, w, p = 1.0, 0.0, 0.0
    for t in (1.0, 2.0, 3.5, 5.0):
        w += reach * t * 0.25
        p += reach * 0.25
        reach *= 0.65
    avg_win = w / p
    win_net = max(avg_win - rt_cost_pct, 0.0)
    return max(win_net / (2.0 + rt_cost_pct), 0.05)


def test_default_payoff_ratio_identical_to_old_formula():
    assert payoff_ratio_from_config(_PROFIT, _RISK) == \
        pytest.approx(_old_payoff(), rel=1e-12)
    assert payoff_ratio_from_config(_PROFIT, _RISK, rt_cost_pct=0.65) == \
        pytest.approx(_old_payoff(0.65), rel=1e-12)


def test_default_sizer_b_identical():
    s = PositionSizer({}, profit_cfg=_PROFIT, risk_cfg=_RISK)
    assert s.tier_reach_decay == 0.65
    assert s.b == pytest.approx(_old_payoff(), rel=1e-12)
    assert s.b_net == pytest.approx(_old_payoff(s.rt_cost_pct), rel=1e-12)


def test_reach_decay_knob_steers_breakeven():
    lo = PositionSizer({"tier_reach_decay": 0.4},
                       profit_cfg=_PROFIT, risk_cfg=_RISK)
    hi = PositionSizer({"tier_reach_decay": 1.0},
                       profit_cfg=_PROFIT, risk_cfg=_RISK)
    # lower reach = later tiers weigh less = smaller avg win = smaller b
    assert lo.b < hi.b
    # hostile values clamp into [0.05, 1.0]
    assert PositionSizer({"tier_reach_decay": 0.0}, _PROFIT,
                         _RISK).tier_reach_decay == 0.05


def test_default_vol_scalar_identical_to_old_formula():
    s = PositionSizer({}, profit_cfg=_PROFIT, risk_cfg=_RISK)
    for sigma in (0.0, 3.0, 5.0, 20.0, 35.0, 60.0, 200.0):
        old = min(max(35.0 / max(sigma, 5.0), 0.3), 1.5)
        assert s._vol_scalar(sigma) == pytest.approx(old, rel=1e-12), sigma


def test_vol_knobs_steer():
    s = PositionSizer({"vol_target_ann_pct": 70.0, "vol_scalar_max": 2.0},
                      profit_cfg=_PROFIT, risk_cfg=_RISK)
    assert s._vol_scalar(35.0) == pytest.approx(2.0)     # 70/35=2, at new cap
    assert s._vol_scalar(280.0) == pytest.approx(0.3)    # floor unchanged


def test_non_finite_sigma_degrades_to_floor_not_nan():
    # deliberate hardening: old code propagated NaN into the ticket size
    s = PositionSizer({}, profit_cfg=_PROFIT, risk_cfg=_RISK)
    assert s._vol_scalar(float("nan")) == pytest.approx(s.vol_scalar_min)
    assert s._vol_scalar(float("inf")) == pytest.approx(s.vol_scalar_min)
