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
  TH-016 observation_lapse — gaps in OUR OWN observation stream break
                          evidence continuity: reset + advice warmup
                          (detector-of-self; lived 2026-07-14)

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
from strategies.swing_points import Candle, swing_high_low

log = logging.getLogger("liquiditybot.strategies.thales")

EPS = 1e-9

# which way each WEIGHTED detector advises (static by construction - see
# the shade_confidence fired.append sites). Used by status() to compute
# each detector's reliability weight against the correct base-rate null
# (A-1: 'up' advice is nulled by the base WIN rate, 'down' by the base
# LOSS rate). The unweighted safety shades (spoof flicker, feed
# integrity) never appear in the ledger.
_DETECTOR_ADVICE = {"grid": "up", "metronome": "up", "clockwork": "up",
                    "stop_revert": "up", "stop_prox": "down"}


def round_number_grid(mark: float) -> list[float]:
    """Self-scaling round-number magnet grid: steps {1, 2.5, 5, 10, 25,
    50}x10^k that land between 0.3% and 3% of `mark` (Osler clustering).
    Extracted VERBATIM from `_stop_zones` (task C3, Compounder Phase C:
    the `_refresh_market_state` precedent - moved lines unchanged, only
    re-scoped) so risk/long_book.py's LongBookEngine can reuse the exact
    same magnet grid for TH-013 bid-hygiene without depending on
    `_AssetState`/candle history (this half of the original computation
    only ever needed `mark`; the swing-extreme magnets stay inline in
    `_stop_zones` because those DO need `_AssetState`). Pure, stateless,
    never raises: `mark <= 0` (or non-finite) returns `[]`."""
    if not mark or not math.isfinite(mark) or mark <= 0:
        return []
    return [round(mark / step) * step for step in _round_number_steps(mark)]


def _round_number_steps(mark: float) -> list[float]:
    """The accepted round-number STEP sizes for `mark` (the grid
    spacings behind round_number_grid's nearest-magnet-per-step list).
    Split out 2026-07-29 so _stop_zones can compute the proximity
    score's geometric null from the finest spacing (A-2) without
    re-deriving the step constants. Pure; `mark <= 0` returns []."""
    if not mark or not math.isfinite(mark) or mark <= 0:
        return []
    k = 10.0 ** math.floor(math.log10(mark))
    return [step for step in (k / 100, k / 40, k / 20, k / 10, k / 4, k / 2)
            if 0.003 * mark <= step <= 0.03 * mark]


@dataclass
class ThalesShade:
    """Result of a shading request. In shadow mode `confidence` echoes
    the input and `would_mult` records the counterfactual."""
    confidence: float
    mult: float = 1.0            # multiplier actually applied
    would_mult: float = 1.0      # multiplier advise mode WOULD apply
    notes: list = field(default_factory=list)
    # V2 vindication loop: which detectors influenced this shade and in
    # which direction ("up" boosted confidence / "down" shaded it). The
    # engine's note_outcome() grades each against the trade's result.
    fired: list = field(default_factory=list)


class _AssetState:
    """Rolling per-asset detector state (in-memory; warms up live)."""

    def __init__(self, cfg: dict):
        m = cfg.get("metronome", {})
        c = cfg.get("clockwork", {})
        self.grid_score = 0.0                    # EWMA [0,1]
        self.prev_levels: set = set()
        self.metro_events: deque = deque(
            maxlen=int(m.get("window_events", 64)))
        self.prev_top: tuple | None = None
        self.metro_score = 0.0
        # clockwork accumulators: bucket -> [n, sum_ret, sum_ret2]
        self.buckets: dict = {}
        self.seen_bars: deque = deque(maxlen=int(c.get("max_history_bars",
                                                       4032)))
        self.seen_bar_set: set = set()
        bc = cfg.get("barclose", {})
        self.bc_nb = int(bc.get("buckets", 10))
        self.bc_bar_sec = float(bc.get("bar_sec", 300.0))
        self.bc_min_events = float(bc.get("min_events", 120.0))
        self.bc_buckets = [0.0] * self.bc_nb
        self.bc_prev_top: tuple | None = None
        self.bc_last_bar = -1
        # typed with the shared Candle shape (strategies/swing_points):
        # a bare `deque` erased the element type at the one place that
        # FEEDS swing_high_low, so annotating only the callee would have
        # left the producer end unknown.
        self.candle_hist: "deque[Candle]" = deque(maxlen=max(
            int(cfg.get("stops", {}).get("swing_lookback", 48)) + 4, 64))
        self.last_sweep: dict = {}               # {"dir": +1/-1, "ts": t}
        self.zone_degenerate = False             # tick grid >= tol band
        self.marks: deque = deque(maxlen=8)
        # TH-016 observation-lapse hygiene (docs/THALES.md). Continuity
        # bookkeeping so a gap in OUR OWN observation stream is treated as
        # broken evidence, never as adjacent snapshots.
        self.last_fast_ts = 0.0                  # newest fast observation
        self.lapse_until = 0.0                   # advice muted until here
        self.lapse_count = 0                     # fast-stream lapses (telemetry)
        self.sweep_fence_ts = 0.0                # sweeps older than this never latch
        self.last_bar_ts = 0.0                   # ts of last accepted candle
        self.bar_spacing = 0.0                   # EWMA of candle spacing
        self.bar_hole_count = 0                  # venue-side candle holes fenced
        # TH-017 spoof-flicker: previous snapshot's large top-of-book
        # levels per side ({price: size}) and a bounded EWMA of vanish-
        # without-trade events. Spoofers operate through top-of-book
        # imbalance (Cartea-Jaimungal-Wang); their footprint in snapshot
        # data is a LARGE level that appears then vanishes while the mid
        # never crossed it (nothing consumed it - it was pulled).
        self.spoof_prev: dict = {"bids": {}, "asks": {}}
        self.spoof_ewma: dict = {"bids": 0.0, "asks": 0.0}
        self.spoof_last_ts: float = 0.0   # wall-clock of the last spoof
        # observation (A-3 cadence normalization; 0.0 = none yet)
        # feed-integrity window: 1 = clean book this cycle, 0 = missing or
        # sanitize-rejected. A sustained low clean-rate means a hostile or
        # unreliable venue for THIS asset -> shade its confidence down.
        fi = cfg.get("feed_integrity", {})
        self.feed_obs: deque = deque(maxlen=int(fi.get("window", 40)))


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
        self._fi = cfg.get("feed_integrity", {})
        self._sp = cfg.get("spoof", {})
        self._lp = cfg.get("lapse", {})
        self._assets: dict = {}
        self._counterfactuals: deque = deque(maxlen=200)
        # ---- V2 reliability ledger (evidence-weighted gains) ------------
        # V1 composed detectors with FIXED config gains — hand-crafted
        # priors that nothing ever validated. V2 closes the loop: every
        # closed trade grades the detectors that advised on its entry
        # (note_outcome), and each detector's gain is scaled by an
        # evidence weight = the normalized LIFT of its vindication
        # WilsonLCB over the contemporaneous outcome base rate (the
        # __base__ ledger; 2026-07-29 A-1 correction — the original
        # max(0, 2*LCB - 1) graded against a 0.5 coin-flip null, the
        # wrong units for a ~16%-win outcome stream: honest up-detectors
        # were muted at exactly min_fired while no-skill down-detectors
        # kept ~0.44 weight). Cold start (either ledger < min_fired)
        # -> w = 1.0, EXACT V1 behavior; a detector with no lift over
        # base loses its voice (w -> 0) but KEEPS BEING GRADED (probation,
        # not a life sentence); weights only ATTENUATE, never amplify
        # beyond the configured gain (amplification is knob-tuning and
        # belongs to the gated tuning pass, not a live feedback loop).
        rel = cfg.get("reliability", {})
        self.rel_enabled = bool(rel.get("enabled", True))
        self.rel_min_fired = int(rel.get("min_fired", 20))
        self._rel: dict = {}     # detector -> {"fired": n, "vindicated": k}

    # ------------------------------------------------------------------
    @property
    def active(self) -> bool:
        return self.enabled and self.influence != "off"

    # ---- V2 reliability -------------------------------------------------
    @staticmethod
    def _wilson_lcb(k: int, n: int, z: float = 1.28) -> float:
        """Lower confidence bound on a proportion (z=1.28 ~ 90%): honest
        with small samples — 3/3 is not 'always right'."""
        if n <= 0:
            return 0.0
        p = k / n
        z2 = z * z
        denom = 1.0 + z2 / n
        centre = p + z2 / (2 * n)
        margin = z * ((p * (1 - p) + z2 / (4 * n)) / n) ** 0.5
        return max(0.0, (centre - margin) / denom)

    def _rel_weight(self, key: str, advice: str = "up") -> float:
        """Evidence weight for a detector's gain. 1.0 until min_fired
        grades exist on BOTH the detector and the shared base ledger
        (the hand-crafted prior rules cold start); then the normalized
        LIFT of the detector's Wilson LCB over the contemporaneous BASE
        RATE of its vindication event.

        2026-07-29 unit-audit correction (THALES A-1): the old weight
        max(0, 2*LCB - 1) graded vindication against a 0.5 COIN-FLIP
        null, but vindication proportions live in outcome-base-rate
        units - at the measured 15.8% live win rate an 'up' detector
        with a genuine 2x win-rate lift (32% when firing) hit weight
        0.000 at exactly min_fired grades (muted), while a
        zero-information 'down' detector (vindicated at the 84% loss
        rate) kept ~0.44 weight. Same defect family as the CVaR 5s/5m
        clock and the payoff flat-sum: a number compared against a null
        in the wrong units. Correct null: base WIN rate for 'up' advice,
        base LOSS rate for 'down' - both from the __base__ ledger
        note_outcome maintains over every graded close. Under it the
        no-skill down detector scores 0 (LCB 0.722 < null 0.842) and
        the 2x-lift up detector keeps a small, n-growing voice
        (LCB 0.188 > null 0.158)."""
        if not self.rel_enabled:
            return 1.0
        r = self._rel.get(key)
        if not r or r.get("fired", 0) < self.rel_min_fired:
            return 1.0
        base = self._rel.get("__base__")
        if not base or int(base.get("fired", 0)) < self.rel_min_fired:
            return 1.0     # no honest null yet -> the prior keeps ruling
        base_win = float(base.get("vindicated", 0)) / max(
            int(base["fired"]), 1)
        null = base_win if advice == "up" else 1.0 - base_win
        null = min(max(null, 0.0), 1.0 - 1e-9)
        lcb = self._wilson_lcb(int(r.get("vindicated", 0)),
                               int(r["fired"]))
        return min(1.0, max(0.0, (lcb - null) / (1.0 - null)))

    def note_outcome(self, fired: list, won: bool) -> None:
        """Grade every detector that shaded a now-closed trade's entry.
        'up' advice is vindicated by a WIN, 'down' advice by a LOSS.
        Also maintains the __base__ ledger (one grade per closed trade,
        fired-or-not) - the contemporaneous outcome base rate that
        _rel_weight uses as its null (A-1 correction above). Callers
        should invoke this on EVERY graded close, including ones where
        no detector fired (empty list), so the null stays unbiased.
        Fail-safe: junk entries are ignored, never raised."""
        try:
            base = self._rel.setdefault("__base__",
                                        {"fired": 0, "vindicated": 0})
            base["fired"] += 1
            if bool(won):
                base["vindicated"] += 1
            for item in fired or []:
                if not (isinstance(item, (list, tuple)) and len(item) == 2):
                    continue
                key, advice = str(item[0]), str(item[1])
                if advice not in ("up", "down"):
                    continue
                r = self._rel.setdefault(key, {"fired": 0, "vindicated": 0})
                r["fired"] += 1
                if (advice == "up") == bool(won):
                    r["vindicated"] += 1
        except Exception:
            log.debug("thales note_outcome degraded", exc_info=True)

    def reliability_to_dict(self) -> dict:
        return {k: dict(v) for k, v in self._rel.items()}

    def reliability_restore(self, d: dict) -> None:
        try:
            for k, v in (d or {}).items():
                self._rel[str(k)] = {"fired": int(v.get("fired", 0)),
                                     "vindicated": int(v.get("vindicated",
                                                             0))}
        except (AttributeError, TypeError, ValueError):
            log.warning("thales reliability restore skipped (malformed)")

    def _st(self, asset: str) -> _AssetState:
        st = self._assets.get(asset)
        if st is None:
            st = self._assets[asset] = _AssetState(self.cfg)
        return st

    # ------------------------------------------------------------------
    # FAST-cycle observation (order book, ~5s cadence). O(levels).
    # ------------------------------------------------------------------
    def _check_lapse(self, st: _AssetState, asset: str, now: float):
        """TH-016 observation-lapse hygiene. The caller only observes when
        a clean book actually arrived, so a large gap between consecutive
        observations means OUR OWN stream broke (proxy outage, pause,
        feed severance, restart with surviving state — all lived on
        2026-07-14). Detectors that compare this snapshot against pre-gap
        memory would manufacture evidence from a discontinuity, and the
        advice channel would act on stale footprints at full confidence:
        reset the continuity state and mute advice through a warmup.
        Clock regression (now jumping backwards) breaks continuity the
        same way and is treated identically."""
        gap = float(self._lp.get("fast_gap_sec", 600.0))
        skew = float(self._lp.get("clock_skew_tol_sec", 1.0))
        last = st.last_fast_ts
        st.last_fast_ts = now
        if last <= 0:
            return                    # first observation: cold start, no gap
        if (now - last) <= gap and now >= last - skew:
            return
        st.lapse_count += 1
        st.lapse_until = now + float(self._lp.get("warmup_sec", 900.0))
        # continuity-dependent memory is fiction across the gap
        st.prev_top = None
        st.prev_levels = set()
        st.metro_events.clear()
        st.metro_score = 0.0          # its evidence deque just vanished
        st.bc_prev_top = None
        st.last_sweep = {}            # a pre-gap sweep must not advise now
        st.sweep_fence_ts = now       # ...nor re-latch from surviving
        st.marks.clear()              # pre-gap candle_hist via _stop_zones
        st.spoof_prev = {"bids": {}, "asks": {}}   # TH-017: gap-straddling
        st.spoof_ewma = {"bids": 0.0, "asks": 0.0}  # vanish events are fiction
        st.spoof_last_ts = 0.0    # A-3 dt clock re-seeds after the gap too
        log.warning("%s", tag(Code.TH_LAPSE,
                    f"{asset}: observation gap {now - last:.0f}s (lapse "
                    f"#{st.lapse_count}) - continuity state reset, advice "
                    f"muted {float(self._lp.get('warmup_sec', 900.0)):.0f}s"))

    def observe_fast(self, asset: str, book: dict | None, mark: float,
                     now: float):
        if not self.active:
            return
        try:
            st = self._st(asset)
            self._check_lapse(st, asset, now)
            if mark and math.isfinite(mark) and mark > EPS:
                st.marks.append((now, float(mark)))
            bids = (book or {}).get("bids") or []
            asks = (book or {}).get("asks") or []
            self._update_grid(st, bids, asks, mark)
            self._update_metronome(st, bids, asks, now)
            self._update_barclose(st, bids, asks, now)
            self._update_spoof(st, bids, asks, mark, now)
        except Exception:
            log.debug("thales observe_fast degraded", exc_info=True)

    def _update_spoof(self, st: _AssetState, bids: list, asks: list,
                      mark: float, now: float = 0.0):
        """TH-017 spoof/layering flicker (Cartea-Jaimungal-Wang: spoofing
        operates through top-of-book imbalance; Korea Exchange evidence:
        imbalance-followers are the victims, thin/volatile books the
        venue). Snapshot-data footprint: a level much larger than its
        neighbors that appears near the top and then VANISHES while the
        mid never crossed its price — pulled, not consumed. Each such
        event bumps a per-side EWMA; the shade path distrusts entries
        whose direction the flickering side would bait.

        2026-07-29 unit-audit correction (THALES A-3): the EWMA used to
        run in PER-POLL units (decay 0.85 applied once per snapshot,
        event contribution 1 per snapshot) while the flicker it measures
        is a wall-time process — the SAME spoofer pulling a wall every
        10s scored ~0.50 at the calibrated 5s cadence, saturated at 1.0
        when rate-limiting stretched polls to ~10s, and could NEVER
        cross thr 0.35 at a hypothetical 2.5s cadence. Now both the
        decay and the event contribution are normalized to wall time
        against the calibration cadence (spoof.decay_cal_sec, default
        5.0 = the nominal fast-poll interval the shipped decay/threshold
        were tuned at): decay_eff = decay**(dt/cal) and each event
        counts cal/dt, so the steady-state score for a flip period T is
        ~cal/T at ANY sampling cadence (0.5 for a 10s spoofer — exactly
        the calibrated behavior). At dt == cal this is byte-identical
        to the old recursion."""
        if not bids or not asks or not mark:
            return
        top_n = int(self._sp.get("top_levels", 5))
        big = float(self._sp.get("big_ratio", 3.0))
        drop = float(self._sp.get("drop_frac", 0.8))
        decay = float(self._sp.get("decay", 0.85))
        cal = max(float(self._sp.get("decay_cal_sec", 5.0)), 1e-6)
        last = st.spoof_last_ts
        dt = (now - last) if (now > 0.0 and last > 0.0) else cal
        dt = min(max(dt, 0.5), 60.0)   # bounded: a pathological clock can
        st.spoof_last_ts = now         # neither freeze nor flush the EWMA
        decay_eff = decay ** (dt / cal)
        evt_scale = cal / dt
        for side, rows in (("bids", bids), ("asks", asks)):
            cur = {}
            sizes = []
            for r in rows[:top_n]:
                try:
                    px, sz = float(r[0]), float(r[1])
                except (TypeError, ValueError, IndexError):
                    continue
                if math.isfinite(px) and math.isfinite(sz) and sz > 0:
                    cur[px] = sz
                    sizes.append(sz)
            med = sorted(sizes)[len(sizes) // 2] if sizes else 0.0
            event = 0.0
            if med > 0:
                for px, was in st.spoof_prev.get(side, {}).items():
                    if was < big * med:
                        continue              # was never suspiciously large
                    now_sz = cur.get(px, 0.0)
                    if now_sz > (1.0 - drop) * was:
                        continue              # still resting: not a flicker
                    # consumed-vs-pulled: if the mid moved THROUGH the
                    # level's price, trades plausibly ate it — innocent.
                    consumed = (mark <= px) if side == "bids" else \
                        (mark >= px)
                    if not consumed:
                        event = max(event, min(1.0, was / (big * med) - 1.0))
            st.spoof_ewma[side] = min(1.0, decay_eff
                * st.spoof_ewma.get(side, 0.0)
                + (1.0 - decay_eff) * event * evt_scale)
            st.spoof_prev[side] = cur

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
            # TH-016: seed the bar-spacing estimate from the BATCH median
            # delta, never from a single first delta - if the first two
            # bars of a fresh state straddle a hole, a raw seed inflates
            # the estimate (3h seed on a 5m feed) and masks every later
            # genuine hole. The median over a windowed fetch is robust:
            # holes are a minority of deltas in any real batch.
            if st.bar_spacing <= 0 and len(candles) >= 3:
                try:
                    tss = sorted(float(b.get("ts") or b.get("time") or 0.0)
                                 for b in candles)
                    diffs = sorted(b - a
                                   for a, b in zip(tss, tss[1:], strict=False)
                                   if b - a > 0 and math.isfinite(b - a))
                    if diffs:
                        st.bar_spacing = diffs[len(diffs) // 2]
                except (TypeError, ValueError, AttributeError):
                    pass
            for bar in candles:
                try:
                    ts = float(bar.get("ts") or bar.get("time") or 0.0)
                    o = float(bar.get("open") or 0.0)
                    c = float(bar.get("close") or 0.0)
                    hi = float(bar.get("high") or max(o, c))
                    lo = float(bar.get("low") or min(o, c))
                except (TypeError, ValueError, AttributeError):
                    continue
                if ts <= 0 or o <= EPS or c <= EPS or not math.isfinite(ts):
                    continue      # non-finite ts would poison last_bar_ts
                if ts in st.seen_bar_set:
                    continue
                if len(st.seen_bars) == st.seen_bars.maxlen:
                    st.seen_bar_set.discard(st.seen_bars[0])
                st.seen_bars.append(ts)
                st.seen_bar_set.add(ts)
                # TH-016 bar-gap fence: venue-side candle holes (halts,
                # maintenance, delist windows) make pre-gap swing extremes
                # and sweeps fiction for post-gap bars. Fence by clearing
                # the candle context; it re-warms over the next bars
                # (swing_high_low stays None below its MIN_BARS floor).
                # Clockwork buckets survive: time-of-day stats are keyed
                # by bucket and are gap-immune by construction.
                if st.last_bar_ts > 0:
                    d = ts - st.last_bar_ts
                    if (st.bar_spacing > 0 and d > float(self._lp.get(
                            "bar_gap_bars", 3.0)) * st.bar_spacing):
                        st.candle_hist.clear()
                        st.last_sweep = {}
                        st.bar_hole_count += 1
                        log.warning("%s", tag(Code.TH_LAPSE,
                                    f"{asset}: candle hole {d:.0f}s "
                                    f"(~{d / st.bar_spacing:.0f} bars) - "
                                    f"swing/sweep context fenced"))
                        # the hole itself must not feed the spacing EWMA:
                        # one 3h gap at 0.1 weight would inflate a 5m
                        # estimate ~4x and mask the next hole
                    elif d > 0:
                        st.bar_spacing = d if st.bar_spacing <= 0 else (
                            0.9 * st.bar_spacing + 0.1 * d)
                # plain assignment, not max: feeds are normalized oldest-
                # first, so after one absurd-but-finite ts (ms-vs-s bar)
                # the next real bar re-bases DOWN and the fence self-heals
                # instead of staying dead behind a huge watermark
                st.last_bar_ts = ts
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
        lookback = int(self._s.get("swing_lookback", 48))
        hist = list(st.candle_hist)[-lookback:]
        # proximity only discriminates when the venue's price grid is
        # finer than the tolerance band: on a coarse-tick asset (FLOW
        # at $0.026, one tick = 38bps vs tol 15bps) every representable
        # price IS a magnet and prox pins at 1.0 carrying zero
        # information. Infer the effective tick as the smallest gap
        # between distinct prices in the window; a window with a single
        # price (dead market) is equally uninformative.
        degenerate = False
        if hist:
            prices = sorted({p for _, o, hi, lo, c in hist
                             for p in (o, hi, lo, c)})
            if len(prices) < 2:
                degenerate = True
            else:
                tick = min(b - a for a, b in
                           zip(prices, prices[1:], strict=False))
                degenerate = tick >= tol * mark
        if degenerate != st.zone_degenerate:
            st.zone_degenerate = degenerate
            log.info("thales stop-zone %s: proximity %s (price grid vs "
                     "%.2f%% tolerance band)", "degenerate" if degenerate
                     else "informative again", "disabled" if degenerate
                     else "re-enabled", tol * 100.0)
        prox = 0.0
        if not degenerate:
            zones = round_number_grid(mark)
            # 2026-07-29 unit-audit correction (THALES A-2): the raw
            # proximity score has a GEOMETRIC base rate — with magnet
            # spacing s and tolerance band tol, a uniformly random mark
            # scores E[max(0, 1 - d/tol)] = tol/s > 0, and at the shipped
            # zone_tol_pct=0.15 vs the 0.30%-of-mark step floor the band
            # covers 30-62% of the gap between adjacent magnets (measured
            # corpus-wide: th_stopzone > 0.5 on 43.4% of 6,462 rows;
            # realized PnL identical above/below 0.5 — the gauge was
            # mostly reporting its own null, not stop hunts). Subtract
            # that null (the same shuffle-null discipline OF-2 applies to
            # model scores): mu_null = tol_abs / s_eff with s_eff the
            # finest gap between adjacent magnets near the mark, then
            # rescale so a random mark reads ~0 while an AT-magnet mark
            # (d ~ 0) still reads ~1. mu_null = tol_abs / finest accepted
            # STEP (the true grid spacing - NOT the gap between the
            # nearest-magnet-per-step prices round_number_grid returns,
            # which frequently coincide). Coarse grids (mu_null -> 0) are
            # numerically unchanged; isolated swing hi/lo magnets have no
            # spacing and need no correction (their null is ~0 already).
            tol_abs = tol * mark
            grid_zones = set(zones)      # round-number magnets only (the
            # swing hi/lo appended below are isolated levels, null ~ 0)
            steps = _round_number_steps(mark)
            mu_null = min(tol_abs / min(steps), 1.0 - 1e-9) if steps else 0.0
            swing_hi, swing_lo = swing_high_low(st.candle_hist, lookback)
            # swing_high_low always returns both or neither (never one
            # Optional resolved without the other) - checking both here
            # (rather than swing_hi alone, pre-C3 behavior) is a no-op
            # behaviorally but narrows `swing_lo`'s type for `zones`
            # (now a real `list[float]` via round_number_grid's return
            # type, not an untyped `[]`) so pyright can prove the
            # `.append(swing_lo)` below is float, not float|None.
            if swing_hi is not None and swing_lo is not None:
                zones.append(swing_hi)
                zones.append(swing_lo)
            for z in zones:
                d = abs(mark - z) / mark
                if d < tol:
                    raw = 1.0 - d / tol
                    # null-subtract ROUND-NUMBER magnets only; swing
                    # hi/lo are isolated levels whose null is ~0
                    if mu_null > 0.0 and z in grid_zones:
                        raw = max(0.0, (raw - mu_null) / (1.0 - mu_null))
                    prox = max(prox, raw)
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
            # W2-24: `ts` is the sweep bar's OPEN timestamp, but the sweep
            # pattern (hi/lo vs prior extremes, close back inside) is only
            # OBSERVABLE once the bar CLOSES — one bar_spacing later.
            # sweep_fence_ts is a wall-clock stamp (set at lapse recovery,
            # _check_lapse). Comparing it against bar-OPEN ts fences a
            # legitimate sweep whose bar opened just before the fence but
            # closed (and so became detectable) after it. bar_spacing
            # defaults to 0.0 until 3+ candles seed it, so this is a no-op
            # until then (identical to the old comparison).
            bar_close_ts = ts + st.bar_spacing
            if sweep and bar_close_ts < st.sweep_fence_ts:
                sweep = 0         # TH-016: pre-lapse sweep bar re-derived
                                  # from surviving candle_hist - never latch
            if sweep:
                # store bar-CLOSE, not bar-open: shade_confidence's decay
                # read (`now - sweep["ts"]`) must measure age from when the
                # sweep became confirmable, not from when its bar opened -
                # otherwise every sweep is born already bar_spacing "stale".
                st.last_sweep = {"dir": sweep, "ts": bar_close_ts}
        return prox, sweep

    # ------------------------------------------------------------------
    # advice
    # ------------------------------------------------------------------
    def shade_confidence(self, asset: str, direction: str, urgency: float,
                         confidence: float, macro_label: str | None,
                         now: float) -> ThalesShade:
        """Compose detector scores into one bounded multiplier. Shadow
        mode records the counterfactual and returns confidence
        untouched. Never returns direction; never exceeds clamps."""
        out = ThalesShade(confidence=float(confidence))
        if not self.active or direction not in ("long", "short"):
            return out
        try:
            st = self._st(asset)
            # TH-016: after an observation lapse every detector is running
            # on freshly-reset or gap-straddling evidence; advice is muted
            # (neutral both modes, exits and gates untouched) until the
            # warmup elapses and the bank re-accumulates live footprints.
            if now < st.lapse_until:
                out.notes.append(tag(Code.TH_LAPSE,
                                     f"post-lapse warmup: advice muted "
                                     f"{st.lapse_until - now:.0f}s"))
                return out
            mark = st.marks[-1][1] if st.marks else 0.0
            d = 1 if direction == "long" else -1
            trending = str(macro_label or "").lower() in (
                "trend", "trending", "bull", "bear", "momentum",
                "trend_up", "trend_down")
            mult = 1.0

            # 2026-07-29 dead-mute fix (A-1 companion, all five weighted
            # detectors below): out.fired is the GRADING ledger, not the
            # shade - it must accrue whenever the detector fires, even at
            # w == 0. The old `if w > 0` gate meant a muted detector was
            # never graded again and could never redeem itself (w=0 was
            # a life sentence, not a probation). The shade contribution
            # (mult) still scales by w exactly as before.
            g_thr = float(self._g.get("score_thr", 0.55))
            if st.grid_score > g_thr and trending:
                w = self._rel_weight("grid", "up")
                mult *= 1.0 + w * float(self._g.get("gain", 0.5)) * (
                    st.grid_score - g_thr)
                out.fired.append(("grid", "up"))
                out.notes.append(tag(Code.TH_GRID_LADDER,
                                     f"grid={st.grid_score:.2f} vs trend"
                                     + (f" (w={w:.2f})" if w < 1 else "")))

            m_thr = float(self._m.get("score_thr", 0.6))
            if (st.metro_score > m_thr
                    and urgency >= float(self._m.get("urgency_min", 0.5))):
                w = self._rel_weight("metronome", "up")
                mult *= 1.0 + w * float(self._m.get("gain", 0.4)) * (
                    st.metro_score - m_thr)
                out.fired.append(("metronome", "up"))
                out.notes.append(tag(Code.TH_METRONOME_MM,
                                     f"metro={st.metro_score:.2f} stale-quote edge"
                                     + (f" (w={w:.2f})" if w < 1 else "")))

            c_score, c_dir = self._clockwork(st, now)
            if c_score > 0 and c_dir == d:
                w = self._rel_weight("clockwork", "up")
                mult *= 1.0 + w * float(self._c.get("gain", 0.06)) * c_score
                out.fired.append(("clockwork", "up"))
                out.notes.append(tag(Code.TH_CLOCKWORK_FLOW,
                                     f"bucket flow z-gated score={c_score:.2f}"
                                     + (f" (w={w:.2f})" if w < 1 else "")))

            prox, _ = self._stop_zones(st, mark)
            if prox > 0.5:
                # shade DOWN: our stop would join the herd's cluster
                w = self._rel_weight("stop_prox", "down")
                mult *= 1.0 - w * float(self._s.get("pre_gain", 0.1)) * (
                    prox - 0.5) * 2.0
                out.fired.append(("stop_prox", "down"))
                out.notes.append(tag(Code.TH_STOP_SWEEP,
                                     f"stop-cluster proximity {prox:.2f}: "
                                     f"not the lemming"
                                     + (f" (w={w:.2f})" if w < 1 else "")))
            sweep = st.last_sweep
            decay = float(self._s.get("revert_decay_sec", 1800))
            if sweep and (now - float(sweep.get("ts", 0))) < decay:
                if int(sweep.get("dir", 0)) == -d:
                    # cluster consumed; fade the overshoot while fresh
                    age = (now - float(sweep["ts"])) / decay
                    w = self._rel_weight("stop_revert", "up")
                    mult *= 1.0 + w * float(self._s.get("post_gain", 0.1)) \
                        * (1.0 - age)
                    out.fired.append(("stop_revert", "up"))
                    out.notes.append(tag(Code.TH_STOP_SWEEP,
                                         f"post-sweep revert window "
                                         f"({1 - age:.0%} left)"
                                         + (f" (w={w:.2f})" if w < 1
                                            else "")))

            # TH-017 spoof flicker: entries in the direction a flickering
            # side would bait get shaded DOWN. UNWEIGHTED like feed
            # integrity: a spoof-detection shade graded by trade outcomes
            # would let a spoofer who fails to move price teach V2 to
            # ignore spoofing. Safety shades are not up for reinterview.
            sp = st.spoof_ewma.get("bids" if d == 1 else "asks", 0.0)
            sp_thr = float(self._sp.get("score_thr", 0.35))
            if sp > sp_thr:
                mult *= 1.0 - float(self._sp.get("gain", 0.4)) * min(
                    1.0, (sp - sp_thr) / max(1.0 - sp_thr, 1e-9))
                out.notes.append(tag(Code.TH_SPOOF_FLICKER,
                                     f"flicker {sp:.2f} on entry side: "
                                     f"book imbalance untrusted"))

            # feed integrity: a venue that keeps feeding this asset missing
            # or sanitize-rejected books is hostile-or-unreliable; shade DOWN
            # (never up). Complementary to the watchdog's hard staleness
            # block - this is the softer, per-asset "trust the signal less".
            dirty = self._feed_integrity(st)
            fi_thr = float(self._fi.get("dirty_frac_thr", 0.25))
            if dirty > fi_thr:
                # feed integrity stays UNWEIGHTED: it guards against data
                # quality, not bot behavior — grading it by trade outcomes
                # would let a lucky win on dirty data teach V2 to trust
                # dirty feeds. Safety shades are not up for reinterview.
                mult *= 1.0 - float(self._fi.get("gain", 0.5)) * (
                    dirty - fi_thr)
                out.notes.append(tag(Code.TH_FEED_INTEGRITY,
                                     f"feed dirty {dirty:.0%}: unreliable "
                                     f"venue, trust signal less"))

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
    def observe_feed_health(self, asset: str, clean: bool, now: float):
        """One record per fast cycle per asset: did a CLEAN book arrive, or
        was it missing / rejected by the sanitize boundary? Never raises."""
        if not self.active:
            return
        try:
            self._st(asset).feed_obs.append(1 if clean else 0)
        except Exception:
            log.debug("thales feed-health observe degraded", exc_info=True)

    def _feed_integrity(self, st: _AssetState) -> float:
        """Dirty fraction over the window, or 0.0 until enough samples. High
        = the venue keeps feeding this asset missing/rejected data, which is
        a hostile-or-unreliable signal to trust its own signal less."""
        obs = st.feed_obs
        if len(obs) < int(self._fi.get("min_obs", 20)):
            return 0.0
        return 1.0 - (sum(obs) / len(obs))

    def _update_barclose(self, st: _AssetState, bids: list, asks: list,
                         now: float):
        """TH-015 bar-close herding: no-code/indicator bots evaluate on
        candle close, so their activity clusters in the first seconds
        after bar boundaries (documented intraday periodicity: bursts in
        the opening 30s bucket of every 5-minute bar). Count top-of-book
        change events into phase-of-bar buckets; the herd shows up as an
        excess share in bucket zero. Rolling decay at each bar rollover
        keeps the window recent (~30 bars at 0.97)."""
        if not bids or not asks:
            return
        try:
            top = (float(bids[0][0]), float(asks[0][0]))
        except (TypeError, ValueError, IndexError):
            return                 # malformed top-of-book row: skip, as siblings do
        bar_idx = int(now // st.bc_bar_sec)
        if bar_idx != st.bc_last_bar:
            st.bc_last_bar = bar_idx
            st.bc_buckets = [v * 0.97 for v in st.bc_buckets]
        if st.bc_prev_top is not None and top != st.bc_prev_top:
            phase = (now % st.bc_bar_sec) / st.bc_bar_sec
            b = min(int(phase * st.bc_nb), st.bc_nb - 1)
            st.bc_buckets[b] += 1.0
        st.bc_prev_top = top

    @staticmethod
    def _barclose_score(st: _AssetState) -> float:
        total = sum(st.bc_buckets)
        if total < st.bc_min_events:
            return 0.0
        uniform = 1.0 / st.bc_nb
        share0 = st.bc_buckets[0] / total
        return float(min(max((share0 - uniform) / (1.0 - uniform), 0.0),
                         1.0))

    def _scores(self, st: _AssetState, now: float) -> dict:
        c_score, c_dir = self._clockwork(st, now)
        mark = st.marks[-1][1] if st.marks else 0.0
        prox, _ = self._stop_zones(st, mark)
        return {"grid": round(st.grid_score, 3),
                "metronome": round(st.metro_score, 3),
                "clockwork": round(c_score, 3), "clockwork_dir": c_dir,
                "stop_zone": round(prox, 3),
                "barclose": round(self._barclose_score(st), 3),
                "spoof_bid": round(st.spoof_ewma.get("bids", 0.0), 3),
                "spoof_ask": round(st.spoof_ewma.get("asks", 0.0), 3),
                "feed_dirty": round(self._feed_integrity(st), 3),
                "lapses": st.lapse_count,
                "bar_holes": st.bar_hole_count,
                "lapse_warmup_sec": max(0, int(st.lapse_until - now))}

    def feature_scores(self, asset: str, now: float) -> dict:
        """Bounded [0,1] detector scores for the meta-model feature
        vector (influence-ladder rung 3, operator-enabled): the model
        learns each footprint's weight from labeled outcomes instead of
        a hand-tuned shade. Read-only, never raises; zeros when the
        engine is disabled or the asset has not warmed up."""
        zeros = {"grid": 0.0, "metronome": 0.0, "clockwork": 0.0,
                 "stop_zone": 0.0, "barclose": 0.0}
        if not self.enabled:
            return zeros
        st = self._assets.get(asset)
        if st is None:
            return zeros
        try:
            if now < st.lapse_until:
                return zeros          # TH-016: no gap-straddling evidence
            s = self._scores(st, now)
            return {k: float(min(max(float(s.get(k, 0.0)), 0.0), 1.0))
                    for k in zeros}
        except Exception:
            log.debug("thales feature_scores degraded", exc_info=True)
            return zeros

    def status(self, now: float) -> dict:
        if not self.enabled:
            return {"influence": "off"}
        try:
            return {"influence": self.influence,
                    "assets": {a: self._scores(st, now)
                               for a, st in self._assets.items()},
                    "recent_advice": list(self._counterfactuals)[-5:],
                    "reliability": {
                        k: {**v, "weight": round(self._rel_weight(
                            k, _DETECTOR_ADVICE.get(k, "up")), 3)}
                        for k, v in self._rel.items() if k != "__base__"},
                    # the shared outcome ledger (_rel_weight's null):
                    # fired = graded closes, vindicated = wins
                    "reliability_base": dict(self._rel.get("__base__", {}))}
        except Exception:
            log.debug("thales status degraded", exc_info=True)
            return {"influence": self.influence, "assets": {}}
