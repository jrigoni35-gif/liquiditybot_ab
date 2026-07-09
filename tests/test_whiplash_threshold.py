"""Whiplash-threshold calibration (the 45h entry-starvation regression).

whiplash = std of the [0,3]-clamped order-book imbalance over the last
20 snapshots, so its structural ceiling is 1.5. Live evidence (45h,
~2,600 samples, healthy 0-2bps-spread Kraken books at the ~30s cadence):
p50~1.1, p95~1.27, max 1.41. The old 0.55 threshold sat BELOW the healthy
5th percentile, labeled every cycle "spoofy" (size_mult=0.0), and vetoed
100% of entries - silently, because the sizer veto logged at DEBUG.

Under test: the recalibrated default discriminates (healthy churn passes,
ceiling-level flip-flopping still fires) and config_guard rejects
structurally incoherent thresholds.
"""

from core.config_guard import validate
from regime.liquidity_regime import LiquidityRegimeEngine


def _book(bid_usd: float, ask_usd: float, mid: float = 100.0,
          levels: int = 10) -> dict:
    """Tight-spread book with the given total notional per side."""
    bids = [[mid - 0.01 * (i + 1), (bid_usd / levels) / mid]
            for i in range(levels)]
    asks = [[mid + 0.01 * (i + 1), (ask_usd / levels) / mid]
            for i in range(levels)]
    return {"bids": bids, "asks": asks}


def _run(engine, books, asset="T"):
    now = 1_000_000.0
    st = None
    for b in books:
        st = engine.update(asset, b, b, now=now)
        now += 30.0
    assert st is not None, "books fixture must not be empty"
    return st


def test_default_threshold_matches_calibration():
    eng = LiquidityRegimeEngine({})
    assert abs(eng.whiplash_threshold - 1.45) < 1e-9


def test_healthy_churn_is_not_spoofy():
    """Alternating 3:1 / 1:3 imbalance = std ~1.33, HEAVIER churn than the
    live healthy p95 (~1.27) - and must still classify tradeable."""
    eng = LiquidityRegimeEngine({"min_depth_usd": 100_000})
    heavy = _book(300_000, 100_000)
    light = _book(100_000, 300_000)
    st = _run(eng, [heavy, light] * 10)
    assert st.imbalance_whiplash > 1.0          # churn genuinely measured
    assert st.label != "spoofy"
    assert st.size_mult > 0.0                   # entries stay sizeable


def test_ceiling_level_flip_flop_still_fires():
    """One-sided books flipping side every snapshot push the std toward
    the 1.5 ceiling - the detector must remain alive for this signature."""
    eng = LiquidityRegimeEngine({"min_depth_usd": 100_000})
    all_bid = _book(400_000, 1.0)               # imbalance -> 3.0 (clamped)
    all_ask = _book(1.0, 400_000)               # imbalance -> ~0.0
    st = _run(eng, [all_bid, all_ask] * 10)
    assert st.imbalance_whiplash >= 1.45
    assert st.label == "spoofy"
    assert st.size_mult == 0.0
    assert st.reduce_only is True               # exits still allowed


def _whiplash_findings(threshold):
    cfg = {"liquidity_regime": {"imbalance_whiplash_threshold": threshold}}
    return [(s, m) for s, m in validate(cfg) if "whiplash" in m]


def test_guard_default_is_clean():
    assert _whiplash_findings(1.45) == []


def test_guard_flags_always_on_threshold():
    assert any(s == "FATAL" for s, _ in _whiplash_findings(0.0))
    assert any(s == "FATAL" for s, _ in _whiplash_findings(-1.0))


def test_guard_flags_dead_detector():
    assert any(s == "WARN" for s, _ in _whiplash_findings(1.5))
    assert any(s == "WARN" for s, _ in _whiplash_findings(2.0))


def test_guard_flags_below_healthy_baseline():
    # the historical 0.55 must never come back silently
    assert any(s == "WARN" for s, _ in _whiplash_findings(0.55))
