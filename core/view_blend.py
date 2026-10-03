"""core/view_blend.py - Black-Litterman views on the target basket (SHADOW;
decides nothing).

THE ALGORITHM (operator 2026-10-03: "an algorithm that is known that can
incorporate all of these within itself"). One portfolio, many signals, each
signal a VIEW whose weight is earned, never assumed:

  prior      the target basket itself. Reverse optimisation (Black &
             Litterman 1992) gives the returns the basket implies,
             pi = delta * Sigma * w_basket, so with NO views the posterior
             weights are exactly the basket (pinned by a test).
  views      each signal is a row of P (which assets) with an expected
             excess return q over the holding horizon, sized by the
             Grinold rule q = IC * sigma_h * z (Grinold & Kahn 2000).
             Relative views (cross-sectional momentum) have rows summing
             to zero; absolute views (trend, stablecoin flow) do not.
  confidence Idzorek (2005): omega_k = (1/c_k - 1) * p_k tau Sigma p_k'.
             c_k comes from the evidence ledger (core/evidence.py): a view
             whose hypothesis is not promoted on FORWARD data has c = 0 and
             is dropped - the posterior cannot be moved by an unproven idea.
  posterior  mu = [(tau Sigma)^-1 + P' Omega^-1 P]^-1
                  [(tau Sigma)^-1 pi + P' Omega^-1 q]
  weights    w = (delta Sigma)^-1 mu, long-only (spot), each asset capped,
             total capped at invest_frac (an absolute view may LOWER total
             exposure; nothing raises it above the basket's own total).
  risk       risk_scale(): implied-vs-realised volatility and crowding may
             only SHRINK the volatility target (de-risk only, like the
             target book's pressure overlay).
  trading    unchanged: core/target_book aim_weights + band + plan
             (Garleanu & Pedersen 2013, Janecek & Shreve 2004).

SAFE: pure functions, numpy only, no I/O. Imported by no decision module
(tests/test_target_book_shadow_pin.py covers the pattern by name).
Record: docs/quant/2026-10-03_view_blend_design.md.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

TAU = 0.05                      # prior uncertainty scale (Black-Litterman's
                                # conventional 0.025-0.05; not fitted)
MAX_CONFIDENCE = 0.5            # no view, however promoted, may outweigh the prior
PROVEN = ("LIVE", "EDGE BELOW ROUND TRIP")   # core/evidence.status values


@dataclass(frozen=True)
class View:
    """One signal as a Black-Litterman view.

    p: asset -> coefficient (relative views sum to 0); q: expected excess
    return of the p-portfolio over the horizon (fraction); confidence in
    [0, MAX_CONFIDENCE]; 0 drops the view. hypothesis: registry id whose
    forward evidence earns the confidence."""
    name: str
    p: dict
    q: float
    confidence: float
    hypothesis: str = ""


def grinold_q(ic: float, sigma_h: float, z: float) -> float:
    """Expected excess return of a signal: IC x volatility x score."""
    return float(ic) * float(sigma_h) * float(z)


def confidence_from_status(status: str, db_exist_forward: float) -> float:
    """Evidence -> confidence. Only a hypothesis whose edge the ledger has
    proven on FORWARD data earns any weight: LIVE, or EDGE BELOW ROUND TRIP
    (real but too small to pay a trip - exactly what a view is for). The
    weight grows with the forward evidence in decibans (13 dB = the
    promotion line) and is capped. UNDECIDED, ELIMINATED, unknown: 0."""
    if str(status) not in PROVEN or not np.isfinite(db_exist_forward):
        return 0.0
    c = 1.0 - 10.0 ** (-max(float(db_exist_forward), 0.0) / 10.0)
    return float(min(MAX_CONFIDENCE, max(0.0, c)))


def implied_returns(w_basket: np.ndarray, sigma: np.ndarray, delta: float) -> np.ndarray:
    return delta * sigma @ w_basket


def posterior(pi: np.ndarray, sigma: np.ndarray, assets: list, views: list,
              tau: float = TAU) -> np.ndarray:
    """Black-Litterman posterior mean. Views with confidence <= 0 or an
    all-zero row are dropped; with none left the posterior IS the prior."""
    rows, qs, oms = [], [], []
    ts = tau * sigma
    for v in views:
        c = float(v.confidence)
        if c <= 0.0:
            continue
        p = np.array([float(v.p.get(a, 0.0)) for a in assets])
        if not np.any(p):
            continue
        c = min(c, MAX_CONFIDENCE)
        var = float(p @ ts @ p)
        if var <= 0.0:
            continue
        rows.append(p)
        qs.append(float(v.q))
        oms.append((1.0 / c - 1.0) * var)
    if not rows:
        return pi.copy()
    P, q, om_inv = np.array(rows), np.array(qs), np.diag(1.0 / np.array(oms))
    ts_inv = np.linalg.inv(ts)
    a = ts_inv + P.T @ om_inv @ P
    b = ts_inv @ pi + P.T @ om_inv @ q
    return np.linalg.solve(a, b)


def weights_from_mu(mu: np.ndarray, sigma: np.ndarray, delta: float,
                    invest_frac: float, cap_mult: float,
                    w_basket: np.ndarray) -> np.ndarray:
    """Mean-variance weights, then the spot constraints: no shorts, each
    asset at most cap_mult x its basket weight, total at most invest_frac."""
    w = np.linalg.solve(delta * sigma, mu)
    w = np.clip(w, 0.0, None)
    w = np.minimum(w, cap_mult * np.maximum(w_basket, 0.0))
    tot = float(w.sum())
    if tot > invest_frac and tot > 0:
        w = w * invest_frac / tot
    return w


def blend(assets: list, w_basket: dict, sigma: np.ndarray, views: list,
          invest_frac: float, cap_mult: float = 2.0, delta: float = 3.0,
          tau: float = TAU) -> dict:
    """The whole step: basket -> implied returns -> posterior -> weights."""
    wb = np.array([float(w_basket.get(a, 0.0)) for a in assets])
    pi = implied_returns(wb, sigma, delta)
    mu = posterior(pi, sigma, assets, views, tau)
    w = weights_from_mu(mu, sigma, delta, invest_frac, cap_mult, wb)
    return {a: float(x) for a, x in zip(assets, w, strict=True)}


def shrunk_cov(returns: np.ndarray, shrink: float = 0.5) -> np.ndarray:
    """Sample covariance shrunk toward its own diagonal (constant-correlation
    is overkill for a handful of assets). shrink is structural, not fitted."""
    s = np.cov(returns, rowvar=False, ddof=1)
    s = np.atleast_2d(s)
    return (1.0 - shrink) * s + shrink * np.diag(np.diag(s))


def risk_scale(iv_rv_ratio: float | None, crowding_z: float | None,
               iv_rv_hi: float = 1.5, crowd_hi: float = 2.0,
               floor: float = 0.5) -> float:
    """De-risk-only multiplier on the volatility target. Implied vol well
    above realised (the market pricing a move it has not made yet) or
    extreme crowding each scale risk down toward `floor`; missing data is
    neutral (1.0), never a reason to add risk."""
    m = 1.0
    if iv_rv_ratio is not None and np.isfinite(iv_rv_ratio) and iv_rv_ratio > iv_rv_hi:
        m = min(m, max(floor, iv_rv_hi / float(iv_rv_ratio)))
    if crowding_z is not None and np.isfinite(crowding_z) and abs(crowding_z) > crowd_hi:
        m = min(m, max(floor, crowd_hi / abs(float(crowding_z))))
    return float(m)
