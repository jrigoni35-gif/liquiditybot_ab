"""tests/test_model_width_probe.py — the schema guard's functional-probe
fallback closes the bare-unstamped-model width hole.

The width check (`if width is not None`) silently skipped a model whose
n_features is None; with no feature_schema_version stamp either, a wrong-width
legacy artifact was adopted and then faulted on every inference. But the current
champion is a CORRECT bare gbt (n_features None, no stamp), so the guard can't
just fail-closed on unknown width. The fallback probes the model with a
contract-width vector: a wider/mismatched artifact raises and is rejected; the
correct bare model returns a value and is accepted.
"""
import numpy as np

from ml.contracts import SCHEMA_VERSION, get_contract
from ml.meta_model import MetaModelService


def _guard():
    m = MetaModelService.__new__(MetaModelService)          # no reload side effects
    m.contract = get_contract()
    return m


class _Model:
    def __init__(self, n_features, proba=None, raises=None):
        self.n_features = n_features
        self._proba = proba
        self._raises = raises

    def predict_proba(self, X):
        if self._raises is not None:
            raise self._raises
        return np.full(len(X), self._proba if self._proba is not None else 0.5)


def test_correct_bare_model_is_accepted():
    # the current-champion case: no stamp, n_features None, but the right width
    g = _guard()
    model = _Model(n_features=None, proba=0.5)
    assert g._schema_mismatch(model, {}) == ""


def test_wrong_width_bare_model_is_rejected_by_probe():
    # a wider/mismatched legacy artifact raises on a contract-width vector
    g = _guard()
    model = _Model(n_features=None, raises=IndexError("index 57 out of bounds"))
    reason = g._schema_mismatch(model, {})
    assert reason and "probe" in reason


def test_known_wrong_width_still_rejected_by_check_2():
    g = _guard()
    bad = _Model(n_features=get_contract().n - 5, proba=0.5)
    assert "width" in g._schema_mismatch(bad, {})


def test_matching_stamp_is_trusted_without_probe():
    # stamp present + current -> accepted; the probe must NOT run (would crash)
    g = _guard()
    model = _Model(n_features=None, raises=RuntimeError("probe must not run"))
    assert g._schema_mismatch(model, {"feature_schema_version": SCHEMA_VERSION}) == ""


def test_stale_stamp_rejected():
    g = _guard()
    model = _Model(n_features=None, proba=0.5)
    reason = g._schema_mismatch(
        model, {"feature_schema_version": int(SCHEMA_VERSION) + 1})
    assert "feature-schema" in reason


def test_real_legacy_bare_gbt_champion_is_not_false_rejected():
    # the exact PC-champion scenario: a real gbt of the CURRENT width but with
    # no stamp and n_features stripped (as legacy artifacts were saved). The
    # probe must accept it — a false rejection would drop the live bot to the
    # cold-start prior for no reason.
    from ml.models import GradientBoostedStumps
    g = _guard()
    n = get_contract().n
    rng = np.random.default_rng(2)
    X = rng.normal(size=(200, n))
    gbt = GradientBoostedStumps(seed=1).fit(X, (X[:, 0] > 0).astype(float))
    gbt.n_features_ = None                     # simulate the pre-stamp artifact
    assert getattr(gbt, "n_features", "x") is None
    assert g._schema_mismatch(gbt, {}) == ""   # accepted via the functional probe
