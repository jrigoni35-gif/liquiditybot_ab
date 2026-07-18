"""tests/test_tune_search.py — the champion calibration engine's math.

The engine is report-only plumbing around four pure pieces: LHS coverage,
RBF surrogate fidelity, IDW exploration geometry, and the bad-region
penalty. The end-to-end pin: on a known synthetic bowl the loop finds the
basin in a budget grid search could never afford at real experiment cost.
"""
import numpy as np

from scripts.tune_search import (acquisition, fit_rbf, idw,
                                 latin_hypercube, propose, surrogate)

B = np.array([[0.0, 1.0], [0.0, 1.0]])


def test_lhs_in_bounds_and_stratified():
    pts = latin_hypercube(10, np.array([[2.0, 4.0], [-1.0, 1.0]]))
    assert pts.shape == (10, 2)
    assert (pts[:, 0] >= 2).all() and (pts[:, 0] <= 4).all()
    assert (pts[:, 1] >= -1).all() and (pts[:, 1] <= 1).all()
    # one sample per axis stratum (the whole point vs uniform random)
    strata = np.floor((pts[:, 0] - 2.0) / 2.0 * 10).astype(int)
    assert len(set(strata.tolist())) == 10


def test_rbf_surrogate_preserves_ordering():
    X = latin_hypercube(12, B, seed=3)
    y = ((X - 0.3) ** 2).sum(1)                 # bowl centred at (.3, .3)
    beta = fit_rbf(X, y)
    near = surrogate(np.array([0.31, 0.29]), X, beta)[0]
    far = surrogate(np.array([0.95, 0.95]), X, beta)[0]
    assert near < far


def test_idw_zero_at_samples_positive_elsewhere():
    X = np.array([[0.5, 0.5]])
    assert idw(np.array([0.5, 0.5]), X)[0] == 0.0
    assert idw(np.array([0.9, 0.9]), X)[0] > 0.0


def test_delta_steers_exploration():
    X = latin_hypercube(12, B, seed=1)          # enough cover for a faithful
    y = ((X - 0.3) ** 2).sum(1)                 # surrogate minimum
    # pure exploitation proposes near the best-known basin
    exploit = propose(X, y, B, delta=0.0)
    assert np.linalg.norm(exploit - 0.3) < 0.35
    # heavy exploration proposes far from every tested point
    explore = propose(X, y, B, delta=50.0)
    d_min = np.sqrt(((X - explore) ** 2).sum(1)).min()
    assert d_min > 0.15


def test_bad_region_repels():
    # bowl at the CENTER, bad point in one corner: the two corners have
    # symmetric surrogate values, so the ONLY difference between them is
    # the infeasibility penalty — the clean measure of its effect
    X = latin_hypercube(12, B, seed=2)
    y = ((X - 0.5) ** 2).sum(1)
    bad = np.array([[0.1, 0.1]])
    beta = fit_rbf(X, y)
    at_bad = acquisition(np.array([0.1, 0.1]), X, y, beta, bad,
                         delta=0.0)[0]
    mirror = acquisition(np.array([0.9, 0.9]), X, y, beta, bad,
                         delta=0.0)[0]
    assert at_bad > mirror + 0.5                # penalty, not surrogate noise


def test_end_to_end_finds_basin_within_budget():
    rng = np.random.default_rng(11)
    target = np.array([0.62, 0.24])

    def experiment(theta):
        return float(((theta - target) ** 2).sum()
                     + 0.001 * rng.standard_normal())
    X = latin_hypercube(6, B, seed=5)
    y = np.array([experiment(t) for t in X])
    for _ in range(14):                         # 20 experiments total
        nxt = propose(X, y, B, delta=1.0)
        X = np.vstack([X, nxt])
        y = np.append(y, experiment(nxt))
    best = X[int(np.argmin(y))]
    assert np.linalg.norm(best - target) < 0.12


def test_proposals_stay_in_bounds():
    bounds = np.array([[5.0, 6.0], [-2.0, -1.0]])
    X = latin_hypercube(4, bounds, seed=9)
    y = np.arange(4.0)
    p = propose(X, y, bounds, delta=1.0)
    assert bounds[0, 0] <= p[0] <= bounds[0, 1]
    assert bounds[1, 0] <= p[1] <= bounds[1, 1]


def test_near_duplicate_points_do_not_blow_up():
    X = np.array([[0.5, 0.5], [0.5 + 1e-9, 0.5]])
    y = np.array([1.0, 1.0])
    beta = fit_rbf(X, y)
    assert np.all(np.isfinite(beta))
    assert np.isfinite(surrogate(np.array([0.4, 0.4]), X, beta)[0])
