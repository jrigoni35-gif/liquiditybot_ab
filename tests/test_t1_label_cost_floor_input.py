"""tests/test_t1_label_cost_floor_input.py — Task 1 (#103): close the P3.5
"documented residual" by threading a REAL register-time cost estimate into
the tier-1 cost floor.

P3.5 (tests/test_p35_label_sim_parity.py) wired risk.profit_tiers.
tier1_cost_floor_pct into ml.labeling.ExitPolicy._tier_trigger /
simulate_exit_policy via est_cost_bps, but every real caller passed the
default 0.0 — the floor was mechanically correct yet INERT in production,
so label-sim geometry diverged from the live book's floored geometry.

The register-time estimate already existed: CandidateLabeler._cost_pct(cand)
(fee floor + the candidate's own capped spread, captured at register time)
is ALREADY the cost_pct fed to the net-of-cost label. This closes the
residual by threading that SAME quantity into est_cost_bps at the two real
call sites — CandidateLabeler._label's exit-policy dispatch (ml/history.py
~:776) and bootstrap_dataset's simulate_exit_policy call (~:939) — via the
documented pct -> bps inverse of tier1_cost_floor_pct's own bps -> pct
conversion: est_cost_bps = cost_pct * 100.0.

These pins CALL the live tier1_cost_floor_pct helper to compute expected
floor values — never a re-derived constant (same discipline as the P3.5
file).
"""
import numpy as np
import pytest

from ml.history import CandidateLabeler, HistoryStore, bootstrap_dataset
from ml.labeling import ExitPolicy, simulate_exit_policy, triple_barrier
from risk.profit_tiers import tier1_cost_floor_pct


def _isolated_tier1_policy(mult=3.0, tier1_frac=0.0005, ts_enabled=False,
                          ts_max=5, ts_min_frac=0.5):
    """Same isolation idiom as test_p35_label_sim_parity.py: no BE, no
    trail, no give-back — the sole exit geometry is the (possibly floored)
    tier-1 trigger, closing 100% in one shot, plus the optional time-stop."""
    return ExitPolicy(
        base_stop_frac=0.20, stop_vol_mult=0.0,
        tiers=[(tier1_frac, 0.0, 1.0)],
        vol_scaled=False, be_after_tier=999, trail_after_tier=999,
        trail_frac=0.01, gb_enabled=False, min_trigger_cost_mult=mult,
        ts_enabled=ts_enabled, ts_max_bars_no_progress=ts_max,
        ts_min_mfe_frac=ts_min_frac)


def _labeler(tmp_path, ml_cfg, policy):
    store = HistoryStore(str(tmp_path / "hist.csv"))
    return CandidateLabeler(store, ml_cfg, exit_policy=policy)


# ============================================================================
# (a) the CandidateLabeler's own cost stack now floors tier 1 in the sim
# ============================================================================

def test_label_dispatch_floors_tier1_on_the_candidates_own_cost_stack(tmp_path):
    """THE point of Task 1: a favorable path that clears the UNFLOORED
    (legacy) tier-1 trigger but stays below the candidate's own cost floor
    must NOT fire tier 1 — it must ride on (here, time-stop scratch) instead
    of resolving at the cheap configured trigger. Sanity leg: the identical
    path WOULD resolve at tier 1, bar 1 with est_cost_bps=0 (the pre-fix,
    every-real-caller-passes-0.0 behavior) — proving the floor, not
    something else, is what changed the outcome."""
    mult, tier1_frac, ts_max, ts_min_frac = 3.0, 0.0005, 3, 0.5
    pol = _isolated_tier1_policy(mult=mult, tier1_frac=tier1_frac,
                                 ts_enabled=True, ts_max=ts_max,
                                 ts_min_frac=ts_min_frac)
    ml_cfg = {"label_mode": "exit_policy", "label_include_spread": True,
             "label_spread_cap_bps": 60.0, "label_round_trip_cost_pct": 0.5}
    lab = _labeler(tmp_path, ml_cfg, pol)
    cand = {"spread_bps": 10.0}
    cost = lab._cost_pct(cand)                       # 0.5% fee + 0.10% spread
    assert cost == pytest.approx(0.6)

    floor_frac = tier1_cost_floor_pct(mult, cost * 100.0) / 100.0  # LIVE helper
    assert floor_frac > tier1_frac, "the floor must actually bind here"

    # 0.3x the floor: comfortably clears the raw trigger, comfortably under
    # BOTH the floor itself and ts_min_frac(0.5) x floor (avoids a boundary
    # exactly at the threshold, which floating-point rounding could tip
    # either way)
    peak = floor_frac * 0.3
    assert peak > tier1_frac
    assert peak < ts_min_frac * floor_frac
    closes = np.array([100.0] + [100.0 * (1 + peak)] * ts_max)
    highs = closes.copy()
    lows = np.array([100.0] + [100.0] * ts_max)      # never breach the hard stop

    out = lab._label(closes, highs, lows, 0, +1, 0.0, cost)
    assert out.barrier == "time_stop", (
        f"the floor should have blocked tier 1; got barrier={out.barrier!r}")
    assert out.bars_held == ts_max

    unfloored = simulate_exit_policy(closes, highs, lows, 0, +1, 0.0, pol,
                                     max_bars=96, cost_pct=cost)
    assert unfloored.barrier == "tier" and unfloored.bars_held == 1


# ============================================================================
# (b) the est_cost_bps handed to the sim equals _cost_pct(cand) * 100.0
# ============================================================================

def test_label_dispatch_threads_cost_pct_times_100_as_est_cost_bps(
        tmp_path, monkeypatch):
    pol = _isolated_tier1_policy()
    ml_cfg = {"label_mode": "exit_policy", "label_include_spread": True,
             "label_spread_cap_bps": 60.0, "label_round_trip_cost_pct": 0.5}
    lab = _labeler(tmp_path, ml_cfg, pol)
    cand = {"spread_bps": 37.0}
    cost = lab._cost_pct(cand)
    assert cost == pytest.approx(0.87)               # 0.5% fee + 37bps spread

    import ml.history as history_mod
    real_sim = history_mod.simulate_exit_policy
    captured: dict = {}

    def spy(*a, **kw):
        captured.update(kw)
        return real_sim(*a, **kw)

    monkeypatch.setattr(history_mod, "simulate_exit_policy", spy)
    closes = np.array([100.0, 100.1])
    highs = np.array([100.0, 100.1])
    lows = np.array([100.0, 100.0])
    lab._label(closes, highs, lows, 0, +1, 0.0, cost)

    assert "est_cost_bps" in captured, "est_cost_bps must be threaded explicitly"
    assert captured["est_cost_bps"] == pytest.approx(cost * 100.0)
    assert captured["est_cost_bps"] == pytest.approx(87.0)


# ============================================================================
# (c) the bootstrap path passes its cost the same way
# ============================================================================

def test_bootstrap_threads_cost_pct_times_100_as_est_cost_bps(monkeypatch):
    import ml.history as history_mod
    real_sim = history_mod.simulate_exit_policy
    captured: list = []

    def spy(*a, **kw):
        captured.append(kw)
        return real_sim(*a, **kw)

    monkeypatch.setattr(history_mod, "simulate_exit_policy", spy)

    t = np.arange(600)
    closes = list(100.0 * (1.0 + 0.15 * np.sin(t / 11.0)))
    candles = [{"time": 1000 + 300 * i, "close": c, "high": c * 1.01,
               "low": c * 0.99, "volume": 100.0 + i}
              for i, c in enumerate(closes)]
    cost_pct = 0.63
    X, y = bootstrap_dataset(candles, label_mode="exit_policy",
                             exit_policy=ExitPolicy(), cost_pct=cost_pct)
    assert len(X) > 0 and len(captured) > 0, "at least one EMA cross must simulate"
    assert all(kw["est_cost_bps"] == pytest.approx(cost_pct * 100.0)
              for kw in captured)
    assert captured[0]["est_cost_bps"] == pytest.approx(63.0)


# ============================================================================
# (d) label_include_spread=False still floors on the fee-only cost stack
# ============================================================================

def test_label_include_spread_false_still_floors_on_fee_only_cost(tmp_path):
    mult, tier1_frac, ts_max, ts_min_frac = 3.0, 0.0005, 3, 0.5
    pol = _isolated_tier1_policy(mult=mult, tier1_frac=tier1_frac,
                                 ts_enabled=True, ts_max=ts_max,
                                 ts_min_frac=ts_min_frac)
    ml_cfg = {"label_mode": "exit_policy", "label_include_spread": False,
             "label_round_trip_cost_pct": 0.5, "label_spread_cap_bps": 60.0}
    lab = _labeler(tmp_path, ml_cfg, pol)
    # a huge spread must be IGNORED entirely: label_include_spread=False
    cand = {"spread_bps": 5000.0}
    cost = lab._cost_pct(cand)
    assert cost == pytest.approx(0.5), "spread must be dropped, fee floor only"

    floor_frac = tier1_cost_floor_pct(mult, cost * 100.0) / 100.0  # LIVE helper
    assert floor_frac > tier1_frac

    peak = floor_frac * 0.3        # see (a) for why not exactly the threshold
    assert peak > tier1_frac
    assert peak < ts_min_frac * floor_frac
    closes = np.array([100.0] + [100.0 * (1 + peak)] * ts_max)
    highs = closes.copy()
    lows = np.array([100.0] + [100.0] * ts_max)

    out = lab._label(closes, highs, lows, 0, +1, 0.0, cost)
    assert out.barrier == "time_stop"
    assert out.bars_held == ts_max


# ============================================================================
# (e) triple_barrier mode is unaffected by the est_cost_bps threading
# ============================================================================

def test_triple_barrier_mode_dispatch_unaffected(tmp_path):
    ml_cfg = {"label_mode": "triple_barrier", "label_pt_vol_mult": 8.0,
             "label_sl_vol_mult": 6.0, "label_max_bars": 50,
             "label_round_trip_cost_pct": 0.5}
    # an exit_policy IS present, but label_mode="triple_barrier" must still
    # dispatch to the legacy barrier, untouched by est_cost_bps threading
    pol = _isolated_tier1_policy(mult=3.0, tier1_frac=0.0005)
    lab = _labeler(tmp_path, ml_cfg, pol)
    assert lab.label_mode == "triple_barrier"

    closes = np.array([100.0, 100.5, 101.5, 100.2])
    highs = np.array([100.0, 100.6, 101.6, 100.3])
    lows = np.array([100.0, 100.4, 101.4, 100.1])
    cost = 0.5
    got = lab._label(closes, highs, lows, 0, +1, 0.02, cost)
    want = triple_barrier(closes, highs, lows, 0, +1, 0.02, lab.pt, lab.sl,
                          lab.horizon, cost_pct=cost)
    assert got == want
