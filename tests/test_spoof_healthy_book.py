"""SD-003 (2026-07-31): a spoof score must not veto a healthy book.

A "spoofy" liquidity label is a TOTAL veto - size_mult 0, reduce_only -
applied per asset on every cycle. The bot's own SD-003 diagnostic
measured it firing on 55% of classified cycles, which is the direct
cause of the entry collapse (27-87 entries/day through 07-22 -> 0-11/day
from 07-24) and of the label starvation downstream (SD-002: "with 0
entries there is no new data, so retraining can never clear").

Live evidence at the time of the fix: DOT scored spoof 0.61 on a 1.3bps
spread while MINA (21.5bps) and FLOW (36.7bps) scored 0.89/0.78. The
detector is right on wide books and wrong on tight ones - so a
structurally healthy book (deep AND tight) raises the bar a spoof score
must clear, rather than muting the detector.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from regime.liquidity_regime import LiquidityRegimeEngine


def _lr(**over):
    cfg = {"min_depth_usd": 100_000, "max_spread_bps": 12.0,
           "spoof_score_threshold": 0.45,
           "spoof_healthy_book_threshold": 0.85}
    cfg.update(over)
    return LiquidityRegimeEngine(cfg)


def test_healthy_book_threshold_defaults_to_the_plain_bar():
    """Extend-with-defaults: a config that never heard of this knob keeps
    the shipped behavior exactly."""
    lr = LiquidityRegimeEngine({"spoof_score_threshold": 0.45})
    assert lr.spoof_healthy_book_threshold == 0.45


def test_config_ships_the_raised_bar():
    import json
    cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                     .read_text(encoding="utf-8"))
    liq = cfg["liquidity_regime"]
    assert liq["spoof_healthy_book_threshold"] == 0.85
    assert liq["spoof_healthy_book_threshold"] > liq["spoof_score_threshold"]


def test_the_dot_false_positive_is_the_pinned_case():
    """DOT: spoof 0.61 on a 1.3bps spread. Above the plain 0.45 bar,
    below the healthy-book 0.85 bar -> must NOT be vetoed."""
    lr = _lr()
    assert 0.61 >= lr.spoof_score_threshold, "was vetoed pre-fix"
    assert 0.61 < lr.spoof_healthy_book_threshold, "not vetoed post-fix"


def test_wide_book_spoof_still_vetoes():
    """MINA 0.89 / FLOW 0.78 on 21.5 / 36.7bps books are wide, so they
    are NOT healthy and face the plain 0.45 bar - still vetoed."""
    lr = _lr()
    for score in (0.89, 0.78):
        assert score >= lr.spoof_score_threshold


def test_real_layering_on_a_tight_book_still_vetoes():
    """The fix raises the bar, it does not mute the detector."""
    lr = _lr()
    assert 0.92 >= lr.spoof_healthy_book_threshold
