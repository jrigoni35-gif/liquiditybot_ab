"""core/evidence.py - the hypothesis ledger: Turing's Banburismus with 2026
anytime-valid guarantees (SAFE: pure functions; decides nothing).

WHY. Fixed-n reads (n=50 / n=100) answer one question once; a result read
early or often inflates false positives. Turing scored each hypothesis as a
running weight of evidence in DECIBANS and stopped the moment it was
decisive. The modern version of that stop rule is an e-process: a
nonnegative supermartingale under H0, so by Ville's inequality
P(ever >= 1/alpha) <= alpha - it may be watched every step and stopped at
any time (Waudby-Smith & Ramdas 2023, "Estimating means of bounded random
variables by betting"; e-BH: Wang & Ramdas 2022).

TWO E-PROCESSES PER HYPOTHESIS (side, null):
  e_exist  ("greater", 0)   - evidence the mean edge is ABOVE zero
  e_dead   ("less", 2c)     - evidence the mean edge is BELOW the round trip
Status: LIVE | ELIMINATED FOR TRIPS | EDGE BELOW ROUND TRIP (a tilt
candidate, never a trip) | UNDECIDED, at threshold 1/alpha (20 = 13.0 dB at
alpha 0.05). The ledger asks the TRIP question (edge vs 2c); "eliminated for
trips" says nothing about a smaller edge used as a tilt, which pays no round
trip - that is a different question with its own registration ("use").

BOUNDS (stated, not hidden). Observations are assumed inside [-B, B] around
the null. The upper tail is clipped at +B, which can only LOWER the mean, so
validity holds. A lower-tail breach below -2B would floor wealth at zero
(bankrupt bet); choose B >= the data's plausible range.

FAILURE MEMORY. `propose` refuses a hypothesis whose (signal, horizon)
fingerprint is already ELIMINATED - the 2026 agentic systems' "experience
memory", enforced - and stamps forward_from = the proposal date: evidence
counts only on data AFTER it (an LLM's or a paper's knowledge of the past
is leakage, "Profit Mirage", 2025).
"""
from __future__ import annotations

import math

import numpy as np


class AlreadyEliminated(ValueError):
    """The ledger already holds this idea as ELIMINATED."""


def decibans(e: float) -> float:
    return 10.0 * math.log10(e) if e > 0 else float("-inf")


def betting_eprocess(x, null_mean: float, bound: float, side: str) -> np.ndarray:
    """Running e-value after each observation.

    y_t = s * (x_t - null), s = +1 for "greater", -1 for "less"; H0: E[y] <= 0.
    Wealth_t = prod (1 + lam_t * min(y_t, B)), lam_t in [0, 1/(2B)] chosen
    from y_1..y_{t-1} only (aGRAPA: m / (v + m^2)), so the bet never sees the
    outcome it is placed on."""
    s = 1.0 if side == "greater" else -1.0
    y = s * (np.asarray(x, float) - null_mean)
    lam_max = 1.0 / (2.0 * bound)
    wealth, out = 1.0, np.empty(len(y))
    for t in range(len(y)):
        lam = 0.0
        if t >= 2:
            past = y[:t]
            m, v = past.mean(), past.var()
            lam = min(max(m / (v + m * m), 0.0), lam_max) if v + m * m > 0 else 0.0
        wealth *= max(1.0 + lam * min(y[t], bound), 0.0)
        out[t] = wealth
    return out


def status(e_exist: float, e_dead: float, threshold: float = 20.0) -> str:
    alive, dead = e_exist >= threshold, e_dead >= threshold
    if alive and dead:
        return "EDGE BELOW ROUND TRIP"
    if alive:
        return "LIVE"
    if dead:
        return "ELIMINATED FOR TRIPS"
    return "UNDECIDED"


def e_bh(e_values: dict, alpha: float = 0.05) -> set:
    """e-BH: FDR <= alpha under ANY dependence between the hypotheses."""
    m = len(e_values)
    ranked = sorted(e_values.items(), key=lambda kv: -kv[1])
    k_star = 0
    for k, (_, e) in enumerate(ranked, start=1):
        if e >= m / (alpha * k):
            k_star = k
    return {name for name, _ in ranked[:k_star]}


def _fingerprint(h: dict) -> tuple:
    return (h.get("signal"), h.get("horizon_h"), h.get("use", "trip"))


def propose(registry: list, hypothesis: dict, today: str) -> dict:
    """Admit a new hypothesis unless the ledger already eliminated it."""
    fp = _fingerprint(hypothesis)
    for h in registry:
        if _fingerprint(h) == fp and str(h.get("status", "")).startswith("ELIMINATED"):
            raise AlreadyEliminated(f"{fp} was eliminated as {h.get('id')}")
    return {**hypothesis, "registered_at": today, "forward_from": today,
            "status": "UNDECIDED"}


def trials(registry: list, family: str) -> int:
    """Every idea ever registered in a family counts - the multiplicity the
    2026 honest-evaluation literature says agentic search must carry."""
    return sum(1 for h in registry if h.get("family") == family)
