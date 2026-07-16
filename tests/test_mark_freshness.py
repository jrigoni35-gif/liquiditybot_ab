"""tests/test_mark_freshness.py — the exit/risk hot path runs on a TRUSTED mark.

Two guarantees:
  * a silently-stalled ticker on a still-live book no longer FREEZES the mark:
    fast_cycle refreshes it from the fresh book mid, so stops/exits keep running
    on a current price (and the watchdog, which reads book_ts, stays consistent);
  * when a symbol's feed goes fully dark (neither ticker nor book refreshes the
    mark within mark_stale_sec), the NON-ESCAPE actions (profit tiers, inventory
    derisk, equity-peak/hard-stop) defer rather than fabricate an exit off a
    frozen price — but the per-position protective stop (an ESCAPE) still runs.
"""
import types
from datetime import datetime, timezone

from core.state import PortfolioState, Position
from core.watchdog import Watchdog
from main import LiquidityBot

PAIR = "XETHZUSD"


def _noop(*a, **k):
    return None


def _bot(stop_price=None, tier_closed=4):
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

    st = PortfolioState(starting_capital=10_000.0)
    pos = Position("eth1", "ETH/USD", "long", 2000.0, 1.0, 1.0,
                   datetime.now(timezone.utc))
    pos.high_water = 2100.0
    pos.trailing_stop_price = 2080.0
    pos.stop_price = stop_price
    pos.tier_closed = tier_closed
    st.add_position(pos)
    b.state = st
    b.pos = pos

    b.watchdog = Watchdog({"enabled": True, "tick_jump_quarantine_pct": 8.0})
    b.watchdog.evaluate = _noop

    b._ticker = {"v": None}       # None -> ticker returns no price
    b._book = {"v": None}         # None -> book fetch returns nothing
    b.kraken = types.SimpleNamespace(
        get_tickers=lambda pairs: ({PAIR: b._ticker["v"]} if b._ticker["v"]
                                   else {}),
        get_order_book=lambda pair: b._book["v"],
        kraken_pair=lambda s: PAIR)
    b.kraken_ws = None

    b.thales = types.SimpleNamespace(observe_feed_health=_noop, observe_fast=_noop)
    b._step_exec_algos = _noop
    b._apply_sim = _noop
    b.orders = types.SimpleNamespace(poll=lambda *a, **k: [],
                                     open_orders=lambda: [],
                                     has_open=lambda *a, **k: False)
    b.store = types.SimpleNamespace(snapshot=_noop)
    b.vol = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(sigma_bar_pct=0.5))
    b.fv = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(fair_value=2000.0))
    b.macro = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(
            playbook={"tier_scale": 1.0}, is_counter_trend=lambda d: False))
    b.inventory = types.SimpleNamespace(
        inventory_ratio=lambda *a, **k: 0.0, soft_cap_pct=50.0,
        hard_cap_pct=100.0, derisk_actions=lambda *a, **k: [])
    b.hedger = types.SimpleNamespace(evaluate=lambda *a, **k: [])
    b.corr = types.SimpleNamespace(state=None)
    b.postmortem = types.SimpleNamespace(record_marks=_noop, poll=lambda now: [])
    b.markout = types.SimpleNamespace(poll=_noop, record_fill=_noop,
                                      snapshot=lambda: {})
    b.risk_protocols = types.SimpleNamespace(observe=_noop)
    b.monitor = types.SimpleNamespace(record_close=_noop)
    b.capital = types.SimpleNamespace(hard_stop_triggered=lambda *a, **k: False)

    # tier-engine SPY: records whether the gate let the engine be consulted
    b._tier_calls = []
    spy = types.SimpleNamespace(evaluate=lambda *a, **k: (
        b._tier_calls.append(1),
        types.SimpleNamespace(should_close_partial=False, close_pct=0.0,
                              tier_fired=0, is_profit_take=False))[1])
    b._tier_engine = lambda scale: spy

    b.exits = []
    b._submit_exit = lambda pos, pct, reason, **k: b.exits.append(
        (pos.position_id, pct, reason))
    b._px = lambda s, p: f"{p:.2f}"
    return b


def _book(mid):
    return {"bids": [[mid - 0.5, 1.0]], "asks": [[mid + 0.5, 1.0]]}


# --- _mark_fresh helper -----------------------------------------------------
def test_mark_fresh_helper():
    b = _bot()
    b._mark_ts = {"ETH/USD": 1000.0}
    assert b._mark_fresh("ETH/USD", 1015.0) is True      # 15s < 20s
    assert b._mark_fresh("ETH/USD", 1030.0) is False     # 30s > 20s
    assert b._mark_fresh("SOL/USD", 1000.0) is False     # never stamped


# --- (A) book-mid fallback keeps the mark fresh when the ticker stalls -------
def test_book_mid_refreshes_a_stalled_ticker():
    b = _bot()
    b._ticker["v"] = None            # ticker returns NO price
    b._book["v"] = _book(2000.0)     # but the book is live
    b.fast_cycle(1000.0)
    assert b.marks["ETH/USD"] == 2000.0            # mark = book mid, not frozen
    assert b._mark_ts["ETH/USD"] == 1000.0         # stamped fresh
    assert b._stop_ok.get("ETH") is True


# --- (B) a fully-dark feed defers non-escape actions ------------------------
def test_stale_mark_defers_the_tier_engine():
    b = _bot(stop_price=None)
    b._ticker["v"] = 2095.0
    b._book["v"] = _book(2095.0)
    b.fast_cycle(1000.0)                            # fresh: tier consulted
    assert len(b._tier_calls) == 1
    # feed goes dark 30s later; mark cannot refresh -> stale
    b._ticker["v"] = None
    b._book["v"] = None
    b.fast_cycle(1030.0)
    assert len(b._tier_calls) == 1, "a stale mark must NOT consult the tier engine"
    assert b.exits == []
    # feed returns -> fresh again -> tier consulted once more
    b._ticker["v"] = 2095.0
    b._book["v"] = _book(2095.0)
    b.fast_cycle(1035.0)
    assert len(b._tier_calls) == 2


def test_protective_stop_still_fires_on_a_stale_mark():
    # the ESCAPE is never gated on freshness: a frozen mark already below the
    # protective stop must still trigger it
    b = _bot(stop_price=1950.0)
    b.marks["ETH/USD"] = 1900.0                     # frozen, below the stop
    b._mark_ts["ETH/USD"] = 1000.0                  # stale
    b._stop_ok["ETH"] = True
    b._ticker["v"] = None                           # dark feed this cycle
    b._book["v"] = None
    b.fast_cycle(1030.0)                            # 30s later -> mark stale
    assert any(r.startswith("stop") for _, _, r in b.exits), \
        "protective stop (escape) must fire even on a stale mark"
