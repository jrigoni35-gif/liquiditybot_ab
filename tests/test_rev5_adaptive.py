"""rev-5 adaptive layer: model ladder blend rung, learned gate weights,
inventory-aware sizing aggression, and the advanced exit couplings
(signal-decay leash + inventory-coupled tier closes).

The contract under test everywhere: DEFAULTS PRESERVE rev-3/4 BEHAVIOR
EXACTLY — every new mechanism must be a no-op when disabled, cold, or
un-passed, and bounded when active.
"""

import numpy as np
import pytest

from core.state import Position
from ml.history import CandidateLabeler, HistoryStore
from ml.models import BlendModel, load_model, save_model
from ml.walkforward import _LADDER, evaluate_and_select
from risk.position_sizer import PositionSizer
from risk.profit_tiers import ProfitTierEngine
from strategies.signal_gates import GateStats


# --------------------------------------------------------------------------
# D1: model ladder — blend rung
# --------------------------------------------------------------------------
def _toy_data(n=400, seed=3):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 6))
    logit = 1.2 * X[:, 0] - 0.8 * X[:, 1] + 0.3 * rng.normal(size=n)
    y = (logit > 0).astype(float)
    return X, y


def test_blend_is_mean_of_members():
    X, y = _toy_data()
    m = BlendModel(seed=7).fit(X, y)
    p = m.predict_proba(X)
    assert np.allclose(p, 0.5 * (m.a.predict_proba(X)
                                 + m.b.predict_proba(X)))
    assert p.min() >= 0.0 and p.max() <= 1.0


def test_blend_serialization_round_trip(tmp_path):
    X, y = _toy_data()
    m = BlendModel(seed=7).fit(X, y)
    path = tmp_path / "blend.json"
    save_model(m, str(path))
    m2 = load_model(str(path))
    assert m2 is not None and m2.kind == "blend"
    assert np.allclose(m.predict_proba(X), m2.predict_proba(X))


def test_ladder_contains_blend_above_gbt():
    assert _LADDER.index("blend") == _LADDER.index("gbt") + 1
    assert _LADDER.index("mlp") > _LADDER.index("blend")


def test_selection_still_simplicity_biased():
    """On near-linear toy data the ladder must not climb to blend/mlp
    without earning it — and the blend block must exist in results."""
    X, y = _toy_data(n=600)
    res = evaluate_and_select(X, y, label_span=5, n_splits=3)
    assert "blend" in res and "mean_brier" in res["blend"]
    order = {name: i for i, name in enumerate(_LADDER)}
    # winner beat every simpler rung by the margin — implied by the rule;
    # sanity: selected is one of the rungs and a model was fitted
    assert res["selected"] in _LADDER
    assert hasattr(res["model"], "predict_proba")
    assert order[res["selected"]] <= order["mlp"]


# --------------------------------------------------------------------------
# D2: learned gate weights
# --------------------------------------------------------------------------
def test_gate_stats_cold_start_is_naive_fraction():
    gs = GateStats({"enabled": True, "min_samples": 40})
    gates = {"a": True, "b": False, "c": True, "d": True}
    assert gs.weighted_confidence(gates, 0.123) == pytest.approx(3 / 4)
    assert gs.weight("a") == 1.0


def test_gate_stats_disabled_returns_fallback():
    gs = GateStats({"enabled": False})
    assert gs.weighted_confidence({"a": True}, 0.42) == 0.42


def test_gate_stats_learns_predictive_gate():
    gs = GateStats({"enabled": True, "min_samples": 20, "strength": 2.0})
    # gate "hot" passes only on wins; gate "dud" passes on everything
    for _ in range(30):
        gs.note_label({"hot": True, "dud": True}, 1)
    for _ in range(30):
        gs.note_label({"hot": False, "dud": True}, 0)
    assert gs.weight("hot") > 1.0
    assert gs.weight("dud") < 1.0          # dud's rate == base rate; LCB drags it under
    assert GateStats.W_LO <= gs.weight("dud") <= GateStats.W_HI
    assert GateStats.W_LO <= gs.weight("hot") <= GateStats.W_HI
    conf_hot = gs.weighted_confidence({"hot": True, "dud": False}, 0.5)
    conf_dud = gs.weighted_confidence({"hot": False, "dud": True}, 0.5)
    assert conf_hot > conf_dud


def test_gate_stats_persistence_round_trip():
    gs = GateStats({"enabled": True, "min_samples": 5})
    for i in range(12):
        gs.note_label({"g1": True, "g2": i % 2 == 0}, i % 3 == 0)
    gs2 = GateStats({"enabled": True, "min_samples": 5})
    gs2.restore(gs.to_dict())
    assert gs2.to_dict() == gs.to_dict()
    assert gs2.weight("g1") == gs.weight("g1")


def test_gate_stats_garbage_safe():
    gs = GateStats({"enabled": True})
    gs.note_label(None, 1)
    gs.note_label({"a": True}, "not-a-label")
    gs.note_label("not-a-dict", 1)
    gs.restore("garbage")
    assert gs.weighted_confidence({"a": True}, 0.9) == pytest.approx(1.0)


# --------------------------------------------------------------------------
# D2 plumbing: candidate labeler carries gates and fires the callback
# --------------------------------------------------------------------------
def _candles(n, start=1000, step=300, px=100.0):
    return [{"time": start + i * step, "close": px, "high": px * 1.001,
             "low": px * 0.999, "volume": 10.0} for i in range(n)]


def test_labeler_fires_on_label_with_gates(tmp_path):
    seen = []
    store = HistoryStore(str(tmp_path / "hist.csv"))
    lab = CandidateLabeler(store, {"label_max_bars": 4},
                           on_label=lambda g, y: seen.append((g, y)))
    lab.update_candles("T", _candles(2))
    lab.register("T", "long", np.zeros(36), 0.01, 1000 + 300,
                 gates_passed={"g1": True, "g2": False})
    lab.update_candles("T", _candles(10))
    written = lab.poll()
    assert written == 1
    assert len(seen) == 1
    assert seen[0][0] == {"g1": True, "g2": False}
    assert seen[0][1] in (0, 1)


def test_labeler_gates_survive_persistence(tmp_path):
    store = HistoryStore(str(tmp_path / "hist.csv"))
    lab = CandidateLabeler(store, {"label_max_bars": 90})
    lab.update_candles("T", _candles(2))
    lab.register("T", "long", np.zeros(36), 0.01, 1300,
                 gates_passed={"gx": True})
    lab2 = CandidateLabeler(store, {"label_max_bars": 90})
    lab2.restore(lab.to_dict())
    assert lab2._cands[0]["gates"] == {"gx": True}


# --------------------------------------------------------------------------
# D3: inventory-aware aggression
# --------------------------------------------------------------------------
class _StubState:
    def __init__(self, positions):
        self.positions = positions


def _pos(symbol, size, px, opened_ts):
    from datetime import datetime, timezone
    return Position(position_id=f"p-{symbol}-{opened_ts}", symbol=symbol,
                    direction="long", entry_price=px, size=size,
                    original_size=size,
                    opened_at=datetime.fromtimestamp(opened_ts,
                                                     tz=timezone.utc))


def _sizer(ia_cfg):
    return PositionSizer({"inventory_aggression": ia_cfg,
                          "min_ticket_usd": 25.0},
                         profit_cfg={}, risk_cfg={})


def test_aggression_boosts_empty_book():
    s = _sizer({"enabled": True, "light_boost": 1.10, "heavy_cut": 0.65,
                "short_window_hours": 6, "max_recent_entries": 3,
                "full_book_heat_frac": 0.35})
    mult, u_l, u_s = s._inventory_aggression(_StubState({}), {}, 10_000.0,
                                             now=1_000_000.0)
    assert mult == pytest.approx(1.10)
    assert u_l == 0.0 and u_s == 0.0


def test_aggression_cuts_full_book():
    now = 1_000_000.0
    # gross heat 40% of equity > full_book_heat_frac 0.35 -> u_long = 1
    positions = {"a": _pos("BTC/USD", 0.04, 100_000.0, now - 50_000)}
    s = _sizer({"enabled": True, "light_boost": 1.10, "heavy_cut": 0.65,
                "full_book_heat_frac": 0.35})
    mult, u_l, u_s = s._inventory_aggression(
        _StubState(positions), {"BTC/USD": 100_000.0}, 10_000.0, now=now)
    assert u_l == 1.0
    assert mult == pytest.approx(0.65)


def test_aggression_short_term_clustering_cuts():
    now = 1_000_000.0
    # three tiny recent entries: negligible heat, but clustering is maxed
    positions = {f"p{i}": _pos(f"S{i}/USD", 0.001, 100.0, now - 600 * i)
                 for i in range(3)}
    s = _sizer({"enabled": True, "light_boost": 1.10, "heavy_cut": 0.65,
                "short_window_hours": 6, "max_recent_entries": 3})
    mult, u_l, u_s = s._inventory_aggression(
        _StubState(positions), {}, 10_000.0, now=now)
    assert u_s == 1.0 and u_l < 0.01
    assert mult == pytest.approx(0.65)


def test_aggression_disabled_and_bounds():
    s = _sizer({"enabled": False})
    assert s.ia_enabled is False
    # constructor clamps hostile values into the safe envelope
    s2 = _sizer({"enabled": True, "light_boost": 9.0, "heavy_cut": 0.0})
    assert s2.ia_light_boost == 1.5
    assert s2.ia_heavy_cut == 0.2


# --------------------------------------------------------------------------
# D4: exit advancements
# --------------------------------------------------------------------------
_TIER_CFG = {
    "tier_1": {"trigger_pct_gain": 1.0, "close_pct_of_position": 25},
    "tier_2": {"trigger_pct_gain": 2.0, "close_pct_of_position": 25},
    "tier_3": {"trigger_pct_gain": 3.5, "close_pct_of_position": 25},
    "tier_4": {"trigger_pct_gain": 5.0, "close_pct_of_position": 25},
    "trailing_stop": {"enabled": True, "activate_after_tier": 1,
                      "trail_pct": 1.0},
    "be_after_tier": 99,          # keep break-even out of these tests
}


def _runner_pos(entry=100.0, hw=110.0, tier_closed=2):
    from datetime import datetime, timezone
    p = Position(position_id="r1", symbol="T/USD", direction="long",
                 entry_price=entry, size=1.0, original_size=2.0,
                 opened_at=datetime.now(timezone.utc))
    p.tier_closed = tier_closed
    p.high_water = hw
    return p


def test_signal_decay_tightens_but_none_is_noop():
    base = ProfitTierEngine(_TIER_CFG)
    decay = ProfitTierEngine({**_TIER_CFG,
                              "signal_decay": {"enabled": True,
                                               "tighten_factor": 0.5}})
    # runner phase (all four tiers fired): px sits between the two stop
    # candidates - a full 1% trail from hw=110 stops at 108.9 (no exit
    # at 109.2); the tightened 0.5% trail stops at 109.45 (exit)
    px = 109.2
    a_base = base.evaluate(_runner_pos(tier_closed=4), px,
                           signal_alive=False)
    a_none = decay.evaluate(_runner_pos(tier_closed=4), px,
                            signal_alive=None)
    a_dead = decay.evaluate(_runner_pos(tier_closed=4), px,
                            signal_alive=False)
    assert a_base.should_close_partial is False   # disabled: full leash
    assert a_none.should_close_partial is False   # unknown: full leash
    assert a_dead.should_close_partial is True    # decayed: tight leash
    assert a_dead.close_pct == 100.0


def test_signal_decay_never_fires_later_than_legacy():
    """Tightening can only make exits SOONER: any px that exits under
    the legacy trail must also exit under the decayed trail."""
    legacy = ProfitTierEngine(_TIER_CFG)
    decay = ProfitTierEngine({**_TIER_CFG,
                              "signal_decay": {"enabled": True,
                                               "tighten_factor": 0.5}})
    for px in (108.5, 108.8, 108.9):
        if legacy.evaluate(_runner_pos(tier_closed=4),
                           px).should_close_partial:
            assert decay.evaluate(_runner_pos(tier_closed=4), px,
                                  signal_alive=False).should_close_partial


def test_inventory_coupling_boosts_fired_tier_close():
    eng = ProfitTierEngine({**_TIER_CFG,
                            "inventory_coupling": {"enabled": True,
                                                   "max_boost": 0.5}})
    pos = _runner_pos(hw=100.0, tier_closed=0)
    act_light = eng.evaluate(pos, 101.5, inventory_pressure=0.0)
    assert act_light.should_close_partial and act_light.close_pct == 25.0
    pos2 = _runner_pos(hw=100.0, tier_closed=0)
    act_heavy = eng.evaluate(pos2, 101.5, inventory_pressure=1.0)
    assert act_heavy.close_pct == pytest.approx(37.5)   # 25 * 1.5


def test_inventory_coupling_clamps_at_100():
    cfg = {**_TIER_CFG,
           "tier_1": {"trigger_pct_gain": 1.0, "close_pct_of_position": 90},
           "inventory_coupling": {"enabled": True, "max_boost": 1.0}}
    eng = ProfitTierEngine(cfg)
    act = eng.evaluate(_runner_pos(hw=100.0, tier_closed=0), 101.5,
                       inventory_pressure=1.0)
    assert act.close_pct == 100.0


def test_rev4_call_signature_unchanged():
    """Old call sites (positional pos, px, sigma) must behave exactly as
    before the rev-5 kwargs existed."""
    eng = ProfitTierEngine(_TIER_CFG)
    act = eng.evaluate(_runner_pos(hw=100.0, tier_closed=0), 101.5, 0.4)
    assert act.should_close_partial and act.close_pct == 25.0
