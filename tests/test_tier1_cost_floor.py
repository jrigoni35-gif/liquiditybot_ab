"""tests/test_tier1_cost_floor.py — Task 1 (P1, 2026-07-23 P&L diagnosis):
tier-1's effective trigger must clear the entry's own estimated round-trip
cost (Position.est_cost_bps, threaded from execution/pretrade.py's
PreTradeDecision.est_cost_bps) by a guarded multiple
(profit_taking.min_trigger_cost_mult, shipped 3.0).

Measured baseline: avg win $0.05 vs avg loss $0.19 across 209 live closes;
tier-1 profit takes banked less than one round-trip cost unit (measured cost
overrun ~20.5bps). The floor RAISES a too-cheap trigger to
min_trigger_cost_mult x est_cost_bps (converted bps -> pct); it never lowers
one that already clears the floor, and it applies to tier-1 (index 0) only.
"""
from datetime import datetime, timezone

import pytest

from core.persistence import position_from_dict, position_to_dict
from core.state import Position
from risk.profit_tiers import ProfitTierEngine


def _pos(direction="long", entry=100.0, est_cost_bps=0.0):
    return Position(position_id="p1", symbol="ETH/USD", direction=direction,
                    entry_price=entry, size=1.0, original_size=1.0,
                    opened_at=datetime.now(timezone.utc),
                    est_cost_bps=est_cost_bps)


def _cfg(trigger_pct_gain, mult=3.0, tier_2_trigger=None):
    tiers = {"tier_1": {"trigger_pct_gain": trigger_pct_gain,
                       "close_pct_of_position": 25}}
    if tier_2_trigger is not None:
        tiers["tier_2"] = {"trigger_pct_gain": tier_2_trigger,
                           "close_pct_of_position": 25}
    return {**tiers, "vol_scaled": False, "min_trigger_cost_mult": mult}


# -- floor binds when the configured trigger is cheaper than the cost floor --
def test_tier1_floor_binds_when_costs_are_high():
    # legacy trigger 0.05%, cost 20bps x 3.0 mult -> floor 0.60%
    cfg = _cfg(trigger_pct_gain=0.05, mult=3.0)
    eng = ProfitTierEngine(cfg)
    p = _pos(est_cost_bps=20.0)
    below_floor = eng.evaluate(p, 100.55)         # +0.55% < 0.60% floor
    assert not below_floor.should_close_partial
    p2 = _pos(est_cost_bps=20.0)
    above_floor = eng.evaluate(p2, 100.65)        # +0.65% > 0.60% floor
    assert above_floor.should_close_partial and above_floor.is_profit_take
    assert above_floor.tier_fired == 1


# -- floor is inert when the configured trigger already clears it -----------
def test_tier1_floor_inert_when_trigger_already_clears_it():
    # legacy trigger 2.0%, cost 20bps x 3.0 mult -> floor 0.60% (below trigger)
    cfg = _cfg(trigger_pct_gain=2.0, mult=3.0)
    eng = ProfitTierEngine(cfg)
    p = _pos(est_cost_bps=20.0)
    above_floor_below_trigger = eng.evaluate(p, 100.70)   # +0.70%: clears the
    assert not above_floor_below_trigger.should_close_partial  # floor, not the
    p2 = _pos(est_cost_bps=20.0)                                # real 2% trigger
    at_trigger = eng.evaluate(p2, 102.0)
    assert at_trigger.should_close_partial and at_trigger.is_profit_take


# -- short-side symmetry: the floor raises the trigger by the same magnitude -
def test_tier1_floor_short_side_symmetry():
    cfg = _cfg(trigger_pct_gain=0.05, mult=3.0)
    long_eng = ProfitTierEngine(cfg)
    short_eng = ProfitTierEngine(cfg)
    long_pos = _pos(direction="long", entry=100.0, est_cost_bps=20.0)
    short_pos = _pos(direction="short", entry=100.0, est_cost_bps=20.0)
    long_below = long_eng.evaluate(long_pos, 100.55)
    short_below = short_eng.evaluate(short_pos, 99.45)
    assert not long_below.should_close_partial
    assert not short_below.should_close_partial
    long_at = long_eng.evaluate(_pos("long", 100.0, 20.0), 100.65)
    short_at = short_eng.evaluate(_pos("short", 100.0, 20.0), 99.35)
    assert long_at.should_close_partial and long_at.tier_fired == 1
    assert short_at.should_close_partial and short_at.tier_fired == 1


# -- floor scoped to tier 1 only: a fired tier-1 lets tier-2 evaluate on its
# -- own (un-floored) configured trigger, even if that trigger sits below
# -- the same cost floor that just bound tier 1 -----------------------------
def test_cost_floor_does_not_apply_to_tier_two():
    cfg = _cfg(trigger_pct_gain=0.05, mult=3.0, tier_2_trigger=0.10)
    eng = ProfitTierEngine(cfg)
    p = _pos(est_cost_bps=20.0)
    p.tier_closed = 1                      # tier 1 already fired
    # +0.30% clears tier_2's OWN 0.10% trigger but sits well below the 0.60%
    # cost floor tier 1 used - proving the floor does not leak to tier 2.
    fires_below_cost_floor = eng.evaluate(p, 100.30)
    assert fires_below_cost_floor.should_close_partial
    assert fires_below_cost_floor.tier_fired == 2


# -- default est_cost_bps=0.0 (legacy/restored positions) is exactly inert --
def test_zero_est_cost_bps_is_inert_no_floor_applied():
    cfg = _cfg(trigger_pct_gain=0.05, mult=3.0)
    eng = ProfitTierEngine(cfg)
    p = _pos(est_cost_bps=0.0)
    a = eng.evaluate(p, 100.06)            # clears the bare 0.05% trigger
    assert a.should_close_partial and a.tier_fired == 1


# -- config guard bounds enforced in the engine's own clamp (defense in depth,
# -- mirrors every other cfg.get(...) parse in this module) -----------------
def test_min_trigger_cost_mult_clamped_to_guard_bounds():
    eng_low = ProfitTierEngine({"min_trigger_cost_mult": 0.1})
    eng_high = ProfitTierEngine({"min_trigger_cost_mult": 99.0})
    assert eng_low.min_trigger_cost_mult == pytest.approx(1.0)
    assert eng_high.min_trigger_cost_mult == pytest.approx(10.0)


def test_min_trigger_cost_mult_defaults_to_3():
    eng = ProfitTierEngine({})
    assert eng.min_trigger_cost_mult == pytest.approx(3.0)


# ---------------------------------------------------------------- persistence
def test_est_cost_bps_persists_round_trip():
    pos = _pos(est_cost_bps=37.5)
    d = position_to_dict(pos)
    back = position_from_dict(d)
    assert back.est_cost_bps == pytest.approx(37.5)


def test_est_cost_bps_defaults_to_zero_for_legacy_snapshot():
    pos = _pos(est_cost_bps=37.5)
    d = position_to_dict(pos)
    d.pop("est_cost_bps")                  # pre-P1 snapshot format
    legacy = position_from_dict(d)
    assert legacy.est_cost_bps == 0.0
