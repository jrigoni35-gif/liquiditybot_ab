"""tests/test_reset_paper_capital.py — the paper-capital reseat rewrites ONLY
the portfolio money base and leaves positions + every other snapshot section
(and the input) untouched."""
from scripts.reset_paper_capital import reset_portfolio


def _snap():
    return {
        "version": 9,
        "portfolio": {
            "starting_capital": 800.0, "cash_balance": 800.05,
            "savings_balance": 0.61, "realized_pnl_total": 0.66,
            "daily_realized_pnl": 0.12, "fees_paid_total": 2.33,
            # both fields below were MISSED by resets before 2026-08-11:
            # monthly was never in _MONEY_ZERO; entry_fees_total was born
            # 2026-08-09 and a stale value breaks the equity identity
            "monthly_realized_pnl": 0.31, "entry_fees_total": 1.87,
            "equity_high_water": 800.69,
            "positions": [{"symbol": "ETH/USD", "size": 0.01},
                          {"symbol": "BTC/USD", "size": 0.0003}],
        },
        "monitor": {"champion_brier": 0.19, "level": 0},
        "open_orders": [{"id": "o1"}],
        "history_pending": {"p1": {"asset": "ETH/USD"}},
        "performance": {"trades": [{"asset": "ETH", "usd": -2.0,
                                    "win": False, "ts": 1.0}]},
    }


def test_money_base_reset_to_capital():
    out = reset_portfolio(_snap(), 5000.0)
    pf = out["portfolio"]
    assert pf["starting_capital"] == 5000.0
    assert pf["cash_balance"] == 5000.0
    assert pf["equity_high_water"] == 5000.0
    assert pf["savings_balance"] == 0.0
    assert pf["realized_pnl_total"] == 0.0
    assert pf["daily_realized_pnl"] == 0.0
    assert pf["fees_paid_total"] == 0.0
    assert pf["monthly_realized_pnl"] == 0.0, \
        "monthly counter must not survive a capital reset"
    assert pf["entry_fees_total"] == 0.0, \
        "stale opening-leg fees would break net_pnl_all_time on a fresh base"
    assert pf["goal_ladder_mult"] == 1.0, \
        "fresh capital regime restarts the RP-072 ladder at the base goal"


def test_positions_are_kept():
    out = reset_portfolio(_snap(), 5000.0)
    pos = out["portfolio"]["positions"]
    assert len(pos) == 2
    assert {p["symbol"] for p in pos} == {"ETH/USD", "BTC/USD"}


def test_other_sections_preserved():
    out = reset_portfolio(_snap(), 5000.0)
    assert out["monitor"] == {"champion_brier": 0.19, "level": 0}
    assert out["open_orders"] == [{"id": "o1"}]
    assert out["history_pending"] == {"p1": {"asset": "ETH/USD"}}
    assert out["version"] == 9


def test_performance_window_is_swept():
    """The rolling perf ledger is DOLLAR-denominated; carrying one capital
    regime's window into another blends populations whose dollar scale
    differs by the reset ratio - pooled-populations on every board tile.
    Money figures, so the sweep takes them."""
    out = reset_portfolio(_snap(), 5000.0)
    assert out["performance"] == {"trades": []}


def test_input_snapshot_not_mutated():
    snap = _snap()
    reset_portfolio(snap, 5000.0)
    assert snap["portfolio"]["starting_capital"] == 800.0
    assert snap["portfolio"]["cash_balance"] == 800.05


def test_missing_portfolio_is_safe():
    out = reset_portfolio({"version": 9}, 5000.0)
    assert out["portfolio"]["cash_balance"] == 5000.0
    assert out["portfolio"].get("positions") in (None, [])
