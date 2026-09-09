"""tests/test_hedge_gating.py — hedge OPEN orders are new risk (W1-5).

`_hedge_actions`' "open" branch priced off `self.marks`/`self.kraken_books`
with NO freshness gate and NO new-risk authority check (entries_enabled,
watchdog.entries_blocked, fault manager, halt) — unlike every other
risk-adding path (entries, tier exits' trusted-mark gate, derisk, equity
ratchet). A frozen feed or a latched halt could still push a live hedge
open at stale-touch pricing mid-incident.

Unwind/trim are risk REDUCTION (invariant #5: escapes are never gated) and
must stay unaffected by every one of these gates.

Uses the REAL execution.hedging.HedgeEngine (not stubbed) so the "open"
and "unwind" HedgeActions driving each case are genuine engine output,
not a rigged test double.
"""
import types
from datetime import datetime, timezone

from core.state import PortfolioState, Position
from core.watchdog import Watchdog
from execution.hedging import HedgeEngine
from main import LiquidityBot

PAIR_BTC = "XXBTZUSD"
NOW = 1_000_000.0


class _FakeCorr:
    """Correlation feed test double — NOT the hedger under test. Fixed
    corr/beta keep the hedge-engine math (which IS real) deterministic."""

    def corr(self, a, b):
        return 0.9

    def beta(self, a, b):
        return 1.0


def _noop(*a, **k):
    return None


def _open_triggering_state():
    """One large signal-side ETH long: net delta (5,000) breaches the
    20%-of-equity cap (2,000 on 10k equity) -> real HedgeEngine emits an
    "open" BTC hedge action."""
    st = PortfolioState(starting_capital=10_000.0)
    st.add_position(Position("eth1", "ETH/USD", "long", 2000.0, 2.5, 2.5,
                             datetime.now(timezone.utc)))
    return st


def _unwind_triggering_state():
    """A held BTC hedge with zero signal-side exposure: signal net delta is
    0, inside the rebalance band -> real HedgeEngine emits an "unwind"."""
    st = PortfolioState(starting_capital=10_000.0)
    hedge = Position("hedge1", "BTC/USD", "short", 30_000.0, 0.2, 0.2,
                     datetime.now(timezone.utc))
    hedge.is_hedge = True
    st.add_position(hedge)
    return st


def _bot(state, entries_enabled=True, halted=False):
    b = LiquidityBot.__new__(LiquidityBot)
    b.dry_run = True                # dry run: isolates the gate under test
    b.live_armed = False            # from the live-arm gate (both bypassed
    b._live_block_logged = 0.0      # identically by dry_run today)
    b._halted = halted
    b.entries_enabled = entries_enabled
    b.symbol_map = {"BTC": "BTC/USD", "ETH": "ETH/USD"}
    b._mark_stale_sec = 20.0
    b.marks = {"ETH/USD": 2000.0, "BTC/USD": 30_000.0}
    b._mark_ts = {"ETH/USD": NOW, "BTC/USD": NOW}
    b._stop_ok = {"ETH": True, "BTC": True}
    b.kraken_books = {"BTC": {"bids": [[29_999.5, 1.0]],
                              "asks": [[30_000.5, 1.0]]}}
    b.kraken = types.SimpleNamespace(kraken_pair=lambda s: PAIR_BTC)
    b.vol = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(sigma_bar_pct=0.5))
    b.max_slip_pct = 0.5
    b.watchdog = Watchdog({"enabled": True, "tick_jump_quarantine_pct": 8.0})

    b.state = state
    b.hedger = HedgeEngine({"enabled": True}, b.symbol_map)     # REAL engine, not stubbed
    b.corr = types.SimpleNamespace(state=_FakeCorr())

    b.hedge_submits = []
    b.orders = types.SimpleNamespace(
        has_open=lambda *a, **k: False,
        submit=lambda **kw: b.hedge_submits.append(kw))

    b.exits = []
    b._submit_exit = lambda pos, pct, reason, **k: b.exits.append(
        (pos.position_id, pct, reason))
    return b


# --- (a) staleness: a stale mark on the hedge-target symbol must block an
#         otherwise-valid hedge OPEN ------------------------------------------
def test_stale_mark_blocks_hedge_open():
    b = _bot(_open_triggering_state())
    b._mark_ts["BTC/USD"] = NOW - 100.0   # 100s > mark_stale_sec(20s): stale
    b._hedge_actions(NOW, equity=10_000.0)
    assert b.hedge_submits == [], \
        "a stale mark on the hedge-target symbol must block the OPEN"


# --- (b) halt: _halted must block hedge OPEN but never unwind ----------------
def test_halted_blocks_hedge_open_but_not_unwind():
    b_open = _bot(_open_triggering_state(), halted=True)
    b_open._hedge_actions(NOW, equity=10_000.0)
    assert b_open.hedge_submits == [], \
        "hedge OPEN is new risk - must be blocked while _halted"

    b_unwind = _bot(_unwind_triggering_state(), halted=True)
    b_unwind._hedge_actions(NOW, equity=10_000.0)
    assert b_unwind.exits, \
        "hedge unwind is risk REDUCTION - must NOT be blocked by _halted"
    assert b_unwind.exits[0][1] == 100.0
    assert "hedge unwind" in b_unwind.exits[0][2]


# --- (c) entries_disabled: kill switch must block hedge OPEN but never
#         unwind ---------------------------------------------------------------
def test_entries_disabled_blocks_hedge_open_but_not_unwind():
    b_open = _bot(_open_triggering_state(), entries_enabled=False)
    b_open._hedge_actions(NOW, equity=10_000.0)
    assert b_open.hedge_submits == [], \
        "hedge OPEN is new risk - must be blocked while entries_enabled=False"

    b_unwind = _bot(_unwind_triggering_state(), entries_enabled=False)
    b_unwind._hedge_actions(NOW, equity=10_000.0)
    assert b_unwind.exits, \
        "hedge unwind must NOT be blocked by the entries kill switch"


# --- bonus: the watchdog data-quality block (named in the same fix) must
#     also block hedge OPEN but never unwind ----------------------------------
def test_watchdog_entries_blocked_blocks_hedge_open_but_not_unwind():
    b_open = _bot(_open_triggering_state())
    b_open.watchdog.state.entries_blocked = True
    b_open._hedge_actions(NOW, equity=10_000.0)
    assert b_open.hedge_submits == [], \
        "hedge OPEN must be blocked while the watchdog blocks entries"

    b_unwind = _bot(_unwind_triggering_state())
    b_unwind.watchdog.state.entries_blocked = True
    b_unwind._hedge_actions(NOW, equity=10_000.0)
    assert b_unwind.exits, \
        "hedge unwind must NOT be blocked by a watchdog entries-block"


# --- sanity: the unmodified happy path still opens a hedge -------------------
def test_fresh_armed_state_still_opens_a_hedge():
    b = _bot(_open_triggering_state())
    b._hedge_actions(NOW, equity=10_000.0)
    assert len(b.hedge_submits) == 1
    submitted = b.hedge_submits[0]
    assert submitted["asset"] == "BTC"
    assert submitted["purpose"] == "hedge"
