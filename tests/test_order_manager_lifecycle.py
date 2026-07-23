"""tests/test_order_manager_lifecycle.py — characterization pins for the
OrderManager live lifecycle (execution/order_manager.py): AddOrder success
and reject, the OM-030 illegal-transition state machine, the OM-050 dead-
man escalation/reset, the live timeout-cancel path, and the OM-010/OM-011
fail-closed input gates. Also pins force_dry (hard invariant #2) end to
end through runner.BotRunner.handle_command.

Real OrderManager throughout; only the venue (`feed`) is stubbed, following
the pattern in tests/test_exec_quality_stats.py and
tests/test_order_time_and_cancel.py.
"""
import json
import types

from core.audit import get_audit
from core.codes import Code
from execution.order_manager import ManagedOrder, OrderManager
from runner import BotRunner


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _feed(add_order_result=None, private_post=None):
    """A minimal venue stub exposing exactly the surface OrderManager calls:
    _private_post(endpoint, data) and cancel_all_orders_after(sec)."""
    calls = []

    def _post(endpoint, data=None):
        calls.append((endpoint, data))
        if private_post is not None:
            return private_post(endpoint, data)
        if endpoint == "AddOrder":
            return add_order_result if add_order_result is not None else {}
        return {}

    feed = types.SimpleNamespace(_private_post=_post,
                                 cancel_all_orders_after=lambda sec: True)
    return feed, calls


def _audit_mark():
    """(path, text-so-far) so a test can read only what IT wrote."""
    p = get_audit().path
    return p, (p.read_text(encoding="utf-8") if p.exists() else "")


def _audit_new_codes(mark):
    path, before = mark
    after = path.read_text(encoding="utf-8") if path.exists() else ""
    new_lines = after[len(before):].strip().splitlines()
    return [json.loads(line)["code"] for line in new_lines if line.strip()]


def _order(status="pending", filled=0.0, created_ts=1000.0, txid="TX1"):
    return ManagedOrder(order_id="o1", txid=txid, asset="ETH", pair="ETHUSD",
                        symbol="ETH/USD", side="buy", price=100.0, size=1.0,
                        filled=filled,
                        avg_price=100.0 if filled else 0.0,
                        status=status, created_ts=created_ts)


# ---------------------------------------------------------------------------
# 5/6. live submit: success + reject (OM-021)
# ---------------------------------------------------------------------------
def test_live_submit_success_tracks_txid_and_open_order():
    feed, calls = _feed(add_order_result={"txid": ["ABC123"]})
    om = OrderManager(feed=feed, config={}, dry_run=False)
    o = om.submit(asset="ETH", symbol="ETH/USD", pair="ETHUSD", side="buy",
                 price=100.0, size=1.0, purpose="entry")
    assert o is not None
    assert o.txid == "ABC123"
    assert o.status == "pending"
    assert o in om.open_orders()
    assert om._orders[o.order_id] is o
    assert calls and calls[0][0] == "AddOrder"


def test_live_submit_reject_increments_venue_rejects_and_audits():
    feed, _calls = _feed(add_order_result={})   # no txid -> a reject
    om = OrderManager(feed=feed, config={}, dry_run=False)
    mark = _audit_mark()
    o = om.submit(asset="ETH", symbol="ETH/USD", pair="ETHUSD", side="buy",
                 price=100.0, size=1.0, purpose="entry")
    assert o is None
    assert om.venue_rejects == 1
    assert om._orders == {}
    assert Code.OM_VENUE_REJECT.value in _audit_new_codes(mark)


# ---------------------------------------------------------------------------
# 7. force_dry end-to-end (hard invariant #2)
# ---------------------------------------------------------------------------
def _live_runner():
    feed, calls = _feed(add_order_result={"txid": ["X1"]})
    om = OrderManager(feed=feed, config={}, dry_run=False)
    r = BotRunner.__new__(BotRunner)
    r.state = "RUNNING"
    r.bot = types.SimpleNamespace(dry_run=False, orders=om, live_armed=True)
    return r, calls


def test_force_dry_flips_both_flags_and_blocks_the_feed():
    r, calls = _live_runner()
    r.handle_command({"cmd": "force_dry"})
    assert r.bot.dry_run is True                # bot.dry_run flipped
    assert r.bot.orders.dry_run is True          # OrderManager cache flipped
    o = r.bot.orders.submit(asset="ETH", symbol="ETH/USD", pair="ETHUSD",
                            side="buy", price=100.0, size=1.0,
                            purpose="entry")
    assert o is not None and o.txid.startswith("DRY-")   # dry-run path taken
    assert calls == [], "force_dry must seal the venue: no private POST"


# ---------------------------------------------------------------------------
# 8. OM-030 illegal transition
# ---------------------------------------------------------------------------
def test_terminal_order_refuses_backward_transition():
    om = OrderManager(feed=None, config={}, dry_run=True)
    o = _order(status="filled")
    om._orders[o.order_id] = o
    mark = _audit_mark()
    ok = om._transition(o, "pending", "bogus resurrection")
    assert ok is False
    assert o.status == "filled"                  # terminal states never move
    assert Code.OM_ILLEGAL_TRANSITION.value in _audit_new_codes(mark)


def test_illegal_transition_from_partial_forces_cancelled():
    om = OrderManager(feed=None, config={}, dry_run=True)
    o = _order(status="partial", filled=0.4)      # "expired" is not legal
    om._orders[o.order_id] = o                    # from partial (OM-030)
    mark = _audit_mark()
    ok = om._transition(o, "expired", "illegal test")
    assert ok is False
    assert o.status == "cancelled"               # forced to the safe terminal
    assert Code.OM_ILLEGAL_TRANSITION.value in _audit_new_codes(mark)


# ---------------------------------------------------------------------------
# 9. OM-050 dead-man escalation + reset
# ---------------------------------------------------------------------------
def test_deadman_escalates_after_three_spaced_failures_then_resets():
    state = {"ok": False}
    feed = types.SimpleNamespace(
        cancel_all_orders_after=lambda sec: state["ok"])
    om = OrderManager(feed=feed, config={"deadman_timeout_sec": 60},
                     dry_run=False)
    mark = _audit_mark()
    # cadence is deadman_sec/2 = 30s; each call below clears that gate
    om.refresh_deadman(now=30.0)
    assert om._deadman_failures == 1
    om.refresh_deadman(now=60.0)
    assert om._deadman_failures == 2
    om.refresh_deadman(now=90.0)
    assert om._deadman_failures == 3
    assert Code.OM_DEADMAN_FAIL.value in _audit_new_codes(mark)
    state["ok"] = True
    om.refresh_deadman(now=120.0)
    assert om._deadman_failures == 0             # a success resets the count
    assert om._deadman_refreshed == 120.0


# ---------------------------------------------------------------------------
# 10. live timeout-cancel resolves terminal by fill ratio
# ---------------------------------------------------------------------------
def test_live_timeout_issues_cancelorder_and_resolves_by_fill_ratio():
    feed, calls = _feed()
    om = OrderManager(feed=feed, config={"order_timeout_sec": 25.0},
                      dry_run=False)
    o = _order(status="partial", filled=0.4, created_ts=1000.0)
    om._orders[o.order_id] = o
    # batch={} (no txid entry): the live path falls through to the timeout
    # check instead of a venue-reported terminal status
    events = om._poll_live(o, now=1030.0, batch={})   # 30s > 25s timeout
    assert ("CancelOrder", {"txid": "TX1"}) in calls
    assert o.status == "cancelled"        # filled > 0 -> cancelled not expired
    assert events and events[-1].final is True


# ---------------------------------------------------------------------------
# 11. OM-011 market orders are exit-escalation only
# ---------------------------------------------------------------------------
def test_om011_market_entry_refused_market_exit_accepted():
    om = OrderManager(feed=None, config={}, dry_run=True)
    entry = om.submit(asset="ETH", symbol="ETH/USD", pair="ETHUSD",
                      side="buy", price=100.0, size=1.0,
                      ordertype="market", purpose="entry")
    assert entry is None
    exit_o = om.submit(asset="ETH", symbol="ETH/USD", pair="ETHUSD",
                       side="sell", price=100.0, size=1.0,
                       ordertype="market", purpose="exit",
                       position_id="p1")
    assert exit_o is not None and exit_o.ordertype == "market"


# ---------------------------------------------------------------------------
# 12. OM-010 fail-closed inputs never raise and never register an order
# ---------------------------------------------------------------------------
def test_om010_fail_closed_inputs_never_raise_or_register():
    om = OrderManager(feed=None, config={}, dry_run=True)
    bad_calls = [
        dict(side="buyy", purpose="entry", ordertype="limit",
            price=100.0, size=1.0),
        dict(side="buy", purpose="bogus", ordertype="limit",
            price=100.0, size=1.0),
        dict(side="buy", purpose="entry", ordertype="stop",
            price=100.0, size=1.0),
        dict(side="buy", purpose="entry", ordertype="limit",
            price=float("nan"), size=1.0),
        dict(side="buy", purpose="entry", ordertype="limit",
            price=100.0, size=float("inf")),
    ]
    for kw in bad_calls:
        o = om.submit(asset="ETH", symbol="ETH/USD", pair="ETHUSD", **kw)
        assert o is None, kw
    assert om._orders == {}
