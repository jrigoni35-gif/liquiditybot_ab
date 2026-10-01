"""core/target_book.py - band math, trade-to-edge, netting, pressure overlay."""
import math

import pytest

from core.codes import Code
from core.target_book import (BookParams, Pressure, PressureLimits,
                              asset_floor_breached, band_halfwidth,
                              base_weights, plan, pressure_from,
                              tilted_targets)

P = BookParams(gamma=3.0, aim_rate=1.0, tilt_cap=0.5, invest_frac=0.9,
               min_order_usd=10.0, maker_fee_bps=15.0)


def test_band_matches_janecek_shreve_closed_form():
    lam, w, g = 0.0015, 0.225, 3.0
    want = (3 / (2 * g) * lam * w * w * (1 - w) ** 2) ** (1 / 3)
    assert band_halfwidth(lam, w, g) == pytest.approx(want)
    assert band_halfwidth(lam, w, g) == pytest.approx(0.0284, abs=5e-4)


def test_band_shape():
    assert band_halfwidth(0.0015, 0.0, 3.0) == 0.0
    assert band_halfwidth(0.0015, 1.0, 3.0) == 0.0
    assert band_halfwidth(0.0, 0.3, 3.0) == 0.0
    # wider with cost (cube root), narrower with risk aversion
    assert band_halfwidth(0.003, 0.3, 3.0) / band_halfwidth(0.0015, 0.3, 3.0) \
        == pytest.approx(2 ** (1 / 3))
    assert band_halfwidth(0.0015, 0.3, 6.0) < band_halfwidth(0.0015, 0.3, 3.0)


def test_weights_sum_to_invest_frac_and_tilts_stay_inside():
    w = base_weights(["A", "B", "C"], {"A": 0.01, "B": 0.02, "C": 0.04},
                     "inverse_vol", 0.9)
    assert sum(w.values()) == pytest.approx(0.9)
    assert w["A"] > w["B"] > w["C"]
    # a missing sigma is not guessed: equal weights
    assert base_weights(["A", "B"], {"A": 0.01}, "inverse_vol", 0.9) == \
        {"A": 0.45, "B": 0.45}
    t = tilted_targets({"A": 0.45, "B": 0.45}, {"A": 5.0, "B": -5.0}, 0.5)
    assert sum(t.values()) == pytest.approx(0.9)
    assert t["A"] == pytest.approx(0.675) and t["B"] == pytest.approx(0.225)


def _px():
    return {"A": 100.0, "B": 100.0}


def test_inside_band_holds():
    units = {"A": 4.5, "B": 4.5}               # 450/450 + 100 cash = targets
    p = plan(units, 100.0, _px(), {"A": 0.45, "B": 0.45}, P)
    assert p.orders == []
    assert p.holds == {"A": Code.TB_IN_BAND.value, "B": Code.TB_IN_BAND.value}


def test_outside_band_trades_to_edge_not_centre():
    units = {"A": 6.0, "B": 3.0}               # A 60%, B 30% of 1000
    p = plan(units, 100.0, _px(), {"A": 0.45, "B": 0.45}, P)
    sell = next(o for o in p.orders if o.asset == "A")
    assert sell.side == "sell"
    assert sell.new_w == pytest.approx(0.45 + p.bands["A"])
    assert sell.notional_usd == pytest.approx((0.60 - 0.45 - p.bands["A"]) * 1000)
    buy = next(o for o in p.orders if o.asset == "B")
    assert buy.new_w == pytest.approx(0.45 - p.bands["B"])


def test_sells_fund_buys_and_buys_clamp_to_cash():
    units = {"A": 9.0, "B": 0.0}               # all in A, no cash
    p = plan(units, 0.0, _px(), {"A": 0.45, "B": 0.45}, P)
    sold = sum(o.notional_usd for o in p.orders if o.side == "sell")
    bought = sum(o.notional_usd for o in p.orders if o.side == "buy")
    assert bought <= sold + 1e-9
    # targets that over-ask the cash (sum > 1) are scaled, never borrowed
    p2 = plan({"A": 0.0, "B": 0.0}, 100.0, _px(), {"A": 0.8, "B": 0.8}, P)
    assert p2.orders
    assert sum(o.notional_usd for o in p2.orders) == pytest.approx(100.0)
    assert all(o.code == Code.TB_CASH_CLAMP.value for o in p2.orders)


def test_long_only_never_negative_and_below_min_skipped():
    p = plan({"A": 1.0, "B": 0.0}, 0.0, _px(), {"A": 0.0, "B": 0.9}, P)
    for o in p.orders:
        if o.side == "sell":
            assert o.notional_usd <= 100.0 + 1e-9
            assert o.new_w >= 0.0
    tiny = BookParams(**{**P.__dict__, "min_order_usd": 1e6})
    p2 = plan({"A": 6.0, "B": 3.0}, 100.0, _px(), {"A": 0.45, "B": 0.45}, tiny)
    assert p2.orders == []
    assert set(p2.holds.values()) == {Code.TB_BELOW_MIN.value}


def test_unpriced_asset_is_held_not_traded():
    p = plan({"A": 6.0, "B": 3.0}, 100.0, {"A": 100.0, "B": float("nan")},
             {"A": 0.45, "B": 0.45}, P)
    assert p.holds["B"] == Code.TB_NO_PRICE.value
    assert all(o.asset != "B" for o in p.orders)


def test_pressure_is_neutral_without_stress_and_only_de_risks():
    lim = PressureLimits()
    n = pressure_from(None, None, None, None, lim)
    assert (n.band_mult, n.aim_mult, n.halt_buys) == (1.0, 1.0, False)
    s = pressure_from(0.05, -60.0, 5.0, 0.1, lim)
    assert s.band_mult > 1.0 and s.aim_mult < 1.0 and not s.halt_buys
    assert s.band_mult <= lim.max_band_mult and s.aim_mult >= lim.min_aim_mult
    worse = pressure_from(0.01, -90.0, 8.0, 0.1, lim)
    assert worse.band_mult >= s.band_mult and worse.aim_mult <= s.aim_mult
    assert pressure_from(None, None, None, 0.3, lim).halt_buys


def test_halt_blocks_buys_never_sells():
    halt = Pressure(halt_buys=True)
    p = plan({"A": 9.0, "B": 0.0}, 0.0, _px(), {"A": 0.45, "B": 0.45}, P, halt)
    assert [o.side for o in p.orders] == ["sell"]
    assert p.holds["B"] == Code.TB_PRESSURE_HALT.value
    assert p.pressure == Code.TB_PRESSURE_HALT.value


def test_pressure_widens_bands():
    wide = Pressure(band_mult=2.0)
    p1 = plan({"A": 4.5, "B": 4.5}, 100.0, _px(), {"A": 0.45, "B": 0.45}, P)
    p2 = plan({"A": 4.5, "B": 4.5}, 100.0, _px(), {"A": 0.45, "B": 0.45}, P, wide)
    assert p2.bands["A"] == pytest.approx(2 * p1.bands["A"])
    assert p2.pressure == Code.TB_PRESSURE_WIDEN.value


def test_asset_floor():
    assert asset_floor_breached([100, 120, 40], 0.6)
    assert not asset_floor_breached([100, 120, 60], 0.6)
    assert not asset_floor_breached([], 0.6)
    assert math.isfinite(band_halfwidth(0.0015, 0.5, 3.0))
