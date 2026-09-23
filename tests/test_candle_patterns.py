"""
Regression for the candlestick-formation features (pat_engulf,
pat_hammer, pat_marubozu): mathematically-defined two-bar formations
fed to the meta-model as FEATURES under the SMC contract - never a
gate, never a veto. Pins the sign conventions (bull +, bear -), the
strength scaling/saturation, the neutral (0.0) on absent/short input -
the same neutral migrate_history pads old rows with - and the schema
placement so the 43->46 bump stays coherent.
"""
from ml.features import FEATURE_NAMES, _candle_patterns


def _bar(o, h, lo, c):
    return {"open": o, "high": h, "low": lo, "close": c}


def test_schema_has_patterns_before_direction():
    # deliberate re-pin: v9 adds the ofi_dir/basis_mom_dir shadow pair
    # (62->64), widening the tail by two; v10 adds the dp_* dark-pool
    # block (64->68), widening it by four more
    assert len(FEATURE_NAMES) == 68
    # v7 trio + v8 flow_tox + v9 shadow pair + v10 dark-pool block slot
    # between the pattern block and the tail
    assert FEATURE_NAMES[-15:] == ["pat_engulf_dir", "pat_hammer_dir",
                                   "pat_marubozu_dir", "vol_term",
                                   "mkt_ret_6_dir", "book_touch_share",
                                   "flow_tox", "ofi_dir", "basis_mom_dir",
                                   "dp_surge_z", "dp_vol_z", "dp_hhi",
                                   "avail_dp",
                                   "direction", "gate_confidence"]


def test_bullish_engulfing_positive_and_scaled():
    e, _, m = _candle_patterns([_bar(10, 10.1, 9.4, 9.5),
                                _bar(9.4, 10.3, 9.3, 10.2)])
    assert 0.75 < e < 0.85            # body ratio 1.6 -> 0.8
    assert m > 0                      # engulfing bar is also directional


def test_bearish_engulfing_negative_and_saturates():
    e, _, _ = _candle_patterns([_bar(10, 10.6, 9.9, 10.5),
                                _bar(10.6, 10.7, 8.0, 8.1)])
    assert e == -1.0                  # >=2x prior body saturates


def test_same_colour_bodies_never_engulf():
    e, _, _ = _candle_patterns([_bar(9, 10.1, 8.9, 10),
                                _bar(8.5, 10.5, 8.4, 10.4)])
    assert e == 0.0


def test_hammer_positive_shooting_star_negative():
    _, h_hammer, _ = _candle_patterns([_bar(10, 10, 10, 10),
                                       _bar(10, 10.05, 9.5, 10.02)])
    _, h_star, _ = _candle_patterns([_bar(10, 10, 10, 10),
                                     _bar(10, 10.5, 9.98, 10.02)])
    assert h_hammer > 0.7
    assert h_star < -0.7


def test_full_body_bar_rejects_nothing():
    _, h, m = _candle_patterns([_bar(10, 10, 10, 10),
                                _bar(10, 11, 10, 11)])
    assert h == 0.0                   # small_body factor kills the wick term
    assert m == 1.0                   # perfect bullish marubozu


def test_doji_scores_zero_conviction():
    _, _, m = _candle_patterns([_bar(10, 10, 10, 10),
                                _bar(10, 10.5, 9.5, 10)])
    assert m == 0.0


def test_neutral_on_short_or_malformed_input():
    assert _candle_patterns([]) == (0.0, 0.0, 0.0)
    assert _candle_patterns([_bar(10, 11, 9, 10.5)]) == (0.0, 0.0, 0.0)
    assert _candle_patterns([{"open": 10}, {"bad": True}]) == (0.0, 0.0, 0.0)
