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

STICKINESS mechanism (documented here and in the C2 report): the brief
and plan are silent on the exact mechanism, so the choice made here is
a persistent, subtractive offset — the simplest mechanism that still
satisfies the one requirement that IS specified: an instant one-rung
downgrade that cannot bounce back on the same evidence. Concretely,
each maybe_downgrade() trip is recorded as a marker (see REDEMPTION
below) and the count of currently-uncleared markers is subtracted from
the freshly recomputed earned rung every time rung() is called, floored
at 0. This is NOT a one-shot override of a cached rung value — if it
were, the very next note_close()/rung() call would recompute straight
from the (unchanged) evidence counters and bounce right back up,
defeating "de-risk fast, re-earn slowly." A subtractive offset can't
bounce back on the same evidence: earned_rung stays capped by
(earned - uncleared_markers) until NEW evidence either raises
earned_rung further or clears a marker (below). Debouncing repeat
maybe_downgrade() calls while dd_frac stays elevated is the CALLER's
job — this class holds no timestamps to detect a breach edge.

REDEMPTION (re-earning a lost rung; the "re-earn slowly" half of the
spec that a forever-subtracted counter would violate — verified by
review: with no redemption, 1000 fresh closes after one downgrade could
never restore an already-earned rung 3). Each maybe_downgrade() trip
that actually drops a real rung (lost_rung >= 1) records a marker: the
rung held just before the drop, plus a snapshot of every evidence
counter at that instant. A marker is redeemed — its cap lifted — the
moment evidence accrued STRICTLY AFTER that snapshot re-clears the lost
rung's OWN gate on its own: fresh closed_paper >= r1.min_closed_paper
for a lost rung 1; fresh closed_live >= r2/r3's own min_closed_live
AND the profit factor over that SAME fresh window >= that rung's own
pf_floor for a lost rung 2 or 3 (the fresh-window pf, not the overall
running pf_live, is used — it is directly tractable since gross
win/loss are already counted, and it is the more honest read: only
evidence strictly after the downgrade should count toward earning it
back). A lost rung 3's adverse_transitions_survived requirement is
deliberately EXEMPT from redemption: survival is cumulative history (a
fact about the past that cannot un-happen), not a perishable that
decays with time or bad closes, so losing rung 3 does not demand
re-surviving a fresh adverse transition — only the closed-count/pf
evidence that actually regressed has to regress back. Downgrades stack
(repeat trips each add their own marker) and each marker redeems
independently against its own snapshot, in the order recorded. Markers
persist across to_dict()/from_dict() (JSON-safe: `downgrade_markers`,
a list of int/float dicts).

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


def _pf(gross_win: float, gross_loss: float) -> float:
    """Profit factor from gross win/loss usd — shared by the overall
    `pf_live` property and the per-marker fresh-window redemption check
    in EvidenceLadder._redeems(). `inf` for a win-only window (correctly
    clears any finite floor); `0.0` for a window with no evidence at all
    (correctly fails any positive floor rather than vacuously passing)."""
    if gross_loss > 0:
        return gross_win / gross_loss
    if gross_win > 0:
        return float("inf")
    return 0.0


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
        # Each entry: {"lost_rung", "closed_paper", "closed_live",
        # "gross_win_live", "gross_loss_live"} — a redemption marker per
        # applied downgrade (see module docstring, REDEMPTION). Pruned
        # of redeemed entries lazily by _prune_redeemed().
        self._downgrade_markers: list[dict] = []

    # ---- evidence feed ---------------------------------------------------
    def note_close(self, net_usd: float, is_live: bool) -> None:
        """Feed one realized, book-tagged close. `is_live` selects the
        paper vs live evidence track; only live closes feed the
        profit-factor counters (paper closes count toward r1's gate
        only — r1 is explicitly a paper-only gate). Two-argument form:
        deliberately omits the plan's third `book_equity_peak_frac_dd`
        arg — drawdown is fed separately via maybe_downgrade(dd_frac);
        controller-directed simplification, not a scope cut."""
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
        """Count of currently-uncleared downgrade markers (i.e. the
        offset actually applied by rung() right now) — redeemed markers
        are pruned first, so this reflects redemption immediately."""
        self._prune_redeemed()
        return len(self._downgrade_markers)

    # ---- profit factor -----------------------------------------------
    @property
    def pf_live(self) -> float:
        """Running live profit factor (gross win usd / gross loss usd).
        `inf` once there is at least one live win and zero live losses
        (an honest read of an unbroken streak — it correctly clears any
        finite pf_floor); `0.0` with no live evidence at all (correctly
        fails any positive pf_floor rather than vacuously passing)."""
        return _pf(self._gross_win_live, self._gross_loss_live)

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
        """Earned rung minus the sticky downgrade-marker offset, floored
        at 0. See the module docstring for why this is a persistent
        subtractive counter (not a cached one-shot rung assignment) and
        for the redemption mechanism that lets uncleared markers drop
        off on fresh evidence."""
        self._prune_redeemed()
        return max(0, self._earned_rung() - len(self._downgrade_markers))

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
        on True. Records a redemption marker (module docstring,
        REDEMPTION) capturing the rung actually held right before this
        drop plus the evidence counters at this instant — but only when
        a real rung is lost (rung() > 0 here); a trip while already
        floored at 0 has nothing to lose and nothing to later redeem.
        No internal edge-detection: this class holds no timestamps, so
        a caller that re-checks a still-breached dd_frac every cycle
        will keep applying downgrades one at a time: the engine (C3/C4)
        must debounce to one call per breach episode."""
        if float(dd_frac) >= self.cfg.dd_downgrade_pct / 100.0:
            lost_rung = self.rung()
            if lost_rung >= 1:
                self._downgrade_markers.append({
                    "lost_rung": lost_rung,
                    "closed_paper": self.closed_paper,
                    "closed_live": self.closed_live,
                    "gross_win_live": self._gross_win_live,
                    "gross_loss_live": self._gross_loss_live,
                })
            return True
        return False

    def _redeems(self, marker: dict) -> bool:
        """True iff `marker` is redeemed by evidence accrued STRICTLY
        AFTER its snapshot re-clearing the lost rung's OWN gate (module
        docstring, REDEMPTION). r3's adverse_transitions_survived is
        deliberately excluded — survival is cumulative history, not a
        perishable, so it does not need re-surviving."""
        lost_rung = marker["lost_rung"]
        if lost_rung <= 0:
            return False
        if lost_rung == 1:
            fresh_paper = self.closed_paper - marker["closed_paper"]
            return fresh_paper >= self.cfg.r1.min_closed_paper
        gate = self.cfg.r2 if lost_rung == 2 else self.cfg.r3
        fresh_live = self.closed_live - marker["closed_live"]
        if fresh_live < gate.min_closed_live:
            return False
        fresh_win = self._gross_win_live - marker["gross_win_live"]
        fresh_loss = self._gross_loss_live - marker["gross_loss_live"]
        # r3 carries no own pf_floor; its quality bar is r2's, same as forward earning.
        pf_gate = self.cfg.r2.pf_floor if lost_rung in (2, 3) else 0.0
        return _pf(fresh_win, fresh_loss) >= pf_gate

    def _prune_redeemed(self) -> None:
        """Drop every marker _redeems() as true, in recorded order.
        Mutates `_downgrade_markers` in place. Called before every
        rung()/downgrades read so redemption takes effect the instant
        fresh evidence clears it — no separate 'check redemption' call
        for the caller to remember."""
        if not self._downgrade_markers:
            return
        self._downgrade_markers = [
            m for m in self._downgrade_markers if not self._redeems(m)]

    # ---- persistence ---------------------------------------------------
    def to_dict(self) -> dict:
        """JSON-safe snapshot of all mutable state (the parsed `cfg` is
        NOT included — it is re-supplied by the caller at construction,
        same convention as RiskProtocolStack.to_dict/from_dict).
        `downgrade_markers` persists any uncleared redemption markers
        (already-redeemed ones are pruned first, so a restored ladder
        never carries dead markers)."""
        self._prune_redeemed()
        return {
            "closed_paper": self.closed_paper,
            "closed_live": self.closed_live,
            "gross_win_live": self._gross_win_live,
            "gross_loss_live": self._gross_loss_live,
            "adverse_transitions_survived":
                self._adverse_transitions_survived,
            "downgrade_markers": [dict(m) for m in self._downgrade_markers],
        }

    def from_dict(self, d: dict | None) -> None:
        """Restore state in place. Never raises: a corrupt/malformed
        snapshot degrades to keeping whatever state already existed on
        `self` (same fail-safe convention as CircuitBreaker.restore /
        RiskProtocolStack.from_dict) rather than crashing resume."""
        if not d:
            return
        try:
            closed_paper = int(d.get("closed_paper", self.closed_paper))
            closed_live = int(d.get("closed_live", self.closed_live))
            gross_win_live = float(
                d.get("gross_win_live", self._gross_win_live))
            gross_loss_live = float(
                d.get("gross_loss_live", self._gross_loss_live))
            adverse = int(d.get("adverse_transitions_survived",
                                 self._adverse_transitions_survived))
            markers = [
                {
                    "lost_rung": int(m["lost_rung"]),
                    "closed_paper": int(m["closed_paper"]),
                    "closed_live": int(m["closed_live"]),
                    "gross_win_live": float(m["gross_win_live"]),
                    "gross_loss_live": float(m["gross_loss_live"]),
                }
                for m in d.get("downgrade_markers", [])
            ]
        except (TypeError, ValueError, KeyError):
            log.warning("EvidenceLadder.from_dict: malformed snapshot - "
                        "keeping current counters")
            return
        self.closed_paper = closed_paper
        self.closed_live = closed_live
        self._gross_win_live = gross_win_live
        self._gross_loss_live = gross_loss_live
        self._adverse_transitions_survived = adverse
        self._downgrade_markers = markers
