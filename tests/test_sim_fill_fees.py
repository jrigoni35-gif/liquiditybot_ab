"""Regression: the dry-run cross simulator must add taker fees on the NEW
crossed notional and never re-touch fees on a no-op poll. The old code
overwrote fees_usd at taker rate on the CUMULATIVE fill every poll, which
clobbered maker fees from passive fills and re-charged on polls that crossed
nothing - corrupting paper PnL and the net_pnl training labels built from it.
"""
import pytest

from execution.order_manager import ManagedOrder, OrderManager


def _om():
    return OrderManager(feed=None, config={"taker_fee_bps": 40.0}, dry_run=True)


def _order():
    return ManagedOrder(order_id="x", txid=None, asset="ETH", pair="ETHUSD",
                        symbol="ETH/USD", side="buy", price=2000.0, size=1.0,
                        ordertype="limit", post_only=False)


def test_cross_charges_taker_fee_on_crossed_notional():
    om, o = _om(), _order()
    om._sim_cross(o, {"asks": [[1999.0, 0.4]]})   # 0.4 @ 1999 crosses (<2000)
    assert o.filled == pytest.approx(0.4)
    assert o.fees_usd == pytest.approx(0.4 * 1999.0 * 40.0 / 1e4)


def test_noop_poll_does_not_re_touch_fees_or_fill():
    om, o = _om(), _order()
    om._sim_cross(o, {"asks": [[1999.0, 0.4]]})
    fees_after_cross, fill_after = o.fees_usd, o.filled
    # book no longer crosses (2001 > order price 2000): nothing new fills
    om._sim_cross(o, {"asks": [[2001.0, 5.0]]})
    assert o.filled == pytest.approx(fill_after)       # unchanged
    assert o.fees_usd == pytest.approx(fees_after_cross)  # NOT re-overwritten


def test_second_cross_adds_not_replaces():
    om, o = _om(), _order()
    om._sim_cross(o, {"asks": [[1999.0, 0.4]]})
    f1 = o.fees_usd
    om._sim_cross(o, {"asks": [[1998.0, 0.6]]})   # remaining 0.6 crosses
    assert o.filled == pytest.approx(1.0)
    assert o.fees_usd == pytest.approx(f1 + 0.6 * 1998.0 * 40.0 / 1e4)
    # blended average across both crosses
    assert o.avg_price == pytest.approx((0.4 * 1999.0 + 0.6 * 1998.0) / 1.0)
