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
                   at/above conviction.agreement_floor
  2 ev multiple  — est_edge_bps >= ev_cost_mult x est_cost_bps, where
                   est_* are the pretrade gate's MEASURED round-trip
                   numbers for THIS entry. config_guard pins
                   ev_cost_mult >= pretrade.min_edge_cost_ratio (a
                   conviction bar under the pretrade bar is vacuous).
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

    def evaluate(self, *, agreement: float, est_edge_bps: float,
                 est_cost_bps: float, regime_known: bool,
                 context_aligned: Optional[bool] = None
                 ) -> ConvictionDecision:
        """Pure and deterministic: same inputs, same decision. The terms
        dict carries the full evidence (values + thresholds) so the audit
        payload explains every disposition without re-derivation."""
        terms: Dict[str, Any] = {
            "agreement": round(float(agreement), 4),
            "agreement_floor": self.agreement_floor,
            "est_edge_bps": round(float(est_edge_bps), 2),
            "est_cost_bps": round(float(est_cost_bps), 2),
            "ev_cost_mult": self.ev_cost_mult,
            "regime_known": bool(regime_known),
            "context_aligned": context_aligned,
        }
        if float(agreement) < self.agreement_floor:
            return ConvictionDecision(False, Code.CV_AGREEMENT_LOW, terms)
        if float(est_edge_bps) < self.ev_cost_mult * float(est_cost_bps):
            return ConvictionDecision(False, Code.CV_EV_MULTIPLE_LOW, terms)
        if not regime_known:
            return ConvictionDecision(False, Code.CV_REGIME_UNKNOWN, terms)
        if context_aligned is False:
            return ConvictionDecision(False, Code.CV_CONTEXT_MISALIGNED,
                                      terms)
        return ConvictionDecision(True, Code.CV_ADMIT, terms)
