"""29c — the week/month close must be crash-atomic.

maybe_close_week advances the persisted week key and zeroes the period P&L
in MEMORY; before this fix those changes waited for the NEXT 30s cadence
snapshot, so a kill inside that window restored the OLD key on restart and
REPLAYED the close: duplicate RP_WEEK_CLOSED audit record, duplicate
weekly_ledger.csv row, and — after a losing week — a SECOND reserve->cash
refill for the same loss, leaving the book of record's balances wrong by up
to the week's loss. main.LiquidityBot._close_periods must force a snapshot
the moment either boundary fires, and stay quiet mid-period (no write
amplification on the 30s fast cycle).
"""
from datetime import datetime, timezone
from types import SimpleNamespace

from core.state import PortfolioState
from main import LiquidityBot
from risk.capital_manager import CapitalManager

MON = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc).timestamp()
NEXT_MON = datetime(2026, 7, 27, 0, 5, tzinfo=timezone.utc).timestamp()


def _stub(tmp_path):
    s = PortfolioState(starting_capital=5000.0)
    s.maybe_close_week(MON)                     # adopt current week key
    s.maybe_close_month(MON)                    # adopt current month key
    snaps = []
    stub = SimpleNamespace(
        state=s,
        capital=CapitalManager({"savings_pct_of_profit": 20,
                                "reserve_pct_of_profit": 10,
                                "max_concurrent_positions": 5,
                                "hard_stop_drawdown_pct": 15}),
        config={"system": {
            "weekly_ledger_path": str(tmp_path / "weekly.csv"),
            "monthly_ledger_path": str(tmp_path / "monthly.csv")}},
        store=SimpleNamespace(snapshot=lambda bot: snaps.append(1) or True),
        _grade_period_goal=lambda *a, **k: {"category": "n/a"},
    )
    return stub, snaps


def test_boundary_close_forces_an_immediate_snapshot(tmp_path):
    stub, snaps = _stub(tmp_path)
    stub.state.record_realized_pnl(-40.0)       # a losing week: the refill case
    LiquidityBot._close_periods(stub, NEXT_MON)
    assert snaps, ("crossing a period boundary must snapshot immediately - "
                   "the close is not durable until it is on disk")


def test_midweek_cycle_does_not_snapshot(tmp_path):
    stub, snaps = _stub(tmp_path)
    LiquidityBot._close_periods(stub, MON + 3600.0)
    assert snaps == [], "no boundary crossed - no extra snapshot"
