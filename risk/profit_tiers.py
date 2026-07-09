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

from risk.protocols import give_back_stop

log = logging.getLogger("liquiditybot.risk.profit_tiers")

_BAR_MINUTES = 5.0     # matches the data feeds' candle interval


def _f(x, default=0.0) -> float:
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


@dataclass
class TierAction:
    should_close_partial: bool
    close_pct: float          # % of *current* position size to close
    realized_pnl: float       # estimated PnL of this close (net of est fees)
    tier_fired: int = 0


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
        gb = cfg.get("give_back", {}) or {}
        self.gb_enabled = bool(gb.get("enabled", False))
        self.gb_arm_gain_pct = max(_f(gb.get("arm_gain_pct", 1.5), 1.5), 0.05)
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

    def _bars_in_trade(self, position) -> float:
        opened = getattr(position, "opened_at", None)
        if opened is None:
            return 0.0
        try:
            if opened.tzinfo is None:
                opened = opened.replace(tzinfo=timezone.utc)
            age_min = (datetime.now(timezone.utc) - opened).total_seconds() / 60.0
        except (TypeError, AttributeError):
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
        hw = getattr(position, "high_water", None)
        if position.direction == "long":
            best = max(_f(hw, position.entry_price), px, position.entry_price)
        else:
            base = _f(hw, position.entry_price) if hw is not None \
                else position.entry_price
            best = min(base, px)
        position.high_water = best

    def _trail_distance_frac(self, position, sigma_bar_pct) -> float:
        legacy = max(_f(self.trailing_stop_config.get("trail_pct", 1.0), 1.0),
                     0.01) / 100.0
        dist = legacy
        if sigma_bar_pct is not None:
            sig = _f(sigma_bar_pct) / 100.0
            if sig > 0:
                dist = max(legacy,
                           self.chandelier_k * sig *
                           math.sqrt(self.chandelier_bars))
        bars = self._bars_in_trade(position)
        if bars > self.tighten_after_bars:
            decay = self.tighten_factor ** ((bars - self.tighten_after_bars)
                                            / 48.0)
            dist *= max(decay, self.tighten_floor)
        return dist

    def _ratchet_stop(self, position, candidate: float) -> None:
        cur = position.trailing_stop_price
        if position.direction == "long":
            if cur is None or candidate > cur:
                position.trailing_stop_price = candidate
        else:
            if cur is None or candidate < cur:
                position.trailing_stop_price = candidate

    def _give_back_candidate(self, position):
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
        if peak_gain < self.gb_arm_gain_pct:
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

    def _exit_floor_hit(self, position, px: float, sigma_bar_pct) -> bool:
        ts_cfg = self.trailing_stop_config
        activate_after = int(ts_cfg.get("activate_after_tier", 2))
        trail_on = bool(ts_cfg.get("enabled", False)) and \
            position.tier_closed >= activate_after
        be_on = position.tier_closed >= self.be_after_tier
        gb_cand = self._give_back_candidate(position)

        if not trail_on and not be_on and gb_cand is None \
                and position.trailing_stop_price is None:
            return False

        if be_on:
            buf = (2.0 * self.est_fee_bps + self.be_buffer_bps) / 1e4
            be_px = position.entry_price * (1.0 + buf) \
                if position.direction == "long" \
                else position.entry_price * (1.0 - buf)
            self._ratchet_stop(position, be_px)

        if trail_on:
            dist = self._trail_distance_frac(position, sigma_bar_pct)
            anchor = _f(getattr(position, "high_water", None),
                        position.entry_price) or position.entry_price
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
                 sigma_bar_pct=None) -> TierAction:
        """Next unfired tier first, then the ratcheting exit floor
        (break-even + chandelier). One action max per cycle."""
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
                pnl = self._estimate_realized_pnl(position, px, close_pct)
                log.info(
                    "Tier %d triggered for %s: gain=%.2f%% (trigger=%.2f%%"
                    "%s), closing %.0f%%", next_tier_index + 1,
                    position.symbol, gain_pct, trigger,
                    ", vol-scaled" if (self.vol_scaled and
                                       sigma_bar_pct is not None) else "",
                    close_pct)
                return TierAction(True, close_pct, pnl,
                                  tier_fired=next_tier_index + 1)

        if self._exit_floor_hit(position, px, sigma_bar_pct):
            pnl = self._estimate_realized_pnl(position, px, 100.0)
            log.info("Exit floor hit for %s at %s (stop=%.6g, hw=%.6g)",
                     position.symbol, px,
                     position.trailing_stop_price or 0.0,
                     _f(getattr(position, "high_water", 0.0)))
            return TierAction(True, 100.0, pnl, tier_fired=next_tier_index)

        return TierAction(False, 0.0, 0.0)
