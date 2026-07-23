"""tests/test_profit_tier_guards.py — Bug 1: NaN entry_price must not poison
the exit floor (risk/profit_tiers.py).

A corrupt/restored Position with entry_price=nan used to poison
_update_high_water via max()/min() (NaN wins both), permanently killing the
trailing floor on the very first evaluate(), and the chandelier anchor
computed off that NaN high_water raised ValueError out of evaluate() once
stop_magnet was enabled (round(nan) in _magnet_grid: "cannot convert float
NaN to integer"). Exits must never be blocked (invariant 5) — a garbage
entry price must degrade safely (fall back to the current price), never
detonate the exit path.
"""
import math
from datetime import datetime, timezone

from core.state import Position
from risk.profit_tiers import ProfitTierEngine


def _nan_entry_pos(direction="long"):
    return Position(position_id="p1", symbol="ETH/USD", direction=direction,
                    entry_price=float("nan"), size=1.0, original_size=1.0,
                    opened_at=datetime.now(timezone.utc), high_water=None)


def _trail_cfg(**extra):
    return {"trailing_stop": {"enabled": True, "activate_after_tier": 0,
                              "trail_pct": 1.0},
            "be_after_tier": 99, **extra}


def test_nan_entry_price_does_not_poison_high_water():
    eng = ProfitTierEngine(_trail_cfg())
    p = _nan_entry_pos()
    eng.evaluate(p, 100.0)
    assert math.isfinite(p.high_water), \
        "high_water must stay finite even with a NaN entry_price"
    eng.evaluate(p, 101.0)
    assert math.isfinite(p.high_water)
    assert p.trailing_stop_price is None or math.isfinite(p.trailing_stop_price)


def test_nan_entry_price_short_side_high_water_finite():
    eng = ProfitTierEngine(_trail_cfg())
    p = _nan_entry_pos(direction="short")
    eng.evaluate(p, 100.0)
    assert math.isfinite(p.high_water)


def test_nan_entry_price_with_stop_magnet_does_not_raise():
    eng = ProfitTierEngine(_trail_cfg(stop_magnet={"band_bps": 25.0}))
    p = _nan_entry_pos()
    eng.evaluate(p, 100.0)
    eng.evaluate(p, 101.0)   # would raise ValueError: cannot convert NaN to int
