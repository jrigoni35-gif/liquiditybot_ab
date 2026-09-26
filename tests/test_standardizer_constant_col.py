"""A feature that was CONSTANT in training must not saturate the model when
it first moves live. Measured 2026-09-26 on the live v10 champion: sent_fear,
dp_surge_z and dp_vol_z had training sd == EPS (1e-9) with non-zero logistic
weights, so dp_vol_z=0.5 drove the logistic member to p=9.4e-14 and
sent_fear=1 drove it to p=1.0. dp_*_z are structurally first non-zero LIVE,
before any training row carries a non-zero value."""
import numpy as np

from ml.models import LogisticModel


def _fit_with_constant_col(seed=3):
    rng = np.random.default_rng(seed)
    n = 400
    X = rng.normal(0, 1, (n, 4))
    X[:, 2] = 0.0                       # constant in training
    y = (X[:, 0] + 0.3 * rng.normal(0, 1, n) > 0).astype(float)
    m = LogisticModel(epochs=200).fit(X, y)
    # the init-noise weight a real fit leaves on a zero-gradient column
    m.w[2] = -0.0116
    return m, X


def test_constant_training_column_does_not_saturate_live():
    m, X = _fit_with_constant_col()
    base = m.predict_proba(X[:20])
    moved = X[:20].copy()
    moved[:, 2] = 0.5
    p = m.predict_proba(moved)
    assert np.all((p > 1e-6) & (p < 1 - 1e-6))
    np.testing.assert_array_equal(p, base)


def test_constant_column_rule_survives_save_load_and_leaves_others():
    m, X = _fit_with_constant_col()
    m2 = LogisticModel.from_dict(m.to_dict())
    moved = X[:20].copy()
    moved[:, 2] = -3.0
    np.testing.assert_array_equal(m2.predict_proba(moved),
                                  m.predict_proba(X[:20]))
    # a column WITH training spread is still read normally
    moved2 = X[:20].copy()
    moved2[:, 0] += 1.0
    assert np.max(np.abs(m2.predict_proba(moved2)
                         - m2.predict_proba(X[:20]))) > 1e-3
