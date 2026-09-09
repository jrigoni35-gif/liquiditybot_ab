"""Regressions for the three open items closed in this pass.

1. Hedger trim-over-hedge: when the asset the hedger would short is already
   held long (or vice versa), it must TRIM that position instead of opening
   the offsetting hedge - same net-delta reduction, half the fee legs, no
   long+short overlap in one asset. Genuine one-sided concentration (hedge
   asset not held) still opens the beta-weighted hedge (smoke parity).
2. Algos: two consecutive structural child rejects abort the parent (the
   docstring promised this; it was never implemented).
3. OrderManager userref: stable across processes (sha256, not salted hash).
"""
from datetime import datetime, timezone

import pytest

from core.state import PortfolioState, Position
from execution.algos import ExecutionScheduler
from execution.hedging import HedgeEngine
from execution.order_manager import OrderManager
from regime.correlation import CorrState

MARKS = {"ETH/USD": 2000.0, "BTC/USD": 60000.0}
SYMBOLS = {"ETH": "ETH/USD", "BTC": "BTC/USD"}


def _pos(pid, symbol, direction, entry, size):
    return Position(pid, symbol, direction, entry, size, size,
                    datetime.now(timezone.utc))


def _hedger():
    return HedgeEngine({"enabled": True, "max_net_delta_pct_of_equity": 15,
                        "rebalance_band_pct": 5, "min_hedge_usd": 50},
                       SYMBOLS)


def _corr():
    return CorrState(corr_fast={("BTC", "ETH"): 0.85},
                     betas={("ETH", "BTC"): 1.2, ("BTC", "ETH"): 0.6})


# --- 1: trim-over-hedge ------------------------------------------------------
def test_overlap_is_trimmed_not_hedged():
    state = PortfolioState(starting_capital=10_000)
    state.add_position(_pos("eth1", "ETH/USD", "long", 2000.0, 1.0))   # $2000
    state.add_position(_pos("btc1", "BTC/USD", "long", 60000.0, 0.01))  # $600
    # net +$2600 > cap $1500; hedge asset = BTC, already held LONG -> trim it
    acts = _hedger().evaluate(state, MARKS, 10_000.0, _corr())
    assert len(acts) == 1 and acts[0].kind == "trim"
    assert acts[0].position_id == "btc1"
    assert acts[0].usd == pytest.approx(600.0)      # full BTC position
    # and no "open" action alongside - one corrective step per cycle
    assert all(a.kind != "open" for a in acts)


def test_no_overlap_still_opens_beta_weighted_hedge():
    state = PortfolioState(starting_capital=10_000)
    state.add_position(_pos("eth1", "ETH/USD", "long", 2000.0, 1.0))   # $2000
    # net +$2000 > cap $1500, BTC not held -> genuine hedge (smoke parity)
    acts = _hedger().evaluate(state, MARKS, 10_000.0, _corr())
    assert len(acts) == 1 and acts[0].kind == "open"
    assert acts[0].asset == "BTC" and acts[0].direction == "short"


def test_short_book_trims_held_short():
    state = PortfolioState(starting_capital=10_000)
    state.add_position(_pos("eth1", "ETH/USD", "short", 2000.0, 1.0))   # -$2000
    state.add_position(_pos("btc1", "BTC/USD", "short", 60000.0, 0.01))  # -$600
    acts = _hedger().evaluate(state, MARKS, 10_000.0, _corr())
    assert len(acts) == 1 and acts[0].kind == "trim"
    assert acts[0].position_id == "btc1" and acts[0].direction == "short"


def test_dust_overlap_falls_through_to_hedge():
    state = PortfolioState(starting_capital=10_000)
    state.add_position(_pos("eth1", "ETH/USD", "long", 2000.0, 1.0))
    # $30 BTC position is below min_hedge_usd=50: not worth a trim order
    state.add_position(_pos("btc1", "BTC/USD", "long", 60000.0, 0.0005))
    acts = _hedger().evaluate(state, MARKS, 10_000.0, _corr())
    assert len(acts) == 1 and acts[0].kind == "open"


# --- 2: algo reject-streak abort --------------------------------------------
def _scheduler():
    return ExecutionScheduler({"enabled": True, "max_children": 4,
                               "min_interval_sec": 10.0})


def test_two_consecutive_rejects_abort_parent():
    s = _scheduler()
    p = s.create_parent("ETH", "ETH/USD", "buy", "long", 1.0,
                        arrival_price=2000.0, now=0.0)
    s.note_child_rejected(p.parent_id, 0.25, "firewall")
    assert p.parent_id in s.parents                 # one reject: still alive
    s.note_child_rejected(p.parent_id, 0.25, "firewall again")
    assert p.parent_id not in s.parents             # two: aborted
    assert "two consecutive" in p.abort_reason


def test_accepted_child_resets_reject_streak():
    s = _scheduler()
    p = s.create_parent("ETH", "ETH/USD", "buy", "long", 1.0,
                        arrival_price=2000.0, now=0.0)
    s.note_child_rejected(p.parent_id, 0.25, "firewall")
    s.note_child_order(p.parent_id, "pos-1")        # success: streak resets
    s.note_child_rejected(p.parent_id, 0.25, "firewall")
    assert p.parent_id in s.parents                 # 1-0-1, never 2 in a row


# --- 3: stable userref --------------------------------------------------------
def test_userref_is_stable_and_int32():
    import hashlib
    oid = "abc12345"
    expect = str(int.from_bytes(
        hashlib.sha256(oid.encode()).digest()[:4], "big") % 2_000_000_000)
    assert OrderManager._userref(oid) == expect     # sha256-derived, unsalted
    assert OrderManager._userref(oid) == OrderManager._userref(oid)
    assert 0 <= int(OrderManager._userref(oid)) < 2_000_000_000
