"""
ml/features.py

Single source of truth for the feature vector. Live inference (meta
model scoring a candidate signal) and offline training (walk-forward on
logged history) both call build_features, so there is no train/serve
skew - the classic way ML trading systems silently die.

Feature families:
price/momentum   - multi-horizon returns normalized by bar vol
volatility       - per-bar vol, daily vol percentile
microstructure   - imbalance, spread, depth, fair-value edge, basis
flow             - volume z-score, funding rate
regime           - macro label one-hots, momentum score, drawdown
cross-asset      - fast corr, corr shift, turbulence percentile
sentiment        - blended influencer/news/crowd score, fear-spike
                     flag (filter inputs only; never *creates* a signal)
context          - crypto Fear&Greed index, BTC-dominance delta
                    (web data), risk-equity z (moomoo basket)
signal           - direction (+1/-1), gate confidence
"""

import math
import time

import numpy as np
from typing import Optional

EPS = 1e-9

FEATURE_NAMES = [
    "ret_1", "ret_6", "ret_12", "ret_48",          # 5m,30m,1h,4h returns / vol
    "sigma_bar_pct", "vol_percentile",
    "imbalance", "spread_bps", "depth_log",
    "fv_edge_bps", "basis_bps",
    "volume_z", "funding_bps",
    "mom_score", "drawdown_pct",
    "regime_bull_quiet", "regime_bull_vol", "regime_range",
    "regime_bear", "regime_crisis",
    "corr_fast", "corr_shift", "turbulence_pct",
    "sent_score", "sent_fear",
    "fear_greed", "dominance_delta", "equity_risk_z",
    "hour_sin", "hour_cos", "weekend",
    "imbalance_delta", "other_ret_6", "depth_ratio",
    "direction", "gate_confidence",
]


def _hour_frac(extras) -> float:
    """UTC time-of-day as a fraction; sin/cos encode the session cycle
    (Asia/EU/US liquidity waves are the strongest intraday seasonality
    crypto has)."""
    tm = time.gmtime((extras or {}).get("ts", time.time()))
    return (tm.tm_hour + tm.tm_min / 60.0) / 24.0


def _ret(closes: np.ndarray, k: int, sigma_bar: float) -> float:
    if len(closes) <= k or closes[-k - 1] <= 0:
        return 0.0
    r = float(np.log(closes[-1] / closes[-k - 1]))
    return float(np.clip(r / (sigma_bar * np.sqrt(k) + EPS), -6, 6))


def build_features(asset: str, direction: str, gate_confidence: float,
                view: dict, fv_state, vol_state, liq_state,
                macro_state, corr_state, sentiment,
                other_asset: Optional[str] = None,
                extras: Optional[dict] = None) -> np.ndarray:
    candles = view.get("candles") or []
    closes = np.array([c["close"] for c in candles], dtype=float) \
        if candles else np.array([0.0])
    vols = np.array([c["volume"] for c in candles], dtype=float) \
        if candles else np.array([0.0])
    sigma_bar = max(vol_state.sigma_bar_pct, 1e-3) / 100.0

    vol_mu = float(vols[-48:].mean()) if len(vols) >= 2 else 0.0
    vol_sd = float(vols[-48:].std()) + EPS
    volume_z = float(np.clip((vols[-1] - vol_mu) / vol_sd, -5, 5)) if len(vols) else 0.0

    imb = view.get("imbalance_ratio", 1.0)
    imb = float(np.clip(np.log(max(imb, 1e-3)), -2, 2))

    regime = macro_state.label
    one_hot = [float(regime == r) for r in
            ("bull_quiet", "bull_volatile", "range", "bear", "crisis")]

    corr_fast, corr_shift = 0.0, 0.0
    if corr_state is not None and other_asset:
        corr_fast = corr_state.corr(asset, other_asset)
        pair = (min(asset, other_asset), max(asset, other_asset))
        corr_shift = corr_state.corr_shift.get(pair, 0.0)
    turb_pct = corr_state.turbulence_pct if corr_state is not None else 50.0

    sent_score = float(getattr(sentiment, "score", 0.0) or 0.0)
    sent_fear = float(bool(getattr(sentiment, "fear_spike", False)))

    x = np.array([
        _ret(closes, 1, sigma_bar), _ret(closes, 6, sigma_bar),
        _ret(closes, 12, sigma_bar), _ret(closes, 48, sigma_bar),
        float(np.clip(vol_state.sigma_bar_pct, 0, 5)),
        vol_state.percentile / 100.0,
        imb,
        float(np.clip(liq_state.spread_bps, 0, 60)) / 10.0,
        float(np.log1p(max(liq_state.depth_top10_usd, 0.0)) / 15.0),
        float(np.clip(fv_state.edge_bps("buy" if direction == "long" else "sell"),
                    -50, 50)) / 10.0,
        float(np.clip(fv_state.basis_bps, -80, 80)) / 10.0,
        volume_z,
        float(np.clip((view.get("funding_rate") or 0.0) * 1e4, -30, 30)) / 10.0,
        macro_state.momentum_score,
        float(np.clip(macro_state.drawdown_pct, 0, 90)) / 100.0,
        *one_hot,
        corr_fast,
        float(np.clip(corr_shift, -1, 1)),
        turb_pct / 100.0,
        float(np.clip(sent_score, -1, 1)),
        sent_fear,
        float(np.clip((extras or {}).get("fear_greed", 50.0), 0, 100)) / 100.0,
        float(np.clip((extras or {}).get("dominance_delta", 0.0), -3, 3)),
        float(np.clip((extras or {}).get("equity_risk_z", 0.0), -4, 4)),
        math.sin(2 * math.pi * _hour_frac(extras)),
        math.cos(2 * math.pi * _hour_frac(extras)),
        float(time.gmtime((extras or {}).get("ts", time.time())).tm_wday >= 5),
        float(np.clip((extras or {}).get("imbalance_delta", 0.0), -2, 2)),
        float(np.clip((extras or {}).get("other_ret_6", 0.0), -3, 3)),
        float(np.clip((extras or {}).get("depth_ratio", 1.0), 0, 3)),
        1.0 if direction == "long" else -1.0,
        float(np.clip(gate_confidence, 0, 1)),
    ], dtype=float)
    if x.shape[0] != len(FEATURE_NAMES):
        raise ValueError(f"feature vector length {x.shape[0]} != "
                        f"{len(FEATURE_NAMES)} (schema mismatch)")
    return x
