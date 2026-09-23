"""
ml/features.py

Single source of truth for the feature vector. Live inference (meta
model scoring a candidate signal) and offline training (walk-forward on
logged history) both call build_features, so there is no train/serve
skew - the classic way ML trading systems silently die.

Feature families:
price/momentum   - multi-horizon returns normalized by bar vol
volatility       - per-bar vol, daily vol percentile, realized-vol
                    term structure (expanding vs compressing)
microstructure   - imbalance, spread, depth, fair-value edge, basis,
                    touch-depth concentration (book SHAPE)
flow             - volume z-score, funding rate
regime           - macro label one-hots, momentum score, drawdown
cross-asset      - fast corr, corr shift, turbulence percentile,
                    equal-weight market-factor drift with the trade
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

# migration neutrals for the context/THALES block: 0.5 = "unknown
# mid-point" for bounded clocks and ages (a padded row should not claim
# a fresh regime or an imminent settlement), 0.0 = "no footprint / no
# dislocation observed".
CONTEXT_NEUTRAL = {"regime_age": 0.5, "funding_dist": 0.5,
                   "venue_disloc_dir": 0.0, "th_grid": 0.0,
                   "th_metronome": 0.0, "th_clockwork": 0.0,
                   "th_stopzone": 0.0, "th_barclose": 0.0,
                   # options positioning: 0.0 = "no fear signal read"
                   "opt_pcr_z": 0.0, "opt_oi_pcr_z": 0.0,
                   "opt_iv_skew": 0.0,
                   "manip_suspect": 0.0}

# migration neutrals for the v7 trio. vol_term/mkt_ret_6_dir: 0.0 =
# "flat term structure / no market drift observed". book_touch_share:
# 0.2 = the even-10-level neutral — the denominator is the top-10
# notionals BOTH SIDES (5 levels per side); under a perfectly flat book
# each of those 10 levels carries 1/10, and the touch is one level per
# side = 2/10 = 0.2. Padding 0.0 would falsely claim a hollow touch.
TRIO_NEUTRAL = {"vol_term": 0.0, "mkt_ret_6_dir": 0.0,
                "book_touch_share": 0.2}

# migration neutral for the v8 flow-toxicity feature: 0.0 = "no
# toxicity signal read" (same convention as the opt_* block). A padded
# old row is indistinguishable from genuinely balanced flow - accepted,
# exactly like the pattern neutrals.
TOX_NEUTRAL = {"flow_tox": 0.0}

# migration neutrals for the v9 SHADOW pair: 0.0 = "no signed event
# flow / no basis drift observed" - a padded pre-v9 row is
# indistinguishable from a genuinely quiet book, the exact TOX_NEUTRAL
# convention. SHADOW status + pre-registered PROMOTION criteria
# (plan docs/superpowers/plans/2026-07-31-tank-quant2.md, Global
# Constraints, recorded verbatim): "a shadow column may be promoted to
# any decision input only after (1) 3 consecutive feature-stability
# snapshots keep it out of the OOS-dead set, (2) the OF battery stays
# green with it in the trained space, (3) markout
# (execution/markout.py) shows non-negative delta on entries taken
# with vs without the signal's favorable side over >=200 live
# entries." Until then the two columns feed ONLY this feature vector -
# tests/test_ofi_feature.py's shadow-purity grep proves no gate/sizer/
# exit/execution module reads them.
V9_NEUTRAL = {"ofi_dir": 0.0, "basis_mom_dir": 0.0}

# migration neutrals for the v10 SHADOW dark-pool block (FINRA ATS weekly
# mirror, basket COIN/MSTR/QQQ): 0.0 = "no dark-pool observation read" -
# a dead/absent mirror's zeros are byte-identical to genuine neutral flow,
# exactly the TOX_NEUTRAL/V9_NEUTRAL convention. dp_hhi's true neutral would
# be a dispersed-book value, but 0.0 is the documented migration neutral
# (same trade-off as book_touch_share: padding must never CLAIM structure).
# avail_dp is the block's own availability feature (1 = real observation,
# 0 = degraded/neutral) and gates the other three to 0.0 in build_features,
# so a stale producer can never serve its last-live value as fresh.
# SHADOW status, same pre-registered promotion law as V9_NEUTRAL: the three
# dp_* columns feed ONLY the feature vector until the TANK quant-2 criteria
# (3 stability snapshots out of the OOS-dead set, green OF battery with it
# in the trained space, non-negative >=200-entry markout delta) all pass.
DP_NEUTRAL = {"dp_surge_z": 0.0, "dp_vol_z": 0.0, "dp_hhi": 0.0,
              "avail_dp": 0.0}

# Bumped whenever vectors change MEANING (v2: side-relative encoding;
# v3: +context/THALES block, 46->53; v4: +options positioning, 53->56;
# v5: +manip_suspect adversarial-data score, 56->57; v6: +th_barclose
# bar-close herd detector, 57->58; v7: +vol_term/mkt_ret_6_dir/
# book_touch_share regime-derivative/market-factor/book-shape trio,
# 58->61; v8: +flow_tox VPIN-lite order-flow toxicity, 61->62 - the
# same bump batches two value-semantics changes with no width change:
# candles/volume re-grounded to the execution venue (wash-trading
# hygiene, Cong et al. 2023) and order-book imbalance distance-decayed
# toward the touch (spoof economics, Stoikov 2018); v9: +ofi_dir/
# basis_mom_dir SHADOW pair, 62->64 - event-based best-level OFI
# (Cont-Kukanov-Stoikov 2014) and perp-basis momentum, ONE batched bump
# for both columns (TANK quant-2 K/N; see V9_NEUTRAL above for the
# pre-registered promotion criteria);
# v10: +dp_surge_z/dp_vol_z/dp_hhi/avail_dp SHADOW dark-pool block, 64->68 -
# FINRA ATS weekly dark-volume context (basket COIN/MSTR/QQQ) mirrored
# outside the bot into darkpool.duckdb and read read-only by
# data/darkpool_feed.py; ONE batched bump for all four columns (same
# TANK quant-2 K/N law; see DP_NEUTRAL above). All four absolute gauges,
# NOT side-relative - like the opt_* fear gauges, direction is an empirical
# question for the model, not doctrine.
# Restore paths must drop pending vectors from other versions - the
# width guard alone cannot see a semantic change, and versioning also
# documents additive bumps.
FEATURE_SCHEMA_VERSION = 10

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
    "regime_age",                 # 0..1: hours since macro label change /24
    "funding_dist",               # 0..1: fraction of 8h cycle to settlement
    "venue_disloc_dir",           # kraken vs street mid, with/against trade
    "th_grid", "th_metronome", "th_clockwork", "th_stopzone",  # THALES [0,1]
    "th_barclose",                # bar-close herd (no-code bot bursts) [0,1]
    "opt_pcr_z",                  # put/call VOLUME ratio z (day hedge flow)
    "opt_oi_pcr_z",               # put/call OPEN-INTEREST ratio z (stock)
    "opt_iv_skew",                # put-minus-call IV, points/10 [-3,3]
                                  # (widened from [-1,1] 2026-07-20: 43%
                                  # of options-available rows censored at
                                  # -1; unit unchanged, no version bump -
                                  # old pinned rows are censored obs)
    "manip_suspect",              # adversarial-data suspicion [0,1]
    "pat_engulf_dir", "pat_hammer_dir", "pat_marubozu_dir",
    "vol_term",                   # log(sigma_12/sigma_96) term structure
    "mkt_ret_6_dir",              # equal-weight market drift, with trade
    "book_touch_share",           # touch notional / top-10 notional [0,1]
    "flow_tox",                   # VPIN-lite order-flow toxicity [0,1]
    "ofi_dir",                    # v9 SHADOW: event OFI (CKS 2014),
                                  # touch-depths/min, with/against trade
    "basis_mom_dir",              # v9 SHADOW: basis drift bps/min /10,
                                  # with/against trade
    "dp_surge_z",                 # v10 SHADOW: z of basket-mean dark-volume
                                  # surge ratio (current FINRA period / avg of
                                  # prior <=4 complete periods) - absolute,
                                  # clip [-4,4]
    "dp_vol_z",                   # v10 SHADOW: z of basket-mean log dark
                                  # volume - absolute, clip [-4,4]
    "dp_hhi",                     # v10 SHADOW: venue concentration 0..1,
                                  # low = dispersed institutional flow
    "avail_dp",                   # v10 SHADOW: 1 = dp_* from a REAL
                                  # observation, 0 = degraded/neutral
                                  # (gates the three dp_* to DP_NEUTRAL)
    "direction", "gate_confidence",
]

# Features EXCLUDED from the input-drift vote (ml.monitor.check_drift). These
# are legitimate MODEL INPUTS but deterministic functions of the CLOCK or a
# monotone counter, not of market state: their decile-PSI on any finite live
# window measures WHERE the window sits in time/phase, not a distributional
# shift the model must relearn. A short overnight window has hour_sin/cos and
# funding_dist clustered at one phase, and regime_age sits low right after a
# label change — each reads as a big PSI vs the all-phases training set while
# nothing about the market has drifted. This is the same reason the PSI kernel
# already returns 0 for degenerate (binary/one-hot) deciles; here the tell is
# semantic (clock/counter) rather than structural (tied edges), so it is named
# explicitly. Market features (vol, spread, returns, imbalance, ...) still vote.
# The v7 trio (vol_term, mkt_ret_6_dir, book_touch_share) was considered and
# left VOTING: all three are functions of market state, not the clock.
DRIFT_EXCLUDED_FEATURES = frozenset({
    "hour_sin", "hour_cos",   # time-of-day cyclical (pure clock)
    "funding_dist",           # fraction of the 8h funding cycle (pure clock)
    "regime_age",             # hours since macro label change /24 (counter)
})

FUNDING_PERIOD_SEC = 8 * 3600.0


def _funding_dist(ts: float) -> float:
    """Time to the NEXT perp funding settlement (00/08/16 UTC), as a
    fraction of the 8h cycle: 0.0 = settling this instant, ~1.0 = just
    settled. Pure clock math, like hour_sin/cos - the clockwork detector
    hunts this pattern in OTHER bots; this feature tells our model where
    IT stands on the same clock."""
    try:
        r = float(ts) % FUNDING_PERIOD_SEC
    except (TypeError, ValueError):
        return 0.5
    return ((FUNDING_PERIOD_SEC - r) % FUNDING_PERIOD_SEC
            / FUNDING_PERIOD_SEC)


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


def _finite(v, default: float = 0.0) -> float:
    """NaN/None/garbage-safe float coercion for producer-fed inputs the
    schema documents as '0.0 when missing/stale' (the v9 shadow pair):
    np.clip would PROPAGATE a NaN into the vector, so guard before it."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


def _th(extras, key: str) -> float:
    """THALES detector score from extras, 0.0 when absent/malformed."""
    try:
        return float(((extras or {}).get("thales") or {}).get(key, 0.0))
    except (TypeError, ValueError):
        return 0.0


def _vol_term(closes: np.ndarray) -> float:
    """Realized-vol term structure log(sigma_short / sigma_long) from the
    5m closes already in view: sigma_short = std of the last 12 bar
    log-returns, sigma_long = std of the last 96. Expanding-vs-compressing
    vol LEADS regime; sigma_bar_pct + vol_percentile give level and rank
    but cannot see the derivative. NOT direction-signed - the term
    structure is symmetric information (expansion hurts/helps both sides
    the same way). Insufficient history (<97 closes, i.e. <96 returns) or
    degenerate sigma_long -> 0.0 (flat = neutral)."""
    if len(closes) < 97 or np.any(closes[-97:] <= 0):
        return 0.0
    lr = np.diff(np.log(closes[-97:]))          # exactly 96 log-returns
    s_short = float(np.std(lr[-12:]))
    s_long = float(np.std(lr))
    if s_long <= 0:
        return 0.0
    # s_short == 0 with live s_long = maximal 12-bar compression: EPS
    # floor keeps the log finite and the clip lands it at -2, without a
    # divide-by-zero warning polluting the cycle logs.
    return float(np.clip(np.log(max(s_short, EPS) / s_long), -2, 2))


def _ret(closes: np.ndarray, k: int, sigma_bar: float) -> float:
    if len(closes) <= k or closes[-k - 1] <= 0:
        return 0.0
    r = float(np.log(closes[-1] / closes[-k - 1]))
    return float(np.clip(r / (sigma_bar * np.sqrt(k) + EPS), -6, 6))


# flow-toxicity window: 48 five-minute bars = 4h, the same lookback the
# volume_z baseline uses - a schema constant like the ret_k horizons,
# not a tunable (changing it is a version bump, not a config edit)
_TOX_BARS = 48


def _flow_toxicity(closes: np.ndarray, vols: np.ndarray,
                   sigma_bar: float) -> float:
    """VPIN-lite order-flow toxicity from bars already in view (Easley,
    Lopez de Prado & O'Hara 2012, RFS - flow toxicity adversely selects
    liquidity providers; VPIN spiked an hour before the Flash Crash).
    Bulk Volume Classification assigns each bar's volume a buy fraction
    Phi(r/sigma); toxicity = volume-weighted |2*buy_frac - 1| over the
    last _TOX_BARS bars, in [0,1]. Balanced two-way flow -> 0, one-sided
    (informed/predatory) flow -> 1. Too little history, dead volume, or
    degenerate sigma -> 0.0 = "no toxicity signal read" (TOX_NEUTRAL)."""
    if len(closes) < _TOX_BARS + 1 or len(vols) < _TOX_BARS or sigma_bar <= 0:
        return 0.0
    px = closes[-(_TOX_BARS + 1):]
    if np.any(px <= 0):
        return 0.0
    v = np.asarray(vols[-_TOX_BARS:], dtype=float)
    v = np.where(np.isfinite(v) & (v > 0), v, 0.0)
    total = float(v.sum())
    if total <= 0:
        return 0.0
    z = np.diff(np.log(px)) / (sigma_bar + EPS)
    buy_frac = np.array([0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
                         for x in z])
    tox = float(np.dot(np.abs(2.0 * buy_frac - 1.0), v) / total)
    return float(np.clip(tox, 0.0, 1.0))


# Macro regime labels, in the SAME order the one-hot block below encodes
# them (FEATURE_NAMES: regime_bull_quiet, regime_bull_vol, regime_range,
# regime_bear, regime_crisis). Mirrors regime.macro_regime.REGIME_LABELS
# (duplicated, not imported - ml/ carries no dependency on regime/, and a
# drift here is immediately falsifiable: every one_hot column would read
# all-zero for that label). Exported so ml/history.py's per-regime live
# counter (Task 4, #103 regime-coverage hold) can decode a written row's
# one-hot back to a label with the EXACT mapping used to encode it here.
REGIME_LABELS = ("bull_quiet", "bull_volatile", "range", "bear", "crisis")
REGIME_ONE_HOT_FEATURES = ("regime_bull_quiet", "regime_bull_vol",
                           "regime_range", "regime_bear", "regime_crisis")


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
    one_hot = [float(regime == r) for r in REGIME_LABELS]

    corr_fast, corr_shift = 0.0, 0.0
    if corr_state is not None and other_asset:
        corr_fast = corr_state.corr(asset, other_asset)
        pair = (min(asset, other_asset), max(asset, other_asset))
        corr_shift = corr_state.corr_shift.get(pair, 0.0)
    turb_pct = corr_state.turbulence_pct if corr_state is not None else 50.0

    sent_score = float(getattr(sentiment, "score", 0.0) or 0.0)
    sent_fear = float(bool(getattr(sentiment, "fear_spike", False)))

    _avail_dp = 1.0 if _finite((extras or {}).get("avail_dp", 0.0)) \
        >= 0.5 else 0.0

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
        float(np.clip((extras or {}).get("regime_age_sec", 0.0)
                      / 86400.0, 0, 1)),
        _funding_dist((extras or {}).get("ts", time.time())),
        dir_sign * float(np.clip((extras or {}).get("venue_disloc_bps", 0.0),
                                 -30, 30)) / 10.0,
        float(np.clip(_th(extras, "grid"), 0, 1)),
        float(np.clip(_th(extras, "metronome"), 0, 1)),
        float(np.clip(_th(extras, "clockwork"), 0, 1)),
        float(np.clip(_th(extras, "stop_zone"), 0, 1)),
        float(np.clip(_th(extras, "barclose"), 0, 1)),
        # options positioning stays ABSOLUTE (like fear_greed/turbulence):
        # a fear gauge whose directional payoff the model must learn -
        # contrarian vs confirmation is an empirical question, not doctrine
        float(np.clip((extras or {}).get("opt_pcr_z", 0.0), -4, 4)),
        float(np.clip((extras or {}).get("opt_oi_pcr_z", 0.0), -4, 4)),
        float(np.clip((extras or {}).get("opt_iv_skew", 0.0), -3, 3)),
        float(np.clip((extras or {}).get("manip_suspect", 0.0), 0, 1)),
        *(dir_sign * v for v in _candle_patterns(candles)),
        _vol_term(closes),
        # market-factor drift WITH the trade: extras carry the RAW
        # equal-weight mean 6-bar log-return across all viewed assets
        # (main._feature_extras); the denominator is _ret's exact 6-bar
        # form (sigma_bar*sqrt(6)+EPS) so the units ARE ret_6_dir's -
        # a bare sigma_bar would run sqrt(6)~2.45x hot and saturate the
        # clip in routine trends, and a 1e-3 floor here would be a
        # percent-unit floor on a fraction-unit sigma (sigma_bar is
        # already floored upstream). Separates "my asset moving" from
        # "everything moving" - the biggest confounder in crypto
        # cross-sections.
        dir_sign * float(np.clip((extras or {}).get("mkt_ret_6", 0.0)
                                 / (sigma_bar * np.sqrt(6.0) + EPS),
                                 -3, 3)),
        # book SHAPE: notional share of the touch within the top-10.
        # thin-behind-the-touch books break differently than thick ones
        # at identical spread; imbalance/depth_log see size, not shape.
        # 0.2 = flat-book neutral (1/10 per level x 2 sides at touch).
        float(np.clip((extras or {}).get("book_touch_share", 0.2), 0, 1)),
        # NOT direction-signed: toxicity is symmetric information (toxic
        # flow hurts whichever side provides the liquidity)
        _flow_toxicity(closes, vols, sigma_bar),
        # v9 SHADOW pair (see V9_NEUTRAL for the pre-registered
        # promotion criteria). Both side-relative: signed flow/drift
        # presented as with-my-trade, same frame as imbalance_dir/
        # basis_dir. ofi_event = view-build event OFI in touch-depth
        # turnovers per minute (already wall-time normalized at the
        # producer); basis_mom_bps = FVState basis drift in bps/min,
        # clip-then-/10 exactly like basis_dir/venue_disloc_dir.
        # _finite: producers document 0.0-on-missing/stale - enforce it
        # here too so a legacy stub/NaN can never poison the vector.
        dir_sign * float(np.clip(_finite(view.get("ofi_event", 0.0)),
                                 -3, 3)),
        dir_sign * float(np.clip(_finite(getattr(fv_state, "basis_mom_bps",
                                                 0.0)), -30, 30)) / 10.0,
        # v10 SHADOW dark-pool block (see DP_NEUTRAL for the pre-registered
        # promotion criteria). All four ABSOLUTE gauges, NOT side-relative:
        # institutional dark-flow accumulation/distribution is symmetric
        # information, like the opt_* fear gauges - whether it confirms or
        # fades a side is an empirical question for the model. avail_dp
        # gates the three dp_* to DP_NEUTRAL here, at the vector boundary,
        # so a stale/malformed producer can never serve its last-live value
        # as a fresh observation. _finite: producers document 0.0-on-
        # missing/stale - enforce it so a legacy stub/NaN can never poison
        # the vector.
        float(np.clip(_finite((extras or {}).get("dp_surge_z", 0.0)),
                      -4, 4)) * _avail_dp,
        float(np.clip(_finite((extras or {}).get("dp_vol_z", 0.0)),
                      -4, 4)) * _avail_dp,
        float(np.clip(_finite((extras or {}).get("dp_hhi", 0.0)),
                      0, 1)) * _avail_dp,
        _avail_dp,
        dir_sign,
        float(np.clip(gate_confidence, 0, 1)),
    ], dtype=float)
    if x.shape[0] != len(FEATURE_NAMES):
        raise ValueError(f"feature vector length {x.shape[0]} != "
                        f"{len(FEATURE_NAMES)} (schema mismatch)")
    return x
