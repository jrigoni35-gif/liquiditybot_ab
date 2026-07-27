"""tests/test_config_guard_pt_cost_mult.py — ml.label_pt_cost_mult bounds
(spec D2/D5, geometry-alignment T2, 2026-07-27). 0 disables the cost floor
(legacy 8sigma/6sigma); the shipped 4.0 puts costs at 25% of the profit
distance. FATAL outside [0, 20] (config nonsense); WARN in (0, 2) (costs
above 50% of the profit distance — the bet the floor exists to prevent).
Follows the _sev/_cfg idiom from tests/test_config_guard_min_pwin.py.
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


def test_shipped_config_pt_cost_mult_has_no_finding():
    # shipped 4.0: no floor finding at any severity
    assert _CFG["ml"]["label_pt_cost_mult"] == 4.0
    for s in ("WARN", "FATAL"):
        assert not any("label_pt_cost_mult" in m for m in _sev(_CFG, s))


def test_negative_pt_cost_mult_is_fatal():
    cfg = _cfg()
    cfg["ml"]["label_pt_cost_mult"] = -0.5
    assert any("label_pt_cost_mult" in m for m in _sev(cfg, "FATAL"))


def test_above_20_pt_cost_mult_is_fatal():
    cfg = _cfg()
    cfg["ml"]["label_pt_cost_mult"] = 20.5
    assert any("label_pt_cost_mult" in m for m in _sev(cfg, "FATAL"))


def test_boundary_values_0_and_20_are_not_fatal():
    for ok in (0.0, 20.0):
        cfg = _cfg()
        cfg["ml"]["label_pt_cost_mult"] = ok
        assert not any("label_pt_cost_mult" in m for m in _sev(cfg, "FATAL")), ok


def test_zero_disables_floor_and_does_not_warn():
    # 0 is the legacy no-floor value, not a "costs eat the profit" warning
    cfg = _cfg()
    cfg["ml"]["label_pt_cost_mult"] = 0.0
    assert not any("label_pt_cost_mult" in m for m in _sev(cfg, "WARN"))


def test_between_0_and_2_warns_costs_above_50_percent():
    cfg = _cfg()
    cfg["ml"]["label_pt_cost_mult"] = 1.0
    msgs = [m for m in _sev(cfg, "WARN") if "label_pt_cost_mult" in m]
    assert any("costs above 50% of the profit distance" in m for m in msgs)


def test_at_or_above_2_does_not_warn():
    cfg = _cfg()
    cfg["ml"]["label_pt_cost_mult"] = 2.0
    assert not any("label_pt_cost_mult" in m for m in _sev(cfg, "WARN"))
