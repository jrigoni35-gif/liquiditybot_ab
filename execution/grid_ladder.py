"""
execution/grid_ladder.py — v10 logistic-armed grid entry ladder.

Grid mechanics with a logistic brain: when a confirmed signal's meta p(win)
clears an ARM bar, the single approved entry is split into a short ladder of
resting maker rungs stepped away from the quote — grid-style laddered entries,
but every rung exists only because the logistic model says the trade is worth
existing, and the WHOLE ladder is bounded by what the PositionSizer already
approved (rung sizes are decay-weighted fractions of the sized total, never
more). Deeper rungs buy (sell) strictly further from fair value than the
rung-0 price the PreTradeGate evaluated, so each deeper rung carries strictly
MORE edge than the entry the EV gate approved — the gate's verdict is
monotone down the ladder by construction.

Hardening (the desk way):
  * ARM/DISARM hysteresis (p_win_arm > p_win_disarm) so a p(win) hovering at
    the bar cannot flap the ladder on and off every cycle;
  * retraction: a spoofy book, a manipulation veto, or a direction flip
    disarms the asset instantly (plan returns unarmed -> caller falls back to
    the plain single-entry path; resting rungs die on the OrderManager's own
    short timeout, so no standing orders outlive their thesis);
  * the caller caps rung count by FREE POSITION SLOTS and the per-asset
    same-side inventory cap, so rung fills can never breach either;
  * rungs are maker limit orders through the full existing rail (firewall,
    collar, venue minimums) — invariant OM-011 untouched;
  * pure planning: plan() is a deterministic function of its inputs plus the
    per-asset armed state — no I/O, no clock, replay/step-test friendly.

All knobs live in config.json `grid_ladder` (guarded by config_guard);
defaults ship DISABLED and behavior-preserving.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from core.codes import Code, tag
from core.sanitize import is_finite as _fin

log = logging.getLogger("liquiditybot.execution.grid_ladder")


@dataclass
class Rung:
    idx: int                 # 0 = at the approved quote price
    price: float
    size_units: float
    offset_bps: float        # distance from rung 0, in bps (0 for rung 0)


@dataclass
class LadderPlan:
    asset: str
    direction: Optional[str]
    armed: bool
    rungs: List[Rung] = field(default_factory=list)
    reason: str = ""         # tagged reason code for the audit trail


class GridLadderEngine:
    def __init__(self, config: dict):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", False))
        self.max_rungs = int(cfg.get("rungs", 3))
        self.spacing_vol_mult = float(cfg.get("spacing_vol_mult", 0.35))
        self.min_spacing_bps = float(cfg.get("min_spacing_bps", 8.0))
        self.size_decay = float(cfg.get("size_decay", 0.7))
        self.p_win_arm = float(cfg.get("p_win_arm", 0.60))
        self.p_win_disarm = float(cfg.get("p_win_disarm", 0.55))
        self._armed: dict = {}          # asset -> direction while armed

    # ------------------------------------------------------------------
    def _retract(self, asset: str, direction: Optional[str],
                 why: str) -> LadderPlan:
        if self._armed.pop(asset, None) is not None:
            log.info("%s", tag(Code.GL_RETRACTED, f"{asset}: {why}"))
        return LadderPlan(asset, direction, False, [],
                          tag(Code.GL_RETRACTED, why))

    def plan(self, asset: str, direction: str, quote_price: float,
             sigma_bar_pct: float, total_units: float, p_win: float,
             liq_label: str = "liquid", manip_vetoed: bool = False,
             max_rungs: Optional[int] = None) -> LadderPlan:
        """Desired ladder for one APPROVED entry (sizer + pretrade already
        passed). Unarmed plan => caller uses the plain single-entry path."""
        if not self.enabled:
            return LadderPlan(asset, direction, False)
        # fail-closed input validation: any garbage input disarms
        if direction not in ("long", "short") \
                or not _fin(quote_price) or quote_price <= 0 \
                or not _fin(total_units) or total_units <= 0 \
                or not _fin(p_win) or not _fin(sigma_bar_pct):
            return self._retract(asset, direction, "invalid inputs")
        # retraction conditions (belt + braces: upstream gates already block
        # spoofy/manip entries, but the engine must be safe standalone)
        if liq_label == "spoofy":
            return self._retract(asset, direction, "spoofy book")
        if manip_vetoed:
            return self._retract(asset, direction, "manipulation veto")

        # ---- ARM / DISARM hysteresis --------------------------------------
        held = self._armed.get(asset)
        if held is not None and held != direction:
            self._retract(asset, held, f"direction flip {held}->{direction}")
            held = None
        if held is None:
            if p_win < self.p_win_arm:
                return LadderPlan(asset, direction, False, [],
                                  tag(Code.GL_BELOW_ARM,
                                      f"p_win {p_win:.3f} < arm "
                                      f"{self.p_win_arm:.2f}"))
            self._armed[asset] = direction
            log.info("%s", tag(Code.GL_ARMED,
                               f"{asset} {direction} p_win={p_win:.3f}"))
        elif p_win < self.p_win_disarm:
            return self._retract(
                asset, direction,
                f"p_win {p_win:.3f} < disarm {self.p_win_disarm:.2f}")

        # ---- geometry -----------------------------------------------------
        sigma_bar_bps = max(sigma_bar_pct, 0.0) * 100.0
        spacing = max(self.min_spacing_bps,
                      self.spacing_vol_mult * sigma_bar_bps)
        n = self.max_rungs
        if max_rungs is not None:
            n = min(n, int(max_rungs))
        n = max(1, n)
        weights = [self.size_decay ** k for k in range(n)]
        wsum = sum(weights)
        sign = -1.0 if direction == "long" else 1.0   # long ladders BELOW
        rungs = [Rung(idx=k,
                      price=quote_price * (1.0 + sign * spacing * k / 1e4),
                      size_units=total_units * w / wsum,
                      offset_bps=spacing * k)
                 for k, w in enumerate(weights)]
        return LadderPlan(asset, direction, True, rungs,
                          tag(Code.GL_PLANNED,
                              f"{asset} {direction} {n} rungs @ "
                              f"{spacing:.1f}bps spacing"))

    def note_exit(self, asset: str) -> None:
        """Position fully closed / signal gone: drop the armed state so the
        next ladder requires a fresh climb over the ARM bar."""
        self._armed.pop(asset, None)
