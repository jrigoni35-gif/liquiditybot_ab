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
    # CROSSED book: the market traded through our resting buy, so we fill AT
    # OUR OWN price as maker. Vehicle changed 2026-08-09 (owed 57 / era
    # boundary #4) from a non-crossing book driving the passive hazard - that
    # hazard double-counted this same crossing and no longer fires when a
    # book is present. The SUBJECT here is unchanged and is fee/slip
    # BOOKING, which _note_exec performs identically on both paths.
    om._poll_dry(o, {"bids": [[1990.0, 5.0]], "asks": [[1999.0, 5.0]]},
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
    # crossed book -> maker-cross (see the note in the maker/zero-slip test)
    om._poll_dry(o2, {"bids": [[1990.0, 5.0]], "asks": [[1999.0, 5.0]]},
                 sigma_bar_pct=0.5, now=o2.created_ts + 1.0)
    s = om.status()
    assert s["maker_fills"] == 1 and s["taker_fills"] == 1
    assert s["maker_share"] == 0.5
    # worst = max(signed): improvement -5 and 0 -> worst is 0
    assert s["worst_slip_bps"] == pytest.approx(0.0)


def test_terminal_counters_mirror_the_om000_om040_split():
    """2026-08-17 funnel telemetry: terminal_orders / timeout_cancels count
    exactly the state-machine branch that audits OM-000/OM-040 — clean
    terminals only. The forced-cancel OM-030 path is not a clean terminal
    and must not count."""
    om = _om()
    s0 = om.status()
    assert s0["terminal_orders"] == 0 and s0["timeout_cancels"] == 0
    o1 = _order()                                  # pending -> expired (OM-040)
    om._orders[o1.order_id] = o1
    assert om._transition(o1, "expired", "ttl")
    o2 = _order()
    o2.order_id = "y"                              # pending -> filled (OM-000)
    om._orders[o2.order_id] = o2
    assert om._transition(o2, "filled", "done")
    s = om.status()
    assert s["terminal_orders"] == 2
    assert s["timeout_cancels"] == 1
    # illegal transition out of a terminal: refused, no counter movement
    o3 = _order()
    o3.order_id = "z"
    o3.status = "filled"
    om._orders[o3.order_id] = o3
    assert not om._transition(o3, "pending", "illegal")
    s2 = om.status()
    assert s2["terminal_orders"] == 2 and s2["timeout_cancels"] == 1


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


def test_post_only_crossed_fills_at_own_price_as_maker():
    """A post-only limit NEVER takes: when the book crosses through the
    resting price, it fills AT ITS OWN price with MAKER fees (the aggressor
    paid taker) — not by sweeping the book at taker fees."""
    om = _om()
    o = _order(side="buy", price=2000.0, post_only=True)   # resting bid 2000
    om._orders[o.order_id] = o
    om._poll_dry(o, {"bids": [[1998.0, 5.0]], "asks": [[1999.0, 2.0]]},
                 sigma_bar_pct=0.5, now=o.created_ts + 1.0)
    assert o.status == "filled" and o.avg_price == pytest.approx(2000.0)
    assert om.maker_fills == 1 and om.taker_fills == 0
    # maker fees on our own-price notional, not taker on swept prices
    assert o.fees_usd == pytest.approx(2000.0 * 25.0 / 1e4)


def test_post_only_uncrossed_book_does_not_sweep():
    om = _om()
    o = _order(side="sell", price=2010.0, post_only=True)  # resting ask 2010
    om._sim_maker_cross(o, {"bids": [[2005.0, 5.0]], "asks": [[2006.0, 5.0]]})
    assert o.filled == 0.0 and om.maker_fills == 0


def test_non_post_only_still_sweeps_as_taker():
    om, o = _om(), _order()                       # post_only=False
    om._orders[o.order_id] = o
    om._poll_dry(o, {"bids": [[1998.0, 5.0]], "asks": [[1999.0, 2.0]]},
                 sigma_bar_pct=0.5, now=o.created_ts + 1.0)
    assert om.taker_fills == 1 and om.maker_fills == 0


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
    # ask 1989 crosses our 1990 resting buy: the market traded THROUGH us and
    # we fill at 1990 as maker (see the note in the maker/zero-slip test).
    om._poll_dry(o, {"bids": [[1980.0, 5.0]], "asks": [[1989.0, 5.0]]},
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


def test_live_fee_prefers_venue_reported_over_bps_estimate():
    """W2-9: Kraken's QueryOrders `fee` is real fee-tier-aware accounting;
    it must win over the static config-bps estimate when present."""
    om = _om()
    o = _order(post_only=False)                      # taker estimate: 40bps
    o.txid = "T1"
    om._orders[o.order_id] = o
    om._poll_live(o, now=o.created_ts + 1.0,
                  batch={"T1": {"vol_exec": "1.0", "price": "2000",
                                "status": "closed", "fee": "3.50"}})
    # bps estimate would be 1.0*2000*40/1e4 = 8.00 - the venue's real 3.50
    # (a better fee tier) must be booked instead
    assert o.fees_usd == pytest.approx(3.50)


def test_live_fee_falls_back_to_bps_when_absent():
    """No `fee` field (or a degraded venue response) -> unchanged bps
    estimate behavior (backward compatible)."""
    om = _om()
    o = _order(post_only=False)
    o.txid = "T1"
    om._orders[o.order_id] = o
    om._poll_live(o, now=o.created_ts + 1.0,
                  batch={"T1": {"vol_exec": "1.0", "price": "2000",
                                "status": "closed"}})
    assert o.fees_usd == pytest.approx(1.0 * 2000.0 * 40.0 / 1e4)


def test_live_fee_ignores_garbage_and_negative_values():
    """A non-finite/negative/garbage `fee` must not poison the booked fee -
    degrade to the bps estimate, exactly like a garbage vol_exec/price."""
    om = _om()
    for bad_fee in ("nan", "-1.0", "not-a-number", None):
        o = _order(post_only=False)
        o.txid = "T1"
        om._orders = {o.order_id: o}
        om._poll_live(o, now=o.created_ts + 1.0,
                      batch={"T1": {"vol_exec": "1.0", "price": "2000",
                                    "status": "closed", "fee": bad_fee}})
        assert o.fees_usd == pytest.approx(1.0 * 2000.0 * 40.0 / 1e4), bad_fee


def test_cancel_time_reconciliation_also_books_venue_fee():
    """The cancel-path final QueryOrders reconciliation must apply the same
    venue-fee preference as the regular poll path."""
    om = OrderManager(feed=None, config={"maker_fee_bps": 25.0,
                                         "taker_fee_bps": 40.0}, dry_run=False)
    calls = []

    def fake_private(endpoint, data=None):
        calls.append(endpoint)
        if endpoint == "QueryOrders":
            return {"T1": {"vol_exec": "0.5", "price": "101.0",
                           "status": "canceled", "fee": "0.42"}}
        return {}
    om._timed_private = fake_private
    o = _order(side="sell", price=100.0, post_only=False)
    o.txid = "T1"
    om._orders[o.order_id] = o
    assert om.cancel_order(o, reason="preempted") is True
    assert o.fees_usd == pytest.approx(0.42)


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
    slips = [s for s, _ in om._slip_bps]              # (slip, notional) pairs
    assert slips[0] == pytest.approx(0.0)             # seg 1 at the limit
    assert slips[1] == pytest.approx(10.0)            # seg 2 at its OWN price
    assert om.status()["worst_slip_bps"] == pytest.approx(10.0)
    # notional booked per segment price: 0.5*2000 + 0.5*2002
    assert om.taker_notional_usd == pytest.approx(0.5 * 2000 + 0.5 * 2002)


# --- 2026-07-29 defect-category audit: weighted slip + dust guard ------------

def test_slip_ledger_notional_weighted_companion():
    """avg_slip_bps stays the per-fill mean (legacy key, unchanged);
    slip_bps_notional_weighted answers what a unit of traded NOTIONAL
    paid (Cochran ch.6 / Bessembinder 2003): $10 probe fills must not
    outvote a 3x-notional conviction fill."""
    om = OrderManager.__new__(OrderManager)
    om.maker_fee_bps, om.taker_fee_bps = 25.0, 40.0
    om.maker_fills = om.taker_fills = 0
    om.maker_notional_usd = om.taker_notional_usd = 0.0
    om.latency_ms = 0.0
    om.venue_rejects = om.zero_format_rejects = 0
    om.cancel_unconfirmed = 0            # OM-090 counter, same shape
    om.terminal_orders = om.timeout_cancels = 0   # funnel tally, same shape
    om._deadman_failures = 0
    om._fee_recon_result = None
    om._orders = {}
    from collections import deque
    om._slip_bps = deque(maxlen=200)
    # probe fill: $10 at +1bp; conviction fill: $30 at +5bps
    om._note_exec(False, 10.0, 100.01, 100.0, "buy")
    om._note_exec(False, 30.0, 100.05, 100.0, "buy")
    s = om.status()
    assert s["avg_slip_bps"] == pytest.approx((1.0 + 5.0) / 2, abs=0.01)
    assert s["slip_bps_notional_weighted"] == pytest.approx(
        (1.0 * 10 + 5.0 * 30) / 40, abs=0.01)      # 4.0, not 3.0
    # zero-notional fill counts in the per-fill mean, never the weighted
    om._note_exec(False, float("nan"), 100.03, 100.0, "buy")
    s2 = om.status()
    assert s2["avg_slip_bps"] == pytest.approx((1 + 5 + 3) / 3, abs=0.01)
    assert s2["slip_bps_notional_weighted"] == pytest.approx(4.0, abs=0.01)


def test_dust_segment_skips_slip_ledger_not_fees():
    """A segment under 1% of the order's notional recovers its price from
    the difference of two near-equal products (Higham-class cancellation
    amplifying venue quantization) — it must not pollute the slip ledger,
    while notional accounting stays exact."""
    om = OrderManager.__new__(OrderManager)
    om.maker_fee_bps, om.taker_fee_bps = 25.0, 40.0
    om.maker_fills = om.taker_fills = 0
    om.maker_notional_usd = om.taker_notional_usd = 0.0
    from collections import deque
    om._slip_bps = deque(maxlen=200)
    # order notional $2000; dust segment $10 (0.5%) -> ledger skipped
    om._note_exec(False, 10.0, 101.0, 100.0, "buy",
                  order_notional_usd=2000.0)
    assert len(om._slip_bps) == 0
    assert om.taker_notional_usd == pytest.approx(10.0)   # booking exact
    # a 5% segment of the same order IS ledgered
    om._note_exec(False, 100.0, 101.0, 100.0, "buy",
                  order_notional_usd=2000.0)
    assert len(om._slip_bps) == 1
    # no order context (whole-fill callers) -> guard inert, always ledgered
    om._note_exec(False, 0.5, 101.0, 100.0, "buy")
    assert len(om._slip_bps) == 2
