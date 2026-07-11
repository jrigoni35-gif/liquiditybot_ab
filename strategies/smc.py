"""
strategies/smc.py — Smart Money Concepts feature engineering (docs/SMC.md)

Six requested signal families, computed directly from the candle
history already carried on the market view (`view["candles"]`, same
source strategies/thales.py accumulates its own rolling window from)
- no new per-asset accumulator to keep in sync with the feed, no
train/serve skew, and short/garbage history degrades to neutral
rather than raising (same discipline as thales.py and ml/features.py).

  1. MTF context        - EMA-cross trend on the 5m view candles (LTF)
                           AND on the real daily candles main.py already
                           fetches for the macro regime engine (HTF),
                           agreement vs. the candidate direction ->
                           mtf_align
  2. Premium/discount    - price's position inside the recent swing
                           range -> pd_zone (0=discount, 1=premium)
  3. Liquidity pockets    - magnetism toward the resting stop cluster
                           beyond the swing extreme, in the trade's
                           direction -> liq_pocket_pull. Reuses
                           strategies/swing_points.swing_high_low, the
                           SAME primitive thales.py TH-013 uses, so the
                           two modules never disagree on "where the
                           recent extremes are"
  4. Fair Value Gaps      - pull toward the nearest unfilled 3-bar
                           imbalance ahead of price -> fvg_pull
  5. FVG/liquidity confluence - whether the nearest FVG (in the trade's
                           direction) and the liquidity-pocket target
                           overlap -> fvg_liq_confluence
  6. Volume Profile       - distance to the Point of Control and
                           position vs. the Value Area -> poc_dist,
                           va_pos

Detect-only: pure feature computation. No gating, no sizing, no order
influence - these are additional columns in the meta-model's feature
vector (ml/features.py), same role as fv_state/vol_state/liq_state.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from strategies.swing_points import swing_high_low

log = logging.getLogger("liquiditybot.strategies.smc")

EPS = 1e-9

NEUTRAL = {
    "mtf_align": 0.0,
    "pd_zone": 0.5,
    "liq_pocket_pull": 0.0,
    "fvg_pull": 0.0,
    "fvg_liq_confluence": 0.0,
    "poc_dist": 0.0,
    "va_pos": 0.0,
}


def _clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _to_bars(candles: list) -> List[tuple]:
    """Sanitizes a raw candle list into ascending, deduped
    (ts, open, high, low, close, volume) tuples. Mirrors
    thales.py's observe_candles parsing so both modules read the
    same feed the same way."""
    seen = set()
    out = []
    for bar in candles or []:
        try:
            ts = float(bar.get("ts") or bar.get("time") or 0.0)
            o = float(bar.get("open") or 0.0)
            c = float(bar.get("close") or 0.0)
            hi = float(bar.get("high") or max(o, c))
            lo = float(bar.get("low") or min(o, c))
            vol = float(bar.get("volume") or 0.0)
        except (TypeError, ValueError, AttributeError):
            continue
        if ts <= 0 or o <= EPS or c <= EPS or ts in seen:
            continue
        seen.add(ts)
        out.append((ts, o, hi, lo, c, vol))
    out.sort(key=lambda b: b[0])
    return out


# ---------------------------------------------------------------------
# 1. MTF context
# ---------------------------------------------------------------------
def _ema(values: Sequence[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    k = 2.0 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
    return ema


def _trend_dir(closes: Sequence[float], fast: int, slow: int) -> int:
    fast_e = _ema(closes, fast)
    slow_e = _ema(closes, slow)
    if fast_e is None or slow_e is None:
        return 0
    if fast_e > slow_e:
        return 1
    if fast_e < slow_e:
        return -1
    return 0


def mtf_align(ltf_closes: Sequence[float], htf_closes: Sequence[float],
             direction: str, cfg: dict) -> float:
    """Agreement between an EMA-cross trend read on the LTF (5m view
    candles) and the SAME read on genuine HTF candles (main.py's daily
    bars, already fetched for the macro regime engine - not a resample
    of the same short window, which the live feed's ~100-200 bar
    default candle limit can never grow into a meaningful multi-day
    higher timeframe). Each available timeframe casts one vote for/
    against the candidate direction; no data on a timeframe simply
    drops its vote rather than forcing a disagreement."""
    trade_d = 1 if direction == "long" else -1 if direction == "short" else 0
    if trade_d == 0:
        return 0.0
    ltf_d = _trend_dir(ltf_closes, int(cfg.get("ltf_fast_period", 9)),
                       int(cfg.get("ltf_slow_period", 21)))
    htf_d = _trend_dir(htf_closes, int(cfg.get("htf_fast_period", 5)),
                       int(cfg.get("htf_slow_period", 15)))
    votes = [d for d in (ltf_d, htf_d) if d != 0]
    if not votes:
        return 0.0
    agree = sum(1 for v in votes if v == trade_d)
    disagree = len(votes) - agree
    return _clip((agree - disagree) / len(votes), -1.0, 1.0)


# ---------------------------------------------------------------------
# 2. Premium / discount zone
# ---------------------------------------------------------------------
def pd_zone(bars: List[tuple], cfg: dict) -> float:
    if not bars:
        return 0.5
    lookback = int(cfg.get("lookback", 48))
    swing_hi, swing_lo = swing_high_low(
        [(ts, o, h, lo, c) for ts, o, h, lo, c, _ in bars], lookback)
    price = bars[-1][4]
    if swing_hi is None or swing_hi - swing_lo < EPS or price <= EPS:
        return 0.5
    return _clip((price - swing_lo) / (swing_hi - swing_lo), 0.0, 1.0)


# ---------------------------------------------------------------------
# 3. Liquidity pockets
# ---------------------------------------------------------------------
def liq_pocket_pull(bars: List[tuple], direction: str, cfg: dict) -> float:
    if not bars or direction not in ("long", "short"):
        return 0.0
    lookback = int(cfg.get("lookback", 48))
    pull_max_pct = float(cfg.get("pull_max_pct", 3.0))
    swing_hi, swing_lo = swing_high_low(
        [(ts, o, h, lo, c) for ts, o, h, lo, c, _ in bars], lookback)
    price = bars[-1][4]
    if swing_hi is None or price <= EPS or pull_max_pct <= EPS:
        return 0.0
    target = swing_hi if direction == "long" else swing_lo
    dist_frac = abs(target - price) / price
    cap = pull_max_pct / 100.0
    if dist_frac >= cap:
        return 0.0
    return _clip(1.0 - dist_frac / cap, 0.0, 1.0)


# ---------------------------------------------------------------------
# 4. Fair Value Gaps + 5. FVG/liquidity confluence
# ---------------------------------------------------------------------
@dataclass
class FVG:
    idx: int
    top: float
    bottom: float
    direction: int   # +1 bullish (gap up), -1 bearish (gap down)

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2.0


def _find_unfilled_fvgs(bars: List[tuple], lookback_bars: int,
                        min_gap_pct: float) -> List[FVG]:
    """Classic 3-candle imbalance: bar[i-1]'s high/low doesn't overlap
    bar[i+1]'s low/high, leaving a gap most of bar[i]'s range covers.
    A gap is "unfilled" if no later bar's range has traded back into
    it since formation."""
    window = bars[-lookback_bars:] if lookback_bars else bars
    n = len(window)
    if n < 3:
        return []
    found = []
    for i in range(1, n - 1):
        _, _, hi1, lo1, _, _ = window[i - 1]
        _, _, hi3, lo3, close3, _ = window[i + 1]
        price_ref = max(close3, EPS)
        if lo3 > hi1:
            gap = lo3 - hi1
            if gap / price_ref >= min_gap_pct / 100.0:
                found.append(FVG(idx=i, top=lo3, bottom=hi1, direction=1))
        elif hi3 < lo1:
            gap = lo1 - hi3
            if gap / price_ref >= min_gap_pct / 100.0:
                found.append(FVG(idx=i, top=lo1, bottom=hi3, direction=-1))
    unfilled = []
    for f in found:
        touched = False
        for j in range(f.idx + 2, n):
            _, _, hi_j, lo_j, _, _ = window[j]
            if hi_j >= f.bottom and lo_j <= f.top:
                touched = True
                break
        if not touched:
            unfilled.append(f)
    return unfilled


def fvg_pull(bars: List[tuple], direction: str, cfg: dict) -> float:
    if not bars or direction not in ("long", "short"):
        return 0.0
    price = bars[-1][4]
    if price <= EPS:
        return 0.0
    unfilled = _find_unfilled_fvgs(
        bars, int(cfg.get("lookback_bars", 150)),
        float(cfg.get("min_gap_pct", 0.02)))
    candidates = [f.mid for f in unfilled
                  if (direction == "long" and f.mid > price)
                  or (direction == "short" and f.mid < price)]
    if not candidates:
        return 0.0
    nearest = min(candidates, key=lambda m: abs(m - price))
    dist_frac = abs(nearest - price) / price
    cap = float(cfg.get("pull_max_pct", 3.0)) / 100.0
    if cap <= EPS or dist_frac >= cap:
        return 0.0
    return _clip(1.0 - dist_frac / cap, 0.0, 1.0)


def fvg_liq_confluence(bars: List[tuple], direction: str, cfg: dict,
                       liquidity_cfg: dict) -> float:
    if not bars or direction not in ("long", "short"):
        return 0.0
    lookback = int(liquidity_cfg.get("lookback", 48))
    swing_hi, swing_lo = swing_high_low(
        [(ts, o, h, lo, c) for ts, o, h, lo, c, _ in bars], lookback)
    if swing_hi is None:
        return 0.0
    target = swing_hi if direction == "long" else swing_lo
    price = bars[-1][4]
    unfilled = _find_unfilled_fvgs(
        bars, int(cfg.get("lookback_bars", 150)),
        float(cfg.get("min_gap_pct", 0.02)))
    candidates = [f for f in unfilled
                  if (direction == "long" and f.mid > price)
                  or (direction == "short" and f.mid < price)]
    if not candidates or target <= EPS:
        return 0.0
    tol = float(cfg.get("confluence_tol_pct", 0.3)) / 100.0 * target
    if tol <= EPS:
        return 0.0
    best = 0.0
    for f in candidates:
        if f.bottom - tol <= target <= f.top + tol:
            d = 0.0
        else:
            d = min(abs(target - f.top), abs(target - f.bottom))
        best = max(best, _clip(1.0 - d / tol, 0.0, 1.0))
    return best


# ---------------------------------------------------------------------
# 6. Volume Profile (POC / Value Area)
# ---------------------------------------------------------------------
def _volume_profile(bars: List[tuple], cfg: dict
                    ) -> Tuple[Optional[float], Optional[float],
                               Optional[float]]:
    lookback_bars = int(cfg.get("lookback_bars", 200))
    window = bars[-lookback_bars:] if lookback_bars else bars
    if len(window) < 8:
        return None, None, None
    los = [b[3] for b in window]
    his = [b[2] for b in window]
    lo, hi = min(los), max(his)
    if hi - lo < EPS:
        return None, None, None
    n_bins = max(int(cfg.get("n_bins", 24)), 3)
    bin_w = (hi - lo) / n_bins
    vols = [0.0] * n_bins
    for _, o, h, lo_p, c, v in window:
        typical = (h + lo_p + c) / 3.0
        b = int((typical - lo) / bin_w)
        b = min(max(b, 0), n_bins - 1)
        vols[b] += max(v, 0.0)
    total = sum(vols)
    if total <= EPS:
        return None, None, None
    poc_bin = max(range(n_bins), key=lambda i: vols[i])
    poc = lo + (poc_bin + 0.5) * bin_w
    va_pct = _clip(float(cfg.get("value_area_pct", 0.68)), 0.01, 1.0)
    va_target = total * va_pct
    included = {poc_bin}
    cum = vols[poc_bin]
    left, right = poc_bin - 1, poc_bin + 1
    while cum < va_target and (left >= 0 or right < n_bins):
        vl = vols[left] if left >= 0 else -1.0
        vr = vols[right] if right < n_bins else -1.0
        if vr >= vl:
            included.add(right)
            cum += vr
            right += 1
        else:
            included.add(left)
            cum += vl
            left -= 1
    lo_bin, hi_bin = min(included), max(included)
    val = lo + lo_bin * bin_w
    vah = lo + (hi_bin + 1) * bin_w
    return poc, val, vah


def poc_dist(bars: List[tuple], cfg: dict) -> float:
    poc, _val, _vah = _volume_profile(bars, cfg)
    if poc is None or not bars:
        return 0.0
    price = bars[-1][4]
    if price <= EPS:
        return 0.0
    cap = float(cfg.get("poc_dist_cap_pct", 5.0)) / 100.0
    if cap <= EPS:
        return 0.0
    dist = (price - poc) / price
    return _clip(dist / cap, -1.0, 1.0)


def va_pos(bars: List[tuple], cfg: dict) -> float:
    poc, val, vah = _volume_profile(bars, cfg)
    if poc is None or not bars:
        return 0.0
    price = bars[-1][4]
    if price <= EPS:
        return 0.0
    if val <= price <= vah:
        return 0.0
    cap = float(cfg.get("poc_dist_cap_pct", 5.0)) / 100.0
    if cap <= EPS:
        return 0.0
    if price < val and val > EPS:
        return -_clip((val - price) / val / cap, 0.0, 1.0)
    if vah > EPS:
        return _clip((price - vah) / vah / cap, 0.0, 1.0)
    return 0.0


# ---------------------------------------------------------------------
# engine
# ---------------------------------------------------------------------
class SMCEngine:
    """Config-driven wrapper: thresholds/windows live in config.json's
    "smc" block (validated by core/config_guard.py), never as literals
    in the decision path. `compute()` never raises - a malformed
    candle list or missing history degrades to the NEUTRAL vector,
    same fail-safe contract as every other feature producer."""

    def __init__(self, config: dict):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", True))
        self._mtf = cfg.get("mtf", {})
        self._pd = cfg.get("pd_zone", {})
        self._liq = cfg.get("liquidity", {})
        self._fvg = cfg.get("fvg", {})
        self._vp = cfg.get("volume_profile", {})
        self._last: dict = {}   # asset -> last computed snapshot (telemetry)

    def compute(self, asset: str, candles: list, direction: str,
               now: float, daily_candles: Optional[list] = None) -> dict:
        if not self.enabled:
            return dict(NEUTRAL)
        try:
            bars = _to_bars(candles)
            if not bars:
                out = dict(NEUTRAL)
            else:
                daily_bars = _to_bars(daily_candles or [])
                ltf_closes = [b[4] for b in bars]
                htf_closes = [b[4] for b in daily_bars]
                out = {
                    "mtf_align": mtf_align(ltf_closes, htf_closes,
                                          direction, self._mtf),
                    "pd_zone": pd_zone(bars, self._pd),
                    "liq_pocket_pull": liq_pocket_pull(
                        bars, direction, self._liq),
                    "fvg_pull": fvg_pull(bars, direction, self._fvg),
                    "fvg_liq_confluence": fvg_liq_confluence(
                        bars, direction, self._fvg, self._liq),
                    "poc_dist": poc_dist(bars, self._vp),
                    "va_pos": va_pos(bars, self._vp),
                }
            self._last[asset] = out
            return out
        except Exception:
            log.debug("smc compute degraded to neutral", exc_info=True)
            return dict(NEUTRAL)

    def status(self) -> dict:
        if not self.enabled:
            return {"enabled": False}
        return {"enabled": True,
                "assets": {a: {k: round(v, 3) for k, v in s.items()}
                           for a, s in self._last.items()}}
