"""TANK quant-2 Task 2 (N): perp-basis momentum shadow feature.

basis_bps (execution/fair_value.py: fair value vs the Kraken mid) is a
LEVEL; its short-window drift is the lead-lag signal (perp flow leads
spot in crypto). d(basis_bps)/dt is computed over the configured window
where basis_bps already lives (FVState, rolled once per update - never
hot-path recomputation), per-second slope scaled x60 = bps/min
(wall-time discipline, THALES A-3), clamped and NaN-safe; a stale
Kraken touch (W2-23 kraken_stale_sec) zeroes it and clears the window
so a re-touch never fabricates a slope off a fossil sample.

Sections:
  1. window math (slope sign, magnitude, pruning, clamp, degenerate)
  2. engine integration through FairValueEngine.update
  3. staleness => 0.0
  4. build_features wiring (basis_mom_dir: side-relative, NaN-safe)
  5. config lift + guard bounds
"""
from types import SimpleNamespace

import pytest

from execution.fair_value import FVState, FairValueEngine
from ml.features import FEATURE_NAMES, build_features

IDX = {n: i for i, n in enumerate(FEATURE_NAMES)}


# ---------------------------------------------------------------- helpers
def _kbook(bid=100.0, ask=100.2):
    return {"bids": [[bid, 1.0]], "asks": [[ask, 1.0]]}


def _vbook(mid, depth=1_000_000.0, spread=0.2):
    return {"bids": [[mid - spread / 2.0, depth]],
            "asks": [[mid + spread / 2.0, depth]]}


def _roll(eng, st, samples):
    """samples = [(now, basis_bps), ...] -> final basis_mom_bps."""
    for now, basis in samples:
        st.basis_bps = basis
        eng._roll_basis_momentum(st, now)
    return st.basis_mom_bps


# ------------------------------------------------- 1. window math (unit)
def test_rising_basis_reads_positive_bps_per_min():
    eng = FairValueEngine({"basis_mom_window_sec": 60.0})
    st = FVState(asset="ETH")
    # +10bps over 60s = +10 bps/min (per-second slope x60)
    assert _roll(eng, st, [(0.0, 0.0), (60.0, 10.0)]) == pytest.approx(10.0)


def test_falling_basis_reads_negative():
    eng = FairValueEngine({"basis_mom_window_sec": 60.0})
    st = FVState(asset="ETH")
    assert _roll(eng, st, [(0.0, 4.0), (30.0, 1.0)]) == pytest.approx(-6.0)


def test_single_sample_is_zero():
    eng = FairValueEngine({"basis_mom_window_sec": 60.0})
    st = FVState(asset="ETH")
    assert _roll(eng, st, [(0.0, 25.0)]) == 0.0


def test_window_prunes_old_samples():
    eng = FairValueEngine({"basis_mom_window_sec": 60.0})
    st = FVState(asset="ETH")
    # the t=0 spike leaves the 60s window by t=90: slope is measured
    # from t=30 (flat), not from the fossil
    mom = _roll(eng, st, [(0.0, -50.0), (30.0, 10.0), (90.0, 10.0)])
    assert mom == pytest.approx(0.0)


def test_slope_is_clamped():
    eng = FairValueEngine({"basis_mom_window_sec": 60.0})
    st = FVState(asset="ETH")
    assert _roll(eng, st, [(0.0, 0.0), (30.0, 100_000.0)]) == 240.0
    st2 = FVState(asset="ETH")
    assert _roll(eng, st2, [(0.0, 0.0), (30.0, -100_000.0)]) == -240.0


def test_sub_second_span_is_denominator_floored():
    # two polls 0.5s apart must not amplify innovation noise x120: the
    # per-second denominator floors at 1s (an EPS-class guard, not a knob)
    eng = FairValueEngine({"basis_mom_window_sec": 60.0})
    st = FVState(asset="ETH")
    assert _roll(eng, st, [(0.0, 0.0), (0.5, 2.0)]) == pytest.approx(120.0)


def test_clock_backwards_resets_never_fabricates():
    eng = FairValueEngine({"basis_mom_window_sec": 60.0})
    st = FVState(asset="ETH")
    assert _roll(eng, st, [(100.0, 5.0), (40.0, 9.0)]) == 0.0


def test_window_length_is_config_lifted():
    st = FVState(asset="ETH")
    # 120s window keeps the t=0 sample that a 60s window would prune
    mom = _roll(FairValueEngine({"basis_mom_window_sec": 120.0}), st,
                [(0.0, 0.0), (30.0, 5.0), (90.0, 15.0)])
    assert mom == pytest.approx(15.0 / 90.0 * 60.0)


# ------------------------------------- 2. engine integration (update)
def test_update_rolls_momentum_from_real_basis():
    # alpha=1: fair value tracks the (depth-dominant) venue microprice;
    # venue mid +2bps over 30s vs a fixed Kraken touch -> ~4 bps/min
    eng = FairValueEngine({"ema_alpha": 1.0})
    eng.update("ETH", [_vbook(100.1)], _kbook(), now=0.0)
    st = eng.update("ETH", [_vbook(100.12)], _kbook(), now=30.0)
    assert st.basis_bps == pytest.approx(2.0, rel=0.02)
    assert st.basis_mom_bps == pytest.approx(4.0, rel=0.05)


def test_fresh_state_defaults_to_zero():
    assert FairValueEngine({}).state("BTC").basis_mom_bps == 0.0


# --------------------------------------------------- 3. staleness => 0
def test_stale_kraken_touch_zeroes_momentum_and_clears_window():
    eng = FairValueEngine({"ema_alpha": 1.0, "kraken_stale_sec": 120.0})
    eng.update("ETH", [_vbook(100.1)], _kbook(), now=0.0)
    st = eng.update("ETH", [_vbook(100.12)], _kbook(), now=30.0)
    assert st.basis_mom_bps != 0.0
    # Kraken stops voting; 270s later the touch is stale (W2-23)
    st = eng.update("ETH", [_vbook(100.12)], {}, now=300.0)
    assert st.basis_mom_bps == 0.0
    assert st.basis_hist == []
    # a fresh re-touch must re-seed, not diff against a fossil sample
    st = eng.update("ETH", [_vbook(100.12)], _kbook(), now=330.0)
    assert st.basis_mom_bps == 0.0


def test_no_vote_cycle_never_fabricates_momentum():
    eng = FairValueEngine({"ema_alpha": 1.0})
    eng.update("ETH", [_vbook(100.1)], _kbook(), now=0.0)
    st = eng.update("ETH", [], {}, now=30.0)     # nobody voted
    assert st.updated is False
    assert st.basis_mom_bps == 0.0


# ----------------------------------------- 4. build_features wiring
def _vector(direction, fv=None):
    candles = [{"time": 100 + i * 300, "open": 10 + i * 0.1,
                "high": 10.3 + i * 0.1, "low": 9.9 + i * 0.1,
                "close": 10.2 + i * 0.1, "volume": 5.0}
               for i in range(60)]
    view = {"candles": candles, "imbalance_ratio": 1.6,
            "funding_rate": 0.0002}
    fv = fv or SimpleNamespace(edge_bps=lambda side: 7.0, basis_bps=12.0)
    vol = SimpleNamespace(sigma_bar_pct=0.4, percentile=55.0)
    liq = SimpleNamespace(spread_bps=4.0, depth_top10_usd=250_000.0)
    macro = SimpleNamespace(label="range", momentum_score=0.6,
                            drawdown_pct=20.0)
    sent = SimpleNamespace(score=0.3, fear_spike=False)
    return build_features("BTC", direction, 0.7, view, fv, vol, liq,
                          macro, None, sent, {},
                          extras={"ts": 1_700_000_000.0})


def _fv(mom):
    return SimpleNamespace(edge_bps=lambda side: 7.0, basis_bps=12.0,
                           basis_mom_bps=mom)


def test_basis_mom_dir_is_side_relative_and_scaled():
    # same clip-then-/10 idiom as basis_dir/venue_disloc_dir
    assert _vector("long", _fv(12.0))[IDX["basis_mom_dir"]] \
        == pytest.approx(1.2)
    assert _vector("short", _fv(12.0))[IDX["basis_mom_dir"]] \
        == pytest.approx(-1.2)


def test_basis_mom_dir_clipped_and_nan_safe():
    assert _vector("long", _fv(45.0))[IDX["basis_mom_dir"]] \
        == pytest.approx(3.0)
    assert _vector("long", _fv(float("nan")))[IDX["basis_mom_dir"]] == 0.0
    # a legacy fv stub without the field (pre-v9 harness) reads 0.0
    assert _vector("long")[IDX["basis_mom_dir"]] == 0.0


# ------------------------------------------- 5. config lift + guard
def test_engine_lifts_and_bounds_the_window_knob():
    assert FairValueEngine({}).basis_mom_window_sec == 60.0
    assert FairValueEngine(
        {"basis_mom_window_sec": 240.0}).basis_mom_window_sec == 240.0


def test_guard_bounds_for_the_basis_momentum_knob():
    from core.config_guard import validate

    def fatals(cfg):
        return [m for s, m in validate(cfg) if s == "FATAL"]

    base = {"system": {"dry_run": True}}
    ok = {**base, "fair_value": {"basis_mom_window_sec": 60.0}}
    assert not any("basis_mom_window_sec" in m for m in fatals(ok))
    assert any("basis_mom_window_sec" in m for m in fatals(
        {**base, "fair_value": {"basis_mom_window_sec": 2.0}}))
    assert any("basis_mom_window_sec" in m for m in fatals(
        {**base, "fair_value": {"basis_mom_window_sec": 5000.0}}))
    # coherence: a window at/below the slow-cycle poll gap (5s x 6 = 30s
    # default) can never hold two samples - structurally zero forever
    assert any("basis_mom_window_sec" in m for m in fatals(
        {**base, "fair_value": {"basis_mom_window_sec": 25.0}}))
