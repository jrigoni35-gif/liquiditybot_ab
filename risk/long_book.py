"""risk/long_book.py — Compounder Phase C long-horizon accumulation book:
EvidenceLadder state machine (task C2, plan
docs/superpowers/plans/2026-07-24-compounder-phase-c-long-book.md §C2).
Pure, clock-free, fully injectable — no wall-clock reads, no I/O.

SCOPE (task C2 only): the evidence ladder that gates the long book's
position-sizing ceiling. LongBookEngine — the accumulation decision
core (spacing, context gates, TH-013 zone hygiene, add sizing) — is
task C3 and is deliberately NOT built here.

Evidence ladder (spec §5): rung 0 = paper only. The book trades
whenever the system runs; realized, BOOK-TAGGED closes earn rungs
r1-r3, each unlocking a wider equity-fraction ceiling. Ceilings are
config-lifted and guard-checked (core/config_guard._long_book_checks)
strictly increasing and <= the shared
risk_protocols.heat.max_portfolio_heat_frac — the long book's ceiling
lives INSIDE the combined portfolio heat cap, never its own risk stack.

  r1: closed_paper >= r1.min_closed_paper
  r2: r1 AND closed_live >= r2.min_closed_live AND pf_live >= r2.pf_floor
  r3: r2 AND closed_live >= r3.min_closed_live AND
      adverse_transitions_survived >= r3.adverse_transitions_survived

A true LADDER: each rung requires every lower rung's own gate to also
clear (you cannot skip r1's paper evidence on live evidence alone).
adverse_transitions_survived is an ENGINE-computed count (a risk-off
context episode the book survived — held exposure, drawdown stayed
under the downgrade line, start to end); this class only stores it via
note_adverse_transition_survived() — the engine (task C4) computes the
transition edges.

Downgrade (LB-041, instant, caller-logged): maybe_downgrade(dd_frac)
drops the EARNED rung by one the moment the book's own equity-curve
drawdown clears dd_downgrade_pct/100.

STICKINESS mechanism (chosen because the brief names it ambiguous and
asks for "the simplest honest one," documented here and in the C2
report): a persistent `_downgrades` counter, incremented once per
maybe_downgrade() trip, subtracted from the freshly recomputed earned
rung every time rung() is called, floored at 0. This is NOT a one-shot
override of a cached rung value — if it were, the very next
note_close()/rung() call would recompute straight from the (unchanged)
evidence counters and bounce right back up, defeating "de-risk fast,
re-earn slowly." A subtractive persistent offset can't bounce back on
the same evidence: earned_rung stays capped by (earned - downgrades)
until NEW evidence raises earned_rung further. Known, accepted gap:
there is no decay/recovery rule for `_downgrades` — none is specified
anywhere in the brief, so none is invented here. A book downgraded
once, after already earning rung 3 (the ladder's ceiling), can never
regain rung 3 (earned tops out at 3, so actual tops out at 2 forever)
without a future, consciously-designed recovery mechanism. Debouncing
repeat maybe_downgrade() calls while dd_frac stays elevated is the
CALLER's job — this class holds no timestamps to detect a breach edge.

Paper vs live ceiling: rung 0 means zero LIVE risk (live_ceiling_frac()
== 0.0, no live rung earned yet) but the book still trades in paper —
paper_ceiling_frac() floors at rung 1's ceiling regardless of the
earned rung, so paper sizing stays realistic from cycle one (the whole
point of paper-first is to size like it matters).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger("liquiditybot.risk.long_book")


@dataclass(frozen=True)
class RungGate:
    """One rung's unlock config: an equity-fraction ceiling plus the
    evidence gates that must clear (in addition to every lower rung's
    own gates) to earn it. A gate a given rung doesn't use keeps its
    zero default (e.g. r1 has no pf_floor)."""
    ceiling_frac: float
    min_closed_paper: int = 0
    min_closed_live: int = 0
    pf_floor: float = 0.0
    adverse_transitions_survived: int = 0


@dataclass(frozen=True)
class LadderConfig:
    """Parsed `long_book.ladder` sub-block (config.json). Defaults mirror
    the shipped planning-convention values (task-C2 brief) so a caller
    that passes an empty/partial dict gets a coherent ladder rather than
    a degenerate all-zero one."""
    r1: RungGate
    r2: RungGate
    r3: RungGate
    dd_downgrade_pct: float

    @classmethod
    def from_dict(cls, cfg: dict | None) -> "LadderConfig":
        cfg = cfg or {}
        r1 = cfg.get("r1", {}) or {}
        r2 = cfg.get("r2", {}) or {}
        r3 = cfg.get("r3", {}) or {}
        return cls(
            r1=RungGate(
                ceiling_frac=float(r1.get("ceiling_frac", 0.10)),
                min_closed_paper=int(r1.get("min_closed_paper", 10))),
            r2=RungGate(
                ceiling_frac=float(r2.get("ceiling_frac", 0.20)),
                min_closed_live=int(r2.get("min_closed_live", 15)),
                pf_floor=float(r2.get("pf_floor", 1.2))),
            r3=RungGate(
                ceiling_frac=float(r3.get("ceiling_frac", 0.30)),
                min_closed_live=int(r3.get("min_closed_live", 30)),
                adverse_transitions_survived=int(
                    r3.get("adverse_transitions_survived", 1))),
            dd_downgrade_pct=float(cfg.get("dd_downgrade_pct", 6.0)),
        )


class EvidenceLadder:
    """Pure, clock-free evidence-ladder state machine. Construct with the
    `long_book.ladder` sub-block (a plain dict, or None for defaults).
    Every method is deterministic given its injected inputs — no
    wall-clock reads, no I/O. Safe to construct one instance per
    long-book asset or one shared instance for the whole book, per the
    engine's (C3/C4) design — this class has no opinion either way."""

    def __init__(self, cfg: dict | None = None):
        self.cfg = LadderConfig.from_dict(cfg)
        self.closed_paper = 0
        self.closed_live = 0
        self._gross_win_live = 0.0
        self._gross_loss_live = 0.0
        self._adverse_transitions_survived = 0
        self._downgrades = 0

    # ---- evidence feed ---------------------------------------------------
    def note_close(self, net_usd: float, is_live: bool) -> None:
        """Feed one realized, book-tagged close. `is_live` selects the
        paper vs live evidence track; only live closes feed the
        profit-factor counters (paper closes count toward r1's gate
        only — r1 is explicitly a paper-only gate)."""
        net_usd = float(net_usd)
        if is_live:
            self.closed_live += 1
            if net_usd > 0:
                self._gross_win_live += net_usd
            elif net_usd < 0:
                self._gross_loss_live += -net_usd
        else:
            self.closed_paper += 1

    def note_adverse_transition_survived(self) -> None:
        """Engine-computed (task C4): call once per risk-off context
        episode the book survived (held exposure, drawdown stayed under
        the downgrade line, start to end). This class only stores the
        count — it has no context/regime awareness of its own."""
        self._adverse_transitions_survived += 1

    @property
    def adverse_transitions_survived(self) -> int:
        return self._adverse_transitions_survived

    @property
    def downgrades(self) -> int:
        return self._downgrades

    # ---- profit factor -----------------------------------------------
    @property
    def pf_live(self) -> float:
        """Running live profit factor (gross win usd / gross loss usd).
        `inf` once there is at least one live win and zero live losses
        (an honest read of an unbroken streak — it correctly clears any
        finite pf_floor); `0.0` with no live evidence at all (correctly
        fails any positive pf_floor rather than vacuously passing)."""
        if self._gross_loss_live > 0:
            return self._gross_win_live / self._gross_loss_live
        if self._gross_win_live > 0:
            return float("inf")
        return 0.0

    # ---- rung ------------------------------------------------------------
    def _earned_rung(self) -> int:
        g1 = self.closed_paper >= self.cfg.r1.min_closed_paper
        g2 = (g1 and self.closed_live >= self.cfg.r2.min_closed_live
              and self.pf_live >= self.cfg.r2.pf_floor)
        g3 = (g2 and self.closed_live >= self.cfg.r3.min_closed_live
              and self._adverse_transitions_survived
              >= self.cfg.r3.adverse_transitions_survived)
        if g3:
            return 3
        if g2:
            return 2
        if g1:
            return 1
        return 0

    def rung(self) -> int:
        """Earned rung minus the sticky downgrade offset, floored at 0.
        See the module docstring for why this is a persistent subtractive
        counter and not a cached one-shot rung assignment."""
        return max(0, self._earned_rung() - self._downgrades)

    def _ceiling_for_rung(self, r: int) -> float:
        if r <= 0:
            return 0.0
        if r == 1:
            return self.cfg.r1.ceiling_frac
        if r == 2:
            return self.cfg.r2.ceiling_frac
        return self.cfg.r3.ceiling_frac

    def live_ceiling_frac(self) -> float:
        """Equity-fraction ceiling for LIVE sizing. Rung 0 -> 0.0 (paper
        only, by design — no live risk until r1 is earned)."""
        return self._ceiling_for_rung(self.rung())

    def paper_ceiling_frac(self) -> float:
        """Equity-fraction ceiling for PAPER sizing. Floors at rung 1's
        ceiling regardless of the earned rung so paper always sizes
        realistically — the book trades whenever the system runs, and
        rung 0 in paper is not "no risk," it's "no LIVE risk"."""
        return self._ceiling_for_rung(max(self.rung(), 1))

    # ---- downgrade ---------------------------------------------------
    def maybe_downgrade(self, dd_frac: float) -> bool:
        """Instant, one-rung drop the moment `dd_frac` clears
        dd_downgrade_pct/100 (dd_frac is a fraction, e.g. 0.07 for a 7%
        drawdown; dd_downgrade_pct is a whole-number percent). Returns
        True iff this call applied a downgrade — the caller logs LB-041
        on True. No internal edge-detection: this class holds no
        timestamps, so a caller that re-checks a still-breached dd_frac
        every cycle will keep applying downgrades one at a time: the
        engine (C3/C4) must debounce to one call per breach episode."""
        if float(dd_frac) >= self.cfg.dd_downgrade_pct / 100.0:
            self._downgrades += 1
            return True
        return False

    # ---- persistence ---------------------------------------------------
    def to_dict(self) -> dict:
        """JSON-safe snapshot of all mutable state (the parsed `cfg` is
        NOT included — it is re-supplied by the caller at construction,
        same convention as RiskProtocolStack.to_dict/from_dict)."""
        return {
            "closed_paper": self.closed_paper,
            "closed_live": self.closed_live,
            "gross_win_live": self._gross_win_live,
            "gross_loss_live": self._gross_loss_live,
            "adverse_transitions_survived":
                self._adverse_transitions_survived,
            "downgrades": self._downgrades,
        }

    def from_dict(self, d: dict | None) -> None:
        """Restore state in place. Never raises: a corrupt/malformed
        snapshot degrades to keeping whatever state already existed on
        `self` (same fail-safe convention as CircuitBreaker.restore /
        RiskProtocolStack.from_dict) rather than crashing resume."""
        if not d:
            return
        try:
            self.closed_paper = int(d.get("closed_paper", self.closed_paper))
            self.closed_live = int(d.get("closed_live", self.closed_live))
            self._gross_win_live = float(
                d.get("gross_win_live", self._gross_win_live))
            self._gross_loss_live = float(
                d.get("gross_loss_live", self._gross_loss_live))
            self._adverse_transitions_survived = int(d.get(
                "adverse_transitions_survived",
                self._adverse_transitions_survived))
            self._downgrades = int(d.get("downgrades", self._downgrades))
        except (TypeError, ValueError):
            log.warning("EvidenceLadder.from_dict: malformed snapshot - "
                        "keeping current counters")
