"""
core/watchdog.py

Tail-event sentry. The existing risk stack handles the market being
against you; this module handles the *infrastructure* being against
you - the class of failures that only matter on the worst day:

  STALE DATA      Kraken stops answering. Marks freeze, so stops
                  evaluate against a dead price while the real market
                  moves. Trip 1 (warn threshold): block new entries.
                  Trip 2 (critical threshold, live, positions open):
                  fire an operator alert - the book is unprotected.

  VENUE DIVERGENCE  Kraken's mid dislocates from the OKX/Binance.US
                  composite fair value beyond a band. Either Kraken is
                  printing bad data, the composite is poisoned, or a
                  venue-specific event is underway. All three mean:
                  no new risk until they re-agree.

  PNL VELOCITY    The drawdown hard stop is a *level* trigger; a flash
                  crash rips through levels faster than a daily limit
                  was designed for. This is a *rate* trigger: equity
                  drop > X% within a rolling window halts new entries
                  immediately, independent of absolute drawdown.

  TICK QUARANTINE A single anomalous print (fat-finger trade, feed
                  glitch) must not be allowed to fire every stop on the
                  book. A mark that jumps more than `tick_jump_pct` in
                  one fast cycle is quarantined: stops hold for exactly
                  one cycle and only act if the NEXT tick confirms the
                  move. A real crash confirms 5 seconds later; a bogus
                  print does not. (Quarantine never delays anything but
                  stop *triggering*; it never blocks exits in flight.)

All state is exported for status.json. All thresholds config-driven
under "watchdog". The module is pure bookkeeping - it never talks to
the network and never raises.
"""

import logging
from collections import deque
from dataclasses import dataclass, field

log = logging.getLogger("liquiditybot.core.watchdog")


@dataclass
class WatchdogState:
    entries_blocked: bool = False
    reasons: list = field(default_factory=list)
    stale_assets: list = field(default_factory=list)
    critical_stale: bool = False
    divergent_assets: list = field(default_factory=list)
    pnl_velocity_pct: float = 0.0
    velocity_tripped: bool = False
    quarantined: dict = field(default_factory=dict)   # asset -> pending mark


class Watchdog:
    def __init__(self, config: dict, alerts=None):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", True))
        self.stale_warn_sec = float(cfg.get("stale_warn_sec", 30))
        self.stale_critical_sec = float(cfg.get("stale_critical_sec", 120))
        self.divergence_bps = float(cfg.get("max_venue_divergence_bps", 150))
        self.vel_window_sec = float(cfg.get("pnl_velocity_window_sec", 900))
        self.vel_max_drop_pct = float(cfg.get("pnl_velocity_max_drop_pct", 6.0))
        self.vel_cooldown_sec = float(cfg.get("pnl_velocity_cooldown_sec", 1800))
        self.tick_jump_pct = float(cfg.get("tick_jump_quarantine_pct", 8.0))
        # a "confirmed" second tick must move at least this fraction of
        # the initial jump in the same direction - lower is stricter about
        # ratifying quarantined moves as real
        self.tick_confirm_ratio = float(cfg.get("tick_confirm_ratio", 0.5))
        self.alerts = alerts

        self._equity_hist: deque = deque()      # (ts, equity)
        self._vel_tripped_at: float = 0.0
        self._last_mark: dict = {}              # asset -> last accepted mark
        self._quarantine: dict = {}             # asset -> proposed mark
        self.state = WatchdogState()

    # ------------------------------------------------------------------
    # tick quarantine
    # ------------------------------------------------------------------
    def filter_mark(self, asset: str, new_mark: float) -> tuple:
        """Returns (mark_for_stops, stop_eval_allowed).

        Normal ticks pass straight through. A tick that jumps more than
        tick_jump_pct vs the last accepted mark is quarantined for one
        call: stops don't evaluate this cycle. If the next tick is also
        beyond the jump band in the same direction, the move is real -
        it is accepted and stops fire normally (one cycle late, ~5s).
        If the next tick returns inside the band, the outlier is
        discarded and never touched a stop."""
        if not self.enabled or new_mark <= 0:
            return new_mark, True
        last = self._last_mark.get(asset)
        if last is None or last <= 0:
            self._last_mark[asset] = new_mark
            return new_mark, True
        jump_pct = abs(new_mark - last) / last * 100.0
        pending = self._quarantine.get(asset)
        if pending is None:
            if jump_pct >= self.tick_jump_pct:
                self._quarantine[asset] = new_mark
                log.warning(f"tick quarantine {asset}: {last:.2f} -> "
                            f"{new_mark:.2f} ({jump_pct:+.1f}%) - holding "
                            f"stops one cycle for confirmation")
                # report the anomalous mark but suppress stop evaluation
                return new_mark, False
            self._last_mark[asset] = new_mark
            return new_mark, True
        # we had a quarantined tick; does this one confirm it?
        same_dir = (new_mark - last) * (pending - last) > 0
        confirmed = same_dir and jump_pct >= self.tick_jump_pct * self.tick_confirm_ratio
        del self._quarantine[asset]
        if confirmed:
            log.warning(f"tick quarantine {asset}: move CONFIRMED at "
                        f"{new_mark:.2f} - stops live")
            self._last_mark[asset] = new_mark
            return new_mark, True
        log.warning(f"tick quarantine {asset}: outlier discarded "
                    f"(next tick {new_mark:.2f} back inside band)")
        self._last_mark[asset] = new_mark
        return new_mark, True

    # ------------------------------------------------------------------
    # main evaluation - call once per fast cycle
    # ------------------------------------------------------------------
    def evaluate(self, now: float, book_ts: dict, assets: list,
                 kraken_mids: dict, fair_values: dict, equity: float,
                 open_positions: int, dry_run: bool) -> WatchdogState:
        st = WatchdogState()
        if not self.enabled:
            self.state = st
            return st

        # --- staleness ---------------------------------------------------
        for a in assets:
            # CUT #10 (B1): a book that NEVER arrived is STALE, not fresh.
            # `get(a, now)` read a never-delivered asset as age 0 - neither
            # warn-stale nor critical-stale - so an asset the feed silently
            # dropped never tripped the sweep. The fail-closed sibling in
            # main.py (`get(asset, 0.0)`, age == now) had it right all along;
            # this was the fail-open half, pinned as a strict xfail in
            # tests/test_fail_open_pins.py until the boundary that could carry
            # it. Entry-decisioning consequence: entries_blocked now flips True
            # for a never-delivered asset. That is the intended reading.
            age = now - book_ts.get(a, 0.0)
            if age >= self.stale_warn_sec:
                st.stale_assets.append(a)
            if age >= self.stale_critical_sec:
                st.critical_stale = True
        if st.stale_assets:
            st.reasons.append(f"stale data: {','.join(st.stale_assets)}")
        if st.critical_stale and open_positions > 0 and not dry_run \
                and self.alerts is not None:
            self.alerts.fire(
                "stale_critical",
                f"execution-venue data stale > {self.stale_critical_sec:.0f}s "
                f"with {open_positions} open position(s). Stops are blind. "
                f"Check connectivity / consider manual intervention.")

        # --- venue divergence ---------------------------------------------
        for a in assets:
            mid = kraken_mids.get(a) or 0.0
            fv = fair_values.get(a) or 0.0
            if mid > 0 and fv > 0:
                div_bps = abs(mid - fv) / fv * 1e4
                if div_bps >= self.divergence_bps:
                    st.divergent_assets.append(f"{a}:{div_bps:.0f}bps")
        if st.divergent_assets:
            st.reasons.append(f"venue divergence: "
                              f"{','.join(st.divergent_assets)}")

        # --- pnl velocity ----------------------------------------------------
        if equity > 0:
            self._equity_hist.append((now, equity))
        cutoff = now - self.vel_window_sec
        while self._equity_hist and self._equity_hist[0][0] < cutoff:
            self._equity_hist.popleft()
        if len(self._equity_hist) >= 2:
            peak = max(e for _, e in self._equity_hist)
            if peak > 0:
                st.pnl_velocity_pct = (equity - peak) / peak * 100.0
        if st.pnl_velocity_pct <= -self.vel_max_drop_pct:
            if now - self._vel_tripped_at > self.vel_cooldown_sec \
                    and self.alerts is not None:
                self.alerts.fire(
                    "pnl_velocity",
                    f"equity dropped {st.pnl_velocity_pct:.1f}% inside "
                    f"{self.vel_window_sec/60:.0f}min (limit "
                    f"{self.vel_max_drop_pct}%). New entries halted.")
            self._vel_tripped_at = now
        # velocity trip latches for the cooldown window
        st.velocity_tripped = (now - self._vel_tripped_at
                               < self.vel_cooldown_sec) \
            and self._vel_tripped_at > 0
        if st.velocity_tripped:
            st.reasons.append(
                f"pnl velocity trip ({st.pnl_velocity_pct:.1f}% / "
                f"{self.vel_window_sec/60:.0f}min)")

        st.quarantined = dict(self._quarantine)
        st.entries_blocked = bool(st.reasons)
        self.state = st
        return st

    # ------------------------------------------------------------------
    def note_evaluation_failure(self, reason: str) -> None:
        """The caller (main.py) isolates a raise out of evaluate() so exits
        never starve on a broken watchdog (invariant #5) - but evaluate()
        only assigns `self.state` at its very end, so a raise partway
        through leaves the PRIOR state in place. If that prior state was
        healthy (entries_blocked=False), every consumer of
        watchdog.state.entries_blocked (algo-child stepping, hedge-open,
        the entry-scan hard return) would fail OPEN during the one
        incident that breaks the watchdog itself. Force the entries side
        closed for as long as evaluate() keeps failing: this flips
        entries_blocked in place (exits never consult it) and stays
        flipped until the NEXT evaluate() call fully succeeds and
        computes a fresh state."""
        self.state.entries_blocked = True
        if reason not in self.state.reasons:
            self.state.reasons.append(reason)

    # ------------------------------------------------------------------
    def status(self) -> dict:
        s = self.state
        return {"entries_blocked": s.entries_blocked,
                "reasons": s.reasons,
                "stale_assets": s.stale_assets,
                "critical_stale": s.critical_stale,
                "divergent": s.divergent_assets,
                "pnl_velocity_pct": round(s.pnl_velocity_pct, 2),
                "velocity_tripped": s.velocity_tripped,
                "quarantined": {k: round(v, 2)
                                for k, v in s.quarantined.items()}}
