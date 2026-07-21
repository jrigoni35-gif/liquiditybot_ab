"""core/goals.py — profit-goal evaluation for the period ledgers.

The dashboards have always labelled equity daily / weekly / monthly, and
the engine learned to close ISO weeks (RP-070) and now months (RP-071),
but nothing stated a TARGET or graded the period against it. This is the
"set goals and explain the misses" layer: a pure function that turns
(actual, goal, context) into a structured verdict the period-close block
audits, writes to the ledger, and surfaces to Grafana.

Deliberately measurement-only: no code here changes a trading decision.
The explanation is STRUCTURAL, not a narrative guess — it names the
category (hit / shortfall / loss), the attainment ratio, the dollar
shortfall, and the close-time context factors that are actually
observable (was the model governed off, were entries enabled). Deeper
"which trades" forensics already live in the per-fill ledger and the
postmortem summary; this layer states the target verdict and points at
those, it does not re-derive them.
"""
from typing import Optional


def evaluate_goal(period: str, actual: float, goal: float,
                  ctx: Optional[dict] = None) -> dict:
    """Grade one period's realized PnL against its target.

    period : "week" | "month" (label only; no behavior depends on it)
    actual : realized PnL for the period, USD (net of fees)
    goal   : target PnL for the period, USD. goal <= 0 disables grading
             (returns category "untracked" - a target must be a positive
             number to be a target).
    ctx    : optional close-time context, all keys optional:
             model_active (bool), entries_enabled (bool),
             reserve_refill (float, USD pulled from reserve on a loss).

    Returns a flat dict (JSON/CSV-friendly, all scalars): period, goal,
    actual, hit, category, attainment_pct, shortfall_usd, miss_reason.
    """
    ctx = ctx or {}
    goal = float(goal)
    actual = float(actual)
    tracked = goal > 0.0
    hit = tracked and actual >= goal
    # attainment is only meaningful against a positive goal; a negative
    # actual floors at 0% (you cannot be "40% of the way" while losing)
    attainment = (round(max(actual, 0.0) / goal * 100.0, 1)
                  if tracked else None)
    shortfall = round(max(goal - actual, 0.0), 2) if tracked else 0.0

    if not tracked:
        category = "untracked"
    elif hit:
        category = "hit"
    elif actual < 0.0:
        category = "loss"          # did not just miss - lost money
    else:
        category = "shortfall"     # made money, under target

    # structural miss reason: name the DOMINANT observable factor, in a
    # fixed precedence, from close-time context that is actually known.
    # Never fabricated - only flags we can read at the boundary.
    reason = ""
    if tracked and not hit:
        if ctx.get("entries_enabled") is False:
            reason = "entries were disabled for part/all of the period"
        elif ctx.get("model_active") is False:
            reason = ("model governed to prior (kelly-throttled) - "
                      "conviction sizing suppressed")
        elif category == "loss":
            rr = float(ctx.get("reserve_refill", 0.0) or 0.0)
            reason = ("realized loss" + (f"; reserve refilled {rr:.2f}"
                                         if rr > 0 else ""))
        else:
            reason = (f"under target by {shortfall:.2f} "
                      f"({attainment:.0f}% attained)")

    return {"period": period, "goal": round(goal, 2),
            "actual": round(actual, 2), "hit": bool(hit),
            "category": category, "attainment_pct": attainment,
            "shortfall_usd": shortfall, "miss_reason": reason}


def goal_progress(period: str, running: float, goal: float) -> dict:
    """Mid-period progress for the live status surface (no boundary yet).
    running = period-to-date realized PnL. Same disabled semantics as
    evaluate_goal (goal <= 0 -> untracked)."""
    goal = float(goal)
    tracked = goal > 0.0
    return {"period": period, "goal": round(goal, 2),
            "running": round(float(running), 2),
            "attainment_pct": (round(max(running, 0.0) / goal * 100.0, 1)
                               if tracked else None),
            "on_track": bool(tracked and running >= goal)}
