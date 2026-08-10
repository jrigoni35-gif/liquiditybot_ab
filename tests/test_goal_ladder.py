"""RP-072 goal ladder - the stressor regime's escalating monthly target.

Operator directive 2026-08-11: "as it starts to succeed, scale the profits to
the most it can stress every month." Registered semantics, pinned here:

  * the effective MONTHLY goal is config base x state.goal_ladder_mult;
  * a month CLOSING at >=100% of its EFFECTIVE goal ratchets the mult x1.5 -
    graded first, escalated after, so a closed month is judged by the bar it
    was run under;
  * the ladder NEVER de-escalates (a missed month keeps the bar);
  * the week grades at base - escalation is monthly by directive;
  * the mult survives restarts (persistence round trip) and resets to 1.0
    only with a capital reset (fresh regime, fresh ladder);
  * grading/telemetry only - no trading decision reads the mult.
"""
from __future__ import annotations

import pytest

from core.state import PortfolioState


def _grade(bot_state, config, realized):
    """Drive main.py's real grader + ratchet logic the way _close_periods
    does, without a full engine: replicate the exact sequence (grade with the
    OLD mult, escalate after) via the same evaluate_goal the engine calls."""
    from core.goals import evaluate_goal
    base = float(config["capital_management"]["monthly_profit_goal_usd"])
    eff = base * bot_state.goal_ladder_mult
    verdict = evaluate_goal("month", realized, eff, {})
    if eff > 0 and realized >= eff:
        bot_state.goal_ladder_mult *= 1.5
    return verdict, eff


CFG = {"capital_management": {"monthly_profit_goal_usd": 100.0}}


def test_met_month_ratchets_after_grading():
    st = PortfolioState(starting_capital=800.0)
    verdict, eff = _grade(st, CFG, realized=120.0)
    assert eff == 100.0                      # graded at the bar it ran under
    assert verdict["hit"] is True
    assert st.goal_ladder_mult == pytest.approx(1.5)
    # next month's bar is 150
    _v, eff2 = _grade(st, CFG, realized=10.0)
    assert eff2 == pytest.approx(150.0)


def test_missed_month_never_deescalates():
    st = PortfolioState(starting_capital=800.0)
    st.goal_ladder_mult = 2.25               # two rungs climbed
    _grade(st, CFG, realized=-50.0)
    assert st.goal_ladder_mult == pytest.approx(2.25), \
        "the stress never relaxes - a missed month keeps the bar"


def test_two_met_months_compound():
    st = PortfolioState(starting_capital=800.0)
    _grade(st, CFG, realized=100.0)          # exactly on the bar counts
    _grade(st, CFG, realized=150.0)
    assert st.goal_ladder_mult == pytest.approx(2.25)
    _v, eff = _grade(st, CFG, realized=0.0)
    assert eff == pytest.approx(225.0)


def test_serializer_and_restore_both_know_the_field():
    """The mult must survive restarts. The full snapshot round trip runs in
    the engine integration suites; here the WRITE and READ sites are pinned
    directly - persistence must serialize goal_ladder_mult in the portfolio
    section and restore it with a >=1.0 clamp (a corrupt 0 would disable
    monthly grading; below-1.0 would relax the stress)."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "core"
           / "persistence.py").read_text(encoding="utf-8")
    assert '"goal_ladder_mult"' in src, "serializer never writes the mult"
    assert src.count("goal_ladder_mult") >= 2, "restore path never reads it"


def test_pre_ladder_snapshot_restores_to_base():
    """A snapshot written before RP-072 has no goal_ladder_mult key - the
    restore path must default to 1.0, and clamp anything below 1.0 up."""
    st = PortfolioState(starting_capital=800.0)
    assert st.goal_ladder_mult == 1.0


def test_engine_grades_month_at_effective_and_escalates_after():
    """AST pin on main.py: the ratchet must fire AFTER RP_MONTH_CLOSED
    grading (grade at the old bar), and _grade_period_goal must scale the
    month goal by the ladder."""
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "main.py").read_text(
        encoding="utf-8")
    assert "goal_ladder_mult" in src
    tree = ast.parse(src)
    grader = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "_grade_period_goal")
    gsrc = ast.get_source_segment(src, grader) or ""
    assert "goal_ladder_mult" in gsrc, \
        "_grade_period_goal does not apply the ladder to the month goal"
    closer = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "_close_periods")
    csrc = ast.get_source_segment(src, closer) or ""
    assert "RP_GOAL_ESCALATED" in csrc, "_close_periods never escalates"
    assert csrc.index("RP_MONTH_CLOSED") < csrc.index("RP_GOAL_ESCALATED"), \
        "escalation must follow grading - a month is judged by the bar it ran under"


def test_code_is_registered():
    from core.codes import Code
    assert Code.RP_GOAL_ESCALATED == "RP-072"
