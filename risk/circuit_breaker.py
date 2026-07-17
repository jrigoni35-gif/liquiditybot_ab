"""risk/circuit_breaker.py — per-asset consecutive-loss circuit breaker.

The failure mode this exists for: one asset's regime turns hostile and the
bot keeps re-entering it — five small stop-outs on the same pair in an
afternoon while every OTHER asset is fine. The portfolio-level rails (loss
budgets, drawdown throttle) react late because each individual loss is small;
the per-asset streak is the early, local signal. Professional desks pull a
misbehaving symbol off the sheet and revisit later — this automates exactly
that, and nothing more:

  * trips after `loss_streak` CONSECUTIVE full-trade losses on one asset;
  * while tripped, NEW entries on that asset are vetoed (SZ-046);
  * exits are NEVER touched (invariant 5 — this module is not even consulted
    on the exit path);
  * auto-resets after `cooldown_hours` — no operator intervention required,
    and a win resets the streak at any time;
  * separate from PerformanceTracker BY DESIGN: that ledger is contractually
    telemetry-only; this class owns its own streaks because it IS a decision
    input, persisted across restarts so a trip can't be laundered by a reboot.
"""
import logging
import time

log = logging.getLogger("liquiditybot.risk.circuit_breaker")


class CircuitBreaker:
    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", True))
        self.loss_streak = max(int(cfg.get("loss_streak", 4)), 2)
        self.cooldown_s = max(float(cfg.get("cooldown_hours", 6.0)), 0.25) \
            * 3600.0
        self._streaks: dict = {}         # asset -> consecutive losses
        self._tripped_at: dict = {}      # asset -> trip timestamp

    # ------------------------------------------------------------------
    def record_close(self, asset: str, won: bool,
                     now: float | None = None) -> bool:
        """Feed one FULL trade close (hedges excluded by the caller).
        Returns True if this close tripped the breaker."""
        if not self.enabled:
            return False
        now = now if now is not None else time.time()
        asset = str(asset)
        if won:
            self._streaks[asset] = 0
            return False
        streak = self._streaks.get(asset, 0) + 1
        self._streaks[asset] = streak
        if streak >= self.loss_streak and asset not in self._tripped_at:
            self._tripped_at[asset] = now
            log.warning(
                "circuit breaker TRIPPED for %s: %d consecutive losses — "
                "new entries blocked for %.1fh (exits unaffected)",
                asset, streak, self.cooldown_s / 3600.0)
            return True
        return False

    def is_tripped(self, asset: str, now: float | None = None) -> bool:
        """True while `asset` is in its cooldown. Expiry auto-clears the trip
        AND the streak (the pause itself is the fresh start)."""
        if not self.enabled:
            return False
        t = self._tripped_at.get(str(asset))
        if t is None:
            return False
        now = now if now is not None else time.time()
        if now - t >= self.cooldown_s:
            self._tripped_at.pop(str(asset), None)
            self._streaks[str(asset)] = 0
            log.info("circuit breaker for %s auto-reset after cooldown",
                     asset)
            return False
        return True

    def remaining_s(self, asset: str, now: float | None = None) -> float:
        t = self._tripped_at.get(str(asset))
        if t is None:
            return 0.0
        now = now if now is not None else time.time()
        return max(self.cooldown_s - (now - t), 0.0)

    # ------------------------------------------------------------------
    def snapshot(self, now: float | None = None) -> dict:
        now = now if now is not None else time.time()
        return {"enabled": self.enabled,
                "loss_streak": self.loss_streak,
                "streaks": {a: s for a, s in self._streaks.items() if s > 0},
                "tripped": {a: round(self.remaining_s(a, now) / 3600.0, 2)
                            for a in list(self._tripped_at)
                            if self.is_tripped(a, now)}}

    def to_dict(self) -> dict:
        return {"streaks": dict(self._streaks),
                "tripped_at": dict(self._tripped_at)}

    def restore(self, d: dict | None) -> None:
        if not d:
            return
        try:
            self._streaks = {str(k): int(v)
                             for k, v in (d.get("streaks") or {}).items()}
            self._tripped_at = {str(k): float(v)
                                for k, v in (d.get("tripped_at") or {}).items()}
        except (TypeError, ValueError, AttributeError):
            log.warning("circuit breaker restore malformed - starting clean")
            self._streaks, self._tripped_at = {}, {}
