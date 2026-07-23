"""
risk/profit_tiers.py — 4-tier scaled profit-taking engine, rev 3
(Vol-Adaptive / Chandelier Build)

rev 2 fired tiers at FIXED %-gains and trailed a FIXED % behind the
last price. Fixed distances are the wrong unit: 1% is a stop-run in a
90th-percentile vol regime and an unreachable target in a quiet one.
rev 3 keeps the exact 4-tier + trailing contract and makes every
distance regime-aware:

  VOL-SCALED TIERS   with vol_scaled=true and a live sigma_bar_pct,
      tier k triggers at trigger_vol_mult_k · sigma_bar (per-bar vol,
      %), CLAMPED to [0.5x, 3.0x] of the legacy trigger_pct_gain so a
      vol-feed fault can never park targets at silly distances. The
      legacy number remains the exact behavior whenever vol is absent
      or vol_scaled=false. Playbook tier_scale multiplies both forms.
  BREAK-EVEN RATCHET after be_after_tier fires, the exit floor
      ratchets to entry ± (est_fee_bps·2 + be_buffer_bps): a trade
      that has paid you once is never again allowed to become a
      round-trip-fees loser.
  CHANDELIER TRAIL   the trail anchors to the position's HIGH-WATER
      mark (persisted on the Position), not the last print, at a
      distance max(legacy trail_pct, chandelier_k · sigma_bar ·
      sqrt(chandelier_bars)). Ratchet-only: the stop can tighten,
      never loosen — including across restarts.
  TIME TIGHTENING    past tighten_after_bars in the trade, the trail
      distance decays by tighten_factor per 48 bars (floored) — an
      aging thesis gets a shorter leash instead of a stale-loss purge.
  GIVE-BACK RATCHET  (rev 4) independent of tier gating: once the PEAK
      open move (from the persisted high_water) reaches arm_gain_pct,
      the exit floor ratchets to lock in (1 - giveback_frac) of that
      peak move; past tighten_gain_pct the locked share rises to
      (1 - tight_frac). Peak-based arming is monotone, so the floor is
      fully reconstructible from high_water after a restart — no new
      persisted state. Composes with break-even and chandelier through
      the same ratchet (max of all floors long / min short).

Single-action-per-cycle contract preserved: at most one TierAction
with should_close_partial=True per evaluate(). realized_pnl estimates
are now NET of est_fee_bps on the closed notional.

evaluate(position, current_price, sigma_bar_pct=None) — the third arg
is optional; every rev-2 call site still works unchanged.
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from core.codes import Code, tag
from risk.protocols import give_back_stop
from core.sanitize import safe_float as _f

log = logging.getLogger("liquiditybot.risk.profit_tiers")

_BAR_MINUTES = 5.0     # matches the data feeds' candle interval


@dataclass
class TierAction:
    should_close_partial: bool
    close_pct: float          # % of *current* position size to close
    realized_pnl: float       # estimated PnL of this close (net of est fees)
    tier_fired: int = 0
    # True ONLY for a scheduled profit-target TAKE (price reached the tier
    # trigger). A protective floor/trail/BE exit also carries tier_fired>0
    # (= tiers already closed) for bookkeeping, but is risk-off, not a take -
    # it must NOT get maker-first resting treatment. Default False preserves
    # the interface (invariant 7).
    is_profit_take: bool = False


class ProfitTierEngine:
    def __init__(self, config: dict):
        cfg = config or {}
        self.tiers = [cfg.get("tier_1", {}), cfg.get("tier_2", {}),
                      cfg.get("tier_3", {}), cfg.get("tier_4", {})]
        self.trailing_stop_config = cfg.get("trailing_stop", {})
        self.vol_scaled = bool(cfg.get("vol_scaled", False))
        self.be_after_tier = int(cfg.get("be_after_tier", 1))
        self.be_buffer_bps = _f(cfg.get("be_buffer_bps", 6.0), 6.0)
        self.est_fee_bps = max(_f(cfg.get("est_fee_bps", 0.0)), 0.0)
        self.chandelier_k = max(_f(cfg.get("chandelier_k", 3.0), 3.0), 0.5)
        self.chandelier_bars = max(int(cfg.get("chandelier_bars", 6)), 1)
        self.tighten_after_bars = max(int(cfg.get("tighten_after_bars", 96)), 1)
        self.tighten_factor = min(max(
            _f(cfg.get("tighten_factor", 0.85), 0.85), 0.5), 1.0)
        self.tighten_floor = min(max(
            _f(cfg.get("tighten_floor", 0.45), 0.45), 0.1), 1.0)
        # SIGNAL-DECAY LEASH (rev 5): a runner's thesis is the ENTRY
        # signal; when that signal is no longer confirmed in the
        # position's direction, the chandelier distance shrinks by
        # tighten_factor - the trade gets a shorter leash the moment its
        # reason to exist has decayed, instead of riding a full-width
        # trail on a dead thesis. signal_alive=None (unknown/stale
        # snapshot) changes NOTHING: only a definitive "not confirmed"
        # tightens, and exits can only come SOONER - never later.
        sd = cfg.get("signal_decay", {}) or {}
        self.sd_enabled = bool(sd.get("enabled", False))
        self.sd_tighten = min(max(
            _f(sd.get("tighten_factor", 0.5), 0.5), 0.1), 1.0)
        self._sd_logged = set()
        # INVENTORY-COUPLED CLOSES (rev 5): when the book is crowded,
        # each fired tier retires MORE of the position (close_pct scaled
        # up by inventory pressure, clamped at 100%). Profits bleed
        # inventory down exactly when inventory is the binding risk;
        # a light book keeps the configured runner fraction.
        ic = cfg.get("inventory_coupling", {}) or {}
        self.ic_enabled = bool(ic.get("enabled", False))
        self.ic_max_boost = min(max(
            _f(ic.get("max_boost", 0.5), 0.5), 0.0), 1.0)
        # CONVICTION RUNNER (rev 6): the entry conviction (Position.confidence =
        # meta p(win) at entry) scales the runner's trail leash. A LOW-conviction
        # winner gets a TIGHTER chandelier (banks sooner); a HIGH-conviction one
        # keeps the full leash to run. One-sided by construction (mult <= 1.0), so
        # it only ever brings the exit SOONER — it composes with the ratchet and
        # never loosens a stop. confidence >= neutral_conf, or <= 0 (unknown /
        # restored / synthetic e.g. quant-trial Positions), is a full-leash no-op,
        # so deployed behavior is byte-identical wherever conviction is unknown.
        cr = cfg.get("conviction_runner", {}) or {}
        self.cr_enabled = bool(cr.get("enabled", False))
        self.cr_neutral_conf = min(max(
            _f(cr.get("neutral_conf", 0.70), 0.70), 0.5), 1.0)
        self.cr_min_conf = min(max(
            _f(cr.get("min_conf", 0.55), 0.55), 0.0), self.cr_neutral_conf)
        self.cr_min_trail_mult = min(max(
            _f(cr.get("min_trail_mult", 0.60), 0.60), 0.1), 1.0)
        self._cr_logged = set()
        # STOP-MAGNET NUDGE (v8, Osler 2003/2005): stop clusters sit just
        # past round numbers, and sweep wicks overshoot the level then
        # revert - a trailing stop parked inside that band gets tagged by
        # a pure hunt, not a genuine break. When a trail candidate lands
        # within band_bps of the nearest round level ON ITS SWEEP SIDE
        # (grid auto-scales with price magnitude), it is nudged to
        # band_bps BEYOND the level - always AWAY from price, so the
        # ratchet (which keeps the tighter of current/candidate) can
        # never loosen an existing stop, and exits are never blocked
        # (invariant 5) - only WHERE the trail sits moves. Code default
        # 0.0 = OFF: bare ProfitTierEngine({}) stays byte-identical
        # legacy; config.json profit_taking.stop_magnet turns it on.
        # KNOWN DIVERGENCE: ml/labeling.py's ExitPolicy sim mirrors the
        # trail in PERCENT space and cannot mirror price-anchored magnet
        # nudges - labels may run up to band_bps wider than the live
        # trail on the occasional magnet-adjacent stop; accepted (same
        # class as the sim's other geometry approximations).
        mg = cfg.get("stop_magnet", {}) or {}
        self.mg_band_bps = min(max(_f(mg.get("band_bps", 0.0)), 0.0), 100.0)
        gb = cfg.get("give_back", {}) or {}
        self.gb_enabled = bool(gb.get("enabled", False))
        self.gb_arm_gain_pct = max(_f(gb.get("arm_gain_pct", 1.5), 1.5), 0.05)
        # VOL-SCALED ARM (2026-07-20 tuning pass): a static arm is fitted
        # to one vol regime's MFE envelope and goes stale when vol moves
        # (the 1.5 arm sat above MFE p90 0.72 and armed once in 55
        # trades). arm_vol_mult > 0 arms at mult * sigma_bar_pct - the
        # same rev-3 calculus the tiers use - so the ratchet tracks the
        # envelope it protects. MFE p90 was ~2.4 sigma_bar; 2.0 sits on
        # a verified plateau. 0 (or a missing sigma at eval time) falls
        # back to the static arm_gain_pct.
        self.gb_arm_vol_mult = max(_f(gb.get("arm_vol_mult", 0.0), 0.0),
                                   0.0)
        self.gb_frac = min(max(_f(gb.get("giveback_frac", 0.40), 0.40),
                               0.05), 0.95)
        self.gb_tighten_gain_pct = max(
            _f(gb.get("tighten_gain_pct", 0.0), 0.0), 0.0)
        self.gb_tight_frac = min(max(_f(gb.get("tight_frac", 0.25), 0.25),
                                     0.05), self.gb_frac)
        self._gb_armed_log = set()

    # ------------------------------------------------------------------
    def _estimate_realized_pnl(self, position, current_price: float,
                               close_pct: float) -> float:
        close_size = position.size * (close_pct / 100.0)
        if position.direction == "long":
            gross = (current_price - position.entry_price) * close_size
        else:
            gross = (position.entry_price - current_price) * close_size
        fees = current_price * close_size * (self.est_fee_bps / 1e4)
        return gross - fees

    def _bars_in_trade(self, position, now: Optional[float] = None) -> float:
        """Bars since entry. `now` (epoch seconds) is the engine's injected
        clock — the LAST wall-clock read in the exit path (EX-8/DL-5): under
        replay, datetime.now here made trail-tightening depend on when the
        replay RAN, not on recorded time. None falls back to wall clock
        (standalone/legacy callers only)."""
        opened = getattr(position, "opened_at", None)
        if opened is None:
            return 0.0
        try:
            if opened.tzinfo is None:
                opened = opened.replace(tzinfo=timezone.utc)
            ref = (datetime.fromtimestamp(now, tz=timezone.utc)
                   if now is not None else datetime.now(timezone.utc))
            age_min = (ref - opened).total_seconds() / 60.0
        except (TypeError, AttributeError, OSError, OverflowError, ValueError):
            return 0.0
        return max(age_min / _BAR_MINUTES, 0.0)

    def _tier_trigger_pct(self, tier: dict, sigma_bar_pct) -> float:
        legacy = tier.get("trigger_pct_gain")
        if legacy is None:
            return float("inf")
        legacy = _f(legacy, float("inf"))
        if not self.vol_scaled or sigma_bar_pct is None:
            return legacy
        sig = _f(sigma_bar_pct)
        mult = _f(tier.get("trigger_vol_mult", 0.0))
        if sig <= 0 or mult <= 0:
            return legacy                       # vol feed absent -> exact rev-2
        return min(max(mult * sig, 0.5 * legacy), 3.0 * legacy)

    # ---- exit-floor machinery (break-even + chandelier, ratchet-only) ----
    def _update_high_water(self, position, px: float) -> None:
        # entry_price sanitized: NaN wins both max() and min(), so a
        # corrupt/restored entry_price (feed glitch, bad snapshot) must
        # never enter the comparison raw or high_water is poisoned to NaN
        # on the very first evaluate() and the trailing floor never fires
        # again. Falls back to the current price when entry is unusable.
        e = _f(position.entry_price)
        if e <= 0:
            e = px
        hw = getattr(position, "high_water", None)
        if position.direction == "long":
            best = max(_f(hw, e), px, e)
        else:
            base = _f(hw, e) if hw is not None else e
            best = min(base, px)
        position.high_water = best

    def _trail_distance_frac(self, position, sigma_bar_pct,
                             decay_mult: float = 1.0,
                             now: Optional[float] = None) -> float:
        legacy = max(_f(self.trailing_stop_config.get("trail_pct", 1.0), 1.0),
                     0.01) / 100.0
        dist = legacy
        if sigma_bar_pct is not None:
            sig = _f(sigma_bar_pct) / 100.0
            if sig > 0:
                dist = max(legacy,
                           self.chandelier_k * sig *
                           math.sqrt(self.chandelier_bars))
        bars = self._bars_in_trade(position, now)
        if bars > self.tighten_after_bars:
            decay = self.tighten_factor ** ((bars - self.tighten_after_bars)
                                            / 48.0)
            dist *= max(decay, self.tighten_floor)
        return dist * min(max(decay_mult, 0.1), 1.0)

    def _conviction_trail_mult(self, position) -> float:
        """Entry-conviction runner leash. Returns a trail-distance multiplier in
        (0, 1]: 1.0 (full leash) for high conviction (>= neutral_conf) or unknown
        conviction (<= 0, e.g. a restored/synthetic Position), shrinking linearly
        to min_trail_mult as conviction falls to min_conf. Tighten-only, so a
        low-conviction winner banks sooner while a high-conviction one runs."""
        if not self.cr_enabled:
            return 1.0
        conf = _f(getattr(position, "confidence", 0.0))
        if conf <= 0.0 or conf >= self.cr_neutral_conf:
            return 1.0
        span = max(self.cr_neutral_conf - self.cr_min_conf, 1e-9)
        t = min(max((self.cr_neutral_conf - conf) / span, 0.0), 1.0)
        mult = 1.0 - (1.0 - self.cr_min_trail_mult) * t
        pid = getattr(position, "position_id", position.symbol)
        if pid not in self._cr_logged:
            self._cr_logged.add(pid)
            log.info(tag(Code.TP_CONVICTION_LEASH,
                         f"{position.symbol} low entry-conviction {conf:.2f} "
                         f"(< {self.cr_neutral_conf:.2f}) — runner trail "
                         f"tightened x{mult:.2f}"))
        return mult

    @staticmethod
    def _magnet_grid(px: float) -> float:
        """Round-number grid for the magnet check, auto-scaled to price
        magnitude (~1% of price, snapped to a power of 10): BTC 118432 ->
        1000, ETH 3600 -> 100, SOL 180 -> 1, ADA 0.45 -> 0.01. Round
        levels = multiples of this grid - the numbers retail stops
        cluster against (Osler: stop-loss orders pool just past round
        numbers)."""
        return 10.0 ** round(math.log10(px) - 2.0)

    def _magnet_adjust(self, direction: str, px: float) -> float:
        """Nudge a stop candidate out of the stop-hunt band around the
        nearest round level on its sweep side. LONG: the stop sits below
        price and a sweep comes DOWN through the magnet, so the relevant
        level is the nearest at/above the stop (ceil); a stop within
        band_bps under it moves to band_bps BELOW the level. SHORT is the
        mirror (floor / above). Always moves AWAY from price - wider,
        never tighter - so composed with the ratchet it can only place
        NEW stop ground, never loosen held ground. band 0 or bad px =
        exact no-op."""
        band = self.mg_band_bps
        if band <= 0.0 or px <= 0.0:
            return px
        g = self._magnet_grid(px)
        # min/max clamp: at the far edge of the band the nudged level can
        # land a hair (<= band^2, ~0.06bp at 25bps) on the TIGHT side of
        # the raw candidate; clamping to the raw candidate makes "away
        # from price, never tighter" exact instead of approximate.
        if direction == "long":
            magnet = math.ceil(px / g) * g
            if (magnet - px) / px * 1e4 < band:
                return min(px, magnet * (1.0 - band / 1e4))
        else:
            magnet = math.floor(px / g) * g
            if (px - magnet) / px * 1e4 < band:
                return max(px, magnet * (1.0 + band / 1e4))
        return px

    def _ratchet_stop(self, position, candidate: float,
                      magnet: bool = True) -> None:
        # magnet=False is for the BREAK-EVEN floor: its contract is
        # locking entry + fees + buffer exactly, and a widening nudge
        # would betray it (a BE floor below breakeven is not breakeven).
        if magnet:
            candidate = self._magnet_adjust(position.direction, candidate)
        cur = position.trailing_stop_price
        if position.direction == "long":
            if cur is None or candidate > cur:
                position.trailing_stop_price = candidate
        else:
            if cur is None or candidate < cur:
                position.trailing_stop_price = candidate

    def _give_back_candidate(self, position, sigma_bar_pct=None):
        """Stop that locks (1 - frac) of the PEAK move once armed by the
        peak gain itself. Returns a price or None while disarmed. Pure
        function of (entry, high_water, config): restart-safe."""
        if not self.gb_enabled:
            return None
        e = _f(position.entry_price)
        if e <= 0:
            return None
        hw = _f(getattr(position, "high_water", None), e)
        long = position.direction == "long"
        peak_gain = ((hw - e) if long else (e - hw)) / e * 100.0
        arm = self.gb_arm_gain_pct
        if self.gb_arm_vol_mult > 0.0 and sigma_bar_pct is not None:
            sig = _f(sigma_bar_pct)
            if sig > 0.0:
                arm = self.gb_arm_vol_mult * sig
        if peak_gain < arm:
            return None
        frac = self.gb_frac
        if 0.0 < self.gb_tighten_gain_pct <= peak_gain:
            frac = self.gb_tight_frac
        key = (position.symbol, round(e, 8))
        if key not in self._gb_armed_log:
            self._gb_armed_log.add(key)
            log.info("give-back armed %s: peak %.2f%% — locking %.0f%% of "
                     "the move", position.symbol, peak_gain,
                     (1.0 - frac) * 100.0)
        return float(give_back_stop(e, hw, long, frac))

    def _exit_floor_hit(self, position, px: float, sigma_bar_pct,
                        signal_alive=None,
                        now: Optional[float] = None) -> bool:
        ts_cfg = self.trailing_stop_config
        activate_after = int(ts_cfg.get("activate_after_tier", 2))
        trail_on = bool(ts_cfg.get("enabled", False)) and \
            position.tier_closed >= activate_after
        be_on = position.tier_closed >= self.be_after_tier
        gb_cand = self._give_back_candidate(position, sigma_bar_pct)

        if not trail_on and not be_on and gb_cand is None \
                and position.trailing_stop_price is None:
            return False

        if be_on:
            buf = (2.0 * self.est_fee_bps + self.be_buffer_bps) / 1e4
            be_px = position.entry_price * (1.0 + buf) \
                if position.direction == "long" \
                else position.entry_price * (1.0 - buf)
            # arm the floor only once price has actually CLEARED it. When
            # the tier-1 trigger sits below the fee buffer (vol-scaled
            # triggers or tier_scale<0.86 regimes), ratcheting be_px in
            # unconditionally installed a floor ABOVE the market — an
            # instant exit BELOW breakeven, with tiers 2-4/chandelier as
            # dead code (audit EX-1 2026-07-17). Once armed while clear,
            # the ratchet holds if price falls back — tighten-only intact.
            cleared = (px > be_px) if position.direction == "long" \
                else (px < be_px)
            if cleared:
                self._ratchet_stop(position, be_px, magnet=False)

        if trail_on:
            decay_mult = 1.0
            if self.sd_enabled and signal_alive is False:
                decay_mult = self.sd_tighten
                pid = getattr(position, "position_id", position.symbol)
                if pid not in self._sd_logged:
                    self._sd_logged.add(pid)
                    log.info(tag(Code.TP_SIGNAL_DECAY,
                                 f"{position.symbol} entry signal decayed - "
                                 f"trail tightened x{self.sd_tighten:.2f}"))
            elif signal_alive is True:
                # thesis re-confirmed: allow the full leash again (the
                # ratchet still never loosens an already-tight stop)
                self._sd_logged.discard(
                    getattr(position, "position_id", position.symbol))
            # entry-conviction leash composes multiplicatively with signal
            # decay: both are tighten-only factors <= 1.0.
            decay_mult *= self._conviction_trail_mult(position)
            dist = self._trail_distance_frac(position, sigma_bar_pct,
                                             decay_mult=decay_mult, now=now)
            # same NaN-entry guard as _update_high_water: the chandelier
            # anchor must never fall back to a raw, possibly-NaN
            # entry_price (which _magnet_grid's round(math.log10(...))
            # can't even accept), so it collapses to the live px instead.
            e = _f(position.entry_price)
            if e <= 0:
                e = px
            anchor = _f(getattr(position, "high_water", None), e) or e
            if anchor <= 0:
                anchor = px
            cand = anchor * (1.0 - dist) if position.direction == "long" \
                else anchor * (1.0 + dist)
            self._ratchet_stop(position, cand)

        if gb_cand is not None:
            self._ratchet_stop(position, gb_cand)

        stop = position.trailing_stop_price
        if stop is None:
            return False
        return px <= stop if position.direction == "long" else px >= stop

    # ------------------------------------------------------------------
    def evaluate(self, position, current_price: float,
                 sigma_bar_pct=None, signal_alive=None,
                 inventory_pressure: float = 0.0,
                 now: Optional[float] = None) -> TierAction:
        """Next unfired tier first, then the ratcheting exit floor
        (break-even + chandelier). One action max per cycle.

        rev-5 optional inputs (defaults preserve rev-3/4 exactly):
        signal_alive       True/False = the entry signal is / is no
                           longer confirmed in this direction; None =
                           unknown (stale or missing snapshot) - no-op.
        inventory_pressure 0..1 crowding of the book; scales fired-tier
                           close_pct up by ic_max_boost at full pressure.
        """
        px = _f(current_price)
        if px <= 0:
            return TierAction(False, 0.0, 0.0)

        self._update_high_water(position, px)
        gain_pct = position.unrealized_pnl_pct(px)
        next_tier_index = position.tier_closed

        if next_tier_index < len(self.tiers):
            tier = self.tiers[next_tier_index]
            trigger = self._tier_trigger_pct(tier, sigma_bar_pct)
            close_pct = _f(tier.get("close_pct_of_position", 0.0))
            if close_pct > 0 and gain_pct >= trigger:
                boost_note = ""
                if self.ic_enabled and inventory_pressure > 0:
                    p = min(max(_f(inventory_pressure), 0.0), 1.0)
                    boosted = min(close_pct * (1.0 + self.ic_max_boost * p),
                                  100.0)
                    if boosted > close_pct + 0.5:
                        boost_note = " " + tag(
                            Code.TP_INV_COUPLING,
                            f"close {close_pct:.0f}%->{boosted:.0f}% "
                            f"(inventory pressure {p:.2f})")
                        close_pct = boosted
                pnl = self._estimate_realized_pnl(position, px, close_pct)
                log.info(
                    "Tier %d triggered for %s: gain=%.2f%% (trigger=%.2f%%"
                    "%s), closing %.0f%%%s", next_tier_index + 1,
                    position.symbol, gain_pct, trigger,
                    ", vol-scaled" if (self.vol_scaled and
                                       sigma_bar_pct is not None) else "",
                    close_pct, boost_note)
                return TierAction(True, close_pct, pnl,
                                  tier_fired=next_tier_index + 1,
                                  is_profit_take=True)

        if self._exit_floor_hit(position, px, sigma_bar_pct,
                                signal_alive=signal_alive, now=now):
            pnl = self._estimate_realized_pnl(position, px, 100.0)
            log.info("Exit floor hit for %s at %s (stop=%.6g, hw=%.6g)",
                     position.symbol, px,
                     position.trailing_stop_price or 0.0,
                     _f(getattr(position, "high_water", 0.0)))
            return TierAction(True, 100.0, pnl, tier_fired=next_tier_index)

        return TierAction(False, 0.0, 0.0)
