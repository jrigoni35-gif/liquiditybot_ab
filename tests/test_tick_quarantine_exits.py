"""tests/test_tick_quarantine_exits.py — a fat-finger print must not reach the
EXIT-decision paths, only the hard stop.

The tick quarantine (core/watchdog.filter_mark) holds stop evaluation for one
cycle when a mark jumps more than tick_jump_quarantine_pct, so a single
anomalous print can't fire a stop. But `filter_mark` still RETURNS the anomalous
mark (for divergence reporting), and main.fast_cycle writes it into self.marks.
Before this fix only the hard protective stop consulted the `stop_ok` flag —
the profit-tier engine (trailing / chandelier / give-back), the equity peak
ratchet, the catastrophe hard-stop and inventory derisk all consumed the poison
mark, which:
  * ratcheted pos.high_water to a fabricated peak (PERSISTED — biases every
    future give-back/chandelier decision), and
  * fabricated a give-back / exit-floor close at a price that never held.

These drive main.fast_cycle through a real Watchdog with an injected feed:
seed a clean mark, inject one fat-finger tick (quarantined), then a reversal
back inside the band (outlier discarded). The exit paths must stay inert on the
quarantined cycle and resume on the confirmed/discarded one.
"""
import json
import types
from datetime import datetime, timezone
from pathlib import Path

from core.state import PortfolioState, Position
from core.watchdog import Watchdog
from main import LiquidityBot

_CFG = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                  .read_text(encoding="utf-8"))

PAIR = "XETHZUSD"


def _noop(*a, **k):
    return None


def _bot_with_long(high_water=2100.0, stop=2080.0, tier_closed=4):
    """A LiquidityBot shell wired for fast_cycle over ONE long ETH position,
    with a real Watchdog + real ProfitTierEngine and every other collaborator
    stubbed. _submit_exit is replaced by a recorder so a fabricated exit is
    observable. Marks are injected via kraken.get_tickers (a per-cycle feed)."""
    b = LiquidityBot.__new__(LiquidityBot)
    b.dry_run = True
    b._halted = False
    b.symbol_map = {"ETH": "ETH/USD"}
    b._pair_of = {"ETH": PAIR}
    b._pair_list = [PAIR]
    b.marks, b._mark_ts, b._stop_ok, b.book_ts, b.kraken_books = {}, {}, {}, {}, {}
    b.last_signals = {}
    b._mark_stale_sec = 20.0

    st = PortfolioState(starting_capital=10_000.0)
    pos = Position("eth1", "ETH/USD", "long", 2000.0, 1.0, 1.0,
                   datetime.now(timezone.utc))
    pos.high_water = high_water
    pos.trailing_stop_price = stop
    pos.stop_price = None                    # path-1 hard protective stop off
    pos.tier_closed = tier_closed            # no fresh tier — exercise the floor
    st.add_position(pos)
    b.state = st
    b.pos = pos

    # real quarantine, but skip the sentry's heavier evaluate()
    b.watchdog = Watchdog({"enabled": True, "tick_jump_quarantine_pct": 8.0})
    b.watchdog.evaluate = _noop

    # per-cycle injected feed
    feed = {"v": None}
    b._feed = feed
    b.kraken = types.SimpleNamespace(
        get_tickers=lambda pairs: ({PAIR: feed["v"]} if feed["v"] else {}),
        get_order_book=lambda pair: {"bids": [[feed["v"], 1.0]],
                                     "asks": [[feed["v"], 1.0]]},
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

    # real tier engine, real config
    b.tiers_base = _CFG.get("profit_taking", {})
    b._tier_engines = {}

    # record fabricated exits instead of routing a real order
    b.exits = []
    b._submit_exit = lambda pos, pct, reason, **k: b.exits.append(
        (pos.position_id, pct, reason))
    return b


def _run(b, mark, now):
    b._feed["v"] = mark
    b.fast_cycle(now)


def test_downward_fat_finger_does_not_fabricate_a_giveback_exit():
    b = _bot_with_long(high_water=2100.0, stop=2080.0)
    _run(b, 2095.0, 1000.0)          # seed a clean mark (2095 > stop, no exit)
    assert b.exits == [], "clean seed cycle must not exit"
    stop_before = b.pos.trailing_stop_price
    _run(b, 1900.0, 1005.0)          # fat-finger DOWN -9.3% -> quarantined
    assert b._stop_ok["ETH"] is False, "a >8% jump must quarantine the tick"
    assert b.exits == [], ("quarantined fat-finger must NOT fire the exit floor "
                           "(pre-fix: 1900 <= trailing stop -> fabricated close)")
    assert b.pos.trailing_stop_price == stop_before, "stop unchanged while quarantined"
    _run(b, 2095.0, 1010.0)          # reversal inside band -> outlier discarded
    assert b._stop_ok["ETH"] is True
    assert b.exits == [], "discarded outlier leaves the position open"


def test_upward_fat_finger_does_not_corrupt_persisted_high_water():
    b = _bot_with_long(high_water=2100.0, stop=2080.0)
    _run(b, 2095.0, 1000.0)          # seed
    peak_before = b.state._equity_high_water
    _run(b, 2300.0, 1005.0)          # fat-finger UP +9.8% -> quarantined
    assert b._stop_ok["ETH"] is False
    assert b.pos.high_water == 2100.0, ("quarantined spike must NOT ratchet the "
                                        "persisted chandelier anchor")
    assert b.state._equity_high_water == peak_before, ("quarantined spike must "
                                                       "NOT ratchet the equity peak")
    _run(b, 2095.0, 1010.0)          # reversal -> discarded
    assert b.pos.high_water == 2100.0


def test_confirmed_move_lets_the_exit_fire_next_cycle():
    # symmetry: the quarantine only DEFERS — a real move confirmed on the next
    # tick fires the exit floor (one cycle late), it does not suppress it.
    b = _bot_with_long(high_water=2100.0, stop=2080.0)
    _run(b, 2095.0, 1000.0)          # seed
    _run(b, 1900.0, 1005.0)          # jump DOWN -> quarantined, no exit
    assert b.exits == []
    _run(b, 1850.0, 1010.0)          # same-direction confirmation -> stops live
    assert b._stop_ok["ETH"] is True
    assert any(pid == "eth1" for pid, _, _ in b.exits), \
        "a CONFIRMED adverse move must fire the exit floor (deferred, not denied)"
