"""
regime/correlation.py

Cross-asset structure monitoring:

  * EWMA covariance (RiskMetrics lambda) at two speeds. The fast/slow
    correlation gap is the "correlation shift" signal - regime changes
    show up in correlations before they show up in price trends.
  * Hedge betas (cov/var from the fast estimator) consumed by
    execution/hedging.py.
  * Kritzman-Li (2010) financial turbulence index: Mahalanobis distance
    of today's cross-asset return vector from its historical
    distribution. Turbulence spikes are an early crisis tell and feed
    the macro engine's crisis overlay.
"""

import logging
import time
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np

from core.codes import Code, tag
from core.sanitize import safe_float

log = logging.getLogger("liquiditybot.regime.correlation")

EPS = 1e-12


@dataclass
class CorrState:
    corr_fast: dict = field(default_factory=dict)    # (a,b) -> rho
    corr_slow: dict = field(default_factory=dict)
    corr_shift: dict = field(default_factory=dict)   # fast - slow
    betas: dict = field(default_factory=dict)        # (a,b) -> beta of a on b
    turbulence: float = 0.0
    turbulence_pct: float = 50.0
    shifted: bool = False                            # any |shift| beyond threshold
    # per-asset EWMA observation counts (2026-08-07 hedge-churn fix): the
    # evidence-quality signal hedging's open gate reads. EMPTY dict =
    # "warmth untracked" - the legacy state every pre-existing caller,
    # stub and restored snapshot constructs - and pair_samples then
    # reports warm-assumed so their behavior stays byte-identical.
    # Populated by CorrelationEngine.update_intraday with real counts.
    samples: dict = field(default_factory=dict)
    # --- turbulence provenance (2026-08-22 instrument verification, D6) --
    # update_turbulence has FIVE early returns that leave the previous
    # turbulence/turbulence_pct standing. Before these fields a held
    # reading was byte-identical to a freshly computed one: no age, no
    # sample count, no flag, no code - a feed outage could freeze the
    # scalar (possibly at a crisis value) with nothing surfacing it.
    # APPENDED with defaults: every pre-existing constructor, stub and
    # restored snapshot builds the legacy state (computed_at 0.0 =
    # "never computed", stale False, no hold reason) unchanged.
    computed_at: float = 0.0     # wall-clock epoch of the last SUCCESSFUL
                                 # turbulence computation; 0.0 = never
    sample_count: int = 0        # shared daily bars behind that reading,
                                 # counted as RETURNS (R.shape[0]) - the
                                 # percentile denominator, and the unit the
                                 # >= 40 floor below is stated in. The
                                 # joined bar count is exactly one higher.
    stale: bool = False          # True when the last update HELD the prior
                                 # reading instead of recomputing it
    hold_reason: str = ""        # which early return held it (slug; see
                                 # CorrelationEngine._hold_turbulence)

    _WARM_ASSUMED = 10**9      # legacy sentinel: warmth was never tracked

    def corr(self, a: str, b: str) -> float:
        return self.corr_fast.get((a, b), self.corr_fast.get((b, a), 0.0))

    def pair_samples(self, a: str, b: str) -> int:
        """Observations backing corr(a, b) = min of the two assets'
        counts. A 2-sample EWMA reads |rho|~1 and a missing pair reads
        0.0 - BOTH are artifacts (the 2026-08-07 churn oscillated
        between exactly those two states), so consumers gate on this
        count, never on the rho value's plausibility."""
        if not self.samples:
            return self._WARM_ASSUMED
        return min(int(self.samples.get(a, 0)), int(self.samples.get(b, 0)))

    def beta(self, a: str, b: str) -> float:
        return self.betas.get((a, b), 0.0)


class _EwmaCov:
    def __init__(self, lam: float):
        self.lam = lam
        self.mean: dict = {}
        self.cov: dict = {}

    def update(self, rets: dict):
        assets = sorted(rets)
        for a in assets:
            m = self.mean.get(a, rets[a])
            self.mean[a] = self.lam * m + (1 - self.lam) * rets[a]
        for a in assets:
            for b in assets:
                da = rets[a] - self.mean[a]
                db = rets[b] - self.mean[b]
                c = self.cov.get((a, b), da * db)
                self.cov[(a, b)] = self.lam * c + (1 - self.lam) * da * db

    def corr(self, a: str, b: str) -> float:
        va = self.cov.get((a, a), 0.0)
        vb = self.cov.get((b, b), 0.0)
        if va <= EPS or vb <= EPS:
            return 0.0
        return float(np.clip(self.cov.get((a, b), 0.0) / np.sqrt(va * vb), -1, 1))

    def beta(self, a: str, b: str) -> float:
        vb = self.cov.get((b, b), 0.0)
        if vb <= EPS:
            return 0.0
        return float(self.cov.get((a, b), 0.0) / vb)


class CorrelationEngine:
    def __init__(self, config: dict, crisis_pct: float | None = None):
        """`config` is the `correlation` block. `crisis_pct` is the ONE
        crisis percentile the system decides on (`regime.crisis_vol_pct`,
        read by regime/macro_regime.py) - passed in, never re-declared:
        the operator warning below used to carry its own hardcoded 95, a
        second copy of that threshold, so editing the config silently
        desynchronised the log from the decision (2026-08-22 turbulence
        verification, §4). The default reproduces the shipped value for
        every caller that does not supply it."""
        cfg = config or {}
        self.fast = _EwmaCov(float(cfg.get("lambda_fast", 0.94)))
        self.slow = _EwmaCov(float(cfg.get("lambda_slow", 0.997)))
        self.shift_threshold = float(cfg.get("shift_threshold", 0.25))
        self.turb_lookback = int(cfg.get("turbulence_lookback_days", 250))
        # H9: fold one ALIGNED cross-asset step, never one caller invocation.
        # The engine is fed the last committed 5m bar close from a per-asset
        # cache whose refresh is budgeted (3 pairs/cycle), so a call carries a
        # mix of freshly-advanced and unchanged series - and folding an
        # unchanged price as a real 0.0 return partitioned the universe into
        # refresh groups whose covariance entries were never updated together.
        # Cross-group corr/beta then read ~0.00 forever, which is below
        # hedging.min_hedge_correlation, i.e. the hedge gate was structurally
        # dead for the assets that most needed it. Rollback: false.
        self.align_updates = bool(cfg.get("align_intraday_by_bar", True))
        # bounded wait so one dead series can never stall the estimator
        self.align_max_wait = max(int(cfg.get("align_max_wait_evals", 8)), 1)
        self._last_close: dict = {}
        self._last_ts: dict = {}        # asset -> bar_ts of its last fold
        self._pending: dict = {}        # asset -> (close, bar_ts|None)
        self._wait = 0                  # consecutive calls that did not fold
        self.state = CorrState()
        # 2026-07-29 log hygiene: "correlation shift detected" used to
        # dump the FULL pair->shift dict at INFO every intraday update
        # (~30s) for as long as the shift persisted - hundreds of lines
        # per episode in the live events feed. Log a compact summary
        # once on the False->True TRANSITION; the ongoing state stays
        # visible at DEBUG and in st.shifted/st.corr_shift for status.
        self._was_shifted = False
        self.crisis_pct = float(95.0 if crisis_pct is None else crisis_pct)
        # turbulence hold latch: the held/recovered codes fire ONLY on the
        # state TRANSITION, never per cycle. update_turbulence runs hourly
        # per asset-universe refresh and a feed outage persists for hours,
        # so a per-cycle emission would repeat the SZ-047 failure (one code
        # at 63% of a 35,530-record audit trail). The CURRENT reason stays
        # continuously readable on state.stale/state.hold_reason.
        self._turb_held = False

    # --- per-cycle intraday returns (5m cadence) -----------------------
    def _stage_intraday(self, closes: dict, bar_ts) -> dict:
        """Buffer this call's observations; return the ALIGNED return vector
        to fold, or {} while the step is still incomplete.

        bar_ts (asset -> bar open timestamp) is the authoritative "did this
        series advance?" evidence and should always be supplied. Without it
        the only available evidence is the close changing: a non-refreshed
        cache hands back the byte-identical float, and treating that as a
        genuine 0.0 return is precisely the H9 defect.
        """
        ts_map = bar_ts or {}
        for gone in [a for a in self._pending if a not in closes]:
            # an asset that left the universe must not hold the step open;
            # its return is re-observed from the unchanged basis if it returns
            self._pending.pop(gone, None)
        for asset, px in closes.items():
            px = float(px)
            if px <= 0:
                continue
            ts = ts_map.get(asset)
            ts = float(ts) if ts is not None else None
            if asset not in self._last_close:
                self._last_close[asset] = px      # anchor only, no return yet
                if ts is not None:
                    self._last_ts[asset] = ts
                continue
            prev_ts = self._last_ts.get(asset)
            if ts is not None:
                if prev_ts is not None and ts <= prev_ts:
                    continue                      # same (or stale) bar
            elif px == self._last_close[asset]:
                continue                          # unrefreshed cache
            # newest observation wins: the pending return always spans from
            # the last FOLDED close, so two advances before a fold compose
            self._pending[asset] = (px, ts)

        tracked = [a for a in closes if a in self._last_close]
        pending = {a: v for a, v in self._pending.items() if a in closes}
        forced = self._wait >= self.align_max_wait
        if len(pending) < 2 or (len(pending) < len(tracked) and not forced):
            # only a HELD partial step burns the budget; quiet calls between
            # bars must not age it out and force a half-universe fold
            self._wait = self._wait + 1 if pending else 0
            return {}
        fold = pending
        stamped = {a: v[1] for a, v in pending.items() if v[1] is not None}
        if stamped and not forced:
            groups: dict = {}
            for a, ts in stamped.items():
                groups.setdefault(ts, []).append(a)
            if len(groups) > 1:
                # the universe straddles two bars: fold the LARGEST group and,
                # on ties, the OLDER one, so the leaders stay pending and the
                # whole universe realigns on the next call
                pick = max(groups, key=lambda t: (len(groups[t]), -t))
                fold = {a: pending[a] for a in groups[pick]}
                if len(fold) < 2:
                    self._wait += 1
                    return {}
                log.debug("correlation: folding %d/%d assets at bar %s",
                        len(fold), len(pending), pick)
        rets = {}
        for asset, (px, _ts) in fold.items():
            last = self._last_close.get(asset)
            if last and last > 0:
                rets[asset] = float(np.log(px / last))
        for asset, (px, ts) in fold.items():      # commit the new basis
            self._last_close[asset] = px
            if ts is not None:
                self._last_ts[asset] = ts
            self._pending.pop(asset, None)
        self._wait = 0
        return rets

    def update_intraday(self, closes: dict, bar_ts: dict | None = None
                        ) -> CorrState:
        """Fold one cross-asset return step. `bar_ts` maps asset -> the bar
        open timestamp the close belongs to; supplying it makes the step
        alignment exact instead of inferred (see _stage_intraday)."""
        if self.align_updates:
            rets = self._stage_intraday(closes, bar_ts)
        else:
            rets = {}
            for asset, px in closes.items():
                last = self._last_close.get(asset)
                self._last_close[asset] = px
                if last and last > 0 and px > 0:
                    rets[asset] = float(np.log(px / last))
        if len(rets) >= 2:
            self.fast.update(rets)
            self.slow.update(rets)
            st = self.state
            for a in rets:
                st.samples[a] = int(st.samples.get(a, 0)) + 1
            st.corr_fast.clear()
            st.corr_slow.clear()
            st.corr_shift.clear()
            st.betas.clear()
            assets = sorted(rets)
            for a, b in combinations(assets, 2):
                cf, cs = self.fast.corr(a, b), self.slow.corr(a, b)
                st.corr_fast[(a, b)] = cf
                st.corr_slow[(a, b)] = cs
                st.corr_shift[(a, b)] = cf - cs
            for a in assets:
                for b in assets:
                    if a != b:
                        st.betas[(a, b)] = self.fast.beta(a, b)
            st.shifted = any(abs(v) >= self.shift_threshold
                            for v in st.corr_shift.values())
            if st.shifted:
                if not self._was_shifted:
                    over = {k: v for k, v in st.corr_shift.items()
                            if abs(v) >= self.shift_threshold}
                    top = sorted(over.items(), key=lambda kv: abs(kv[1]),
                                 reverse=True)[:3]
                    log.info(
                        "correlation shift detected: %d pair(s) >= %.2f; "
                        "largest: %s", len(over), self.shift_threshold,
                        ", ".join(f"{a}-{b} {v:+.2f}"
                                  for (a, b), v in top))
                else:
                    log.debug("correlation shift ongoing: %s", st.corr_shift)
            self._was_shifted = st.shifted
        return self.state

    # --- daily turbulence (Kritzman-Li) --------------------------------
    def _hold_turbulence(self, reason: str) -> CorrState:
        """Stamp the reading as HELD and return it unchanged.

        Every early return in update_turbulence leaves the PREVIOUS
        turbulence scalar standing - which is the right behavior (a
        half-joined day is worse than yesterday's number), but before
        this it was indistinguishable from a fresh computation. The
        scalar reaches regime/macro_regime.py's crisis clause, so a feed
        outage could hold it at a crisis value indefinitely with nothing
        surfacing it (2026-08-22 verification, D6).

        `reason` is a short stable slug naming WHICH early return held
        it: few_assets / no_step / bad_step / few_shared_bars /
        few_returns. The code fires on the TRANSITION only.
        """
        st = self.state
        st.stale = True
        st.hold_reason = reason
        if not self._turb_held:
            self._turb_held = True
            log.warning(tag(
                Code.CR_TURBULENCE_HELD,
                f"turbulence held ({reason}) - the previous reading "
                f"(t={st.turbulence:.1f}, p{st.turbulence_pct:.0f}, "
                f"n={st.sample_count}) stands and is being consumed as "
                f"if fresh; one log per hold episode, live state on "
                f"status.correlation.stale/hold_reason"))
        return st

    def update_turbulence(self, daily_candles_by_asset: dict) -> CorrState:
        """daily_candles_by_asset: asset -> list of daily candle dicts
        (oldest-first, each carrying its bar-open `time`).

        M7: rows are joined on the BAR TIMESTAMP, never on list position.
        Positional stacking silently pairs asset A's day d with asset B's
        day d-k whenever one venue's history is shorter, deeper, or one
        poll staler than another's - and the Mahalanobis distance it feeds
        is a single-row read, so a one-day shear corrupts both Sigma and
        the reference distribution the percentile is scored against.
        """
        # 1. drop each series' newest row. All three venue feeds request
        #    include_forming=True (justified for the macro engine, which
        #    averages over 21-126 day lookbacks) - but turbulence scores
        #    exactly ONE row, so a partial day's return vector measured
        #    against a full-day distribution reads as artificial calm.
        prepped = {}
        for asset, candles in (daily_candles_by_asset or {}).items():
            if not isinstance(candles, list) or len(candles) < 61:
                continue
            by_ts = {}
            for c in candles[:-1]:
                t = safe_float(c.get("time"))
                px = safe_float(c.get("close"))
                if t > 0 and px > 0:
                    by_ts[t] = px                 # last write wins on dupes
            if len(by_ts) >= 60:
                prepped[asset] = by_ts
        if len(prepped) < 2:
            return self._hold_turbulence("few_assets")
        # 2. one shared day lattice. Venues label the same trading day at
        #    different hours (OKX "1D" rolls 00:00 Hong Kong = 16:00 UTC,
        #    Kraken interval=1440 rolls 00:00 UTC), so an exact-timestamp
        #    join would return the empty set and silently kill the index.
        #    Bucketing by the series' own median step pairs each venue's
        #    day-d bar with every other's, which is the closest join the
        #    data supports until okx_feed requests "1Dutc".
        steps = []
        for by_ts in prepped.values():
            ts = sorted(by_ts)
            d = sorted(b - a for a, b in zip(ts, ts[1:], strict=False)
                       if b > a)
            if d:
                steps.append(d[len(d) // 2])
        if not steps:
            return self._hold_turbulence("no_step")
        steps.sort()
        step = steps[len(steps) // 2]
        if step <= 0:
            return self._hold_turbulence("bad_step")
        keyed = {a: {round(t / step): px for t, px in by_ts.items()}
                 for a, by_ts in prepped.items()}
        assets = sorted(keyed)
        shared = sorted(set.intersection(*(set(k) for k in keyed.values())))
        if len(shared) < 41:                      # 40 returns is the floor
            log.debug("turbulence: only %d shared daily bars across %d "
                    "assets - holding the previous reading",
                    len(shared), len(assets))
            return self._hold_turbulence("few_shared_bars")
        days = shared[-(self.turb_lookback + 1):]
        R = np.column_stack([
            np.diff(np.log(np.maximum(
                np.array([keyed[a][d] for d in days], dtype=float), EPS)))
            for a in assets
        ])                                            # (len(days)-1, A)
        if R.shape[0] < 40:
            return self._hold_turbulence("few_returns")
        mu = R.mean(axis=0)
        cov = np.cov(R, rowvar=False)
        cov += np.eye(cov.shape[0]) * (np.trace(cov) / cov.shape[0]) * 0.05  # shrink
        try:
            inv = np.linalg.inv(cov)
        except np.linalg.LinAlgError:
            inv = np.linalg.pinv(cov)
        d = np.einsum("ij,jk,ik->i", R - mu, inv, R - mu)  # Mahalanobis^2 series
        self.state.turbulence = float(d[-1])
        self.state.turbulence_pct = float((d < d[-1]).mean() * 100.0)
        # provenance stamp: this pass RECOMPUTED the scalar. wall clock,
        # telemetry only - no decision reads it (same lane as the
        # engine's _mark_wall_ts freshness stamps).
        self.state.computed_at = float(time.time())
        self.state.sample_count = int(R.shape[0])
        if self._turb_held:
            self._turb_held = False
            log.info(tag(
                Code.CR_TURBULENCE_FRESH,
                f"turbulence recomputed after a hold "
                f"({self.state.sample_count} returns across "
                f"{len(assets)} assets) - reading is live again"))
        self.state.stale = False
        self.state.hold_reason = ""
        if self.state.turbulence_pct >= self.crisis_pct:
            log.warning(f"turbulence spike: {self.state.turbulence:.1f} "
                        f"(p{self.state.turbulence_pct:.0f} >= "
                        f"p{self.crisis_pct:.0f})")
        return self.state
