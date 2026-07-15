"""CapitalManager config wiring + concurrent-position cap.

Wiring audit: main.py passed the FULL config to CapitalManager, but every
tunable lives in config.json's "capital_management" section - so the shipped
values were silently ignored and the hardcoded defaults ran (harmless only
while the two happened to match). CapitalManager now extracts its own section
(and still accepts a bare section dict); main.py passes the section like its
sibling constructors. These tests pin both shapes, the shipped-config path
end-to-end, the cap boundary, and the config_guard floor.
"""
import json
import types
from pathlib import Path

from core.config_guard import validate
from risk.capital_manager import CapitalManager


def _state(n_open, daily_pnl=0.0, ddown=0.0):
    return types.SimpleNamespace(
        open_position_count=lambda: n_open,
        starting_capital=10_000.0,
        daily_realized_pnl=daily_pnl,
        drawdown_pct=lambda: ddown)


def test_full_config_shape_reads_the_section():
    cm = CapitalManager({"capital_management": {"max_concurrent_positions": 5},
                         "system": {"dry_run": True}})
    assert cm.max_concurrent_positions == 5


def test_bare_section_shape_still_works():
    cm = CapitalManager({"max_concurrent_positions": 4})
    assert cm.max_concurrent_positions == 4


def test_shipped_config_cap_actually_reaches_the_manager():
    # the regression that motivated the fix: config.json's value must win
    # over the code default when the full config is what gets passed
    cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                     .read_text(encoding="utf-8"))
    cm = CapitalManager(cfg)
    assert cm.max_concurrent_positions == \
        cfg["capital_management"]["max_concurrent_positions"]
    assert cm.max_concurrent_positions == 5


def test_cap_blocks_at_limit_and_allows_below():
    cm = CapitalManager({"max_concurrent_positions": 5})
    assert cm.can_open_new_position(_state(4)) is True
    assert cm.can_open_new_position(_state(5)) is False
    assert cm.can_open_new_position(_state(6)) is False


def test_pending_entries_reserve_cap_slots():
    """Positions are booked on FILL, not on submit, so a resting (pending)
    entry order is committed risk invisible to open_position_count(). The
    cap must count filled + pending, or one-pending-entry-per-asset can
    overfill max_concurrent when they all fill. Default 0 = legacy exact."""
    cm = CapitalManager({"max_concurrent_positions": 5})
    # 3 filled + 2 pending entries == 5 committed: cap is reached
    assert cm.can_open_new_position(_state(3), in_flight_entries=2) is False
    assert cm.can_open_new_position(_state(3), in_flight_entries=1) is True
    # pending alone can reach the cap with zero filled
    assert cm.can_open_new_position(_state(0), in_flight_entries=5) is False
    assert cm.can_open_new_position(_state(0), in_flight_entries=4) is True
    # a stray negative can never LOOSEN the cap
    assert cm.can_open_new_position(_state(5), in_flight_entries=-3) is False
    # the default preserves the pre-reservation behaviour exactly
    assert cm.can_open_new_position(_state(4)) is True


def test_guard_zero_max_concurrent_is_fatal():
    cfg = {"system": {"dry_run": True},
           "capital_management": {"max_concurrent_positions": 0}}
    assert any("max_concurrent_positions" in m
               for sev, m in validate(cfg) if sev == "FATAL")


def test_guard_shipped_cap_is_clean():
    cfg = {"system": {"dry_run": True},
           "capital_management": {"max_concurrent_positions": 5}}
    assert not any("max_concurrent_positions" in m
                   for sev, m in validate(cfg) if sev == "FATAL")
