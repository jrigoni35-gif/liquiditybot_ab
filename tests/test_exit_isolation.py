"""tests/test_exit_isolation.py — one bad position must never starve the rest
of the book's hard stops (invariant #5: an escape is never blocked).

The fast-cycle stop/tier loop used to run every open position in one
unguarded `for`. A single position whose evaluation deterministically raised
(a corrupt stop_price, a bad vol.state, a tier-engine edge) propagated out of
the loop, so EVERY position ordered after it never got its hard stop submitted
— indefinitely, while the process looked healthy. Now each position is
isolated: a raise is counted (_exit_eval_failures) and logged, and the next
position is still managed.
"""
import types
from datetime import datetime, timezone

from core.state import PortfolioState, Position
from main import LiquidityBot

PAIR = "XETHZUSD"


def _noop(*a, **k):
    return None


def _bot():
    b = LiquidityBot.__new__(LiquidityBot)
    b.dry_run = True
    b._halted = False
    b.symbol_map = {"ETH": "ETH/USD"}
    b._pair_of = {"ETH": PAIR}
    b._pair_list = [PAIR]
    b.marks, b._mark_ts, b._stop_ok, b.book_ts, b.kraken_books = {}, {}, {}, {}, {}
    b.last_signals = {}
    b._stop_hit = {}
    b._mark_stale_sec = 20.0
    b._exit_eval_failures = 0
    b.state = PortfolioState(starting_capital=10_000.0)

    b.watchdog = types.SimpleNamespace(
        evaluate=_noop,
        filter_mark=lambda asset, px: (px, True))   # confirmed, stop_ok
    b.kraken = types.SimpleNamespace(
        get_tickers=lambda pairs: {PAIR: 1900.0},    # ETH mark 1900
        get_order_book=lambda pair: {"bids": [[1899.5, 1.0]],
                                     "asks": [[1900.5, 1.0]]},
        kraken_pair=lambda s: PAIR)
    b.kraken_ws = None
    b.thales = types.SimpleNamespace(observe_feed_health=_noop, observe_fast=_noop)
    b._step_exec_algos = _noop
    b._apply_sim = _noop
    b._handle_fill = _noop
    b._equity = lambda: 10_000.0
    b.orders = types.SimpleNamespace(poll=lambda *a, **k: [],
                                     open_orders=lambda: [],
                                     has_open=lambda *a, **k: False)
    b.store = types.SimpleNamespace(snapshot=_noop)
    b.vol = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(sigma_bar_pct=0.5))
    b.fv = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(fair_value=1900.0))
    b.macro = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(playbook={"tier_scale": 1.0}))
    b.inventory = types.SimpleNamespace(
        inventory_ratio=lambda *a, **k: 0.0, soft_cap_pct=50.0,
        hard_cap_pct=100.0, derisk_actions=lambda *a, **k: [])
    b.hedger = types.SimpleNamespace(evaluate=lambda *a, **k: [])
    b.corr = types.SimpleNamespace(state=None)
    b.postmortem = types.SimpleNamespace(record_marks=_noop, poll=lambda now: [])
    b.risk_protocols = types.SimpleNamespace(observe=_noop)
    b.monitor = types.SimpleNamespace(record_close=_noop)
    b.capital = types.SimpleNamespace(hard_stop_triggered=lambda *a, **k: False)
    b._tier_engine = lambda scale: types.SimpleNamespace(
        evaluate=lambda *a, **k: types.SimpleNamespace(
            should_close_partial=False, close_pct=0.0, tier_fired=0,
            is_profit_take=False))
    b._px = lambda s, p: f"{p:.2f}"
    return b


def _add_pos(b, pid, stop):
    p = Position(pid, "ETH/USD", "long", 2000.0, 1.0, 1.0,
                 datetime.now(timezone.utc))
    p.stop_price = stop          # 1900 mark is below -> stop triggers
    p.tier_closed = 0
    b.state.add_position(p)


def test_raising_position_does_not_starve_the_next_ones_stop():
    b = _bot()
    _add_pos(b, "bad", 1950.0)    # ordered FIRST, its exit submit will raise
    _add_pos(b, "good", 1940.0)   # ordered SECOND, must still be flattened

    exits = []

    def submit(pos, pct, reason, **k):
        if pos.position_id == "bad":
            raise RuntimeError("simulated corrupt-position blow-up")
        exits.append((pos.position_id, pct, reason))
    b._submit_exit = submit

    b.fast_cycle(1000.0)

    # the bad position raised, but the good one's hard stop still fired
    assert [e[0] for e in exits] == ["good"], \
        "a raising position must not starve the next position's stop"
    assert b._exit_eval_failures == 1        # the failure is counted/visible


def test_all_positions_managed_when_none_raise():
    b = _bot()
    _add_pos(b, "p1", 1950.0)
    _add_pos(b, "p2", 1940.0)
    exits = []
    b._submit_exit = lambda pos, pct, reason, **k: exits.append(pos.position_id)
    b.fast_cycle(1000.0)
    assert sorted(exits) == ["p1", "p2"] and b._exit_eval_failures == 0
