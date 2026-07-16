"""tests/test_conviction_runner.py — rev-6 entry-conviction runner leash.

The entry conviction (Position.confidence = meta p(win) at entry) scales the
runner's chandelier trail: a LOW-conviction winner banks sooner (tighter trail),
a HIGH-conviction one keeps the full leash to run. Contract under test:

  * TIGHTEN-ONLY — it can only bring an exit SOONER, never later (invariant 5).
  * FULL LEASH when conviction is unknown (<= 0, e.g. restored/synthetic
    Positions like the quant-trial fixtures) or high (>= neutral_conf) — so
    deployed behavior is byte-identical wherever conviction is not informative.
  * BOUNDED — hostile config is clamped into a safe envelope.
"""
from datetime import datetime, timezone

from core.state import Position
from risk.profit_tiers import ProfitTierEngine

_TIER_CFG = {
    "tier_1": {"trigger_pct_gain": 1.0, "close_pct_of_position": 25},
    "tier_2": {"trigger_pct_gain": 2.0, "close_pct_of_position": 25},
    "tier_3": {"trigger_pct_gain": 3.5, "close_pct_of_position": 25},
    "tier_4": {"trigger_pct_gain": 5.0, "close_pct_of_position": 25},
    "trailing_stop": {"enabled": True, "activate_after_tier": 1,
                      "trail_pct": 1.0},
    "be_after_tier": 99,          # keep break-even + give-back out of these tests
}
_CR = {"enabled": True, "neutral_conf": 0.70, "min_conf": 0.55,
       "min_trail_mult": 0.6}


def _pos(conf, entry=100.0, hw=110.0, tier_closed=4):
    p = Position(position_id=f"cr-{conf}", symbol="T/USD", direction="long",
                 entry_price=entry, size=1.0, original_size=2.0,
                 opened_at=datetime.now(timezone.utc), confidence=conf)
    p.tier_closed = tier_closed
    p.high_water = hw
    return p


# px sits between the full-leash stop (hw*0.99 = 108.9, no exit) and the
# low-conviction stop (0.6x trail -> hw*0.994 = 109.34, exit).
_PX = 109.2


def test_high_conviction_keeps_full_leash():
    eng = ProfitTierEngine({**_TIER_CFG, "conviction_runner": _CR})
    # confidence at/above neutral -> full leash -> no exit at _PX
    assert eng.evaluate(_pos(0.85), _PX).should_close_partial is False


def test_low_conviction_banks_sooner():
    eng = ProfitTierEngine({**_TIER_CFG, "conviction_runner": _CR})
    act = eng.evaluate(_pos(0.55), _PX)     # at min_conf -> max tighten (0.6x)
    assert act.should_close_partial is True
    assert act.close_pct == 100.0


def test_unknown_conviction_is_full_leash_noop():
    """confidence <= 0 (restored/synthetic, e.g. quant-trial Positions) must be
    byte-identical to conviction_runner disabled — this is what keeps the
    quant-trial gates untouched."""
    on = ProfitTierEngine({**_TIER_CFG, "conviction_runner": _CR})
    off = ProfitTierEngine(_TIER_CFG)
    a_on = on.evaluate(_pos(0.0), _PX)
    a_off = off.evaluate(_pos(0.0), _PX)
    assert a_on.should_close_partial is False
    assert a_off.should_close_partial is False
    assert a_on.should_close_partial == a_off.should_close_partial


def test_disabled_ignores_conviction():
    eng = ProfitTierEngine({**_TIER_CFG,
                            "conviction_runner": {**_CR, "enabled": False}})
    # even a low-conviction position gets the full leash when the block is off
    assert eng.evaluate(_pos(0.55), _PX).should_close_partial is False


def test_leash_only_ever_fires_sooner():
    """Tighten-only: any px that exits under the full leash must also exit
    under the low-conviction tightened leash."""
    full = ProfitTierEngine(_TIER_CFG)
    tight = ProfitTierEngine({**_TIER_CFG, "conviction_runner": _CR})
    for px in (108.5, 108.8, 108.9, 109.0, 109.3):
        if full.evaluate(_pos(0.0), px).should_close_partial:
            assert tight.evaluate(_pos(0.55), px).should_close_partial, \
                f"tightened leash fired LATER than full leash at {px}"


def test_conviction_is_monotone_in_leash():
    """Lower conviction => tighter stop => exits at a px a higher-conviction
    trade would still be holding."""
    eng = ProfitTierEngine({**_TIER_CFG, "conviction_runner": _CR})
    # mid conviction (0.625) stop = hw*(1-0.008)=109.12; low (0.55) = 109.34
    assert eng.evaluate(_pos(0.55), 109.2).should_close_partial is True
    assert eng.evaluate(_pos(0.625), 109.2).should_close_partial is False


def test_hostile_config_is_clamped():
    eng = ProfitTierEngine({**_TIER_CFG,
                            "conviction_runner": {"enabled": True,
                                                  "neutral_conf": 0.70,
                                                  "min_conf": 0.90,   # >= neutral
                                                  "min_trail_mult": 0.0}})
    # min_conf clamped to <= neutral, min_trail_mult floored to >= 0.1
    assert eng.cr_min_conf <= eng.cr_neutral_conf
    assert eng.cr_min_trail_mult >= 0.1


def test_rev5_call_paths_unchanged():
    """A position with no conviction block behaves exactly as rev-5."""
    eng = ProfitTierEngine(_TIER_CFG)
    act = eng.evaluate(_pos(0.0, hw=100.0, tier_closed=0), 101.5, 0.4)
    assert act.should_close_partial and act.close_pct == 25.0
