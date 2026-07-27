"""tests/test_config_guard_min_pwin.py — the sizer entry bar must be honest.

History: min_p_win 0.55 sat below the ~0.632 net-Kelly breakeven — a phantom
bar the guard flagged as an ADVISORY. The 2026-07-27 operator-directed fix
ships p_bar_mode="derived" (bar pinned to breakeven + margin, min_p_win as
floor), so the shipped config can no longer be phantom BY CONSTRUCTION and
the advisory is scoped to absolute mode. What must now hold: mode/margin are
validated, the probe-strangulation interlock WARNs before geometry drift
closes the exploration clearance, and absolute-mode configs keep the
original honesty note.
"""
import json
from pathlib import Path

from core.config_guard import validate

_CFG = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                  .read_text(encoding="utf-8"))


def _cfg():
    return json.loads(json.dumps(_CFG))


def _sev(cfg, s):
    return [m for sev, m in validate(cfg) if sev == s]


def test_shipped_derived_config_has_no_phantom_finding_at_any_severity():
    # derived mode pins the bar at/above breakeven by construction - the
    # phantom condition is impossible, so no min_p_win finding fires
    assert _CFG["position_sizer"]["p_bar_mode"] == "derived"
    for s in ("ADVISORY", "WARN", "FATAL"):
        assert not any("min_p_win" in m for m in _sev(_CFG, s))


def test_absolute_mode_keeps_the_phantom_advisory():
    cfg = _cfg()
    cfg["position_sizer"]["p_bar_mode"] = "absolute"
    assert any("min_p_win" in m for m in _sev(cfg, "ADVISORY"))
    assert not any("min_p_win" in m for m in _sev(cfg, "WARN"))
    assert not any("min_p_win" in m for m in _sev(cfg, "FATAL"))


def test_absolute_mode_no_finding_once_at_or_above_breakeven():
    cfg = _cfg()
    cfg["position_sizer"]["p_bar_mode"] = "absolute"
    cfg["position_sizer"]["min_p_win"] = 0.70
    assert not any("min_p_win" in m for m in _sev(cfg, "ADVISORY"))


def test_unknown_p_bar_mode_is_fatal():
    cfg = _cfg()
    cfg["position_sizer"]["p_bar_mode"] = "adaptive"
    assert any("p_bar_mode" in m for m in _sev(cfg, "FATAL"))


def test_edge_margin_out_of_bounds_is_fatal():
    for bad in (-0.01, 0.25):
        cfg = _cfg()
        cfg["position_sizer"]["p_bar_edge_margin"] = bad
        assert any("p_bar_edge_margin" in m for m in _sev(cfg, "FATAL")), bad


def test_probe_clearance_interlock_warns_before_the_trickle_dies():
    # shipped: explore p 0.64 vs derived bar ~0.6317 -> clearance ~0.008, no
    # warning. A margin that closes the gap under 0.005 must WARN: probes
    # dying at SZ-023 is the Jul-24 drought re-created from the bar side.
    assert not any("exploration.p_win" in m and "clearance" in m
                   for m in _sev(_CFG, "WARN"))
    cfg = _cfg()
    cfg["position_sizer"]["p_bar_edge_margin"] = 0.01   # bar 0.6417 vs 0.64
    assert any("clearance" in m for m in _sev(cfg, "WARN"))


def test_cost_heavy_geometry_pushing_bar_past_090_warns():
    cfg = _cfg()
    # brutal geometry: tiny wins, fat stop, heavy fees -> breakeven ~> 0.9
    cfg["risk"]["stop_loss_pct"] = 8.0
    for t in ("tier_1", "tier_2", "tier_3", "tier_4"):
        cfg["profit_taking"][t]["trigger_pct_gain"] = 0.8
    assert any("derived entry bar" in m and "0.90" in m
               for m in _sev(cfg, "WARN"))
