"""config_guard: profit_taking.min_trigger_cost_mult bounds (Task 1, P1).

The floor multiplies the entry's own estimated round-trip cost
(Position.est_cost_bps) to raise tier-1's effective trigger. Below 1.0x the
floor couldn't even guarantee covering a single cost unit (the whole point
of the floor); above 10.0x tier-1 would almost never fire in ordinary vol
regimes. Both ends FATAL regardless of dry_run (a structural config-nonsense
check, same class as chandelier_k/tighten_factor's own bounds).
"""
from core.config_guard import validate


def _cfg(mult):
    return {"system": {"dry_run": True},
            "profit_taking": {"min_trigger_cost_mult": mult}}


def _fatals(cfg):
    return [m for sev, m in validate(cfg) if sev == "FATAL"]


def test_default_min_trigger_cost_mult_no_fatal():
    assert not any("min_trigger_cost_mult" in m for m in _fatals({}))


def test_shipped_3x_no_fatal():
    assert not any("min_trigger_cost_mult" in m for m in _fatals(_cfg(3.0)))


def test_below_1x_is_fatal():
    assert any("min_trigger_cost_mult" in m for m in _fatals(_cfg(0.5)))


def test_above_10x_is_fatal():
    assert any("min_trigger_cost_mult" in m for m in _fatals(_cfg(10.5)))


def test_boundary_1x_and_10x_are_not_fatal():
    assert not any("min_trigger_cost_mult" in m for m in _fatals(_cfg(1.0)))
    assert not any("min_trigger_cost_mult" in m for m in _fatals(_cfg(10.0)))
