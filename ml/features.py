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
smc              - Smart Money Concepts structural context
                    (strategies/smc.py, docs/SMC.md): multi-timeframe
                    trend alignment, premium/discount zone, liquidity-
                    pocket pull, fair-value-gap pull + confluence,
                    volume-profile POC/Value-Area position
signal           - direction (+1/-1), gate confidence
"""

import math
import time

import numpy as np
from typing import Optional

EPS = 1e-9

# documented neutrals for schema migration (scripts/migrate_history.py):
# 0.0 = "no formation present", the exact value _candle_patterns returns
# when the shape is absent - padded old rows are indistinguishable from
# genuinely patternless bars.
PATTERN_NEUTRAL = {"pat_engulf_dir": 0.0, "pat_hammer_dir": 0.0,
                   "pat_marubozu_dir": 0.0}

# Bumped whenever same-width vectors change MEANING (v2: side-relative
# encoding). Restore paths must drop pending vectors from other versions
# - the width guard alone cannot see a semantic change.
FEATURE_SCHEMA_VERSION = 2

# *_dir features are SIDE-RELATIVE: market-absolute signed quantities
# multiplied by trade direction, so "+" always means "with my trade".
# Labels are side-aware (win = the side taken paid); presenting signed
# features in the same frame lets the linear ladder baseline use them
# without waiting for a tree model to earn interactions. fv_edge_bps
# and mtf_align were ALREADY side-relative by construction and keep
# their names.
FEATURE_NAMES = [
    "ret_1_dir", "ret_6_dir", "ret_12_dir", "ret_48_dir",  # drift w/ trade
    "sigma_bar_pct", "vol_percentile",
    "imbalance_dir", "spread_bps", "depth_log",
    "fv_edge_bps", "basis_dir",
    "volume_z", "funding_dir",
    "mom_dir", "drawdown_pct",
    "regime_bull_quiet", "regime_bull_vol", "regime_range",
    "regime_bear", "regime_crisis",
    "corr_fast", "corr_shift", "turbulence_pct",
    "sent_dir", "sent_fear",
    "fear_greed", "dominance_delta", "equity_risk_z",
    "hour_sin", "hour_cos", "weekend",
    "imbalance_delta_dir", "other_ret_6_dir", "depth_ratio",
    "mtf_align", "pd_zone", "liq_pocket_pull",
    "fvg_pull", "fvg_liq_confluence", "poc_dist", "va_pos",
    "pat_engulf_dir", "pat_hammer_dir", "pat_marubozu_dir",
    "direction", "gate_confidence",
]


def _hour_frac(extras) -> float:
    """UTC time-of-day as a fraction; sin/cos encode the session cycle
    (Asia/EU/US liquidity waves are the strongest intraday seasonality
    crypto has)."""
    tm = time.gmtime((extras or {}).get("ts", time.time()))
    return (tm.tm_hour + tm.tm_min / 60.0) / 24.0


def _candle_patterns(candles: list) -> tuple:
    """Two-bar formation scores in [-1, 1], 0.0 = absent/neutral. Pure
    mathematically-defined formations on the last two COMMITTED bars
    (the feeds drop the forming candle), fed to the meta-model as
    features - never a gate, never a veto (same contract as the SMC
    block): the model learns from labeled outcomes whether each
    formation deserves weight.

    pat_engulf   signed body-engulfing: opposite-colour body covering
                 the prior body's span; strength = body-size ratio
                 (2x prior body saturates at +/-1)
    pat_hammer   signed rejection wick: + long lower wick (hammer),
                 - long upper wick (shooting star), damped toward 0 as
                 the body grows (a full-body bar rejects nothing)
    pat_marubozu signed conviction: body share of true range, sign =
                 candle direction; +/-1 full-body momentum bar, 0 doji
    """
    if not candles or len(candles) < 2:
        return 0.0, 0.0, 0.0
    try:
        prev, last = candles[-2], candles[-1]
        o0, c0 = float(prev["open"]), float(prev["close"])
        o1, h1 = float(last["open"]), float(last["high"])
        l1, c1 = float(last["low"]), float(last["close"])
    except (KeyError, TypeError, ValueError):
        return 0.0, 0.0, 0.0
    rng = max(h1 - l1, EPS)
    body, body_prev = c1 - o1, c0 - o0
    engulf = 0.0
    if body * body_prev < 0 and abs(body) > EPS:
        lo0, hi0 = min(o0, c0), max(o0, c0)
        if min(o1, c1) <= lo0 and max(o1, c1) >= hi0:
            ratio = abs(body) / (abs(body_prev) + EPS)
            engulf = float(np.sign(body) * np.clip(ratio / 2.0, 0.0, 1.0))
    upper = h1 - max(o1, c1)
    lower = min(o1, c1) - l1
    small_body = 1.0 - min(abs(body) / rng, 1.0)
    hammer = float(np.clip((lower - upper) / rng, -1.0, 1.0) * small_body)
    marubozu = float(np.sign(body) * min(abs(body) / rng, 1.0))
    return engulf, hammer, marubozu


def _ret(closes: np.ndarray, k: int, sigma_bar: float) -> float:
    if len(closes) <= k or closes[-k - 1] <= 0:
        return 0.0
    r = float(np.log(closes[-1] / closes[-k - 1]))
    return float(np.clip(r / (sigma_bar * np.sqrt(k) + EPS), -6, 6))


def build_features(asset: str, direction: str, gate_confidence: float,
                view: dict, fv_state, vol_state, liq_state,
                macro_state, corr_state, sentiment, smc_feats: dict,
                other_asset: Optional[str] = None,
                extras: Optional[dict] = None) -> np.ndarray:
    dir_sign = 1.0 if direction == "long" else -1.0
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
        dir_sign * _ret(closes, 1, sigma_bar),
        dir_sign * _ret(closes, 6, sigma_bar),
        dir_sign * _ret(closes, 12, sigma_bar),
        dir_sign * _ret(closes, 48, sigma_bar),
        float(np.clip(vol_state.sigma_bar_pct, 0, 5)),
        vol_state.percentile / 100.0,
        dir_sign * imb,
        float(np.clip(liq_state.spread_bps, 0, 60)) / 10.0,
        float(np.log1p(max(liq_state.depth_top10_usd, 0.0)) / 15.0),
        float(np.clip(fv_state.edge_bps("buy" if direction == "long" else "sell"),
                    -50, 50)) / 10.0,
        dir_sign * float(np.clip(fv_state.basis_bps, -80, 80)) / 10.0,
        volume_z,
        dir_sign * float(np.clip((view.get("funding_rate") or 0.0) * 1e4,
                                 -30, 30)) / 10.0,
        dir_sign * macro_state.momentum_score,
        float(np.clip(macro_state.drawdown_pct, 0, 90)) / 100.0,
        *one_hot,
        corr_fast,
        float(np.clip(corr_shift, -1, 1)),
        turb_pct / 100.0,
        dir_sign * float(np.clip(sent_score, -1, 1)),
        sent_fear,
        float(np.clip((extras or {}).get("fear_greed", 50.0), 0, 100)) / 100.0,
        float(np.clip((extras or {}).get("dominance_delta", 0.0), -3, 3)),
        float(np.clip((extras or {}).get("equity_risk_z", 0.0), -4, 4)),
        math.sin(2 * math.pi * _hour_frac(extras)),
        math.cos(2 * math.pi * _hour_frac(extras)),
        float(time.gmtime((extras or {}).get("ts", time.time())).tm_wday >= 5),
        dir_sign * float(np.clip((extras or {}).get("imbalance_delta", 0.0),
                                 -2, 2)),
        dir_sign * float(np.clip((extras or {}).get("other_ret_6", 0.0),
                                 -3, 3)),
        float(np.clip((extras or {}).get("depth_ratio", 1.0), 0, 3)),
        float(np.clip((smc_feats or {}).get("mtf_align", 0.0), -1, 1)),
        float(np.clip((smc_feats or {}).get("pd_zone", 0.5), 0, 1)),
        float(np.clip((smc_feats or {}).get("liq_pocket_pull", 0.0), 0, 1)),
        float(np.clip((smc_feats or {}).get("fvg_pull", 0.0), 0, 1)),
        float(np.clip((smc_feats or {}).get("fvg_liq_confluence", 0.0), 0, 1)),
        float(np.clip((smc_feats or {}).get("poc_dist", 0.0), -1, 1)),
        float(np.clip((smc_feats or {}).get("va_pos", 0.0), -1, 1)),
        *(dir_sign * v for v in _candle_patterns(candles)),
        dir_sign,
        float(np.clip(gate_confidence, 0, 1)),
    ], dtype=float)
    if x.shape[0] != len(FEATURE_NAMES):
        raise ValueError(f"feature vector length {x.shape[0]} != "
                        f"{len(FEATURE_NAMES)} (schema mismatch)")
    return x
