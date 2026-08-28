"""tests/test_config_guard_knob_lifts.py — the 2026-08-27 config-audit knob
lifts (SAFE-FIX items 8/9): position_sizer.explore_floor_mult and
liquidity_regime.spoof_ewma_alpha lifted into config.json at their IDENTICAL
code defaults (overfit discipline: lift with the same default, then guard).

Pins, in order: the lift is PRESENT in the shipped config; the config value
EQUALS the code default the readers have always run on (so the lift is
behavior-preserving by construction — runtime A/B byte-equality on real
sizing/veto decisions was also verified at ship time); the new config_guard
coherence checks FIRE on injected incoherent values and stay quiet on the
shipped file and on the valid boundary values.
"""
import copy
import json
from pathlib import Path

from core.config_guard import validate
from regime.liquidity_regime import LiquidityRegimeEngine
from risk.position_sizer import PositionSizer

_CFG = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                  .read_text(encoding="utf-8"))


def _fatals(cfg):
    return [m for sev, m in validate(cfg) if sev == "FATAL"]


def _warns(cfg):
    return [m for sev, m in validate(cfg) if sev == "WARN"]


def _with(path, value):
    cfg = copy.deepcopy(_CFG)
    node = cfg
    *parents, leaf = path.split(".")
    for p in parents:
        node = node[p]
    node[leaf] = value
    return cfg


# --- the lifts are present at the identical code default --------------------

def test_explore_floor_mult_lift_present_and_equals_code_default():
    assert _CFG["position_sizer"]["explore_floor_mult"] == 1.2
    # the code default on a cfg WITHOUT the key must equal the lifted
    # config value — that identity IS the behavior-preservation claim
    bare = PositionSizer({"entry_cooldown_min": 0}, {}, {})
    assert bare.explore_floor_mult == \
        _CFG["position_sizer"]["explore_floor_mult"]


def test_spoof_ewma_alpha_lift_present_and_equals_code_default():
    assert _CFG["liquidity_regime"]["spoof_ewma_alpha"] == 0.06
    bare = LiquidityRegimeEngine({})
    assert bare.ewma_alpha == _CFG["liquidity_regime"]["spoof_ewma_alpha"]


def test_shipped_config_no_fatal_on_the_new_checks():
    fatals = _fatals(_CFG)
    assert not any("explore_floor_mult" in m for m in fatals)
    assert not any("spoof_ewma_alpha" in m for m in fatals)


# --- injections: the guard fires on incoherent values -----------------------

def test_explore_floor_mult_below_one_is_fatal():
    fatals = _fatals(_with("position_sizer.explore_floor_mult", 0.5))
    assert any("explore_floor_mult" in m for m in fatals)


def test_explore_floor_mult_above_five_is_fatal():
    fatals = _fatals(_with("position_sizer.explore_floor_mult", 9.0))
    assert any("explore_floor_mult" in m for m in fatals)


def test_explore_floor_mult_valid_boundaries_pass():
    for v in (1.0, 5.0):
        assert not any(
            "explore_floor_mult" in m
            for m in _fatals(_with("position_sizer.explore_floor_mult", v))
        ), f"valid boundary {v} must not FATAL"


def test_spoof_ewma_alpha_zero_is_fatal():
    fatals = _fatals(_with("liquidity_regime.spoof_ewma_alpha", 0.0))
    assert any("spoof_ewma_alpha" in m for m in fatals)


def test_spoof_ewma_alpha_above_one_is_fatal():
    fatals = _fatals(_with("liquidity_regime.spoof_ewma_alpha", 1.5))
    assert any("spoof_ewma_alpha" in m for m in fatals)


def test_spoof_ewma_alpha_boundary_one_passes_but_warns_smoothing_off():
    cfg = _with("liquidity_regime.spoof_ewma_alpha", 1.0)
    assert not any("spoof_ewma_alpha" in m for m in _fatals(cfg))
    assert any("spoof_ewma_alpha" in m for m in _warns(cfg))
