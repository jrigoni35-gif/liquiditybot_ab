"""
ml/calibration.py

Probability calibration. Kelly sizing consumes probabilities literally:
p=0.60 must actually win ~60% of the time or every position is sized
wrong in the same direction. AUC measures ranking, not truth - a model
can rank perfectly and still be systematically overconfident.

IsotonicCalibrator: pool-adjacent-violators (PAV) fit on OUT-OF-FOLD
predictions from the walk-forward (never on in-sample predictions -
that just learns the training optimism). Serializes into the model JSON
so live inference applies the exact mapping training measured.

brier_score: mean squared error of probabilities - the metric the
online monitor tracks, because unlike AUC it punishes miscalibration.
"""

import numpy as np

EPS = 1e-9


def brier_score(y_true, y_prob) -> float:
    y = np.asarray(y_true, float)
    p = np.asarray(y_prob, float)
    if len(y) == 0:
        return 0.25
    return float(np.mean((p - y) ** 2))


def calibration_gap(y_true, y_prob, n_bins: int = 5) -> float:
    """Expected calibration error: |predicted p - realized rate| averaged
    over probability bins, weighted by bin count."""
    y = np.asarray(y_true, float)
    p = np.asarray(y_prob, float)
    if len(y) < n_bins:
        return 0.0
    edges = np.quantile(p, np.linspace(0, 1, n_bins + 1))
    gap, total = 0.0, 0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (p >= lo) & (p <= hi if i == n_bins - 1 else p < hi)
        n = int(mask.sum())
        if n == 0:
            continue
        gap += n * abs(float(p[mask].mean()) - float(y[mask].mean()))
        total += n
    return gap / max(total, 1)


class IsotonicCalibrator:
    """PAV isotonic regression mapping raw p -> calibrated p."""

    def __init__(self):
        self.x = None    # raw prob knots (ascending)
        self.y = None    # calibrated values (non-decreasing)

    def fit(self, p_raw, y_true):
        p = np.asarray(p_raw, float)
        y = np.asarray(y_true, float)
        if len(p) < 20:
            return self          # too little data: identity
        order = np.argsort(p, kind="mergesort")
        px, yy = p[order], y[order]
        # PAV: pools of (value_sum, weight)
        vals, wts, xs = [], [], []
        for xi, yi in zip(px, yy):
            vals.append(yi)
            wts.append(1.0)
            xs.append(xi)
            while len(vals) > 1 and vals[-2] / wts[-2] > vals[-1] / wts[-1]:
                v = vals.pop()
                w = wts.pop()
                x = xs.pop()
                vals[-1] += v
                wts[-1] += w
                xs[-1] = x   # right edge of pool
        # merge duplicate x knots: tree/blend models emit clustered raw
        # probabilities, so adjacent pools can share a right edge —
        # np.interp needs increasing xp, so keep the LAST (largest) y
        # per distinct x
        ys = list(np.clip(np.array(vals, float) / np.array(wts, float),
                          0.02, 0.98))
        mx, my = [], []
        for xv, yv in zip(xs, ys):
            if mx and xv == mx[-1]:
                my[-1] = yv
            else:
                mx.append(xv)
                my.append(yv)
        self.x = np.array(mx, float)
        self.y = np.array(my, float)
        return self

    @property
    def fitted(self) -> bool:
        return self.x is not None and len(self.x) >= 2

    def transform(self, p):
        if not self.fitted:
            return np.asarray(p, float)
        assert self.x is not None and self.y is not None  # fitted implies both set
        p = np.asarray(p, float)
        return np.interp(p, self.x, self.y)

    def to_dict(self):
        if not self.fitted:
            return None
        assert self.x is not None and self.y is not None  # fitted implies both set
        return {"x": self.x.tolist(), "y": self.y.tolist()}

    @classmethod
    def from_dict(cls, d):
        c = cls()
        if d:
            c.x = np.array(d["x"], float)
            c.y = np.array(d["y"], float)
        return c


def feature_deciles(X) -> list:
    """Per-feature decile edges of the training distribution - stored in
    the model artifact so live input drift is measurable later."""
    X = np.asarray(X, float)
    qs = np.linspace(0, 1, 11)
    return [np.quantile(X[:, j], qs).tolist() for j in range(X.shape[1])]


def psi(train_edges: list, recent_col) -> float:
    """Population Stability Index of one feature vs its training deciles.
    Rule of thumb: <0.10 stable, 0.10-0.25 drifting, >0.25 major shift."""
    x = np.asarray(recent_col, float)
    if len(x) < 10:
        return 0.0
    # np.array (not asarray) so overwriting the outer edges below never mutates
    # a caller's stored decile array in place (silent drift-baseline corruption)
    edges = np.array(train_edges, float)
    # DEGENERATE deciles: a binary / one-hot / sparse feature collapses its
    # decile edges to repeated values (weekend -> [0,...,0,1,1]). np.histogram
    # on duplicate edges buckets almost all mass into one bin vs the flat 0.1
    # expectation and reports an ENORMOUS PSI even for an IDENTICAL live
    # distribution — this pinned drift_share permanently >= 0.30 across the ~18
    # binary/flag features (one-hot regimes, th_*, pat_*, SMC flags), firing
    # spurious retrains and burying real drift on continuous features. Deciles-
    # PSI is only meaningful when the edges are strictly increasing; for a
    # degenerate (tied) feature report 0 (no false drift) rather than a
    # fabricated shift.
    if np.unique(edges).size < edges.size:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    expected = np.full(10, 0.1)
    counts, _ = np.histogram(x, bins=edges)
    actual = counts / max(counts.sum(), 1)
    e = 1e-4
    return float(np.sum((actual - expected) *
                        np.log((actual + e) / (expected + e))))
