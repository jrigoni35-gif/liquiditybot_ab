"""Leverage-governor floor ordering (audit fix, 0da246c): the min_leverage
dust floor is an entry-practicality bound on the vol/regime/region ladder —
it must run BEFORE margin-health scaling, so a margin-stressed book is NEVER
re-inflated back up to the floor exactly when the governor is de-risking it.
"""
import pytest

from risk.leverage import LeverageGovernor


def _gov(**over):
    cfg = {"region_max_leverage": 10.0, "target_vol_annual_pct": 35.0,
           "min_leverage": 0.25, "margin_scale_below_pct": 200.0,
           "margin_block_below_pct": 150.0, "use_margin": True}
    cfg.update(over)
    return LeverageGovernor(cfg)


def test_margin_stress_is_never_re_inflated_to_the_floor():
    # vol-target 35/17.5 = 2.0x; margin 155% -> frac (155-150)/50 = 0.10
    # -> 0.20x. The old order bounced this back UP to the 0.25x floor.
    lev, reasons = _gov().allowed_leverage(
        sigma_annual_pct=17.5, regime_cap=3.0, margin_level_pct=155.0)
    assert lev == pytest.approx(0.20)
    assert lev < 0.25, "margin de-risking must win over the dust floor"


def test_margin_block_still_zeroes():
    lev, _ = _gov().allowed_leverage(
        sigma_annual_pct=17.5, regime_cap=3.0, margin_level_pct=140.0)
    assert lev == 0.0


def test_unstressed_dust_ladder_is_still_floored():
    # extreme vol: 35/175 = 0.2x from the ladder alone -> floored to 0.25x,
    # then margin healthy (>=200%) leaves it alone
    lev, reasons = _gov().allowed_leverage(
        sigma_annual_pct=175.0, regime_cap=3.0, margin_level_pct=300.0)
    assert lev == pytest.approx(0.25)
    assert any("min-leverage floor" in r for r in reasons)


def test_no_margin_mode_unchanged():
    lev, _ = _gov(use_margin=False).allowed_leverage(
        sigma_annual_pct=17.5, regime_cap=3.0, margin_level_pct=0.0)
    assert lev == 1.0                       # capped at 1x, floor irrelevant
