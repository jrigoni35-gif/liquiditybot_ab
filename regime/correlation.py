"""
regime/correlation.py

Cross-asset structure monitoring:

  * EWMA covariance (RiskMetrics lambda) at two speeds. The fast/slow
    correlation gap is the "correlation shift" signal - regime changes
    show up in correlations before they show up in price trends.
  * Hedge betas (cov/var from the fast estimator) consumed by
    execution/hedging.py.
  * Kritzman-Li (2010) financial turbulence index: Mahalanobis distance
    of today's cross-asset return vector from its historical
    distribution. Turbulence spikes are an early crisis tell and feed
    the macro engine's crisis overlay.
"""

import logging
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np

log = logging.getLogger("liquiditybot.regime.correlation")

EPS = 1e-12


@dataclass
class CorrState:
    corr_fast: dict = field(default_factory=dict)    # (a,b) -> rho
    corr_slow: dict = field(default_factory=dict)
    corr_shift: dict = field(default_factory=dict)   # fast - slow
    betas: dict = field(default_factory=dict)        # (a,b) -> beta of a on b
    turbulence: float = 0.0
    turbulence_pct: float = 50.0
    shifted: bool = False                            # any |shift| beyond threshold

    def corr(self, a: str, b: str) -> float:
        return self.corr_fast.get((a, b), self.corr_fast.get((b, a), 0.0))

    def beta(self, a: str, b: str) -> float:
        return self.betas.get((a, b), 0.0)


class _EwmaCov:
    def __init__(self, lam: float):
        self.lam = lam
        self.mean: dict = {}
        self.cov: dict = {}

    def update(self, rets: dict):
        assets = sorted(rets)
        for a in assets:
            m = self.mean.get(a, rets[a])
            self.mean[a] = self.lam * m + (1 - self.lam) * rets[a]
        for a in assets:
            for b in assets:
                da = rets[a] - self.mean[a]
                db = rets[b] - self.mean[b]
                c = self.cov.get((a, b), da * db)
                self.cov[(a, b)] = self.lam * c + (1 - self.lam) * da * db

    def corr(self, a: str, b: str) -> float:
        va = self.cov.get((a, a), 0.0)
        vb = self.cov.get((b, b), 0.0)
        if va <= EPS or vb <= EPS:
            return 0.0
        return float(np.clip(self.cov.get((a, b), 0.0) / np.sqrt(va * vb), -1, 1))

    def beta(self, a: str, b: str) -> float:
        vb = self.cov.get((b, b), 0.0)
        if vb <= EPS:
            return 0.0
        return float(self.cov.get((a, b), 0.0) / vb)


class CorrelationEngine:
    def __init__(self, config: dict):
        cfg = config or {}
        self.fast = _EwmaCov(float(cfg.get("lambda_fast", 0.94)))
        self.slow = _EwmaCov(float(cfg.get("lambda_slow", 0.997)))
        self.shift_threshold = float(cfg.get("shift_threshold", 0.25))
        self.turb_lookback = int(cfg.get("turbulence_lookback_days", 250))
        self._last_close: dict = {}
        self.state = CorrState()

    # --- per-cycle intraday returns (5m cadence) -----------------------
    def update_intraday(self, closes: dict) -> CorrState:
        rets = {}
        for asset, px in closes.items():
            last = self._last_close.get(asset)
            self._last_close[asset] = px
            if last and last > 0 and px > 0:
                rets[asset] = float(np.log(px / last))
        if len(rets) >= 2:
            self.fast.update(rets)
            self.slow.update(rets)
            st = self.state
            st.corr_fast.clear()
            st.corr_slow.clear()
            st.corr_shift.clear()
            st.betas.clear()
            assets = sorted(rets)
            for a, b in combinations(assets, 2):
                cf, cs = self.fast.corr(a, b), self.slow.corr(a, b)
                st.corr_fast[(a, b)] = cf
                st.corr_slow[(a, b)] = cs
                st.corr_shift[(a, b)] = cf - cs
            for a in assets:
                for b in assets:
                    if a != b:
                        st.betas[(a, b)] = self.fast.beta(a, b)
            st.shifted = any(abs(v) >= self.shift_threshold
                            for v in st.corr_shift.values())
            if st.shifted:
                log.info(f"correlation shift detected: {st.corr_shift}")
        return self.state

    # --- daily turbulence (Kritzman-Li) --------------------------------
    def update_turbulence(self, daily_candles_by_asset: dict) -> CorrState:
        """daily_candles_by_asset: asset -> list of daily candle dicts."""
        assets = sorted(a for a, c in daily_candles_by_asset.items()
                        if c and len(c) >= 60)
        if len(assets) < 2:
            return self.state
        n = min(len(daily_candles_by_asset[a]) for a in assets)
        n = min(n, self.turb_lookback + 1)
        R = np.column_stack([
            np.diff(np.log(np.maximum(
                np.array([c["close"] for c in daily_candles_by_asset[a][-n:]],
                        dtype=float), EPS)))
            for a in assets
        ])                                            # (n-1, A)
        if R.shape[0] < 40:
            return self.state
        mu = R.mean(axis=0)
        cov = np.cov(R, rowvar=False)
        cov += np.eye(cov.shape[0]) * (np.trace(cov) / cov.shape[0]) * 0.05  # shrink
        try:
            inv = np.linalg.inv(cov)
        except np.linalg.LinAlgError:
            inv = np.linalg.pinv(cov)
        d = np.einsum("ij,jk,ik->i", R - mu, inv, R - mu)  # Mahalanobis^2 series
        self.state.turbulence = float(d[-1])
        self.state.turbulence_pct = float((d < d[-1]).mean() * 100.0)
        if self.state.turbulence_pct >= 95:
            log.warning(f"turbulence spike: {self.state.turbulence:.1f} "
                        f"(p{self.state.turbulence_pct:.0f})")
        return self.state
