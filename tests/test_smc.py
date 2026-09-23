"""strategies/smc.py — Smart Money Concepts feature engineering.

Contract under test, one section per requested concept:
  1. mtf_align       - LTF/HTF EMA-cross agreement vs. trade direction,
                        missing timeframes drop their vote (never force
                        a tie), no direction -> neutral
  2. pd_zone         - price's position in the recent swing range,
                        short history degrades to neutral (0.5)
  3. liq_pocket_pull - magnetism toward the swing extreme beyond price,
                        in the trade's direction only
  4. fvg_pull        - pull toward the nearest unfilled 3-candle
                        imbalance ahead of price, direction-gated
  5. fvg_liq_confluence - overlap between the nearest FVG and the
                        liquidity-pocket target
  6. poc_dist / va_pos - distance to the volume-profile POC and
                        position vs. the Value Area

Plus: SMCEngine.compute() end-to-end (garbage/disabled -> neutral,
never raises) and core/config_guard.py coherence checks.
"""

import math

from core.config_guard import validate
from strategies.smc import (NEUTRAL, SMCEngine, fvg_liq_confluence,
                            fvg_pull, liq_pocket_pull, mtf_align, pd_zone,
                            poc_dist, va_pos)

EPS = 1e-9


def _flat_bars(n, price=100.0, vol=0.0):
    return [(float(i), price, price + 1, price - 1, price, vol)
            for i in range(n)]


# ---------------------------------------------------------------------
# 1. MTF context
# ---------------------------------------------------------------------
def test_mtf_align_full_agreement_long():
    ltf = [100 + 0.5 * i for i in range(40)]
    htf = [80 + 1.0 * i for i in range(30)]
    assert mtf_align(ltf, htf, "long", {}) == 1.0


def test_mtf_align_full_disagreement_when_direction_flipped():
    ltf = [100 + 0.5 * i for i in range(40)]
    htf = [80 + 1.0 * i for i in range(30)]
    assert mtf_align(ltf, htf, "short", {}) == -1.0


def test_mtf_align_neutral_on_flat_trend():
    flat = [100.0] * 40
    assert mtf_align(flat, flat, "long", {}) == 0.0


def test_mtf_align_missing_htf_drops_vote_not_forces_tie():
    ltf = [100 + 0.5 * i for i in range(40)]
    # no HTF data at all - the LTF vote alone should still carry
    assert mtf_align(ltf, [], "long", {}) == 1.0


def test_mtf_align_neutral_without_a_direction():
    ltf = [100 + 0.5 * i for i in range(40)]
    assert mtf_align(ltf, ltf, None, {}) == 0.0
    assert mtf_align(ltf, ltf, "sideways", {}) == 0.0


# ---------------------------------------------------------------------
# 2. Premium / discount zone
# ---------------------------------------------------------------------
def _pd_bars(close, n=20, lo=90, hi=110):
    bars = [(float(i), 100, 101, 99, 100, 0) for i in range(n - 1)]
    bars.append((float(n - 1), close, hi, lo, close, 0))
    return bars


def test_pd_zone_near_range_top_is_premium():
    assert pd_zone(_pd_bars(108), {"lookback": 20}) == 0.9


def test_pd_zone_near_range_bottom_is_discount():
    assert pd_zone(_pd_bars(92), {"lookback": 20}) == 0.1


def test_pd_zone_neutral_below_min_bars():
    assert pd_zone(_flat_bars(5), {"lookback": 20}) == 0.5


def test_pd_zone_neutral_on_zero_width_range():
    assert pd_zone(_flat_bars(10, price=100.0), {"lookback": 20}) == 0.5


def test_pd_zone_empty_history():
    assert pd_zone([], {"lookback": 20}) == 0.5


# ---------------------------------------------------------------------
# 3. Liquidity pockets
# ---------------------------------------------------------------------
_LIQ_BARS = [
    (0.0, 100, 101, 99, 100, 0), (1.0, 100, 101, 99, 100, 0),
    (2.0, 100, 101, 99, 100, 0), (3.0, 100, 101, 99, 100, 0),
    (4.0, 100, 101, 99, 100, 0), (5.0, 100, 101, 99, 100, 0),
    (6.0, 104, 105, 103, 104, 0), (7.0, 104.8, 104.9, 104.7, 104.9, 0),
]


def test_liq_pocket_pull_strong_when_price_near_swing_high_long():
    cfg = {"lookback": 48, "pull_max_pct": 3.0}
    pull = liq_pocket_pull(_LIQ_BARS, "long", cfg)
    assert pull > 0.9


def test_liq_pocket_pull_zero_when_far_from_target_short():
    cfg = {"lookback": 48, "pull_max_pct": 3.0}
    assert liq_pocket_pull(_LIQ_BARS, "short", cfg) == 0.0


def test_liq_pocket_pull_zero_on_bad_direction():
    assert liq_pocket_pull(_LIQ_BARS, "sideways", {"lookback": 48}) == 0.0


def test_liq_pocket_pull_zero_on_empty_history():
    assert liq_pocket_pull([], "long", {"lookback": 48}) == 0.0


# ---------------------------------------------------------------------
# 4. Fair Value Gaps + 5. FVG/liquidity confluence
# ---------------------------------------------------------------------
# 8-bar fixture: a clean bullish FVG [100, 103.5] forms mid-history, then
# a sharp drop later forms a second (bearish) unfilled gap [96, 103.5]
# without retracing back into the bullish one. Current price = 95.
_GAP_BARS = [
    (0.0, 98, 99, 97, 98, 0), (1.0, 98, 99, 97, 98, 0),
    (2.0, 98, 99, 97, 98, 0), (3.0, 99, 100, 98, 99, 0),
    (4.0, 103, 104, 99, 103, 0), (5.0, 107, 108, 103.5, 107, 0),
    (6.0, 106, 108.5, 104, 106, 0), (7.0, 95, 96, 94, 95, 0),
]


def test_fvg_pull_positive_toward_nearest_unfilled_gap_ahead():
    out = fvg_pull(_GAP_BARS, "long", {"pull_max_pct": 10.0})
    assert math.isclose(out, 0.5, abs_tol=1e-6)


def test_fvg_pull_zero_when_no_gap_ahead_in_direction():
    # both unfilled gaps sit ABOVE current price -> nothing for a short
    assert fvg_pull(_GAP_BARS, "short", {"pull_max_pct": 10.0}) == 0.0


def test_fvg_pull_zero_beyond_cap():
    assert fvg_pull(_GAP_BARS, "long", {"pull_max_pct": 0.01}) == 0.0


def test_fvg_pull_zero_on_bad_direction():
    assert fvg_pull(_GAP_BARS, "up", {"pull_max_pct": 10.0}) == 0.0


def test_fvg_liq_confluence_detects_overlap_within_tolerance():
    out = fvg_liq_confluence(_GAP_BARS, "long",
                             {"confluence_tol_pct": 10.0}, {"lookback": 48})
    assert out == 1.0


def test_fvg_liq_confluence_zero_when_tolerance_too_tight():
    out = fvg_liq_confluence(_GAP_BARS, "long",
                             {"confluence_tol_pct": 0.1}, {"lookback": 48})
    assert out == 0.0


def test_fvg_liq_confluence_zero_without_candidates_in_direction():
    out = fvg_liq_confluence(_GAP_BARS, "short",
                             {"confluence_tol_pct": 10.0}, {"lookback": 48})
    assert out == 0.0


# ---------------------------------------------------------------------
# 6. Volume Profile (POC / Value Area)
# ---------------------------------------------------------------------
def _vp_bars_offset():
    bars = []
    ts = 0.0
    for _ in range(15):
        bars.append((ts, 100.0, 101.0, 100.0, 100.5, 100.0))
        ts += 1.0
    for _ in range(5):
        bars.append((ts, 110.0, 111.0, 110.0, 110.5, 1.0))
        ts += 1.0
    return bars


_VP_CFG = {"lookback_bars": 20, "n_bins": 22, "value_area_pct": 0.68,
          "poc_dist_cap_pct": 5.0}


def test_poc_dist_clamped_when_price_far_from_heavy_volume_zone():
    assert poc_dist(_vp_bars_offset(), _VP_CFG) == 1.0


def test_va_pos_positive_above_value_area():
    assert va_pos(_vp_bars_offset(), _VP_CFG) == 1.0


def test_poc_dist_small_when_price_inside_heavy_zone():
    bars = [(float(i), 100.0, 101.0, 99.0, 100.0, 10.0) for i in range(20)]
    out = poc_dist(bars, _VP_CFG)
    assert abs(out) < 0.05


def test_va_pos_zero_when_price_inside_value_area():
    bars = [(float(i), 100.0, 101.0, 99.0, 100.0, 10.0) for i in range(20)]
    assert va_pos(bars, _VP_CFG) == 0.0


def test_volume_profile_neutral_below_min_bars():
    bars = [(float(i), 100.0, 101.0, 99.0, 100.0, 10.0) for i in range(5)]
    assert poc_dist(bars, _VP_CFG) == 0.0
    assert va_pos(bars, _VP_CFG) == 0.0


# ---------------------------------------------------------------------
# SMCEngine: config-driven wrapper, fail-safe contract
# ---------------------------------------------------------------------
def _candles(n=60, start=100.0, step=0.1, vol=10.0):
    out = []
    p = start
    for i in range(n):
        o, c = p, p + step
        hi, lo = max(o, c) + 0.05, min(o, c) - 0.05
        out.append({"ts": float(i * 300), "open": o, "high": hi,
                    "low": lo, "close": c, "volume": vol})
        p = c
    return out


def test_engine_disabled_returns_neutral():
    eng = SMCEngine({"enabled": False})
    out = eng.compute("ETH", _candles(), "long", 0.0)
    assert out == NEUTRAL
    assert eng.status() == {"enabled": False}


def test_engine_garbage_candles_never_raises_and_degrades_neutral():
    eng = SMCEngine({})
    out = eng.compute("ETH", [{"junk": 1}, None, {"ts": "bad"}], "long", 0.0)
    assert out == NEUTRAL
    out2 = eng.compute("ETH", None, "long", 0.0, daily_candles="not a list")
    assert all(math.isfinite(v) for v in out2.values())


def test_engine_produces_finite_values_within_contract_ranges():
    eng = SMCEngine({})
    candles = _candles(n=80, step=0.3)
    daily = _candles(n=30, start=80.0, step=1.0, vol=100.0)
    out = eng.compute("BTC", candles, "long", 1000.0, daily_candles=daily)
    assert set(out.keys()) == set(NEUTRAL.keys())
    ranges = {"mtf_align": (-1, 1), "pd_zone": (0, 1),
              "liq_pocket_pull": (0, 1), "fvg_pull": (0, 1),
              "fvg_liq_confluence": (0, 1), "poc_dist": (-1, 1),
              "va_pos": (-1, 1)}
    for k, v in out.items():
        assert math.isfinite(v)
        lo, hi = ranges[k]
        assert lo - 1e-9 <= v <= hi + 1e-9


def test_engine_status_reflects_last_asset_snapshot():
    eng = SMCEngine({})
    eng.compute("ETH", _candles(), "long", 0.0)
    status = eng.status()
    assert status["enabled"] is True
    assert "ETH" in status["assets"]
    assert set(status["assets"]["ETH"].keys()) == set(NEUTRAL.keys())


# ---------------------------------------------------------------------
# feature-vector schema integration
# ---------------------------------------------------------------------
def test_feature_names_include_smc_columns_in_order():
    from ml.features import FEATURE_NAMES
    expected = ["mtf_align", "pd_zone", "liq_pocket_pull", "fvg_pull",
               "fvg_liq_confluence", "poc_dist", "va_pos"]
    idx = [FEATURE_NAMES.index(n) for n in expected]
    assert idx == sorted(idx)                       # contiguous, in order
    assert FEATURE_NAMES[-2:] == ["direction", "gate_confidence"]


def test_contract_declares_ranges_for_every_smc_feature():
    from ml.contracts import _RANGES, SCHEMA_VERSION, get_contract
    for name in ("mtf_align", "pd_zone", "liq_pocket_pull", "fvg_pull",
                "fvg_liq_confluence", "poc_dist", "va_pos"):
        assert name in _RANGES
    assert SCHEMA_VERSION == 10  # deliberate re-pin: v9 shadow pair, v10
    # dark-pool block (dp_* SHADOW, 64->68)
    contract = get_contract()
    assert contract.n == len(contract.names)


def test_build_features_accepts_smc_feats_and_clips_garbage():
    import numpy as np
    from ml.features import FEATURE_NAMES, build_features

    class _St:
        def __getattr__(self, item):
            return 0.0

        def edge_bps(self, *_a, **_k):
            return 0.0

    view = {"candles": [], "imbalance_ratio": 1.0, "funding_rate": 0.0}
    feats = build_features(
        "ETH", "long", 0.5, view, _St(), _St(), _St(), _St(), None, None,
        {"mtf_align": 5.0, "pd_zone": -3.0}, other_asset=None, extras=None)
    assert feats.shape[0] == len(FEATURE_NAMES)
    assert np.isfinite(feats).all()
    i = FEATURE_NAMES.index("mtf_align")
    assert feats[i] == 1.0                           # clipped to [-1, 1]
    j = FEATURE_NAMES.index("pd_zone")
    assert feats[j] == 0.0                            # clipped to [0, 1]
    k = FEATURE_NAMES.index("liq_pocket_pull")
    assert feats[k] == 0.0                            # missing key -> default

    feats_empty = build_features(
        "ETH", "short", 0.5, view, _St(), _St(), _St(), _St(), None, None,
        {}, other_asset=None, extras=None)
    assert feats_empty.shape[0] == len(FEATURE_NAMES)
    assert np.isfinite(feats_empty).all()
    assert feats_empty[FEATURE_NAMES.index("pd_zone")] == 0.5   # dict default


# ---------------------------------------------------------------------
# config_guard coherence
# ---------------------------------------------------------------------
def _fatals(cfg):
    return [m for s, m in validate(cfg) if s == "FATAL"]


def test_guard_rejects_inverted_mtf_periods():
    assert any("smc.mtf.ltf_slow_period" in m for m in _fatals(
        {"smc": {"enabled": True, "mtf": {"ltf_fast_period": 20,
                                          "ltf_slow_period": 10}}}))


def test_guard_rejects_zero_or_negative_pct_knobs():
    assert any("smc.liquidity.pull_max_pct" in m for m in _fatals(
        {"smc": {"enabled": True, "liquidity": {"pull_max_pct": 0.0}}}))
    assert any("smc.fvg.pull_max_pct" in m for m in _fatals(
        {"smc": {"enabled": True, "fvg": {"pull_max_pct": -1.0}}}))


def test_guard_rejects_bad_value_area_pct():
    assert any("value_area_pct" in m for m in _fatals(
        {"smc": {"enabled": True,
                 "volume_profile": {"value_area_pct": 1.5}}}))


def test_guard_rejects_too_few_volume_profile_bins():
    assert any("n_bins" in m for m in _fatals(
        {"smc": {"enabled": True, "volume_profile": {"n_bins": 2}}}))


def test_guard_rejects_too_short_lookback_windows():
    assert any("smc.pd_zone.lookback" in m for m in _fatals(
        {"smc": {"enabled": True, "pd_zone": {"lookback": 3}}}))


def test_guard_skips_all_checks_when_disabled():
    fatals = _fatals({"smc": {"enabled": False,
                              "mtf": {"ltf_fast_period": 999,
                                      "ltf_slow_period": 1}}})
    assert not any("smc." in m for m in fatals)
