"""tests/test_exit_starvation.py — no pre-stop raise may starve the per-position
stop loop, and no bad fill may discard the rest of its batch (invariant #5:
disarm/faults/kill switches block NEW risk, never escapes).

Two starvation classes are pinned here, both distinct from the per-position
isolation already covered in test_exit_isolation:

W1-1  cycle_once runs hourly_cycle BEFORE fast_cycle and only advances
      _last_macro on success, so a DETERMINISTIC raise inside the hourly/slow
      refit (a poisoned cached candle in macro.update, a model-load edge) used
      to re-raise every cycle forever — fast_cycle's stop loop never ran again.
      The same class lives in fast_cycle's PRE-STOP segment: a raise in any of
      _step_exec_algos / orders.poll / watchdog.evaluate / postmortem.record_marks
      / markout.poll / risk_protocols.observe / the postmortem.poll close loop
      propagated out of fast_cycle ahead of the stop loop.

W1-2  orders.poll advances order state and drains deferred events before
      returning, so if _handle_fill raised on event i, events i+1..n were
      discarded (book/venue desync; a dry-run fill lost permanently) and the
      post-batch snapshot was skipped.
"""
import types
from datetime import datetime, timezone

from core.state import PortfolioState, Position
from main import LiquidityBot

PAIR = "XETHZUSD"


def _noop(*a, **k):
    return None


def _boom(*a, **k):
    raise RuntimeError("simulated deterministic blow-up")


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

    # --- cycle_once / hourly / slow scaffolding ---
    b._cycle = 0
    b._cycle_lifetime = 0
    b._last_macro = 0.0
    b.macro_refit_sec = 3600.0
    b.slow_every = 6
    b.slow_cycle = _noop
    b.daily_candles = {}
    b.config = {"exchanges": {"okx": {"symbols": []},
                              "binanceus": {"symbols": []}}}

    b.watchdog = types.SimpleNamespace(
        evaluate=_noop,
        filter_mark=lambda asset, px: (px, True))
    b.kraken = types.SimpleNamespace(
        get_tickers=lambda pairs: {PAIR: 1900.0},
        get_order_book=lambda pair: {"bids": [[1899.5, 1.0]],
                                     "asks": [[1900.5, 1.0]]},
        get_daily_candles=lambda pair: [],
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
        state=lambda a: types.SimpleNamespace(playbook={"tier_scale": 1.0}),
        update=_noop)
    b.corr = types.SimpleNamespace(
        state=types.SimpleNamespace(turbulence_pct=0.0), update_turbulence=_noop)
    b.monitor = types.SimpleNamespace(
        record_close=_noop, decay_stale_causes=_noop)
    b.inventory = types.SimpleNamespace(
        inventory_ratio=lambda *a, **k: 0.0, soft_cap_pct=50.0,
        hard_cap_pct=100.0, derisk_actions=lambda *a, **k: [])
    b.hedger = types.SimpleNamespace(evaluate=lambda *a, **k: [])
    b.postmortem = types.SimpleNamespace(record_marks=_noop, poll=lambda now: [])
    b.markout = types.SimpleNamespace(poll=_noop, record_fill=_noop,
                                      snapshot=lambda: {})
    b.risk_protocols = types.SimpleNamespace(observe=_noop)
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
    p.stop_price = stop          # 1900 mark below stop -> stop triggers
    p.tier_closed = 0
    b.state.add_position(p)


# --- W1-1 (a): a raise in the hourly/slow refit must not starve the stop loop -
def test_hourly_raise_does_not_starve_the_stop_loop():
    b = _bot()
    _add_pos(b, "p", 1950.0)             # stop 1950 > mark 1900 -> breached
    exits = []
    b._submit_exit = lambda pos, pct, reason, **k: exits.append(pos.position_id)

    calls = {"n": 0}

    def poisoned(*a, **k):
        calls["n"] += 1
        raise RuntimeError("poisoned cached candle in macro.update")
    b.macro.update = poisoned            # deterministic raise INSIDE hourly_cycle

    b.cycle_once(now=10_000.0)           # hourly fires (10000 - 0 >= 3600)

    assert exits == ["p"], \
        "a deterministic hourly raise must not starve the per-position stop loop"
    assert b._last_macro == 10_000.0, \
        "the cadence stamp must advance so a poisoned hour doesn't retry every cycle"
    assert calls["n"] == 1
    assert b._exit_eval_failures >= 1    # the isolated failure is counted/visible

    # a poisoned hour must not RE-RUN hourly (and re-raise) every cycle:
    b.cycle_once(now=10_000.0)
    assert calls["n"] == 1, "hourly must not retry until the macro interval elapses"
    assert exits == ["p", "p"], "the stop loop still runs the following cycle"


# --- W1-1 (b): a raise in ONE pre-stop fast_cycle stage must not starve exits -
def test_prestop_stage_raise_does_not_starve_the_stop_loop():
    b = _bot()
    _add_pos(b, "p", 1950.0)
    exits = []
    b._submit_exit = lambda pos, pct, reason, **k: exits.append(pos.position_id)
    b.markout.poll = _boom               # one pre-stop stage raises deterministically

    b.fast_cycle(1000.0)

    assert exits == ["p"], \
        "a pre-stop stage raise must not starve the per-position stop loop"
    assert b._exit_eval_failures >= 1


# --- W1-2: a raising fill must not discard the rest of the poll batch ---------
def test_one_raising_fill_does_not_discard_the_rest_of_the_batch():
    b = _bot()
    e1 = types.SimpleNamespace(tag="e1")
    e2 = types.SimpleNamespace(tag="e2")
    b.orders.poll = lambda *a, **k: [e1, e2]
    applied, snapped = [], []

    def handle(event, now=None):
        if event is e1:
            raise RuntimeError("bad fill blew up")
        applied.append(event.tag)
    b._handle_fill = handle
    b.store.snapshot = lambda *a, **k: snapped.append(True)

    b.fast_cycle(1000.0)

    assert applied == ["e2"], \
        "a raising fill must not discard the remaining fills in the batch"
    assert snapped == [True], "the post-batch snapshot must still run"
    assert b._exit_eval_failures >= 1


# --- W1-1: a slow-cycle raise is isolated; the heartbeat still advances -------
def test_slow_cycle_raise_is_isolated_and_heartbeat_advances():
    b = _bot()
    b._last_macro = 10_000.0             # hourly already fresh: skip it this call
    b.slow_cycle = _boom                 # slow_cycle (cycle 0, 0 % slow_every == 0)

    b.cycle_once(now=10_000.0)

    assert b._cycle == 1, \
        "a slow_cycle raise must not freeze the heartbeat (retry-starving slow work)"
    assert b._exit_eval_failures >= 1
