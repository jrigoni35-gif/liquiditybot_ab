"""
Cold-start bootstrap regression (information-flow audit, 2026-07-15).

bootstrap_dataset builds an EMA-cross pseudo-labeled dataset from OKX 5m
candle history when there is no live history yet (scripts/train_meta.py
--bootstrap, and the auto-retrain cold path). Two defects made it both
crash and, if patched naively, mis-sign every short row:

1. CRASH: it wrote features under the pre-v2 names ret_1/ret_6/ret_12/
   ret_48/mom_score. Those names were renamed to *_dir in schema v6 and no
   longer exist in FEATURE_NAMES, so setf()'s name_idx[name] KeyError'd on
   the FIRST EMA cross - the entire bootstrap aborted.
2. SIGN SKEW: *_dir features are SIDE-RELATIVE (value * side). The bootstrap
   wrote the RAW return/momentum, so every short-side pseudo-signal encoded
   its drift with the opposite sign from how live rows encode the same
   quantity - the model would learn contradictory directions from the two
   data sources.
"""
import numpy as np

from ml.features import FEATURE_NAMES
from ml.history import bootstrap_dataset


def _candles(closes):
    # minimal OHLCV dicts; highs/lows straddle close so barriers can fire
    return [{"time": 1000 + 300 * i, "close": c,
             "high": c * 1.01, "low": c * 0.99, "volume": 100.0 + i}
            for i, c in enumerate(closes)]


def _wave(n=600):
    # several full up/down swings so BOTH long (up-cross) and short
    # (down-cross) pseudo-signals are generated
    t = np.arange(n)
    return list(100.0 * (1.0 + 0.15 * np.sin(t / 11.0)))


def test_bootstrap_does_not_crash_and_matches_the_current_schema():
    X, y = bootstrap_dataset(_candles(_wave()))
    assert X.shape[1] == len(FEATURE_NAMES), "one column per current feature"
    assert len(X) == len(y) and len(X) > 0, "crosses produced labeled rows"
    assert np.isfinite(X).all() and set(np.unique(y)) <= {0.0, 1.0}


def test_bootstrap_features_are_side_relative_like_live_rows():
    """A crash-free run is not enough: the *_dir columns must carry the
    SIDE-RELATIVE sign. Drive a clean up-cross (long) on a rising ramp so
    'ret_*_dir' should read positive (drift WITH the long); a clean
    down-cross (short) on a falling ramp should ALSO read positive (falling
    price is with the short)."""
    idx = {n: k for k, n in enumerate(FEATURE_NAMES)}
    # bootstrap needs >=300 candles; long flat->rising and rising->falling
    # ramps put an up-cross (long) and a down-cross (short) in the window

    def ramp(start, step, n):
        return list(start + step * np.arange(n))

    # rising -> both crosses present; check the LONG rows (up-cross, +drift)
    up = ([100.0] * 120 + ramp(100.0, 0.4, 240))
    Xl, _ = bootstrap_dataset(_candles(up))
    longs = Xl[Xl[:, idx["direction"]] > 0] if len(Xl) else Xl
    assert len(longs) > 0, "a sustained rise must yield >=1 long pseudo-signal"
    assert (longs[:, idx["ret_6_dir"]] >= 0).mean() > 0.6, \
        "long-side ret_6_dir should mostly read WITH the up move"

    # rise then sustained fall -> the SHORT rows (down-cross, price falling)
    dn = ([100.0] * 60 + ramp(100.0, 0.4, 150) + ramp(160.0, -0.4, 150))
    Xs, _ = bootstrap_dataset(_candles(dn))
    assert len(Xs) > 0
    shorts = Xs[Xs[:, idx["direction"]] < 0]
    assert len(shorts) > 0, "a sustained fall must yield >=1 short pseudo-signal"
    assert (shorts[:, idx["ret_6_dir"]] >= 0).mean() > 0.6, \
        "short-side ret_6_dir must be side-flipped: falling price reads +"
    assert set(np.unique(Xs[:, idx["direction"]])) <= {-1.0, 1.0}
