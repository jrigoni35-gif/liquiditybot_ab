"""tests/test_fault_wiring.py — the central FaultManager is no longer dead code.

It is constructed + armed by the engine, latched by the halt conditions
(catastrophe hard-stop, runner wedge), and its op-state gates NEW risk while
NEVER gating exits (invariant #5). These pin the wiring; core FaultManager
state-machine semantics live in test_review_round2.py.
"""
import types
from datetime import datetime, timezone

from core.fault import FaultManager, OpState, Severity
from core.state import PortfolioState, Position
from main import LiquidityBot
from runner import BotRunner

PAIR = "XETHZUSD"


def _noop(*a, **k):
    return None


# --- runner wedge latches the fault authority -------------------------------
def _wedge_runner(halt_at, with_fault=True):
    r = BotRunner.__new__(BotRunner)
    r._cycle_fail_streak = 0
    r._cycle_fail_halt = halt_at
    r._wedge_alerted = False
    fm = None
    if with_fault:
        fm = FaultManager()
        fm.arm()
    r.bot = types.SimpleNamespace(
        _halted=False, fault=fm,
        alerts=types.SimpleNamespace(fire=lambda *a, **k: None))
    return r, fm


def test_wedge_latches_fault_to_halted_but_never_blocks_exits():
    r, fm = _wedge_runner(halt_at=2)
    assert fm.allow_new_risk() is True         # armed
    r._note_cycle_failure()
    r._note_cycle_failure()                     # crosses the wedge threshold
    assert fm.state is OpState.HALTED
    assert fm.allow_new_risk() is False         # NEW risk refused
    assert fm.allow_exits() is True             # exits ALWAYS allowed
    assert "cycle_wedged" in fm.status()["faults"]
    assert r.bot._halted is True


def test_wedge_on_a_bot_without_a_fault_manager_still_halts():
    # an older/duck-typed bot without .fault must not crash the wedge path
    r, fm = _wedge_runner(halt_at=1, with_fault=False)
    r._note_cycle_failure()
    assert fm is None and r.bot._halted is True


# --- engine constructs + arms a fault manager -------------------------------
def test_fault_manager_gate_matches_op_state():
    # the exact new-risk gate the slow cycle uses, in isolation
    fm = FaultManager()
    fm.arm()
    halted = False
    assert not (halted or (fm is not None and not fm.allow_new_risk()))  # trades
    fm.latch("x", Severity.CRITICAL, "boom")
    assert (halted or (fm is not None and not fm.allow_new_risk()))       # blocked


# --- catastrophe hard-stop latches the fault authority (fast_cycle) ----------
def _fast_bot(hard_stop):
    b = LiquidityBot.__new__(LiquidityBot)
    b.dry_run = True
    b._halted = False
    b.symbol_map = {"ETH": "ETH/USD"}
    b._pair_of = {"ETH": PAIR}
    b._pair_list = [PAIR]
    b.marks, b._mark_ts, b._stop_ok, b.book_ts, b.kraken_books = {}, {}, {}, {}, {}
    b.last_signals, b._stop_hit = {}, {}
    b._mark_stale_sec = 20.0
    b._exit_eval_failures = 0
    b.state = PortfolioState(starting_capital=10_000.0)
    b.state.add_position(Position("p1", "ETH/USD", "long", 2000.0, 1.0, 1.0,
                                  datetime.now(timezone.utc)))
    b.fault = FaultManager()
    b.fault.arm()
    b.watchdog = types.SimpleNamespace(
        evaluate=_noop, filter_mark=lambda a, px: (px, True))
    b.kraken = types.SimpleNamespace(
        get_tickers=lambda pairs: {PAIR: 1900.0},
        get_order_book=lambda pair: {"bids": [[1899.5, 1.0]],
                                     "asks": [[1900.5, 1.0]]},
        kraken_pair=lambda s: PAIR)
    b.kraken_ws = None
    b.thales = types.SimpleNamespace(observe_feed_health=_noop, observe_fast=_noop)
    b._step_exec_algos = _noop
    b._apply_sim = _noop
    b._handle_fill = _noop
    b._equity = lambda: 8_000.0
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
    b.markout = types.SimpleNamespace(poll=_noop, record_fill=_noop,
                                      snapshot=lambda: {})
    b.risk_protocols = types.SimpleNamespace(observe=_noop)
    b.monitor = types.SimpleNamespace(record_close=_noop)
    b.capital = types.SimpleNamespace(
        hard_stop_triggered=lambda *a, **k: hard_stop)
    b.exits = []
    b._submit_exit = lambda pos, pct, reason, **k: b.exits.append(pos.position_id)
    b._px = lambda s, p: f"{p:.2f}"
    return b


def test_hard_stop_latches_fault_and_flattens():
    b = _fast_bot(hard_stop=True)
    b.fast_cycle(1000.0)
    assert b._halted is True
    assert b.fault.state is OpState.HALTED
    assert "hard_stop_drawdown" in b.fault.status()["faults"]
    assert b.exits == ["p1"]                     # flattened despite the halt
    assert b.fault.allow_exits() is True


def test_no_hard_stop_stays_armed():
    b = _fast_bot(hard_stop=False)
    b.fast_cycle(1000.0)
    assert b.fault.state is OpState.ARMED and b._halted is False
