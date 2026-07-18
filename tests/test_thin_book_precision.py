"""Thin-book precision entries (execution/tactics.py).

Adverse-selection defense: a thin book is a toxic book — crossing it pays
the full spread to an informed counterparty exactly when depth is scarce.
When thin_book_maker_only is enabled, an entry into a "thin" liquidity
regime is forced MAKER-only (never taker) and rests improved deeper into
the spread for a precise fill. Contract:
  - OFF (default): behavior is unchanged — a high-urgency thin entry still
    takes the taker cross;
  - ON: a thin book never produces a taker plan at any urgency; it rests
    maker (post_only) improved thin_improve_spread_frac into the spread;
  - ON changes NOTHING for liquid/spoofy books (only 'thin' is affected);
  - config_guard rejects a thin_improve_spread_frac that reaches the touch.
"""
from types import SimpleNamespace

from core.config_guard import validate
from execution.tactics import ExecutionPlanner

BOOK = {"bids": [[100.0, 1.0]], "asks": [[100.20, 1.0]]}   # 20c spread
Q = SimpleNamespace(bid=100.0, ask=100.20)


def _planner(**over):
    cfg = {"enabled": True, "allow_taker": True, "join_at_urgency": 0.40,
           "improve_at_urgency": 0.70, "taker_at_urgency": 0.88,
           "improve_spread_frac": 0.25}
    cfg.update(over)
    return ExecutionPlanner(cfg)


def test_off_by_default_thin_high_urgency_still_takes():
    p = _planner()                                   # thin_book_maker_only off
    plan = p.plan_entry("long", Q, BOOK, urgency=0.95, liq_label="thin")
    assert plan.taker is True and plan.style == "taker"


def test_on_thin_never_takes_rests_maker_precise():
    p = _planner(thin_book_maker_only=True, thin_improve_spread_frac=0.40)
    plan = p.plan_entry("long", Q, BOOK, urgency=0.95, liq_label="thin")
    assert plan.taker is False and plan.post_only is True
    assert plan.style == "improve"
    # rests 40% into the 20c spread from the bid: 100.00 + 0.40*0.20 = 100.08
    assert abs(plan.price - 100.08) < 1e-9
    assert plan.price < 100.20                        # strictly inside, a maker


def test_on_thin_short_side_symmetric():
    p = _planner(thin_book_maker_only=True, thin_improve_spread_frac=0.40)
    plan = p.plan_entry("short", Q, BOOK, urgency=0.95, liq_label="thin")
    assert plan.taker is False
    assert abs(plan.price - 100.12) < 1e-9            # ask - 0.40*spread


def test_on_liquid_book_unaffected_still_takes():
    p = _planner(thin_book_maker_only=True)
    plan = p.plan_entry("long", Q, BOOK, urgency=0.95, liq_label="liquid")
    assert plan.taker is True and plan.style == "taker"


def test_thin_low_urgency_joins_regardless():
    # below join_at both modes fall back to the A-S quote (no chase)
    for mo in (False, True):
        p = _planner(thin_book_maker_only=mo)
        plan = p.plan_entry("long", Q, BOOK, urgency=0.10, liq_label="thin")
        assert plan.taker is False and plan.post_only is True


def test_guard_rejects_full_spread_improve():
    fatals = [m for s, m in validate(
        {"execution_tactics": {"thin_improve_spread_frac": 0.5}})
        if s == "FATAL"]
    assert any("thin_improve_spread_frac" in m for m in fatals)
    clean = [m for s, m in validate(
        {"execution_tactics": {"thin_improve_spread_frac": 0.4}})
        if s == "FATAL"]
    assert not any("thin_improve_spread_frac" in m for m in clean)
