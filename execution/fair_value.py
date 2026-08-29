"""
execution/fair_value.py — rev 2.0 (Assurance Build)

Estimated-value engine: the anchor every quote, entry price, and edge
calculation hangs off. Rev 2 changes, in order of importance:

  UNCERTAINTY-DISCOUNTED EDGE. The engine now tracks the dispersion of
  its own innovations (EWMA of |raw - smoothed| in bps). edge_bps()
  subtracts `edge_haircut_z` x that dispersion from the apparent edge
  before reporting it. An "edge" smaller than the estimator's own noise
  floor is a statistical mirage — reporting it as zero is the single
  highest-value profit fix in the stack, because every mirage trade
  pays the full 40-80bps cost stack to capture nothing (venue-true
  Kraken Tier-1 maker/taker as of cut #8, 2026-08-28).

  INNOVATION GATING. A raw print that jumps more than `gate_z` noise
  units gets a reduced blend weight for one update instead of full
  alpha — one flashed order or poisoned venue book cannot yank fair
  value; a real move passes through over 2 updates (same philosophy as
  the watchdog's tick quarantine, applied to the estimator).

  FAIL-CLOSED INPUTS. Non-finite or non-positive prices/sizes are
  dropped at ingestion; a book that contributes nothing valid simply
  doesn't vote. updated=False whenever no venue voted.

Public surface unchanged: FairValueEngine(config).state(asset) /
.update(asset, venue_books, kraken_book) -> FVState with .fair_value,
.kraken_mid/.kraken_bid/.kraken_ask, .basis_bps, .updated,
.edge_bps(side). New read-only fields: .fv_sigma_bps, .innovation_bps.
"""

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Optional

from core.sanitize import is_finite_pos as _finite_pos

log = logging.getLogger("liquiditybot.execution.fair_value")

EPS = 1e-12

# v9 SHADOW basis-momentum bound, bps/min: 3x the feature clip window
# (+/-80bps of basis_dir) traversed in one minute. A structural sanity
# clamp, not a tunable - the ml/features.py clip is far tighter anyway.
BASIS_MOM_CAP_BPS_MIN = 240.0


@dataclass
class FVState:
    asset: str
    fair_value: float = 0.0
    fair_value_raw: float = 0.0
    kraken_mid: float = 0.0
    kraken_bid: float = 0.0
    kraken_ask: float = 0.0
    basis_bps: float = 0.0
    updated: bool = False
    fv_sigma_bps: float = 0.0        # EWMA innovation dispersion (noise floor)
    innovation_bps: float = 0.0      # last raw-vs-smoothed innovation
    edge_haircut_z: float = 1.0      # injected by engine from config
    kraken_touch_ts: float = 0.0     # wall-clock ts of the last FRESH Kraken
                                     # touch (W2-23 age-stamp)
    kraken_fresh: bool = True        # False once the touch is older than the
                                     # staleness bound - basis_bps/edge_bps
                                     # read neutral/zero while this is False
    basis_mom_bps: float = 0.0       # v9 SHADOW: d(basis_bps)/dt over the
                                     # configured window, bps/MINUTE. Feeds
                                     # ONLY ml basis_mom_dir (shadow-purity
                                     # grep test); 0.0 on stale/degenerate.
    basis_hist: list = field(default_factory=list)
                                     # (ts, basis_bps) samples inside the
                                     # momentum window - state lives HERE,
                                     # where basis_bps lives, rolled once
                                     # per update (never hot-path recompute)

    def edge_bps(self, side: str) -> float:
        """Uncertainty-discounted edge of executing at the Kraken touch
        vs fair value. Sign convention unchanged: positive = the
        executable price is in your favor. The apparent edge is shrunk
        toward zero by edge_haircut_z x the estimator's own noise floor;
        edge you cannot distinguish from noise is reported as zero."""
        if not self.updated or self.fair_value <= 0:
            return 0.0
        if side == "buy":
            if self.kraken_ask <= 0:
                return 0.0
            raw = (self.fair_value - self.kraken_ask) / self.fair_value * 1e4
        else:
            if self.kraken_bid <= 0:
                return 0.0
            raw = (self.kraken_bid - self.fair_value) / self.fair_value * 1e4
        haircut = self.edge_haircut_z * self.fv_sigma_bps
        if raw > 0:
            return max(raw - haircut, 0.0)
        return min(raw + haircut, 0.0)


def microprice(book: dict) -> float:
    """Size-weighted top-of-book value (Stoikov). Invalid levels are
    ignored; a book with no valid touch contributes 0 (no vote)."""
    bids, asks = book.get("bids") or [], book.get("asks") or []
    if not bids or not asks:
        return 0.0
    try:
        bp, bs = float(bids[0][0]), float(bids[0][1])
        ap, as_ = float(asks[0][0]), float(asks[0][1])
    except (TypeError, ValueError, IndexError):
        return 0.0
    if not (_finite_pos(bp) and _finite_pos(ap)) or ap < bp:
        return 0.0                       # crossed/absurd book: no vote
    bs = bs if _finite_pos(bs) else 0.0
    as_ = as_ if _finite_pos(as_) else 0.0
    tot = bs + as_
    if tot <= EPS:
        return 0.5 * (bp + ap)
    return (bp * as_ + ap * bs) / tot


def _depth_usd(book: dict, levels: int = 10) -> float:
    total = 0.0
    for side in ("bids", "asks"):
        for row in (book.get(side) or [])[:levels]:
            try:
                p, s = float(row[0]), float(row[1])
            except (TypeError, ValueError, IndexError):
                continue
            if _finite_pos(p) and _finite_pos(s):
                total += p * s
    return total


class FairValueEngine:
    def __init__(self, config: dict):
        cfg = config or {}
        self.alpha = min(max(float(cfg.get("ema_alpha", 0.35)), 0.01), 1.0)
        self.gate_z = max(float(cfg.get("innovation_gate_z", 4.0)), 1.0)
        self.gated_alpha_frac = min(max(float(
            cfg.get("gated_alpha_frac", 0.25)), 0.0), 1.0)
        self.haircut_z = max(float(cfg.get("edge_haircut_z", 1.0)), 0.0)
        self.sigma_lambda = min(max(float(
            cfg.get("sigma_lambda", 0.90)), 0.5), 0.999)
        # W2-23: how long a Kraken touch may hold after Kraken stops voting
        # before basis_bps/edge_bps must go neutral rather than fabricate a
        # signal off a frozen touch vs a still-updating fair value. Default
        # mirrors core/watchdog.py's stale_critical_sec (120s) - the same
        # "past this, treat as absent" bound the rest of the book-freshness
        # stack already uses; lifted here rather than duplicated.
        self.kraken_stale_sec = max(float(cfg.get("kraken_stale_sec", 120.0)), 0.0)
        # v9 SHADOW basis momentum window (config fair_value.
        # basis_mom_window_sec, default + bounds documented there and in
        # core/config_guard.py). Clamped to sane structure here as well
        # so a direct-construction harness cannot zero the denominator.
        self.basis_mom_window_sec = min(max(float(
            cfg.get("basis_mom_window_sec", 60.0)), 1.0), 3600.0)
        self._states: dict = {}

    # ------------------------------------------------------------------
    def _roll_basis_momentum(self, st: FVState, now: float) -> None:
        """Roll the v9 SHADOW basis-momentum window with this update's
        fresh basis_bps: per-SECOND slope over the samples inside
        basis_mom_window_sec, scaled x60 to bps/min (wall-time
        discipline, THALES A-3 - never per-update units that alias with
        poll cadence). The span denominator floors at 1s (an EPS-class
        guard: two same-instant polls must not amplify innovation noise
        into a phantom slope), the result clamps at +/-BASIS_MOM_CAP,
        and every degenerate path (single sample, clock backwards,
        non-finite) lands on the 0.0 neutral."""
        h = st.basis_hist
        h.append((now, st.basis_bps))
        cutoff = now - self.basis_mom_window_sec
        while len(h) > 1 and h[0][0] < cutoff:
            h.pop(0)
        span = now - h[0][0]
        if span < 0.0:                    # clock stepped backwards: reseed
            del h[:-1]
            st.basis_mom_bps = 0.0
            return
        if len(h) < 2 or span <= 0.0:
            st.basis_mom_bps = 0.0
            return
        slope = (st.basis_bps - h[0][1]) / max(span, 1.0) * 60.0
        if not math.isfinite(slope):
            st.basis_mom_bps = 0.0
            return
        st.basis_mom_bps = max(-BASIS_MOM_CAP_BPS_MIN,
                               min(slope, BASIS_MOM_CAP_BPS_MIN))

    def state(self, asset: str) -> FVState:
        return self._states.get(asset) or FVState(
            asset=asset, edge_haircut_z=self.haircut_z)

    # ------------------------------------------------------------------
    def update(self, asset: str, venue_books: list, kraken_book: dict,
            now: Optional[float] = None) -> FVState:
        now = time.time() if now is None else now
        st = self._states.get(asset) or FVState(
            asset=asset, edge_haircut_z=self.haircut_z)
        st.edge_haircut_z = self.haircut_z

        mps, weights = [], []
        for book in venue_books or []:
            mp = microprice(book or {})
            if mp > 0:
                mps.append(mp)
                weights.append(max(_depth_usd(book), 1.0))
        if kraken_book:
            kb = kraken_book.get("bids") or []
            ka = kraken_book.get("asks") or []
            try:
                kbid = float(kb[0][0]) if kb else 0.0
                kask = float(ka[0][0]) if ka else 0.0
            except (TypeError, ValueError, IndexError):
                kbid = kask = 0.0
            if _finite_pos(kbid) and _finite_pos(kask) and kask >= kbid:
                st.kraken_bid, st.kraken_ask = kbid, kask
                st.kraken_mid = 0.5 * (kbid + kask)
                st.kraken_touch_ts = now
                st.kraken_fresh = True
                mp = microprice(kraken_book)
                if mp > 0:
                    mps.append(mp)
                    weights.append(max(_depth_usd(kraken_book), 1.0))

        # W2-23: a Kraken touch that did NOT vote this cycle (outage, or a
        # kraken_book that failed the finite/crossed checks above) ages from
        # its last real touch_ts. Past kraken_stale_sec it is zeroed rather
        # than left frozen - fair_value keeps blending from external books
        # regardless, so a frozen touch vs a drifting fair_value fabricates
        # basis/edge that grows for the entire outage if left unchecked.
        if st.kraken_mid > 0 and (now - st.kraken_touch_ts) > self.kraken_stale_sec:
            st.kraken_bid = st.kraken_ask = st.kraken_mid = 0.0
            st.kraken_fresh = False
            # v9 SHADOW: a stale touch has no basis, so it has no basis
            # SLOPE either - zero the momentum and drop the window so a
            # later re-touch re-seeds instead of diffing against fossils
            st.basis_mom_bps = 0.0
            st.basis_hist.clear()

        if not mps:
            st.updated = False
            self._states[asset] = st
            return st

        tot = sum(weights)
        raw = sum(m * w for m, w in zip(mps, weights, strict=True)) / tot
        st.fair_value_raw = raw

        if st.fair_value <= 0:
            st.fair_value = raw
            st.fv_sigma_bps = 0.0
            st.innovation_bps = 0.0
        else:
            innov_bps = (raw - st.fair_value) / st.fair_value * 1e4
            st.innovation_bps = innov_bps
            noise = max(st.fv_sigma_bps, 0.5)      # floor: never zero-gate
            alpha = self.alpha
            if abs(innov_bps) > self.gate_z * noise:
                # jump beyond the gate: damp this update (FV-020). A real
                # move persists and passes fully on the next update; a
                # flashed order does not.
                alpha *= self.gated_alpha_frac
                log.info("FV-020: %s innovation %.0fbps > %.1fx noise "
                         "%.1fbps — damped blend this update",
                         asset, innov_bps, self.gate_z, noise)
            st.fair_value = alpha * raw + (1 - alpha) * st.fair_value
            # EWMA of absolute innovation = the estimator's noise floor
            st.fv_sigma_bps = self.sigma_lambda * st.fv_sigma_bps + \
                (1 - self.sigma_lambda) * abs(innov_bps)

        if st.kraken_mid > 0:
            st.basis_bps = (st.fair_value - st.kraken_mid) / \
                st.kraken_mid * 1e4
            self._roll_basis_momentum(st, now)
        else:
            st.basis_bps = 0.0   # W2-23: no fresh touch -> no basis, never stale
            st.basis_mom_bps = 0.0
            st.basis_hist.clear()
        st.updated = True
        self._states[asset] = st
        return st
