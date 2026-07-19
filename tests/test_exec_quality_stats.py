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


def test_query_orders_chunks_all_txids_over_50():
    """Live poll must QueryOrders in chunks of 50 and merge, so the 51st+
    resting order is actually polled (was truncated to the first 50)."""
    om = OrderManager(feed=None, config={}, dry_run=False)
    calls = []

    def fake_query(ep, data):
        ids = data["txid"].split(",")
        calls.append(ids)
        return {t: {"vol_exec": "0", "price": "0", "status": "open"}
                for t in ids}
    om._timed_private = fake_query
    om.refresh_deadman = lambda now: None
    for i in range(51):
        o = ManagedOrder(order_id=f"o{i}", txid=f"T{i}", asset="ETH",
                         pair="ETHUSD", symbol="ETH/USD", side="buy",
                         price=2000.0, size=1.0)
        om._orders[o.order_id] = o
    om.poll(books={}, sigma_by_asset={}, now=1000.0)
    assert len(calls) == 2                       # 50 + 1, not one truncated call
    flat = [t for chunk in calls for t in chunk]
    assert set(flat) == {f"T{i}" for i in range(51)} and len(flat) == 51


def test_arrival_ref_makes_crossing_buy_show_true_cost():
    """The correction: with an arrival mark recorded, a marketable buy that
    fills BELOW its (aggressive) limit no longer looks like 'improvement' — it
    books the real implementation shortfall vs the arrival mid."""
    om, o = _om(), _order()                       # buy limit 2000
    o.arrival_ref = 1998.0                         # mark when we decided
    om._sim_cross(o, {"asks": [[1999.0, 1.0]]})   # crossed up to 1999
    # (1999-1998)/1998 = +5.0 bps ADVERSE (paid above arrival), not -5 vs limit
    assert om.status()["avg_slip_bps"] == pytest.approx(5.0, abs=0.02)


def test_arrival_ref_passive_maker_shows_capture_not_zero():
    """A passive buy resting below the arrival mid is price improvement, not a
    tautological zero — the ledger must show the favourable capture."""
    om = _om()
    o = _order(price=1990.0, post_only=True)       # rest 1990, mark 2000
    o.arrival_ref = 2000.0
    om._rng = _Rng()
    om._orders[o.order_id] = o
    om._poll_dry(o, {"bids": [[1990.0, 5.0]], "asks": [[2010.0, 5.0]]},
                 sigma_bar_pct=0.5, now=o.created_ts + 1.0)
    # (1990-2000)/2000 = -50 bps -> favourable maker capture vs mid
    assert om.status()["avg_slip_bps"] == pytest.approx(-50.0, abs=0.02)
    assert om.maker_fills == 1


def test_submit_records_arrival_ref_from_ref_price():
    """submit() stamps the arrival mark onto the order so the ledger books IS
    against it (not the collarable limit)."""
    om = _om()
    o = om.submit(asset="ETH", symbol="ETH/USD", pair="ETHUSD", side="buy",
                  price=2000.0, size=1.0, purpose="entry", ref_price=1998.0,
                  book={"bids": [[1997.0, 5.0]], "asks": [[2001.0, 5.0]]})
    assert o is not None and o.arrival_ref == pytest.approx(1998.0)


def test_missing_arrival_ref_falls_back_to_limit():
    """Backward-compatible: an order with no arrival mark (arrival_ref 0) books
    vs its own limit exactly as before — no regression for direct construction
    or legacy persisted orders."""
    om, o = _om(), _order()                       # arrival_ref defaults 0.0
    assert o.arrival_ref == 0.0
    om._sim_cross(o, {"asks": [[1999.0, 1.0]]})
    assert om.status()["avg_slip_bps"] == pytest.approx(-5.0)   # vs limit 2000


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
