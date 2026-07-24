"""risk/conviction.py — Phase A Conviction Formula (Compounder program,
docs/superpowers/specs/2026-07-24-compounder-framework-design.md §2).

Deterministic, registered admission rule for CONVICTION entries (the
non-probe channel). A conviction entry is admitted only when ALL terms
agree — conjunctive, no fitted weights, no blended scores; every
disposition is a registered CV-* code (core/codes.py).

Terms (fixed evaluation order; the FIRST failing term names the code):
  1 agreement    — the gate stack's own agreement measure (pass-fraction
                   of gates_passed, the same arithmetic
                   strategies/signal_gates.py uses for its confidence)
                   at/above conviction.agreement_floor. agreement=None
                   means not-applicable (no gate stack to agree on - the
                   long book today) and auto-passes, exactly symmetric
                   with term 4's None semantics (C4 review, Important #4).
  2 ev multiple  — est_edge_bps >= ev_cost_mult x est_cost_bps, where
                   est_* are the pretrade gate's MEASURED round-trip
                   numbers for THIS entry. config_guard pins
                   ev_cost_mult >= pretrade.min_edge_cost_ratio (a
                   conviction bar under the pretrade bar is vacuous).
                   est_edge_bps/est_cost_bps=None means not-applicable
                   (no pretrade EV gate on this path) and auto-passes
                   (either both are None together, or neither - the
                   caller's contract, not enforced here).
  3 regime known — the current regime's live-label count at/above the T4
                   coverage floor (engine-side: main.
                   _regime_under_coverage_floor over
                   history.regime_live_count). No evidence, no conviction.
  4 context      — long-book only: context_aligned=None means
                   not-applicable (the 5m book today) and auto-passes;
                   False denies with CV-040. Phase B/C wire real values.

MODES — report (shipped default) vs enforce:
  report:  every conviction attempt is evaluated and audit-logged;
           entry behavior stays BYTE-IDENTICAL (nothing is blocked).
           This is the honest threshold-derivation period: floors and
           multiples are re-derived from REPORTED dispositions.
  enforce: a denied conviction entry is skipped (registered code). The
           config flip is a CONSCIOUS operator decision after report
           telemetry review + green quant-trials adjudication at
           200x1200 — never widened to make CI pass (OF-4 / T6 law).

Cadence governor: mirror of the P3 probe throttle's rolling window —
the admit share of the last share_window conviction EVALUATIONS (global
+ per-regime). Outside [share_lo, share_hi] with >= share_min_n samples
the formula has silently become always-on/always-off: that raises a
CV-050/051 alarm on the state TRANSITION (audit + status). It never
auto-tunes a threshold. Windows are process-local, not persisted: a
restart judges nothing until share_min_n fresh samples accrue —
silence, never a false alarm, is the failure mode of a reset window.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional, Tuple

from core.codes import Code


@dataclass(frozen=True)
class ConvictionDecision:
    admitted: bool
    code: Code
    terms: Dict[str, Any]


class ConvictionFormula:
    def __init__(self, cfg: dict):
        cfg = cfg or {}
        self.enabled = bool(cfg.get("enabled", True))
        self.mode = str(cfg.get("mode", "report"))
        self.agreement_floor = float(cfg.get("agreement_floor", 0.75))
        self.ev_cost_mult = float(cfg.get("ev_cost_mult", 2.0))
        self.share_window = max(int(cfg.get("share_window", 40)), 1)
        self.share_min_n = max(int(cfg.get("share_min_n", 20)), 1)
        self.share_lo = float(cfg.get("share_lo", 0.10))
        self.share_hi = float(cfg.get("share_hi", 0.90))
        self._admits: Deque[bool] = deque(maxlen=self.share_window)
        self._regime_admits: Dict[str, Deque[bool]] = {}
        self._alarm_state: Dict[str, str] = {}
        self._evaluated = 0
        self._admitted = 0
        self._denials: Dict[str, int] = {}

    @property
    def enforce(self) -> bool:
        return self.enabled and self.mode == "enforce"

    def evaluate(self, *, agreement: Optional[float],
                 est_edge_bps: Optional[float],
                 est_cost_bps: Optional[float], regime_known: bool,
                 context_aligned: Optional[bool] = None
                 ) -> ConvictionDecision:
        """Pure and deterministic: same inputs, same decision. The terms
        dict carries the full evidence (values + thresholds) so the audit
        payload explains every disposition without re-derivation.

        `agreement`/`est_edge_bps`/`est_cost_bps` accept None = not-
        applicable (C4 review, Important #4): the term is auto-passed and
        recorded as null in `terms`, exactly symmetric with `context_
        aligned`'s existing None convention. Every 5m call site always
        passes real floats (unchanged); the long-book admission path
        passes None for terms 1-2 (it has no gate-stack agreement measure
        or pretrade EV estimate of its own to offer) instead of the prior
        fabricated 1.0/1.0/0.0 stand-ins that trivially cleared both
        terms - None is an honest "not measured," not a faked pass."""
        terms: Dict[str, Any] = {
            "agreement": None if agreement is None
            else round(float(agreement), 4),
            "agreement_floor": self.agreement_floor,
            "est_edge_bps": None if est_edge_bps is None
            else round(float(est_edge_bps), 2),
            "est_cost_bps": None if est_cost_bps is None
            else round(float(est_cost_bps), 2),
            "ev_cost_mult": self.ev_cost_mult,
            "regime_known": bool(regime_known),
            "context_aligned": context_aligned,
        }
        if agreement is not None and float(agreement) < self.agreement_floor:
            return ConvictionDecision(False, Code.CV_AGREEMENT_LOW, terms)
        if est_edge_bps is not None and est_cost_bps is not None and \
                float(est_edge_bps) < self.ev_cost_mult * float(est_cost_bps):
            return ConvictionDecision(False, Code.CV_EV_MULTIPLE_LOW, terms)
        if not regime_known:
            return ConvictionDecision(False, Code.CV_REGIME_UNKNOWN, terms)
        if context_aligned is False:
            return ConvictionDecision(False, Code.CV_CONTEXT_MISALIGNED,
                                      terms)
        return ConvictionDecision(True, Code.CV_ADMIT, terms)

    # ---- cadence governor (mirror of the P3 probe-share window) -----

    def note(self, decision: ConvictionDecision, regime_label: str) -> None:
        """Feed one conviction EVALUATION (admit or deny) into the rolling
        cadence windows. Evaluations, not orders: the governor watches the
        FORMULA's selectivity, which exists in report mode too."""
        self._evaluated += 1
        if decision.admitted:
            self._admitted += 1
        else:
            self._denials[decision.code.value] = \
                self._denials.get(decision.code.value, 0) + 1
        self._admits.append(decision.admitted)
        d = self._regime_admits.get(regime_label)
        if d is None:
            d = deque(maxlen=self.share_window)
            self._regime_admits[regime_label] = d
        d.append(decision.admitted)

    @staticmethod
    def _share(d: Deque[bool]) -> float:
        return (sum(1 for a in d if a) / len(d)) if d else 0.0

    def cadence_alarms(self) -> List[Tuple[Code, str]]:
        """Transition-edge alarms only (state CHANGES, never per-cycle
        spam): for the global window and each regime window holding >=
        share_min_n samples, an admit share outside [share_lo, share_hi]
        raises CV-050/051 once, until the state changes again. The
        governor never auto-tunes a threshold — thresholds move only by
        conscious re-derivation (overfit law)."""
        out: List[Tuple[Code, str]] = []
        windows = [("all", self._admits)] + sorted(
            self._regime_admits.items())
        for key, d in windows:
            if len(d) < self.share_min_n:
                continue
            share = self._share(d)
            state = "high" if share > self.share_hi else \
                    "low" if share < self.share_lo else "ok"
            if state != self._alarm_state.get(key, "ok") and state != "ok":
                code = Code.CV_CADENCE_HIGH if state == "high" \
                    else Code.CV_CADENCE_LOW
                out.append((code,
                            f"conviction admit share {share:.0%} ({key}, "
                            f"n={len(d)}) outside [{self.share_lo:.0%}, "
                            f"{self.share_hi:.0%}]"))
            self._alarm_state[key] = state
        return out

    def status(self) -> dict:
        return {
            "enabled": self.enabled, "mode": self.mode,
            "evaluated": self._evaluated, "admitted": self._admitted,
            "denials": dict(self._denials),
            "share": round(self._share(self._admits), 3),
            "n": len(self._admits),
            "by_regime": {k: {"share": round(self._share(d), 3),
                              "n": len(d)}
                          for k, d in sorted(self._regime_admits.items())},
            "alarm": self._alarm_state.get("all", "ok"),
        }
