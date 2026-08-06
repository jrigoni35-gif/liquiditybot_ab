"""The profit-pool skim must grade the TRADE, not each winning leg.

Round-2 finding (2026-08-05). `record_realized_profit` was invoked once per
exit FILL with `net` (gross minus that leg's exit fee) — not `trade_net`,
which additionally carries the slice's pro-rata share of the ENTRY fees.
Two defects in one call:

  (a) the skim base overstated profit by the leg's entry fees, so savings
      and reserve were funded from money the trade never netted;
  (b) it fired per LEG, so a trade whose tier-1 take closed +$16 and whose
      thesis-stop later closed -$96 (net -$80) still moved ~$4.80 into
      LOCKED pools.

Tiered exits are the NORMAL trade shape here, so cash — the sizing base —
bled monotonically into locked pools as a function of gross winning legs
rather than net profit. Savings is never clawed back by design, so every
one of those skims was permanent.

The fix separates two concerns that were fused: cash settlement stays
per-leg (correct — entry fees already left cash at fill time via
record_entry_fee, so `net` is the right cash delta), while the three-way
POOL SPLIT happens once, at position close, on the fully-net trade result.
"""
from core.state import PortfolioState
from risk.capital_manager import CapitalManager


def _cm(sav=20, resv=10):
    return CapitalManager({"savings_pct_of_profit": sav,
                           "reserve_pct_of_profit": resv,
                           "max_concurrent_positions": 5,
                           "hard_stop_drawdown_pct": 15})


def _state(cash=5000.0):
    s = PortfolioState(starting_capital=cash)
    return s


def test_winning_leg_of_a_losing_trade_skims_nothing():
    """THE bug, in the shape the engine actually produces: a tier take
    banks a small win, then the stop takes a larger loss."""
    s, cm = _state(), _cm()
    cm.record_realized_profit(16.0, s, skim=False)     # tier-1 leg
    cm.record_realized_profit(-96.0, s, skim=False)    # thesis stop
    cm.skim_trade(-80.0, s)                            # the TRADE lost

    assert s.savings_balance == 0.0, \
        "a losing trade must never fund the locked pools"
    assert s.reserve_balance == 0.0
    # cash carries the full realized loss and nothing else
    assert abs(s.cash_balance - (5000.0 - 80.0)) < 1e-9


def test_winning_trade_skims_once_on_the_fully_net_result():
    s, cm = _state(), _cm()
    cm.record_realized_profit(60.0, s, skim=False)     # tier-1 leg
    cm.record_realized_profit(60.0, s, skim=False)     # runner leg
    cm.skim_trade(100.0, s)          # net of entry fees: 120 gross -> 100

    # skim grades the TRADE's 100, not the 120 of gross winning legs
    assert abs(s.savings_balance - 20.0) < 1e-9
    assert abs(s.reserve_balance - 10.0) < 1e-9
    # cash: +120 settled, -30 skimmed
    assert abs(s.cash_balance - (5000.0 + 120.0 - 30.0)) < 1e-9
    # equity conserves the full gain across pools regardless of the split
    assert abs(s.total_equity({}) - (5000.0 + 120.0)) < 1e-9


def test_skim_false_settles_pnl_without_touching_pools():
    s, cm = _state(), _cm()
    cm.record_realized_profit(100.0, s, skim=False)
    assert s.savings_balance == 0.0 and s.reserve_balance == 0.0
    assert abs(s.cash_balance - 5100.0) < 1e-9
    assert abs(s.realized_pnl_total - 100.0) < 1e-9      # P&L still booked


def test_skim_trade_does_not_double_book_pnl():
    """skim_trade moves money BETWEEN pools; it must not re-book P&L that
    the per-leg settlement already recorded, or realized totals inflate."""
    s, cm = _state(), _cm()
    cm.record_realized_profit(100.0, s, skim=False)
    before = (s.realized_pnl_total, s.daily_realized_pnl,
              s.weekly_realized_pnl, s.monthly_realized_pnl)
    cm.skim_trade(100.0, s)
    after = (s.realized_pnl_total, s.daily_realized_pnl,
             s.weekly_realized_pnl, s.monthly_realized_pnl)
    assert before == after
    assert abs(s.total_equity({}) - 5100.0) < 1e-9      # equity unchanged


def test_losing_trade_skim_is_a_noop():
    s, cm = _state(), _cm()
    cm.record_realized_profit(-40.0, s, skim=False)
    cm.skim_trade(-40.0, s)
    assert s.savings_balance == 0.0 and s.reserve_balance == 0.0
    assert abs(s.cash_balance - 4960.0) < 1e-9


def test_legacy_single_call_still_skims():
    """The one-shot form (skim defaults True) keeps its old behavior, so
    every existing caller and the weekly-pool suite are unchanged."""
    s, cm = _state(), _cm()
    cm.record_realized_profit(100.0, s)
    assert abs(s.savings_balance - 20.0) < 1e-9
    assert abs(s.reserve_balance - 10.0) < 1e-9
