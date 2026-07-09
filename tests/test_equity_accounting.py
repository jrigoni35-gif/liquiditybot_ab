"""Regression: total_equity is PnL-settled, not notional-settled.

Cash is never debited when a position opens, so equity must add each open
position's marked-to-market GAIN/LOSS, not its full size*price notional.
The old code added notional, inflating equity by the cost basis of open
inventory (buy 1@2000 with no move -> reads 12000 instead of 10000) and,
because the sizer/inventory caps/watchdog all scale off equity, loosening
every risk control the more inventory was held.
"""
from datetime import datetime, timezone

from core.state import Position, PortfolioState


def _pos(direction, entry, size, symbol="ETH/USD"):
    return Position(position_id="p", symbol=symbol, direction=direction,
                    entry_price=entry, size=size, original_size=size,
                    opened_at=datetime.now(timezone.utc))


def _portfolio(cash=10_000.0):
    p = PortfolioState(starting_capital=cash)
    return p


def test_open_long_at_entry_does_not_inflate_equity():
    p = _portfolio()
    p.add_position(_pos("long", 2000.0, 1.0))
    # no price move -> equity unchanged, NOT cash + 2000 notional
    assert p.total_equity({"ETH/USD": 2000.0}) == 10_000.0


def test_long_equity_tracks_unrealized_gain():
    p = _portfolio()
    p.add_position(_pos("long", 2000.0, 1.0))
    assert p.total_equity({"ETH/USD": 2100.0}) == 10_100.0   # +$100 unrealized
    assert p.total_equity({"ETH/USD": 1900.0}) == 9_900.0    # -$100 unrealized


def test_short_equity_is_sign_correct():
    p = _portfolio()
    p.add_position(_pos("short", 2000.0, 1.0))
    # a short GAINS when price falls
    assert p.total_equity({"ETH/USD": 1900.0}) == 10_100.0
    assert p.total_equity({"ETH/USD": 2100.0}) == 9_900.0


def test_no_marks_returns_cash_plus_savings():
    p = _portfolio()
    p.add_position(_pos("long", 2000.0, 1.0))
    assert p.total_equity() == 10_000.0


def test_realized_pnl_flows_through_cash_consistently():
    p = _portfolio()
    p.record_realized_pnl(250.0)          # a closed winner
    assert p.total_equity() == 10_250.0
