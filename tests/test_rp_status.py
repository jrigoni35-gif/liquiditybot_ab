"""tests/test_rp_status.py — BotRunner._rp_status: the §6 risk-protocol
posture block. Contract: every number derives from the stack's/sizer's OWN
attributes (no duplicated thresholds), and the section NEVER raises — a fault
yields {} (blank panel), not a wedged status write."""
from types import SimpleNamespace

import pytest

from core.state import PortfolioState
from risk.position_sizer import PositionSizer
from risk.protocols import RiskProtocolStack
from runner import BotRunner


def _bot(equity=5000.0):
    state = PortfolioState(starting_capital=equity)
    stack = RiskProtocolStack({})
    sizer = PositionSizer({"min_ticket_usd": 15.0}, profit_cfg={}, risk_cfg={},
                          capital_cfg={"hard_stop_drawdown_pct": 15.0})
    return SimpleNamespace(risk_protocols=stack, sizer=sizer, state=state,
                           marks={})


def test_fresh_book_is_neutral():
    out = BotRunner._rp_status(_bot(), 5000.0)
    assert out["daily_budget_used_frac"] == 0.0
    assert out["weekly_budget_used_frac"] == 0.0
    assert out["taper_mult"] == 1.0            # nothing spent -> no taper
    assert out["heat_frac"] == 0.0             # no positions
    assert out["heat_cap_frac"] == pytest.approx(0.35)
    assert out["dd_throttle_mult"] == 1.0      # no drawdown


def test_drawdown_engages_throttle_with_sizers_own_params():
    bot = _bot()
    # 7.5% MTM drawdown = half the 15% hard stop -> (1-0.5)^1.5 ~= 0.3536
    bot.state._equity_high_water = 5000.0
    out = BotRunner._rp_status(bot, 4625.0)    # -7.5% from the high water
    assert out["dd_throttle_mult"] == pytest.approx(
        (1.0 - 0.5) ** bot.sizer.dd_throttle_power, abs=1e-3)
    # floor honored: catastrophic dd never throttles below the sizer's floor
    out2 = BotRunner._rp_status(bot, 4250.0 - 1.0)   # ~15%+ dd
    assert out2["dd_throttle_mult"] >= bot.sizer.dd_throttle_floor


def test_budget_consumption_flows_from_stack():
    bot = _bot()
    stack = bot.risk_protocols
    stack.observe(5000.0, marks={}, now=1_000.0)     # anchor day/week at 5000
    # a 1.25% loss = half the 2.5% daily budget -> taper begins (start 0.5)
    out = BotRunner._rp_status(bot, 4937.5)
    assert out["daily_budget_used_frac"] == pytest.approx(0.5, abs=0.01)
    assert out["taper_mult"] <= 1.0


def test_faulty_bot_yields_empty_never_raises():
    assert BotRunner._rp_status(SimpleNamespace(), 5000.0) == {}
    assert BotRunner._rp_status(
        SimpleNamespace(risk_protocols=None, sizer=None), 5000.0) == {}
    # stack that raises internally -> {} (and no exception escapes)
    class Boom:
        def spent_fracs(self, equity):
            raise RuntimeError("boom")
    bot = _bot()
    bot.risk_protocols = Boom()
    assert BotRunner._rp_status(bot, 5000.0) == {}
