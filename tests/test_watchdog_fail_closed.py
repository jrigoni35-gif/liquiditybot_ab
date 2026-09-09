"""tests/test_watchdog_fail_closed.py — W2-27: a raised watchdog.evaluate must
fail the ENTRIES side CLOSED, not open.

Wave-1 (f952497) isolated watchdog.evaluate in fast_cycle so a raise there
cannot starve the exit loop below it — correct, exits must never depend on
the watchdog succeeding. But the except-branch only counted/logged the
failure; `self.watchdog.state` (a fresh WatchdogState() built at the TOP of
evaluate(), only assigned to self.state at the very END) is never reassigned
on a raise, so every consumer of `watchdog.state.entries_blocked` —
_step_exec_algos, the hedge-open gate, and the main entry-scan hard return —
reads the FROZEN PRIOR value. If that prior value was False (the common
case: a healthy watchdog that then starts raising), entries proceed
unprotected during the one incident that breaks the watchdog itself.

The hedge-open gate is the sharpest same-cycle repro: `_run_hedge_pass` runs
AFTER the watchdog.evaluate try/except within the SAME fast_cycle() call
(main.py order: _step_exec_algos -> ... -> watchdog.evaluate -> ... ->
_run_hedge_pass), so it observes whatever the raise leaves behind THIS
cycle, not a stale prior-cycle read.
"""
import types
from datetime import datetime, timezone

from core.state import PortfolioState, Position
from core.watchdog import Watchdog
from execution.hedging import HedgeEngine
from main import LiquidityBot

PAIR_ETH = "XETHZUSD"
PAIR_BTC = "XXBTZUSD"
NOW = 1_000_000.0


class _FakeCorr:
    """Correlation feed test double — NOT the hedger under test. Fixed
    corr/beta keep the real HedgeEngine's math deterministic."""

    def corr(self, a, b):
        return 0.9

    def beta(self, a, b):
        return 1.0


def _noop(*a, **k):
    return None


def _boom(*a, **k):
    raise RuntimeError("watchdog.evaluate blew up (simulated infra fault)")


def _bot():
    """A fast_cycle-drivable bot with one large signal-side ETH long: net
    delta breaches the 20%-of-equity hedge cap (same trigger as
    test_hedge_gating.py's _open_triggering_state), so the real HedgeEngine
    emits an "open" BTC hedge action every cycle unless a new-risk gate
    blocks it."""
    b = LiquidityBot.__new__(LiquidityBot)
    b.dry_run = True
    b.live_armed = False
    b._live_block_logged = 0.0
    b._halted = False
    b.entries_enabled = True
    b.max_slip_pct = 0.5
    b.symbol_map = {"ETH": "ETH/USD", "BTC": "BTC/USD"}
    b._pair_of = {"ETH": PAIR_ETH, "BTC": PAIR_BTC}
    b._pair_list = [PAIR_ETH, PAIR_BTC]
    b.marks = {"ETH/USD": 2000.0, "BTC/USD": 30_000.0}
    b._mark_ts = {"ETH/USD": NOW, "BTC/USD": NOW}
    b._stop_ok = {"ETH": True, "BTC": True}
    b.book_ts = {"ETH": NOW, "BTC": NOW}
    b.kraken_books = {
        "ETH": {"bids": [[1999.5, 1.0]], "asks": [[2000.5, 1.0]]},
        "BTC": {"bids": [[29_999.5, 1.0]], "asks": [[30_000.5, 1.0]]},
    }
    b.last_signals = {}
    b._stop_hit = {}
    b._mark_stale_sec = 20.0
    b._exit_eval_failures = 0
    b.config = {}
    b._last_entry_admit_ts = NOW

    b.state = PortfolioState(starting_capital=10_000.0)
    pos = Position("eth1", "ETH/USD", "long", 2000.0, 2.5, 2.5,
                   datetime.now(timezone.utc))
    pos.stop_price = None          # never trips a stop; isolates the hedge gate
    pos.tier_closed = 0
    b.state.add_position(pos)

    b.watchdog = Watchdog({"enabled": True, "tick_jump_quarantine_pct": 8.0})

    b.kraken = types.SimpleNamespace(
        get_tickers=lambda pairs: {PAIR_ETH: 2000.0, PAIR_BTC: 30_000.0},
        get_order_book=lambda pair: (
            {"bids": [[1999.5, 1.0]], "asks": [[2000.5, 1.0]]}
            if pair == PAIR_ETH else
            {"bids": [[29_999.5, 1.0]], "asks": [[30_000.5, 1.0]]}),
        get_daily_candles=lambda pair: [],
        kraken_pair=lambda s: PAIR_BTC if "BTC" in s else PAIR_ETH)
    b.kraken_ws = None
    b.thales = types.SimpleNamespace(observe_feed_health=_noop, observe_fast=_noop)
    b._step_exec_algos = _noop
    b._apply_sim = _noop
    b._handle_fill = _noop
    b._equity = lambda: 10_000.0
    b.hedge_submits = []
    b.orders = types.SimpleNamespace(
        poll=lambda *a, **k: [], open_orders=lambda: [],
        has_open=lambda *a, **k: False,
        submit=lambda **kw: b.hedge_submits.append(kw))
    b.store = types.SimpleNamespace(snapshot=_noop)
    b.vol = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(sigma_bar_pct=0.5))
    b.fv = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(
            fair_value=2000.0 if a == "ETH" else 30_000.0))
    b.macro = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(playbook={"tier_scale": 1.0}),
        update=_noop)
    b.corr = types.SimpleNamespace(state=_FakeCorr(), update_turbulence=_noop)
    b.monitor = types.SimpleNamespace(record_close=_noop, decay_stale_causes=_noop)
    b.inventory = types.SimpleNamespace(
        inventory_ratio=lambda *a, **k: 0.0, soft_cap_pct=50.0,
        hard_cap_pct=100.0, derisk_actions=lambda *a, **k: [])
    b.hedger = HedgeEngine({"enabled": True}, b.symbol_map)       # REAL engine, not stubbed
    b.postmortem = types.SimpleNamespace(record_marks=_noop, poll=lambda now: [])
    b.markout = types.SimpleNamespace(poll=_noop, record_fill=_noop,
                                      snapshot=lambda: {})
    b.risk_protocols = types.SimpleNamespace(observe=_noop)
    b.capital = types.SimpleNamespace(hard_stop_triggered=lambda *a, **k: False,
                                      weekly_rollover=lambda *a, **k: 0.0)
    b._tier_engine = lambda scale: types.SimpleNamespace(
        evaluate=lambda *a, **k: types.SimpleNamespace(
            should_close_partial=False, close_pct=0.0, tier_fired=0,
            is_profit_take=False))
    b._px = lambda s, p: f"{p:.2f}"
    return b


# --- sanity: confirm the trigger actually opens a hedge absent any fault ----
def test_sanity_fresh_watchdog_still_opens_the_hedge():
    b = _bot()
    b.fast_cycle(NOW)
    assert len(b.hedge_submits) == 1, \
        "sanity check: the triggering position must open a hedge when " \
        "nothing is wrong"


# --- W2-27: a raising watchdog.evaluate must block entries THIS cycle ------
def test_watchdog_raise_blocks_hedge_open_in_the_same_cycle():
    b = _bot()
    assert b.watchdog.state.entries_blocked is False    # prior state: healthy
    b.watchdog.evaluate = _boom                         # now raises deterministically

    b.fast_cycle(NOW)

    assert b.hedge_submits == [], \
        "a raised watchdog.evaluate must fail entries CLOSED this cycle, " \
        "not proceed on the frozen prior entries_blocked=False"
    assert b._exit_eval_failures >= 1                   # isolation still counted it


def test_watchdog_raise_forces_entries_blocked_state():
    b = _bot()
    b.watchdog.evaluate = _boom

    b.fast_cycle(NOW)

    assert b.watchdog.state.entries_blocked is True, \
        "the isolation except-branch must force the effective " \
        "entries-blocked posture when evaluate() itself raised"


# --- exits stay untouched: the fix must not gate risk-reduction ------------
def test_watchdog_raise_does_not_block_hedge_unwind():
    b = _bot()
    # zero signal-side exposure + a held hedge -> HedgeEngine emits "unwind"
    b.state = PortfolioState(starting_capital=10_000.0)
    hedge = Position("hedge1", "BTC/USD", "short", 30_000.0, 0.2, 0.2,
                     datetime.now(timezone.utc))
    hedge.is_hedge = True
    hedge.stop_price = None
    b.state.add_position(hedge)
    exits = []
    b._submit_exit = lambda pos, pct, reason, **k: exits.append(pos.position_id)
    b.watchdog.evaluate = _boom

    b.fast_cycle(NOW)

    assert exits and exits[0] == "hedge1", \
        "hedge unwind is risk REDUCTION (invariant #5) - must never be " \
        "gated by a watchdog failure"


# --- recovery: once evaluate succeeds again, the block lifts ---------------
def test_watchdog_recovery_unblocks_entries_next_cycle():
    b = _bot()
    b.watchdog.evaluate = _boom
    b.fast_cycle(NOW)
    assert b.hedge_submits == []

    b.watchdog.evaluate = Watchdog.evaluate.__get__(b.watchdog, Watchdog)
    b.fast_cycle(NOW + 1.0)

    assert len(b.hedge_submits) == 1, \
        "once evaluate() succeeds again and computes a fresh healthy " \
        "state, the forced block must lift"
