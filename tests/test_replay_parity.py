"""tests/test_replay_parity.py — W2-18: wall-clock seeds break replay parity.

Two independent clocks were seeded from time.time() at construction/record
time instead of the caller's own injected `now`, so anything replaying
historical data (a backtest, a determinism-gate replay - see
execution/replay_gate.py) with a `now` far from the real wall clock got
nonsense elapsed-time math:

(a) main.py `_last_entry_admit_ts` (the ML-073 drought clock) was seeded
    with time.time() at __init__. Under replay, `now - _last_entry_admit_ts`
    (main.py's `_maybe_realize_mature_label`) goes wildly negative (real
    wall-clock epoch is almost always far ahead of a historical replay
    `now`), so the drought fastpath can never arm.

(b) ml/monitor.py `record_close` stamped `_last_cause_ts = time.time()`
    while `decay_stale_causes(now)` compares against the caller's injected
    `now` - under replay the two clocks never converge, so stale-cause
    decay (built specifically to avoid a cost_overrun-bump deadlock) never
    fires.
"""
import types

from core.state import PortfolioState
from ml.monitor import ModelMonitor
from main import LiquidityBot

PAIR = "XETHZUSD"


def _noop(*a, **k):
    return None


def _bot():
    """Minimal fast_cycle-drivable bot, no open positions (isolates the
    drought-clock seed from the rest of the per-position machinery)."""
    b = LiquidityBot.__new__(LiquidityBot)
    b.dry_run = True
    b._halted = False
    b.entries_enabled = True
    b.config = {}
    b.symbol_map = {"ETH": "ETH/USD"}
    b._pair_of = {"ETH": PAIR}
    b._pair_list = [PAIR]
    b.marks, b._mark_ts, b._stop_ok, b.book_ts, b.kraken_books = {}, {}, {}, {}, {}
    b.last_signals = {}
    b._stop_hit = {}
    b._mark_stale_sec = 20.0
    b._exit_eval_failures = 0
    b.state = PortfolioState(starting_capital=10_000.0)
    b._last_entry_admit_ts = None      # freshly constructed (post-fix __init__)

    b.watchdog = types.SimpleNamespace(
        evaluate=_noop, filter_mark=lambda a, px: (px, True))
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
    b.monitor = types.SimpleNamespace(record_close=_noop, decay_stale_causes=_noop)
    b.inventory = types.SimpleNamespace(
        inventory_ratio=lambda *a, **k: 0.0, soft_cap_pct=50.0,
        hard_cap_pct=100.0, derisk_actions=lambda *a, **k: [])
    b.hedger = types.SimpleNamespace(evaluate=lambda *a, **k: [])
    b.postmortem = types.SimpleNamespace(record_marks=_noop, poll=lambda now: [])
    b.markout = types.SimpleNamespace(poll=_noop, record_fill=_noop,
                                      snapshot=lambda: {})
    b.risk_protocols = types.SimpleNamespace(observe=_noop)
    b.capital = types.SimpleNamespace(hard_stop_triggered=lambda *a, **k: False,
                                      weekly_rollover=lambda *a, **k: 0.0)
    return b


# --- (a) the drought clock must seed from the replay's own injected now ----
def test_drought_clock_seeds_from_first_injected_now_not_wall_clock():
    b = _bot()
    historical_now = 1_000.0    # a replay clock, decoupled from wall time

    b.fast_cycle(historical_now)

    assert b._last_entry_admit_ts == historical_now, \
        "the ML-073 drought clock must lazily seed from the first " \
        "injected now (fast_cycle), not time.time() sampled at __init__ - " \
        "under replay the real wall clock is almost always far ahead of " \
        "the historical now, driving drought_h wildly negative"


def test_drought_clock_seed_is_lazy_once_not_reseeded_every_cycle():
    b = _bot()
    b._last_entry_admit_ts = 5_000.0     # already seeded (restore, or prior cycle)

    b.fast_cycle(9_000.0)

    assert b._last_entry_admit_ts == 5_000.0, \
        "an already-seeded drought clock must not be clobbered by a " \
        "later cycle's now - only the FIRST unseeded cycle seeds it"


# --- (b) monitor.record_close must stamp the caller's injected now --------
def test_record_close_stamps_the_callers_injected_now():
    mon = ModelMonitor({"cause_stale_hours": 4.0})
    historical_now = 1_000.0

    mon.record_close(0.6, 0, True, cause="cost_overrun", now=historical_now)

    assert mon._last_cause_ts == historical_now, \
        "record_close must stamp the now the caller already has, not " \
        "time.time() sampled inside record_close"


def test_decay_fires_on_the_replay_clock_not_the_wall_clock():
    mon = ModelMonitor({"cause_stale_hours": 4.0})
    historical_now = 1_000.0
    for i in range(6):
        mon.record_close(0.6, 0, True, cause="cost_overrun",
                         now=historical_now + i)
    assert mon.edge_ratio_bump > 0
    bump0, win0 = mon.edge_ratio_bump, len(mon._causes_window)

    # the REPLAY clock advances 5h past the last close -> must decay, even
    # though real wall-clock time has barely moved
    mon.decay_stale_causes(historical_now + 5 + 5 * 3600)

    assert mon.edge_ratio_bump < bump0, \
        "decay_stale_causes must key off the now the caller already has - " \
        "under replay, time.time() sampled inside record_close never " \
        "converges with the historical now decay compares against, so " \
        "the deadlock-prevention decay never fires"
    assert len(mon._causes_window) == win0 - 1
