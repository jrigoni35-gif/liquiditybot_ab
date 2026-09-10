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
    # 0.006 since the 2026-07-20 tuning pass: the ledger showed movers
    # peak at MFE p90 0.72% while the ratchet armed at 1.5% (armed once
    # in 55 trades) - the labeler mirrors the DEPLOYED geometry (#30)
    assert p.gb_arm_frac == 0.006 and p.trail_after_tier == 2


def test_immediate_stop_is_a_loss():
    c, h, ll = _bars([(100.5, 97.0, 98.0)])      # -3% low breaches 2% stop
    out = simulate_exit_policy(c, h, ll, 0, +1, 0.0, _flat_policy(),
                               max_bars=96, cost_pct=0.5)
    assert out.label == 0 and out.barrier == "sl"
    assert abs(out.ret_pct - (-2.0)) < 1e-9      # exited at the stop, not -3%


def test_clean_run_through_all_tiers():
    # PATH RE-ANCHORED at cut #8 (boundary #5, fee truth, 2026-08-28), still
    # clean at cut #9. ExitPolicy.from_config reads the LIVE profit_taking.
    # est_fee_bps: cut #8 moved it 40 -> 80 (BE/trail floor 2*fee+buffer
    # doubled 86bps -> 166bps), so this path was re-anchored to shallower
    # pullbacks to stay clean at the higher floor. Cut #9 (Tier-3 truth) then
    # dropped est_fee 80 -> 38 (floor back to 82bps, below the original 86),
    # so the path stays clean a fortiori - no re-anchor needed. The claim
    # under test is the tier arithmetic on a clean four-tier run
    # (0.25*(1+2+3.5+5)% = 2.875%), untouched by either cut. The DEEPER-
    # pullback path's cross-cut history is pinned below.
    c, h, ll = _bars([(101.0, 100.5, 100.8), (102.0, 101.8, 101.9),
                      (103.5, 103.0, 103.4), (105.0, 104.4, 104.9)])
    out = simulate_exit_policy(c, h, ll, 0, +1, 0.0, _flat_policy(),
                               max_bars=96, cost_pct=0.5)
    # 0.25*(1+2+3.5+5)% = 2.875% realized across the four scale-outs
    assert out.barrier == "tier"
    assert abs(out.ret_pct - 2.875) < 1e-6
    assert out.label == 1


def test_cut9_unwound_boundary5s_runner_exit_shift_on_the_old_path():
    """Cut #9 UNWOUND cut #8's runner-exit shift on this path - pinned.

    History pinned here across two cuts on the SAME deeper-pullback path:
      - pre-cut-8 (est_fee_bps=40, BE/trail floor 2*40+6=86bps): closed on
        the tier-4 scale-out for +2.875%;
      - cut #8 (est_fee_bps=80, floor 166bps): the doubled floor caught the
        runner on the trail first (barrier="trail", ~+1.4%), label still 1;
      - cut #9 (Tier-3 fee truth, est_fee_bps=38, floor 2*38+6=82bps - even
        BELOW the pre-cut 86): cut #8 OVER-stated the fee ~2x, so correcting
        it drops the floor back under the pullbacks and the runner clears to
        tier 4 again for +2.875%. The exit shift is UNWOUND; the label was
        1 throughout - no cut ever turned this winner into a loser, they
        moved WHERE the runner is released. Observed on the real labeler
        (barrier/label/ret verified at the cut, not argued from the diff);
        decision record docs/quant/2026-08-29_fee_tier_correction_adjudication.md.
    """
    c, h, ll = _bars([(101.0, 100.5, 100.8), (102.0, 101.0, 101.8),
                      (103.5, 102.5, 103.0), (105.0, 104.0, 104.8)])
    out = simulate_exit_policy(c, h, ll, 0, +1, 0.0, _flat_policy(),
                               max_bars=96, cost_pct=0.5)
    # which cost world this ran in: cut #9 shipped 38; cut #10 (2026-09-06,
    # E1, on a legacy-ladder premise corrected 2026-09-08: 22/38 IS Tier 3,
    # 20/35 is Tier 4) moved it to 35.
    # The outcome below is computed at the explicit cost_pct=0.5 passed above
    # and does not read this key - the pin is a world-stamp, not an input.
    # cut #12 (2026-09-08, FEE-4: the account's real Tier 5) moved it to 30.
    assert _CFG["profit_taking"]["est_fee_bps"] == 30    # the cut, as shipped
    assert out.barrier == "tier"                         # cleared to tier 4
    assert out.label == 1
    assert abs(out.ret_pct - 2.875) < 1e-6               # full four-tier run


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


# --- 2026-07-29 unit-audit mirrors (BE fee term, chandelier, tighten-0) ------

def test_be_floor_includes_the_live_fee_term():
    """Live BE floor = (2*est_fee_bps + be_buffer_bps)/1e4 as a gain level
    (profit_tiers.py:655). With 40bps fees + 6bps buffer that is +0.86%;
    the old sim floor was the 6bps buffer alone (+0.06%) — an ~80bps exit-
    level divergence on every BE event."""
    p = _flat_policy()
    p.be_after_tier, p.trail_after_tier = 1, 9
    p.gb_enabled, p.ts_enabled = False, False
    p.est_fee_bps, p.be_buffer_frac = 40.0, 6.0 / 1e4
    # bar1 fires tier 1 (+1%); bar2 pulls back through the BE floor but
    # stays above the raw buffer (low +0.30%)
    c, h, ll = _bars([(101.2, 100.6, 101.0), (101.0, 100.30, 100.4)])
    out = simulate_exit_policy(c, h, ll, 0, +1, 0.0, p,
                               max_bars=96, cost_pct=0.5)
    assert out.barrier == "trail"                # floored out, not stopped
    # realized = tier1 0.25*1% + remainder 0.75 * floor 0.0086
    expected = (0.25 * 0.01 + 0.75 * (2 * 40.0 / 1e4 + 6.0 / 1e4)) * 100
    assert abs(out.ret_pct - expected) < 1e-9
    # and with fees zeroed the old buffer-only floor is NOT hit by +0.30%
    p2 = _flat_policy()
    p2.be_after_tier, p2.trail_after_tier = 1, 9
    p2.gb_enabled, p2.ts_enabled = False, False
    p2.est_fee_bps, p2.be_buffer_frac = 0.0, 6.0 / 1e4
    out2 = simulate_exit_policy(c, h, ll, 0, +1, 0.0, p2,
                                max_bars=96, cost_pct=0.5)
    assert out2.barrier == "time"                # rides through the pullback


def test_trail_distance_mirrors_the_live_chandelier():
    """Live trail distance = max(trail_pct, k*sigma*sqrt(bars))
    (profit_tiers.py:429-437). At sigma_bar=0.003, k=3, bars=6 the
    chandelier term is 2.205% — the old static 1% leash stopped runners
    the live engine kept."""
    p = _flat_policy()
    p.trail_after_tier, p.be_after_tier = 1, 9
    p.gb_enabled, p.ts_enabled = False, False
    p.trail_frac, p.chandelier_k, p.chandelier_bars = 0.010, 3.0, 6
    p.tiers = [(0.01, 0.0, 0.25)]        # single tier: arms trail, 75% rides
    # tier 1 fires (+1%), peak +5%, pullback to +3.5% (1.5% off peak:
    # inside the 2.205% chandelier leash, OUTSIDE the old 1% one)
    c, h, ll = _bars([(101.2, 100.8, 101.0), (105.0, 103.5, 104.0),
                      (104.2, 103.5, 103.8)])
    out = simulate_exit_policy(c, h, ll, 0, +1, 0.003, p,
                               max_bars=96, cost_pct=0.5)
    assert out.barrier == "time"                 # survives the pullback
    # a pullback past peak-2.205% (low +2.5%) fires the trail
    c2, h2, ll2 = _bars([(101.2, 100.8, 101.0), (105.0, 103.5, 104.0),
                         (104.2, 102.5, 102.8)])
    out2 = simulate_exit_policy(c2, h2, ll2, 0, +1, 0.003, p,
                                max_bars=96, cost_pct=0.5)
    assert out2.barrier == "trail"


def test_giveback_tighten_zero_means_off_like_live():
    """profit_tiers.py:587: 0 < tighten_gain <= peak arms the tight rung —
    0 disables it. The old sim treated 0 as always-tight (locking 75%
    instead of 60% of the peak): inverted semantics."""
    p = _flat_policy()
    p.gb_enabled, p.be_after_tier, p.trail_after_tier = True, 9, 9
    p.ts_enabled = False
    p.gb_arm_frac, p.gb_arm_vol_mult = 0.005, 0.0
    p.gb_frac, p.gb_tight_frac, p.gb_tighten_frac = 0.40, 0.25, 0.0
    p.tiers = [(0.99, 0.0, 0.25)]        # tiers out of reach: pure give-back
    # peak +2% then a full retrace: with tighten OFF the lock is 60% of
    # peak (exit +1.2%); always-tight would have locked 75% (+1.5%)
    c, h, ll = _bars([(102.0, 101.0, 101.5), (101.5, 99.0, 99.5)])
    out = simulate_exit_policy(c, h, ll, 0, +1, 0.0, p,
                               max_bars=96, cost_pct=0.5)
    # barrier tags "sl" (no tier fired -> tier_idx==0 names the adverse
    # branch); the VALUE proves the give-back floor: exit at +1.2%
    # (0.6 * 2% lock), not -2% (stop) and not +1.5% (always-tight 0.75)
    assert out.barrier == "sl"
    assert abs(out.ret_pct - 1.2) < 1e-9
