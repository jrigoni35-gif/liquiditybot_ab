"""29f — a rejected exit must still climb the escalation ladder, and an
exit must never be rejectable for a non-finite price.

The failure corner (deep-dive 2026-08-05): with every price reference
poisoned (mark, book mid and fair value all absent/non-finite), the exit
limit price computes to NaN, the firewall rejects it outright
(FW_INVALID_PRICE — the is_exit substitution needs a valid reference), and
`if order is None: return` skipped the attempt counter — so the position
could never reach the esc_market_after MARKET rung through this path. The
escape stayed blocked exactly as long as the feed stayed poisoned,
contradicting invariant #5 (exits ALWAYS allowed) in the one corner where
it matters most. Two guards, both pinned here: rejected submissions still
count an attempt, and the computed exit price falls back mark -> ref ->
entry so it is always finite.

`_submit_exit` is exercised off a minimal SimpleNamespace stub — the same
sanctioned pattern its own body documents for `_clear_long_book_bid_...`.
"""
import math
from types import SimpleNamespace

from main import LiquidityBot


class _RejectingOrders:
    """Records every submit and rejects it (order=None), like the firewall."""
    def __init__(self):
        self.submitted = []

    def open_orders(self):
        return []

    def _ordermin(self, pair):
        return 0.0

    def submit(self, **kw):
        self.submitted.append(kw)
        return None


def _stub_bot():
    orders = _RejectingOrders()
    stub = SimpleNamespace(
        orders=orders,
        kraken=SimpleNamespace(kraken_pair=lambda s: "XETHZUSD"),
        kraken_books={},
        marks={},
        _asset_of=lambda s: "ETH",
        _mark_fresh=lambda s, now: False,
        _exit_attempts={},
        max_slip_pct=0.10,
        esc_widen_mult=2.0,
        esc_max_slip_pct=0.60,
        esc_market_after=3,
        maker_first_profit_exits=False,
        fv=SimpleNamespace(state=lambda a: SimpleNamespace(fair_value=None)),
        vol=SimpleNamespace(state=lambda a: SimpleNamespace(sigma_bar_pct=1.2)),
        _equity=lambda: 5000.0,
    )
    return stub, orders


def _pos():
    return SimpleNamespace(symbol="ETH/USD", position_id="pos-1", size=1.0,
                           direction="long", entry_price=100.0)


def test_rejected_exit_still_counts_an_attempt():
    stub, orders = _stub_bot()
    LiquidityBot._submit_exit(stub, _pos(), 100.0, "hard_stop", now=1000.0)
    assert len(orders.submitted) == 1
    assert stub._exit_attempts.get("pos-1") == 1, \
        "a rejected exit must advance the ladder toward the MARKET rung"


def test_poisoned_feed_still_produces_a_finite_exit_price():
    stub, orders = _stub_bot()
    stub.marks = {"ETH/USD": float("nan")}      # poisoned mark, empty book,
    LiquidityBot._submit_exit(stub, _pos(), 100.0, "hard_stop", now=1000.0)
    assert len(orders.submitted) == 1
    price = orders.submitted[0]["price"]
    assert isinstance(price, float) and math.isfinite(price) and price > 0, \
        "an exit must never reach the firewall with a non-finite price"
    assert price == 100.0                        # entry-price fallback


def test_preempt_drains_the_late_fill_before_sizing_the_escape():
    """The maker-preempt oversell window (round-2 finding, 2026-08-05).

    cancel_order()'s last look recovers a fill that landed since the last
    poll into order.filled and QUEUES its FillEvent on _deferred_events -
    delivered only by the NEXT poll. take_deferred() exists precisely so
    _submit_exit can observe that fill before it sizes the replacement
    escape off pos.size... and it had ZERO production callers. Live, a
    100% close after a fully-filled preempted take sells the position
    twice (flips short); the deferred fill then drives pos.size to the
    zero-clamp with the extra units unaccounted.

    _submit_exit must drain and apply deferred events after preempting,
    before it reads pos.size."""
    stub, orders = _stub_bot()
    pos = _pos()

    class _PreemptOrders(_RejectingOrders):
        def __init__(self):
            super().__init__()
            self.drained = False

        def open_orders(self):
            resting = SimpleNamespace(purpose="exit",
                                      position_id="pos-1", post_only=True)
            return [] if self.drained else [resting]

        def cancel_order(self, order, reason=""):
            return True

        def take_deferred(self):
            # the last look recovered the maker take's fill
            self.drained = True
            return [SimpleNamespace(fill_size=1.0, order=None)]

        def submit(self, **kw):
            self.submitted.append(kw)
            return SimpleNamespace(order_id="ok")

    orders = _PreemptOrders()
    stub.orders = orders
    applied = []
    stub._handle_fill = lambda ev, now: applied.append(ev)

    LiquidityBot._submit_exit(stub, pos, 100.0, "hard_stop", now=1000.0)

    assert orders.drained, \
        "_submit_exit must drain take_deferred() after preempting a maker take"
    assert applied, "the recovered fill must be applied through _handle_fill"


def test_accepted_exit_counts_exactly_one_attempt():
    stub, orders = _stub_bot()
    orders.submit = lambda **kw: SimpleNamespace(order_id="ok")  # accepted
    LiquidityBot._submit_exit(stub, _pos(), 100.0, "hard_stop", now=1000.0)
    assert stub._exit_attempts.get("pos-1") == 1     # unchanged behavior
