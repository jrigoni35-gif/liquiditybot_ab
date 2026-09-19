"""
regime/vol_regime.py

Short/medium-horizon volatility regime classification. Feeds three
consumers:

  * risk/leverage.py       - vol-targeted gross leverage (Moreira-Muir)
  * execution/market_maker - sigma input to the quote-width model
  * risk/position_sizer.py - vol scalar on position size

Estimators: close-to-close realized vol on 5m bars (fast) blended with
the Parkinson high-low range estimator (efficient, robust to sparse
sampling). Regime percentile is computed against the asset's own daily
Parkinson history so "extreme" means extreme *for this asset*, not an
absolute number.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

log = logging.getLogger("liquiditybot.regime.vol")

EPS = 1e-12
BARS_5M_PER_YEAR = 288 * 365
DAYS_PER_YEAR = 365
# Minimum 5m bars before the fast estimate is trusted (VolState.measured).
# config_guard pins informed_flow's V3 sufficiency floor to >= this, so
# every signal-driven entry path is warm-by-construction: no decision
# geometry ever does arithmetic on the placeholder defaults below.
FAST_WARMUP_BARS = 20


@dataclass
class VolState:
    asset: str
    sigma_bar_pct: float = 0.05      # per-5m-bar vol, in % of price
    sigma_daily_pct: float = 2.0     # per-day vol, %
    sigma_annual_pct: float = 60.0   # annualized, %
    percentile: float = 50.0         # vs. own daily history
    label: str = "normal"            # low | normal | elevated | extreme
    # True only once update() has computed the fast estimate from real
    # candles this session. The numeric defaults above are PLACEHOLDERS,
    # not measurements: consumers whose geometry scales off sigma (the
    # exit-floor arm, vol-scaled tiers) must treat measured=False as "no
    # vol feed" (pass None), never do arithmetic on 0.05 — that exact
    # arithmetic armed the give-back ratchet on a 0.18% peak 38s after a
    # restart and exited a restored position (LINK 3ea2a851, 2026-07-28).
    measured: bool = False

    @property
    def sigma_bar_pct_measured(self) -> Optional[float]:
        """sigma_bar_pct, or None while the fast estimate has not yet been
        computed from real candles this session. THE ONE guard against the
        placeholder-default defect (LINK 3ea2a851, 2026-07-28): consumers
        whose geometry scales off per-bar vol must treat an unmeasured
        state as "no vol feed" and take their own designed fallback, never
        do arithmetic on the 0.05 placeholder. Centralizing the guard on
        the producer (instead of at every call site, the old
        main._measured_sigma pattern) makes it impossible to consume the
        placeholder by accident: a raw `sigma_bar_pct` read remains
        available only for paths that genuinely want the default (venue
        formatting, telemetry), and every decision-geometry path routes
        through this property."""
        return self.sigma_bar_pct if self.measured else None


class VolRegimeEngine:
    def __init__(self, config: dict):
        cfg = config or {}
        self.fast_bars = int(cfg.get("fast_lookback_bars_5m", 100))
        self.low_pct = float(cfg.get("low_pct", 30.0))
        self.elevated_pct = float(cfg.get("elevated_pct", 70.0))
        self.extreme_pct = float(cfg.get("extreme_pct", 90.0))
        self._states: dict = {}

    def state(self, asset: str) -> VolState:
        return self._states.get(asset) or VolState(asset=asset)

    @staticmethod
    def _parkinson(highs: np.ndarray, lows: np.ndarray) -> np.ndarray:
        """Per-bar Parkinson VARIANCE estimates (hl^2 / 4ln2), NOT vols.
        Parkinson (1980) defines the estimator in the variance domain;
        averaging per-bar VOLS instead carries an exact deterministic
        bias (E[|hl|]/sqrt(4ln2) = sqrt(8/pi)/sqrt(4ln2) = 0.9584, i.e.
        -4.2% on the leg — 2026-07-29 literature audit). Callers take
        sqrt(mean(...)) — the RMS — to land in vol space."""
        hl = np.log(np.maximum(highs, EPS) / np.maximum(lows, EPS))
        return hl * hl / (4.0 * np.log(2.0))

    def update(self, asset: str, candles_5m: list, candles_daily: list) -> VolState:
        st = self._states.get(asset) or VolState(asset=asset)

        # --- fast estimate from 5m bars ---
        if candles_5m and len(candles_5m) >= FAST_WARMUP_BARS:
            c5 = candles_5m[-self.fast_bars:]
            closes = np.array([c["close"] for c in c5], dtype=float)
            highs = np.array([c["high"] for c in c5], dtype=float)
            lows = np.array([c["low"] for c in c5], dtype=float)
            rets = np.diff(np.log(np.maximum(closes, EPS)))
            cc = float(rets.std())
            # RMS of per-bar Parkinson variances (variance-domain mean,
            # then sqrt) — the estimator's own domain; see _parkinson
            pk = float(np.sqrt(self._parkinson(highs, lows).mean()))
            sigma_bar = 0.5 * cc + 0.5 * pk           # blended per-bar vol
            st.sigma_bar_pct = sigma_bar * 100.0
            st.measured = True
            st.sigma_annual_pct = sigma_bar * np.sqrt(BARS_5M_PER_YEAR) * 100.0
            st.sigma_daily_pct = sigma_bar * np.sqrt(288) * 100.0

        # --- percentile vs. own daily Parkinson history ---
        if candles_daily and len(candles_daily) >= 40:
            dh = np.array([c["high"] for c in candles_daily], dtype=float)
            dl = np.array([c["low"] for c in candles_daily], dtype=float)
            # per-day Parkinson VOLS (sqrt of per-day variances — a single
            # bar per day, so this is the same per-day number as before;
            # only multi-bar AVERAGES needed the RMS correction)
            pv = np.sqrt(self._parkinson(dh, dl))
            # compare the fast (intraday-derived) daily vol to history; if
            # the fast estimate is missing, fall back to the RMS of the
            # last 5 daily bars (variance-domain mean, same correction).
            # Gate on `measured`, not truthiness: the dataclass placeholder
            # sigma_daily_pct=2.0 is truthy, which made this fallback dead
            # code and fabricated the percentile from a constant whenever
            # daily candles were warm before the 5m estimate (2026-07-29
            # unit audit).
            current = st.sigma_daily_pct / 100.0 if st.measured \
                else float(np.sqrt((pv[-5:] ** 2).mean()))
            st.percentile = float((pv < current).mean() * 100.0)

        if st.percentile >= self.extreme_pct:
            st.label = "extreme"
        elif st.percentile >= self.elevated_pct:
            st.label = "elevated"
        elif st.percentile <= self.low_pct:
            st.label = "low"
        else:
            st.label = "normal"

        self._states[asset] = st
        return st
