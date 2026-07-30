"""tests/test_giveback_cost_floor.py — 2026-07-30 give-back ARM COST FLOOR.

Live incident (events.jsonl, operator-verified): in a quiet regime the
vol-scaled arm (2σ) armed the give-back at 0.25% (DOGE) and 0.31% (LINK)
peaks — inside the ~0.65% round-trip cost stack — so each "lock 60% of
the move" exit banked a guaranteed NET LOSS (measured -$0.12 / -$0.06),
and every probe closed as a 'realized' overlay before its bracket legs
could resolve (zero tb_* live labels — the gbt/blend unlock currency).

Contract: the EFFECTIVE arm never sits below the peak at which the
LOCKED share clears the position's own cost —
    arm_eff = max(vol_or_static_arm, est_cost_pct / (1 - giveback_frac))
Fully derived (no new literal, no new knob). est_cost_bps == 0
(legacy positions, quant-trials world, restored snapshots) keeps the
floor at 0 — exactly inert, the same inertness contract P1's tier-1
cost floor ships. Mirrored in the label sim via the SAME est_cost_bps
the tier-1 floor mirror already threads (both 0-inert together).
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from core.state import Position
from ml.labeling import ExitPolicy, simulate_exit_policy
from risk.profit_tiers import ProfitTierEngine


def _engine(giveback_frac=0.4):
    return ProfitTierEngine({
        "vol_scaled": False, "est_fee_bps": 40, "be_buffer_bps": 6,
        "give_back": {"enabled": True, "arm_gain_pct": 0.6,
                      "arm_vol_mult": 2.0, "giveback_frac": giveback_frac,
                      "tighten_gain_pct": 4.0, "tight_frac": 0.25}})


def _pos(peak_pct, est_cost_bps=0.0):
    p = Position(position_id="p1", symbol="ETH/USD", direction="long",
                 entry_price=100.0, size=1.0, original_size=1.0,
                 opened_at=datetime.now(timezone.utc))
    p.high_water = 100.0 * (1 + peak_pct / 100.0)
    p.est_cost_bps = est_cost_bps
    return p


def test_cost_floor_blocks_arming_inside_the_cost_band():
    """The live LINK case: sigma 0.155 -> vol arm 0.31%; cost 65bps and
    locked share 0.6 -> floor 65/100/0.6 = 1.083%. A 0.31% peak must NOT
    arm (pre-fix it did, and lost money); a 1.2% peak clears the floor."""
    eng = _engine()
    assert eng._give_back_candidate(
        _pos(0.31, est_cost_bps=65.0), sigma_bar_pct=0.155) is None
    assert eng._give_back_candidate(
        _pos(1.2, est_cost_bps=65.0), sigma_bar_pct=0.155) is not None


def test_zero_cost_is_byte_identical_legacy():
    # est_cost_bps=0 (legacy / trials / restored): floor 0, vol arm rules
    eng = _engine()
    assert eng._give_back_candidate(
        _pos(0.31, est_cost_bps=0.0), sigma_bar_pct=0.155) is not None


def test_floor_scales_with_locked_share():
    # giveback_frac 0.5 -> locked 0.5 -> floor = 0.65/0.5 = 1.30%
    eng = _engine(giveback_frac=0.5)
    assert eng._give_back_candidate(
        _pos(1.2, est_cost_bps=65.0), sigma_bar_pct=0.155) is None
    assert eng._give_back_candidate(
        _pos(1.4, est_cost_bps=65.0), sigma_bar_pct=0.155) is not None


def test_static_arm_also_floored():
    # no sigma (static arm 0.6%) is inside the 1.083% floor too: a 0.7%
    # peak that armed pre-fix must not arm with cost threaded
    eng = _engine()
    assert eng._give_back_candidate(
        _pos(0.7, est_cost_bps=65.0), sigma_bar_pct=None) is None
    assert eng._give_back_candidate(
        _pos(0.7, est_cost_bps=0.0), sigma_bar_pct=None) is not None


# ---------------------------------------------------------------------
# label-sim mirror (P3.5 parity: one discipline, two consumers)
# ---------------------------------------------------------------------
def _sim_policy():
    return ExitPolicy.from_config({
        "profit_taking": {
            "tier_1": {"trigger_pct_gain": 50.0, "close_pct_of_position": 25},
            "trailing_stop": {"enabled": False},
            "time_stop": {"enabled": False},
            "give_back": {"enabled": True, "arm_gain_pct": 0.6,
                          "arm_vol_mult": 2.0, "giveback_frac": 0.4}},
        "risk": {"stop_loss_pct": 10.0}})


def _fade_path():
    """Rise to +0.5% by bar 5, fade to +0.02% and hold to bar 40 — a
    small fake-out. Pre-fix the sim's give-back arms at 2σ=0.2% and the
    floor exit fires on the fade; with cost threaded the arm floor
    (1.083%) exceeds the 0.5% peak so the ride goes to the vertical."""
    closes = np.array([100.0 + 0.1 * min(j, 5) - (0.096 * min(max(j - 5, 0), 5))
                       for j in range(41)])
    return closes, closes + 0.001, closes - 0.001


def test_labeler_mirrors_the_cost_floor():
    closes, highs, lows = _fade_path()
    pol = _sim_policy()
    out0 = simulate_exit_policy(closes, highs, lows, 0, +1, 0.001, pol,
                                max_bars=40, est_cost_bps=0.0)
    out65 = simulate_exit_policy(closes, highs, lows, 0, +1, 0.001, pol,
                                 max_bars=40, est_cost_bps=65.0)
    # cost=0: give-back armed at the 0.5% peak, floor exit on the fade
    assert out0.bars_held < 40 and out0.barrier != "time"
    # cost=65: arm floored at 1.083% > peak -> never arms -> vertical
    assert out65.barrier == "time" and out65.bars_held == 40
