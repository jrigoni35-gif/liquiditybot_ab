"""tests/test_exit_preemption.py — a risk-off exit must PREEMPT a resting maker
profit-take, never wait it out.

Maker-first profit exits (test_maker_first_exit.py) rest post-only on the
passive side to capture the spread. But _submit_exit's "one live exit per
position" dedup used to drop ANY later exit while one rested — so a hard stop,
fault, derisk or hedge-unwind arriving mid-rest was silently discarded and the
position sat unprotected for a full order timeout (~25s) behind a maker order
that, in a fast adverse move, never fills (it rests on the wrong side).

The fix: a risk-off exit (profit_take=False) cancels a resting maker
profit-take (post_only) and takes its place marketable-first. Every other
pairing keeps the dedup — a marketable risk-off exit already in flight is not
duplicated, and a profit-take never preempts anything.

Exit-routing tests drive the REAL main._submit_exit against a stub self (same
idiom as test_maker_first_exit); the cancel primitive is tested against a real
dry-run OrderManager.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import main as main_mod
from core.state import Position
from execution.order_manager import ManagedOrder, OrderManager


def _resting(post_only: bool) -> ManagedOrder:
    return ManagedOrder(order_id="rest1", txid=None, asset="ETH",
                        pair="XETHZUSD", symbol="ETH/USD", side="sell",
                        price=101.0, size=1.0, status="pending", purpose="exit",
                        position_id="p1", post_only=post_only)


def _fake_self(resting):
    captured, cancels = {}, []

    def fake_submit(**kw):
        captured.update(kw)
        return SimpleNamespace(order_id="new", position_id="p1", purpose="exit")

    def fake_cancel(order, reason="cancelled"):
        cancels.append((order, reason))
        if order in resting:
            resting.remove(order)          # mirror the real terminal transition
        return True

    fake = SimpleNamespace(
        _asset_of=lambda s: "ETH",
        kraken=SimpleNamespace(kraken_pair=lambda s: "XETHZUSD"),
        orders=SimpleNamespace(open_orders=lambda: list(resting),
                               _ordermin=lambda p: 0.0,
                               submit=fake_submit, cancel_order=fake_cancel),
        _exit_attempts={"p1": 1},          # the maker already consumed attempt 1
        max_slip_pct=0.5, esc_widen_mult=2.0, esc_max_slip_pct=3.0,
        esc_market_after=3,
        kraken_books={"ETH": {"bids": [[99.0, 5.0]], "asks": [[101.0, 5.0]]}},
        marks={"ETH/USD": 100.0}, maker_first_profit_exits=True,
        # EX-6 collar-ref chain: fresh mark -> book mid -> fair value
        _mark_fresh=lambda sym, now: True,
        fv=SimpleNamespace(state=lambda a: SimpleNamespace(
            fair_value=100.0)),
        _equity=lambda: 1000.0,
        vol=SimpleNamespace(state=lambda a: SimpleNamespace(sigma_bar_pct=0.3)),
    )
    fake._captured, fake._cancels = captured, cancels
    return fake


def _pos():
    return Position(position_id="p1", symbol="ETH/USD", direction="long",
                    entry_price=100.0, size=1.0, original_size=1.0,
                    opened_at=datetime.now(timezone.utc))


def _submit(fake, *, reason, tier_fired, profit_take):
    main_mod.LiquidityBot._submit_exit(fake, _pos(), close_pct=100.0,
                                       reason=reason, tier_fired=tier_fired,
                                       now=1000.0, profit_take=profit_take)


# --- the fix: risk-off preempts a resting maker take ------------------------
def test_risk_off_preempts_resting_maker_take():
    fake = _fake_self([_resting(post_only=True)])
    _submit(fake, reason="hard stop", tier_fired=0, profit_take=False)
    assert len(fake._cancels) == 1, "the resting maker take must be cancelled"
    assert fake._captured, "a replacement exit must be submitted, not dropped"
    assert fake._captured["post_only"] is False, "the escape is marketable"
    assert fake._captured["price"] < 99.0, "priced through the bid (marketable)"


def test_protective_floor_also_preempts_resting_maker_take():
    # a trailing/BE floor close carries tier_fired>0 but profit_take=False:
    # it is risk-off and must also clear the resting maker take.
    fake = _fake_self([_resting(post_only=True)])
    _submit(fake, reason="tier 2 trail", tier_fired=2, profit_take=False)
    assert len(fake._cancels) == 1
    assert fake._captured and fake._captured["post_only"] is False


# --- dedup preserved for every other pairing --------------------------------
def test_profit_take_does_not_preempt_and_is_deduped():
    fake = _fake_self([_resting(post_only=True)])
    _submit(fake, reason="tier 1", tier_fired=1, profit_take=True)
    assert fake._cancels == [], "a profit-take must never preempt"
    assert fake._captured == {}, "and must be deduped against the live take"


def test_risk_off_does_not_duplicate_a_live_marketable_escape():
    # a marketable risk-off exit already resting IS the escape; a second
    # risk-off exit must not cancel/duplicate it — the ladder re-attempts on
    # expiry. (post_only=False -> not preemptable.)
    fake = _fake_self([_resting(post_only=False)])
    _submit(fake, reason="hard stop", tier_fired=0, profit_take=False)
    assert fake._cancels == []
    assert fake._captured == {}


# --- the cancel primitive on a real dry-run OrderManager --------------------
def test_cancel_order_terminates_and_removes_from_open():
    om = OrderManager(feed=None, config={}, dry_run=True)
    o = _resting(post_only=True)
    om._orders[o.order_id] = o
    assert o in om.open_orders()
    assert om.cancel_order(o, reason="preempted") is True
    assert o.status == "cancelled"
    assert o not in om.open_orders(), "a cancelled order is no longer live"
    # idempotent: cancelling a terminal order is a no-op, not an error
    assert om.cancel_order(o) is False


# --- escalation-ladder de-escalation: only a COMPLETED exit resets ----------
def _ladder_fill(order, fill_size, attempts):
    """Drive the REAL _handle_fill exit branch with a stub self (same idiom
    as the _submit_exit routing tests above)."""
    from execution.order_manager import FillEvent
    pos = Position(position_id="p1", symbol="ETH/USD", direction="long",
                   entry_price=100.0, size=1.0, original_size=1.0,
                   opened_at=datetime.now(timezone.utc))
    fake = SimpleNamespace(
        state=SimpleNamespace(get_position=lambda pid: pos,
                              record_fees=lambda f: None),
        capital=SimpleNamespace(
            record_realized_profit=lambda n, s, **kw: None,
            skim_trade=lambda n, s: None),
        _exit_attempts=dict(attempts), _pos_realized={},
        _ledger_fill=lambda *a, **k: None,   # record layer: no-op stub
        _px=lambda s, p: f"{p:.2f}",
        _finalize_position=lambda p, n, t: None,
    )
    main_mod.LiquidityBot._handle_fill(
        fake, FillEvent(order, fill_size, 101.0, final=False), now=0.0)
    return fake


def test_dribble_partial_fill_does_not_reset_the_ladder():
    """A 3% partial on a timed-out attempt used to wipe _exit_attempts, so
    the ladder never widened its slippage cap nor reached the market rung —
    exactly the dislocated-book case it exists for."""
    o = _resting(post_only=False)
    o.filled = 0.03                            # dribble: remaining 0.97
    fake = _ladder_fill(o, fill_size=0.03, attempts={"p1": 2})
    assert fake._exit_attempts == {"p1": 2}, \
        "partial fill must keep the escalation counter"


def test_completed_exit_resets_the_ladder():
    o = _resting(post_only=False)
    o.filled = 1.0                             # this exit order COMPLETED
    fake = _ladder_fill(o, fill_size=0.97, attempts={"p1": 2})
    assert fake._exit_attempts == {}, "a completed exit de-escalates"
