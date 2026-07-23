"""config_guard: order_manager.fee_recon.{tolerance_bps,interval_hours}
bounds (W2-9 remainder, Task 2 #103).

tolerance_bps in (0, 50]: at/below 0 the periodic reconciliation would flag
ordinary float noise every interval; above 50bps it can no longer catch a
real Kraken tier jump. interval_hours in [1, 168]: below hourly it would
out-cadence hourly_cycle itself; above a week a real tier change could hide
for a full trading week. Both FATAL regardless of dry_run - structural
config-nonsense checks, same class as tier1_cost_floor's own bounds.
"""
from core.config_guard import validate


def _cfg(tolerance_bps=1.0, interval_hours=24.0, enabled=True):
    return {"system": {"dry_run": True},
            "order_manager": {"fee_recon": {"enabled": enabled,
                                            "tolerance_bps": tolerance_bps,
                                            "interval_hours": interval_hours}}}


def _fatals(cfg):
    return [m for sev, m in validate(cfg) if sev == "FATAL"]


def test_default_fee_recon_no_fatal():
    assert not any("fee_recon" in m for m in _fatals({}))


def test_shipped_values_no_fatal():
    assert not any("fee_recon" in m for m in _fatals(_cfg(1.0, 24.0)))


def test_tolerance_zero_is_fatal():
    assert any("tolerance_bps" in m for m in _fatals(_cfg(tolerance_bps=0.0)))


def test_tolerance_negative_is_fatal():
    assert any("tolerance_bps" in m
              for m in _fatals(_cfg(tolerance_bps=-1.0)))


def test_tolerance_above_50_is_fatal():
    assert any("tolerance_bps" in m
              for m in _fatals(_cfg(tolerance_bps=50.5)))


def test_tolerance_boundary_50_is_not_fatal():
    assert not any("tolerance_bps" in m
                  for m in _fatals(_cfg(tolerance_bps=50.0)))


def test_interval_below_1_is_fatal():
    assert any("interval_hours" in m
              for m in _fatals(_cfg(interval_hours=0.5)))


def test_interval_above_168_is_fatal():
    assert any("interval_hours" in m
              for m in _fatals(_cfg(interval_hours=200.0)))


def test_interval_boundary_1_and_168_are_not_fatal():
    assert not any("interval_hours" in m
                  for m in _fatals(_cfg(interval_hours=1.0)))
    assert not any("interval_hours" in m
                  for m in _fatals(_cfg(interval_hours=168.0)))


def test_disabled_skips_bound_checks():
    # an out-of-range tolerance on a DISABLED block is inert config, not a
    # live risk - never checked (matches the ml.adaptive_gbt opt-in pattern)
    assert not any("fee_recon" in m
                  for m in _fatals(_cfg(tolerance_bps=999.0, enabled=False)))
