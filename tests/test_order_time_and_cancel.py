"""Fleet-verified execution fixes (2026-07-20):

1. DETERMINISTIC TIME: ManagedOrder.created_ts stamped from wall clock while
   poll() compares against the injected cycle `now` broke replay in both
   directions — historical replays never expired an order (negative age:
   no escalation, dedup blocked exits forever), and time-travel drivers
   expired every order instantly. submit(now=...) now stamps engine time.

2. CANCEL-TIME FILL RECONCILIATION (live path): cancel_order transitioned
   terminal without a last QueryOrders, silently dropping any fill that
   landed after the previous poll — the preempting risk-off exit then sized
   off a stale pos.size and oversold. The final query books the remainder
   as a deferred FillEvent delivered by the next poll(), keeping every fill
   on the engine's single _handle_fill path; a fully-filled-before-cancel
   order finalizes as FILLED, not cancelled.
"""
from execution.order_manager import EPS, ManagedOrder, OrderManager


def _om(dry=True):
    return OrderManager(feed=None, config={"order_timeout_sec": 25.0},
                        dry_run=dry)


def _exit_order(filled=0.0):
    return ManagedOrder(order_id="o1", txid="TX1", asset="ETH",
                        pair="XETHZUSD", symbol="ETH/USD", side="sell",
                        price=100.0, size=1.0, filled=filled,
                        avg_price=100.0 if filled else 0.0,
                        status="partial" if filled else "pending",
                        purpose="exit", position_id="p1", post_only=False)


# --- 1. injected time -------------------------------------------------------
def test_submit_stamps_injected_engine_time():
    om = _om(dry=True)
    o = om.submit(asset="ETH", symbol="ETH/USD", pair="XETHZUSD",
                  side="sell", price=100.0, size=1.0, purpose="exit",
                  position_id="p1", post_only=False, now=1_000_000.0)
    assert o is not None and o.created_ts == 1_000_000.0
    # replay-direction contract: 26 engine-seconds later the order expires
    # (with a wall-clock stamp this age would be hugely negative and the
    # timeout would NEVER fire)
    om.poll({}, {}, now=1_000_026.0)
    assert o.status in ("expired", "cancelled")


def test_submit_without_now_still_uses_wall_clock():
    import time
    om = _om(dry=True)
    o = om.submit(asset="ETH", symbol="ETH/USD", pair="XETHZUSD",
                  side="sell", price=100.0, size=1.0, purpose="exit",
                  position_id="p1", post_only=False)
    assert abs(o.created_ts - time.time()) < 5.0


# --- 2. cancel-time reconciliation ------------------------------------------
def _live_om_with_venue(query_response):
    om = _om(dry=False)
    calls = []

    def fake_private(endpoint, data=None):
        calls.append(endpoint)
        if endpoint == "QueryOrders":
            return query_response
        return {}

    om._timed_private = fake_private
    return om, calls


def test_cancel_books_the_late_fill_before_terminal():
    o = _exit_order(filled=0.3)
    # venue: 0.2 more filled since the last poll (cumulative 0.5 @ avg 101)
    om, calls = _live_om_with_venue(
        {"TX1": {"vol_exec": "0.5", "price": "101.0", "status": "canceled"}})
    om._orders[o.order_id] = o
    assert om.cancel_order(o, reason="preempted") is True
    assert calls == ["CancelOrder", "QueryOrders"], "final reconciliation ran"
    assert o.status == "cancelled" and abs(o.filled - 0.5) < 1e-12
    # the late fill is delivered by the NEXT poll, through the normal path
    events = om.poll({}, {}, now=0.0)
    assert len(events) == 1 and abs(events[0].fill_size - 0.2) < 1e-12
    assert om._deferred_events == [], "queue drains"


def test_cancel_of_fully_filled_order_finalizes_as_filled():
    o = _exit_order(filled=0.3)
    om, _ = _live_om_with_venue(
        {"TX1": {"vol_exec": "1.0", "price": "101.0", "status": "closed"}})
    om._orders[o.order_id] = o
    assert om.cancel_order(o, reason="preempted") is True
    assert o.status == "filled", "a filled order is a FILL, not a cancel"
    events = om.poll({}, {}, now=0.0)
    assert [round(e.fill_size, 6) for e in events] == [0.7, 0.0]
    assert events[-1].final is True


def test_cancel_query_failure_keeps_forced_terminal():
    o = _exit_order(filled=0.3)
    om = _om(dry=False)

    def exploding(endpoint, data=None):
        if endpoint == "QueryOrders":
            raise RuntimeError("venue down")
        return {}

    om._timed_private = exploding
    om._orders[o.order_id] = o
    # a blocked escape is the worse failure: cancel still goes terminal
    assert om.cancel_order(o, reason="preempted") is True
    assert o.status == "cancelled" and o.remaining > EPS
    assert om.poll({}, {}, now=0.0) == []


def test_dry_run_cancel_never_queries_the_venue():
    om = _om(dry=True)
    calls = []
    om._timed_private = lambda e, d=None: calls.append(e)
    o = _exit_order()
    o.txid = "DRY-o1"
    om._orders[o.order_id] = o
    assert om.cancel_order(o) is True
    assert calls == [], "dry-run cancels are purely local"
