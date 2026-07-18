"""ml/interpret.py — post-hoc interpretability, exact where exactness exists.

Contract under test:
  - GBT attribution is EXACT interventional Shapley: additivity to the
    raw margin at machine precision, null features get exactly zero,
    and the enumeration matches a brute-force Shapley on a tiny tree;
  - logistic attribution is the exact linear decomposition of the logit;
  - the Rudin rule: unexplainable model kinds get a refusal, never a
    plausible guess; blend explains both members;
  - correlation clustering merges duplicated features; grouped
    permutation importance credits an informative cluster and can call
    everything useless (the verdict MDI cannot reach);
  - attribution fingerprints and rotation behave (identical windows ->
    cos 1, orthogonal profiles -> 0);
  - config_guard rejects report-lying knob values.
"""
import numpy as np

from core.config_guard import validate
from ml.interpret import (attribution_profile, background_sample, brier,
                          cluster_features, explain, gbt_margin, gbt_shap,
                          grouped_permutation_importance, logistic_attrib,
                          profile_rotation)
from ml.models import BlendModel, GradientBoostedStumps, LogisticModel, NumpyMLP


def _fit_gbt(n=400, d=6, seed=3, **kw):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d))
    logit = 1.6 * X[:, 0] - 1.1 * X[:, 1] + 0.4 * X[:, 0] * X[:, 1]
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(float)
    kw.setdefault("n_estimators", 60)
    m = GradientBoostedStumps(seed=seed, **kw).fit(X, y)
    return m, X, y


# ---------------------------------------------------------------------
# exactness
# ---------------------------------------------------------------------
def test_gbt_shap_additivity_machine_precision():
    m, X, _ = _fit_gbt()
    bg = X[:64]
    for row in X[100:110]:
        contrib, base = gbt_shap(m, row, bg)
        assert abs(base + contrib.sum() - gbt_margin(m, row)) < 1e-9


def test_gbt_shap_null_feature_gets_zero():
    m, X, _ = _fit_gbt()
    used = set()
    from ml.interpret import _tree_feats
    for t in m.trees:
        _tree_feats(t, used)
    unused = set(range(X.shape[1])) - used
    if not unused:                      # ensure at least one dead column
        m2, X2, _ = _fit_gbt(d=8, seed=5)
        contrib, _ = gbt_shap(m2, X2[0], X2[:64])
        dead = set(range(8)) - {f for t in m2.trees
                                for f in _tree_feats(t, set())}
        for j in dead:
            assert contrib[j] == 0.0
        return
    contrib, _ = gbt_shap(m, X[0], X[:64])
    for j in unused:
        assert contrib[j] == 0.0


def test_gbt_shap_matches_brute_force_on_single_tree():
    """One depth-2 tree, 2 features: enumeration must equal the Shapley
    formula computed by hand over the 4 subsets."""
    tree = {"f": 0, "t": 0.0,
            "L": {"f": 1, "t": 0.0, "L": {"v": -2.0}, "R": {"v": 1.0}},
            "R": {"v": 3.0}}
    m = GradientBoostedStumps()
    m.trees = [tree]
    m.base = 0.0
    m.lr = 1.0
    m.n_features_ = 2
    rng = np.random.default_rng(0)
    Z = rng.normal(size=(200, 2))
    x = np.array([-1.0, 1.0])           # lands in the L/R = 1.0 leaf

    def walk(xv, zv, S):
        p = xv if 0 in S else zv
        if p[0] > 0.0:
            return 3.0
        q = xv if 1 in S else zv
        return 1.0 if q[1] > 0.0 else -2.0

    def v(S):
        return float(np.mean([walk(x, z, S) for z in Z]))

    phi0 = 0.5 * (v({0}) - v(set())) + 0.5 * (v({0, 1}) - v({1}))
    phi1 = 0.5 * (v({1}) - v(set())) + 0.5 * (v({0, 1}) - v({0}))
    contrib, base = gbt_shap(m, x, Z)
    assert abs(contrib[0] - phi0) < 1e-12
    assert abs(contrib[1] - phi1) < 1e-12
    assert abs(base - v(set())) < 1e-12


def test_logistic_attrib_exact_logit_decomposition():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(300, 4))
    y = (X[:, 2] > 0).astype(float)
    m = LogisticModel().fit(X, y)
    x = X[7]
    contrib, base = logistic_attrib(m, x)
    z = float(np.log(m.predict_proba(x)[0] / (1 - m.predict_proba(x)[0])))
    assert abs(base + contrib.sum() - z) < 1e-9
    assert np.argmax(np.abs(contrib)) == 2      # the only real driver


# ---------------------------------------------------------------------
# faithful-or-refuse dispatch
# ---------------------------------------------------------------------
def test_explain_refuses_mlp_and_explains_blend_members():
    mlp = NumpyMLP(hidden=(4,), epochs=2)
    e = explain(mlp, np.zeros(3))
    assert e["exact"] is False and "refus" in e["refusal"]
    rng = np.random.default_rng(2)
    X = rng.normal(size=(300, 4))
    y = (X[:, 0] > 0).astype(float)
    bl = BlendModel().fit(X, y)
    eb = explain(bl, X[0], background=X[:32])
    assert eb["exact"] and eb["members"]["a"]["kind"] == "logistic"
    assert eb["members"]["b"]["kind"] == "gbt"
    assert eb["members"]["b"]["exact"]


def test_explain_gbt_without_background_refuses():
    m, X, _ = _fit_gbt()
    e = explain(m, X[0], background=None)
    assert e["exact"] is False and "background" in e["refusal"]


# ---------------------------------------------------------------------
# clustered permutation importance
# ---------------------------------------------------------------------
def test_cluster_features_merges_duplicates():
    rng = np.random.default_rng(4)
    a = rng.normal(size=500)
    b = rng.normal(size=500)
    X = np.column_stack([a, a + rng.normal(0, 0.05, 500), b])
    groups = cluster_features(X, thr=0.7)
    assert [0, 1] in groups and [2] in groups


def test_grouped_permutation_credits_the_informative_cluster():
    rng = np.random.default_rng(6)
    n = 600
    a = rng.normal(size=n)
    X = np.column_stack([a, a + rng.normal(0, 0.05, n),
                         rng.normal(size=n)])
    y = (a > 0).astype(float)

    def predict(A):                      # a model that split credit: uses
        s = 0.5 * A[:, 0] + 0.5 * A[:, 1]   # BOTH duplicated columns
        return 1 / (1 + np.exp(-3 * s))

    imp = grouped_permutation_importance(predict, X, y,
                                         cluster_features(X, 0.7))
    top = imp[0]
    assert top["features"] == [0, 1]     # cluster shuffled as a block wins
    assert top["delta_brier_mean"] > 0.05
    noise = next(r for r in imp if r["features"] == [2])
    assert abs(noise["delta_brier_mean"]) < 0.01


def test_grouped_permutation_can_call_everything_useless():
    rng = np.random.default_rng(8)
    X = rng.normal(size=(400, 3))
    y = rng.integers(0, 2, 400).astype(float)

    def predict(A):
        return np.full(len(A), 0.5)      # constant model: nothing matters

    imp = grouped_permutation_importance(predict, X, y)
    assert all(abs(r["delta_brier_mean"]) < 1e-12 for r in imp)


# ---------------------------------------------------------------------
# fingerprints
# ---------------------------------------------------------------------
def test_attribution_profile_and_rotation():
    m, X, _ = _fit_gbt()
    bg = X[:64]
    p1 = attribution_profile(m, X[100:140], bg)
    assert abs(p1.sum() - 1.0) < 1e-9
    assert profile_rotation(p1, p1) > 0.9999
    ortho = np.zeros_like(p1)
    ortho[int(np.argmin(p1))] = 1.0
    assert profile_rotation(np.eye(len(p1))[0], np.eye(len(p1))[1]) == 0.0
    mlp = NumpyMLP(hidden=(4,), epochs=2)
    assert attribution_profile(mlp, X[:5]).sum() == 0.0   # refusal -> zeros


def test_background_sample_spans_history():
    X = np.arange(1000, dtype=float).reshape(500, 2)
    bg = np.asarray(background_sample(X, 10))
    assert bg.shape == (10, 2)
    assert bg[0, 0] == 0.0 and bg[-1, 0] == 998.0        # first AND last era


def test_brier_helper():
    assert brier(np.array([1.0, 0.0]), np.array([1.0, 0.0])) == 0.0
    assert abs(brier(np.array([1.0]), np.array([0.5])) - 0.25) < 1e-12


# ---------------------------------------------------------------------
# config_guard
# ---------------------------------------------------------------------
def test_guard_rejects_report_lying_knobs():
    def fatals(cfg):
        return [m for s, m in validate(cfg) if s == "FATAL"]
    assert any("background_rows" in m for m in fatals(
        {"ml": {"interpret": {"background_rows": 4}}}))
    assert any("corr_cluster_thr" in m for m in fatals(
        {"ml": {"interpret": {"corr_cluster_thr": 0.1}}}))
    assert any("eval_frac" in m for m in fatals(
        {"ml": {"interpret": {"eval_frac": 0.9}}}))
    assert any("n_repeats" in m for m in fatals(
        {"ml": {"interpret": {"n_repeats": 1}}}))
    assert not any("interpret" in m for m in fatals(
        {"ml": {"interpret": {}}}))      # defaults are coherent


# ---------------------------------------------------------------------
# report core (pure build path, no filesystem)
# ---------------------------------------------------------------------
def test_build_report_end_to_end_on_synthetic_champion():
    from scripts.interpret_report import build_report
    m, X, y = _fit_gbt(n=500)
    md, rep = build_report(m, None, X, y, {}, background=X[:64])
    assert rep["kind"] == "gbt"
    assert rep["additivity_ok"] is True
    assert "Clustered permutation importance" in md
    assert "Attribution fingerprint" in md
    assert 0.0 <= rep["attribution_drift_cos"] <= 1.0
    top = rep["importance"][0]
    assert 0 in top["features"] or 1 in top["features"]  # real drivers win
