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
import math
import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np
from typing import Optional

from core.codes import Code, tag

log = logging.getLogger("liquiditybot.regime.liquidity")

EPS = 1e-9


@dataclass
class LiquidityState:
    asset: str
    label: str = "liquid"            # liquid | thin | spoofy
    spread_bps: float = 5.0          # execution venue (Kraken) spread
    combined_spread_bps: float = 5.0
    combined_crossed: bool = False   # merged street book bid>=ask (DL-2)
    depth_top10_usd: float = 0.0     # Kraken two-sided depth
    depth_ratio: float = 1.0         # vs trailing median depth
    imbalance_whiplash: float = 0.0  # std of imbalance ratio, recent window
    imbalance_ratio: float = 1.0     # decayed Kraken-book imbalance (the flow
                                     # scalar; surfaced to the view so the alpha
                                     # can evaluate Kraken-only listings — v9)
    tier: str = "core"               # liquidity cap-tier (core|mid|micro),
                                     # derived from trailing-median depth (v9)
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
    # W2-11: was the PRIOR cycle a fresh-Kraken observation? Used to reseed
    # large_levels on recovery from a no-Kraken gap instead of diffing the
    # recovered book against whatever was tracked before/through the gap.
    kraken_fresh_prev: bool = True


def _spread_bps(book: dict) -> float:
    bids, asks = book.get("bids") or [], book.get("asks") or []
    if not bids or not asks:
        return 999.0
    bb, ba = bids[0][0], asks[0][0]
    # DL-2: a CROSSED book (bid >= ask) is garbage, not tight. Single-
    # venue books are rejected upstream by clean_book, but the price-
    # merged multi-venue book can cross legitimately-looking levels
    # from different venues (USDT-perp vs USD-spot basis) - the old
    # max(...,0.0) turned that into spread=0.0, a fake ULTRA-TIGHT
    # book that masked the max_spread_bps entry veto and poisoned the
    # spread features. Crossed = unmeasurable = the same fail-closed
    # sentinel as a one-sided book.
    if bb >= ba:
        return 999.0
    mid = 0.5 * (bb + ba)
    return max((ba - bb) / (mid + EPS) * 1e4, 0.0)


def _depth_usd(book: dict, levels: int = 10) -> float:
    bids = book.get("bids") or []
    asks = book.get("asks") or []
    return (sum(p * s for p, s in bids[:levels]) +
            sum(p * s for p, s in asks[:levels]))


def _decayed_notional(side: list, levels: int, decay_bps: float) -> float:
    """Top-N notional with exponential distance decay toward the side's
    OWN best (spoof economics, Stoikov 2018 / Cont-Kukanov-Stoikov: size
    far from the touch is cheap to paint and cancel - layering; size at
    the touch gets executed, so near-touch depth carries the information).
    Each level's p*s is weighted exp(-dist_bps / decay_bps), dist measured
    against the side's own best (book SHAPE only - the spread is not
    counted, so a wide-but-honest book is not penalized). decay_bps <= 0
    reproduces the legacy equal-weight sum byte-identically."""
    if decay_bps <= 0.0 or not side or side[0][0] <= 0:
        return sum(p * s for p, s in side[:levels])
    best = side[0][0]
    return sum(p * s * math.exp(-(abs(p - best) / best * 1e4) / decay_bps)
               for p, s in side[:levels])


def _imbalance(book: dict, levels: int = 10, decay_bps: float = 0.0) -> float:
    bids = book.get("bids") or []
    asks = book.get("asks") or []
    b = _decayed_notional(bids, levels, decay_bps)
    a = _decayed_notional(asks, levels, decay_bps)
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
        # v8 anti-layering: distance-decay half-life (bps from each side's
        # own best) for the imbalance notional. A painted far-from-touch
        # wall decays toward zero weight instead of dragging the ratio;
        # 0 disables (exact legacy equal-weight). Ratio is shape-invariant
        # under symmetric books, so the whiplash calibration above holds.
        self.imbalance_decay_bps = float(cfg.get("imbalance_decay_bps", 15.0))

        # --- v9 liquidity-tier isolation ---------------------------------
        # An asset is classified into a cap-tier from its OWN trailing-median
        # Kraken top-10 depth; the tier scales ONLY the two categorical
        # executability floors (depth / spread). CORE reproduces the legacy
        # flat floors byte-identically, so ETH/BTC — and quant_trials /
        # overfit — never move; MID/MICRO lower the ceilings so a low-volume
        # asset is judged on its own scale and REACHES the honest EV gate
        # (which stays flat). Tier is a DERIVED category (median depth vs the
        # tier floors), never a hardcoded symbol map — overfit discipline.
        tcfg = cfg.get("tiers") or {}
        self.tiers_enabled = bool(tcfg.get("enabled", False))
        order = tcfg.get("order") or ["core", "mid", "micro"]
        tiers = []
        for name in order:
            t = tcfg.get(name) or {}
            tiers.append((
                str(name),
                float(t.get("min_depth_usd", self.min_depth_usd)),
                float(t.get("max_spread_bps", self.max_spread_bps)),
            ))
        tiers.sort(key=lambda x: x[1], reverse=True)   # richest tier first
        self._tiers = tiers if (self.tiers_enabled and tiers) else [
            ("core", self.min_depth_usd, self.max_spread_bps)]
        # hysteresis dead-band: once assigned, a tier is only vacated when the
        # median clears the relevant boundary by this fraction — so an asset
        # whose median drifts across a boundary does not flicker its tier (and
        # its size_mult / spread ceiling / LT-010 log) cycle-to-cycle.
        self.tier_hysteresis_frac = max(float(tcfg.get("hysteresis_frac", 0.15)),
                                        0.0)

        self._trk: dict = {}
        self._states: dict = {}

    def state(self, asset: str) -> LiquidityState:
        return self._states.get(asset) or LiquidityState(asset=asset)

    def _tier_for(self, median_depth_usd: float,
                  prev: Optional[str] = None) -> tuple:
        """(name, min_depth_usd, max_spread_bps) for the RICHEST tier whose
        depth floor the asset's trailing-median depth clears. The thinnest
        tier is the fallback, so a sub-floor asset is still judged on the
        gentlest scale rather than the majors'.

        With a prior tier and a hysteresis band, the asset STAYS in `prev`
        until the median clears the boundary by tier_hysteresis_frac — the
        dead-band that stops boundary-hugging assets from flickering tiers."""
        raw = next((e for e in self._tiers                 # descending floor
                    if median_depth_usd >= e[1]), self._tiers[-1])
        if prev is None or self.tier_hysteresis_frac <= 0.0:
            return raw
        prev_entry = next((e for e in self._tiers if e[0] == prev), None)
        if prev_entry is None or raw[0] == prev_entry[0]:
            return raw
        h = self.tier_hysteresis_frac
        if raw[1] > prev_entry[1]:            # promotion: clear richer floor +h
            return raw if median_depth_usd >= raw[1] * (1.0 + h) else prev_entry
        # demotion: drop below prev's OWN floor by -h before giving up the tier
        return raw if median_depth_usd < prev_entry[1] * (1.0 - h) else prev_entry

    # ------------------------------------------------------------------
    def update(self, asset: str, combined_book: dict, kraken_book: dict,
            now: Optional[float] = None) -> LiquidityState:
        now = now if now is not None else time.time()
        trk = self._trk.setdefault(asset, _AssetTracker())
        st = self._states.get(asset) or LiquidityState(asset=asset)

        # W2-11: kraken_fresh gates every STATEFUL history below. main.py
        # (DL-10) hands us kraken_book={} once the Kraken book passes
        # watchdog.stale_critical_sec, with external feeds (OKX/Binance.US)
        # still live in combined_book. A no-fresh-Kraken cycle is a
        # NO-OBSERVATION cycle for depth_hist/imb_hist/mid_hist/large_levels —
        # the combined book is a different venue mix (external-scale depth,
        # different quote/perp-spot basis) and must never be treated as an
        # exec-book sample. exec_book itself still falls back to combined_book
        # so spread/depth/tier stay informative (display/label) during the
        # gap, exactly as before.
        kraken_fresh = bool(kraken_book and kraken_book.get("bids"))
        exec_book = kraken_book if kraken_fresh else combined_book
        st.spread_bps = _spread_bps(exec_book)
        st.combined_spread_bps = _spread_bps(combined_book)
        _cb, _ca = (combined_book.get("bids") or []), \
            (combined_book.get("asks") or [])
        st.combined_crossed = bool(_cb and _ca and _cb[0][0] >= _ca[0][0])
        st.depth_top10_usd = _depth_usd(exec_book)

        # only REAL depth observations feed the trailing median: appending the
        # 0.0 of an empty/stale book would drag an asset's structural depth
        # (and thus its tier) down during an outage and keep it there until the
        # zeros flush — relaxing a major's floor exactly in the volatile
        # recovery window. The instantaneous reading below still flags collapse.
        # A no-fresh-Kraken cycle is likewise skipped outright (no-observation,
        # W2-11): the "REAL depth" requirement means a real KRAKEN depth, not
        # combined-book notional standing in for it.
        if kraken_fresh and st.depth_top10_usd > 0.0:
            trk.depth_hist.append(st.depth_top10_usd)
        med = float(np.median(trk.depth_hist)) if trk.depth_hist else 0.0
        st.depth_ratio = st.depth_top10_usd / (med + EPS) if med > 0 else 1.0

        # v9 cap-tier from the STRUCTURAL (trailing-median) depth, not the
        # instantaneous depth — an asset's tier must not flip snapshot to
        # snapshot; "is depth unusually low right now" is depth_ratio's job.
        # Hysteresis (prev tier) pins a boundary-hugging asset against flicker.
        prev_tier = st.tier
        tier_name, tier_min_depth, tier_max_spread = self._tier_for(med, prev_tier)
        st.tier = tier_name
        if self.tiers_enabled and tier_name != prev_tier:
            log.info("%s", tag(Code.LT_TIER_ASSIGNED,
                     f"{asset} {prev_tier}->{tier_name} "
                     f"(median depth ${med:,.0f}; floor "
                     f"${tier_min_depth:,.0f}/{tier_max_spread:.0f}bps)"))

        # imbalance / whiplash / mid-track / spoof all read the EXECUTION book
        # (Kraken), NOT the combined book. combined_book price-sorts OKX-USDT
        # perp levels together with Binance.US-USD spot levels (different quote
        # currency + perp/spot basis); a few-bps offset that flips sign around
        # zero flips which venue owns the merged touch, so its imbalance
        # square-waves between the two venues' depths - artificial whiplash
        # that tripped a false 'spoofy' size-veto on BTC/ETH (SD-003; ~15% of
        # the majors' manip_suspect rows). The whiplash/spoof thresholds were
        # calibrated on single-venue books anyway, so the coherent exec book
        # is both correct and on-distribution. Depth (a USD sum, USDT~USD) and
        # combined_spread_bps stay on the combined book as informational.
        #
        # W2-11: without a fresh Kraken touch there is no exec-book sample at
        # all this cycle. imb_hist/mid_hist/large_levels hold their prior
        # state untouched (no-observation) rather than absorb the combined
        # book's different-venue imbalance/levels; imbalance_ratio and
        # imbalance_whiplash likewise hold their last real-Kraken reading.
        if kraken_fresh:
            imb = _imbalance(exec_book, decay_bps=self.imbalance_decay_bps)
            st.imbalance_ratio = imb      # the flow scalar the alpha reads
            trk.imb_hist.append(imb)
            st.imbalance_whiplash = float(np.std(trk.imb_hist)) if len(trk.imb_hist) >= 5 else 0.0

            bids = (exec_book.get("bids") or [])
            asks = (exec_book.get("asks") or [])
            if bids and asks:
                trk.mid_hist.append(0.5 * (bids[0][0] + asks[0][0]))

            if not trk.kraken_fresh_prev:
                # recovering from a no-Kraken gap: reseed large-level tracking
                # from the fresh book instead of diffing it against whatever
                # was tracked through the gap (never combined-era in the fixed
                # code, but reseeding is the honest recovery contract either
                # way — no vanish-events fabricated off a stale reference).
                trk.large_levels = {}
            spoof_events = self._detect_spoof_events(trk, exec_book, now)
        else:
            spoof_events = 0
        trk.kraken_fresh_prev = kraken_fresh

        trk.spoof_ewma = (1 - self.ewma_alpha) * trk.spoof_ewma + self.ewma_alpha * spoof_events
        trk.events += spoof_events
        st.spoof_score = float(1.0 - np.exp(-3.0 * trk.spoof_ewma))
        st.spoof_events_total = trk.events

        # --- classify ---
        if st.spoof_score >= self.spoof_score_threshold or \
        st.imbalance_whiplash >= self.whiplash_threshold:
            st.label, st.size_mult, st.reduce_only = "spoofy", 0.0, True
        elif st.depth_top10_usd < tier_min_depth or st.spread_bps > tier_max_spread:
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
