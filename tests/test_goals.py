"""Profit-goal ledger (recommended-order #1): weekly + monthly targets,
goal-vs-actual grading, and a STRUCTURAL miss explanation (core/goals.py).

Extends RP-070 (week) with RP-071 (month). Measurement only - nothing
here changes a trading decision; the verdict is graded, audited, written
to outputs/{weekly,monthly}_ledger.csv, and surfaced to Grafana. Grading
uses close-time context flags (model governed off / entries disabled)
that are actually observable, never fabricated.
"""
from datetime import datetime, timezone

from core.config_guard import validate
from core.goals import evaluate_goal, goal_progress
from core.state import PortfolioState

JAN = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc).timestamp()
FEB = datetime(2026, 2, 3, 0, 5, tzinfo=timezone.utc).timestamp()
MAR = datetime(2026, 3, 2, 0, 5, tzinfo=timezone.utc).timestamp()


# ---------------------------------------------------------- evaluate_goal
def test_hit_when_actual_meets_goal():
    v = evaluate_goal("week", 30.0, 25.0)
    assert v["hit"] is True and v["category"] == "hit"
    assert v["shortfall_usd"] == 0.0 and v["miss_reason"] == ""
    assert v["attainment_pct"] == 120.0


def test_shortfall_made_money_under_target():
    v = evaluate_goal("week", 10.0, 25.0)
    assert v["hit"] is False and v["category"] == "shortfall"
    assert v["shortfall_usd"] == 15.0 and v["attainment_pct"] == 40.0
    assert "under target" in v["miss_reason"]


def test_loss_is_distinct_from_shortfall():
    v = evaluate_goal("month", -12.0, 100.0)
    assert v["category"] == "loss" and v["hit"] is False
    # attainment floors at 0 while losing, never negative
    assert v["attainment_pct"] == 0.0
    assert v["shortfall_usd"] == 112.0
    assert "realized loss" in v["miss_reason"]


def test_zero_goal_is_untracked_not_a_miss():
    v = evaluate_goal("week", -5.0, 0.0)
    assert v["category"] == "untracked" and v["hit"] is False
    assert v["attainment_pct"] is None and v["miss_reason"] == ""


def test_miss_reason_precedence_entries_beats_model_beats_loss():
    # entries disabled dominates every other factor
    v = evaluate_goal("week", -3.0, 25.0,
                      {"entries_enabled": False, "model_active": False})
    assert "entries were disabled" in v["miss_reason"]
    # model-off dominates a plain loss when entries WERE enabled
    v = evaluate_goal("week", -3.0, 25.0,
                      {"entries_enabled": True, "model_active": False})
    assert "governed to prior" in v["miss_reason"]
    # neither flag -> the loss itself, with the refill context
    v = evaluate_goal("week", -3.0, 25.0,
                      {"entries_enabled": True, "model_active": True,
                       "reserve_refill": 3.0})
    assert "realized loss" in v["miss_reason"] and "3.00" in v["miss_reason"]


def test_a_hit_never_carries_a_miss_reason_even_with_bad_context():
    v = evaluate_goal("week", 99.0, 25.0,
                      {"entries_enabled": False, "model_active": False})
    assert v["hit"] is True and v["miss_reason"] == ""


# ---------------------------------------------------------- goal_progress
def test_goal_progress_on_track_and_untracked():
    p = goal_progress("week", 30.0, 25.0)
    assert p["on_track"] is True and p["attainment_pct"] == 120.0
    p = goal_progress("week", 5.0, 25.0)
    assert p["on_track"] is False and p["attainment_pct"] == 20.0
    p = goal_progress("week", 5.0, 0.0)          # untracked
    assert p["on_track"] is False and p["attainment_pct"] is None


# --------------------------------------------------- state monthly close
def test_month_close_mirrors_week_boundary_semantics():
    s = PortfolioState(starting_capital=5000.0)
    s._last_month_key = ""                       # pre-upgrade snapshot
    assert s.maybe_close_month(JAN) is None      # adopt, no phantom month-0
    s.record_realized_pnl(40.0)
    assert s.monthly_realized_pnl == 40.0
    assert s.maybe_close_month(JAN) is None       # mid-month: nothing
    mo = s.maybe_close_month(FEB)
    assert mo is not None and mo["month"] == "2026-01"
    assert mo["monthly_realized"] == 40.0
    assert s.monthly_realized_pnl == 0.0          # reset on close
    assert s.maybe_close_month(FEB) is None        # once per boundary


def test_month_and_week_counters_are_independent():
    s = PortfolioState(starting_capital=5000.0)
    s.record_realized_pnl(10.0)
    assert s.weekly_realized_pnl == 10.0 and s.monthly_realized_pnl == 10.0
    # daily reset must not touch the period counters
    s.reset_daily_pnl()
    assert s.weekly_realized_pnl == 10.0 and s.monthly_realized_pnl == 10.0


# ---------------------------------------------------------------- guard
def test_guard_rejects_negative_goal_and_accepts_zero_disable():
    base = {"capital_management": {"starting_capital_usd": 5000,
            "savings_pct_of_profit": 20, "reserve_pct_of_profit": 10,
            "reinvestment_pct_of_profit": 70, "max_concurrent_positions": 5,
            "daily_loss_limit_pct": 5, "hard_stop_drawdown_pct": 15}}
    base["capital_management"]["weekly_profit_goal_usd"] = -1
    assert any(sev == "FATAL" and "weekly_profit_goal_usd" in m
               for sev, m in validate(base))
    base["capital_management"]["weekly_profit_goal_usd"] = 0     # disable
    base["capital_management"]["monthly_profit_goal_usd"] = 0
    assert not [m for _s, m in validate(base) if "profit_goal" in m]
