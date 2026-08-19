"""Metric implementations pinned against hand-computed / analytic values —
the numpy-only stand-ins for sklearn/scipy must EARN trust, not borrow it.
Each pin is a value derivable on paper, not a recorded output."""
import math

import numpy as np

import scripts.ground_truth_metrics as gm


def test_confusion_and_prf1_hand_case():
    #            true: 1 1 0 0 1   pred: 1 0 0 1 1
    cm = gm.confusion([1, 1, 0, 0, 1], [1, 0, 0, 1, 1])
    assert cm == [[1, 1], [1, 2]]           # tn=1 fp=1 / fn=1 tp=2
    prec, rec, f1 = gm.prf1(cm)
    assert abs(prec - 2 / 3) < 1e-12
    assert abs(rec - 2 / 3) < 1e-12
    assert abs(f1 - 2 / 3) < 1e-12          # p==r -> f1==p


def test_average_precision_known_value():
    # ranks by score: y=1 (p=1/1), y=0, y=1 (p=2/3) -> AP=(1+2/3)/2
    ap = gm.average_precision([1, 0, 1], [0.9, 0.8, 0.7])
    assert abs(ap - (1.0 + 2.0 / 3.0) / 2.0) < 1e-12
    # degenerate: no positives -> 0.0 by contract
    assert gm.average_precision([0, 0], [0.9, 0.1]) == 0.0


def test_ks_identical_and_disjoint():
    a = np.linspace(0, 1, 50)
    d, p = gm.ks_2samp(a, a.copy())
    assert d == 0.0 and p > 0.99
    d2, p2 = gm.ks_2samp(np.zeros(40), np.ones(40))
    assert d2 == 1.0 and p2 < 1e-6


def test_chisquare_analytic_df2():
    # obs [10,20,30] vs exp [20,20,20]: chi2 = 5+0+5 = 10, df=2,
    # survival(df=2) = exp(-chi2/2) = exp(-5) — analytic, on paper
    chi2, p, valid = gm.chisquare([10, 20, 30], [20, 20, 20])
    assert abs(chi2 - 10.0) < 1e-12
    assert abs(p - math.exp(-5.0)) < 1e-9
    assert valid is True
    # perfect fit -> chi2 0, p 1
    c0, p0, _ = gm.chisquare([5, 5], [5, 5])
    assert c0 == 0.0 and abs(p0 - 1.0) < 1e-12
    # Cochran floor: any expected cell under 5 -> flagged invalid
    _, _, v = gm.chisquare([1, 9], [2, 8])
    assert v is False


def test_bland_altman_known_bias():
    ba = gm.bland_altman([1.0, 2.0, 3.0], [0.5, 1.5, 2.5])
    assert ba["n"] == 3
    assert abs(ba["bias"] - 0.5) < 1e-12
    assert abs(ba["sd_diff"]) < 1e-12       # constant offset -> sd 0
    assert abs(ba["loa_low"] - 0.5) < 1e-9


def test_render_md_carries_caveats_and_rejections(tmp_path):
    rep = {"corpus": "SYNTHETIC benchmark (test)", "on_synthetic": True,
           "family": "logistic", "n_rows": 10, "n_oof": 8,
           "rejected": {"accuracy": "a", "mae_rmse_r2": "b"},
           "ks_train_vs_recent": {}, "chi_square_barrier_mix": {},
           "bland_altman_referees": {}}
    md = gm.render_md(rep)
    assert "SYNTHETIC" in md and "machinery, not market" in md
    assert "Rejected metrics" in md
