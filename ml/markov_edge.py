# ml/markov_edge.py
"""Markov-modulated Brownian edge model (operator request 2026-09-29).
RESEARCH ONLY - nothing in the order path imports this module (pinned by
tests/test_markov_edge.py). scripts/markov_edge_report.py is its one caller.

WHY. The 2026-09-29 directional screen found no single feature with a usable
edge (the strongest, venue_disloc_dir, AUC 0.414). The operator asked for a
Markov chain that combines signals into STATES and forms the best action per
state, grounded in Brownian theory and judged walk-forward.

THE MODEL.
  1. STATES  a small pre-registered discretisation of MARKET-ABSOLUTE
             variables (the side-relative *_dir features times the side).
  2. DRIFT   price is Brownian with a state-dependent drift. P(up barrier
             first) depends on the drift only through theta = 2*mu/sigma^2,
             and with barriers a (up) and b (down) only through
             psi = theta*(a+b) and the ratio r = b/(a+b):
                 P_up = (e^{psi*r} - 1) / (e^{psi*r} - e^{-psi*(1-r)})
             psi is DIMENSIONLESS - drift per barrier width - so assets of
             different volatility share one parameter per state. psi = 0 is
             the fair game: P_up = r (= b/(a+b)).
  3. FIT     per state, a MAP estimate of psi from barrier outcomes on a
             grid, under a N(0, sd^2) prior whose sd is set by a PSEUDO-COUNT:
             the prior weighs as much as `prior_n` driftless observations.
  4. CHAIN   a Dirichlet-smoothed transition matrix over states; the drift
             a trade experiences is psi averaged over the chain's expected
             OCCUPANCY across the holding time (an approximation of the
             exact Markov-modulated first passage: it treats the drift as
             constant at its time-average).
  5. ACTION  long / short / skip by expected value net of cost - the fair-game
             condition V = p*a - (1-p)*b - C > 0.

Pure numpy, no I/O. Units: a, b, cost are fractions of price.
"""
from __future__ import annotations

import numpy as np

# psi grid: +-12 barrier-widths. At the bot's 4:3 bracket (r = 3/7 or 4/7)
# it spans P_up 0.001..0.994 (r = 3/7) and 0.006..0.999 (r = 4/7); fitted
# values sit far inside (a MAP on the bound means the grid must widen). The
# 0.025 step is far below any estimable resolution at n ~ 10^3.
PSI_GRID = np.linspace(-12.0, 12.0, 961)


def hit_prob(psi, r):
    """P(drifted Brownian motion hits the up barrier first), vectorised.
    psi = theta*(a+b), r = b/(a+b) in (0, 1). Numerically stable for large
    |psi| (both branches keep every exponent <= 0)."""
    psi = np.asarray(psi, float)
    r = np.asarray(r, float)
    psi, r = np.broadcast_arrays(psi, r)
    out = np.array(r, dtype=float, copy=True)          # psi == 0 limit
    pos = psi > 1e-9
    neg = psi < -1e-9
    # psi > 0: divide through by e^{psi*r}
    p, rr = psi[pos], r[pos]
    out[pos] = -np.expm1(-p * rr) / -np.expm1(-p)
    # psi < 0: multiply through by e^{psi*(1-r)}
    q, rn = psi[neg], r[neg]
    out[neg] = np.expm1(q * rn) * np.exp(q * (1 - rn)) / np.expm1(q)
    return np.clip(out, 0.0, 1.0)


def bm_hit_prob(theta: float, a: float, b: float) -> float:
    """Scalar form in price units: P(hit +a before -b), theta = 2mu/sigma^2."""
    if a <= 0 or b <= 0:
        raise ValueError("barrier distances must be positive")
    return float(hit_prob(theta * (a + b), b / (a + b)))


def fair_p(a: float, b: float, cost: float) -> float:
    """Break-even win probability p* = (b + C) / (a + b)."""
    return (b + cost) / (a + b)


def expected_value(p, a, b, cost):
    """V = p*a - (1-p)*b - C (fractions of price)."""
    return np.asarray(p) * a - (1.0 - np.asarray(p)) * b - cost


def outcome_loglik(up_first, r) -> np.ndarray:
    """(n, len(PSI_GRID)) matrix of log P(outcome_i | psi_g). Precomputed
    once per corpus; a state's likelihood is then a column sum over its rows,
    which is what makes the within-day permutation null affordable."""
    up = np.asarray(up_first, float)[:, None]
    p = hit_prob(PSI_GRID[None, :], np.asarray(r, float)[:, None])
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return up * np.log(p) + (1 - up) * np.log1p(-p)


def prior_sd(r_mean: float, prior_n: float) -> float:
    """Prior sd on psi equal in weight to `prior_n` driftless observations.
    Fisher information per observation at psi = 0 is (dP/dpsi)^2 / (r(1-r))
    with dP/dpsi|_0 = r(1-r)/2, i.e. r(1-r)/4."""
    info = r_mean * (1 - r_mean) / 4.0
    return float(1.0 / np.sqrt(max(prior_n, 1e-9) * info))


def map_psi(loglik_rows: np.ndarray, sd: float) -> float:
    """MAP psi from a state's rows of the outcome_loglik matrix."""
    if loglik_rows.shape[0] == 0:
        return 0.0
    post = loglik_rows.sum(axis=0) - 0.5 * (PSI_GRID / sd) ** 2
    return float(PSI_GRID[int(np.argmax(post))])


def transition_matrix(seqs, n_states: int, alpha: float = 1.0) -> np.ndarray:
    """Row-stochastic K x K matrix from consecutive pairs within each
    sequence of `seqs` (one sequence per asset - never across assets),
    Dirichlet(alpha)-smoothed so no transition has probability 0."""
    C = np.full((n_states, n_states), float(alpha))
    for s in seqs:
        s = np.asarray(s, int)
        if len(s) > 1:
            np.add.at(C, (s[:-1], s[1:]), 1.0)
    return C / C.sum(axis=1, keepdims=True)


def occupancy(A: np.ndarray, s: int, k: int) -> np.ndarray:
    """Mean state distribution over steps 0..k-1 starting in s."""
    k = max(int(k), 1)
    v = np.zeros(A.shape[0])
    v[int(s)] = 1.0
    acc = np.zeros_like(v)
    for _ in range(k):
        acc += v
        v = v @ A
    return acc / k


def effective_psi(A: np.ndarray, psis, s: int, k: int) -> float:
    """Occupancy-weighted drift over a k-step hold starting in state s."""
    return float(occupancy(A, s, k) @ np.asarray(psis, float))


def side_p(psi: float, a: float, b: float, side: int) -> float:
    """Win probability for a trade on `side` (+1 long, -1 short) with its
    own target a and stop b. A short's target is DOWN: it wins when the
    price path hits -a before +b, i.e. the up-first problem with the drift
    sign flipped and the barriers swapped."""
    r = b / (a + b)
    return float(hit_prob(psi if side > 0 else -psi, r))


def best_action(psi: float, a: float, b: float, cost: float) -> tuple:
    """(action, p, ev) over {long, short, skip}; skip has ev 0."""
    p_l, p_s = side_p(psi, a, b, +1), side_p(psi, a, b, -1)
    ev_l = float(expected_value(p_l, a, b, cost))
    ev_s = float(expected_value(p_s, a, b, cost))
    if max(ev_l, ev_s) <= 0.0:
        return "skip", float("nan"), 0.0
    if ev_l >= ev_s:
        return "long", p_l, ev_l
    return "short", p_s, ev_s
