"""
strategies/thales.py — the lazy-bot insecurity model (docs/THALES.md).

Named for Thales of Miletus, who reserved every olive press in town for
a pittance because he could see what everyone else couldn't be bothered
to look at (Aristotle, Politics I.11). This module is a bank of
detectors for the footprints that lazily-configured trading bots leave
in public market data, plus a bounded advice channel that shades entry
confidence when those footprints line up with our signal.

Detectors (reason codes in core/codes.py, evidence in docs/THALES.md):
  TH-010 grid_ladder    — evenly spaced, size-uniform, persistent
                          resting levels (grid bots)
  TH-011 metronome_mm   — clock-driven top-of-book refresh cadence
                          (pure-MM defaults refresh on a timer)
  TH-012 clockwork_flow — recurring time-of-day flow, ONLY when it
                          beats a significance gate (anti-overfit)
  TH-013 stop_herding   — stop clusters at round numbers / swing
                          extremes; sweep-and-revert events

Influence modes (config "thales.influence"):
  off     engine dormant
  shadow  detectors run, telemetry recorded, ZERO decision influence
          (the default — promotion to advise requires shadow evidence)
  advise  bounded confidence shading, clamped to
          [1/max_conf_shade, max_conf_shade]; never touches direction,
          all_confirmed, or any risk-stack clamp

Hard boundary: detect-and-react only. This module reads public data
and shades our own firewall-gated limit entries. It never places,
spaces, or times orders to trigger anyone else's stops.

Engine discipline: no wall-clock reads (callers pass `now`), no
network, no I/O; garbage inputs degrade to neutral scores, never raise.
"""

import logging
import math
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from core.codes import Code, tag

log = logging.getLogger("liquiditybot.strategies.thales")

EPS = 1e-9


@dataclass
class ThalesShade:
    """Result of a shading request. In shadow mode `confidence` echoes
    the input and `would_mult` records the counterfactual."""
    confidence: float
    mult: float = 1.0            # multiplier actually applied
    would_mult: float = 1.0      # multiplier advise mode WOULD apply
    notes: list = field(default_factory=list)


class _AssetState:
    """Rolling per-asset detector state (in-memory; warms up live)."""

    def __init__(self, cfg: dict):
        m = cfg.get("metronome", {})
        c = cfg.get("clockwork", {})
        self.grid_score = 0.0                    # EWMA [0,1]
        self.prev_levels: set = set()
        self.metro_events: deque = deque(
            maxlen=int(m.get("window_events", 64)))
        self.prev_top = None
        self.metro_score = 0.0
        # clockwork accumulators: bucket -> [n, sum_ret, sum_ret2]
        self.buckets: dict = {}
        self.seen_bars: deque = deque(maxlen=int(c.get("max_history_bars",
                                                       4032)))
        self.seen_bar_set: set = set()
        self.candle_hist: deque = deque(maxlen=max(
            int(cfg.get("stops", {}).get("swing_lookback", 48)) + 4, 64))
        self.last_sweep: dict = {}               # {"dir": +1/-1, "ts": t}
        self.marks: deque = deque(maxlen=8)


class ThalesEngine:
    def __init__(self, config: dict):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", False))
        self.influence = str(cfg.get("influence", "shadow")).lower()
        if self.influence not in ("off", "shadow", "advise"):
            log.warning(f"thales: unknown influence "
                        f"'{self.influence}' -> shadow")
            self.influence = "shadow"
        self.max_shade = float(cfg.get("max_conf_shade", 1.15))
        self.cfg = cfg
        self._g = cfg.get("grid", {})
        self._m = cfg.get("metronome", {})
        self._c = cfg.get("clockwork", {})
        self._s = cfg.get("stops", {})
        self._assets: dict = {}
        self._counterfactuals: deque = deque(maxlen=200)

    # ------------------------------------------------------------------
    @property
    def active(self) -> bool:
        return self.enabled and self.influence != "off"

    def _st(self, asset: str) -> _AssetState:
        st = self._assets.get(asset)
        if st is None:
            st = self._assets[asset] = _AssetState(self.cfg)
        return st

    # ------------------------------------------------------------------
    # FAST-cycle observation (order book, ~5s cadence). O(levels).
    # ------------------------------------------------------------------
    def observe_fast(self, asset: str, book: dict, mark: float, now: float):
        if not self.active:
            return
        try:
            st = self._st(asset)
            if mark and math.isfinite(mark) and mark > EPS:
                st.marks.append((now, float(mark)))
            bids = (book or {}).get("bids") or []
            asks = (book or {}).get("asks") or []
            self._update_grid(st, bids, asks, mark)
            self._update_metronome(st, bids, asks, now)
        except Exception:
            log.debug("thales observe_fast degraded", exc_info=True)

    def _update_grid(self, st: _AssetState, bids: list, asks: list,
                     mark: float):
        """Grid bots rest evenly spaced, size-uniform ladders that
        persist across snapshots. MM churn near the touch does not."""
        skip = int(self._g.get("skip_top", 2))
        min_lv = int(self._g.get("min_levels", 6))
        alpha = float(self._g.get("ewma_alpha", 0.15))
        levels = []
        for side in (bids, asks):
            for row in side[skip:skip + 12]:
                try:
                    px, sz = float(row[0]), float(row[1])
                except (TypeError, ValueError, IndexError):
                    continue
                if math.isfinite(px) and math.isfinite(sz) and px > EPS:
                    levels.append((px, sz))
        snap = 0.0
        if len(levels) >= min_lv:
            reg = []
            for half in (sorted(px for px, _ in levels if mark and px <= mark),
                         sorted(px for px, _ in levels if not mark or px > mark)):
                gaps = np.diff(np.asarray(half, float))
                gaps = gaps[gaps > EPS]
                if len(gaps) >= 3:
                    cv = float(gaps.std() / (gaps.mean() + EPS))
                    reg.append(max(0.0, 1.0 - cv))
            sizes = np.asarray([sz for _, sz in levels], float)
            size_cv = float(sizes.std() / (sizes.mean() + EPS))
            size_reg = max(0.0, 1.0 - size_cv)
            if reg:
                # persistence: fraction of resting levels unchanged
                # since the previous snapshot (Jaccard)
                cur = {round(px, 8) for px, _ in levels}
                inter = len(cur & st.prev_levels)
                union = len(cur | st.prev_levels) or 1
                persist = inter / union
                st.prev_levels = cur
                snap = float(np.mean(reg)) * (0.5 + 0.5 * size_reg) * persist
            else:
                st.prev_levels = {round(px, 8) for px, _ in levels}
        st.grid_score = (1 - alpha) * st.grid_score + alpha * min(snap, 1.0)

    def _update_metronome(self, st: _AssetState, bids: list, asks: list,
                          now: float):
        """Timer-driven MMs replace the touch at near-constant
        intervals; event-driven flow arrives Poisson-ish. Low CV of
        inter-replacement intervals = clock-quoting."""
        try:
            top = (round(float(bids[0][0]), 8), round(float(bids[0][1]), 6),
                   round(float(asks[0][0]), 8), round(float(asks[0][1]), 6))
        except (TypeError, ValueError, IndexError):
            return
        if st.prev_top is not None and top != st.prev_top:
            st.metro_events.append(now)
        st.prev_top = top
        min_ev = int(self._m.get("min_events", 8))
        if len(st.metro_events) >= min_ev:
            iv = np.diff(np.asarray(st.metro_events, float))
            iv = iv[iv > EPS]
            min_iv = float(self._m.get("min_interval_sec", 8.0))
            if len(iv) >= min_ev - 1 and float(np.median(iv)) >= min_iv:
                cv = float(iv.std() / (iv.mean() + EPS))
                st.metro_score = max(0.0, min(1.0, 1.0 - cv))
            else:
                # sub-interval churn: cannot separate clock from event
                # flow at our sampling cadence — stay neutral
                st.metro_score = 0.0

    # ------------------------------------------------------------------
    # SLOW-cycle observation (candles). Deduped by bar timestamp.
    # ------------------------------------------------------------------
    def observe_candles(self, asset: str, candles: list, now: float):
        if not self.active or not candles:
            return
        try:
            st = self._st(asset)
            for bar in candles:
                try:
                    ts = float(bar.get("ts") or bar.get("time") or 0.0)
                    o = float(bar.get("open") or 0.0)
                    c = float(bar.get("close") or 0.0)
                    hi = float(bar.get("high") or max(o, c))
                    lo = float(bar.get("low") or min(o, c))
                except (TypeError, ValueError, AttributeError):
                    continue
                if ts <= 0 or o <= EPS or c <= EPS:
                    continue
                if ts in st.seen_bar_set:
                    continue
                if len(st.seen_bars) == st.seen_bars.maxlen:
                    st.seen_bar_set.discard(st.seen_bars[0])
                st.seen_bars.append(ts)
                st.seen_bar_set.add(ts)
                st.candle_hist.append((ts, o, hi, lo, c))
                ret = (c / o - 1.0) * 100.0
                bmin = int(self._c.get("bucket_minutes", 60))
                bucket = int((ts % 86400) // (bmin * 60))
                n, s, s2 = st.buckets.get(bucket, (0, 0.0, 0.0))
                st.buckets[bucket] = (n + 1, s + ret, s2 + ret * ret)
        except Exception:
            log.debug("thales observe_candles degraded", exc_info=True)

    # ------------------------------------------------------------------
    # detector reads
    # ------------------------------------------------------------------
    def _clockwork(self, st: _AssetState, now: float) -> tuple:
        """(score [0,1], direction ±1) for the CURRENT bucket, only if
        its mean return clears a t-gate vs the pooled distribution.
        Insignificant seasonality scores 0 — by construction."""
        bmin = int(self._c.get("bucket_minutes", 60))
        min_obs = int(self._c.get("min_obs", 24))
        z_thr = float(self._c.get("z_thr", 2.33))
        bucket = int((now % 86400) // (bmin * 60))
        n, s, s2 = st.buckets.get(bucket, (0, 0.0, 0.0))
        if n < min_obs:
            return 0.0, 0
        tot_n = sum(v[0] for v in st.buckets.values())
        tot_s = sum(v[1] for v in st.buckets.values())
        tot_s2 = sum(v[2] for v in st.buckets.values())
        if tot_n < 2 * min_obs:
            return 0.0, 0
        pooled_mu = tot_s / tot_n
        pooled_var = max(tot_s2 / tot_n - pooled_mu ** 2, EPS)
        mu_b = s / n
        z = (mu_b - pooled_mu) / math.sqrt(pooled_var / n)
        if abs(z) < z_thr:
            return 0.0, 0
        score = min(1.0, (abs(z) - z_thr) / z_thr)
        return score, (1 if z > 0 else -1)

    def _stop_zones(self, st: _AssetState, mark: float) -> tuple:
        """(proximity [0,1], sweep_dir ±1/0). Proximity: how close the
        mark sits to a stop-cluster magnet (round number or swing
        extreme). Sweep: last bar pierced a magnet then closed back."""
        if not mark or not math.isfinite(mark) or mark <= EPS:
            return 0.0, 0
        tol = float(self._s.get("zone_tol_pct", 0.15)) / 100.0
        zones = []
        # self-scaling round-number grid: steps {1, 2.5, 5}x10^k that
        # land between 0.3% and 3% of price (Osler clustering)
        k = 10.0 ** math.floor(math.log10(mark))
        for step in (k / 100, k / 40, k / 20, k / 10, k / 4, k / 2):
            if 0.003 * mark <= step <= 0.03 * mark:
                zones.append(round(mark / step) * step)
        lookback = int(self._s.get("swing_lookback", 48))
        hist = list(st.candle_hist)[-lookback:]
        if len(hist) >= 8:
            zones.append(max(h for _, _, h, _, _ in hist))
            zones.append(min(low for _, _, _, low, _ in hist))
        prox = 0.0
        for z in zones:
            d = abs(mark - z) / mark
            if d < tol:
                prox = max(prox, 1.0 - d / tol)
        sweep = 0
        if len(hist) >= 2:
            ts, o, hi, lo, c = hist[-1]
            prior = hist[:-1]
            prior_hi = max(h for _, _, h, _, _ in prior)
            prior_lo = min(low for _, _, _, low, _ in prior)
            if hi > prior_hi and c < prior_hi:
                sweep = +1        # swept the highs, closed back inside
            elif lo < prior_lo and c > prior_lo:
                sweep = -1        # swept the lows, closed back inside
            if sweep:
                st.last_sweep = {"dir": sweep, "ts": ts}
        return prox, sweep

    # ------------------------------------------------------------------
    # advice
    # ------------------------------------------------------------------
    def shade_confidence(self, asset: str, direction: str, urgency: float,
                         confidence: float, macro_label: str,
                         now: float) -> ThalesShade:
        """Compose detector scores into one bounded multiplier. Shadow
        mode records the counterfactual and returns confidence
        untouched. Never returns direction; never exceeds clamps."""
        out = ThalesShade(confidence=float(confidence))
        if not self.active or direction not in ("long", "short"):
            return out
        try:
            st = self._st(asset)
            mark = st.marks[-1][1] if st.marks else 0.0
            d = 1 if direction == "long" else -1
            trending = str(macro_label or "").lower() in (
                "trend", "trending", "bull", "bear", "momentum",
                "trend_up", "trend_down")
            mult = 1.0

            g_thr = float(self._g.get("score_thr", 0.55))
            if st.grid_score > g_thr and trending:
                mult *= 1.0 + float(self._g.get("gain", 0.5)) * (
                    st.grid_score - g_thr)
                out.notes.append(tag(Code.TH_GRID_LADDER,
                                     f"grid={st.grid_score:.2f} vs trend"))

            m_thr = float(self._m.get("score_thr", 0.6))
            if (st.metro_score > m_thr
                    and urgency >= float(self._m.get("urgency_min", 0.5))):
                mult *= 1.0 + float(self._m.get("gain", 0.4)) * (
                    st.metro_score - m_thr)
                out.notes.append(tag(Code.TH_METRONOME_MM,
                                     f"metro={st.metro_score:.2f} stale-quote edge"))

            c_score, c_dir = self._clockwork(st, now)
            if c_score > 0 and c_dir == d:
                mult *= 1.0 + float(self._c.get("gain", 0.06)) * c_score
                out.notes.append(tag(Code.TH_CLOCKWORK_FLOW,
                                     f"bucket flow z-gated score={c_score:.2f}"))

            prox, _ = self._stop_zones(st, mark)
            if prox > 0.5:
                # shade DOWN: our stop would join the herd's cluster
                mult *= 1.0 - float(self._s.get("pre_gain", 0.1)) * (
                    prox - 0.5) * 2.0
                out.notes.append(tag(Code.TH_STOP_SWEEP,
                                     f"stop-cluster proximity {prox:.2f}: "
                                     f"not the lemming"))
            sweep = st.last_sweep
            decay = float(self._s.get("revert_decay_sec", 1800))
            if sweep and (now - float(sweep.get("ts", 0))) < decay:
                if int(sweep.get("dir", 0)) == -d:
                    # cluster consumed; fade the overshoot while fresh
                    age = (now - float(sweep["ts"])) / decay
                    mult *= 1.0 + float(self._s.get("post_gain", 0.1)) * (
                        1.0 - age)
                    out.notes.append(tag(Code.TH_STOP_SWEEP,
                                         f"post-sweep revert window "
                                         f"({1 - age:.0%} left)"))

            lo, hi = 1.0 / self.max_shade, self.max_shade
            mult = max(lo, min(hi, mult))
            out.would_mult = mult
            if self.influence == "advise" and abs(mult - 1.0) > 1e-6:
                out.mult = mult
                out.confidence = max(0.0, min(1.0, confidence * mult))
                out.notes.append(tag(Code.TH_CONF_SHADE,
                                     f"conf x{mult:.3f}"))
            else:
                out.notes.insert(0, tag(Code.TH_SHADOW, f"would x{mult:.3f}"))
            if abs(mult - 1.0) > 1e-6:
                self._counterfactuals.append({
                    "ts": round(now, 1), "asset": asset, "dir": direction,
                    "mult": round(mult, 4), "applied":
                        self.influence == "advise",
                    "scores": self._scores(st, now)})
        except Exception:
            log.debug("thales shade degraded to neutral", exc_info=True)
        return out

    # ------------------------------------------------------------------
    # telemetry
    # ------------------------------------------------------------------
    def _scores(self, st: _AssetState, now: float) -> dict:
        c_score, c_dir = self._clockwork(st, now)
        mark = st.marks[-1][1] if st.marks else 0.0
        prox, _ = self._stop_zones(st, mark)
        return {"grid": round(st.grid_score, 3),
                "metronome": round(st.metro_score, 3),
                "clockwork": round(c_score, 3), "clockwork_dir": c_dir,
                "stop_zone": round(prox, 3)}

    def status(self, now: float) -> dict:
        if not self.enabled:
            return {"influence": "off"}
        try:
            return {"influence": self.influence,
                    "assets": {a: self._scores(st, now)
                               for a, st in self._assets.items()},
                    "recent_advice": list(self._counterfactuals)[-5:]}
        except Exception:
            log.debug("thales status degraded", exc_info=True)
            return {"influence": self.influence, "assets": {}}
