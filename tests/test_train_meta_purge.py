"""tests/test_train_meta_purge.py — the DEPLOYED selector must purge folds by
TIME, not row count.

purged_walk_forward supports a leak-free time-based purge (drop every training
row whose triple-barrier label window reaches into the test block), and
overfit_check already measures that process — but scripts/train_meta.py, the
script that actually selects and deploys the champion, called
evaluate_and_select WITHOUT the signal-time array, so it fell back to the
row-count purge. Signals arrive in bursts, so a fixed row count spans a variable
amount of time; a dense pre-boundary burst leaks future labels the row-count
purge silently keeps (OF-6). These pin the mechanism the fix now engages.
"""
import numpy as np

from ml.walkforward import BAR_SECONDS, evaluate_and_select, purged_walk_forward


def _bursty_sig(n=240, boundary=120, label_span=4, burst=8):
    """Signal times: many sparse early rows that resolve well before the fold
    boundary, then a dense BURST of `burst` rows (> label_span) packed into the
    horizon just before the boundary, then the test block. The burst rows'
    label windows overlap the test block, so a correct purge must drop them."""
    horizon = label_span * BAR_SECONDS
    sig = np.zeros(n)
    # sparse early rows, spaced 2*horizon apart -> each resolves before the next
    for i in range(boundary - burst):
        sig[i] = i * 2 * horizon
    t_test = (boundary - burst) * 2 * horizon + horizon      # test boundary time
    # burst: packed into (t_test - horizon, t_test) -> labels reach the test
    for j in range(burst):
        sig[boundary - burst + j] = t_test - horizon * 0.5 + j
    # test block + beyond, marching one horizon per row
    for i in range(boundary, n):
        sig[i] = t_test + (i - boundary) * horizon
    return sig, horizon


def test_time_purge_drops_bursty_leak_that_rowcount_keeps():
    n, boundary, label_span, burst = 240, 120, 4, 8
    sig, horizon = _bursty_sig(n, boundary, label_span, burst)

    def _fold_at(boundary, **kw):
        for tr, te in purged_walk_forward(n, n_splits=5, label_span=label_span,
                                          **kw):
            if te[0] == boundary:
                return tr, te
        return None, None

    tr_rowcount, te = _fold_at(boundary)                 # sig=None -> row count
    tr_time, _ = _fold_at(boundary, sig=sig)             # time-based purge
    assert te is not None and te[0] == boundary
    cutoff = sig[boundary] - horizon                     # label must resolve <= this

    # row-count purge KEEPS burst rows whose labels reach into the test (leak)
    assert tr_rowcount.size and sig[tr_rowcount].max() > cutoff, \
        "row-count purge should leak a bursty pre-boundary row (that's the bug)"
    # time-based purge keeps NONE whose label window overlaps the test block
    assert tr_time.size == 0 or sig[tr_time].max() <= cutoff, \
        "time-based purge must drop every row whose label reaches the test block"


def test_evaluate_and_select_runs_with_signal_times():
    # end-to-end plumbing: the selector accepts sig and returns OOF arrays fit
    # under the time-based purge (the path train_meta now takes on live data).
    rng = np.random.default_rng(5)
    n = 240
    X = rng.normal(size=(n, 4))
    y = (X[:, 0] + 0.4 * rng.normal(size=n) > 0).astype(float)
    sig = np.sort(rng.uniform(0, n * BAR_SECONDS, size=n))
    res = evaluate_and_select(X, y, label_span=4, n_splits=4, sig=sig)
    assert res["model"] is not None
    assert res["selected"] in ("logistic", "gbt", "blend", "mlp")
    assert res[res["selected"]]["oof_p"].size > 0
