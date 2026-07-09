"""
execution/hedging.py

Beta-weighted delta hedging within the Kraken universe. When net
portfolio delta (signed USD across all positions) exceeds the cap, the
excess is offset with a position in the *other* asset, sized by the
EWMA beta from regime/correlation.py. Hedge validity is conditional on
correlation: if BTC/ETH correlation decays below the floor, the hedge
is a second bet rather than a hedge and gets unwound.

Hedge positions are tagged is_hedge=True: exempt from profit tiers,
excluded from signal-side inventory, unwound when net delta normalizes
or correlation breaks.
"""

import logging
from dataclasses import dataclass

log = logging.getLogger("liquiditybot.execution.hedging")

EPS = 1e-9


@dataclass
class HedgeAction:
    kind: str          # open | unwind | trim
    asset: str         # asset to trade
    symbol: str        # Kraken symbol, e.g. BTC/USD
    direction: str     # long | short  (for open; for trim: side being reduced)
    usd: float
    position_id: str = ""
    reason: str = ""


class HedgeEngine:
    def __init__(self, config: dict, symbol_map: dict):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", True))
        self.max_net_delta_pct = float(cfg.get("max_net_delta_pct_of_equity", 20.0))
        self.rebalance_band_pct = float(cfg.get("rebalance_band_pct", 8.0))
        self.min_corr = float(cfg.get("min_hedge_correlation", 0.55))
        self.min_hedge_usd = float(cfg.get("min_hedge_usd", 50.0))
        # betas below beta_floor are treated as unreliable -> hedge 1:1;
        # a single hedge never exceeds max_equity_frac of equity.
        # Lifted to config (identical defaults) per overfit discipline.
        self.beta_floor = float(cfg.get("beta_floor", 0.1))
        self.max_equity_frac = float(cfg.get("max_equity_frac", 0.5))
        self.symbol_map = symbol_map   # asset -> Kraken symbol

    @staticmethod
    def _asset_of(symbol: str) -> str:
        return symbol.split("/")[0] if "/" in symbol else symbol

    def net_delta_usd(self, state, marks: dict, include_hedges: bool = True) -> float:
        total = 0.0
        for pos in state.open_positions():
            if not include_hedges and getattr(pos, "is_hedge", False):
                continue
            px = marks.get(pos.symbol) or pos.entry_price
            sgn = 1.0 if pos.direction == "long" else -1.0
            total += sgn * pos.size * px
        return total

    def evaluate(self, state, marks: dict, equity: float, corr_state) -> list:
        if not self.enabled or equity <= EPS:
            return []
        actions = []
        assets = sorted(self.symbol_map)
        if len(assets) < 2:
            return []

        net = self.net_delta_usd(state, marks)
        cap = equity * self.max_net_delta_pct / 100.0
        band = equity * self.rebalance_band_pct / 100.0

        hedges = [p for p in state.open_positions() if getattr(p, "is_hedge", False)]

        # --- unwind conditions ---
        for pos in hedges:
            a, b = self._asset_of(pos.symbol), None
            others = [x for x in assets if x != a]
            b = others[0] if others else a
            corr = abs(corr_state.corr(a, b)) if corr_state else 1.0
            if corr < self.min_corr:
                actions.append(HedgeAction("unwind", a, pos.symbol, pos.direction,
                                           usd=pos.size * (marks.get(pos.symbol) or pos.entry_price),
                                        position_id=pos.position_id,
                                        reason=f"correlation {corr:.2f} below floor"))
            elif abs(net) <= band:
                actions.append(HedgeAction("unwind", a, pos.symbol, pos.direction,
                                           usd=pos.size * (marks.get(pos.symbol) or pos.entry_price),
                                        position_id=pos.position_id,
                                        reason="net delta normalized"))
        if actions:
            return actions

        # --- open condition ---
        if abs(net) <= cap:
            return []
        # exposure concentrated where? hedge with the other asset
        by_asset = {}
        for pos in state.open_positions():
            if getattr(pos, "is_hedge", False):
                continue
            a = self._asset_of(pos.symbol)
            px = marks.get(pos.symbol) or pos.entry_price
            sgn = 1.0 if pos.direction == "long" else -1.0
            by_asset[a] = by_asset.get(a, 0.0) + sgn * pos.size * px
        if not by_asset:
            return []
        exposed = max(by_asset, key=lambda a: abs(by_asset[a]))
        others = [a for a in assets if a != exposed]
        if not others:
            return []
        hedge_asset = others[0]
        excess = abs(net) - band

        # ---- trim-over-hedge: if the book already holds the hedge asset on
        # the side the hedge would offset, opening the offsetting order means
        # carrying long AND short in the same asset - two spreads, two fee
        # legs, zero extra protection. Reducing the existing position moves
        # net delta 1:1 (no beta estimate needed) with half the transactions.
        # Genuine one-sided concentration (hedge asset not held) still gets
        # the beta-weighted hedge below.
        overlap_side = "long" if net > 0 else "short"
        trims, remaining = [], excess
        overlaps = [p for p in state.open_positions()
                    if not getattr(p, "is_hedge", False)
                    and self._asset_of(p.symbol) == hedge_asset
                    and p.direction == overlap_side]
        overlaps.sort(key=lambda p: -(p.size * (marks.get(p.symbol)
                                                or p.entry_price)))
        for pos in overlaps:
            if remaining < self.min_hedge_usd:
                break
            px = marks.get(pos.symbol) or pos.entry_price
            cut = min(remaining, pos.size * px)
            if cut < self.min_hedge_usd:
                continue
            trims.append(HedgeAction(
                "trim", hedge_asset, pos.symbol, pos.direction, usd=cut,
                position_id=pos.position_id,
                reason=f"net delta {net:+,.0f} beyond cap {cap:,.0f}; "
                       f"reducing held {overlap_side} beats opening the "
                       f"offsetting hedge"))
            remaining -= cut
        if trims:
            # one corrective step per cycle: re-evaluate on the reduced book
            # next cycle instead of also opening a hedge against stale marks
            return trims

        corr = abs(corr_state.corr(exposed, hedge_asset)) if corr_state else 0.0
        if corr < self.min_corr:
            log.info(f"hedge skipped: corr({exposed},{hedge_asset})={corr:.2f} < floor")
            return []
        beta = corr_state.beta(exposed, hedge_asset) if corr_state else 1.0
        beta = beta if abs(beta) > self.beta_floor else 1.0
        hedge_usd = min(excess * abs(beta), equity * self.max_equity_frac)
        if hedge_usd < self.min_hedge_usd:
            return []
        direction = "short" if net > 0 else "long"
        actions.append(HedgeAction(
            "open", hedge_asset, self.symbol_map[hedge_asset], direction,
            usd=hedge_usd,
            reason=f"net delta {net:+,.0f} beyond cap {cap:,.0f}, beta={beta:.2f}"))
        return actions
