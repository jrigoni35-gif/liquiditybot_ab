"""tests/test_exit_policy_label.py — the exit-policy replay labeler.

The candidate/bootstrap labels must answer the SAME question a live trade poses:
"does this signal net positive under our REAL exit policy (hard stop + tiered
scale-outs + give-back/trailing runner)?" — not the old symmetric 8σ/6σ single
barrier. These pin the replay against hand-computed paths so a brain re-baseline
rests on a verified label, and confirm the policy is read from live config.
"""
import json
from pathlib import Path

import numpy as np

from ml.labeling import ExitPolicy, simulate_exit_policy, triple_barrier

_CFG = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                  .read_text(encoding="utf-8"))


def _flat_policy():
    # vol_scaled off + sigma 0 -> clean 2% stop, tiers at 1/2/3.5/5%
    p = ExitPolicy.from_config(_CFG)
    p.vol_scaled = False
    return p


def _bars(path):
    """path: list of (high, low, close) -> arrays with a leading entry bar."""
    highs = [100.0] + [h for h, _, _ in path]
    lows = [100.0] + [ll for _, ll, _ in path]
    closes = [100.0] + [c for _, _, c in path]
    return np.array(closes), np.array(highs), np.array(lows)


def test_from_config_reads_live_geometry():
    p = ExitPolicy.from_config(_CFG)
    assert p.base_stop_frac == 0.02 and p.stop_vol_mult == 4.0
    assert len(p.tiers) == 4
    assert p.tiers[0][2] == 0.25                 # 25% close per tier
    assert p.gb_arm_frac == 0.015 and p.trail_after_tier == 2


def test_immediate_stop_is_a_loss():
    c, h, ll = _bars([(100.5, 97.0, 98.0)])      # -3% low breaches 2% stop
    out = simulate_exit_policy(c, h, ll, 0, +1, 0.0, _flat_policy(),
                               max_bars=96, cost_pct=0.5)
    assert out.label == 0 and out.barrier == "sl"
    assert abs(out.ret_pct - (-2.0)) < 1e-9      # exited at the stop, not -3%


def test_clean_run_through_all_tiers():
    c, h, ll = _bars([(101.0, 100.5, 100.8), (102.0, 101.0, 101.8),
                      (103.5, 102.5, 103.0), (105.0, 104.0, 104.8)])
    out = simulate_exit_policy(c, h, ll, 0, +1, 0.0, _flat_policy(),
                               max_bars=96, cost_pct=0.5)
    # 0.25*(1+2+3.5+5)% = 2.875% realized across the four scale-outs
    assert out.barrier == "tier"
    assert abs(out.ret_pct - 2.875) < 1e-6
    assert out.label == 1


def test_runup_then_giveback_exits_on_the_floor_not_at_peak():
    # tiers 1+2 fill on a +2% bar, then price sags to +1.1% -> the give-back /
    # trailing floor (locked ~1.2%) closes the runner ABOVE break-even
    c, h, ll = _bars([(102.0, 101.0, 101.5), (102.0, 101.1, 101.2)])
    out = simulate_exit_policy(c, h, ll, 0, +1, 0.0, _flat_policy(),
                               max_bars=96, cost_pct=0.5)
    assert out.barrier == "trail"
    assert out.label == 1
    assert 1.0 < out.ret_pct < 2.0               # locked below peak, above BE


def test_adverse_checked_before_favorable_within_a_bar():
    # a bar that both tags a tier (high) and breaches the stop (low): the
    # conservative replay must take the STOP, never the tier
    c, h, ll = _bars([(105.0, 97.0, 100.0)])
    out = simulate_exit_policy(c, h, ll, 0, +1, 0.0, _flat_policy(),
                               max_bars=96, cost_pct=0.5)
    assert out.label == 0 and out.barrier == "sl"


def test_time_barrier_scratch_is_a_loss_after_cost():
    # drifts to +0.3% and never tags a tier; net of 0.5% cost -> loss
    path = [(100.5, 99.5, 100.1)] * 5 + [(100.5, 99.5, 100.3)]
    c, h, ll = _bars(path)
    out = simulate_exit_policy(c, h, ll, 0, +1, 0.0, _flat_policy(),
                               max_bars=96, cost_pct=0.5)
    assert out.barrier == "time"
    assert abs(out.ret_pct - 0.3) < 1e-6 and out.label == 0


def test_short_side_is_symmetric():
    # short entry 100; price falls (favorable) to tag tiers 1+2 and never pops
    # back up to trip the break-even floor, so the runner closes in profit
    c, h, ll = _bars([(100.3, 99.0, 99.2), (99.5, 98.0, 98.5)])
    out = simulate_exit_policy(c, h, ll, 0, -1, 0.0, _flat_policy(),
                               max_bars=96, cost_pct=0.5)
    assert out.ret_pct > 0 and out.label == 1

    c2, h2, ll2 = _bars([(103.0, 100.5, 101.0)])   # +3% up breaches short stop
    out2 = simulate_exit_policy(c2, h2, ll2, 0, -1, 0.0, _flat_policy(),
                                max_bars=96, cost_pct=0.5)
    assert out2.label == 0 and out2.barrier == "sl"


def test_replay_differs_from_triple_barrier_on_a_dip_then_target():
    # THE point: a path that dips −5% (survives the label's 6σ stop) then tags
    # +8% is a triple-barrier WIN but a live STOP-OUT (−2% hard stop). sigma
    # 1% -> label pt=8σ=8%, sl=6σ=6%; live stop=max(2%,4%)=4%.
    sigma = 0.01
    c, h, ll = _bars([(100.5, 95.5, 96.0),       # −4.5% dip: > live 4% stop,
                                                 #            < label 6% stop
                      (108.5, 108.0, 108.2)])    # then +8.5%: tags label pt
    tb = triple_barrier(c, h, ll, 0, +1, sigma, pt_mult=8.0, sl_mult=6.0,
                        max_bars=96, cost_pct=0.5)
    p = ExitPolicy.from_config(_CFG)             # vol_scaled ON (live)
    ep = simulate_exit_policy(c, h, ll, 0, +1, sigma, p, max_bars=96,
                              cost_pct=0.5)
    assert tb.label == 1 and tb.barrier == "pt"  # barrier calls it a win
    assert ep.label == 0 and ep.barrier == "sl"  # the real policy stops out
