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

import pytest

from core.audit import get_audit
from core.codes import Code
from core.persistence import order_from_dict, order_to_dict
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
# 7b. W2-5: force_dry cancels still-resting LIVE venue orders BEFORE
# flipping the flags, so nothing is left routing through the dry-run
# simulator while genuinely resting on Kraken.
# ---------------------------------------------------------------------------
def test_force_dry_cancels_resting_live_orders_before_sealing():
    r, calls = _live_runner()
    o = r.bot.orders.submit(asset="ETH", symbol="ETH/USD", pair="ETHUSD",
                            side="buy", price=100.0, size=1.0,
                            purpose="entry")
    assert o is not None and o in r.bot.orders.open_orders()
    calls.clear()
    mark = _audit_mark()
    r.handle_command({"cmd": "force_dry"})
    # both flags still flip (invariant #2)
    assert r.bot.dry_run is True and r.bot.orders.dry_run is True
    # the resting order was cancelled through the LIVE path (venue
    # CancelOrder issued) rather than left to route through _poll_dry
    assert ("CancelOrder", {"txid": "X1"}) in calls
    assert o.status == "cancelled"
    assert o not in r.bot.orders.open_orders()
    assert Code.OM_CLEAN_TERMINAL.value in _audit_new_codes(mark)


def test_force_dry_ack_reports_cancelled_count(caplog):
    r, _ = _live_runner()
    r.bot.orders.submit(asset="ETH", symbol="ETH/USD", pair="ETHUSD",
                        side="buy", price=100.0, size=1.0, purpose="entry")
    r.bot.orders.submit(asset="ETH", symbol="ETH/USD", pair="ETHUSD",
                        side="sell", price=100.0, size=1.0, purpose="exit",
                        position_id="p1")
    with caplog.at_level("WARNING"):
        r.handle_command({"cmd": "force_dry"})
    assert all(o.status == "cancelled" for o in r.bot.orders._orders.values())
    ack = [rec.message for rec in caplog.records if "control: force_dry" in
          rec.message]
    assert ack and "2 resting live order(s) cancelled" in ack[0]


def test_force_dry_with_no_open_orders_still_seals_cleanly():
    """Regression: the common case (nothing resting) must behave exactly
    as before - both flags flip, no crash iterating an empty order set."""
    r, calls = _live_runner()
    r.handle_command({"cmd": "force_dry"})
    assert r.bot.dry_run is True and r.bot.orders.dry_run is True
    assert calls == []


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
# 10b. C4 review, Critical #1(a): per-order TTL override (ttl_sec) -
# the long-horizon accumulation book needs its own patient resting
# lifetime (hours) distinct from the shared ~25s order_timeout_sec.
# ---------------------------------------------------------------------------
def test_ttl_sec_override_survives_past_the_shared_default_timeout():
    om = OrderManager(feed=None, config={"order_timeout_sec": 25.0},
                      dry_run=True)
    o = om.submit(asset="ETH", symbol="ETH/USD", pair="ETHUSD", side="buy",
                 price=100.0, size=1.0, purpose="entry", now=1000.0,
                 ttl_sec=6 * 3600.0)
    assert o is not None and o.ttl_sec == 6 * 3600.0
    # 30s later: past the shared 25s default, well inside the 6h override.
    # No book -> _poll_dry never fills, only the timeout branch can fire.
    events = om._poll_dry(o, book=None, sigma_bar_pct=0.05, now=1030.0)
    assert o.status == "pending", \
        "the per-order TTL override must survive past the shared default"
    assert events == []


def test_ttl_sec_override_expires_at_its_own_ttl_not_the_shared_default():
    om = OrderManager(feed=None, config={"order_timeout_sec": 25.0},
                      dry_run=True)
    o = om.submit(asset="ETH", symbol="ETH/USD", pair="ETHUSD", side="buy",
                 price=100.0, size=1.0, purpose="entry", now=1000.0,
                 ttl_sec=6 * 3600.0)
    events = om._poll_dry(o, book=None, sigma_bar_pct=0.05,
                          now=1000.0 + 6 * 3600.0 + 1.0)
    assert o.status == "expired"          # zero-fill -> expired, not cancelled
    assert events and events[-1].final is True


def test_ttl_sec_none_falls_back_to_the_shared_default_timeout_dry_run():
    # regression: a caller that omits ttl_sec (every pre-existing caller)
    # behaves EXACTLY as before - the shared order_timeout_sec applies.
    om = OrderManager(feed=None, config={"order_timeout_sec": 25.0},
                      dry_run=True)
    o = om.submit(asset="ETH", symbol="ETH/USD", pair="ETHUSD", side="buy",
                 price=100.0, size=1.0, purpose="entry", now=1000.0)
    assert o.ttl_sec is None
    events = om._poll_dry(o, book=None, sigma_bar_pct=0.05, now=1030.0)
    assert o.status == "expired"
    assert events and events[-1].final is True


def test_ttl_sec_override_applies_on_the_live_path_too():
    feed, calls = _feed()
    om = OrderManager(feed=feed, config={"order_timeout_sec": 25.0},
                      dry_run=False)
    o = _order(status="partial", filled=0.4, created_ts=1000.0)
    o.ttl_sec = 6 * 3600.0
    om._orders[o.order_id] = o
    # 30s later (past the shared 25s default): the live TTL override must
    # keep this order resting - no CancelOrder issued, no timeout event.
    events = om._poll_live(o, now=1030.0, batch={})
    assert calls == [], "the override must prevent the shared-default timeout"
    assert o.status == "partial"
    assert events == []
    # now well past the 6h override: the SAME order times out on its own TTL
    events2 = om._poll_live(o, now=1000.0 + 6 * 3600.0 + 1.0, batch={})
    assert ("CancelOrder", {"txid": "TX1"}) in calls
    assert o.status == "cancelled"        # filled > 0 -> cancelled not expired
    assert events2 and events2[-1].final is True


def test_ttl_sec_non_finite_or_non_positive_degrades_to_none():
    om = OrderManager(feed=None, config={}, dry_run=True)
    for bad in (float("nan"), float("inf"), -1.0, 0.0):
        o = om.submit(asset="ETH", symbol="ETH/USD", pair="ETHUSD",
                      side="buy", price=100.0, size=1.0, purpose="entry",
                      ttl_sec=bad)
        assert o is not None and o.ttl_sec is None, bad


def test_ttl_sec_round_trips_through_persistence():
    o = _order()
    o.ttl_sec = 6 * 3600.0
    d = order_to_dict(o)
    assert d["ttl_sec"] == 6 * 3600.0
    back = order_from_dict(d)
    assert back.ttl_sec == pytest.approx(6 * 3600.0)


def test_ttl_sec_absent_from_persisted_dict_restores_none():
    # legacy snapshot written before this task has no "ttl_sec" key at all.
    o = _order()
    d = order_to_dict(o)
    del d["ttl_sec"]
    assert order_from_dict(d).ttl_sec is None


# ---------------------------------------------------------------------------
# 10c. C4 review, Minor #10: has_open's book-aware filter (a resting
# LONG-book bid must not block the 5m book's own has_open("entry") check)
# ---------------------------------------------------------------------------
def test_has_open_book_aware_filter_distinguishes_5m_and_long():
    om = OrderManager(feed=None, config={}, dry_run=True)
    om.submit(asset="ETH", symbol="ETH/USD", pair="ETHUSD", side="buy",
             price=100.0, size=1.0, purpose="entry", meta={"book": "5m"})
    assert om.has_open("ETH", "entry") is True
    assert om.has_open("ETH", "entry", book="5m") is True
    assert om.has_open("ETH", "entry", book="long") is False


def test_has_open_book_aware_filter_finds_a_long_book_order():
    om = OrderManager(feed=None, config={}, dry_run=True)
    om.submit(asset="ETH", symbol="ETH/USD", pair="ETHUSD", side="buy",
             price=100.0, size=1.0, purpose="entry", meta={"book": "long"})
    assert om.has_open("ETH", "entry", book="long") is True
    assert om.has_open("ETH", "entry", book="5m") is False


def test_has_open_no_meta_book_defaults_5m():
    # every pre-existing 5m submit() call omits meta["book"] entirely -
    # has_open's book filter must default the SAME "5m" main._handle_fill
    # already assumes, or this whole fix silently reclassifies every
    # existing 5m order as book=None.
    om = OrderManager(feed=None, config={}, dry_run=True)
    om.submit(asset="ETH", symbol="ETH/USD", pair="ETHUSD", side="buy",
             price=100.0, size=1.0, purpose="entry")
    assert om.has_open("ETH", "entry", book="5m") is True


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


# ---------------------------------------------------------------------------
# 13. OM-013 post-format zero guard (W2-8): pair precision can floor a
# dust-but-nonzero size/price to a venue string that parses to ZERO. The
# ordermin gate is keyed on the RAW float and is skipped entirely when a
# pair's ordermin metadata is 0.0 (Kraken AssetPairs omission / new pair) -
# this must be caught separately, on BOTH the live and dry-run paths, for
# both price and volume, for both entry and exit purposes.
# ---------------------------------------------------------------------------
_ZERO_FMT_META = {"XXXUSD": {"price_decimals": 2, "lot_decimals": 2,
                             "ordermin": 0.0}}


def test_zero_format_volume_refused_live_exit_never_reaches_addorder():
    feed, calls = _feed(add_order_result={"txid": ["T1"]})
    om = OrderManager(feed=feed, config={}, dry_run=False,
                      pair_meta=_ZERO_FMT_META)
    mark = _audit_mark()
    o = om.submit(asset="XXX", symbol="XXX/USD", pair="XXXUSD", side="sell",
                 price=100.0, size=0.001, purpose="exit", position_id="p1")
    assert o is None
    assert not any(ep == "AddOrder" for ep, _ in calls), \
        "a zero-formatted volume must never reach the venue call"
    assert om._orders == {}
    assert om.zero_format_rejects == 1
    assert Code.OM_ZERO_AFTER_FORMAT.value in _audit_new_codes(mark)


def test_zero_format_price_refused_live_entry():
    feed, calls = _feed(add_order_result={"txid": ["T1"]})
    om = OrderManager(feed=feed, config={}, dry_run=False,
                      pair_meta=_ZERO_FMT_META)
    # size formats fine (1.0 -> "1.00") but price floors to "0.00"
    o = om.submit(asset="XXX", symbol="XXX/USD", pair="XXXUSD", side="buy",
                 price=0.001, size=1.0, purpose="entry")
    assert o is None
    assert not any(ep == "AddOrder" for ep, _ in calls)
    assert om.zero_format_rejects == 1


def test_zero_format_volume_refused_dry_run_too():
    """Paper trading must not exercise an order the real venue could never
    accept: the guard applies identically before dry-run registration."""
    om = OrderManager(feed=None, config={}, dry_run=True,
                      pair_meta=_ZERO_FMT_META)
    o = om.submit(asset="XXX", symbol="XXX/USD", pair="XXXUSD", side="sell",
                 price=100.0, size=0.001, purpose="exit", position_id="p1")
    assert o is None
    assert om._orders == {}
    assert om.zero_format_rejects == 1


def test_zero_format_guard_does_not_disturb_normal_orders():
    """Regression: a non-dust order at the same pair still submits fine."""
    feed, calls = _feed(add_order_result={"txid": ["T1"]})
    om = OrderManager(feed=feed, config={}, dry_run=False,
                      pair_meta=_ZERO_FMT_META)
    o = om.submit(asset="XXX", symbol="XXX/USD", pair="XXXUSD", side="buy",
                 price=100.0, size=1.0, purpose="entry")
    assert o is not None and o.txid == "T1"
    assert calls and calls[0][0] == "AddOrder"
    assert calls[0][1]["volume"] == "1.00" and calls[0][1]["price"] == "100.00"
    assert om.zero_format_rejects == 0


def test_zero_format_market_exit_ignores_price_field():
    """A market-order exit sends no price field to the venue; only the
    formatted VOLUME can trip the guard for ordertype=market."""
    feed, calls = _feed(add_order_result={"txid": ["T1"]})
    om = OrderManager(feed=feed, config={}, dry_run=False,
                      pair_meta=_ZERO_FMT_META)
    o = om.submit(asset="XXX", symbol="XXX/USD", pair="XXXUSD", side="sell",
                 price=0.0, size=1.0, purpose="exit", position_id="p1",
                 ordertype="market", ref_price=100.0)
    assert o is not None, "market exit volume formats fine; must not be blocked"
    assert "price" not in calls[0][1]
