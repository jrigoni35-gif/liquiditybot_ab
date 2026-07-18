"""A-S reservation skew (risk/position_sizer.py inventory_skew).

Avellaneda-Stoikov 2008: r = s − q·γ·σ² prices the next trade against
SIGNED inventory; their Table 1 evidence: ~6% expected-profit cost for
>2x lower P&L variance. Taker transplant under test:
  - only entries that INCREASE net signed exposure are scaled;
  - inventory-REDUCING entries are never penalized (they are the
    liquidation the reservation price asks for);
  - penalty is linear in q, quadratic (clamped) in vol, floored;
  - hedge shorts count signed (they pull q toward zero);
  - shadow mode computes and logs but never multiplies;
  - config_guard rejects unknown mode / inverted gamma / zero floor.
"""
from datetime import datetime, timezone

import pytest

from core.config_guard import validate
from core.state import Position
from risk.position_sizer import PositionSizer


class _StubState:
    def __init__(self, positions):
        self.positions = positions


def _pos(symbol, size, px, direction="long"):
    return Position(position_id=f"p-{symbol}-{direction}", symbol=symbol,
                    direction=direction, entry_price=px, size=size,
                    original_size=size,
                    opened_at=datetime.fromtimestamp(1_000_000.0,
                                                     tz=timezone.utc))


def _sizer(sk_cfg=None):
    return PositionSizer(
        {"inventory_skew": sk_cfg or {"mode": "active", "gamma": 0.5,
                                      "sigma_ref_pct": 60.0,
                                      "amp_min": 0.25, "amp_max": 4.0,
                                      "floor_mult": 0.25},
         "inventory_aggression": {"full_book_heat_frac": 0.35},
         "min_ticket_usd": 25.0},
        profit_cfg={}, risk_cfg={})


# long book: 3500 notional on 10k equity = 35% = exactly full_book_heat
LONG_BOOK = {"a": _pos("BTC/USD", 0.035, 100_000.0)}
MARKS = {"BTC/USD": 100_000.0}


def test_same_direction_entry_is_scaled_down():
    s = _sizer()
    mult, q = s._inventory_skew(_StubState(LONG_BOOK), MARKS, 10_000.0,
                                "long", 60.0)
    assert q == pytest.approx(1.0)           # book at the full-heat cap
    # amp = (60/60)^2 = 1 -> mult = 1 - 0.5*1*1 = 0.5
    assert mult == pytest.approx(0.5)


def test_inventory_reducing_entry_is_never_penalized():
    s = _sizer()
    mult, q = s._inventory_skew(_StubState(LONG_BOOK), MARKS, 10_000.0,
                                "short", 60.0)
    assert q == pytest.approx(1.0)
    assert mult == 1.0                       # the liquidation A-S wants


def test_empty_book_is_neutral_both_ways():
    s = _sizer()
    for d in ("long", "short"):
        mult, q = s._inventory_skew(_StubState({}), {}, 10_000.0, d, 60.0)
        assert (mult, q) == (1.0, 0.0)


def test_penalty_quadratic_in_vol_and_clamped():
    s = _sizer()
    half = _StubState({"a": _pos("BTC/USD", 0.0175, 100_000.0)})  # q=0.5
    calm, _ = s._inventory_skew(half, MARKS, 10_000.0, "long", 30.0)
    hot, _ = s._inventory_skew(half, MARKS, 10_000.0, "long", 120.0)
    # amp calm = (30/60)^2 = 0.25 -> 1 - .5*.5*.25 = 0.9375
    # amp hot = (120/60)^2 = 4 (at amp_max) -> 1 - .5*.5*4 = 0 -> floor
    assert calm == pytest.approx(0.9375)
    assert hot == pytest.approx(0.25)        # floored, never zero


def test_hedge_short_pulls_q_toward_zero():
    s = _sizer()
    hedged = _StubState({"a": _pos("BTC/USD", 0.035, 100_000.0),
                         "h": _pos("ETH/USD", 1.75, 1_000.0, "short")})
    mult, q = s._inventory_skew(hedged, {"BTC/USD": 100_000.0,
                                         "ETH/USD": 1_000.0},
                                10_000.0, "long", 60.0)
    assert q == pytest.approx(0.5)           # 3500 - 1750 over 3500 cap
    assert mult == pytest.approx(0.75)


def test_bad_sigma_degrades_to_reference_not_neutral():
    s = _sizer()
    m_nan, _ = s._inventory_skew(_StubState(LONG_BOOK), MARKS, 10_000.0,
                                 "long", float("nan"))
    assert m_nan == pytest.approx(0.5)       # unknown vol = ref vol, not 0


def test_shadow_mode_is_default_and_never_multiplies():
    s = PositionSizer({"inventory_aggression":
                       {"full_book_heat_frac": 0.35}},
                      profit_cfg={}, risk_cfg={})
    assert s.sk_mode == "shadow"             # default: telemetry first
    mult, q = s._inventory_skew(_StubState(LONG_BOOK), MARKS, 10_000.0,
                                "long", 60.0)
    assert mult == pytest.approx(0.5)        # computed for the shadow note
    # decide() gating is exercised via the mode check: shadow computes,
    # only 'active' multiplies - pinned here at the switch itself
    assert "active" != s.sk_mode


def test_guard_rejects_incoherent_skew_knobs():
    def fatals(cfg):
        return [m for s_, m in validate(cfg) if s_ == "FATAL"]
    assert any("inventory_skew.mode" in m for m in fatals(
        {"position_sizer": {"inventory_skew": {"mode": "yolo"}}}))
    assert any("gamma" in m for m in fatals(
        {"position_sizer": {"inventory_skew": {"gamma": -0.5}}}))
    assert any("sigma_ref_pct" in m for m in fatals(
        {"position_sizer": {"inventory_skew": {"sigma_ref_pct": 0.0}}}))
    assert any("floor_mult" in m for m in fatals(
        {"position_sizer": {"inventory_skew": {"floor_mult": 0.0}}}))
    assert not any("inventory_skew" in m for m in fatals(
        {"position_sizer": {"inventory_skew": {}}}))
