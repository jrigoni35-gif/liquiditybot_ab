"""Calibration observability + a conservative selection metric.

Every candidate reports its calibrated OOF Brier and residual calibration
gap (the "look into the gap" deliverable). Selection itself stays on RAW
Brier on purpose: raw Brier penalizes miscalibration, so it is the stricter,
simplicity-preserving bar. Selecting on calibrated Brier let isotonic
"rescue" a complex model's miscalibration and elect it in a pure-linear world
- the opposite of the overfit discipline. The deploy gate (main.py) applies
calibration as the FINAL ship check; selection refuses to be rescued into
complexity.
"""
import numpy as np

from ml.calibration import IsotonicCalibrator, brier_score
from ml.walkforward import evaluate_and_select


def _data(n=600, seed=5):
    rng = np.random.default_rng(seed)
    X = rng.normal(0, 1, (n, 6))
    y = (X[:, 0] * 1.1 + rng.normal(0, 1.0, n) > 0).astype(float)
    return X, y


def test_results_report_calibrated_brier_and_gap():
    X, y = _data()
    r = evaluate_and_select(X, y, n_splits=4)
    for k in r["admitted"]:
        assert "mean_brier_cal" in r[k] and "calib_gap" in r[k]
        assert 0.0 <= r[k]["calib_gap"] <= 1.0
        assert 0.0 < r[k]["mean_brier_cal"] < 0.5


def test_selection_uses_raw_brier_the_conservative_bar():
    """The winner must be argmin over the ladder on RAW Brier within the
    simplicity margin - the stricter bar that penalizes miscalibration."""
    X, y = _data()
    r = evaluate_and_select(X, y, n_splits=4)
    winner = r["selected"]
    from ml.walkforward import BRIER_MARGIN
    wb = r[winner]["mean_brier"]
    for k in r["admitted"]:
        assert r[k]["mean_brier"] >= wb - BRIER_MARGIN - 1e-12


def test_calibrated_selection_would_not_be_rescued_into_complexity():
    """A pure-linear world must keep the baseline. This is the exact case
    where selecting on CALIBRATED Brier misfired (isotonic rescued a complex
    model past the margin); raw-Brier selection holds the line."""
    rng = np.random.default_rng(3)
    X = rng.normal(size=(700, 6))
    y = (rng.random(700) < 1 / (1 + np.exp(-(0.9 * X[:, 0] - 0.1)))
         ).astype(float)
    r = evaluate_and_select(X, y, label_span=30)
    assert r["selected"] == "logistic"


def test_reported_calibrated_brier_matches_deploy_path_recompute():
    """The reported mean_brier_cal for the winner must equal what
    main._maybe_auto_retrain recomputes (fit fresh isotonic on sel['oof_p'],
    Brier on the transform) - the diagnostic and the deploy gate must agree."""
    X, y = _data()
    r = evaluate_and_select(X, y, n_splits=4)
    sel = r[r["selected"]]
    cal = IsotonicCalibrator().fit(sel["oof_p"], sel["oof_y"])
    oof_cal = cal.transform(sel["oof_p"])
    deploy_brier = brier_score(sel["oof_y"], oof_cal)
    assert abs(deploy_brier - sel["mean_brier_cal"]) < 1e-9
