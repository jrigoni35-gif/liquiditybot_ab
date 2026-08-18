"""
execution/market_maker.py — rev 2.0 (Assurance Build)

Avellaneda-Stoikov quote engine, hardened and made structurally
profitable-or-silent:

  STRUCTURAL FEE FLOOR (QT-010). Rev 1 floored the half spread at a
  config minimum that could sit BELOW round-trip economics. Rev 2
  enforces  half_spread >= maker_fee + min_profit_bps  as an invariant:
  a passive fill at our own quote can never be net-negative by
  construction. If the config minimum is below that floor, the floor
  wins and the event is logged once.

  DIMENSIONAL HYGIENE. sigma enters as per-bar fraction of price and
  tau in bars; the vol term is 0.5*gamma*sigma*sqrt(tau) — diffusion
  scaling over the quote horizon (sigma*sqrt(tau) = expected |move|
  over tau bars, gamma-weighted). The 2026-07-29 unit audit found this
  docstring previously claimed gamma*sigma^2*tau/sigma = gamma*sigma*tau
  (linear in tau) while the code shipped sqrt(tau); the CODE is the
  contract — sqrt(tau) is the deliberate choice (quote width tracks the
  diffusion envelope, not linear time), and the doc now matches it. The
  intensity term ln(1+gamma/k)/gamma * sigma is a pure fraction too.
  LITERATURE MAPPING (2026-07-29 audit, citations verified): the
  linear-sigma overall form (not A-S 2008's gamma*sigma^2*(T-t)) is the
  Gueant-Lehalle-Fernandez-Tapia 2013 STATIONARY normalization — the
  peer-reviewed form for perpetual quoting, where raw A-S collapses to
  the fee floor as T-t -> 0. Multiplying the intensity term by sigma is
  not in either paper: it re-parameterizes the fill-decay constant
  kappa_AS = k/sigma (distance measured in sigma units — the same
  nondimensionalization pretrade's p_fill uses), and as sigma -> 0 the
  structural fee floor below binds, so the term is fail-safe.
  All inputs validated finite; garbage in -> quote at maximum-width
  posture around the last sane value rather than a NaN quote.

  BOUNDED SKEW. Inventory skew is clamped so the reservation price can
  never cross its own quote (bid <= reservation <= ask always holds),
  and the skew cannot exceed the half spread — inventory pressure
  widens the passive side, it never creates a crossed self-quote.

Public surface unchanged: AvellanedaStoikovQuoter(config).quote(
fair_value, sigma_bar_pct, inventory_ratio, liq_label, fee_bps) ->
Quote(reservation, bid, ask, half_spread_bps, skew_bps).
"""

import logging
import math
from dataclasses import dataclass

import numpy as np

from core.codes import Code, tag

log = logging.getLogger("liquiditybot.execution.market_maker")


@dataclass
class Quote:
    reservation: float
    bid: float
    ask: float
    half_spread_bps: float
    skew_bps: float


class AvellanedaStoikovQuoter:
    def __init__(self, config: dict):
        cfg = config or {}
        self.gamma = max(float(cfg.get("gamma", 0.8)), 1e-3)
        self.k_intensity = max(float(cfg.get("k_intensity", 1.5)), 1e-3)
        self.tau_bars = max(float(cfg.get("tau_bars", 6.0)), 0.1)
        self.min_half_spread_bps = max(float(
            cfg.get("min_half_spread_bps", 26.0)), 0.0)
        self.max_half_spread_bps = max(float(
            cfg.get("max_half_spread_bps", 60.0)), self.min_half_spread_bps)
        # structural profitability floor: a passive round trip must clear
        # fees plus this margin, or the quote is not worth resting
        self.min_profit_bps = max(float(cfg.get("min_profit_bps", 1.0)), 0.0)
        self.liq_mults = {"liquid": 1.0, "thin": 1.5, "spoofy": 2.5}
        self.liq_mults.update(cfg.get("liquidity_spread_mults", {}) or {})
        self._floor_logged = False

    # ------------------------------------------------------------------
    def quote(self, fair_value: float, sigma_bar_pct: float,
              inventory_ratio: float, liq_label: str = "liquid",
              fee_bps: float = 16.0) -> Quote:
        """fair_value from FairValueEngine; sigma_bar_pct per-bar vol in
        % of price; inventory_ratio signed inventory / hard cap in
        [-1, 1]. Output invariants: bid <= reservation <= ask, and
        half_spread_bps >= fee_bps + min_profit_bps."""
        # ---- input validation: never emit a NaN quote ------------------
        if not (isinstance(fair_value, (int, float))
                and math.isfinite(fair_value) and fair_value > 0):
            log.error("quoter: invalid fair_value %r — refusing to quote",
                      fair_value)
            return Quote(0.0, 0.0, 0.0, self.max_half_spread_bps, 0.0)
        sigma_bar_pct = sigma_bar_pct if (
            isinstance(sigma_bar_pct, (int, float))
            and math.isfinite(sigma_bar_pct) and sigma_bar_pct > 0) else 0.05
        fee_bps = fee_bps if (isinstance(fee_bps, (int, float))
                              and math.isfinite(fee_bps)
                              and fee_bps >= 0) else 25.0
        q = float(np.clip(inventory_ratio if (
            isinstance(inventory_ratio, (int, float))
            and math.isfinite(inventory_ratio)) else 0.0, -1.0, 1.0))

        sigma = max(sigma_bar_pct, 1e-4) / 100.0     # fraction of price

        # ---- half spread ------------------------------------------------
        vol_term = 0.5 * self.gamma * sigma * math.sqrt(self.tau_bars)
        intensity_term = math.log(1.0 + self.gamma / self.k_intensity) \
            / self.gamma
        half_frac = vol_term + intensity_term * sigma
        half_bps = half_frac * 1e4 + fee_bps
        half_bps *= self.liq_mults.get(liq_label, 1.0)

        # QT-010: structural profitability floor beats the config minimum
        fee_floor = fee_bps + self.min_profit_bps
        lo = max(self.min_half_spread_bps, fee_floor)
        if lo > self.min_half_spread_bps and not self._floor_logged:
            log.warning(tag(
                Code.QT_FEE_FLOOR,
                f"config min_half_spread_bps={self.min_half_spread_bps:.1f} "
                f"is inside the round trip (fee {fee_bps:.1f} + margin "
                f"{self.min_profit_bps:.1f}) — structural floor {lo:.1f}bps "
                f"enforced"))
            self._floor_logged = True
        half_bps = float(np.clip(half_bps, lo, max(self.max_half_spread_bps,
                                                   lo)))

        # ---- reservation skew (bounded to the half spread) ---------------
        skew_frac = q * self.gamma * sigma * math.sqrt(self.tau_bars)
        max_skew_frac = 0.9 * half_bps / 1e4
        skew_frac = float(np.clip(skew_frac, -max_skew_frac, max_skew_frac))
        reservation = fair_value * (1.0 - skew_frac)

        half = half_bps / 1e4
        return Quote(
            reservation=reservation,
            bid=reservation * (1.0 - half),
            ask=reservation * (1.0 + half),
            half_spread_bps=half_bps,
            skew_bps=skew_frac * 1e4,
        )
