"""tests/test_bracket_exits.py — geometry-alignment Task 5: model-lane
bracket entries, bracket exits, tb_* live reasons ("the traded bet is the
labeled bet", docs/superpowers/specs/2026-07-27-geometry-alignment-design.md
spec D1).

Five binding behaviors, each with its own section below:
  1. Entry (conviction AND probe) computes the bracket via barrier_geometry
     and stamps it on the Position - tested at the newly-extracted
     `LiquidityBot._bracket_for_entry` seam (a pure-ish per-trade sizing
     helper) plus `_handle_fill`'s stamping from order.meta.
  2. Exit evaluation for a bracket position REPLACES the tier engine's
     scheduled profit-take/PT-060 time-stop for that position (never
     both); overlays (give-back/chandelier ratchet) stay senior.
  3. Close reasons (tb_pt/tb_sl/tb_time) thread VERBATIM into the live-
     label barrier column - `label_era_of` then tags the row
     LABEL_ERA_TRIPLE_BARRIER.
  4. bracket_exits.enabled=false -> byte-identical legacy (tier exits, no
     bracket fields stamped).
  5. Guards (core/config_guard.py): FATAL incoherent label_mode; WARN
     probe-clearance extended to the worst-case floored-bracket bar
     (0.614 at the shipped config - computed, not hardcoded).

Harness: `LiquidityBot.__new__(LiquidityBot)` stub-bot pattern established
by tests/test_exit_starvation.py, tests/test_conviction_integration.py,
tests/test_long_book_integration.py - real, cheap engine instances
(PositionSizer/InventoryManager/ProfitTierEngine/LeverageGovernor) with
everything else hand-set. Section 1's full-engine proof mirrors
tests/test_context_integration.py's mocked-feeds harness
(`_force_confirmed_signals` + a real LiquidityBot over MockOKX/
MockBinanceUS/MockKraken).
"""
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pytest

from core.config_guard import validate
from core.persistence import position_from_dict, position_to_dict
from core.state import PortfolioState, Position
from execution.inventory import InventoryManager
from ml.features import FEATURE_NAMES
from ml.history import (LABEL_ERA_TRIPLE_BARRIER, HistoryStore,
                        label_era_of)
from ml.labeling import barrier_geometry
from regime.liquidity_regime import LiquidityState
from regime.macro_regime import DEFAULT_PLAYBOOKS, MacroRegimeState
from regime.vol_regime import VolState
from risk.leverage import LeverageGovernor
from risk.position_sizer import PositionSizer

EPS = 1e-9

# ---------------------------------------------------------------------------
# shared fixtures (mirrors tests/test_sizer_derived_bar.py's fixture shape)
# ---------------------------------------------------------------------------
PROFIT_CFG = {"tier_1": {"trigger_pct_gain": 1.0, "close_pct_of_position": 25},
              "tier_2": {"trigger_pct_gain": 2.0, "close_pct_of_position": 25},
              "tier_3": {"trigger_pct_gain": 3.5, "close_pct_of_position": 25},
              "tier_4": {"trigger_pct_gain": 5.0, "close_pct_of_position": 25}}
RISK_CFG = {"stop_loss_pct": 2.0}
PRETRADE_CFG = {"maker_fee_bps": 25.0, "taker_fee_bps": 40.0,
                "min_order_usd": 15}
EQUITY = 5000.0


def _sizer(**over):
    cfg = {"min_p_win": 0.55, "entry_cooldown_min": 0, "min_ticket_usd": 15}
    cfg.update(over)
    return PositionSizer(cfg, PROFIT_CFG, RISK_CFG, pretrade_cfg=PRETRADE_CFG)


def _lev():
    state = PortfolioState(starting_capital=EQUITY)
    return LeverageGovernor({"use_margin": False}).decide(
        state, {}, EQUITY, 60.0, 2.0, 0.0)


def _bull():
    return MacroRegimeState("ETH", label="bull_quiet",
                            playbook=dict(DEFAULT_PLAYBOOKS["bull_quiet"]))


def _bracket_bot(*, bracket_enabled=True, pt_mult=8.0, sl_mult=6.0,
                 pt_cost_mult=4.0, label_max_bars=96, sizer=None):
    """Minimal stub for `_bracket_for_entry` - real PositionSizer/
    InventoryManager, everything else the method touches hand-set."""
    from main import LiquidityBot
    bot = LiquidityBot.__new__(LiquidityBot)
    bot._bracket_exits_enabled = bracket_enabled
    bot._label_pt_vol_mult = pt_mult
    bot._label_sl_vol_mult = sl_mult
    bot._label_pt_cost_mult = pt_cost_mult
    bot._label_max_bars = label_max_bars
    bot.state = PortfolioState(starting_capital=EQUITY)
    bot.sizer = sizer or _sizer()
    bot.inventory = InventoryManager({})
    bot.monitor = types.SimpleNamespace(kelly_mult=1.0)
    bot.marks = {}
    return bot


def _pass1(bot, *, price=2000.0, p_win=0.75, vol_state=None):
    vol_state = vol_state or VolState("ETH", sigma_bar_pct=0.3)
    return bot.sizer.size(
        "ETH", "long", price, p_win, EQUITY, bot.state, _bull(), vol_state,
        LiquidityState("ETH"), 1.0, bot.inventory, _lev(), bot.marks)


# ===========================================================================
# Behavior 1: entry computes + stamps the bracket
# ===========================================================================

def test_bracket_for_entry_computes_barrier_geometry_and_stamps_deadline():
    """Non-floored case: sigma_bar_pct=0.3 (frac 0.003), cost 50bps
    (0.5%), pt_mult=8/sl_mult=6/pt_cost_mult=4.0 -> sigma_eff stays
    0.003 (0.003 > 4.0*0.005/8=0.0025) -> pt=2.4%, sl=1.8% exactly."""
    bot = _bracket_bot()
    vol_state = VolState("ETH", sigma_bar_pct=0.3)
    sized1 = _pass1(bot, vol_state=vol_state)
    decision = types.SimpleNamespace(est_cost_bps=50.0, size_units=sized1.units)
    now = 1_700_000_000.0
    pt, sl, deadline, sized2, reasons = bot._bracket_for_entry(
        asset="ETH", symbol="ETH/USD", direction="long", price=2000.0,
        p_win=0.75, equity=EQUITY, macro_state=_bull(), vol_state=vol_state,
        liq_state=LiquidityState("ETH"),
        verdict=types.SimpleNamespace(risk_multiplier=1.0),
        lev_decision=_lev(), now=now, decision=decision, explored=False,
        aggressive=False, explore_scale=1.0, manip_scale=1.0, sized=sized1)
    assert abs(pt - 0.024) < 1e-9
    assert abs(sl - 0.018) < 1e-9
    assert deadline == now + 96 * 300.0          # BAR_SECONDS = 300
    assert sized2 is not None and sized2.approved
    assert reasons == []
    # cross-checked against the shared helper directly
    pt2, sl2 = barrier_geometry(0.003, 0.5, 8.0, 6.0, 4.0)
    assert abs(pt - pt2) < 1e-12 and abs(sl - sl2) < 1e-12


def test_bracket_for_entry_floored_case_matches_shared_helper():
    """Low vol: sigma_bar_pct=0.1 (frac 0.001) floors to sigma_eff=0.0025
    -> pt=2.0%, sl=1.5% (the shipped-config floor numbers)."""
    bot = _bracket_bot()
    vol_state = VolState("ETH", sigma_bar_pct=0.1)
    sized1 = _pass1(bot, vol_state=vol_state)
    decision = types.SimpleNamespace(est_cost_bps=50.0, size_units=sized1.units)
    pt, sl, deadline, sized2, reasons = bot._bracket_for_entry(
        asset="ETH", symbol="ETH/USD", direction="long", price=2000.0,
        p_win=0.75, equity=EQUITY, macro_state=_bull(), vol_state=vol_state,
        liq_state=LiquidityState("ETH"),
        verdict=types.SimpleNamespace(risk_multiplier=1.0),
        lev_decision=_lev(), now=1000.0, decision=decision, explored=False,
        aggressive=False, explore_scale=1.0, manip_scale=1.0, sized=sized1)
    assert abs(pt - 0.02) < 1e-9
    assert abs(sl - 0.015) < 1e-9


def test_bracket_for_entry_rescales_decision_size_units_to_pass2_notional():
    """decision.size_units (the participation-clamped PASS-1 amount) must
    scale by the SAME ratio PASS-2's units bear to PASS-1's - never a
    re-run of the pretrade gate.

    T5 review IMPORTANT-1 note: sigma_bar_pct=0.6 (not the floored 0.1
    case - see test_bracket_for_entry_upward_rescale_is_clamped_to_
    pass1_ceiling below, which owns that upward/clamped scenario) gives a
    genuine DOWNWARD rescale here, so this test keeps proving the ratio
    is a real, non-trivial multiplier that threads through to
    decision.size_units - not accidentally exercising the ceiling
    clamp's cap."""
    bot = _bracket_bot()
    vol_state = VolState("ETH", sigma_bar_pct=0.6)   # sl=3.6% > stop_loss_pct_ref
    sized1 = _pass1(bot, vol_state=vol_state)
    assert sized1.approved and sized1.units > 0
    # simulate a participation-clamp: decision.size_units is HALF of sized1
    decision = types.SimpleNamespace(est_cost_bps=50.0,
                                     size_units=sized1.units * 0.5)
    pt, sl, deadline, sized2, reasons = bot._bracket_for_entry(
        asset="ETH", symbol="ETH/USD", direction="long", price=2000.0,
        p_win=0.75, equity=EQUITY, macro_state=_bull(), vol_state=vol_state,
        liq_state=LiquidityState("ETH"),
        verdict=types.SimpleNamespace(risk_multiplier=1.0),
        lev_decision=_lev(), now=1000.0, decision=decision, explored=False,
        aggressive=False, explore_scale=1.0, manip_scale=1.0, sized=sized1)
    assert pt > 0.0 and sl > 0.0
    assert sized2 is not None and sized2 is not sized1
    # the bracket's own b_net_trade genuinely differs from the legacy
    # tier-average b_net at this floor -> PASS-2's notional is NOT
    # PASS-1's (a non-trivial ratio, not a vacuous 1.0x check)
    assert sized2.units < sized1.units, (
        "fixture must reproduce a genuine downward rescale (ratio < 1.0) "
        "or this test can no longer distinguish 'ratio threaded through' "
        "from 'ratio clamped at the ceiling'")
    expected_ratio = sized2.units / sized1.units
    assert abs(decision.size_units - sized1.units * 0.5 * expected_ratio) < 1e-6


def test_bracket_for_entry_upward_rescale_is_clamped_to_pass1_ceiling():
    """T5 review IMPORTANT-1: PASS-1's `sized`/`decision.size_units` is the
    entry's ONE approval against the participation/impact/EV cost stack
    (pretrade.evaluate()) - a CEILING. A FLOORED bracket (sigma_bar_pct=0.1
    -> sl=1.5% < stop_loss_pct_ref=2.0%) inflates PASS-2's notional via
    risk-in-size (stop_loss_pct_ref/sl_pct, risk/position_sizer.py) -
    measured 1.46x at this exact fixture (the reviewer's own number).
    decision.size_units must never be scaled ABOVE what PASS-1 approved;
    only downscale is allowed."""
    bot = _bracket_bot()
    vol_state = VolState("ETH", sigma_bar_pct=0.1)
    sized1 = _pass1(bot, vol_state=vol_state)
    decision = types.SimpleNamespace(est_cost_bps=50.0, size_units=sized1.units)
    pt, sl, deadline, sized2, reasons = bot._bracket_for_entry(
        asset="ETH", symbol="ETH/USD", direction="long", price=2000.0,
        p_win=0.75, equity=EQUITY, macro_state=_bull(), vol_state=vol_state,
        liq_state=LiquidityState("ETH"),
        verdict=types.SimpleNamespace(risk_multiplier=1.0),
        lev_decision=_lev(), now=1000.0, decision=decision, explored=False,
        aggressive=False, explore_scale=1.0, manip_scale=1.0, sized=sized1)
    assert sized2 is not None and sized2.units > sized1.units * 1.4, (
        "fixture must reproduce the reviewer's upward-rescale case "
        "(bracket-driven notional materially ABOVE PASS-1's) or this "
        "test proves nothing")
    assert decision.size_units <= sized1.units + 1e-9, (
        "PASS-1's approval is a CEILING: a bracket whose risk-in-size "
        "wants MORE notional must never grow decision.size_units past "
        "what the pretrade gate already cleared (ratio clamped <= 1.0)")
    # T8 nit (carried from T5 review): the <= above also passes on an
    # accidental additional downscale - pin the EXACT clamped case too.
    # rescale_ratio = min(bracket_units/pass1_units, 1.0) clamps to
    # EXACTLY 1.0 here (bracket wants > 1.4x), so decision.size_units
    # (seeded at sized1.units, multiplied by that exact 1.0) must equal
    # the PASS-1 approved units bit-for-bit, not merely bound it.
    assert decision.size_units == sized1.units, (
        "clamped case must reproduce PASS-1's approved units EXACTLY "
        "(ratio pinned at 1.0), not just fall under the ceiling")


def test_bracket_for_entry_downward_rescale_is_unaffected_by_the_clamp():
    """Companion to the ceiling test above: an ordinary DOWNWARD rescale
    (bracket-driven notional smaller than PASS-1's) must still shrink
    decision.size_units exactly as before - the clamp only caps growth."""
    bot = _bracket_bot()
    vol_state = VolState("ETH", sigma_bar_pct=0.6)   # sl=3.6% > stop_loss_pct_ref=2.0%
    sized1 = _pass1(bot, vol_state=vol_state)
    decision = types.SimpleNamespace(est_cost_bps=50.0, size_units=sized1.units)
    pt, sl, deadline, sized2, reasons = bot._bracket_for_entry(
        asset="ETH", symbol="ETH/USD", direction="long", price=2000.0,
        p_win=0.75, equity=EQUITY, macro_state=_bull(), vol_state=vol_state,
        liq_state=LiquidityState("ETH"),
        verdict=types.SimpleNamespace(risk_multiplier=1.0),
        lev_decision=_lev(), now=1000.0, decision=decision, explored=False,
        aggressive=False, explore_scale=1.0, manip_scale=1.0, sized=sized1)
    assert sized2 is not None and sized2.units < sized1.units, (
        "fixture must reproduce a genuine downward rescale or this test "
        "proves nothing")
    expected = sized1.units * (sized2.units / sized1.units)
    assert abs(decision.size_units - expected) < 1e-9


def test_bracket_for_entry_probe_path_also_computes_bracket():
    """Operator decision 1 (spec D1): ALL model-lane entries - conviction
    AND probes - trade the bracket. explored=True must not change the
    geometry computed (only floor_to_min feeds the sizer differently)."""
    bot = _bracket_bot()
    vol_state = VolState("ETH", sigma_bar_pct=0.3)
    sized1 = _pass1(bot, vol_state=vol_state, p_win=0.70)
    decision = types.SimpleNamespace(est_cost_bps=50.0, size_units=sized1.units)
    pt, sl, deadline, sized2, reasons = bot._bracket_for_entry(
        asset="ETH", symbol="ETH/USD", direction="long", price=2000.0,
        p_win=0.70, equity=EQUITY, macro_state=_bull(), vol_state=vol_state,
        liq_state=LiquidityState("ETH"),
        verdict=types.SimpleNamespace(risk_multiplier=1.0),
        lev_decision=_lev(), now=1000.0, decision=decision, explored=True,
        aggressive=False, explore_scale=0.25, manip_scale=1.0, sized=sized1)
    assert pt > 0.0 and sl > 0.0 and sized2 is not None
    assert abs(pt - 0.024) < 1e-9         # identical geometry to conviction


def test_bracket_for_entry_disabled_is_legacy_inert():
    """bracket_exits.enabled=false -> zero fractions, `sized` returned
    UNCHANGED (same object), decision.size_units untouched."""
    bot = _bracket_bot(bracket_enabled=False)
    vol_state = VolState("ETH", sigma_bar_pct=0.3)
    sized1 = _pass1(bot, vol_state=vol_state)
    decision = types.SimpleNamespace(est_cost_bps=50.0, size_units=sized1.units)
    orig_units = decision.size_units
    pt, sl, deadline, sized2, reasons = bot._bracket_for_entry(
        asset="ETH", symbol="ETH/USD", direction="long", price=2000.0,
        p_win=0.75, equity=EQUITY, macro_state=_bull(), vol_state=vol_state,
        liq_state=LiquidityState("ETH"),
        verdict=types.SimpleNamespace(risk_multiplier=1.0),
        lev_decision=_lev(), now=1000.0, decision=decision, explored=False,
        aggressive=False, explore_scale=1.0, manip_scale=1.0, sized=sized1)
    assert (pt, sl, deadline) == (0.0, 0.0, 0.0)
    assert sized2 is sized1
    assert decision.size_units == orig_units
    assert reasons == []


def test_bracket_for_entry_veto_signals_none_sized():
    """An extreme sl (huge cost relative to a tiny pt) can drive net-Kelly
    below the sizer's bar - the caller must see sized=None + reasons, the
    SAME contract as an ordinary sizer veto."""
    bot = _bracket_bot(pt_mult=0.5, sl_mult=6.0, pt_cost_mult=0.0)
    vol_state = VolState("ETH", sigma_bar_pct=5.0)     # huge sigma, no floor
    sized1 = _pass1(bot, vol_state=vol_state, p_win=0.56)
    decision = types.SimpleNamespace(est_cost_bps=50.0,
                                     size_units=sized1.units if sized1.approved
                                     else 1.0)
    pt, sl, deadline, sized2, reasons = bot._bracket_for_entry(
        asset="ETH", symbol="ETH/USD", direction="long", price=2000.0,
        p_win=0.56, equity=EQUITY, macro_state=_bull(), vol_state=vol_state,
        liq_state=LiquidityState("ETH"),
        verdict=types.SimpleNamespace(risk_multiplier=1.0),
        lev_decision=_lev(), now=1000.0, decision=decision, explored=False,
        aggressive=False, explore_scale=1.0, manip_scale=1.0, sized=sized1)
    assert sized2 is None
    assert reasons


# ---- _handle_fill stamping -------------------------------------------------

def _fill_bot():
    from main import LiquidityBot
    bot = LiquidityBot.__new__(LiquidityBot)
    bot.state = PortfolioState(starting_capital=EQUITY)
    bot.config = {"long_book": {}}
    bot._pos_thales = {}
    bot.postmortem = types.SimpleNamespace(note_fill=lambda *a, **k: None)
    bot.history = types.SimpleNamespace(log_entry=lambda *a, **k: None)
    bot._asset_of = lambda s: s.split("/")[0]
    bot._px = lambda s, p: f"{p:.2f}"
    bot._ledger_fill = lambda *a, **k: None
    return bot


class _Order:
    def __init__(self, **kw):
        self.position_id = kw.get("position_id")
        self.symbol = kw["symbol"]
        self.side = kw["side"]
        self.purpose = kw.get("purpose", "entry")
        self.leverage = kw.get("leverage", 1.0)
        self.meta = kw.get("meta", {})
        self.fees_usd = kw.get("fees_usd", 0.0)


class _Event:
    def __init__(self, order, fill_size, fill_price):
        self.order = order
        self.fill_size = fill_size
        self.fill_price = fill_price


def test_handle_fill_stamps_bracket_fields_from_order_meta():
    bot = _fill_bot()
    order = _Order(position_id="p1", symbol="ETH/USD", side="buy",
                   meta={"features": np.zeros(len(FEATURE_NAMES)), "bracket_pt_frac": 0.024,
                         "bracket_sl_frac": 0.018,
                         "bracket_deadline_ts": 123456.0})
    ev = _Event(order, 1.0, 2000.0)
    bot._handle_fill(ev, now=1000.0)
    pos = bot.state.get_position("p1")
    assert pos.bracket_pt_frac == pytest.approx(0.024)
    assert pos.bracket_sl_frac == pytest.approx(0.018)
    assert pos.bracket_deadline_ts == pytest.approx(123456.0)
    # sl leg: stop_price = entry*(1 - sl_frac) for a long
    assert pos.stop_price == pytest.approx(2000.0 * (1 - 0.018))


def test_handle_fill_short_bracket_stop_price_is_above_entry():
    bot = _fill_bot()
    order = _Order(position_id="p2", symbol="ETH/USD", side="sell",
                   meta={"features": np.zeros(len(FEATURE_NAMES)), "bracket_pt_frac": 0.02,
                         "bracket_sl_frac": 0.015,
                         "bracket_deadline_ts": 1.0})
    ev = _Event(order, 1.0, 2000.0)
    bot._handle_fill(ev, now=1000.0)
    pos = bot.state.get_position("p2")
    assert pos.direction == "short"
    assert pos.stop_price == pytest.approx(2000.0 * (1 + 0.015))


def test_handle_fill_no_bracket_meta_is_legacy_inert(monkeypatch):
    """No bracket_* keys in order.meta (pre-T5 order, or bracket_exits
    disabled) -> Position fields default 0.0 and stop_price falls back to
    the legacy config-derived _stop_price_for path."""
    bot = _fill_bot()
    bot._stop_price_for = lambda direction, entry, asset: 1900.0
    order = _Order(position_id="p3", symbol="ETH/USD", side="buy",
                   meta={"features": np.zeros(len(FEATURE_NAMES))})
    ev = _Event(order, 1.0, 2000.0)
    bot._handle_fill(ev, now=1000.0)
    pos = bot.state.get_position("p3")
    assert (pos.bracket_pt_frac, pos.bracket_sl_frac,
           pos.bracket_deadline_ts) == (0.0, 0.0, 0.0)
    assert pos.stop_price == 1900.0


# ===========================================================================
# Behavior 4 (checked alongside 1): core/state.py + core/persistence.py
# ===========================================================================

def test_position_bracket_fields_default_zero():
    p = Position("p", "ETH/USD", "long", 2000.0, 1.0, 1.0,
                datetime.now(timezone.utc))
    assert (p.bracket_pt_frac, p.bracket_sl_frac,
           p.bracket_deadline_ts) == (0.0, 0.0, 0.0)


def test_persistence_round_trips_bracket_fields():
    p = Position("p", "ETH/USD", "long", 2000.0, 1.0, 1.0,
                datetime.now(timezone.utc))
    p.bracket_pt_frac, p.bracket_sl_frac, p.bracket_deadline_ts = \
        0.024, 0.018, 555.0
    d = position_to_dict(p)
    back = position_from_dict(d)
    assert (back.bracket_pt_frac, back.bracket_sl_frac,
           back.bracket_deadline_ts) == (0.024, 0.018, 555.0)


def test_persistence_defaults_bracket_fields_for_legacy_snapshot():
    p = Position("p", "ETH/USD", "long", 2000.0, 1.0, 1.0,
                datetime.now(timezone.utc))
    d = position_to_dict(p)
    del d["bracket_pt_frac"], d["bracket_sl_frac"], d["bracket_deadline_ts"]
    back = position_from_dict(d)
    assert (back.bracket_pt_frac, back.bracket_sl_frac,
           back.bracket_deadline_ts) == (0.0, 0.0, 0.0)


# ===========================================================================
# Behavior 3: close reasons thread verbatim into the live-label barrier
# ===========================================================================

def test_log_close_default_barrier_is_realized_legacy_call(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    hs.log_entry("p1", "ETH", "long", np.zeros(len(FEATURE_NAMES)))
    hs.log_close("p1", 5.0)                        # no barrier kwarg at all
    import csv
    with open(hs.path, encoding="utf-8") as f:
        row = list(csv.DictReader(f))[0]
    assert row["barrier"] == "realized"
    assert row["label_era"] != LABEL_ERA_TRIPLE_BARRIER


@pytest.mark.parametrize("reason", ["tb_pt", "tb_sl", "tb_time"])
def test_log_close_threads_bracket_reason_verbatim_into_tb_era(
        tmp_path, reason):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    hs.log_entry("p1", "ETH", "long", np.zeros(len(FEATURE_NAMES)))
    hs.log_close("p1", 5.0, barrier=reason, pt_frac=0.02, sl_frac=0.015)
    import csv
    with open(hs.path, encoding="utf-8") as f:
        row = list(csv.DictReader(f))[0]
    assert row["barrier"] == reason
    assert label_era_of(row["barrier"]) == LABEL_ERA_TRIPLE_BARRIER
    assert float(row["pt_frac"]) == pytest.approx(0.02)
    assert float(row["sl_frac"]) == pytest.approx(0.015)


def test_log_close_non_bracket_reason_never_leaks_into_barrier(tmp_path):
    """_finalize_position only ever passes tb_pt/tb_sl/tb_time verbatim -
    any other exit reason ("hard stop", "tier 1", ratchet strings, ...)
    must fall back to "realized", never pollute the barrier column with
    a human-readable string label_era_of doesn't recognize."""
    hs = HistoryStore(str(tmp_path / "h.csv"))
    hs.log_entry("p1", "ETH", "long", np.zeros(len(FEATURE_NAMES)))
    hs.log_close("p1", 5.0, barrier="hard stop")
    import csv
    with open(hs.path, encoding="utf-8") as f:
        row = list(csv.DictReader(f))[0]
    assert row["barrier"] == "hard stop"    # log_close itself is a thin
    # passthrough - the "never anything but tb_*/realized" discipline is
    # main._finalize_position's job, covered by the two tests below.


def _finalize_bot(tmp_path):
    from main import LiquidityBot
    bot = LiquidityBot.__new__(LiquidityBot)
    bot.history = HistoryStore(str(tmp_path / "h.csv"))
    bot.perf = types.SimpleNamespace(record_close=lambda *a, **k: None)
    bot.breaker = types.SimpleNamespace(record_close=lambda *a, **k: False)
    bot.postmortem = types.SimpleNamespace(on_close=lambda *a, **k: None)
    bot.state = PortfolioState(starting_capital=EQUITY)
    bot._pos_thales = {}
    bot.thales = types.SimpleNamespace(note_outcome=lambda *a, **k: None)
    bot._stop_hit = {}
    bot._exit_attempts = {}
    bot.macro = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(label="range"))
    bot.liq = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(label="liquid"))
    bot.ladder = types.SimpleNamespace(note_exit=lambda a: None)
    bot._asset_of = lambda s: s.split("/")[0]
    return bot


def _finalize_pos(**bracket_kw):
    p = Position("p1", "ETH/USD", "long", 2000.0, 1.0, 1.0,
                datetime.now(timezone.utc))
    for k, v in bracket_kw.items():
        setattr(p, k, v)
    return p


@pytest.mark.parametrize("reason", ["tb_pt", "tb_sl", "tb_time"])
def test_finalize_position_threads_bracket_reason_into_tb_era(
        tmp_path, reason):
    bot = _finalize_bot(tmp_path)
    pos = _finalize_pos(bracket_pt_frac=0.02, bracket_sl_frac=0.015)
    bot.history.log_entry(pos.position_id, "ETH", "long", np.zeros(len(FEATURE_NAMES)))
    bot._finalize_position(pos, 5.0, 1000.0, close_reason=reason)
    import csv
    with open(bot.history.path, encoding="utf-8") as f:
        row = list(csv.DictReader(f))[0]
    assert row["barrier"] == reason
    assert label_era_of(row["barrier"]) == LABEL_ERA_TRIPLE_BARRIER
    assert float(row["pt_frac"]) == pytest.approx(0.02)


def test_finalize_position_overlay_reason_falls_back_to_realized(tmp_path):
    """A senior-overlay close (give-back "tier trail", hard stop, ...) on
    a BRACKET position must NOT thread its human-readable reason into the
    barrier column - only the exact tb_pt/tb_sl/tb_time strings ever do."""
    bot = _finalize_bot(tmp_path)
    pos = _finalize_pos(bracket_pt_frac=0.02, bracket_sl_frac=0.015)
    bot.history.log_entry(pos.position_id, "ETH", "long", np.zeros(len(FEATURE_NAMES)))
    bot._finalize_position(pos, 5.0, 1000.0, close_reason="tier trail")
    import csv
    with open(bot.history.path, encoding="utf-8") as f:
        row = list(csv.DictReader(f))[0]
    assert row["barrier"] == "realized"
    assert label_era_of(row["barrier"]) != LABEL_ERA_TRIPLE_BARRIER
    # pt_frac/sl_frac still thread even though barrier stayed "realized"
    # (T5: "thread bracket values into live-close rows too")
    assert float(row["pt_frac"]) == pytest.approx(0.02)


def test_finalize_position_default_close_reason_is_realized(tmp_path):
    """The dust-flat call site's default (close_reason="") reproduces the
    legacy hardcoded "realized" tag - byte-identical to pre-T5."""
    bot = _finalize_bot(tmp_path)
    pos = _finalize_pos()
    bot.history.log_entry(pos.position_id, "ETH", "long", np.zeros(len(FEATURE_NAMES)))
    bot._finalize_position(pos, 5.0, 1000.0)
    import csv
    with open(bot.history.path, encoding="utf-8") as f:
        row = list(csv.DictReader(f))[0]
    assert row["barrier"] == "realized"


# ===========================================================================
# Behavior 2: exit evaluation - bracket replaces the tier engine (never
# both), overlays (give-back ratchet) stay senior
# ===========================================================================

TIERS_HIGH = {
    "tier_1": {"trigger_pct_gain": 50.0, "close_pct_of_position": 25},
    "tier_2": {"trigger_pct_gain": 60.0, "close_pct_of_position": 25},
    "tier_3": {"trigger_pct_gain": 70.0, "close_pct_of_position": 25},
    "tier_4": {"trigger_pct_gain": 80.0, "close_pct_of_position": 25},
    "vol_scaled": False,
    "trailing_stop": {"enabled": False},
    "give_back": {"enabled": False},
    "time_stop": {"enabled": False},
}

TIERS_LOW_TIER1 = dict(TIERS_HIGH, **{
    "tier_1": {"trigger_pct_gain": 1.0, "close_pct_of_position": 25}})

TIERS_GIVE_BACK = dict(TIERS_HIGH, **{
    "give_back": {"enabled": True, "arm_gain_pct": 1.0, "giveback_frac": 0.5}})


def _exit_bot(tiers_cfg):
    from main import LiquidityBot
    bot = LiquidityBot.__new__(LiquidityBot)
    bot.state = None            # inventory_ratio is stubbed - args unread
    bot.marks = {}
    bot._stop_ok = {}
    bot._mark_ts = {}
    bot._mark_stale_sec = 20.0
    bot._stop_hit = {}
    bot._exit_attempts = {}
    bot.last_signals = {}
    bot.inventory = types.SimpleNamespace(
        inventory_ratio=lambda *a, **k: 0.0, soft_cap_pct=50.0,
        hard_cap_pct=100.0)
    bot.vol = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(sigma_bar_pct=0.5))
    bot.tiers_base = tiers_cfg
    bot._tier_engines = {}
    bot.orders = types.SimpleNamespace(open_orders=lambda: [])
    return bot


def _bracket_pos(direction="long", entry=100.0, pt_frac=0.05, sl_frac=0.02,
                 deadline_ts=0.0, stop_price=None):
    p = Position("p1", "ETH/USD", direction, entry, 1.0, 1.0,
                datetime.now(timezone.utc))
    p.bracket_pt_frac = pt_frac
    p.bracket_sl_frac = sl_frac
    p.bracket_deadline_ts = deadline_ts
    p.stop_price = stop_price if stop_price is not None else (
        entry * (1 - sl_frac) if direction == "long"
        else entry * (1 + sl_frac))
    return p


def _run(bot, pos, px, now=1000.0, equity=EQUITY):
    bot.marks[pos.symbol] = px
    bot._mark_ts[pos.symbol] = now
    macro_states = {"ETH": types.SimpleNamespace(
        playbook={"tier_scale": 1.0})}
    exits = []
    bot._submit_exit = lambda p, pct, reason, **k: exits.append(
        {"reason": reason, "pct": pct, **k})
    bot._manage_open_position(pos, now, equity, macro_states)
    return exits


def test_bracket_pt_leg_fires_maker_first_profit_exit_long():
    bot = _exit_bot(TIERS_HIGH)
    pos = _bracket_pos(pt_frac=0.05, sl_frac=0.02)   # entry 100, pt=105
    exits = _run(bot, pos, px=105.5)                 # above the pt target
    assert len(exits) == 1
    assert exits[0]["reason"] == "tb_pt"
    assert exits[0]["pct"] == 100.0
    assert exits[0].get("profit_take") is True


def test_bracket_pt_leg_fires_for_short():
    bot = _exit_bot(TIERS_HIGH)
    pos = _bracket_pos(direction="short", entry=100.0, pt_frac=0.05,
                       sl_frac=0.02)                 # pt = 95
    exits = _run(bot, pos, px=94.0)
    assert exits and exits[0]["reason"] == "tb_pt"


def test_bracket_sl_leg_fires_via_stop_price_reason_tb_sl():
    bot = _exit_bot(TIERS_HIGH)
    pos = _bracket_pos(pt_frac=0.05, sl_frac=0.02)   # stop = 98
    exits = _run(bot, pos, px=97.5)                  # below the sl level
    assert len(exits) == 1
    assert exits[0]["reason"] == "tb_sl"
    assert exits[0]["pct"] == 100.0


def test_bracket_deadline_fires_tb_time_when_no_leg_hit():
    bot = _exit_bot(TIERS_HIGH)
    pos = _bracket_pos(pt_frac=0.05, sl_frac=0.02, deadline_ts=900.0)
    exits = _run(bot, pos, px=101.0, now=1000.0)     # past deadline_ts=900
    assert len(exits) == 1
    assert exits[0]["reason"] == "tb_time"
    assert exits[0]["pct"] == 100.0


def test_bracket_no_exit_before_deadline_and_within_brackets():
    bot = _exit_bot(TIERS_HIGH)
    pos = _bracket_pos(pt_frac=0.05, sl_frac=0.02, deadline_ts=2000.0)
    exits = _run(bot, pos, px=101.0, now=1000.0)     # before deadline
    assert exits == []


def test_bracket_replaces_tier_engine_scheduled_profit_take():
    """A tier-1 trigger that WOULD fire for a legacy position (1% gain)
    must be suppressed for a bracket position whose own pt (5%) hasn't
    been reached yet - never both, and no phantom exit either."""
    bot = _exit_bot(TIERS_LOW_TIER1)
    pos = _bracket_pos(pt_frac=0.05, sl_frac=0.10)   # pt=105, sl=90 (wide,
    # never touched at px=101.5)
    exits = _run(bot, pos, px=101.5, now=1000.0)     # 1.5% gain: clears
    # tier-1's 1% trigger, but not the bracket's 5% pt
    assert exits == [], (
        "the tier engine's tier-1 profit-take must be suppressed for a "
        "bracket position, and the bracket's own pt/deadline legs have "
        "not fired yet - asserting NO exit proves the replacement, not "
        "just a differently-labeled one")


def test_non_bracket_position_still_fires_the_legacy_tier_trigger():
    """Contrast case for the test above: the SAME tier-1 config, on a
    NON-bracket position (bracket_pt_frac=0.0), must fire normally -
    proves the suppression above is bracket-gated, not a global change."""
    bot = _exit_bot(TIERS_LOW_TIER1)
    pos = Position("p1", "ETH/USD", "long", 100.0, 1.0, 1.0,
                  datetime.now(timezone.utc))
    exits = _run(bot, pos, px=101.5, now=1000.0)
    assert len(exits) == 1
    assert exits[0]["reason"] == "tier 1"
    assert exits[0].get("profit_take") is True


def test_give_back_ratchet_still_fires_on_a_bracket_position():
    """Overlays (spec D1: give-back/chandelier ratchet) stay SENIOR to
    the bracket - a two-cycle arm-then-trigger sequence must close via
    the tier engine's OWN reason ("tier trail"), never tb_pt/tb_time,
    proving the ratchet pre-empts the bracket's own checks that same
    cycle. entry=100, arm_gain_pct=1.0%, giveback_frac=0.5: cycle 1 at
    px=102 arms (high_water=102, gb floor=101, not yet crossed); cycle 2
    at px=100.5 crosses back through the 101 floor."""
    bot = _exit_bot(TIERS_GIVE_BACK)
    pos = _bracket_pos(pt_frac=0.10, sl_frac=0.10)   # both far from px
    exits1 = _run(bot, pos, px=102.0, now=1000.0)
    assert exits1 == [], "cycle 1 only ARMS the ratchet, no exit yet"
    exits2 = _run(bot, pos, px=100.5, now=1005.0)
    assert len(exits2) == 1
    assert exits2[0]["reason"] == "tier trail"
    assert exits2[0]["reason"] not in ("tb_pt", "tb_sl", "tb_time")
    assert exits2[0].get("profit_take") is not True


TIERS_LOW_TIER1_OCCLUDED_GIVE_BACK = dict(TIERS_LOW_TIER1, **{
    "give_back": {"enabled": True, "arm_gain_pct": 2.0, "giveback_frac": 0.2}})


def test_give_back_floor_fires_in_the_tier1_occluded_band():
    """T5 review IMPORTANT-2: ProfitTierEngine.evaluate() returns EARLY on
    the tier-1 trigger (gain_pct >= 1%) BEFORE it ever reaches
    _exit_floor_hit - and tier_closed never advances for a bracket
    position (the scheduled take that would advance it is always
    suppressed), so that early return recurs EVERY cycle gain stays >=1%.
    An armed give-back floor sitting ABOVE tier-1's own trigger price
    (giveback_frac=0.2 keeps 80% of a 2% peak -> floor=101.6; tier-1's
    trigger price is 101) would otherwise never be checked at all while
    price sits anywhere in [101, 102) - the occluded band the reviewer
    demonstrated (entry 100, floor armable at 102, px 101.5 -> no exit,
    pre-fix). Cycle 1 at px=102 only arms the floor; cycle 2 at px=101.5
    (1.5% gain, still >= tier-1's 1%) has crossed 101.6 and must exit with
    the overlay reason ("tier trail"), never tb_*."""
    bot = _exit_bot(TIERS_LOW_TIER1_OCCLUDED_GIVE_BACK)
    pos = _bracket_pos(pt_frac=0.10, sl_frac=0.10)   # both far from px
    exits1 = _run(bot, pos, px=102.0, now=1000.0)
    assert exits1 == [], "cycle 1 only arms the floor (peak=102 > floor 101.6)"
    exits2 = _run(bot, pos, px=101.5, now=1005.0)
    assert len(exits2) == 1, (
        "the give-back floor crossed at 101.5 (< armed floor 101.6) must "
        "fire even though gain (1.5%) is still >= tier-1's 1% trigger")
    assert exits2[0]["reason"] == "tier trail"
    assert exits2[0]["reason"] not in ("tb_pt", "tb_sl", "tb_time")
    assert exits2[0].get("profit_take") is not True


def test_give_back_floor_not_crossed_in_occluded_band_no_false_exit():
    """Companion to the test above: the SAME occluded-band setup, but
    price stays ABOVE the armed floor (101.7 > 101.6) - no exit fires.
    The fix must not introduce a false positive."""
    bot = _exit_bot(TIERS_LOW_TIER1_OCCLUDED_GIVE_BACK)
    pos = _bracket_pos(pt_frac=0.10, sl_frac=0.10)
    exits1 = _run(bot, pos, px=102.0, now=1000.0)
    assert exits1 == []
    exits2 = _run(bot, pos, px=101.7, now=1005.0)
    assert exits2 == [], "floor (101.6) not crossed at 101.7 - no exit"


def test_bracket_pt_time_stop_suppressed_for_bracket_position():
    """PT-060 time-stop (a tier-engine scratch mechanism) must ALSO be
    suppressed for a bracket position - the bracket's own deadline leg
    owns "give up on a stale thesis" instead."""
    tiers = dict(TIERS_HIGH, **{
        "time_stop": {"enabled": True, "max_bars_no_progress": 1,
                      "min_mfe_frac_of_tier1": 0.99}})
    bot = _exit_bot(tiers)
    pos = _bracket_pos(pt_frac=0.05, sl_frac=0.10, deadline_ts=1e12)
    # bars_in_trade needs opened_at far enough in the past to clear
    # max_bars_no_progress=1 (5m bars) - now far past opened_at
    pos.opened_at = datetime.fromtimestamp(1000.0, tz=timezone.utc)
    exits = _run(bot, pos, px=100.1, now=1000.0 + 3600.0)
    assert exits == [], (
        "time-stop would otherwise scratch this position - suppressed "
        "for a bracket position (deadline_ts=1e12, far future, so the "
        "bracket's own vertical never fires here either)")


def test_disabled_flag_takes_the_legacy_branch():
    """T5 review MINOR-6 rename (was
    test_bracket_mutation_disabling_flag_flips_bracket_branch_off - this
    is a DEFAULT-STATE test, not a mutation check: it never mutates any
    source line, it constructs a position the way bracket_exits.enabled=
    false actually leaves one - bracket_pt_frac at its 0.0 default (no
    entry ever stamps it) - and asserts the is_bracket gate in
    _manage_open_position routes it to the ordinary tier engine. The
    REAL mutation checks (forcing the enabled-flag branch/is_bracket
    condition itself) are run separately, outside pytest, per the task's
    scratchpad-copy-restore protocol."""
    bot = _exit_bot(TIERS_LOW_TIER1)
    pos = Position("p1", "ETH/USD", "long", 100.0, 1.0, 1.0,
                  datetime.now(timezone.utc))
    assert pos.bracket_pt_frac == 0.0
    exits = _run(bot, pos, px=101.5, now=1000.0)
    assert exits and exits[0]["reason"] == "tier 1"


# ===========================================================================
# Behavior 5: guards
# ===========================================================================

def _base_cfg(**over):
    cfg = {
        "ml": {"label_mode": "triple_barrier", "label_pt_cost_mult": 4.0,
              "label_pt_vol_mult": 8.0, "label_sl_vol_mult": 6.0,
              "label_round_trip_cost_pct": 0.5,
              "exploration": {"enabled": True, "p_win": 0.64}},
        "pretrade": {"maker_fee_bps": 25.0, "taker_fee_bps": 40.0},
        "bracket_exits": {"enabled": True},
    }
    for k, v in over.items():
        parts = k.split(".")
        d = cfg
        for p in parts[:-1]:
            d = d.setdefault(p, {})
        d[parts[-1]] = v
    return cfg


def test_fatal_bracket_enabled_with_non_triple_barrier_label_mode():
    cfg = _base_cfg()
    cfg["ml"]["label_mode"] = "exit_policy"
    findings = validate(cfg)
    fatals = [m for sev, m in findings if sev == "FATAL"]
    assert any("bracket_exits.enabled" in m for m in fatals)


def test_bracket_enabled_with_triple_barrier_is_not_fatal():
    cfg = _base_cfg()
    findings = validate(cfg)
    fatals = [m for sev, m in findings if sev == "FATAL"
             if "bracket_exits" in m]
    assert fatals == []


def test_bracket_disabled_never_fatals_regardless_of_label_mode():
    cfg = _base_cfg()
    cfg["bracket_exits"]["enabled"] = False
    cfg["ml"]["label_mode"] = "exit_policy"
    findings = validate(cfg)
    fatals = [m for sev, m in findings if sev == "FATAL"
             if "bracket_exits" in m]
    assert fatals == []


def test_probe_clearance_worst_case_bracket_bar_pins_shipped_number():
    """The shipped config.json numbers (pt_cost_mult=4.0, rt_cost_pct=0.5,
    fees 25/40bps) must compute the worst-case floored-bracket bar to
    0.614 (spec D2's own worked example), COMPUTED here from the guard's
    inputs, never hardcoded in the guard itself.

    T5 review MINOR-7 strengthening: the arithmetic above only proves
    THIS test's own hand-derivation is self-consistent - it never called
    validate(), so it never actually pinned the GUARD's internal number.
    Mirrors tests/test_config_guard_min_pwin.py's
    test_probe_clearance_interlock_warns_before_the_trickle_dies pattern:
    push a config's clearance under 0.005 and assert THROUGH validate()'s
    own WARN output that it fires with this SAME hand-derived 0.614."""
    pcm, ptm, slm, lbl_rt = 4.0, 8.0, 6.0, 0.5
    pt_floor_pct = pcm * lbl_rt
    sl_floor_pct = (slm / ptm) * pt_floor_pct
    sizer_rt_pct = (25.0 + 40.0) / 100.0
    b_net_worst = (pt_floor_pct - sizer_rt_pct) / (sl_floor_pct + sizer_rt_pct)
    worst_bar = 1.0 / (1.0 + b_net_worst)
    assert abs(worst_bar - 0.614) < 5e-4

    # close the clearance to just under 0.005 and assert the WARN fires
    # THROUGH validate() with the guard's OWN internally computed
    # worst_bar matching this test's hand-derived 0.614 - not just a
    # coincidental WARN on unrelated numbers.
    cfg = _base_cfg(**{"ml.exploration.p_win": worst_bar + 0.004})
    findings = validate(cfg)
    warns = [m for sev, m in findings if sev == "WARN"
            if "floored-bracket breakeven" in m]
    assert warns, "a margin that closes clearance under 0.005 must WARN"
    assert any(f"{worst_bar:.3f}" in m for m in warns), (
        "the guard's own WARN message must cite the SAME worst_bar this "
        "test hand-derived (0.614), proving validate() computes it "
        "identically rather than off a hardcoded constant")


def test_probe_clearance_warn_fires_below_005_headroom():
    cfg = _base_cfg(**{"ml.exploration.p_win": 0.618})   # 0.618-0.614=0.004
    findings = validate(cfg)
    warns = [m for sev, m in findings if sev == "WARN"
            if "floored-bracket breakeven" in m]
    assert warns, "clearance 0.004 < 0.005 must WARN"


def test_probe_clearance_no_warn_with_shipped_config_headroom():
    cfg = _base_cfg()                                     # p_win=0.64
    findings = validate(cfg)
    warns = [m for sev, m in findings if sev == "WARN"
            if "floored-bracket breakeven" in m]
    assert warns == [], "shipped 0.64 clears 0.614 by 0.026 - no WARN"


def test_probe_clearance_warn_inert_when_floor_disabled():
    cfg = _base_cfg(**{"ml.label_pt_cost_mult": 0.0,
                       "ml.exploration.p_win": 0.51})
    findings = validate(cfg)
    warns = [m for sev, m in findings if sev == "WARN"
            if "floored-bracket breakeven" in m]
    assert warns == [], "pt_cost_mult=0 disables the floor - no worst case"


def test_shipped_config_json_has_zero_bracket_related_fatals():
    import json
    root = Path(__file__).resolve().parents[1]
    cfg = json.loads((root / "config.json").read_text(encoding="utf-8"))
    findings = validate(cfg)
    fatals = [m for sev, m in findings if sev == "FATAL"]
    assert fatals == [], f"shipped config.json must not FATAL: {fatals}"


# ===========================================================================
# Behavior 1 (full-engine proof) + Behavior 4 (legacy byte-identical):
# a REAL LiquidityBot over mocked exchange feeds, driven through the actual
# slow_cycle/fast_cycle entry pipeline (mirrors tests/test_context_
# integration.py's `_force_confirmed_signals` + mocked-feeds harness).
# ===========================================================================
from main import LiquidityBot, load_config  # noqa: E402
from scripts.smoke_test import MockBinanceUS, MockKraken, MockOKX  # noqa: E402
from strategies.signal_gates import SignalResult  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]


def _entry_cfg(*, bracket_enabled=True, force_probe=False):
    cfg = load_config(str(_ROOT / "config.json"))
    cfg["capital_management"]["starting_capital_usd"] = 10_000
    cfg["system"]["dry_run"] = True
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    cfg["context"]["enabled"] = False
    cfg["long_book"]["enabled"] = False
    cfg["bracket_exits"]["enabled"] = bracket_enabled
    cfg["position_sizer"] = dict(cfg.get("position_sizer", {}),
                                entry_cooldown_min=0, min_p_win=0.50)
    # clear net-Kelly + fill realism knobs so a forced confirmed signal
    # reliably produces a real order/fill (tests/test_context_
    # integration.py's own _cfg(force_fill=True) precedent)
    cfg["ml"]["cold_start_prior_p"] = 0.66
    cfg["pretrade"]["min_edge_cost_ratio"] = 0.1
    cfg["pretrade"]["price_exit_leg"] = False
    cfg.setdefault("order_manager", {}).setdefault(
        "sim_fill", {})["queue_aware"] = False
    if force_probe:
        # p_win stays sub-breakeven (conviction alone would never enter);
        # exploration.p_win bumps it just past net-Kelly so a FORCED probe
        # admission (below) is the only thing that lets this signal size.
        cfg["ml"]["cold_start_prior_p"] = 0.30
        cfg["ml"]["exploration"]["enabled"] = True
    return cfg


def _entry_bot(cfg, prices):
    bot = LiquidityBot(cfg, okx=MockOKX(prices), binanceus=MockBinanceUS(prices),
                       kraken=MockKraken(prices), resume=False)
    if hasattr(bot, "context"):
        bot.context.fetch = lambda *a, **k: None
    return bot


def _force_confirmed_signals(bot: LiquidityBot) -> None:
    bot.gates.evaluate_asset = lambda base_asset, view: SignalResult(
        symbol=f"{base_asset}/USD", direction="long", confidence=1.0,
        size=0.0, all_confirmed=True, gates_passed={})


def _drive(bot, n=30, seed=7):
    t = 1_700_000_000.0
    bot.hourly_cycle(t)
    for a in ("ETH", "BTC"):
        st = bot.macro.state(a)
        st.label = "bull_quiet"
        st.playbook = dict(bot.macro.playbooks["bull_quiet"])
        bot.macro._states[a] = st
    rng = np.random.default_rng(seed)
    prices = bot.okx.prices
    for cycle in range(n):
        for a in prices:
            prices[a] *= float(np.exp(rng.normal(0.0006, 0.0035)))
        bot.fast_cycle(t)
        if cycle % 3 == 0:
            bot.slow_cycle(t)
        t += 5.0
    return bot


def test_full_engine_conviction_entry_stamps_bracket_fields(tmp_path,
                                                            monkeypatch):
    monkeypatch.chdir(tmp_path)
    prices = {"ETH": 2000.0, "BTC": 60000.0}
    bot = _entry_bot(_entry_cfg(bracket_enabled=True), prices)
    _force_confirmed_signals(bot)
    _drive(bot, n=30)
    open_5m = [p for p in bot.state.open_positions() if p.book == "5m"]
    assert open_5m, "the forced confirmed signal never produced a fill"
    assert any(p.bracket_pt_frac > 0.0 and p.bracket_sl_frac > 0.0
              and p.bracket_deadline_ts > 0.0 for p in open_5m), (
        "at least one real, engine-driven entry must carry a stamped "
        "bracket when bracket_exits.enabled=true")


def test_full_engine_bracket_disabled_stamps_nothing(tmp_path, monkeypatch):
    """Behavior 4 (byte-identical legacy): the SAME forced-entry harness
    with bracket_exits.enabled=false must never stamp bracket fields -
    the mutation-check partner of the test above."""
    monkeypatch.chdir(tmp_path)
    prices = {"ETH": 2000.0, "BTC": 60000.0}
    bot = _entry_bot(_entry_cfg(bracket_enabled=False), prices)
    _force_confirmed_signals(bot)
    _drive(bot, n=30)
    open_5m = [p for p in bot.state.open_positions() if p.book == "5m"]
    assert open_5m, "the forced confirmed signal never produced a fill"
    assert all(p.bracket_pt_frac == 0.0 and p.bracket_sl_frac == 0.0
              and p.bracket_deadline_ts == 0.0 for p in open_5m)


def test_bracket_exits_key_absent_defaults_to_disabled(tmp_path, monkeypatch):
    """T5 review IMPORTANT-3: main.py's runtime default for
    bracket_exits.enabled must match core/config_guard.py's own default
    (False, core/config_guard.py:~600) - the two had drifted (main.py
    defaulted True), so a config that OMITS the key entirely traded the
    bracket with the coherence FATAL (enabled + non-triple_barrier
    label_mode) never even evaluated. Cheap unit check on the parsed
    attribute, no cycle driving needed."""
    monkeypatch.chdir(tmp_path)
    prices = {"ETH": 2000.0, "BTC": 60000.0}
    cfg = _entry_cfg(bracket_enabled=True)
    del cfg["bracket_exits"]
    bot = _entry_bot(cfg, prices)
    assert bot._bracket_exits_enabled is False


def test_full_engine_bracket_keyless_config_stamps_nothing(tmp_path,
                                                           monkeypatch):
    """Behavior 4 (byte-identical legacy), keyless variant: a config with
    NO bracket_exits key at all must produce the exact same "no bracket
    fields stamped" result as bracket_exits.enabled=false explicitly -
    proving the default flip is really wired end to end, not just the
    parsed attribute."""
    monkeypatch.chdir(tmp_path)
    prices = {"ETH": 2000.0, "BTC": 60000.0}
    cfg = _entry_cfg(bracket_enabled=True)
    del cfg["bracket_exits"]
    bot = _entry_bot(cfg, prices)
    _force_confirmed_signals(bot)
    _drive(bot, n=30)
    open_5m = [p for p in bot.state.open_positions() if p.book == "5m"]
    assert open_5m, "the forced confirmed signal never produced a fill"
    assert all(p.bracket_pt_frac == 0.0 and p.bracket_sl_frac == 0.0
              and p.bracket_deadline_ts == 0.0 for p in open_5m)


def test_full_engine_probe_entry_also_stamps_bracket(tmp_path, monkeypatch):
    """Operator decision 1 (spec D1): probes trade the bracket too. Force
    EVERY admitted entry through the probe path via
    _probe_admission_decision, independent of the exploration RNG roll -
    a real fill under bracket_exits.enabled=true must still carry it."""
    monkeypatch.chdir(tmp_path)
    prices = {"ETH": 2000.0, "BTC": 60000.0}
    bot = _entry_bot(_entry_cfg(bracket_enabled=True, force_probe=True),
                     prices)
    _force_confirmed_signals(bot)
    bot._probe_admission_decision = lambda now, asset, regime_label=None: True
    _drive(bot, n=30)
    open_5m = [p for p in bot.state.open_positions() if p.book == "5m"]
    assert open_5m, "the forced probe signal never produced a fill"
    assert any(p.is_probe for p in open_5m), \
        "the harness must have actually routed at least one entry as a probe"
    assert any(p.is_probe and p.bracket_pt_frac > 0.0 for p in open_5m), (
        "a probe entry must ALSO carry a stamped bracket (operator "
        "decision 1: ALL model-lane entries trade the bracket)")
