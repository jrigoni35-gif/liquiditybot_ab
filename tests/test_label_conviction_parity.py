"""tests/test_label_conviction_parity.py — the exit-policy label sim must
mirror the live conviction-runner trail (W2-1).

The LIVE exit engine (risk/profit_tiers.ProfitTierEngine) tightens the
chandelier trail multiplicatively for a low-entry-conviction position
(`conviction_runner`, enabled in production with min_conf=0.55,
neutral_conf=0.70). The counterfactual label sim omitted it entirely, so any
candidate/bootstrap label for a signal with p_win in [0.55, 0.70) ran on a
WIDER leash than the live position would get — the counterfactual banked more
than reality, a systematic optimism bias on exactly the borderline-confidence
trades the meta-model most needs labeled honestly.

These pin the sim's tightened trail to the SAME implementation the live engine
uses (a single shared pure function), and prove the tightened label differs
from the unconditioned one.
"""
from datetime import datetime, timezone

import numpy as np

from core.state import Position
from ml.labeling import ExitPolicy, simulate_exit_policy
from risk.profit_tiers import ProfitTierEngine, conviction_trail_mult

_CR = {"enabled": True, "neutral_conf": 0.70, "min_conf": 0.55,
       "min_trail_mult": 0.6}


def _isolated_policy():
    """An ExitPolicy that isolates the TRAILING floor: no tier fires, no
    break-even, no give-back, hard stop far away — so the ONLY exit geometry in
    play is the conviction-scaled chandelier trail, and the outcome is a clean
    function of the trail distance."""
    return ExitPolicy(
        base_stop_frac=0.20, stop_vol_mult=0.0,
        tiers=[(9.9, 0.0, 0.25)],           # trigger 990%: never fires
        vol_scaled=False, be_after_tier=999,
        trail_after_tier=0,                 # trail armed from the first bar
        trail_frac=0.01, gb_enabled=False,
        cr_enabled=True, cr_neutral_conf=0.70,
        cr_min_conf=0.55, cr_min_trail_mult=0.6)


def _engine():
    return ProfitTierEngine({
        "trailing_stop": {"enabled": True, "activate_after_tier": 0,
                          "trail_pct": 1.0},
        "conviction_runner": _CR})


def _pos(conf, entry=100.0):
    return Position(position_id=f"cr-{conf}", symbol="T/USD",
                    direction="long", entry_price=entry, size=1.0,
                    original_size=1.0,
                    opened_at=datetime.now(timezone.utc), confidence=conf)


def _bars(path):
    """path: list of (high, low, close) -> arrays with a leading entry bar."""
    highs = [100.0] + [h for h, _, _ in path]
    lows = [100.0] + [ll for _, ll, _ in path]
    closes = [100.0] + [c for _, _, c in path]
    return np.array(closes), np.array(highs), np.array(lows)


def test_tightened_trail_banks_sooner_and_differs_from_unconditioned():
    """rise -> small pullback that breaches the TIGHTENED trail but not the
    full trail -> continue up. The low-conviction leash banks at the tightened
    floor; the unconditioned sim (today's behavior) rides the continuation to a
    strictly BIGGER gain — the optimism bias made explicit."""
    pol = _isolated_policy()
    # bar1: +5% high -> peak 5%; tightened(0.6x) floor 5-0.6=4.4%, full 4.0%
    # bar2: dip to 104.2 (=+4.2%) breaches the 4.4% tightened floor but sits
    #       above the 4.0% full floor -> tightened EXITS, full leash HOLDS
    # bar3: continue up to +8% -> the untightened runner rides it higher
    c, h, ll = _bars([(105.0, 100.5, 104.0),
                      (104.2, 104.2, 104.2),
                      (108.0, 107.5, 108.0)])
    tight = simulate_exit_policy(c, h, ll, 0, +1, 0.0, pol,
                                 max_bars=96, cost_pct=0.5, conviction=0.55)
    full = simulate_exit_policy(c, h, ll, 0, +1, 0.0, pol,
                                max_bars=96, cost_pct=0.5, conviction=None)
    assert tight.ret_pct < full.ret_pct          # the whole point of W2-1
    assert abs(tight.ret_pct - 4.4) < 1e-9        # banked at the tightened floor
    assert abs(full.ret_pct - 8.0) < 1e-9         # rode the continuation


def test_parity_sim_trail_distance_equals_live_engine_composed():
    """The sim's tightened trail distance must equal the LIVE engine's
    `_trail_distance_frac(...) * _conviction_trail_mult(...)` composed distance,
    computed by CALLING the real engine helpers — single source of truth, never
    a copied constant."""
    pol = _isolated_policy()
    eng = _engine()
    pos = _pos(0.55)
    conv = eng._conviction_trail_mult(pos)                     # live mult
    # live composed trail distance (sigma absent -> legacy trail, no time decay)
    expected_dist = eng._trail_distance_frac(pos, None, decay_mult=conv)
    c, h, ll = _bars([(105.0, 100.5, 104.0),      # arm trail at +5% peak
                      (104.2, 104.2, 104.2)])     # breach the tightened floor
    out = simulate_exit_policy(c, h, ll, 0, +1, 0.0, pol,
                               max_bars=96, cost_pct=0.5, conviction=0.55)
    peak_gain = 0.05
    assert abs(out.ret_pct / 100.0 - (peak_gain - expected_dist)) < 1e-12
    assert abs(conv - 0.6) < 1e-12                # sanity on the composed mult


def test_sim_and_engine_share_one_conviction_implementation():
    """The label sim and the live engine must resolve the conviction multiplier
    through the SAME pure function — no parallel formula to drift."""
    eng = _engine()
    for conf in (0.0, 0.50, 0.55, 0.60, 0.625, 0.70, 0.85):
        assert eng._conviction_trail_mult(_pos(conf)) == conviction_trail_mult(
            conf, True, 0.70, 0.55, 0.6)


def test_none_conviction_is_current_behavior_noop():
    """conviction=None (bootstrap / unavailable) must be byte-identical to the
    pre-fix sim: the full leash, every caller preserved (invariant 7)."""
    pol = _isolated_policy()
    c, h, ll = _bars([(105.0, 100.5, 104.0),
                      (104.2, 104.2, 104.2),
                      (108.0, 107.5, 108.0)])
    none_out = simulate_exit_policy(c, h, ll, 0, +1, 0.0, pol,
                                    max_bars=96, cost_pct=0.5, conviction=None)
    # high conviction (>= neutral) is also a full-leash no-op — same outcome
    high_out = simulate_exit_policy(c, h, ll, 0, +1, 0.0, pol,
                                    max_bars=96, cost_pct=0.5, conviction=0.85)
    assert none_out.ret_pct == high_out.ret_pct   # both full-leash: identical
    assert abs(none_out.ret_pct - 8.0) < 1e-9      # rode the continuation
