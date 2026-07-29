"""Kill-switch recovery loop (2026-07-12 live incident).

At $800 equity the governor's L2 kill switch wedged the whole learning
loop: kelly floored at 0.4 shrank every exploration ticket to $1-4,
the $15 min-ticket floor vetoed 100% of them (SZ-042 storm), no labels
accrued, retrain had nothing new, and note_deployed didn't clear the
evidence window - so even a successful deploy was re-convicted by the
old model's records on the next close. Three fixes under test:

  1. floor_to_min: exploration entries floor up to the min ticket (a
     label costs the min ticket; that's what exploration is FOR). Hard
     vetoes still veto; default off preserves old behavior.
  2. note_deployed clears the window: a fresh champion starts with
     fresh evidence.
  3. _thesis_scored_p: the governor grades the model on its OWN call
     (model_p), never on the exploration-forced sizing p.
"""
import types

from core.state import PortfolioState
from execution.inventory import InventoryManager
from main import LiquidityBot
from ml.monitor import ModelMonitor
from regime.liquidity_regime import LiquidityState
from regime.macro_regime import DEFAULT_PLAYBOOKS, MacroRegimeState
from regime.vol_regime import VolState
from risk.leverage import LeverageGovernor
from risk.position_sizer import PositionSizer

PROFIT_CFG = {"tier_1": {"trigger_pct_gain": 1.0, "close_pct_of_position": 25},
              "tier_2": {"trigger_pct_gain": 2.0, "close_pct_of_position": 25},
              "tier_3": {"trigger_pct_gain": 3.5, "close_pct_of_position": 25},
              "tier_4": {"trigger_pct_gain": 5.0, "close_pct_of_position": 25}}
EQUITY = 800.0


def _size(floor_to_min, size_mult=1.0, risk_scale=0.4):
    sizer = PositionSizer({"min_p_win": 0.55, "entry_cooldown_min": 0,
                           "min_ticket_usd": 15},
                          PROFIT_CFG, {"stop_loss_pct": 2.0},
                          pretrade_cfg={"min_order_usd": 15})
    state = PortfolioState(starting_capital=EQUITY)
    lev = LeverageGovernor({"use_margin": False}).decide(
        state, {}, EQUITY, 60.0, 2.0, 0.0)
    bull = MacroRegimeState("ETH", label="bull_quiet",
                            playbook=dict(DEFAULT_PLAYBOOKS["bull_quiet"]))
    vol = VolState("ETH", sigma_annual_pct=50.0)
    liq = LiquidityState("ETH", size_mult=size_mult)
    # p(win) 0.72: a marginal-but-POSITIVE net edge, just above the honest 0.690
    # net breakeven. The exit-leg cost fix (maker entry + taker exit, not
    # 2*maker) raised b_net's breakeven to ~0.632; the old 0.62 fixture now
    # sits BELOW it, so net-Kelly f* <= 0 (SZ-030) zeroes the trade before the
    # exploration-FLOOR logic under test can run. Re-baselined consciously to
    # keep exercising the floor mechanism (SZ-042/044/031), not the breakeven.
    return sizer.size("ETH", "long", 2000.0, 0.72, EQUITY, state, bull, vol,
                      liq, 1.0, InventoryManager({}), lev, {},
                      risk_scale=risk_scale, floor_to_min=floor_to_min)


def test_small_equity_exploration_starves_without_floor():
    d = _size(floor_to_min=False)
    assert not d.approved
    assert any("SZ-042" in r for r in d.reasons), d.reasons


def test_floor_rescues_exploration_ticket():
    d = _size(floor_to_min=True)
    assert d.approved, d.reasons
    # the floor now clears the pretrade min-order with margin (max(min_ticket,
    # min_order*1.2) = max(15, 18) = 18): a bare min-ticket floor landed a few
    # cents under min_order at the maker quote and died PT-031.
    assert d.usd == 18.0
    assert any("SZ-044" in r for r in d.reasons), d.reasons


def test_floor_never_rescues_a_zeroed_trade():
    d = _size(floor_to_min=True, size_mult=0.0)
    assert not d.approved
    assert any("SZ-031" in r for r in d.reasons), d.reasons


def test_deploy_clears_the_evidence_window(tmp_path):
    mon = ModelMonitor({"window_trades": 30, "min_trades_to_judge": 15,
                        "retrain_flag_path": str(tmp_path / "r.flag")})
    for _ in range(20):                       # confidently wrong: p=.9, loss
        mon.record_close(0.9, 0, True)
    assert mon.level == 2 and mon.use_model is False
    mon.note_deployed(0.12)
    assert mon.level == 0 and mon.use_model is True and mon.kelly_mult == 1.0
    # the old records are gone: one close on the NEW model must not
    # re-evaluate the stale window and re-convict (observed live)
    mon.record_close(0.6, 1, True)
    assert mon.level == 0


def test_thesis_scored_p_prefers_model_p():
    t = types.SimpleNamespace(model_p=0.56, p_win=0.62)
    assert LiquidityBot._thesis_scored_p(t) == 0.56
    legacy = types.SimpleNamespace(model_p=-1.0, p_win=0.62)
    assert LiquidityBot._thesis_scored_p(legacy) == 0.62
