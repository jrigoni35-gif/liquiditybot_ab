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
    # RE-BASELINED at cut #8 (boundary #5, fee truth, 2026-08-28): the
    # breakeven this literal has to clear is derived from the LIVE fee
    # constants, and true Tier-1 fees (40/80) moved it 0.690 -> 0.8335.
    # 0.70 was "above breakeven" only in the 25/40 world; below the cut it
    # is a FATAL, which is the guard being RIGHT. The pin's subject is the
    # guard's clean-above-breakeven branch, so the literal moves with the
    # breakeven - the number is a fixture, not the claim.
    cfg = copy.deepcopy(_CFG)
    cfg["ml"]["exploration"]["p_win"] = 0.90
    assert not _explore_fatals(cfg)


def test_disabled_exploration_never_flags():
    cfg = copy.deepcopy(_CFG)
    cfg["ml"]["exploration"]["enabled"] = False
    cfg["ml"]["exploration"]["p_win"] = 0.10      # nonsense, but off
    assert not _explore_fatals(cfg)
