"""
regime/liquidity_regime.py

Classifies the *executability* of the market right now, and detects
book manipulation so the bot never trades against painted liquidity.

Outputs one of three regimes per asset:
liquid  - normal spreads, stable depth  -> full pipeline
thin    - wide spread / shallow book    -> shrink size, maker-only
spoofy  - manipulation signature        -> block NEW risk (reduce-only)

Spoof detection (defensive - this identifies manipulation by others so
the bot ignores it; the bot itself never paints liquidity):
A level is flagged when an abnormally large resting order (>= N x the
median level size) appears, then vanishes within a few snapshots while
price never traded through or touched it. Real size gets consumed or
stays; painted size gets pulled untouched. An EWMA of such events plus
order-book-imbalance "whiplash" (rapid flip-flopping of the imbalance
ratio, the same signature exploited in Prosperity-style bot arenas)
forms the spoof score.
"""

import logging
import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np
from typing import Optional

log = logging.getLogger("liquiditybot.regime.liquidity")

EPS = 1e-9


@dataclass
class LiquidityState:
    asset: str
    label: str = "liquid"            # liquid | thin | spoofy
    spread_bps: float = 5.0          # execution venue (Kraken) spread
    combined_spread_bps: float = 5.0
    depth_top10_usd: float = 0.0     # Kraken two-sided depth
    depth_ratio: float = 1.0         # vs trailing median depth
    imbalance_whiplash: float = 0.0  # std of imbalance ratio, recent window
    spoof_score: float = 0.0         # 0..1
    spoof_events_total: int = 0
    size_mult: float = 1.0           # applied by sizer
    reduce_only: bool = False


@dataclass
class _AssetTracker:
    depth_hist: deque = field(default_factory=lambda: deque(maxlen=60))
    imb_hist: deque = field(default_factory=lambda: deque(maxlen=20))
    mid_hist: deque = field(default_factory=lambda: deque(maxlen=12))
    # (side, price) -> {"size":, "first_ts":, "seen":}
    large_levels: dict = field(default_factory=dict)
    spoof_ewma: float = 0.0
    events: int = 0


def _spread_bps(book: dict) -> float:
    bids, asks = book.get("bids") or [], book.get("asks") or []
    if not bids or not asks:
        return 999.0
    bb, ba = bids[0][0], asks[0][0]
    mid = 0.5 * (bb + ba)
    return max((ba - bb) / (mid + EPS) * 1e4, 0.0)


def _depth_usd(book: dict, levels: int = 10) -> float:
    bids = book.get("bids") or []
    asks = book.get("asks") or []
    return (sum(p * s for p, s in bids[:levels]) +
            sum(p * s for p, s in asks[:levels]))


def _imbalance(book: dict, levels: int = 10) -> float:
    bids = book.get("bids") or []
    asks = book.get("asks") or []
    b = sum(p * s for p, s in bids[:levels])
    a = sum(p * s for p, s in asks[:levels])
    if a <= EPS:
        return 3.0 if b > 0 else 1.0
    return min(b / a, 3.0)


class LiquidityRegimeEngine:
    def __init__(self, config: dict):
        cfg = config or {}
        self.min_depth_usd = float(cfg.get("min_depth_usd", 150_000))
        self.max_spread_bps = float(cfg.get("max_spread_bps", 12.0))
        self.spoof_size_mult = float(cfg.get("spoof_size_mult", 8.0))
        self.spoof_max_lifetime_s = float(cfg.get("spoof_max_lifetime_sec", 90.0))
        self.spoof_score_threshold = float(cfg.get("spoof_score_threshold", 0.45))
        # whiplash = std of the [0,3]-clamped imbalance ratio over the last
        # 20 snapshots, so its structural ceiling is 1.5 (all-samples
        # alternating 0<->3). Calibrated against 45h / ~2,600 samples of
        # healthy Kraken books at the ~30s cadence: p50~1.1, p95~1.27,
        # max 1.41 - the old 0.55 default sat BELOW the healthy 5th
        # percentile (0.66), labeling every cycle "spoofy" (size_mult=0)
        # and silently vetoing 100% of entries. 1.45 sits above the
        # observed healthy max and below the ceiling: it fires only on
        # churn outside anything seen on a normal book.
        self.whiplash_threshold = float(cfg.get("imbalance_whiplash_threshold", 1.45))
        # proximity buffer for the touched test (bps of level price): at the
        # ~30s book-sampling cadence a vanished level NEAR the sampled mid
        # path was plausibly CONSUMED between snapshots (filled, not pulled).
        # Without the buffer, normal fills read as spoof events and the score
        # saturates near 1.0 on healthy books (observed live: spoof p50 0.93
        # on 0.5bps-spread Kraken books = detector always-on = useless as a
        # signal). Painted walls sitting away from the touch still count.
        self.touch_buffer_bps = float(cfg.get("spoof_touch_buffer_bps", 5.0))
        self.ewma_alpha = float(cfg.get("spoof_ewma_alpha", 0.06))
        self.track_levels = int(cfg.get("track_levels", 15))
        self._trk: dict = {}
        self._states: dict = {}

    def state(self, asset: str) -> LiquidityState:
        return self._states.get(asset) or LiquidityState(asset=asset)

    # ------------------------------------------------------------------
    def update(self, asset: str, combined_book: dict, kraken_book: dict,
            now: Optional[float] = None) -> LiquidityState:
        now = now if now is not None else time.time()
        trk = self._trk.setdefault(asset, _AssetTracker())
        st = self._states.get(asset) or LiquidityState(asset=asset)

        exec_book = kraken_book if (kraken_book and kraken_book.get("bids")) else combined_book
        st.spread_bps = _spread_bps(exec_book)
        st.combined_spread_bps = _spread_bps(combined_book)
        st.depth_top10_usd = _depth_usd(exec_book)

        trk.depth_hist.append(st.depth_top10_usd)
        med = float(np.median(trk.depth_hist)) if trk.depth_hist else 0.0
        st.depth_ratio = st.depth_top10_usd / (med + EPS) if med > 0 else 1.0

        imb = _imbalance(combined_book)
        trk.imb_hist.append(imb)
        st.imbalance_whiplash = float(np.std(trk.imb_hist)) if len(trk.imb_hist) >= 5 else 0.0

        bids = (combined_book.get("bids") or [])
        asks = (combined_book.get("asks") or [])
        if bids and asks:
            trk.mid_hist.append(0.5 * (bids[0][0] + asks[0][0]))

        spoof_events = self._detect_spoof_events(trk, combined_book, now)
        trk.spoof_ewma = (1 - self.ewma_alpha) * trk.spoof_ewma + self.ewma_alpha * spoof_events
        trk.events += spoof_events
        st.spoof_score = float(1.0 - np.exp(-3.0 * trk.spoof_ewma))
        st.spoof_events_total = trk.events

        # --- classify ---
        if st.spoof_score >= self.spoof_score_threshold or \
        st.imbalance_whiplash >= self.whiplash_threshold:
            st.label, st.size_mult, st.reduce_only = "spoofy", 0.0, True
        elif st.depth_top10_usd < self.min_depth_usd or st.spread_bps > self.max_spread_bps:
            st.label, st.size_mult, st.reduce_only = "thin", 0.5, False
        else:
            st.label, st.size_mult, st.reduce_only = "liquid", 1.0, False

        if st.label != "liquid":
            log.info(f"[{asset}] liquidity={st.label} spread={st.spread_bps:.1f}bps "
                    f"depth=${st.depth_top10_usd:,.0f} spoof={st.spoof_score:.2f} "
                    f"whiplash={st.imbalance_whiplash:.2f}")
        self._states[asset] = st
        return st

    # ------------------------------------------------------------------
    def _detect_spoof_events(self, trk: _AssetTracker, book: dict, now: float) -> int:
        """Count large levels that vanished young without price touching them."""
        sizes = [p * s for p, s in (book.get("bids") or [])[:self.track_levels]] + \
                [p * s for p, s in (book.get("asks") or [])[:self.track_levels]]
        if len(sizes) < 6:
            return 0
        median_usd = float(np.median(sizes))
        threshold = self.spoof_size_mult * max(median_usd, 1.0)

        current = {}
        for side, levels in (("bid", book.get("bids") or []),
                            ("ask", book.get("asks") or [])):
            for p, s in levels[:self.track_levels]:
                if p * s >= threshold:
                    current[(side, round(p, 8))] = p * s

        events = 0
        # levels that disappeared
        for key, info in list(trk.large_levels.items()):
            if key in current:
                info["seen"] = now
                continue
            side, price = key
            lifetime = now - info["first_ts"]
            del trk.large_levels[key]
            if lifetime > self.spoof_max_lifetime_s:
                continue  # rested long enough to be plausibly real
            # was price ever close enough to trade it? The sampled mid path is
            # 30s-granular, so require the level to be OUTSIDE a proximity
            # buffer of that path before calling it untouched: fills between
            # snapshots consume near-touch levels without the sampled mids
            # ever straddling them, and a consumed level is not a spoof.
            if trk.mid_hist:
                mids = np.array(trk.mid_hist)
                buf = price * (self.touch_buffer_bps / 1e4)
                touched = (mids.min() - buf) <= price <= (mids.max() + buf)
            else:
                touched = True
            if not touched:
                events += 1
                log.debug(f"spoof event: {side} {price} vanished after {lifetime:.0f}s untouched")
        # new large levels start tracking
        for key, usd in current.items():
            if key not in trk.large_levels:
                trk.large_levels[key] = {"size": usd, "first_ts": now, "seen": now}
        return events
