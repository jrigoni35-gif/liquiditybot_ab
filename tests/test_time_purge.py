"""
Time-based walk-forward purge (information-flow audit, 2026-07-15).

The purge protects OOF from lookahead: a training row whose label window
overlaps the test block leaks the future. purged_walk_forward dropped a
fixed COUNT of rows (label_span), but label_span is in BARS and rows arrive
in BURSTS - a dense burst of signals right before a fold boundary spans far
less TIME than label_span bars, so its still-resolving labels leaked into
the test (row-count under-purge). The fix purges by signal TIME: drop every
train row with sig[i] + label_span*BAR_SECONDS > sig[test_start].
"""
import numpy as np

from ml.history import HistoryStore
from ml.walkforward import BAR_SECONDS, purged_walk_forward


def test_row_count_purge_is_unchanged_when_no_sig():
    # sig=None must reproduce the exact legacy row-count folds
    folds = list(purged_walk_forward(600, n_splits=4, label_span=50))
    assert folds, "legacy row-count folds still yielded"
    for tr, te in folds:
        assert tr[-1] < te[0]                       # expanding, train precedes
        assert te[0] - tr[-1] - 1 >= 50 - 1         # ~label_span row gap


def test_row_count_leaks_where_time_purge_does_not():
    """Signals arrive every 30s but the label horizon is 96 bars * 300s =
    28800s (960 rows). Row-count drops only 96 ROWS (2880s), leaving ~26000s
    of still-resolving labels leaking into the test - the exact SD/OF-6 bug.
    Time-purge drops the full time horizon, so no kept train row's label can
    reach the test."""
    n = 4000
    label_span = 96
    horizon = label_span * BAR_SECONDS
    sig = 1_000_000.0 + np.arange(n) * 30.0         # 30s apart (sub-bar dense)

    row = list(purged_walk_forward(n, n_splits=4, label_span=label_span))
    tim = list(purged_walk_forward(n, n_splits=4, label_span=label_span,
                                   sig=sig))

    # row-count LEAKS: a kept train row's label reaches past its test start
    assert any(len(tr) and sig[tr[-1]] + horizon > sig[te[0]]
               for tr, te in row), \
        "row-count purge should leak on sub-bar-spaced signals (the bug)"

    # time-purge NEVER leaks: every kept train row fully resolves before test
    assert tim, "time-purge still yields viable folds"
    for tr, te in tim:
        assert not len(tr) or sig[tr[-1]] + horizon <= sig[te[0]] + 1e-6, \
            "time-purge left a row whose label overlaps the test"


def test_load_training_data_returns_aligned_sorted_sig(tmp_path):
    from ml.features import FEATURE_NAMES
    store = HistoryStore(str(tmp_path / "h.csv"))
    fa = np.zeros(len(FEATURE_NAMES))
    fb = fa + 1.0
    fc = fa + 2.0
    # write OUT of signal-time order; load must sort X,y,w AND sig together
    store._append_row("p2", "BTC", "long", fb, 1, 1.0, "live", signal_ts=2000.0)
    store._append_row("p1", "BTC", "long", fa, 0, 1.0, "live", signal_ts=1000.0)
    store._append_row("p3", "ETH", "short", fc, 1, 1.0, "live", signal_ts=3000.0)
    X, y, w, sig = store.load_training_data(return_sig=True)
    assert list(sig) == [1000.0, 2000.0, 3000.0], "sig sorted ascending"
    assert np.allclose(X[0], fa) and np.allclose(X[2], fc), "X follows sig"
    assert list(y) == [0.0, 1.0, 1.0]               # labels track their rows
    # legacy 3-tuple call still works unchanged
    assert len(store.load_training_data()) == 3


def test_return_sig_on_missing_file_still_unpacks_to_four(tmp_path):
    """A fresh checkout has no signal_history.csv (outputs/ is gitignored).
    load_training_data(return_sig=True) must still return a 4-tuple there,
    or `python scripts/overfit_check.py` (a DoD gate) crashes on the unpack
    before it can fall back to the synthetic benchmark."""
    store = HistoryStore(str(tmp_path / "does_not_exist.csv"))
    X, y, w, sig = store.load_training_data(return_sig=True)   # must not raise
    assert len(X) == len(y) == len(w) == len(sig) == 0
    # legacy 3-tuple path on a missing file is unchanged
    assert len(store.load_training_data()) == 3
