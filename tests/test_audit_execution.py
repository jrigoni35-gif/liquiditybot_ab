"""tests/test_audit_execution.py — regression pins for the 2026-08-01
whole-codebase audit, "execution" group (execution/order_manager.py).

H2  ManagedOrder.size kept the UNFLOORED request while the venue received
    _fmt_volume's ROUND_FLOOR string. Live `order.filled` mirrors Kraken's
    `vol_exec` (that same floored string), so `remaining` settled in
    [0, 10^-lot_decimals) and never reached main.py's EPS=1e-9. The
    exit-escalation counter (`main.py:1704`, popped only on
    `order.remaining <= EPS`) therefore never de-escalated: maker-first
    profit exits (which require `attempts == 0`) died from the second tier
    on, and the `go_market` rung armed with no failed fill ever occurring.

H3  `_poll_live`'s timeout branch cancelled WITHOUT the final QueryOrders
    reconciliation that `cancel_order` performs, so a fill landing in the
    cancel window was dropped permanently — and that window is not a rare
    race: poll() takes ONE batched snapshot at the top, then each timing-out
    order issues its own throttled CancelOrder round-trip afterwards.

M2  Exit preemption sized the replacement escape off a stale `pos.size`
    because `cancel_order`'s recovered fill queued on `_deferred_events`,
    drained only by the NEXT poll(). `take_deferred()` is the
    OrderManager-side half of the fix (main._submit_exit must call it —
    see the report's cross-file note).

Real OrderManager throughout; only the venue (`feed`) is stubbed, following
tests/test_order_time_and_cancel.py and tests/test_exec_quality_stats.py.
"""
import types

import pytest

from execution.order_manager import EPS, ManagedOrder, OrderManager

# main.py's own epsilon (main.py:107). The exit-ladder de-escalation at
# main.py:1704 compares `order.remaining` against THIS, not against
# order_manager's 1e-12 — pinned as a literal so this suite does not import
# the engine just to read one constant.
MAIN_EPS = 1e-9

# BTC-shaped venue metadata: 8 lot decimals is the strictest precision in
# the shipped universe and the one the finding was measured against.
_LOT8 = {"XXBTZUSD": {"lot_decimals": 8, "price_decimals": 1,
                      "ordermin": 0.0001}}
# a realistic 8-dp-and-then-some sizer output (fractional Kelly on an
# 8-decimal pair produces exactly this shape) and its floored twin
_RAW_SIZE = 0.073012345678
_FLOORED_SIZE = 0.07301234


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _om_live(pair_meta=None, query_queue=None, config=None):
    """Real OrderManager on the LIVE path, venue stubbed.

    `query_queue` is consumed in call order by QueryOrders (the last entry
    then repeats), so a test can make the batched poll snapshot and the
    post-cancel last look DISAGREE — which is the whole of H3.
    """
    calls = []
    queue = list(query_queue or [])

    def _post(endpoint, data=None):
        calls.append((endpoint, dict(data or {})))
        if endpoint == "AddOrder":
            return {"txid": ["TX1"]}
        if endpoint == "QueryOrders":
            if not queue:
                return {}
            return queue.pop(0) if len(queue) > 1 else queue[0]
        return {}

    feed = types.SimpleNamespace(_private_post=_post,
                                 cancel_all_orders_after=lambda sec: True)
    om = OrderManager(feed=feed,
                      config=config or {"order_timeout_sec": 25.0},
                      dry_run=False, pair_meta=pair_meta or {})
    return om, calls


def _endpoints(calls):
    return [ep for ep, _ in calls]


def _resting(filled=0.0, created_ts=1000.0, size=1.0):
    return ManagedOrder(order_id="o1", txid="TX1", asset="BTC",
                        pair="XXBTZUSD", symbol="BTC/USD", side="sell",
                        price=50_000.0, size=size, filled=filled,
                        avg_price=50_000.0 if filled else 0.0,
                        status="partial" if filled else "pending",
                        purpose="exit", position_id="p1", post_only=False,
                        created_ts=created_ts)


def _submit_exit(om, size=1.0, now=1000.0, post_only=False):
    return om.submit(asset="BTC", symbol="BTC/USD", pair="XXBTZUSD",
                     side="sell", price=50_000.0, size=size, purpose="exit",
                     position_id="p1", close_pct=100.0, post_only=post_only,
                     ref_price=50_000.0, now=now)


# ---------------------------------------------------------------------------
# H2 — order.size must be the quantity the venue actually receives
# ---------------------------------------------------------------------------
def test_submit_adopts_the_floored_volume_it_actually_sends():
    """The wire volume and ManagedOrder.size are ONE quantity, not two."""
    om, calls = _om_live(pair_meta=_LOT8)
    o = _submit_exit(om, size=_RAW_SIZE)
    assert o is not None
    wire = [d for ep, d in calls if ep == "AddOrder"][0]["volume"]
    assert wire == "0.07301234", "ROUND_FLOOR at lot_decimals=8"
    assert o.size == _FLOORED_SIZE
    assert o.size == float(wire), "the order carries the SUBMITTED quantity"


def test_live_full_fill_drives_remaining_under_the_engine_epsilon():
    """The consequence H2 is really about: with the unfloored size, a fully
    filled order kept `remaining` at 5.678e-9 — above main.py's 1e-9 — so
    `_exit_attempts` was never popped and the ladder ratcheted forever."""
    om, _ = _om_live(pair_meta=_LOT8)
    o = _submit_exit(om, size=_RAW_SIZE)
    # the venue echoes back exactly the volume string it was handed
    om._poll_live(o, now=1001.0,
                  batch={"TX1": {"vol_exec": "0.07301234",
                                 "price": "50000.0", "status": "closed"}})
    assert o.status == "filled"
    assert o.remaining <= MAIN_EPS, ("a fully filled order must satisfy "
                                     "main.py:1704's de-escalation test")
    assert o.fill_ratio == pytest.approx(1.0, abs=1e-12)


def test_dry_and_live_submit_agree_on_the_recorded_size():
    """_sim_maker_cross fills `order.remaining` exactly, so an unfloored dry
    size made paper metrics claim a maker capture the live path could never
    reach. Both paths must record the same quantity."""
    live, _ = _om_live(pair_meta=_LOT8)
    dry = OrderManager(feed=None, config={"order_timeout_sec": 25.0},
                       dry_run=True, pair_meta=_LOT8)
    lo = _submit_exit(live, size=_RAW_SIZE)
    do = _submit_exit(dry, size=_RAW_SIZE)
    assert lo is not None and do is not None
    assert lo.size == do.size == _FLOORED_SIZE


def test_size_already_at_venue_precision_is_untouched():
    """Behavior preservation: the floor is a no-op for any size the venue
    could already accept verbatim (the overwhelmingly common case)."""
    om, _ = _om_live(pair_meta=_LOT8)
    o = _submit_exit(om, size=0.25)
    assert o is not None and o.size == 0.25


def test_ordermin_floored_escape_still_equals_the_venue_minimum():
    """Invariant #5 guard: EX-4 floors a firewall-clamped exit back UP to
    ordermin so the escape stays executable. The volume floor must not shave
    that back below the minimum again."""
    om = OrderManager(feed=None, config={}, dry_run=True)
    om._ordermin = lambda pair: 0.1
    o = om.submit(asset="BTC", symbol="BTC/USD", pair="XXBTZUSD",
                  side="sell", price=50_000.0, size=0.1, purpose="exit",
                  position_id="p1", post_only=False, ref_price=50_000.0)
    assert o is not None, "the escape must stay executable"
    assert o.size == 0.1


# ---------------------------------------------------------------------------
# H3 — the timeout cancel gets the SAME last look cancel_order performs
# ---------------------------------------------------------------------------
def test_timeout_cancel_recovers_a_fill_from_the_cancel_window():
    """Batch staleness, the dominant trigger: poll()'s single QueryOrders
    snapshot says 'open', the order fills while the throttled CancelOrder is
    in flight, and the last look is the only thing that can see it."""
    om, calls = _om_live(
        pair_meta=_LOT8,
        query_queue=[
            # the batched snapshot at the top of poll(): still resting
            {"TX1": {"vol_exec": "0", "price": "0", "status": "open"}},
            # the last look AFTER CancelOrder: it filled in between
            {"TX1": {"vol_exec": "1.00000000", "price": "50100.0",
                     "status": "closed", "fee": "2.00"}},
        ])
    o = _submit_exit(om, size=1.0, now=1000.0)
    events = om.poll({}, {}, now=1030.0)          # 30s > 25s timeout
    assert _endpoints(calls) == ["AddOrder", "QueryOrders",
                                 "CancelOrder", "QueryOrders"]
    assert o.status == "filled", "a fill is a FILL, not a timeout expiry"
    assert sum(e.fill_size for e in events) == pytest.approx(1.0)
    assert events[-1].final is True
    assert o.fees_usd == pytest.approx(2.00), "venue fee booked, not the bps"
    # recovered inside poll(), so the engine applies it THIS cycle — nothing
    # is left on the deferred queue to be double-applied later
    assert om._deferred_events == []


def test_timeout_cancel_books_a_partial_that_landed_in_the_window():
    """A partial recovered at cancel time still cancels — but the units are
    booked, so the position is not forked from the venue."""
    om, calls = _om_live(
        pair_meta=_LOT8,
        query_queue=[
            {"TX1": {"vol_exec": "0", "price": "0", "status": "open"}},
            {"TX1": {"vol_exec": "0.4", "price": "50100.0",
                     "status": "canceled"}},
        ])
    o = _submit_exit(om, size=1.0, now=1000.0)
    events = om.poll({}, {}, now=1030.0)
    assert o.filled == pytest.approx(0.4)
    assert o.status == "cancelled", "the resting remainder really did cancel"
    assert [round(e.fill_size, 8) for e in events] == [0.4, 0.0]
    assert events[-1].final is True
    assert o.remaining > EPS


def test_timeout_reconcile_failure_keeps_the_forced_terminal():
    """Fail-safe contract, identical to cancel_order's: a venue that cannot
    answer the last look must NOT leave the order in limbo — it still goes
    terminal off last-known fill state."""
    calls = []

    def _post(endpoint, data=None):
        calls.append(endpoint)
        if endpoint == "QueryOrders":
            raise RuntimeError("venue down")
        return {}

    feed = types.SimpleNamespace(_private_post=_post,
                                 cancel_all_orders_after=lambda sec: True)
    om = OrderManager(feed=feed, config={"order_timeout_sec": 25.0},
                      dry_run=False)
    o = _resting(filled=0.4, created_ts=1000.0)
    om._orders[o.order_id] = o
    events = om._poll_live(o, now=1030.0, batch={})
    assert calls == ["CancelOrder", "QueryOrders"], "the last look was tried"
    assert o.status == "cancelled" and o.filled == pytest.approx(0.4)
    assert events and events[-1].final is True


def test_timeout_reconcile_ignores_a_garbage_venue_response():
    """safe_float's contract carried into the new call site: NaN/garbage
    vol_exec degrades to last-known, never a phantom fill."""
    om, calls = _om_live(
        query_queue=[
            {"TX1": {"vol_exec": "0", "price": "0", "status": "open"}},
            {"TX1": {"vol_exec": "NaN", "price": "not-a-number",
                     "status": "open"}},
        ])
    o = _resting(filled=0.4, created_ts=1000.0)
    om._orders[o.order_id] = o
    events = om.poll({}, {}, now=1030.0)
    assert _endpoints(calls) == ["QueryOrders", "CancelOrder", "QueryOrders"]
    assert o.filled == pytest.approx(0.4), "no phantom fill from garbage"
    assert o.status == "cancelled"
    assert [round(e.fill_size, 8) for e in events] == [0.0]


def test_dry_run_timeout_never_reconciles_against_the_venue():
    """The last look is live-only: paper trading must issue no private POST
    at all (the dry simulator owns its own terminal transitions)."""
    calls = []
    feed = types.SimpleNamespace(
        _private_post=lambda ep, data=None: calls.append(ep),
        cancel_all_orders_after=lambda sec: True)
    om = OrderManager(feed=feed, config={"order_timeout_sec": 25.0},
                      dry_run=True, pair_meta=_LOT8)
    o = _submit_exit(om, size=1.0, now=1000.0)
    om.poll({}, {}, now=1030.0)
    assert calls == []
    assert o.status in ("expired", "cancelled")


def test_cancel_order_last_look_survives_the_shared_helper():
    """Non-regression for the H3 refactor: cancel_order's own final
    reconciliation (correct, and pinned by tests/test_order_time_and_cancel
    .py) must behave identically now that it routes through _final_reconcile
    — including the deferred-delivery contract."""
    om, calls = _om_live(
        query_queue=[{"TX1": {"vol_exec": "0.5", "price": "50100.0",
                              "status": "canceled"}}])
    o = _resting(filled=0.3)
    om._orders[o.order_id] = o
    assert om.cancel_order(o, reason="preempted") is True
    assert _endpoints(calls) == ["CancelOrder", "QueryOrders"]
    assert o.status == "cancelled" and o.filled == pytest.approx(0.5)
    # still DEFERRED (not returned by cancel_order) — the engine's single
    # _handle_fill path owns application
    events = om.poll({}, {}, now=0.0)
    assert [round(e.fill_size, 8) for e in events] == [0.2]


# ---------------------------------------------------------------------------
# M2 — the preempting exit must be able to SEE the recovered fill
# ---------------------------------------------------------------------------
def test_take_deferred_exposes_the_late_fill_before_the_next_poll():
    """main._submit_exit preempts a resting maker take, then sizes the
    replacement escape off pos.size a few lines later. Without a drain here
    the recovered 0.25 is invisible until the next poll(), so the escape is
    sized off a stale (too large) position."""
    om, _ = _om_live(
        query_queue=[{"TX1": {"vol_exec": "0.25", "price": "50100.0",
                              "status": "canceled"}}])
    o = _resting(filled=0.0)
    o.post_only = True                       # a resting maker profit-take
    om._orders[o.order_id] = o
    assert om.cancel_order(o, reason="preempted by hard_stop") is True
    drained = om.take_deferred()
    assert [round(e.fill_size, 8) for e in drained] == [0.25]
    assert all(e.order is o for e in drained), "same order object"


def test_take_deferred_drains_exactly_once():
    """Single application: whatever the caller drained must NOT be replayed
    by the next poll(), or the fill is booked twice."""
    om, _ = _om_live(
        query_queue=[{"TX1": {"vol_exec": "0.25", "price": "50100.0",
                              "status": "canceled"}}])
    o = _resting(filled=0.0)
    om._orders[o.order_id] = o
    om.cancel_order(o, reason="preempted by hard_stop")
    assert len(om.take_deferred()) == 1
    assert om.take_deferred() == []
    assert om.poll({}, {}, now=0.0) == []


def test_take_deferred_is_empty_when_nothing_was_deferred():
    om, _ = _om_live()
    assert om.take_deferred() == []
