"""tests/test_sizer_derived_bar.py — the entry p(win) bar derived from the
payoff geometry (2026-07-27 drought diagnosis, operator-directed fix).

An absolute min_p_win is geometry-blind: the shipped 0.55 sat BELOW the
net-Kelly breakeven (~0.632 at current tiers/stop/fees), so it was a
phantom — entries in [0.55, breakeven) passed the bar only to die SZ-030
one step later, and any tier/fee change silently re-breaks an absolute
number. p_bar_mode="derived" pins the bar to the geometry itself:
max(breakeven + p_bar_edge_margin, min_p_win). The shipped margin is 0.0 —
pure de-phantomization, no new fitted number — and the exploration
synthetic p (0.64) must keep clearing the derived bar, which the config
guard enforces with clearance headroom (probe strangulation is exactly how
the Jul-24 drought started; never re-create it from the bar side).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.state import PortfolioState  # noqa: E402
from execution.inventory import InventoryManager  # noqa: E402
from regime.liquidity_regime import LiquidityState  # noqa: E402
from regime.macro_regime import DEFAULT_PLAYBOOKS, MacroRegimeState  # noqa: E402
from regime.vol_regime import VolState  # noqa: E402
from risk.leverage import LeverageGovernor  # noqa: E402
from risk.position_sizer import (PositionSizer,  # noqa: E402
                                 payoff_ratio_from_config)

PROFIT_CFG = {"tier_1": {"trigger_pct_gain": 1.0, "close_pct_of_position": 25},
              "tier_2": {"trigger_pct_gain": 2.0, "close_pct_of_position": 25},
              "tier_3": {"trigger_pct_gain": 3.5, "close_pct_of_position": 25},
              "tier_4": {"trigger_pct_gain": 5.0, "close_pct_of_position": 25}}
RISK_CFG = {"stop_loss_pct": 2.0}
PRETRADE = {"maker_fee_bps": 25.0, "taker_fee_bps": 40.0, "min_order_usd": 15}
EQUITY = 5000.0


def _sizer(**over):
    cfg = {"min_p_win": 0.55, "entry_cooldown_min": 0, "min_ticket_usd": 15}
    cfg.update(over)
    return PositionSizer(cfg, PROFIT_CFG, RISK_CFG, pretrade_cfg=PRETRADE)


def _size(sizer, p_win, bracket=None):
    state = PortfolioState(starting_capital=EQUITY)
    lev = LeverageGovernor({"use_margin": False}).decide(
        state, {}, EQUITY, 60.0, 2.0, 0.0)
    bull = MacroRegimeState("ETH", label="bull_quiet",
                            playbook=dict(DEFAULT_PLAYBOOKS["bull_quiet"]))
    return sizer.size("ETH", "long", 2000.0, p_win, EQUITY, state, bull,
                      VolState("ETH", sigma_annual_pct=50.0),
                      LiquidityState("ETH", size_mult=1.0), 1.0,
                      InventoryManager({}), lev, {}, bracket=bracket)


def _breakeven():
    rt = (PRETRADE["maker_fee_bps"] + PRETRADE["taker_fee_bps"]) / 100.0
    b_net = payoff_ratio_from_config(PROFIT_CFG, RISK_CFG, rt_cost_pct=rt)
    return 1.0 / (1.0 + b_net)


def test_absolute_mode_is_the_default_and_preserves_the_literal_bar():
    s = _sizer()                                  # no p_bar_mode key at all
    assert s.p_bar_base == 0.55                   # existing callers unchanged
    s2 = _sizer(p_bar_mode="absolute", min_p_win=0.60)
    assert s2.p_bar_base == 0.60


def test_derived_mode_pins_the_bar_to_breakeven_plus_margin():
    be = _breakeven()
    s = _sizer(p_bar_mode="derived", p_bar_edge_margin=0.0)
    assert abs(s.p_bar_base - be) < 1e-9
    s2 = _sizer(p_bar_mode="derived", p_bar_edge_margin=0.02)
    assert abs(s2.p_bar_base - (be + 0.02)) < 1e-9


def test_derived_bar_never_drops_below_the_min_p_win_floor():
    # a generous geometry (tiny stop, cheap fees) puts breakeven low; the
    # configured min_p_win then acts as the floor, not a phantom
    s = PositionSizer({"min_p_win": 0.55, "p_bar_mode": "derived",
                       "entry_cooldown_min": 0},
                      PROFIT_CFG, {"stop_loss_pct": 0.5},
                      pretrade_cfg={"maker_fee_bps": 2.0,
                                    "taker_fee_bps": 4.0})
    assert s.p_bar_base == 0.55                   # floor wins


def test_phantom_zone_now_rejects_at_the_bar_with_sz023():
    # p in (0.55, breakeven): old behavior passed the bar and died SZ-030;
    # derived mode rejects it AT the bar with the honest code
    be = _breakeven()
    p_phantom = (0.55 + be) / 2.0
    d = _size(_sizer(p_bar_mode="derived"), p_phantom)
    assert d.usd == 0.0
    assert any("SZ-023" in r for r in d.reasons)
    assert not any("SZ-030" in r for r in d.reasons)


def test_p_above_derived_bar_passes_the_bar():
    be = _breakeven()
    d = _size(_sizer(p_bar_mode="derived"), be + 0.03)
    assert not any("SZ-023" in r for r in d.reasons)


def test_exploration_synthetic_p_still_clears_the_shipped_derived_bar():
    # the F0b probe trickle is the bot's only entry flow during a model
    # drought; the shipped geometry must leave the synthetic probe p
    # (ml.exploration.p_win = 0.64) above the derived bar
    import json
    cfg = json.loads(
        (Path(__file__).resolve().parents[1] / "config.json")
        .read_text(encoding="utf-8"))
    ps = cfg["position_sizer"]
    assert ps.get("p_bar_mode") == "derived"      # the shipped fix
    rt = (cfg["pretrade"]["maker_fee_bps"]
          + cfg["pretrade"]["taker_fee_bps"]) / 100.0
    b_net = payoff_ratio_from_config(
        cfg["profit_taking"], cfg["risk"], rt_cost_pct=rt,
        reach_decay=ps.get("tier_reach_decay", 0.65))
    bar = max(1.0 / (1.0 + b_net) + ps.get("p_bar_edge_margin", 0.0),
              ps["min_p_win"])
    explore_p = cfg["ml"]["exploration"]["p_win"]
    assert explore_p > bar, (
        f"probe synthetic p {explore_p} must clear the derived bar {bar:.4f}"
        f" or the F0b trickle dies at SZ-023")


# ---------------------------------------------------------------------------
# Task 4: per-trade bracket bar + risk-in-size notional
# ---------------------------------------------------------------------------

def test_bracket_overrides_the_global_bar_per_trade():
    s = _sizer(p_bar_mode="derived")
    # wide bracket (pt 4%, sl 3%): b=(4-.65)/(3+.65)=0.918, bar 0.521
    d = _size(s, 0.55, bracket=(4.0, 3.0))
    assert not any("SZ-023" in r for r in d.reasons)   # clears 0.521
    d2 = _size(s, 0.50, bracket=(4.0, 3.0))
    assert any("SZ-023" in r for r in d2.reasons)      # below it


def test_bracket_notional_scales_dollar_risk_to_the_stop():
    s = _sizer(p_bar_mode="derived")
    d_legacy_like = _size(s, 0.80, bracket=(2.667, 2.0))  # sl == 2%
    d_wide = _size(s, 0.80, bracket=(5.334, 4.0))         # sl 2x wider
    assert d_legacy_like.approved and d_wide.approved
    # same p, same b (ratio equal) -> same f; notional halves as sl doubles
    assert abs(d_wide.usd - d_legacy_like.usd / 2.0) < max(
        0.02 * d_legacy_like.usd, 1.0)


def test_no_bracket_is_byte_identical_legacy():
    s = _sizer(p_bar_mode="derived")
    a = _size(s, 0.70)
    b = _size(s, 0.70, bracket=None)
    assert (a.usd, a.kelly_f, a.reasons) == (b.usd, b.kelly_f, b.reasons)


def test_bracket_invalid_values_fail_closed():
    # nonfinite or non-positive bracket legs are a fail-closed SZ_INVALID_INPUT,
    # never a silent fall-through to the legacy geometry
    s = _sizer(p_bar_mode="derived")
    for bad in ((0.0, 2.0), (4.0, 0.0), (float("nan"), 2.0),
               (4.0, float("nan")), (4.0, float("inf")),
               (float("-inf"), 2.0), (-1.0, 2.0)):
        d = _size(s, 0.90, bracket=bad)
        assert d.usd == 0.0, f"bracket={bad!r} should fail closed"
        assert any("SZ-010" in r for r in d.reasons), (
            f"bracket={bad!r} missing SZ-010: {d.reasons}")


def test_absolute_mode_bracket_bar_unchanged_but_payoff_b_reports_bracket():
    # absolute mode: the bar stays the fixed p_bar_base regardless of any
    # bracket (D3 conditional: derived formula only applies when
    # p_bar_mode == "derived"). Use a TIGHT bracket whose own breakeven
    # (~0.913) sits well above the fixed absolute bar (0.55) -- if the bar
    # incorrectly picked up the bracket geometry in absolute mode, this
    # p_win would die SZ-023; it must not, because the bar ignores it here.
    s = _sizer()                                   # absolute mode, default
    assert s.p_bar_mode == "absolute"
    tight = (1.0, 3.0)                              # b_net=(1-.65)/(3+.65)=0.0959
    d = _size(s, 0.70, bracket=tight)
    assert not any("SZ-023" in r for r in d.reasons)  # bar == 0.55, unaffected
    # tight bracket's own breakeven (~0.913) is above 0.70, so net-Kelly
    # correctly still vetoes it -- just not via the bar
    assert not d.approved

    # a generous bracket that clears both the (unchanged) absolute bar and
    # its own Kelly breakeven: approved, and payoff_b must report the
    # BRACKET b (~0.918), not the legacy config b_net (~0.583)
    wide = (4.0, 3.0)
    d2 = _size(s, 0.85, bracket=wide)
    assert d2.approved
    expected_b = (4.0 - s.rt_cost_pct) / (3.0 + s.rt_cost_pct)
    assert abs(d2.payoff_b - expected_b) < 1e-6
    assert abs(d2.payoff_b - s.b_net) > 0.05        # distinct from legacy net b
