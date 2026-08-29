"""Foundational Confidence (FC) — confidence in a FOUNDATION, not an outcome.

SHADOW INSTRUMENT (operator directive 2026-08-29). Measurement only: NOT wired
into any decision path, sizer, gate, or order — that would be model
development, frozen 2026-08-10. Nothing in main.py/runner.py/risk/execution
imports this. It SCORES how much each causal thesis behind a decision is
earning its keep, so the operator can see which foundations to trust, and so
the system can act under irreducible uncertainty without deadlocking on an
unprovable edge.

WHY THIS EXISTS — the "non-emotional trader" made mechanical. A human who
phases out individual wins and losses does not track P&L; they track whether
the FOUNDATION that led them into the trade held up, WHY a win or loss
happened, and what it led to. This instrument does the same: the sign of the
P&L never moves confidence by itself — only the ATTRIBUTED cause does. A loss
that happened for a known, documented external reason (a news gap, beta, not
the thesis failing) barely dents the foundation; a loss where the thesis's own
mechanism was invalidated moves it a lot.

THE MATH — three coupled ideas.

1. LOG-ODDS (the logarithmic equation; it compounds). Confidence in a
   foundation F is carried as log-odds L = ln( P(F valid) / P(F invalid) ).
   Evidence is Bayesian and ADDITIVE in log space:
       L <- L + w * llr
   where llr is the log-likelihood ratio of one outcome under F-valid vs
   F-invalid (+ validates, - invalidates) and w is its weight. Because updates
   ADD, a foundation that keeps being validated COMPOUNDS its confidence
   linearly in the count of (effective, attributed) confirmations — the
   compound-improvement the operator asked for. Confidence itself is the
   logistic C = sigma(L) = 1/(1+e^-L) in (0,1).

2. ATTRIBUTION x INDEPENDENCE (the real reasoning; the non-emotional core).
   The weight w = attribution * independence:
     - attribution a in [0,1]: how much this outcome was CAUSED by F's
       mechanism vs external/noise/beta. a=0 => the outcome is uninformative
       about F (a loss "despite" the thesis does not tank it). This is the
       documented WHY.
     - independence u in (0,1]: the effective-n weight. Overlapping/correlated
       observations carry less evidence — you cannot compound confidence out
       of correlated trips (the n_eff ceiling the session measured).

3. DEGRADATION (anti-deadlock; the parameter set). Absent fresh evidence,
   L decays toward the prior 0 (maximal uncertainty) with a half-life tau:
       L <- L * exp(-dt * ln2 / tau)
   and L is clamped to [L_FLOOR, L_CEIL]. Together these BREAK DEADLOCK two
   ways: (a) a once-invalidated foundation decays back UP toward "I don't
   know" so the system will RE-TEST it rather than locking it out forever; a
   once-validated one decays back DOWN so it must keep earning rather than
   locking in stale over-confidence. (b) the floor guarantees confidence never
   collapses to "never act" — it bottoms out at a small "willing to test"
   level, so an unprovable edge is probed at small size and left to compound
   if it is real, instead of vetoed into a deadlock.

Every update is written to a LEDGER (what F predicted, what happened, the
attribution and llr, the resulting L) — the "how it got documented and why /
what it led to" the operator named.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# Confidence never reaches certainty (always some doubt, always updatable) and
# never reaches zero (always a minimum willing-to-test level) — the two bounds
# that keep the system out of both over-confidence and under-confidence
# deadlock. sigma(+/-4) ~= 0.982 / 0.018.
L_CEIL = 4.0
L_FLOOR = -4.0
DEFAULT_HALF_LIFE_S = 7.0 * 86400.0  # 1 week: the degradation parameter


def confidence_of(log_odds: float) -> float:
    """Logistic map log-odds -> confidence in (0,1)."""
    if log_odds >= 0:
        return 1.0 / (1.0 + math.exp(-log_odds))
    e = math.exp(log_odds)          # underflow-safe for very negative L
    return e / (1.0 + e)


def llr_binary(p_foundation: float, p_baseline: float, won: bool) -> float:
    """The unit-safe way to turn a binary outcome into an llr for observe().

    Returns the log-likelihood ratio in NATS of the outcome under the
    foundation's predicted win-probability vs a baseline: contextual (measured
    AGAINST the baseline, not in a vacuum), proportional (a ratio), and
    dimensionless. NEVER pass a raw return (%) or a P&L ($) as `llr` — those
    are different units and adding them into a log-odds accumulator is
    meaningless (operator directive 2026-08-29: nothing enters the equation
    without context and proportion). A continuous outcome (a return) must be
    reduced to such a probability first (e.g. did it clear its own cost-and-
    target threshold), never fed in raw.

    Both probabilities are clamped off {0,1}: a certainty claim is never
    admitted, so one outcome can never send confidence to the bound in a
    single step (same anti-deadlock spirit as L_FLOOR/L_CEIL).
    """
    if not (math.isfinite(p_foundation) and math.isfinite(p_baseline)):
        raise ValueError("probabilities must be finite")
    eps = 1e-6
    pf = min(1.0 - eps, max(eps, p_foundation))
    p0 = min(1.0 - eps, max(eps, p_baseline))
    if won:
        return math.log(pf / p0)
    return math.log((1.0 - pf) / (1.0 - p0))


@dataclass
class Foundation:
    """One causal thesis, with its earned-and-degraded log-odds confidence."""

    name: str
    half_life_s: float = DEFAULT_HALF_LIFE_S
    log_odds: float = 0.0                 # prior = 0 => confidence 0.5
    n_eff: float = 0.0                    # accumulated effective evidence
    last_ts: "float | None" = None
    ledger: list = field(default_factory=list)

    def _decay_to(self, ts: float) -> None:
        """Degrade toward the prior (0) by elapsed time. Anti-deadlock: stale
        confidence reverts to 'willing to test', high or low."""
        if self.last_ts is None:
            self.last_ts = ts
            return
        dt = ts - self.last_ts
        if dt > 0.0 and self.half_life_s > 0.0:
            self.log_odds *= math.exp(-dt * math.log(2.0) / self.half_life_s)
        # a backwards clock never AGES evidence; it just re-anchors
        self.last_ts = max(ts, self.last_ts)

    def observe(self, ts: float, llr: float, attribution: float,
                independence: float, note: str = "") -> float:
        """Update on one outcome and return the new confidence.

        llr: log-likelihood ratio in NATS under F-valid vs F-invalid (sign: +
             validates, - invalidates). MUST come from llr_binary() or an
             equivalently unit-consistent nats derivation — never a raw return
             or P&L (unit-mixing; operator directive 2026-08-29).
        attribution in [0,1]: how much the outcome was caused by F's mechanism
             (0 => uninformative; the non-emotional filter).
        independence in (0,1]: effective-n weight (correlated obs weigh less).
        """
        if not (0.0 <= attribution <= 1.0):
            raise ValueError(f"attribution must be in [0,1], got {attribution}")
        if not (0.0 < independence <= 1.0):
            raise ValueError(f"independence must be in (0,1], got {independence}")
        if not math.isfinite(llr):
            raise ValueError(f"llr must be finite, got {llr}")
        self._decay_to(ts)
        w = attribution * independence
        self.log_odds = max(L_FLOOR, min(L_CEIL, self.log_odds + w * llr))
        self.n_eff += independence
        c = confidence_of(self.log_odds)
        self.ledger.append({
            "ts": ts, "llr": llr, "attribution": attribution,
            "independence": independence, "weight": w,
            "log_odds": self.log_odds, "confidence": c, "note": note,
        })
        return c

    def confidence(self, ts: "float | None" = None) -> float:
        """Current confidence, decayed to `ts` if given (a read is also a
        degradation — confidence you have not re-earned is worth less)."""
        if ts is not None:
            self._decay_to(ts)
        return confidence_of(self.log_odds)


def combine(foundations: "list[Foundation]", ts: "float | None" = None
            ) -> float:
    """Confidence of a DECISION resting on several INDEPENDENT foundations:
    log-odds add (evidence compounds across foundations), then map to (0,1).
    Empty set => 0.5 (no foundation => maximal uncertainty, still willing to
    test — never 0, never deadlocked)."""
    if not foundations:
        return 0.5
    total = 0.0
    for f in foundations:
        if ts is not None:
            f._decay_to(ts)
        total += f.log_odds
    return confidence_of(max(L_FLOOR, min(L_CEIL, total)))
