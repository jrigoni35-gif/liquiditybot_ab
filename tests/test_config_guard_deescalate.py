"""W2-17 config guard: ml.monitor.deescalate_healthy_windows range check.

<1 disables the de-escalation deadband outright (reopens the L0<->L1 flap
the knob exists to fix); an absurdly high value leaves a recovered model
throttled long past what the evidence supports. Range-checked like the
other bounded governor knobs (config_guard.py's adaptive_gbt.bags pattern).
"""
from core.config_guard import validate


def _sev(cfg, sev):
    return [m for s, m in validate(cfg) if s == sev]


def test_default_knob_value_is_within_range():
    cfg = {"system": {"dry_run": True},
           "ml": {"monitor": {"deescalate_healthy_windows": 3}}}
    assert not any("deescalate_healthy_windows" in m for m in _sev(cfg, "FATAL"))


def test_zero_is_fatal():
    cfg = {"system": {"dry_run": True},
           "ml": {"monitor": {"deescalate_healthy_windows": 0}}}
    assert any("deescalate_healthy_windows" in m for m in _sev(cfg, "FATAL"))


def test_negative_is_fatal():
    cfg = {"system": {"dry_run": True},
           "ml": {"monitor": {"deescalate_healthy_windows": -1}}}
    assert any("deescalate_healthy_windows" in m for m in _sev(cfg, "FATAL"))


def test_above_ten_is_fatal():
    cfg = {"system": {"dry_run": True},
           "ml": {"monitor": {"deescalate_healthy_windows": 11}}}
    assert any("deescalate_healthy_windows" in m for m in _sev(cfg, "FATAL"))


def test_ten_is_allowed():
    cfg = {"system": {"dry_run": True},
           "ml": {"monitor": {"deescalate_healthy_windows": 10}}}
    assert not any("deescalate_healthy_windows" in m for m in _sev(cfg, "FATAL"))


def test_one_is_allowed():
    cfg = {"system": {"dry_run": True},
           "ml": {"monitor": {"deescalate_healthy_windows": 1}}}
    assert not any("deescalate_healthy_windows" in m for m in _sev(cfg, "FATAL"))
