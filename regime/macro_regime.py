"""
regime/macro_regime.py

Detects 1-6 month macro regimes early and maps them to trade-logic
adjustments ("playbooks") derived from published, battle-tested quant
models rather than ad-hoc rules:

  * Hamilton (1989) Markov regime switching  -> Gaussian HMM over daily
    returns + volatility, implemented in pure numpy (scaled Baum-Welch EM;
    the state is read off the POSTERIOR MARGINAL at the last bar via
    `posteriors()` + argmax, NOT a Viterbi path decode - this docstring
    claimed "+ Viterbi" until 2026-09-09 and no Viterbi has ever existed in
    this module; the claim is struck rather than implemented, because
    switching to a path decode would change labels, which changes playbooks,
    which is COHORT-RESETTING). States are relabeled each fit by their
    return/vol profile so "bull"/"bear"/"range" are stable semantic labels,
    not raw indices.

    The fitted transition matrix `GaussianHMM.A` is the Markov chain itself.
    Nothing in the decision path reads it; `scripts/regime_chain_report.py`
    (SAFE, report-only) surfaces it - dwell times, steady state, and the
    chain-implied vs realized occupancy gap.
  * Time-series momentum (Moskowitz, Ooi, Pedersen 2012) -> 1m/3m/6m
    lookback trend votes. This is the "use past cycles" logic: TSMOM's
    documented edge is precisely that the past 1-12 month cycle predicts
    the next leg.
  * Volatility-managed sizing (Moreira & Muir 2017) -> vol percentile
    feeds the playbook size/leverage caps (consumed by risk/leverage.py).

Label switching uses hysteresis (N consecutive confirmations) so the bot
doesn't flip playbooks on one noisy day - early but not jumpy.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

log = logging.getLogger("liquiditybot.regime.macro")

EPS = 1e-9

REGIME_LABELS = ("bull_quiet", "bull_volatile", "range", "bear", "crisis")

# Default playbooks. Overridable via config["regime"]["playbooks"].
# size_mult scales position size; leverage_cap is consumed by LeverageGovernor;
# tier_scale multiplies profit-tier triggers (>1 = let winners run);
# stop_mult widens/tightens the protective stop; direction_bias gates entries.
DEFAULT_PLAYBOOKS = {
    "bull_quiet":    {"direction_bias": "long",  "size_mult": 1.00, "leverage_cap": 10.0,
                    "tier_scale": 1.25, "stop_mult": 1.00, "allow_new": True,
                    "counter_trend_conf_bonus": 0.15},
    "bull_volatile": {"direction_bias": "long",  "size_mult": 0.60, "leverage_cap": 3.0,
                    "tier_scale": 0.80, "stop_mult": 1.30, "allow_new": True,
                    "counter_trend_conf_bonus": 0.10},
    "range":         {"direction_bias": "both",  "size_mult": 0.70, "leverage_cap": 2.0,
                    "tier_scale": 0.70, "stop_mult": 0.90, "allow_new": True,
                    "counter_trend_conf_bonus": 0.00},
    "bear":          {"direction_bias": "short", "size_mult": 0.70, "leverage_cap": 2.0,
                    "tier_scale": 0.85, "stop_mult": 1.15, "allow_new": True,
                    "counter_trend_conf_bonus": 0.15},
    "crisis":        {"direction_bias": "none",  "size_mult": 0.30, "leverage_cap": 1.0,
                    "tier_scale": 0.60, "stop_mult": 1.50, "allow_new": False,
                    "counter_trend_conf_bonus": 0.25},
}


@dataclass
class MacroRegimeState:
    asset: str
    label: str = "range"
    hmm_label: str = "range"           # raw HMM vote before ensemble/hysteresis
    state_probs: dict = field(default_factory=dict)
    momentum_score: float = 0.0        # [-1, 1] TSMOM vote
    momentum_z: float = 0.0            # vol-scaled trend strength
    drawdown_pct: float = 0.0          # from trailing 180d high
    vol_percentile: float = 50.0       # daily Parkinson vol percentile
    playbook: dict = field(default_factory=lambda: dict(DEFAULT_PLAYBOOKS["range"]))
    fitted: bool = False
    bars_used: int = 0

    def allows_direction(self, direction: str) -> bool:
        bias = self.playbook.get("direction_bias", "both")
        if bias == "none":
            return False
        if bias == "both":
            return True
        return direction == bias

    def is_counter_trend(self, direction: str) -> bool:
        bias = self.playbook.get("direction_bias", "both")
        return bias in ("long", "short") and direction != bias


class GaussianHMM:
    """Diagonal-covariance Gaussian HMM fit with scaled Baum-Welch EM.

    Small, dependency-free implementation sized for daily crypto data
    (a few hundred to a couple thousand observations, 2-4 states).
    """

    def __init__(self, n_states: int = 3, n_iter: int = 80, tol: float = 1e-5,
                seed: int = 7, sticky: float = 0.95, restarts: int = 3):
        self.K = n_states
        self.n_iter = n_iter
        self.tol = tol
        self.seed = seed
        self.sticky = sticky
        self.restarts = restarts
        self.pi = None
        self.A = None
        self.means_ = None
        self.vars_ = None
        self._mu = None   # feature standardization
        self._sd = None
        self.loglik_ = -np.inf

    # ---- internals -----------------------------------------------------
    def _log_emissions(self, X: np.ndarray) -> np.ndarray:
        T, D = X.shape
        assert self.means_ is not None and self.vars_ is not None  # model is fitted
        logB = np.empty((T, self.K))
        for k in range(self.K):
            var = self.vars_[k]
            diff = X - self.means_[k]
            logB[:, k] = -0.5 * (np.sum(diff * diff / var, axis=1)
                                 + np.sum(np.log(2.0 * np.pi * var)))
        return logB

    def _forward_backward(self, logB: np.ndarray):
        T = logB.shape[0]
        # per-row max subtraction keeps exp() in range; absorbed by scaling c
        m = logB.max(axis=1, keepdims=True)
        B = np.exp(logB - m)

        alpha = np.empty((T, self.K))
        c = np.empty(T)
        alpha[0] = self.pi * B[0]
        c[0] = alpha[0].sum() + EPS
        alpha[0] /= c[0]
        for t in range(1, T):
            alpha[t] = (alpha[t - 1] @ self.A) * B[t]
            c[t] = alpha[t].sum() + EPS
            alpha[t] /= c[t]

        beta = np.empty((T, self.K))
        beta[-1] = 1.0
        for t in range(T - 2, -1, -1):
            beta[t] = (self.A @ (B[t + 1] * beta[t + 1])) / c[t + 1]

        gamma = alpha * beta
        gamma /= gamma.sum(axis=1, keepdims=True) + EPS

        # xi accumulated (K,K) rather than stored (T,K,K)
        xi_sum = np.zeros((self.K, self.K))
        for t in range(T - 1):
            xi = (alpha[t][:, None] * self.A) * (B[t + 1] * beta[t + 1])[None, :]
            s = xi.sum() + EPS
            xi_sum += xi / s

        loglik = float(np.sum(np.log(c)) + np.sum(m))
        return gamma, xi_sum, loglik

    def _init_params(self, X: np.ndarray, rng: np.random.Generator):
        T, D = X.shape
        # seed means by quantile bands of feature 0 (returns) + jitter
        qs = np.quantile(X[:, 0], np.linspace(0.15, 0.85, self.K))
        means = np.zeros((self.K, D))
        means[:, 0] = qs
        for d in range(1, D):
            means[:, d] = np.quantile(X[:, d], np.linspace(0.3, 0.7, self.K))
        means += rng.normal(0, 0.05, means.shape)
        var0 = X.var(axis=0) + 1e-3
        self.means_ = means
        self.vars_ = np.tile(var0, (self.K, 1))
        self.pi = np.full(self.K, 1.0 / self.K)
        A = np.full((self.K, self.K), (1.0 - self.sticky) / max(self.K - 1, 1))
        np.fill_diagonal(A, self.sticky)
        self.A = A

    def fit(self, X_raw: np.ndarray) -> bool:
        X_raw = np.asarray(X_raw, dtype=float)
        if X_raw.ndim != 2 or X_raw.shape[0] < 8 * self.K:
            return False
        self._mu = X_raw.mean(axis=0)
        self._sd = X_raw.std(axis=0) + EPS
        X = (X_raw - self._mu) / self._sd

        best = None
        for r in range(self.restarts):
            rng = np.random.default_rng(self.seed + r)
            self._init_params(X, rng)
            prev = -np.inf
            for _ in range(self.n_iter):
                logB = self._log_emissions(X)
                gamma, xi_sum, ll = self._forward_backward(logB)
                # M-step
                self.pi = gamma[0] + EPS
                self.pi /= self.pi.sum()
                denom = gamma[:-1].sum(axis=0)[:, None] + EPS
                self.A = xi_sum / denom
                self.A = np.clip(self.A, 1e-6, None)
                self.A /= self.A.sum(axis=1, keepdims=True)
                w = gamma.sum(axis=0)[:, None] + EPS
                self.means_ = (gamma.T @ X) / w
                assert self.vars_ is not None  # seeded by _init_params
                for k in range(self.K):
                    diff = X - self.means_[k]
                    self.vars_[k] = (gamma[:, k][:, None] * diff * diff).sum(axis=0) / w[k]
                self.vars_ = np.maximum(self.vars_, 1e-6)
                if abs(ll - prev) < self.tol * max(1.0, abs(prev)):
                    prev = ll
                    break
                prev = ll
            assert (self.pi is not None and self.A is not None
                    and self.means_ is not None and self.vars_ is not None)
            if best is None or prev > best[0]:
                best = (prev, self.pi.copy(), self.A.copy(),
                        self.means_.copy(), self.vars_.copy())
        assert best is not None  # restarts >= 1 always sets best on the first pass
        self.loglik_, self.pi, self.A, self.means_, self.vars_ = best
        return True

    def posteriors(self, X_raw: np.ndarray) -> np.ndarray:
        assert self._mu is not None and self._sd is not None  # model is fitted
        X = (np.asarray(X_raw, dtype=float) - self._mu) / self._sd
        logB = self._log_emissions(X)
        gamma, _, _ = self._forward_backward(logB)
        return gamma

    def state_return_means(self) -> np.ndarray:
        """Per-state mean of feature 0 (daily return), de-standardized."""
        assert (self.means_ is not None and self._sd is not None
                and self._mu is not None)  # model is fitted
        return self.means_[:, 0] * self._sd[0] + self._mu[0]

    def state_vol_means(self) -> np.ndarray:
        """Per-state mean of feature 1 (log vol), de-standardized."""
        assert (self.means_ is not None and self._sd is not None
                and self._mu is not None)  # model is fitted
        return self.means_[:, 1] * self._sd[1] + self._mu[1]


def parkinson_vol(highs: np.ndarray, lows: np.ndarray) -> np.ndarray:
    """Per-bar Parkinson volatility estimate (same units as returns)."""
    hl = np.log(np.maximum(highs, EPS) / np.maximum(lows, EPS))
    return np.sqrt(hl * hl / (4.0 * np.log(2.0)))


# --- TSMOM score lattice ------------------------------------------------
# The TSMOM score is mean(sign(r_lb)) over n lookbacks, so it is NOT a
# continuum: it can only take the n+1 values (n-2j)/n. A threshold is a
# CUT on that lattice, and its meaning is entirely "how many lookbacks
# must agree" - a value that lands beside a lattice point rather than
# between two of them silently encodes a different vote count than the
# one it documents. That is exactly how momentum_bear_max=-0.34 came to
# demand UNANIMITY (-1/3 = -0.3333... > -0.34, so the 2-of-3 level fails
# the `score <= thr` test) while its own comment claimed "at least 2 of
# 3 agree" - and, because momentum_bull_min=0.67 already meant 3-of-3,
# it INVERTED the intended asymmetry: bear needed 3/3 *and* a >=20%
# drawdown where bull needed only 3/3.
def tsmom_lattice(n_lookbacks: int) -> list:
    """Every value mean(sign) can take over n votes: +1 .. -1, step 2/n."""
    n = max(int(n_lookbacks), 1)
    return [(n - 2 * j) / n for j in range(n + 1)]


def tsmom_threshold_conflict(threshold: float, n_lookbacks: int):
    """The lattice point `threshold` is too close to, or None if it is safe.

    "Too close" is within 1/(2n) - half of the half-step. Inside that band
    the cut is decided by which side of a representable value the constant
    happens to fall, i.e. by rounding, not by design. Guard shape mirrors
    core/config_guard.py's FATAL checks; kept here because the engine is
    also constructed directly (tests, replay) with no config pass.
    """
    n = max(int(n_lookbacks), 1)
    lat = tsmom_lattice(n)
    near = min(lat, key=lambda v: abs(v - threshold))
    return near if abs(near - threshold) <= 1.0 / (2 * n) else None


class MacroRegimeEngine:
    def __init__(self, config: dict):
        cfg = config or {}
        self.n_states = int(cfg.get("hmm_states", 3))
        self.min_bars = int(cfg.get("min_daily_bars", 120))
        self.hysteresis = int(cfg.get("hysteresis_confirms", 2))
        self.mom_lookbacks = cfg.get("momentum_lookbacks_days", [21, 63, 126])
        self.dd_lookback = int(cfg.get("drawdown_lookback_days", 180))
        self.vol_hi_pct = float(cfg.get("bull_volatile_vol_pct", 70.0))
        self.crisis_vol_pct = float(cfg.get("crisis_vol_pct", 95.0))
        self.bear_dd_pct = float(cfg.get("bear_drawdown_pct", 20.0))
        # TSMOM cuts on the score lattice (see tsmom_lattice above). With
        # the shipped 3 lookbacks the score lives on {-1, -1/3, +1/3, +1}:
        #   bear  score <= -0.10  -> -1/3 and -1 pass = "at least 2 of 3 agree"
        #   bull  score >= +0.67  -> only +1 passes   = "all 3 agree"
        # i.e. the documented asymmetry - a bear thesis is cheaper to reach
        # than a bull one (it still needs a >=20% drawdown alongside), which
        # the old -0.34 default inverted by sitting 0.0067 BELOW the -1/3
        # level it was meant to admit. Both are config knobs per overfit
        # discipline; the lattice guard below rejects a re-introduction.
        k_lb = max(len(self.mom_lookbacks), 1)
        self.mom_bear_max = self._lattice_safe(
            float(cfg.get("momentum_bear_max", -0.10)), k_lb,
            "momentum_bear_max", inclusive_below=True)
        self.mom_bull_min = self._lattice_safe(
            float(cfg.get("momentum_bull_min", 0.67)), k_lb,
            "momentum_bull_min", inclusive_below=False)
        playbooks = dict(DEFAULT_PLAYBOOKS)
        for name, pb in (cfg.get("playbooks") or {}).items():
            if name in playbooks:
                merged = dict(playbooks[name])
                merged.update(pb)
                playbooks[name] = merged
        self.playbooks = playbooks

        self._hmm: dict = {}                 # asset -> GaussianHMM
        self._states: dict = {}              # asset -> MacroRegimeState
        self._pending: dict = {}             # asset -> (candidate_label, count)

    @staticmethod
    def _lattice_safe(threshold: float, n_lookbacks: int, name: str,
                    inclusive_below: bool) -> float:
        """Repair a TSMOM threshold that the score lattice cannot express,
        and say so loudly.

        A threshold placed BESIDE a lattice point was placed there to include
        that point - it is the only reason to write -0.34 instead of -0.5. So
        the repair keeps that point selected and moves the cut into the
        interior of its gap (a third of a step, comfortably outside the
        1/(2n) band on both sides). Repair rather than raise: startup FATALs
        belong to core/config_guard.py and a shipped config must not take the
        runner down mid-session - but it must not silently keep running an
        inverted rule either, so this is an ERROR-level line every boot.
        """
        near = tsmom_threshold_conflict(threshold, n_lookbacks)
        if near is None:
            return threshold
        n = max(int(n_lookbacks), 1)
        step = 2.0 / n
        # clamp keeps the sign contract config_guard enforces (bear cuts are
        # negative, bull cuts positive) without re-entering the tolerance band
        if inclusive_below:                       # applied as `score <= thr`
            fixed = min(near + step / 3.0, -1.0 / (4 * n))
        else:                                     # applied as `score >= thr`
            fixed = max(near - step / 3.0, 1.0 / (4 * n))
        log.error(
            "regime.%s=%.4f sits within %.4f of the achievable TSMOM level "
            "%+.4f (%d lookbacks): the cut is decided by rounding, not by "
            "design, and encodes a different vote count than it documents. "
            "Using %+.4f (same lookbacks selected, lattice-safe) - fix the "
            "config value.", name, threshold, 1.0 / (2 * n), near, n, fixed)
        return fixed

    def state(self, asset: str) -> MacroRegimeState:
        return self._states.get(asset) or MacroRegimeState(asset=asset)

    # ------------------------------------------------------------------
    def update(self, asset: str, daily_candles: list,
            turbulence_pct: Optional[float] = None) -> MacroRegimeState:
        """Refit/refresh the macro regime from daily OHLCV candles.

        Call on a slow cadence (hourly is plenty; the signal moves daily).
        turbulence_pct: optional cross-asset turbulence percentile from
        regime/correlation.py - spikes force the crisis overlay early.
        """
        st = self._states.get(asset) or MacroRegimeState(asset=asset)
        candles = daily_candles or []
        n = len(candles)
        st.bars_used = n
        if n < max(30, min(self.mom_lookbacks) + 2):
            self._states[asset] = st
            return st

        closes = np.array([c["close"] for c in candles], dtype=float)
        highs = np.array([c["high"] for c in candles], dtype=float)
        lows = np.array([c["low"] for c in candles], dtype=float)
        rets = np.diff(np.log(np.maximum(closes, EPS)))
        pvol = parkinson_vol(highs, lows)[1:]

        # --- TSMOM votes (Moskowitz-Ooi-Pedersen) ---
        votes, zmags = [], []
        daily_sd = float(rets[-126:].std() + EPS)
        for lb in self.mom_lookbacks:
            if len(rets) >= lb:
                r = float(rets[-lb:].sum())
                votes.append(np.sign(r))
                zmags.append(r / (daily_sd * np.sqrt(lb)))
        st.momentum_score = float(np.mean(votes)) if votes else 0.0
        st.momentum_z = float(np.tanh(np.mean(zmags))) if zmags else 0.0

        # --- drawdown from trailing high ---
        window = closes[-self.dd_lookback:]
        st.drawdown_pct = float((window.max() - closes[-1]) / (window.max() + EPS) * 100)

        # --- vol percentile (daily Parkinson, smoothed 5d) ---
        recent_vol = float(pvol[-5:].mean())
        st.vol_percentile = float((pvol < recent_vol).mean() * 100)

        # --- HMM fit (Hamilton regime switching) ---
        hmm_label = "range"
        if n >= self.min_bars:
            X = np.column_stack([rets, np.log(pvol + EPS)])
            hmm = self._hmm.get(asset) or GaussianHMM(n_states=self.n_states)
            if hmm.fit(X):
                self._hmm[asset] = hmm
                gamma = hmm.posteriors(X)
                cur = gamma[-1]
                order = np.argsort(hmm.state_return_means())   # low -> high mean ret
                sem = {int(order[0]): "bear", int(order[-1]): "bull"}
                for k in range(self.n_states):
                    sem.setdefault(k, "range")
                st.state_probs = {sem[k]: round(float(cur[k]), 4)
                                for k in range(self.n_states)}
                # merge duplicate semantic keys (K>3) by max prob
                probs = {}
                for k in range(self.n_states):
                    key = sem[k]
                    probs[key] = max(probs.get(key, 0.0), float(cur[k]))
                hmm_label = max(probs, key=lambda k: probs[k])
                st.fitted = True
        st.hmm_label = hmm_label

        # --- ensemble -> semantic label ---
        raw = self._ensemble_label(st, turbulence_pct)

        # --- hysteresis: require N consecutive confirmations to switch ---
        if raw != st.label:
            cand, cnt = self._pending.get(asset, (raw, 0))
            cnt = cnt + 1 if cand == raw else 1
            self._pending[asset] = (raw, cnt)
            # crisis is allowed to engage immediately - that's the point
            if cnt >= self.hysteresis or raw == "crisis":
                st.label = raw
                self._pending[asset] = (raw, 0)
        else:
            self._pending[asset] = (raw, 0)

        st.playbook = dict(self.playbooks.get(st.label, DEFAULT_PLAYBOOKS["range"]))
        self._states[asset] = st
        log.info(
            f"[{asset}] macro={st.label} hmm={st.hmm_label} mom={st.momentum_score:+.2f} "
            f"dd={st.drawdown_pct:.1f}% volpct={st.vol_percentile:.0f}"
        )
        return st

    def _ensemble_label(self, st: MacroRegimeState,
                        turbulence_pct: Optional[float]) -> str:
        # Crisis overlay: extreme vol or cross-asset turbulence trumps everything.
        if st.vol_percentile >= self.crisis_vol_pct or \
        (turbulence_pct is not None and turbulence_pct >= self.crisis_vol_pct):
            return "crisis"
        bearish = (st.hmm_label == "bear") or \
                (st.momentum_score <= self.mom_bear_max and
                 st.drawdown_pct >= self.bear_dd_pct)
        bullish = (st.hmm_label == "bull" and st.momentum_score >= 0.0) or \
                (st.momentum_score >= self.mom_bull_min and
                 st.hmm_label != "bear")
        if bearish and not bullish:
            return "bear"
        if bullish:
            return "bull_volatile" if st.vol_percentile >= self.vol_hi_pct else "bull_quiet"
        return "range"
