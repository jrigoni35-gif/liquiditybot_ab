"""
risk/leverage.py

Leverage governor. Gross leverage is *earned* by low volatility, never
taken by default - volatility targeting (Moreira & Muir 2017): the
allowed gross leverage scales with target_vol / realized_vol, and is
then clamped by, in order:

1. region cap        - Kraken permits at most 10x in the user's
                        region; hard ceiling from config, never exceeded
1b. asset cap        - the venue's PER-ASSET cap for the operator's
                        location (2026-10-01, operator: "correlate all
                        assets with the leverage options appropriate for my
                        location"; Alabama, Kraken US margin). A flat
                        region scalar cannot represent a venue whose caps
                        are per asset (PAXG 5x under a 10x scalar). Applied
                        only when the caller names the asset AND the config
                        carries `asset_max_leverage`; an asset absent from
                        that table gets `unlisted_asset_max_leverage`
                        (default 1.0 = spot only: fail closed - an asset the
                        venue does not margin can never be levered by
                        omission). Bounding the BOOK's allowed leverage for
                        an entry in that asset is conservative: no single
                        position can exceed the book allowance.
2. regime playbook   - crisis 1x, bear/range 2x, bull_volatile 3x,
                        bull_quiet up to the vol-target amount
3. margin health     - live: Kraken TradeBalance margin level; scaled
                        down below 200%, entries blocked below 150%
                        (Kraken liquidates around 40%; the buffer is
                        the point)

Exposure headroom converts allowed leverage into the max additional USD
the book can take on right now.
"""

import logging
from dataclasses import dataclass

log = logging.getLogger("liquiditybot.risk.leverage")

EPS = 1e-9


@dataclass
class LeverageDecision:
    allowed_leverage: float
    headroom_usd: float
    margin_level_pct: float
    reasons: list


class LeverageGovernor:
    def __init__(self, config: dict):
        cfg = config or {}
        self.region_cap = float(cfg.get("region_max_leverage", 10.0))
        self.target_vol_annual_pct = float(cfg.get("target_vol_annual_pct", 35.0))
        self.min_leverage = float(cfg.get("min_leverage", 0.25))
        self.margin_scale_below_pct = float(cfg.get("margin_scale_below_pct", 200.0))
        self.margin_block_below_pct = float(cfg.get("margin_block_below_pct", 150.0))
        self.use_margin = bool(cfg.get("use_margin", False))
        raw_caps = cfg.get("asset_max_leverage") or {}
        self.asset_caps = ({str(k).upper(): float(v)
                            for k, v in raw_caps.items()
                            if not str(k).startswith("_")}
                           if isinstance(raw_caps, dict) else {})
        self.unlisted_cap = float(cfg.get("unlisted_asset_max_leverage", 1.0))

    def asset_cap(self, asset: "str | None") -> "float | None":
        """The venue cap for `asset`, or None when no per-asset table is
        configured or no asset was named (legacy behaviour exactly)."""
        if not self.asset_caps or not asset:
            return None
        return self.asset_caps.get(str(asset).upper(), self.unlisted_cap)

    def allowed_leverage(self, sigma_annual_pct: float, regime_cap: float,
                        margin_level_pct: float,
                        asset: "str | None" = None) -> tuple:
        reasons = []
        vol = max(sigma_annual_pct, 5.0)
        lev = self.target_vol_annual_pct / vol
        reasons.append(f"vol-target {self.target_vol_annual_pct:.0f}/{vol:.0f} -> {lev:.2f}x")

        if lev > regime_cap:
            lev = regime_cap
            reasons.append(f"regime cap {regime_cap:.1f}x")
        if lev > self.region_cap:
            lev = self.region_cap
            reasons.append(f"region cap {self.region_cap:.0f}x (Kraken)")
        a_cap = self.asset_cap(asset)
        if a_cap is not None and lev > a_cap:
            lev = a_cap
            reasons.append(f"asset cap {a_cap:g}x ({str(asset).upper()}, "
                           f"venue/location)")

        # dust floor applies to the vol/regime/region ladder ONLY, and must
        # run BEFORE margin health: it is an entry-practicality bound (avoid
        # dust-sized vol-target entries), not a risk floor. Applied after
        # margin scaling it RE-INFLATED a margin-stressed book back up to the
        # floor exactly when the governor was de-risking it (a 155% margin
        # level scaling 2.0x down to 0.20x was bounced back to 0.25x).
        if 0.0 < lev < self.min_leverage:
            lev = self.min_leverage
            reasons.append(f"min-leverage floor {self.min_leverage:.2f}x")

        if not self.use_margin:
            lev = min(lev, 1.0)
            reasons.append("margin disabled: capped at 1x")
        elif margin_level_pct > 0:
            if margin_level_pct < self.margin_block_below_pct:
                lev = 0.0
                reasons.append(f"margin level {margin_level_pct:.0f}% - entries blocked")
            elif margin_level_pct < self.margin_scale_below_pct:
                frac = (margin_level_pct - self.margin_block_below_pct) / \
                    (self.margin_scale_below_pct - self.margin_block_below_pct)
                lev *= max(frac, 0.0)
                reasons.append(f"margin level {margin_level_pct:.0f}% - scaled x{frac:.2f}")

        lev = max(lev, 0.0)
        return lev, reasons

    def decide(self, state, marks: dict, equity: float,
            sigma_annual_pct: float, regime_cap: float,
            margin_level_pct: float = 0.0,
            asset: "str | None" = None) -> LeverageDecision:
        lev, reasons = self.allowed_leverage(sigma_annual_pct, regime_cap,
                                            margin_level_pct, asset=asset)
        gross = 0.0
        for pos in state.open_positions():
            px = marks.get(pos.symbol) or pos.entry_price
            gross += pos.size * px
        headroom = max(equity * lev - gross, 0.0)
        return LeverageDecision(allowed_leverage=lev, headroom_usd=headroom,
                                margin_level_pct=margin_level_pct, reasons=reasons)
