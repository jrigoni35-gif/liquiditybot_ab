"""tests/test_config_guard_min_pwin.py — the sizer entry bar must be honest.

position_sizer.min_p_win is the EARLY p(win) gate, but the net-Kelly step floors
size to 0 below the breakeven regardless (SZ-030). If min_p_win sits BELOW that
breakeven it is a phantom — the headline "minimum win prob" is not the effective
one. The guard WARNs (never fatal — the bot trades correctly) so the number is
honest; exploration.p_win was already guarded, min_p_win was the blind spot.
"""
import json
from pathlib import Path

from core.config_guard import validate

_CFG = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                  .read_text(encoding="utf-8"))


def _warns(cfg):
    return [m for s, m in validate(cfg) if s == "WARN"]


def _advisories(cfg):
    return [m for s, m in validate(cfg) if s == "ADVISORY"]


def _fatals(cfg):
    return [m for s, m in validate(cfg) if s == "FATAL"]


def test_shipped_config_flags_phantom_bar_as_advisory_not_warn_or_fatal():
    # shipped min_p_win (0.55) is below the ~0.63 breakeven. It is an ADVISORY
    # (config-honesty note; the bot trades correctly) - deliberately NOT a WARN,
    # so it stays off the WARNING+ incidents stream, and never a FATAL.
    assert any("min_p_win" in m for m in _advisories(_CFG))
    assert not any("min_p_win" in m for m in _warns(_CFG))
    assert not any("min_p_win" in m for m in _fatals(_CFG))


def test_no_finding_once_min_p_win_is_at_or_above_breakeven():
    cfg = json.loads(json.dumps(_CFG))
    cfg["position_sizer"]["min_p_win"] = 0.70     # comfortably above breakeven
    assert not any("min_p_win" in m for m in _advisories(cfg))
    assert not any("min_p_win" in m for m in _warns(cfg))
