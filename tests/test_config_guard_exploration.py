"""config_guard: exploration p_win must clear the net-Kelly breakeven.

Regression for a silent learning outage (2026-07-15): the cost-honest sizer
(maker+taker round-trip) raised the net breakeven to ~0.632 while
ml.exploration.p_win stayed 0.62, so the sizer SZ-030-vetoed EVERY dry-run
exploration entry - zero learning trades, flat equity, model starved. The
guard now FATALs on this incoherent combination so it can't recur silently.
"""
import copy
import json
from pathlib import Path

from core.config_guard import validate

_CFG = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                  .read_text(encoding="utf-8"))


def _explore_fatals(cfg):
    return [m for s, m in validate(cfg)
            if s == "FATAL" and "exploration.p_win" in m]


def test_shipped_config_explore_p_win_clears_breakeven():
    assert not _explore_fatals(_CFG)


def test_p_win_below_breakeven_is_fatal():
    cfg = copy.deepcopy(_CFG)
    cfg["ml"]["exploration"]["p_win"] = 0.60      # below ~0.632
    fatals = _explore_fatals(cfg)
    assert fatals and "breakeven" in fatals[0]


def test_p_win_above_breakeven_is_clean():
    cfg = copy.deepcopy(_CFG)
    cfg["ml"]["exploration"]["p_win"] = 0.70
    assert not _explore_fatals(cfg)


def test_disabled_exploration_never_flags():
    cfg = copy.deepcopy(_CFG)
    cfg["ml"]["exploration"]["enabled"] = False
    cfg["ml"]["exploration"]["p_win"] = 0.10      # nonsense, but off
    assert not _explore_fatals(cfg)
