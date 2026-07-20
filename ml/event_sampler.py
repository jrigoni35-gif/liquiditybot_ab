"""
ml/event_sampler.py — State-Change Sampler (SCS): event-based candidate
sampling.

WHY: candidates register on every confirmed signal every cycle, so the
training corpus is a CLOCK sample of a slow-moving state — mean per-asset
label uniqueness 0.06 (2,016 rows ≈ 120 independent lessons). This module
replaces the clock with an event clock: a candidate is only registered
when the market has plausibly entered a NEW state since the last one.

Method: symmetric CUSUM change detection on log returns (Page 1954,
Biometrika 41:100-115), with the vol-scaled threshold form of the
symmetric CUSUM filter in Lopez de Prado, AFML 2018 ch. 2, in the spirit
of information-driven clocks (Easley / Lopez de Prado / O'Hara 2012,
J. Portfolio Mgmt 39:19-29). Unique twist: the CUSUM price trigger is
OR-fused with the bot's OWN state detectors — a macro regime-label flip
or liquidity regime-label flip is a new market state even without net
price drift (vol collapse, book flip), so those fire the sampler too.

Calibration (60h of real Kraken 5m data, ETH/BTC/SOL/XRP): symmetric
CUSUM with h = k·sigma_bar at k=3.0 gives ~30 events/day/asset, median
gap ~45 min, implied uniqueness ~0.11 at one-third the row rate.
Effective-lessons/day is FLAT across k in [1, 4] (the 8h label span
bounds it), so k=3.0 is a plateau choice, not a fitted peak (OF-4). The
win is state DIVERSITY + 3-6x less redundancy (less memorization-band
overfit, faster retrains, less prior skew), not more raw information.

Restart semantics: state is in-memory only, deliberately. A restart
re-bootstraps one event per asset — harmless, because candidates are
plentiful and uniqueness weighting downstream still guards against the
odd redundant row; persisting CUSUM sums would buy nothing but another
snapshot key.

Pure python + math, deterministic, no I/O, no wall clock.
"""
import math


class StateChangeSampler:
    """Per-asset symmetric CUSUM on log returns, OR-fused with regime /
    liquidity label flips. `observe()` returns True when the asset has
    entered a new market state worth learning from."""

    # EWMA smoothing for the internal r^2 variance fallback (only used
    # when no sigma_bar_pct is supplied); matches the repo's slow-gauge
    # alpha (e.g. spoof_ewma_alpha) — a per-bar vol estimate, not a knob
    # in a decision path: sigma_bar_pct is the production input.
    # fallback-vol EWMA alpha: lifted to config (ml.sampling.ewma_alpha)
    # with an identical default per CLAUDE.md overfit discipline - it
    # decides h whenever sigma_bar_pct is absent, i.e. it is in the
    # sampling decision path

    def __init__(self, cfg: dict):
        cfg = cfg or {}
        self.enabled = bool(cfg.get("cusum_enabled", False))
        self.k = float(cfg.get("cusum_k", 3.0))
        self._ewma_alpha = min(max(float(cfg.get("ewma_alpha", 0.06)),
                                   1e-4), 0.5)
        # per-asset state: last price, CUSUM sums, EWMA of r^2 (variance
        # fallback), last-seen regime / liquidity labels
        self._st: dict = {}

    def observe(self, asset: str, price: float, sigma_bar_pct=None,
                regime_label=None, liq_label=None) -> bool:
        """Advance the asset's state one bar; True = teachable event.

        Must be called EVERY cycle (the CUSUM integrates drift bar by
        bar); the caller latches the result until it consumes it.
        """
        if not self.enabled:
            return True                     # legacy: every cycle an event
        # bad price: ignore the observation entirely — do not advance the
        # CUSUM, do not update labels, do not corrupt the return baseline
        if not isinstance(price, (int, float)) or not math.isfinite(price) \
                or price <= 0.0:
            return False

        st = self._st.get(asset)
        if st is None:
            # bootstrap: first valid observation IS an event (a state we
            # have never seen); initializes the baseline for returns
            self._st[asset] = {"px": float(price), "sp": 0.0, "sn": 0.0,
                               "var": 0.0, "regime": regime_label,
                               "liq": liq_label}
            return True

        # ---- OR-fused label triggers ---------------------------------
        # the bot's own detectors flipping label = new market state even
        # with zero net drift; None->label is a detector warming up, not
        # a transition, so it never triggers (but the label is adopted)
        label_event = False
        if regime_label is not None:
            if st["regime"] is not None and regime_label != st["regime"]:
                label_event = True
            st["regime"] = regime_label
        if liq_label is not None:
            if st["liq"] is not None and liq_label != st["liq"]:
                label_event = True
            st["liq"] = liq_label

        # ---- symmetric CUSUM on log returns --------------------------
        r = math.log(float(price) / st["px"])
        st["px"] = float(price)
        # UNITS: sigma_bar_pct is a PERCENT (0.3 means 0.3%/bar); r is a
        # FRACTION. Convert percent -> fraction exactly once, HERE.
        if sigma_bar_pct is not None and isinstance(sigma_bar_pct, (int, float)) \
                and math.isfinite(sigma_bar_pct) and sigma_bar_pct > 0.0:
            sigma = float(sigma_bar_pct) / 100.0
        else:
            # self-contained fallback: EWMA of r^2 as the variance proxy
            st["var"] = ((1.0 - self._ewma_alpha) * st["var"]
                         + self._ewma_alpha * r * r)
            sigma = math.sqrt(st["var"])
        st["sp"] = max(0.0, st["sp"] + r)
        st["sn"] = min(0.0, st["sn"] + r)
        h = self.k * sigma
        cusum_event = h > 0.0 and (st["sp"] > h or st["sn"] < -h)

        if cusum_event or label_event:
            # reset BOTH sums on ANY trigger: a label flip means the
            # state changed, so drift accumulated in the old state must
            # not carry into the new one
            st["sp"] = st["sn"] = 0.0
            return True
        return False
