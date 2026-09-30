"""Pins for ml/markov_edge.py + scripts/markov_edge_report.py (research only).

The instrument must be able to FAIL: a planted persistent state drift has to
be found out of sample, a driftless corpus must not produce one, and the
walk-forward purge must exclude every label that resolves inside the test day.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from ml import markov_edge as me  # noqa: E402
import markov_edge_report as rep  # noqa: E402

H = 432 * 300.0


# ---------------- Brownian first passage ----------------
def test_driftless_is_the_fair_game():
    assert me.bm_hit_prob(0.0, 0.018, 0.0135) == pytest.approx(
        0.0135 / 0.0315)


@pytest.mark.parametrize("psi", [-9.0, -1.3, -1e-6, 1e-6, 0.7, 11.0])
@pytest.mark.parametrize("r", [0.3, 3 / 7, 0.5, 4 / 7])
def test_reflection_identity(psi, r):
    # P(up first | psi, r) + P(down first) = 1, and down-first is the
    # reflected problem: drift -psi, barrier ratio 1 - r
    assert me.hit_prob(psi, r) + me.hit_prob(-psi, 1 - r) == pytest.approx(
        1.0, abs=1e-9)


def test_monotone_in_drift_and_bounded():
    p = me.hit_prob(me.PSI_GRID, 3 / 7)
    assert np.all(np.diff(p) >= -1e-12)
    assert p[0] < 2e-3 and p[-1] > 0.99         # measured 0.00105 / 0.99417


def test_matches_monte_carlo():
    # discrete Gaussian random walk with drift ~ Brownian motion; the
    # step is small against the barriers so discretisation bias is < 1%
    rng = np.random.default_rng(0)
    a, b, mu, sig, dt = 1.0, 0.75, 0.4, 1.0, 1e-3
    theta = 2 * mu / sig ** 2
    n, x = 4000, np.zeros(4000)
    done = np.zeros(n, bool)
    up = np.zeros(n, bool)
    while not done.all():
        live = ~done
        x[live] += mu * dt + sig * np.sqrt(dt) * rng.standard_normal(
            live.sum())
        hu, hd = live & (x >= a), live & (x <= -b)
        up |= hu
        done |= hu | hd
    assert up.mean() == pytest.approx(me.bm_hit_prob(theta, a, b), abs=0.03)


def test_fair_p_and_value_agree():
    a, b, c = 0.018, 0.0135, 0.0045
    ps = me.fair_p(a, b, c)
    assert float(me.expected_value(ps, a, b, c)) == pytest.approx(0.0,
                                                                  abs=1e-12)


def test_short_is_the_flipped_problem():
    a, b = 0.018, 0.0135
    # a short wins when price hits -a before +b
    assert me.side_p(0.8, a, b, -1) == pytest.approx(
        1 - float(me.hit_prob(0.8, a / (a + b))))
    act, _, ev = me.best_action(0.0, a, b, 0.0045)
    assert act == "skip" and ev == 0.0          # the fair game never trades


def test_map_recovers_planted_drift_and_prior_shrinks():
    rng = np.random.default_rng(1)
    r = np.full(4000, 3 / 7)
    y = (rng.random(4000) < me.hit_prob(1.5, r)).astype(float)
    L = me.outcome_loglik(y, r)
    sd = me.prior_sd(3 / 7, 50)
    assert me.map_psi(L, sd) == pytest.approx(1.5, abs=0.25)
    # 10 straight up-first rows: the bare likelihood runs to the grid edge,
    # 50 driftless pseudo-observations hold the estimate near the fair game
    L10 = me.outcome_loglik(np.ones(10), np.full(10, 3 / 7))
    assert me.map_psi(L10, 1e6) == me.PSI_GRID[-1]
    assert 0.0 < me.map_psi(L10, sd) < 1.5
    assert me.map_psi(L[:0], sd) == 0.0


def test_chain_is_stochastic_and_never_crosses_assets():
    A = me.transition_matrix([[0, 0, 1], [2, 2]], 3, alpha=1.0)
    assert np.allclose(A.sum(axis=1), 1.0)
    # state 1 is only ever LAST in its asset's sequence: its row is the pure
    # prior. Concatenating the assets would add a false 1 -> 2 transition.
    assert np.allclose(A[1], [1 / 3, 1 / 3, 1 / 3])
    assert np.allclose(A[0], [2 / 5, 2 / 5, 1 / 5])
    occ = me.occupancy(A, 0, 1)
    assert occ.tolist() == [1.0, 0.0, 0.0]


# ---------------- walk-forward instrument ----------------
def _synthetic(psi_by_state, days=24, per_day=150, stay=0.97, seed=3,
               day_noise=0.0):
    rng = np.random.default_rng(seed)
    K = len(psi_by_state)
    rows = {k: [] for k in ("ts", "asset", "side", "up_first", "resolved",
                            "r", "pt", "sl", "cost", "ret", "sigma",
                            "state")}
    s = 0
    for day in range(days):
        lvl = rng.normal(0, day_noise)
        for i in range(per_day):
            if rng.random() > stay:
                s = int(rng.integers(0, K))
            side = 1 if rng.random() < 0.5 else -1
            pt, sl = 0.018, 0.0135
            up_d, dn_d = (pt, sl) if side > 0 else (sl, pt)
            r = dn_d / (up_d + dn_d)
            upf = rng.random() < me.hit_prob(psi_by_state[s] + lvl, r)
            win = upf == (side > 0)
            rows["ts"].append(day * 86400.0 + i * 500.0)
            rows["asset"].append("X")
            rows["side"].append(side)
            rows["up_first"].append(float(upf))
            rows["resolved"].append(True)
            rows["r"].append(r)
            rows["pt"].append(pt)
            rows["sl"].append(sl)
            rows["cost"].append(0.0045)
            rows["ret"].append((pt if win else -sl) - 0.0045)
            rows["sigma"].append(0.00225)
            rows["state"].append(s)
    d = {k: np.asarray(v) for k, v in rows.items()}
    d["day"] = (d["ts"] // 86400).astype(int)
    return d


def _state_spec(K):
    return lambda d, tr: (d["state"], K)


def test_planted_edge_is_found_out_of_sample():
    d = _synthetic([-2.5, 0.0, 2.5])
    L = me.outcome_loglik(d["up_first"], d["r"])
    res, tested = rep.walk_forward(d, L, _state_spec(3), horizon_sec=H)
    for v in ("static", "chain"):
        assert np.mean(res[v]["gain"]) > 0.02, v
        assert np.mean(res[v]["auc"]) > 0.6, v
        assert np.mean(res[v]["uplift"]) > 0.0, v
    assert tested.sum() > 0


def test_no_edge_is_not_invented():
    d = _synthetic([0.0, 0.0, 0.0])
    L = me.outcome_loglik(d["up_first"], d["r"])
    res, _ = rep.walk_forward(d, L, _state_spec(3), horizon_sec=H)
    assert np.mean(res["static"]["gain"]) < 0.005
    assert abs(np.mean(res["static"]["auc"]) - 0.5) < 0.06


def test_permutation_null_destroys_the_planted_edge():
    d = _synthetic([-2.5, 0.0, 2.5])
    L = me.outcome_loglik(d["up_first"], d["r"])
    nres, _ = rep.walk_forward(d, L, _state_spec(3),
                               rng=np.random.default_rng(5), horizon_sec=H)
    assert np.mean(nres["static"]["gain"]) < 0.01


def test_purge_excludes_labels_resolving_in_the_test_day():
    d = {"ts": np.array([0.0, 86400 * 5 - H - 1, 86400 * 5 - H,
                         86400 * 5 - 1.0])}
    m = rep.train_mask(d, 5, H)
    # only a label whose full horizon ends before day 5 starts may train
    assert m.tolist() == [True, True, False, False]


def test_hold_steps_follow_expected_exit_time():
    d = _synthetic([0.0], days=2, per_day=50)
    seqs = rep._sequences(d, d["state"], np.ones(len(d["ts"]), bool))
    k = rep._hold_steps(d, np.ones(len(d["ts"]), bool), seqs, H)
    # (a/sigma)(b/sigma) = 8 x 6 = 48 bars = 14400 s over 500 s gaps
    assert k["X"] == round(48 * 300 / 500)


def test_research_only_nothing_in_the_order_path_imports_it():
    offenders = []
    for base in ("main.py", "runner.py", "core", "execution", "risk",
                 "strategies", "regime", "data", "api"):
        p = ROOT / base
        files = [p] if p.is_file() else list(p.rglob("*.py"))
        for f in files:
            if "markov_edge" in f.read_text(encoding="utf-8", errors="ignore"):
                offenders.append(str(f.relative_to(ROOT)))
    assert offenders == []


# ---------------- forward-registered operator spec ----------------
def test_operator_spec_states_and_train_only_cut():
    d = {"regime": np.array([-1, 0, 1, 2, 3, 4, 0, 4]),
         "sigma": np.array([1.0, 1.0, 1.0, 1.0, 9.0, 9.0, 9.0, 9.0])}
    tr = np.array([True] * 4 + [False] * 4)       # train median = 1.0
    s, k = rep._operator_spec(d, tr)
    assert k == 6 and s.min() >= 0 and s.max() < k
    # none->range, bull, bull, range, bear, bear(crisis), bull, bear
    assert (s // 2).tolist() == [1, 0, 0, 1, 2, 2, 0, 2]
    # the cut is the TRAIN median (1.0): every test row (9.0) is high-vol.
    # An all-rows median (5.0) would also split the train rows - it doesn't.
    assert (s % 2).tolist() == [0, 0, 0, 0, 1, 1, 1, 1]
    d2 = dict(d, sigma=np.array([1.0, 2.0, 3.0, 4.0, 0.0, 0.0, 0.0, 0.0]))
    s2, _ = rep._operator_spec(d2, tr)            # train median 2.5
    assert (s2 % 2).tolist() == [0, 0, 1, 1, 0, 0, 0, 0]


def test_forward_spec_never_scores_a_day_before_its_registration():
    d = _synthetic([-2.5, 0.0, 2.5], days=24)
    L = me.outcome_loglik(d["up_first"], d["r"])
    _, tested = rep.walk_forward(d, L, _state_spec(3), horizon_sec=H,
                                 min_test_day=20)
    assert tested.any()
    assert d["day"][tested].min() >= 20
    _, none = rep.walk_forward(d, L, _state_spec(3), horizon_sec=H,
                               min_test_day=10_000)
    assert not none.any()


def test_no_test_days_reads_nan_never_a_significant_p(tmp_path):
    # a corpus that ends before FORWARD_FROM: the forward spec has zero test
    # days, and its p must be nan - not the 1/(1+R) floor that reads as 0.005
    import csv
    rng = np.random.default_rng(11)
    path = tmp_path / "sh.csv"
    cols = ["source", "label_era", "signal_ts", "direction", "pt_frac",
            "sl_frac", "label_ret_pct", "sigma_bar_pct", "barrier", "asset",
            "basis_dir", "venue_disloc_dir"] + rep.REGIMES
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for i in range(12 * 60):
            side = 1 if i % 2 else -1
            bar = ["tb_pt", "tb_sl", "tb_time"][int(rng.integers(0, 3))]
            ret = {"tb_pt": 1.8 - 0.45, "tb_sl": -1.35 - 0.45,
                   "tb_time": 0.1}[bar]
            reg = [0.0] * 5
            reg[int(rng.integers(0, 5))] = 1.0
            w.writerow(["candidate", "triple_barrier_h432",
                        rep.ERA9_START + 100 + i * 1440, side, 0.018,
                        0.0135, ret, 0.225, bar, "X",
                        rng.normal(), rng.normal(), *reg])
    out = rep.run(path, null_reps=2)
    fwd = out["specs"]["operator"]
    assert fwd["scored_rows"] == 0 and fwd["forward_from"] == rep.FORWARD_FROM
    for v in ("static", "chain"):
        assert fwd[v]["test_days"] == 0
        assert np.isnan(fwd[v]["null_p"]) and np.isnan(fwd[v]["auc_null_p"])
    assert out["specs"]["pooled"]["static"]["test_days"] > 0
    assert out["counting"]["ok"]
    # the CS-1 line counts the REGISTERED specs' scoring, never the forward's
    assert out["counting"]["buckets"]["scored"] ==         out["specs"]["pooled"]["scored_rows"] > 0


# ---------------- test-side censoring (correction 2026-09-30) ----------------
def test_a_day_is_mature_only_after_its_last_label_could_resolve():
    end5 = 6 * 86400.0                     # day 5 ends here
    assert rep.mature_day(5, end5 + H, H)
    assert not rep.mature_day(5, end5 + H - 1, H)
    assert rep.mature_day(5, None, H)      # no as-of = caller's own risk


def test_immature_test_days_are_never_scored():
    d = _synthetic([-2.5, 0.0, 2.5], days=24)
    L = me.outcome_loglik(d["up_first"], d["r"])
    as_of = 20 * 86400.0 + H               # days 0..19 mature, 20..23 not
    _, tested = rep.walk_forward(d, L, _state_spec(3), horizon_sec=H,
                                 as_of=as_of)
    assert tested.any()
    assert d["day"][tested].max() == 19
