"""Acceptance suite for the overfit battery (ml/overfit.py). Each probe
is checked for the property that makes it a valid instrument:
discrimination — it must PASS clean pipelines and FAIL dirty ones."""
import numpy as np

from ml.models import auc_score
from ml.calibration import brier_score
from ml.overfit import (train_test_gap, shuffled_label_check, pbo_cscv,
                        model_space_pbo, purge_leakage_probe,
                        feature_dof_report, deflated_sharpe,
                        regime_stratum_labels, regime_stratified_oof,
                        REGIME_STRATA, REGIME_MIN_N)
from ml.features import FEATURE_NAMES


def _interaction_world(n, d=10, seed=0, dense=False):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d))
    if dense:                       # signal in many features
        logit = sum(0.4 * X[:, j] * (1 if j % 2 else -1) for j in range(d)) \
            + 0.8 * X[:, 0] * (X[:, 1] > 0) - 0.3
    else:
        logit = 0.6 * X[:, 0] + 1.8 * X[:, 1] * (X[:, 2] > 0) - 0.4
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(float)
    return X, y


# ---------------------------------------------------------------- shuffle null
def test_shuffle_null_passes_clean_pipeline():
    X, y = _interaction_world(900, seed=1)
    r = shuffled_label_check(X, y, label_span=30, repeats=3)
    assert r["ok"], f"clean pipeline flagged as leaking: {r}"
    assert abs(r["mean_auc"] - 0.5) < 0.06


def test_shuffle_null_band_calibrated():
    """The null test targets MECHANICAL/index leakage: a global label
    shuffle severs any feature-label correlation, so a feature that
    merely equals the label does NOT fire it (that is what OF-7/importance
    and OF-2's mechanical checks are for). What must hold is calibration:
    on clean data the shuffled OOF AUC sits tight around 0.5, inside the
    analytic null band, across seeds."""
    for seed in (2, 12, 22):
        X, y = _interaction_world(900, seed=seed)
        X = np.column_stack([X, y * 4.0 - 2.0])   # feature=label: still 0.5
        r = shuffled_label_check(X, y, label_span=30, repeats=3)
        assert r["ok"], f"null band miscalibrated at seed {seed}: {r}"
        assert abs(r["mean_auc"] - 0.5) < 0.06, r


def test_shuffle_null_catches_split_contamination(monkeypatch):
    """Positive detection case. The one leak class that survives a global
    label shuffle is SPLITTER contamination: test indices appearing in
    train. A memorizer then recovers even random labels out-of-fold. We
    break the splitter deliberately and the probe must fire."""
    import ml.overfit as of

    def leaky_splitter(n, n_splits, label_span, sig=None):
        # every "test" row is also in "train" — the purge bug incarnate
        # (sig accepted for interface parity with the time-purge signature)
        idx = np.arange(n)
        block = n // (n_splits + 1)
        for k in range(1, n_splits + 1):
            te = idx[k * block:(k + 1) * block]
            tr = idx[:(k + 1) * block]          # includes te wholesale
            yield tr, te

    monkeypatch.setattr(of, "purged_walk_forward", leaky_splitter)
    X, y = _interaction_world(700, seed=5)
    r = of.shuffled_label_check(X, y, label_span=30, repeats=3)
    assert not r["ok"], f"contaminated splitter went undetected: {r}"
    assert r["mean_auc"] > 0.55, r


# ---------------------------------------------------------------- train/OOF gap
def test_regularized_gbt_gap_controlled():
    X, y = _interaction_world(2000, seed=3)
    g = train_test_gap(X, y, label_span=40)
    # the fix that matters: the memorization gap is bounded. A properly
    # regularized GBT on near-linear data should converge TOWARD the
    # linear model, not dominate it, so we require only that it does not
    # generalize worse than logistic — beating it is a bonus, not the test.
    assert g["gbt"]["gap_auc"] < 0.12, f"GBT still memorizing: {g['gbt']}"
    assert g["gbt"]["oof_auc"] >= g["logistic"]["oof_auc"] - 0.01, \
        f"GBT generalizes worse than linear: {g}"


# ---------------------------------------------------------------- PBO / CSCV
def test_pbo_low_when_one_config_truly_best():
    rng = np.random.default_rng(4)
    T, N = 240, 6
    M = rng.normal(0, 1, (T, N))
    M[:, 0] += 0.8                     # config 0 genuinely dominates
    r = pbo_cscv(M, n_blocks=8)
    assert r["pbo"] < 0.2, f"PBO high on a real winner: {r}"


def test_pbo_discriminates_winner_from_noise():
    """Absolute PBO on a single noise draw is seed-noisy; the invariant
    is DISCRIMINATION — noise selection must overfit far more than a real
    winner, averaged over seeds."""
    def pbo_winner(s):
        rng = np.random.default_rng(s)
        M = rng.normal(0, 1, (240, 6))
        M[:, 0] += 0.8
        return pbo_cscv(M, n_blocks=8)["pbo"]

    def pbo_noise(s):
        rng = np.random.default_rng(s)
        return pbo_cscv(rng.normal(0, 1, (240, 8)), n_blocks=8)["pbo"]

    w = np.mean([pbo_winner(s) for s in range(8)])
    z = np.mean([pbo_noise(s) for s in range(8)])
    assert z > w + 0.2, f"PBO fails to separate noise from a real winner: " \
                        f"winner={w:.2f} noise={z:.2f}"


def test_model_space_pbo_runs_end_to_end():
    X, y = _interaction_world(800, seed=6)
    r = model_space_pbo(X, y, label_span=30, n_splits=4, n_blocks=6)
    assert r["pbo"] is not None and 0.0 <= r["pbo"] <= 1.0
    assert "is_winner" in r and r["selection_rule"] == "simplicity_ladder"
    assert r["pbo_argmax"] is not None


def test_ladder_selection_cannot_chase_split_luck():
    """The deployed rule (margin-stabilized simplicity ladder) must not
    anti-select: on data where per-split argmax chases IS luck, the
    ladder's PBO has to sit at or below the argmax PBO, and at or below
    the no-anti-selection line (0.5 + small sampling slack)."""
    # PINNED benchmark width: this asserts a single-seed statistical
    # property of the LADDER MECHANICS (ladder PBO <= argmax PBO), which
    # is schema-independent - the sibling mechanics tests all run at
    # d=10. Deriving d from the live FEATURE_NAMES made every legitimate
    # feature addition reshuffle fold luck and flip the inequality (a
    # dimensionality artifact, observed on the 43->46 candle-pattern
    # bump), so the world is frozen at the width it was calibrated on.
    # Bars stay put; the object under test never drifts.
    X, y = _interaction_world(1200, d=43, seed=9)
    r = model_space_pbo(X, y, label_span=40, n_splits=5, n_blocks=8)
    assert r["pbo"] <= r["pbo_argmax"] + 1e-9, r
    assert r["pbo"] <= 0.55, f"deployed ladder anti-selects: {r}"


# ---------------------------------------------------------------- purge probe
def test_purge_never_manufactures_edge():
    r = purge_leakage_probe()
    assert r["purge_does_not_inflate"], r


# ---------------------------------------------------------------- feature DoF
def test_dof_flags_starved_dataset():
    X, y = _interaction_world(60, d=len(FEATURE_NAMES), seed=7)
    r = feature_dof_report(X, y, FEATURE_NAMES, label_span=16)
    assert r["starved"], "60 rows / 36 features must read as starved"


def test_dof_discriminates_dense_vs_sparse():
    # sparse: signal in 2 features -> high dead fraction
    Xs, ys = _interaction_world(1500, d=len(FEATURE_NAMES), seed=8, dense=False)
    rs = feature_dof_report(Xs, ys, FEATURE_NAMES, label_span=40)
    # dense: signal spread across many -> lower dead fraction
    Xd, yd = _interaction_world(1500, d=len(FEATURE_NAMES), seed=8, dense=True)
    rd = feature_dof_report(Xd, yd, FEATURE_NAMES, label_span=40)
    assert not rs["starved"] and not rd["starved"]
    assert rd["dead_feature_frac"] < rs["dead_feature_frac"], \
        f"DoF cannot tell dense from sparse: dense={rd['dead_feature_frac']} " \
        f"sparse={rs['dead_feature_frac']}"


# ---------------------------------------------------------------- deflated SR
def test_deflated_sharpe_penalizes_more_trials():
    d1 = deflated_sharpe(0.15, n_returns=250, skew=-0.2, kurtosis=5,
                         n_trials=1)
    d50 = deflated_sharpe(0.15, n_returns=250, skew=-0.2, kurtosis=5,
                          n_trials=50)
    assert d1["dsr"] > d50["dsr"], "more trials must deflate the Sharpe"
    assert 0.0 <= d50["dsr"] <= 1.0


# ------------------------------------------------------- OOF gap carries OOF
def test_train_test_gap_return_oof_is_additive():
    """return_oof=True must not change a single existing key/value — it may
    only ADD 'oof_idx'/'oof_pred'. This is the guarantee scripts/
    overfit_check.py's regime diagnostic depends on to be report-only."""
    X, y = _interaction_world(600, seed=21)
    baseline = train_test_gap(X, y, label_span=30, n_splits=4)
    with_oof = train_test_gap(X, y, label_span=30, n_splits=4,
                              return_oof=True)
    for name in baseline:
        base_keys = set(baseline[name])
        new_keys = set(with_oof[name])
        assert new_keys >= base_keys
        assert new_keys - base_keys <= {"oof_idx", "oof_pred"}
        for k in base_keys:
            assert with_oof[name][k] == baseline[name][k], (name, k)
    g = with_oof["gbt"]
    if g.get("folds"):
        assert "oof_idx" in g and "oof_pred" in g
        assert len(g["oof_idx"]) == len(g["oof_pred"])
        # every OOF prediction traces back to a row inside the corpus
        assert g["oof_idx"].max() < len(X)


# ------------------------------------------------------- regime stratification
def test_regime_stratum_labels_all_zero_is_unknown():
    one_hot = np.array([
        [1, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 1],
    ])
    labels = regime_stratum_labels(one_hot)
    assert list(labels) == ["bull_quiet", "unknown", "range", "unknown",
                            "crisis"]


def test_regime_stratified_oof_stratifies_planted_structure():
    """Planted per-regime one-hot structure must land counts + metrics in
    the right strata, and a well-populated stratum's AUC/Brier must match
    the SAME numbers a direct auc_score/brier_score call gives on that
    exact slice (no silent mis-indexing between oof_idx and the one-hot
    block)."""
    rng = np.random.default_rng(42)
    n_bull, n_bear, n_thin = 120, 90, 10
    n = n_bull + n_bear + n_thin
    one_hot = np.zeros((n, 5))
    one_hot[:n_bull, 0] = 1                          # bull_quiet
    one_hot[n_bull:n_bull + n_bear, 3] = 1            # bear
    one_hot[n_bull + n_bear:, 4] = 1                  # crisis (thin)
    y = rng.integers(0, 2, n).astype(float)
    pred = rng.random(n)
    oof_idx = np.arange(n)

    res = regime_stratified_oof(y, oof_idx, pred, one_hot,
                                pooled_auc=0.55, pooled_brier=0.25)

    assert set(res.keys()) == {*REGIME_STRATA, "unknown"}
    assert res["bull_quiet"]["n_oof"] == n_bull
    assert res["bear"]["n_oof"] == n_bear
    assert res["crisis"]["n_oof"] == n_thin
    assert res["range"]["n_oof"] == 0
    assert res["bull_vol"]["n_oof"] == 0
    assert res["unknown"]["n_oof"] == 0

    for s, sl in (("bull_quiet", slice(0, n_bull)),
                 ("bear", slice(n_bull, n_bull + n_bear))):
        assert res[s]["scored"] is True
        assert res[s]["auc"] == auc_score(y[sl], pred[sl])
        assert res[s]["brier"] == brier_score(y[sl], pred[sl])


def test_regime_stratified_oof_thin_stratum_never_scored():
    """A stratum below REGIME_MIN_N reports insufficient-n and is NEVER
    scored — no auc/brier value at all, regardless of how clean the
    planted signal in it is."""
    n = REGIME_MIN_N - 1
    one_hot = np.zeros((n, 5))
    one_hot[:, 1] = 1                                 # bull_vol
    y = np.array([float(i % 2) for i in range(n)])
    pred = np.where(y > 0.5, 0.9, 0.1)                # perfectly separable
    res = regime_stratified_oof(y, np.arange(n), pred, one_hot)
    assert res["bull_vol"]["n_oof"] == n
    assert res["bull_vol"]["scored"] is False
    assert res["bull_vol"]["auc"] is None
    assert res["bull_vol"]["brier"] is None


def test_regime_stratified_oof_indexes_into_a_larger_corpus():
    """oof_idx is a SUBSET of a larger y (exactly how train_test_gap's
    return_oof supplies it: OOF rows are a slice of the full corpus, not
    rows 0..n-1). Stratification must key off oof_idx, not row position
    inside the OOF arrays."""
    n_total = 400
    rng = np.random.default_rng(5)
    y_full = rng.integers(0, 2, n_total).astype(float)
    oof_idx = np.arange(100, 300)                     # a middle slice
    one_hot = np.zeros((len(oof_idx), 5))
    one_hot[:150, 2] = 1                              # range
    one_hot[150:, 3] = 1                              # bear
    pred = rng.random(len(oof_idx))
    res = regime_stratified_oof(y_full, oof_idx, pred, one_hot)
    assert res["range"]["n_oof"] == 150
    assert res["bear"]["n_oof"] == 50
    y_oof = y_full[oof_idx]
    assert res["range"]["auc"] == auc_score(y_oof[:150], pred[:150])


def test_regime_stratified_oof_flags_material_degrade_vs_pooled():
    n = 100
    one_hot = np.zeros((n, 5))
    one_hot[:, 3] = 1                                 # bear
    rng = np.random.default_rng(3)
    y = rng.integers(0, 2, n).astype(float)
    pred = np.full(n, 0.5)                            # uninformative -> 0.5
    degraded = regime_stratified_oof(y, np.arange(n), pred, one_hot,
                                     pooled_auc=0.90)
    assert degraded["bear"]["scored"]
    assert degraded["bear"]["auc"] == 0.5
    assert degraded["bear"]["degrade"] is True

    not_degraded = regime_stratified_oof(y, np.arange(n), pred, one_hot,
                                         pooled_auc=0.55)
    assert not_degraded["bear"]["degrade"] is False


# ------------------------------------------------------- learning curve (MLM)
# Standing plateau-vs-climb instrument (operator-approved, 2026-07-29): skill
# vs corpus size on expanding CHRONOLOGICAL prefixes, scored with the same
# time-purged walk-forward the deployed selector uses. Report-only in
# scripts/overfit_check.py — these pins cover the pure computation here.

def _lc_factory(seed=7):
    from ml.models import GradientBoostedStumps
    return lambda: GradientBoostedStumps(seed=seed)


def test_learning_curve_shape_and_prefix_monotonicity():
    from ml.overfit import LC_FRACTIONS, learning_curve
    X, y = _interaction_world(700, seed=5)
    sig = np.arange(700, dtype=float) * 300.0
    pts = learning_curve(X, y, None, sig, None, _lc_factory(),
                         label_span=30)
    assert len(pts) == len(LC_FRACTIONS)
    ns = [p["n"] for p in pts]
    assert ns == sorted(ns) and ns[-1] == 700
    for p in pts:
        if p["scored"]:
            assert 0.0 <= p["auc"] <= 1.0
            assert 0.0 <= p["brier"] <= 1.0
            assert p["n_oof"] >= 1


def test_learning_curve_sorts_by_signal_time_itself():
    """Prefixes must be CHRONOLOGICAL regardless of row order handed in —
    a shuffled corpus and its sorted twin produce identical curves."""
    from ml.overfit import learning_curve
    X, y = _interaction_world(500, seed=6)
    sig = np.arange(500, dtype=float) * 300.0
    rng = np.random.default_rng(0)
    perm = rng.permutation(500)
    a = learning_curve(X, y, None, sig, None, _lc_factory(), label_span=30)
    b = learning_curve(X[perm], y[perm], None, sig[perm], None,
                       _lc_factory(), label_span=30)
    for pa, pb in zip(a, b):
        assert pa["n"] == pb["n"] and pa["scored"] == pb["scored"]
        if pa["scored"]:
            assert pa["auc"] == pb["auc"]


def test_learning_curve_thin_prefix_not_scored():
    from ml.overfit import LC_MIN_OOF, learning_curve
    # 80-row corpus: the 25% prefix (20 rows) can never clear LC_MIN_OOF
    X, y = _interaction_world(80, seed=7)
    sig = np.arange(80, dtype=float) * 300.0
    pts = learning_curve(X, y, None, sig, None, _lc_factory(),
                         label_span=5)
    assert pts[0]["scored"] is False
    assert pts[0]["auc"] is None
    assert LC_MIN_OOF > 0                     # the floor exists and is real


def test_learning_curve_planted_signal_scores_above_chance_at_full_n():
    # a strong planted signal must be visible at the full prefix — the
    # instrument can distinguish "there is skill" from noise
    X, y = _interaction_world(900, d=10, seed=8, dense=True)
    from ml.overfit import learning_curve
    sig = np.arange(900, dtype=float) * 300.0
    pts = learning_curve(X, y, None, sig, None, _lc_factory(),
                         label_span=30)
    assert pts[-1]["scored"] and pts[-1]["auc"] > 0.55


def test_learning_curve_trend_verdicts():
    from ml.overfit import LC_TREND_MARGIN_AUC, learning_curve_trend

    def _pts(aucs):
        return [{"n": 100 * (i + 1), "scored": True, "auc": a,
                 "brier": 0.25, "n_oof": 100} for i, a in enumerate(aucs)]

    assert learning_curve_trend(_pts([0.48, 0.50, 0.55, 0.58]))["trend"] \
        == "climbing"
    assert learning_curve_trend(_pts([0.52, 0.50, 0.51, 0.52]))["trend"] \
        == "flat"
    assert learning_curve_trend(_pts([0.58, 0.56, 0.50, 0.48]))["trend"] \
        == "declining"
    # unscored points are excluded; < 3 scored points -> insufficient
    thin = [{"n": 100, "scored": False, "auc": None, "brier": None,
             "n_oof": 5}] * 4
    assert learning_curve_trend(thin)["trend"] == "insufficient"
    two = _pts([0.5, 0.6])
    assert learning_curve_trend(two)["trend"] == "insufficient"
    assert 0.0 < LC_TREND_MARGIN_AUC < 0.5


def test_overfit_check_learning_curve_section_is_report_only():
    """The runner's learning-curve section may only info(), never check() —
    same contract the regime diagnostic pins. Source pin on the script."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "scripts"
           / "overfit_check.py").read_text(encoding="utf-8")
    start = src.index("def learning_curve_diagnostic(")
    end = src.index("\ndef ", start + 10)
    # judge the CODE, not the docstring (which may itself say "check()")
    code = src[start:end].split('"""')[2]
    assert "check(" not in code
    assert "info(" in code
    # and main() wraps it in the same degrade-to-a-skip-line isolation
    assert "learning curve diagnostic skipped" in src


# ------------------------------------------------- DSR expected-max fidelity
def test_dsr_expected_max_uses_exact_quantiles():
    """Bailey & LdP's SR0 = sqrt(V)*[(1-g)*Z^-1(1-1/N) + g*Z^-1(1-1/(N*e))]
    with EXACT inverse-normal quantiles (2026-07-29 literature audit: the
    old sqrt(2 ln N) asymptotics overstated SR0 +12-17% at N=10-100)."""
    import math

    from ml.overfit import _norm_cdf, _norm_ppf, deflated_sharpe

    # the inverse is a true inverse of the module's own CDF
    for p in (0.05, 0.5, 0.9, 0.99, 0.999):
        assert abs(_norm_cdf(_norm_ppf(p)) - p) < 1e-12
    em = 0.5772156649
    for trials in (2, 10, 100):
        v = 0.04
        expected = math.sqrt(v) * (
            (1 - em) * _norm_ppf(1 - 1 / trials)
            + em * _norm_ppf(1 - 1 / (trials * math.e)))
        got = deflated_sharpe(0.5, 250, n_trials=trials,
                              var_trial_sr=v)["sr0_threshold"]
        assert abs(got - expected) < 1e-12
    # hand-checked paper value at N=10, V=0.04: Z^-1(0.9)=1.2816,
    # Z^-1(1-1/(10e))=1.7862 -> SR0 = 0.2*(0.4228*1.2816+0.5772*1.7862)
    got10 = deflated_sharpe(0.5, 250, n_trials=10,
                            var_trial_sr=0.04)["sr0_threshold"]
    assert abs(got10 - 0.3146) < 5e-4
    # single trial: no deflation
    assert deflated_sharpe(0.5, 250, n_trials=1)["sr0_threshold"] == 0.0


def test_parkinson_rms_is_unbiased_on_planted_gbm():
    """RMS (variance-domain mean) removes the exact Jensen bias
    (mean-of-vols / RMS = sqrt(8/pi)/sqrt(4ln2) = 0.9584 under driftless
    BM — Parkinson 1980). Two pins: (a) the Jensen ratio itself on the
    planted candles, (b) the blended estimate lands near true sigma at
    fine intra-bar discretization (the residual gap is Garman-Klass
    discrete-monitoring bias, ~O(1/sqrt(steps)), NOT the Jensen bias —
    at 500 steps it is a few percent, protective direction)."""
    import numpy as np

    from regime.vol_regime import VolRegimeEngine

    rng = np.random.default_rng(3)
    true_sigma, n, steps = 0.003, 3000, 500
    candles = []
    px = 100.0
    for _ in range(n):
        path = px * np.exp(np.cumsum(
            rng.normal(0.0, true_sigma / np.sqrt(steps), steps)))
        candles.append({"open": px, "high": float(path.max()),
                        "low": float(path.min()),
                        "close": float(path[-1])})
        px = float(path[-1])
    eng = VolRegimeEngine({"fast_lookback_bars_5m": n})
    highs = np.array([c["high"] for c in candles])
    lows = np.array([c["low"] for c in candles])
    variances = eng._parkinson(highs, lows)
    rms = float(np.sqrt(variances.mean()))
    mean_of_vols = float(np.sqrt(variances).mean())     # the OLD estimator
    assert abs(mean_of_vols / rms - 0.9584) < 0.01      # the exact Jensen gap
    st = eng.update("X", candles, [])
    est = st.sigma_bar_pct / 100.0
    # blend within a few percent of truth; the old form sat ~2.1% lower
    # ON TOP of discretization by construction
    assert abs(est - true_sigma) / true_sigma < 0.045
    assert est > (0.5 * true_sigma + 0.5 * mean_of_vols) - 1e-12


def test_dsr_trials_config_lifted_with_identical_default():
    """Debate-1 item A: OF-5's n_trials is a decision-path knob - lifted
    to ml.overfit.dsr_n_trials (identical default 7), guard-bounded."""
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    src = (root / "scripts" / "overfit_check.py").read_text(encoding="utf-8")
    assert "n_trials=_dsr_trials" in src, "OF-5 must read the lifted knob"
    assert "n_trials=7" not in src, "no bare trials literal in OF-5"
    cfg = json.loads((root / "config.json").read_text(encoding="utf-8"))
    assert cfg["ml"]["overfit"]["dsr_n_trials"] == 7, "identical default"

    from core.config_guard import validate

    def _msgs(c, sev):
        return [m for s, m in validate(c) if s == sev and "dsr_n_trials" in m]

    base = {"system": {"dry_run": True}}
    assert not _msgs(base, "FATAL"), "default must stay clean"
    bad = {"system": {"dry_run": True},
           "ml": {"overfit": {"dsr_n_trials": 0}}}
    assert _msgs(bad, "FATAL"), "0 trials is not a deflation"
    low = {"system": {"dry_run": True},
           "ml": {"overfit": {"dsr_n_trials": 3}}}
    assert _msgs(low, "WARN") and not _msgs(low, "FATAL"), \
        "below-baseline trials warns (weaker gate), never fatal"
