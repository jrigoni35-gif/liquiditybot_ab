"""tests/test_exec_quality_stats.py — §3 execution-quality ledger: every fill
path books a maker/taker count + notional and signed slippage vs the price we
ASKED for (positive bps = adverse, negative = price improvement). Telemetry
only; existing fee math is asserted unchanged elsewhere (test_sim_fill_fees).
"""
import pytest

from execution.order_manager import ManagedOrder, OrderManager


def _om():
    return OrderManager(feed=None, config={"maker_fee_bps": 25.0,
                                           "taker_fee_bps": 40.0},
                        dry_run=True)


def _order(side="buy", price=2000.0, ordertype="limit", post_only=False):
    return ManagedOrder(order_id="x", txid=None, asset="ETH", pair="ETHUSD",
                        symbol="ETH/USD", side=side, price=price, size=1.0,
                        ordertype=ordertype, post_only=post_only)


class _Rng:
    """Deterministic stand-in: always fill, full fraction."""
    def random(self):
        return 0.0

    def uniform(self, a, b):
        return b


def test_sim_cross_books_taker_with_improvement():
    om, o = _om(), _order()                       # buy limit 2000
    om._sim_cross(o, {"asks": [[1999.0, 0.4]]})   # filled 1bp better than asked
    assert om.taker_fills == 1 and om.maker_fills == 0
    assert om.taker_notional_usd == pytest.approx(0.4 * 1999.0)
    s = om.status()
    # (1999-2000)/2000 = -5 bps -> negative = price improvement
    assert s["avg_slip_bps"] == pytest.approx(-5.0)
    assert s["maker_share"] == 0.0


def test_sim_cross_market_books_adverse_slip():
    om = _om()
    o = _order(ordertype="market", price=2000.0)  # protection/quote reference
    om._sim_cross(o, {"asks": [[2005.0, 2.0]]})   # market walks 25bps above ref
    assert om.taker_fills == 1
    assert om.status()["avg_slip_bps"] == pytest.approx(25.0)
    assert om.status()["worst_slip_bps"] == pytest.approx(25.0)


def test_sell_side_slip_sign():
    om = _om()
    o = _order(side="sell", price=2000.0)
    om._sim_cross(o, {"bids": [[2001.0, 2.0]]})   # sold ABOVE ask price: improvement
    assert om.status()["avg_slip_bps"] == pytest.approx(-5.0)


def test_sim_passive_books_maker_zero_slip():
    om, o = _om(), _order(post_only=True)
    om._rng = _Rng()
    om._orders[o.order_id] = o
    # non-crossing book (asks above the buy limit) -> passive path fills
    om._poll_dry(o, {"bids": [[1990.0, 5.0]], "asks": [[2010.0, 5.0]]},
                 sigma_bar_pct=0.5, now=o.created_ts + 1.0)
    assert om.maker_fills == 1 and om.taker_fills == 0
    assert om.maker_notional_usd == pytest.approx(1.0 * 2000.0)
    s = om.status()
    assert s["avg_slip_bps"] == pytest.approx(0.0)
    assert s["maker_share"] == 1.0


def test_status_mixed_share_and_no_fill_none():
    om = _om()
    s0 = om.status()
    assert s0["maker_share"] is None and s0["avg_slip_bps"] is None \
        and s0["worst_slip_bps"] is None
    # one taker...
    o1 = _order()
    om._sim_cross(o1, {"asks": [[1999.0, 1.0]]})
    # ...and one maker
    o2 = _order(post_only=True)
    om._rng = _Rng()
    om._orders[o2.order_id] = o2
    om._poll_dry(o2, {"bids": [[1990.0, 5.0]], "asks": [[2010.0, 5.0]]},
                 sigma_bar_pct=0.5, now=o2.created_ts + 1.0)
    s = om.status()
    assert s["maker_fills"] == 1 and s["taker_fills"] == 1
    assert s["maker_share"] == 0.5
    # worst = max(signed): improvement -5 and 0 -> worst is 0
    assert s["worst_slip_bps"] == pytest.approx(0.0)


def test_note_exec_garbage_safe():
    om = _om()
    om._note_exec(True, float("nan"), float("inf"), 0.0, "buy")
    om._note_exec(False, None, "x", None, "sell")     # type: ignore[arg-type]
    s = om.status()                                   # never raises
    assert s["avg_slip_bps"] is None                  # no garbage slip booked
    # NaN must NOT poison the accumulator (max(nan, 0) is nan!): a poisoned
    # notional would ride into a gauge and invalidate the whole OTLP batch
    assert s["maker_notional_usd"] == 0.0
    om._note_exec(True, 100.0, 2000.0, 2000.0, "buy")
    assert om.status()["maker_notional_usd"] == 100.0   # still accumulates


def test_live_multi_segment_slippage_uses_segment_price():
    """Kraken reports the CUMULATIVE average; the ledger must book each
    segment at its OWN recovered price, not the blend (review finding F1:
    blended booking dilutes worst_slip on live book-walking fills)."""
    om = _om()
    o = _order()                                      # buy limit 2000
    o.txid = "T1"
    # segment 1: 0.5 filled at 2000 (cumulative avg 2000)
    om._poll_live(o, now=o.created_ts + 1.0,
                  batch={"T1": {"vol_exec": "0.5", "price": "2000",
                                "status": "open"}})
    # segment 2: +0.5 filled, cumulative avg 2001 -> segment price is
    # (1.0*2001 - 0.5*2000)/0.5 = 2002, i.e. +10bps adverse, NOT +5bps
    om._poll_live(o, now=o.created_ts + 2.0,
                  batch={"T1": {"vol_exec": "1.0", "price": "2001",
                                "status": "open"}})
    slips = list(om._slip_bps)
    assert slips[0] == pytest.approx(0.0)             # seg 1 at the limit
    assert slips[1] == pytest.approx(10.0)            # seg 2 at its OWN price
    assert om.status()["worst_slip_bps"] == pytest.approx(10.0)
    # notional booked per segment price: 0.5*2000 + 0.5*2002
    assert om.taker_notional_usd == pytest.approx(0.5 * 2000 + 0.5 * 2002)
