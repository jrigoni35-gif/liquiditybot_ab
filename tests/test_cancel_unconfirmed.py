"""OM-090: an unconfirmed venue cancel must be AUDIBLE, not silent.

`feed._private_post` never raises — on a rate limit, a 5xx, or a Kraken
error payload it returns None. Both cancel paths (the timeout terminator in
_poll_live and the explicit preempt in cancel_order) discarded that result
and forced local state terminal anyway, so the order left open_orders() and
was never queried again while the REAL order — submitted GTC, no expiretm —
kept resting at the venue. Worse, a healthy bot keeps re-arming
CancelAllOrdersAfter every ~30s, so the deadman that is supposed to be the
venue-side backstop never fires. An orphaned ENTRY is untracked inventory
with no stop; an orphaned EXIT means the venue is flat while the local book
says open, and the ladder's next rung double-sells.

The terminal transition still happens (a blocked escape is the worse
failure). These tests pin that the residue is COUNTED and AUDITED so an
operator can reconcile against the venue.
"""
import time
import types

from core.codes import Code
from execution.order_manager import ManagedOrder, OrderManager


def _dead_feed():
    """A live feed whose private POSTs all fail the way Kraken's do:
    _private_post returns None rather than raising (rate limit / 5xx /
    error payload)."""
    return types.SimpleNamespace(
        _private_post=lambda endpoint, data=None: None,
        cancel_all_orders_after=lambda sec: True,
        kraken_pair=lambda symbol: "XETHZUSD")


def _om(dry_run: bool) -> OrderManager:
    return OrderManager(feed=_dead_feed(),
                        config={"order_timeout_sec": 25.0},
                        dry_run=dry_run)


def _resting(om: OrderManager) -> ManagedOrder:
    o = ManagedOrder(order_id="o1", txid="TX1", asset="ETH",
                     pair="XETHZUSD", symbol="ETH/USD", side="sell",
                     price=2000.0, size=1.0, purpose="exit",
                     position_id="p1", post_only=True,
                     created_ts=time.time() - 10_000)
    om._orders[o.order_id] = o
    return o


def test_unconfirmed_preempt_cancel_is_counted():
    om = _om(dry_run=False)
    o = _resting(om)
    om.cancel_order(o, reason="preempted by hard_stop")
    assert om.cancel_unconfirmed == 1, \
        "a venue cancel with no confirmation must be counted, not swallowed"
    assert o.status in ("cancelled", "expired"), \
        "the terminal transition must still happen (never block an escape)"


def test_unconfirmed_timeout_cancel_is_counted():
    om = _om(dry_run=False)
    o = _resting(om)
    om._poll_live(o, time.time(), {})
    assert om.cancel_unconfirmed == 1


def test_dry_run_never_flags_a_cancel():
    om = _om(dry_run=True)
    o = _resting(om)
    om.cancel_order(o, reason="preempted by hard_stop")
    assert om.cancel_unconfirmed == 0, \
        "dry-run posts nothing to the venue - there is no orphan to report"


def test_counter_is_exposed_in_the_status_readout():
    om = _om(dry_run=False)
    om.cancel_unconfirmed = 3
    assert om.status().get("cancel_unconfirmed") == 3


def test_code_is_registered():
    assert Code.OM_CANCEL_UNCONFIRMED.value == "OM-090"
