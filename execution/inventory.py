"""
execution/inventory.py

Inventory risk management - the discipline layer that stops the book
from "spiking and losing money". Position limits are the single most
enforced rule in every trading competition for a reason: unbounded
inventory converts a pricing edge into directional gambling.

Rules enforced here:
  * Per-asset soft cap  (% of equity): above it, no adds in the same
    direction; profit tiers tighten (signaled via tier_tighten) so the
    position bleeds down on its own.
  * Per-asset hard cap: above it, forced reduction back to the soft cap
    - no discretion, no exceptions.
  * Stale-inventory purge: losers older than max_age_hours with the
    regime against them are cut. Old red inventory is the classic
    slow-death failure mode.
  * inventory_ratio in [-1, 1] feeds the Avellaneda-Stoikov quote skew,
    so quoting itself mean-reverts inventory before caps ever trigger.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("liquiditybot.execution.inventory")

EPS = 1e-9


@dataclass
class DeriskAction:
    position_id: str
    asset: str
    close_pct: float
    reason: str
    urgent: bool = False


@dataclass
class AddDecision:
    allowed: bool
    allowed_usd: float
    reason: str = ""
    tier_tighten: bool = False


class InventoryManager:
    def __init__(self, config: dict):
        cfg = config or {}
        self.soft_cap_pct = float(cfg.get("soft_cap_pct_of_equity", 15.0))
        self.hard_cap_pct = float(cfg.get("hard_cap_pct_of_equity", 25.0))
        self.max_age_hours = float(cfg.get("stale_max_age_hours", 36.0))
        self.stale_loss_pct = float(cfg.get("stale_min_loss_pct", 0.5))

    # ------------------------------------------------------------------
    @staticmethod
    def _asset_of(symbol: str) -> str:
        return symbol.split("/")[0] if "/" in symbol else symbol

    def inventory_usd(self, state, asset: str, marks: dict) -> float:
        """Signed USD exposure in one asset (long positive)."""
        total = 0.0
        for pos in state.open_positions():
            if self._asset_of(pos.symbol) != asset:
                continue
            px = marks.get(pos.symbol) or pos.entry_price
            sgn = 1.0 if pos.direction == "long" else -1.0
            total += sgn * pos.size * px
        return total

    def inventory_ratio(self, state, asset: str, marks: dict, equity: float) -> float:
        """Signed inventory / hard cap, clamped to [-1, 1]. Feeds AS skew."""
        hard_usd = equity * self.hard_cap_pct / 100.0
        if hard_usd <= EPS:
            return 0.0
        r = self.inventory_usd(state, asset, marks) / hard_usd
        return max(-1.0, min(1.0, r))

    # ------------------------------------------------------------------
    def can_add(self, state, asset: str, direction: str, order_usd: float,
                equity: float, marks: dict) -> AddDecision:
        inv = self.inventory_usd(state, asset, marks)
        soft = equity * self.soft_cap_pct / 100.0
        hard = equity * self.hard_cap_pct / 100.0
        sgn = 1.0 if direction == "long" else -1.0
        same_side = inv * sgn > 0

        if same_side and abs(inv) >= soft:
            return AddDecision(False, 0.0,
                            f"inventory {inv:+,.0f} past soft cap {soft:,.0f}",
                            tier_tighten=True)

        # headroom to the hard cap in this direction
        headroom = hard - sgn * inv
        if headroom <= EPS:
            return AddDecision(False, 0.0, "no headroom to hard cap",
                            tier_tighten=True)
        allowed = min(order_usd, headroom)
        # opposite-side adds reduce net inventory - always fine up to cap
        tighten = same_side and (sgn * inv + allowed) >= soft
        return AddDecision(True, allowed, tier_tighten=tighten)

    # ------------------------------------------------------------------
    def derisk_actions(self, state, marks: dict, equity: float,
                    macro_states: dict, now: Optional[float] = None) -> list:
        """Forced reductions: hard-cap breaches and stale losing inventory."""
        now = now if now is not None else time.time()
        actions = []
        hard = equity * self.hard_cap_pct / 100.0
        soft = equity * self.soft_cap_pct / 100.0

        # hard cap breach -> reduce largest positions in the offending asset
        by_asset = {}
        for pos in state.open_positions():
            by_asset.setdefault(self._asset_of(pos.symbol), []).append(pos)
        for asset, positions in by_asset.items():
            inv = self.inventory_usd(state, asset, marks)
            if abs(inv) > hard:
                excess = abs(inv) - soft
                positions.sort(key=lambda p: -(p.size * (marks.get(p.symbol) or p.entry_price)))
                for pos in positions:
                    px = marks.get(pos.symbol) or pos.entry_price
                    sgn = 1.0 if pos.direction == "long" else -1.0
                    if inv * sgn <= 0:      # opposite side, keeps net down
                        continue
                    pos_usd = pos.size * px
                    cut = min(excess, pos_usd)
                    if cut <= EPS:
                        break
                    pct = min(100.0, cut / pos_usd * 100.0)
                    actions.append(DeriskAction(pos.position_id, asset, pct,
                                                f"hard cap breach ({inv:+,.0f} USD)",
                                                urgent=True))
                    excess -= cut

        # stale losing inventory purge
        for pos in state.open_positions():
            if getattr(pos, "is_hedge", False):
                continue
            age_h = (now - pos.opened_at.timestamp()) / 3600.0
            if age_h < self.max_age_hours:
                continue
            px = marks.get(pos.symbol)
            if px is None:
                continue
            pnl_pct = pos.unrealized_pnl_pct(px)
            asset = self._asset_of(pos.symbol)
            macro = macro_states.get(asset)
            regime_against = bool(macro) and macro.is_counter_trend(pos.direction)
            if pnl_pct <= -self.stale_loss_pct and regime_against:
                actions.append(DeriskAction(pos.position_id, asset, 100.0,
                                            f"stale loser {age_h:.0f}h, regime against"))
        return actions
