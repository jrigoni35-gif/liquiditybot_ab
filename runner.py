"""
runner.py - the process that drives the engine.

The engine (main.LiquidityBot) is loop-free: it exposes cycle_once().
This runner owns the ONLY loop in the system, and around each cycle it:

  1. consumes control commands from outputs/control/ (dropped by the
     git remote-control plane or by hand: any JSON {"cmd": ...} file works)
  2. runs one engine cycle if state is RUNNING (or a step was requested)
  3. writes the full UI-facing status to outputs/status.json (atomic)
     and appends the equity curve point
  4. snapshots on cadence (the engine also snapshots after every fill)

Commands: start, pause, stop, step, snapshot, entries_on, entries_off,
arm_live (requires confirm phrase), disarm_live, force_dry (one-way
LIVE->DRY), flatten_all,
sim_price_shock / sim_force_fear / sim_force_regime / sim_clear
(sim_* are refused outright when config is live).

Run:  python runner.py [--config config.json] [--fresh] [--paused]
"""

import argparse
import sys
import os
import logging
import math
import time
from pathlib import Path
from typing import Callable, Optional

from core import code_stats
from core.audit import get_audit
from core.goals import goal_progress
from core.persistence import StateStore
from core.precision import round_price
from core.runtime import (ARM_PHRASE, ControlChannel, JsonlLogHandler,
                          SingleInstanceLock, StatusWriter)
from core.session_digest import write_digest
from main import LiquidityBot, load_config

log = logging.getLogger("liquiditybot.runner")


def merge_skimmer_universe(config: dict,
                           active_path: str = "outputs/skimmer_active.json"
                           ) -> list:
    """Widen trading_pairs with the skimmer's persisted promotions — called
    ONLY from the live entrypoint (main). Replay/smoke/overfit construct
    LiquidityBot(cfg) directly and never pass through here, so the quant
    battery stays pinned to its recorded universe. Promotions apply in
    dry-run always; in live only with skimmer.apply_in_live. Bounded by the
    skimmer's max_extra and the config-guard 12-pair fallback envelope.
    Returns the pairs that were merged (for logs/tests)."""
    sk_cfg = (config or {}).get("skimmer", {}) or {}
    if not bool(sk_cfg.get("enabled")):
        return []
    if not (bool(config.get("system", {}).get("dry_run", True))
            or bool(sk_cfg.get("apply_in_live", False))):
        return []
    from core.skimmer import AssetSkimmer
    core = list(config.get("exchanges", {}).get("kraken", {})
                .get("trading_pairs", []))
    extra = AssetSkimmer.load_active(active_path, core,
                                     int(sk_cfg.get("max_extra", 6)))
    if extra:
        # write through setdefault so a config missing exchanges/kraken (the
        # read above degrades to []) can't KeyError on the write-back
        config.setdefault("exchanges", {}).setdefault(
            "kraken", {})["trading_pairs"] = core + extra
        # Guard-visible provenance: promoted pairs already consumed the
        # promotion budget, so config_guard must not count max_extra against
        # them again (2026-07-25 false FATAL: 6 core + 6 merged read as 18).
        config.setdefault("skimmer", {})["_merged_promoted"] = list(extra)
        log.warning("skimmer: universe widened for this boot: %d core + "
                    "promoted %s", len(core), extra)
    return extra


class BotRunner:
    def __init__(self, config: dict, bot: LiquidityBot | None = None,
                 start_paused: bool = False, resume: bool = True,
                 lock: SingleInstanceLock | None = None):
        self.config = config
        self._lock = lock
        self.bot = bot or LiquidityBot(config, resume=resume)
        self._rec_sink = None
        if config.get("system", {}).get("record_feeds"):
            from data.replay import FeedRecorder
            from data.recording import (DEFAULT_MAX_FILE_MB,
                                        DEFAULT_RETAIN_DAYS,
                                        DEFAULT_RETAIN_FILES, SinkRotator,
                                        pnl_snapshot, prune_recordings,
                                        session_sink, update_sidecar)
            sys_cfg = config["system"]
            rec_dir = sys_cfg.get("recording_dir", "outputs/recordings")
            rc = sys_cfg.get("recording", {}) or {}
            now = time.time()
            # retention: keep months of session files bounded (age + count) so
            # a long-running recorder never fills the disk
            try:
                dropped = prune_recordings(
                    rec_dir, rc.get("retain_days", DEFAULT_RETAIN_DAYS),
                    rc.get("retain_files", DEFAULT_RETAIN_FILES), now)
                if dropped:
                    log.info("recording retention pruned %d old session(s)",
                             len(dropped))
            except Exception:
                log.exception("recording prune failed - continuing")
            # Recording SETUP is fail-soft: a bad recording_dir (OSError) or a
            # non-numeric max_file_mb (ValueError) must DISABLE recording, never
            # take down the boot — record_feeds is default-true now. On failure
            # before the feeds are wrapped, recording simply stays off.
            try:
                sink = session_sink(rec_dir, now)
                max_bytes = int(rc.get("max_file_mb", DEFAULT_MAX_FILE_MB)) \
                    * (1 << 20)
                rotator = SinkRotator(sink, max_bytes)   # shared: recorders roll together
                for name in ("okx", "binanceus", "kraken"):
                    setattr(self.bot, name,
                            FeedRecorder(getattr(self.bot, name), name,
                                         rotator=rotator))
                self._rec_sink = sink
                # flat-start sidecar: the reconciliation gate ties replay P&L to
                # THIS session's live P&L delta; a clean tie-out wants a flat start.
                # self_contained: every engine input was recorded, so replay ties
                # out EXACTLY. False when an unrecorded feed was live — reconcile
                # then only WARNs, never hard-fails. The Kraken/Binance WS book
                # streams (websockets.*) drive fills FIRST (main.py get_order_book)
                # but are NOT wrapped by FeedRecorder — only the REST fallback is —
                # so any active WS book source makes the recording NON-self-contained.
                _ws = config.get("websockets", {}) or {}
                start_snap = pnl_snapshot(
                    self.bot.state.realized_pnl_total, self.bot._equity(),
                    self.bot.state.open_position_count(), now)
                start_snap["self_contained"] = not (
                    config.get("sentiment", {}).get("enabled")
                    or config.get("webdata", {}).get("enabled")
                    or config.get("moomoo", {}).get("enabled")
                    or _ws.get("kraken_enabled")
                    or _ws.get("enabled"))
                update_sidecar(sink, "start", start_snap)
                log.warning(f"feed recording ON -> {sink} (replay it with "
                            f"scripts/replay.py)")
            except Exception:
                log.exception("feed recording setup failed - recording disabled "
                              "for this session; bot continues normally")
        # asset skimmer: watches the candidate pool (<=2 REST calls per loop
        # pass, self-throttled) and persists promotions for the NEXT boot's
        # universe merge in main(). Core = booted pairs minus persisted
        # promotions, so a promoted pair keeps being scored (else it could
        # never be demoted). Telemetry+file only — never trades.
        try:
            from core.skimmer import AssetSkimmer
            _booted = list(config.get("exchanges", {}).get("kraken", {})
                           .get("trading_pairs", []))
            _promoted = AssetSkimmer.load_active(
                "outputs/skimmer_active.json", [], 99)
            self.skimmer = AssetSkimmer(
                config.get("skimmer", {}),
                getattr(self.bot, "kraken", None),
                core_pairs=[p for p in _booted if p not in _promoted])
        except Exception:                    # telemetry must never block boot
            log.exception("skimmer init failed - running without it")
            self.skimmer = None
        self.control = ControlChannel()
        # purge STALE commands queued before this runner existed: a leftover
        # "stop" from a previous life otherwise executes at boot and kills the
        # fresh runner within its first cycle (observed live: two stale stops
        # consumed at +1.2s -> instant shutdown). Commands are for the runner
        # that is alive when they are sent, not whichever starts next.
        stale = self.control.consume()
        if stale:
            log.warning("discarded %d stale control command(s) queued before "
                        "startup: %s", len(stale),
                        [c.get("cmd") for c in stale])
        self.status = StatusWriter()
        self._last_status: dict = {}
        api_cfg = (config or {}).get("api_server", {})
        from api.rest_server import RestStatusServer
        from api.grpc_server import GrpcStatusServer
        self.rest_api = RestStatusServer(
            api_cfg.get("rest", {}),
            status_provider=lambda: self._last_status,
            control_send=self.control.send)
        self.grpc_api = GrpcStatusServer(
            api_cfg.get("grpc", {}),
            status_provider=lambda: self._last_status,
            control_send=self.control.send)
        self.rest_api.start()
        self.grpc_api.start()
        # DURABLE risk-off: pause and entries_off survive every restart via
        # sentinel files. Without them, ANY relaunch — supervisor revive,
        # keepalive, the 15-min auto-updater — silently reverted an
        # operator's risk-off back to full-risk-on (audit F2 2026-07-17).
        # start/entries_on delete the sentinels; nothing else does.
        self._paused_sentinel = Path("outputs") / "paused.on"
        self._entries_off_sentinel = Path("outputs") / "entries_off.on"
        self.state = ("PAUSED" if (start_paused
                                   or self._paused_sentinel.exists())
                      else "RUNNING")
        if self.state == "PAUSED" and self._paused_sentinel.exists():
            log.warning("boot PAUSED: outputs/paused.on present (operator "
                        "risk-off survives restarts; send 'start' to resume)")
        if self._entries_off_sentinel.exists():
            self.bot.entries_enabled = False
            log.warning("boot with entries DISABLED: outputs/entries_off.on "
                        "present (send 'entries_on' to re-enable)")
        self._step_requested = False
        self._stop = False
        self._forfeited = False   # duplicate-runner exit: peer owns the book
        self.poll_sec = self.bot.poll_sec
        # wedge guard: a cycle_once that raises EVERY iteration used to spin
        # forever logging "continuing" while no stops/entries ran and the
        # dashboard showed nothing wrong. Count consecutive failures; after
        # cycle_fail_halt of them, latch new-risk halt (exits still run each
        # cycle - invariant #5) and fire ONE loud alert. We never auto-flatten
        # (a transient feed outage must not dump the book) and never self-
        # terminate (a deterministic fault would just relaunch-storm); the
        # operator sees the alert + status and intervenes.
        self._cycle_fail_streak = 0
        self._cycle_fail_halt = int(
            config.get("system", {}).get("cycle_fail_halt", 10))
        self._wedge_alerted = False
        self._wedge_latched = False     # cycle_wedged fault currently latched
        self._recover_streak = 0        # consecutive healthy cycles since a wedge

    # ------------------------------------------------------------------
    @staticmethod
    def _set_sentinel(p: Path) -> None:
        try:
            p.parent.mkdir(exist_ok=True)
            p.touch()
        except OSError:
            log.warning("could not write sentinel %s - the risk-off will "
                        "NOT survive a restart", p)

    @staticmethod
    def _clear_sentinel(p: Path) -> None:
        try:
            p.unlink()
        except OSError:
            pass

    # ------------------------------------------------------------------
    def handle_command(self, c: dict, now: Optional[float] = None):
        cmd, args = c["cmd"], c.get("args", {})
        bot = self.bot
        note = ""
        if cmd == "start":
            self.state = "RUNNING"
            self._clear_sentinel(self._paused_sentinel)
        elif cmd == "pause":
            self.state = "PAUSED"
            self._set_sentinel(self._paused_sentinel)
        elif cmd == "stop":
            self._stop = True
        elif cmd == "step":
            self._step_requested = True
        elif cmd == "snapshot":
            ok = bot.store.snapshot(bot)
            note = f"snapshot {'saved' if ok else 'FAILED'}"
        elif cmd == "entries_on":
            bot.entries_enabled = True
            self._clear_sentinel(self._entries_off_sentinel)
        elif cmd == "entries_off":
            bot.entries_enabled = False
            self._set_sentinel(self._entries_off_sentinel)
        elif cmd == "arm_live":
            if bot.dry_run:
                note = "REFUSED: config is dry_run - arming is meaningless"
            elif args.get("confirm") != ARM_PHRASE:
                note = f"REFUSED: confirm phrase must be exactly '{ARM_PHRASE}'"
            else:
                bot.live_armed = True
                note = "LIVE TRADING ARMED by operator"
        elif cmd == "disarm_live":
            bot.live_armed = False
            note = "live trading disarmed (exits still allowed)"
        elif cmd == "clear_fault":
            # operator override for the fault authority: name the fault to
            # clear (FaultManager requires an explicit key — "clear everything"
            # is deliberately not offered). Re-enables new risk if it was the
            # last fault. The wedge also auto-recovers on a healthy streak.
            fm = getattr(bot, "fault", None)
            key = args.get("key", "")
            if fm is None:
                note = "no fault authority"
            elif not key:
                note = f"REFUSED: name the fault to clear ({fm.status()['faults']})"
            else:
                cleared = fm.clear_fault(key, operator="control")
                if key == "cycle_wedged":
                    self._wedge_latched = False
                    self._recover_streak = 0
                note = (f"fault {key} cleared -> op-state {fm.status()['state']}"
                        if cleared else f"no such fault {key!r}")
        elif cmd == "force_dry":
            # one-way, safe-direction only: LIVE -> DRY. There is no
            # command that sets dry_run False; returning to live requires
            # config dry_run=false + restart + typed ARM phrase.
            if bot.dry_run:
                note = "already dry-run"
            else:
                # W2-5: cancel every still-resting LIVE venue order BEFORE
                # flipping the flags. Flipping first left any resting order
                # routed through _poll_dry from the NEXT poll onward, which
                # SIMULATES a fill on an order genuinely resting on Kraken -
                # in the 0..deadman_sec window before the venue dead-man
                # cancels it, a real fill could land with no local record
                # (and with deadman_timeout_sec=0 it rests unmanaged
                # forever). cancel_order() is called while
                # bot.orders.dry_run is STILL False so it takes the live
                # path (venue CancelOrder + final-fill reconciliation query)
                # rather than the dry-run no-op.
                cancelled = 0
                for o in list(bot.orders.open_orders()):
                    try:
                        if bot.orders.cancel_order(o, reason="force_dry"):
                            cancelled += 1
                            log.warning("force_dry: cancelled resting live "
                                        "order %s %s %s (txid=%s)",
                                        o.side, o.pair, o.purpose, o.txid)
                    except Exception:
                        log.exception("force_dry: cancel failed for order "
                                      "%s (txid=%s) - flags still seal new "
                                      "risk; venue dead-man is the backstop",
                                      o.order_id, o.txid)
                bot.live_armed = False
                bot.dry_run = True
                bot.orders.dry_run = True     # OrderManager caches the flag
                note = (f"FORCED DRY-RUN by operator - {cancelled} resting "
                        f"live order(s) cancelled, live order paths sealed; "
                        f"live again = config + restart + ARM")
        elif cmd == "flatten_all":
            # per-position isolation: an emergency flatten must not half-
            # complete silently because one position errors on exit submission
            # - every OTHER position still gets flattened, and the ack reports
            # the truth (submitted vs failed) instead of a blanket "requested".
            submitted, failed = 0, 0
            for pos in list(bot.state.open_positions()):
                try:
                    # W2-6: pass the loop's INJECTED now, not a wall-clock
                    # fallback - this is the one exit path that used to sit
                    # outside the injected-now discipline every other exit
                    # call site already follows (replay/determinism parity).
                    bot._submit_exit(pos, 100.0, "operator flatten_all",
                                     now=now)
                    submitted += 1
                except Exception:
                    failed += 1
                    log.exception("[%s] flatten_all exit submission raised - "
                                  "flattening the rest", pos.symbol)
            note = f"flatten submitted for {submitted} position(s)"
            if self.state == "PAUSED":
                # W2-6: orders.poll/refresh_deadman still run every tick while
                # paused (see _run_paused_order_maintenance) so these exits
                # are not left resting unmanaged until the venue's dead-man
                # cancels them with no local reconciliation.
                note += "; exits will be managed while paused"
            if failed:
                note += f"; {failed} FAILED to submit - see log, retry"
        elif cmd.startswith("sim_"):
            if not bot.dry_run:
                note = "REFUSED: simulations are dry-run only"
            elif cmd == "sim_price_shock":
                bot.sim.price_shock[args.get("asset", "ETH")] = {
                    "pct": float(args.get("pct", -5.0)),
                    "cycles": int(args.get("cycles", 3))}
            elif cmd == "sim_force_fear":
                bot.sim.force_fear = int(args.get("cycles", 6))
            elif cmd == "sim_force_regime":
                bot.sim.force_regime[args.get("asset", "ETH")] = {
                    "label": args.get("label", "crisis"),
                    "cycles": int(args.get("cycles", 12))}
            elif cmd == "sim_clear":
                bot.sim.price_shock.clear()
                bot.sim.force_regime.clear()
                bot.sim.force_fear = 0
        log.warning(f"control: {cmd} {args or ''} -> "
                    f"{note or 'ok'} (runner={self.state})")

    # ------------------------------------------------------------------
    @staticmethod
    def _rp_status(bot, equity: float) -> dict:
        """Risk-protocol posture for the trading dashboard's §6. Every number
        comes from the stack's/sizer's OWN attributes and module formulas —
        telemetry duplicates no thresholds. Never raises; on any fault the
        section is simply {} (a blank panel, never a wedged status write)."""
        try:
            rp = getattr(bot, "risk_protocols", None)
            sizer = getattr(bot, "sizer", None)
            if rp is None or sizer is None:
                return {}
            from risk.protocols import budget_taper_mult
            d_frac, w_frac = rp.spent_fracs(equity)
            heat = sizer._open_heat_frac(bot.state, bot.marks, equity)
            dd = max(float(bot.state.drawdown_mtm_pct(equity)), 0.0)
            throttle = 1.0
            if sizer.hard_stop_dd_pct > 1e-9 and dd > 0:
                frac = min(dd / sizer.hard_stop_dd_pct, 1.0)
                throttle = max((1.0 - frac) ** sizer.dd_throttle_power,
                               sizer.dd_throttle_floor)
            return {
                "daily_budget_used_frac": round(float(d_frac), 4),
                "weekly_budget_used_frac": round(float(w_frac), 4),
                "taper_mult": round(float(budget_taper_mult(
                    max(d_frac, w_frac), rp.bd_taper_start, rp.bd_floor)), 4),
                "heat_frac": round(float(heat), 4),
                "heat_cap_frac": rp.ht_max,
                "dd_throttle_mult": round(float(throttle), 4),
            }
        except Exception:
            log.exception("risk-protocol status failed - section omitted")
            return {}

    @staticmethod
    def _probe_budget_status(bot, now: float) -> dict:
        """SPB-R §8 telemetry (docs/superpowers/specs/2026-07-30-probe-
        budget-spbr-design.md): the engine's own probe_budget_status()
        verbatim - bucket level, governor, trailing-24h counters,
        per-asset eff_weight, per-regime live labels. getattr-guarded
        ({} for a pre-SPB-R bot or a minimal test stub) and never raises
        - on any fault the section is simply {} (a blank panel, never a
        wedged status write; the _rp_status convention)."""
        try:
            fn: "Optional[Callable[[float], dict]]" = getattr(
                bot, "probe_budget_status", None)
            return fn(now) if callable(fn) else {}
        except Exception:
            log.exception("probe-budget status failed - section omitted")
            return {}

    @staticmethod
    def _long_book_status(bot, now: float) -> dict:
        """Compounder Phase C long-book posture (task C4). hasattr-guarded
        (bot.long_ladder absent -> {}, same convention as _rp_status
        above): a bot built before this task, or a minimal test stub,
        simply omits the section rather than raising. Every number comes
        from the engine's OWN attributes/ladder - telemetry duplicates no
        thresholds. pf_live is JSON-safe (None, never the raw `inf` a
        win-only window produces - risk/long_book.py's EvidenceLadder.
        pf_live docstring)."""
        ladder = getattr(bot, "long_ladder", None)
        if ladder is None:
            return {}
        try:
            lb_cfg = bot.config.get("long_book", {}) or {}
            positions = [p for p in bot.state.open_positions()
                        if getattr(p, "book", "5m") == "long"]
            # C4 review, Minor #8: also count resting long-book entry
            # orders (now load-bearing - order_ttl_hours can leave a bid
            # resting for hours, so a filled-positions-only figure would
            # understate true exposure for most of that window).
            resting_orders = [o for o in bot.orders.open_orders()
                              if o.purpose == "entry"
                              and o.meta.get("book", "5m") == "long"]
            book_exposure_usd = sum(
                p.size * (bot.marks.get(p.symbol) or p.entry_price)
                for p in positions) + \
                sum(o.remaining * o.price for o in resting_orders)
            ceiling_frac = ladder.paper_ceiling_frac() if bot.dry_run \
                else ladder.live_ceiling_frac()
            last_ts = getattr(bot, "_long_last_add_ts", {}) or {}
            last_add_age_h = (
                round((now - max(last_ts.values())) / 3600.0, 2)
                if last_ts else None)
            pf_live = ladder.pf_live
            return {
                "enabled": bool(lb_cfg.get("enabled", False)),
                "rung": ladder.rung(),
                "ceiling_frac": round(float(ceiling_frac), 4),
                "book_exposure_usd": round(float(book_exposure_usd), 2),
                "positions": len(positions),
                "adds_placed": int(getattr(bot, "_long_adds_placed", 0)),
                "last_add_age_h": last_add_age_h,
                "paused_reason": getattr(bot, "_long_last_deny", "") or "",
                "closed_paper": ladder.closed_paper,
                "closed_live": ladder.closed_live,
                "pf_live": round(pf_live, 4) if math.isfinite(pf_live)
                else None,
                "context_aligned_last": getattr(
                    bot, "_long_context_aligned_last", None),
            }
        except Exception:
            log.exception("long-book status failed - section omitted")
            return {}

    @staticmethod
    def _goal_progress(bot) -> dict:
        """Live period-to-date progress toward the config profit goals,
        for the status surface / Grafana (measurement only). 0 goal ->
        untracked (goal_progress handles it)."""
        cm = bot.config.get("capital_management", {})
        return {
            "week": goal_progress("week", bot.state.weekly_realized_pnl,
                                  cm.get("weekly_profit_goal_usd", 0) or 0),
            "month": goal_progress("month", bot.state.monthly_realized_pnl,
                                   cm.get("monthly_profit_goal_usd", 0) or 0),
        }

    def build_status(self, now: float) -> dict:
        bot = self.bot
        marks = bot.marks
        positions = []
        pm = getattr(bot.orders, "pair_meta", {})
        for p in bot.state.open_positions():
            pair = bot.kraken.kraken_pair(p.symbol)
            mark = marks.get(p.symbol) or p.entry_price
            # entry <= 0 is never a real fill. Without this guard the uPnL
            # below evaluates to mark*size - the ENTIRE notional shown as
            # fake profit (observed on a just-opened position flashing a
            # +$218 "winner"). Show a null uPnL and log it loudly so the
            # transient that produces a zero entry gets caught at the source.
            bad_entry = not (p.entry_price and p.entry_price > 0)
            if bad_entry:
                log.warning("status: %s %s serialized with entry_price=%r "
                            "(<=0) - uPnL suppressed; investigate the open "
                            "path", p.symbol, p.position_id[:8], p.entry_price)
            positions.append({
                "id": p.position_id[:8], "symbol": p.symbol,
                "direction": p.direction, "size": round(p.size, 8),
                # prices at per-asset venue precision (sub-dollar pairs keep
                # >=4 decimals) - a hardcoded 2 quantized ARB/MINA/FLOW into
                # a wrong entry/mark and a wrong on-screen uPnL. uPnL itself
                # is computed from FULL-precision entry_price, then rounded as
                # a dollar/pct value.
                "entry": round_price(p.entry_price, pm, pair),
                "mark": round_price(mark, pm, pair),
                "upnl_pct": None if bad_entry
                else round(p.unrealized_pnl_pct(mark), 3),
                "upnl_usd": None if bad_entry
                else round((mark - p.entry_price) * p.size *
                                  (1 if p.direction == "long" else -1), 2),
                "stop": round_price(p.stop_price, pm, pair)
                if p.stop_price else None,
                "trail": round_price(p.trailing_stop_price, pm, pair)
                if p.trailing_stop_price else None,
                "tiers_fired": p.tier_closed,
                "age_h": round((now - p.opened_at.timestamp()) / 3600.0, 1),
                "p_win": round(p.confidence, 2), "hedge": p.is_hedge,
                "fees_usd": round(p.fees_paid_usd, 2),
            })
        orders = [{
            "id": o.order_id, "symbol": o.symbol, "side": o.side,
            "purpose": o.purpose,
            "price": round_price(o.price, pm, bot.kraken.kraken_pair(o.symbol)),
            "size": round(o.size, 8), "fill": round(o.fill_ratio * 100, 1),
            "age_s": round(now - o.created_ts, 1), "status": o.status,
        } for o in bot.orders.open_orders()]
        regimes = {}
        for a in bot.symbol_map:
            m, v, lq, f = (bot.macro.state(a), bot.vol.state(a),
                           bot.liq.state(a), bot.fv.state(a))
            regimes[a] = {"macro": m.label, "momentum": round(m.momentum_score, 2),
                          "vol": v.label, "vol_pct": round(v.percentile, 0),
                          "liq": lq.label, "spread_bps": round(lq.spread_bps, 1),
                          "spoof": round(lq.spoof_score, 2),
                          "basis_bps": round(f.basis_bps, 1)}
        sent = bot.xscan.snapshot()
        web = bot.webdata.snapshot()
        risk = bot.moomoo.snapshot()
        equity = bot._equity()
        return {
            "ts": now, "cycle": bot._cycle,
            "cycle_lifetime": getattr(bot, "_cycle_lifetime", 0),
            "runner_state": self.state,
            "mode": "DRY_RUN" if bot.dry_run else
                    ("LIVE_ARMED" if bot.live_armed else "LIVE_DISARMED"),
            "entries_enabled": bot.entries_enabled, "halted": bot._halted,
            # central fault authority: op-state (ARMED/DEGRADED/HALTED) + the
            # latched-fault table. Was dead/dark before it was wired in.
            "fault": (bot.fault.status() if getattr(bot, "fault", None)
                      else {"state": "UNKNOWN", "faults": {}}),
            "equity": round(equity, 2),
            "cash": round(bot.state.cash_balance, 2),
            "savings": round(bot.state.savings_balance, 2),
            "reserve": round(bot.state.reserve_balance, 2),
            "weekly_pnl": round(bot.state.weekly_realized_pnl, 2),
            "monthly_pnl": round(bot.state.monthly_realized_pnl, 2),
            "goals": self._goal_progress(bot),
            "daily_pnl": round(bot.state.daily_realized_pnl, 2),
            "realized_total": round(bot.state.realized_pnl_total, 2),
            "fees_total": round(bot.state.fees_paid_total, 2),
            "drawdown_pct": round(bot.state.drawdown_pct(), 2),
            "latency_ms": round(bot.orders.latency_ms, 1),
            "feed_latency_ms": round(getattr(bot.kraken, "latency_ms", 0.0), 1),
            # truthful mark freshness: feed_latency_ms only updates on a
            # SUCCESSFUL Kraken call, so a Ticker outage freezes prices AND
            # freezes the latency gauge - stale marks read as live everywhere.
            # marks_age_sec = age of the OLDEST live mark; it climbs the moment
            # a price stops updating, giving the UI a real staleness signal.
            "marks_age_sec": round(max(
                (now - bot._mark_ts.get(s, now)
                 for s in bot.marks), default=0.0), 1),
            "positions": positions, "open_orders": orders,
            # shallow-copy: the REST/gRPC provider returns _last_status from an
            # API thread while the engine thread mutates bot.last_signals in
            # slow_cycle - a live reference risks a torn read / "dict changed
            # size". Copied like manip_suspect below. The file path is already
            # safe (serialized in-thread), this covers the API path.
            "signals": dict(getattr(bot, "last_signals", {})),
            "exec_algos": bot.algo.status() if hasattr(bot, "algo") else {},
            "regimes": regimes,
            "sentiment": {"score": round(sent.score, 3),
                          "fear": sent.fear_spike,
                          "euphoria": sent.euphoria_spike,
                          "available": sent.available,
                          "per_source": sent.per_source,
                          "per_figure": sent.per_figure},
            "webdata": {"fear_greed": web.fear_greed,
                        "btc_dominance": round(web.btc_dominance, 2),
                        "dominance_delta": round(web.dominance_delta, 3),
                        "available": web.available},
            "context": bot.context.status() if hasattr(bot, "context") else {},
            "moomoo": {"risk_z": round(risk.risk_z, 2),
                       "basket_ret_pct": risk.basket_ret_pct,
                       "per_ticker": risk.per_ticker,
                       "available": risk.available,
                       "opt_pcr": risk.opt_pcr,
                       "opt_pcr_z": round(risk.opt_pcr_z, 2),
                       "opt_oi_pcr": risk.opt_oi_pcr,
                       "opt_oi_pcr_z": round(risk.opt_oi_pcr_z, 2),
                       "opt_iv_skew": round(risk.opt_iv_skew, 3),
                       "options_available": risk.options_available},
            "manip_suspect": dict(getattr(bot, "_manip_scores", {})),
            "watchdog": bot.watchdog.status(),
            "equity_drift_pct": round(bot._equity_drift_pct, 3),
            "monitor": bot.monitor.status(),
            "conviction": bot.conviction.status()
                if hasattr(bot, "conviction") else {},
            "long_book": self._long_book_status(bot, now)
                if hasattr(bot, "long_ladder") else {},
            "ml": {"trained": bot.meta.trained,
                   "drift_share": bot.monitor.drift_share,
                   "drifting": bot.monitor.drifting[:5],
                   "model_kind": getattr(bot.meta.model, "kind", None),
                   "history_rows": bot.history.row_count(),
                   # learning-velocity split (§5): live = ground truth,
                   # candidate = triple-barrier proxy
                   "labels_by_source": bot.history.source_counts(),
                   "pending_labels": len(bot.history._pending),
                   "open_candidates": len(bot.candidates._cands),
                   "retrain_flag": bot.monitor.flag_path.exists(),
                   "retrain_calib_gap": getattr(bot, "_last_retrain_calib_gap", {}),
                   # failure-visibility counters: each event logs, but only
                   # a surfaced cumulative count exposes the TREND of a
                   # subsystem quietly dying behind in-range neutral values
                   "model_fallbacks": bot.meta.fallbacks,
                   "infer_faults": bot.meta.infer_faults,
                   "contract_failed": bot.meta.contract.failed,
                   "smc_faults": getattr(bot.smc, "compute_faults", 0),
                   # rising -> retrain silently failing every cycle, stale
                   # champion kept forever (was invisible before)
                   "retrain_failures": getattr(bot, "_retrain_failures", 0),
                   # AFML corpus-quality stats from the last training load:
                   # clean live count (evidence gate), mean average-uniqueness
                   # (overlap redundancy), ML-074 prior-skew flag, and (label-
                   # era instrumentation, DEEP DIVE progress.md) per-era/per-
                   # exit-reason label rates ("label_era") + the ML-080
                   # barrier-mix drift alarm ("era_mix_drift") - written
                   # verbatim, so these ride along for free
                   "load_stats": getattr(bot.history, "last_load_stats", {}),
                   # geometry-alignment T6 (spec D6, ML-082): labeled-vs-
                   # realized bracket comparator, a bounded window updated
                   # incrementally at CLOSE time (unlike load_stats above,
                   # which only refreshes on a retrain) - see HistoryStore.
                   # bracket_divergence_summary's docstring. Report-only.
                   "bracket_divergence": bot.history.bracket_divergence_summary()
                   if hasattr(bot.history, "bracket_divergence_summary")
                   else {},
                   # SPB-R probe budget (§8): mode/tokens/governor +
                   # trailing-24h counters + per-asset eff_weight -
                   # schema EXTENDED, never broken ({} pre-SPB-R)
                   "probe_budget": self._probe_budget_status(bot, now),
                   "gate_stats": bot.gate_stats.summary()},
            "audit_dropped_writes": get_audit().dropped,
            # torn final lines recovered on adoption (unclean stops). Rising ->
            # the process is being killed mid-write repeatedly.
            "audit_tail_truncations": getattr(get_audit(), "tail_truncations", 0),
            # per-position exit/stop evaluations that RAISED and were isolated
            # (one bad position no longer starves the rest of the book's
            # stops). Rising -> a position is wedging its own escape path.
            "exit_eval_failures": getattr(bot, "_exit_eval_failures", 0),
            # consecutive whole-cycle failures; at cycle_fail_halt the runner
            # latches a new-risk halt and alerts. Nonzero -> cycle_once is
            # raising and the loop is degraded (was invisible before).
            "cycle_consecutive_failures": self._cycle_fail_streak,
            # previously-dark fault ledgers — status() methods the runner never
            # called. Firewall's latched fault + per-code reject tallies; the
            # order manager's venue rejects (OM-021) and dead-man refresh
            # failures (OM-050); and the central reason-code frequency ledger
            # (every PT-/SZ-/RP-/FW-/… emission). Surfaced for the incidents
            # dashboard so nothing keeps failing invisibly.
            # post-fill mark-out: empirical adverse selection per asset+horizon
            # (negative bps = our entries are being scalped)
            "markout": bot.markout.snapshot()
            if getattr(bot, "markout", None) is not None else {},
            # rolling trade-performance ledger (win-rate/PF/expectancy/streak,
            # portfolio + per asset) — the trading dashboard's §1
            "performance": bot.perf.snapshot()
            if getattr(bot, "perf", None) is not None else {},
            # risk-protocol posture (§6): budget consumption + the CURRENT
            # multipliers, computed from the stack's/sizer's OWN attributes and
            # formulas — no constants duplicated into telemetry
            "risk_protocols": self._rp_status(bot, equity),
            # asset skimmer: candidate rankings + the promoted set that will
            # join the universe at the next restart
            "skimmer": _sk.snapshot()
            if (_sk := getattr(self, "skimmer", None)) is not None else {},
            # per-asset consecutive-loss breaker: active pauses + streaks
            "circuit_breaker": bot.breaker.snapshot(now)
            if getattr(bot, "breaker", None) is not None else {},
            "firewall": bot.firewall.status()
            if getattr(bot, "firewall", None) is not None else {},
            "order_manager": bot.orders.status()
            if getattr(bot, "orders", None) is not None else {},
            "code_stats": {"by_prefix": code_stats.by_prefix(),
                           "top": code_stats.top(15),
                           # entry-decision families in FULL (§4 signal-edge
                           # panels): top-N crowding by chatty TH/SZ codes must
                           # not blank the EV-gate / exploration-rate view.
                           # Bounded by the code registry (~25 PT/SZ codes).
                           "entry_codes": {
                               k: v for k, v in code_stats.snapshot().items()
                               if k.startswith(("PT-", "SZ-"))}},
            "thales": bot.thales.status(now) if hasattr(bot, "thales") else {},
            "ws": bot.ws_manager.health()
            if getattr(bot, "ws_manager", None) is not None else {},
            "ws_kraken": _kws.health()
            if (_kws := getattr(bot, "kraken_ws", None)) is not None else {},
            "sim": bot.sim.describe(),
        }

    # ------------------------------------------------------------------
    def _note_cycle_ok(self, recovered: bool = True):
        """A clean cycle_once clears the failure streak. If a wedge was latched,
        require a SUSTAINED healthy streak (cycle_fail_halt successes) before
        auto-clearing it — enough to ride out a flapping feed without resuming
        risk on one lucky cycle. (review A1-F1: the wedge must be RECOVERABLE,
        not a permanent strand.)

        recovered=False (the PAUSED branch): a paused runner is healthy in the
        sense that it isn't accumulating failures — reset the streak/alert —
        but a pause proves NOTHING about cycle health, so it must never
        advance the wedge-recovery streak. Before this split, a latched
        CRITICAL cycle_wedged fault auto-cleared after cycle_fail_halt PAUSED
        loop ticks with zero successful cycles, re-enabling new risk on false
        evidence the moment the operator resumed."""
        self._cycle_fail_streak = 0
        self._wedge_alerted = False
        if not recovered:
            return                # pause: no evidence of recovery — hold latch
        if self._wedge_latched:
            self._recover_streak += 1
            if self._recover_streak >= self._cycle_fail_halt:
                self._wedge_latched = False
                self._recover_streak = 0
                fm = getattr(self.bot, "fault", None)
                if fm is not None:
                    try:
                        fm.clear_fault("cycle_wedged", operator="auto-recover")
                    except Exception:
                        log.exception("wedge fault-clear failed")
                log.warning("cycle wedge cleared after %d healthy cycles - "
                            "new risk re-enabled", self._cycle_fail_halt)

    def _note_cycle_failure(self) -> int:
        """One cycle_once failure. At cycle_fail_halt consecutive failures,
        latch a CRITICAL fault ('cycle_wedged') in the fault authority — which
        refuses NEW risk (op-state HALTED) while exits keep running every cycle
        (invariant #5) — and fire ONE loud alert. We DON'T touch bot._halted:
        that flag is the persisted CATASTROPHE latch; the wedge uses the
        process-scoped, RECOVERABLE fault instead, so a transient feed blip
        self-heals (healthy streak, or a restart re-arms the FM) rather than
        stranding the bot after a restart. Never auto-flatten / self-terminate.
        Returns the streak for the caller's log."""
        self._cycle_fail_streak += 1
        self._recover_streak = 0
        if self._cycle_fail_streak >= self._cycle_fail_halt \
                and not self._wedge_alerted:
            self._wedge_alerted = True
            self._wedge_latched = True
            fm = getattr(self.bot, "fault", None)
            if fm is not None:
                try:
                    from core.fault import Severity
                    fm.latch("cycle_wedged", Severity.CRITICAL,
                             f"cycle_once raised {self._cycle_fail_streak}x "
                             f"consecutively - new risk refused until it recovers")
                except Exception:
                    log.exception("wedge fault-latch failed")
            try:
                self.bot.alerts.fire(
                    "runner_wedged",
                    f"cycle_once raised {self._cycle_fail_streak} times in a "
                    f"row - refusing NEW risk until it recovers. Exit ORDERS "
                    f"are never gated by this halt (invariant #5), and the "
                    f"hourly/slow refit + every pre-stop stage are isolated so "
                    f"the per-position stop loop still runs; a raise in an "
                    f"un-isolated pre-stop path can still skip a cycle's exit "
                    f"evaluation, so check exit_eval_failures + the logs.")
            except Exception:
                log.exception("wedge alert failed - fault still latched")
        return self._cycle_fail_streak

    # ------------------------------------------------------------------
    def _run_paused_order_maintenance(self, now: float) -> None:
        """W2-6: while PAUSED, exit-purpose orders already in flight (an
        operator flatten_all, or a resting exit from before the pause) must
        still be MANAGED - invariant #5 is pause blocks NEW risk, it never
        blocks an escape. Before this, handle_command ran every loop tick
        even while paused, but orders.poll (fills/timeouts + the live
        dead-man refresh, both inside OrderManager.poll for the non-dry
        path) only ran inside cycle_once/fast_cycle - so a flatten order sat
        resting unmanaged until the venue's blunt ~60s dead-man cancelled it
        with NO local reconciliation (a fill landing in that window would be
        silently lost).

        Deliberately NOT the full fast_cycle: no marks/books refetch, no
        stop/derisk/hedge evaluation runs here - only the order-maintenance
        slice, so no new-risk path can execute while paused. Gated on at
        least one EXIT-purpose order being open so a plain pause with an
        empty book (the overwhelming common case) costs nothing extra.
        Isolated like every other telemetry/maintenance slice in the loop:
        never raises, never touches the wedge-failure streak."""
        bot = self.bot
        om = getattr(bot, "orders", None)
        if om is None:
            return
        try:
            open_orders = om.open_orders()
        except Exception:
            log.exception("paused order-maintenance: open_orders() raised")
            return
        if not any(o.purpose == "exit" for o in open_orders):
            return
        try:
            sig = {a: bot.vol.state(a).sigma_bar_pct for a in bot.symbol_map}
            fills = om.poll(bot.kraken_books, sig, now)
        except Exception:
            log.exception("paused order-maintenance: orders.poll raised - "
                          "continuing (venue dead-man is the backstop)")
            return
        for event in fills:
            try:
                bot._handle_fill(event, now)
            except Exception:
                log.exception("paused order-maintenance: fill apply raised "
                              "for one event - continuing with the rest")

    # ------------------------------------------------------------------
    def run(self):
        bot = self.bot
        # single dense startup line - the operator sees mode, capital,
        # guardrail budgets, and resume status at a glance
        oh = "on" if bot.orders.deadman_sec > 0 else "off"
        log.info(
            f"runner starting: {'DRY' if bot.dry_run else 'LIVE'} "
            f"state={self.state} equity=${bot._equity():,.0f} "
            f"cap=${bot.state.starting_capital:,.0f} "
            f"fees={bot.orders.maker_fee_bps:.0f}/"
            f"{bot.orders.taker_fee_bps:.0f}bps "
            f"deadman={oh}({bot.orders.deadman_sec}s) "
            f"resumed={bot._resumed}")
        # startup self-test (live): a skewed clock corrupts nonces, order
        # timestamps and staleness math - surface it before trading
        if not bot.dry_run:
            try:
                skew = bot.kraken.get_server_time_skew_sec()
                if skew is not None and abs(skew) > 2.0:
                    bot.alerts.fire(
                        "clock_skew",
                        f"local clock is {skew:+.1f}s vs Kraken server "
                        f"time - fix NTP before arming live trading")
                elif skew is not None:
                    log.info(f"clock skew vs venue: {skew:+.2f}s (ok)")
            except Exception:
                log.warning("clock skew check unavailable")
        try:
            while not self._stop:
                now = time.time()
                # heartbeat BEFORE the cycle body: a repeatedly-raising cycle
                # (feed outage, etc.) must not let the lock go stale while
                # this process is alive - a stale lock invites a second
                # runner to take over and duplicate the loop.
                if self._lock is not None:
                    if not self._lock.refresh() and self._lock.forfeited:
                        # a LIVE peer owns this outputs/ dir - we are the
                        # duplicate. Exiting stops new risk only (the peer
                        # keeps managing positions/exits); staying would
                        # race snapshots and eat its control commands.
                        from core.codes import Code
                        log.critical(
                            "%s: lost the instance lock to a live peer "
                            "for %d consecutive heartbeats - this runner "
                            "is a duplicate and is shutting down",
                            Code.RT_DUPLICATE_RUNNER.value,
                            self._lock.lost_count)
                        get_audit().log(
                            "runner", Code.RT_DUPLICATE_RUNNER,
                            "duplicate runner self-terminated (lost "
                            "instance lock to live peer)",
                            {"pid": self._lock.pid,
                             "lost_count": self._lock.lost_count})
                        self._forfeited = True
                        self._stop = True
                        break
                try:
                    # per-command isolation: consume() has already unlinked
                    # every cmd file, so a raise in one command would drop the
                    # REST of the batch — including a queued `stop` behind a
                    # failing `flatten_all`. Each command stands alone.
                    for c in self.control.consume():
                        try:
                            self.handle_command(c, now)
                        except Exception:
                            log.exception("control command %r failed - "
                                          "continuing with the rest",
                                          (c or {}).get("cmd", c)
                                          if isinstance(c, dict) else c)
                    if self._stop:
                        break
                    # ONLY cycle_once feeds the wedge counter (review A1-F2): a
                    # telemetry/snapshot/status-write failure must NEVER escalate
                    # to a trading halt or be misattributed to "cycle_once
                    # raised". A paused runner counts as healthy (clears the
                    # streak) — it isn't wedged.
                    if self.state == "RUNNING" or self._step_requested:
                        stepped = self._step_requested
                        self._step_requested = False
                        try:
                            bot.cycle_once(now)
                        except Exception:
                            n = self._note_cycle_failure()
                            log.exception("cycle_once raised (%d in a row) - "
                                          "continuing", n)
                        else:
                            self._note_cycle_ok()
                            if stepped:
                                log.info(f"stepped one cycle -> {bot._cycle}")
                    else:
                        # paused: not failing, but not proof of recovery either
                        self._note_cycle_ok(recovered=False)
                        # W2-6: exits already in flight (e.g. an operator
                        # flatten_all issued while paused) must still be
                        # MANAGED - invariant #5 is pause blocks NEW risk,
                        # never escapes. NOT the full fast_cycle: no new-risk
                        # path runs here, only fills/timeouts/dead-man.
                        self._run_paused_order_maintenance(now)
                    # telemetry: isolated, never counts toward the wedge streak
                    try:
                        if now - bot._last_snapshot >= bot.snapshot_sec:
                            bot.store.snapshot(bot)
                            bot._last_snapshot = now
                        # skimmer watch tick: self-throttled (round-robin, one
                        # candidate per eval interval); isolated with the rest
                        # of telemetry — a skimmer fault never touches trading
                        if (_sk := getattr(self, "skimmer", None)) is not None:
                            _sk.evaluate(now)
                        snap = self.build_status(now)
                        # write BEFORE publishing to the API threads: write()
                        # mutates snap (adds written_at), and a REST poll
                        # serializing a dict that grows mid-iteration raises
                        # (audit F9 2026-07-17). After write() the dict is
                        # stable, so sharing it is safe.
                        self.status.write(snap, now)
                        self._last_status = snap
                    except Exception:
                        log.exception("status/snapshot write failed - "
                                      "continuing (does not halt trading)")
                except KeyboardInterrupt:
                    log.info("shutdown requested")
                    break
                except Exception:
                    log.exception("runner loop error - continuing")
                elapsed = time.time() - now
                time.sleep(max(self.poll_sec - elapsed, 0.25))
        finally:
            bot.moomoo.close()
            ws = getattr(bot, "ws_manager", None)
            if ws is not None:
                ws.stop()               # join the daemon stream thread
            kws = getattr(bot, "kraken_ws", None)
            if kws is not None:
                kws.stop()              # join the Kraken stream thread
            # finalize the recording sidecar with this session's END P&L, so
            # the replay-vs-live reconciliation gate has both endpoints. A
            # forfeited duplicate leaves the shared dir to the live peer.
            _rec = getattr(self, "_rec_sink", None)
            if _rec is not None and not self._forfeited:
                try:
                    from data.recording import pnl_snapshot, update_sidecar
                    update_sidecar(_rec, "end", pnl_snapshot(
                        bot.state.realized_pnl_total, bot._equity(),
                        bot.state.open_position_count(), time.time()))
                except Exception:
                    log.exception("recording end-sidecar failed")
            if self._forfeited:
                # a LIVE PEER owns this outputs/ dir: the book, the venue
                # orders, the snapshot and status.json are ITS to manage.
                # Running the normal shutdown here clobbered the peer's good
                # snapshot with this duplicate's stale state, flipped its
                # status to STOPPED, and in live mode would have cancelled
                # the peer's resting stops account-wide (audit C-F1
                # 2026-07-17). Stop our own servers and leave.
                try:
                    self.rest_api.stop()
                    self.grpc_api.stop()
                except Exception:
                    log.debug("api server stop failed during forfeit exit")
                log.warning("duplicate-runner exit: venue orders, snapshot "
                            "and status left to the live peer")
            else:
                if not bot.dry_run:
                    # nothing may rest unmanaged while the bot is offline:
                    # cancel every venue order, then disarm the dead-man timer
                    try:
                        if bot.kraken.cancel_all_orders():
                            log.warning("shutdown: all venue orders cancelled")
                        bot.kraken.cancel_all_orders_after(0)
                    except Exception:
                        log.exception("shutdown venue cleanup failed - VERIFY "
                                      "open orders on Kraken manually")
                    if bot.state.open_position_count() > 0:
                        bot.alerts.fire(
                            "shutdown_with_positions",
                            f"bot stopped with "
                            f"{bot.state.open_position_count()} open "
                            f"position(s) and no working orders. The book is "
                            f"UNMANAGED until restart.", level="WARNING")
                ok = bot.store.snapshot(bot)
                try:
                    final = self.build_status(time.time())
                    final["runner_state"] = "STOPPED"
                    self.status.write(final)
                    self.rest_api.stop()
                    self.grpc_api.stop()
                except Exception:
                    log.debug("final status write failed during shutdown")
                log.info(f"final snapshot {'saved' if ok else 'FAILED'} -> "
                         f"{bot.store.path}. Restart with `python runner.py`.")
                # leave a reconciled, machine-readable digest of the run so
                # the next session (operator or agent) can pick up from an
                # accurate summary instead of cross-joining six raw streams.
                # Best-effort: a digest failure never mars a clean shutdown.
                try:
                    d = write_digest("outputs", self.config)
                    log.info(f"session digest: {d['verdict']} -> "
                             f"outputs/session_digest.md")
                except Exception:
                    log.debug("session digest write failed during shutdown")
            if self._lock is not None:
                self._lock.release()   # ownership-aware: no-op when forfeited


def main():
    ap = argparse.ArgumentParser(description="liquiditybot v2 runner")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--fresh", action="store_true",
                    help="ignore and delete saved state")
    ap.add_argument("--paused", action="store_true",
                    help="start paused; use the dashboard or a start command")
    args = ap.parse_args()

    # Windows console hardening: force UTF-8 on stdout/stderr so unicode
    # in log lines never raises UnicodeEncodeError on legacy codepages or
    # redirected output. No-op where streams are already UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
            except (AttributeError, OSError, ValueError):
                # Rare: detached, non-tty, or already-configured streams.
                # This is best-effort; the fallback is the platform default.
                continue

    # anchor the process to the package directory: config.json and every
    # relative outputs/ path resolve identically no matter where the
    # process was launched from (path-resolution fix, run-from-anywhere)
    os.chdir(Path(__file__).resolve().parent)

    config = load_config(args.config)
    logging.basicConfig(
        level=getattr(logging, config.get("system", {}).get("log_level", "INFO")),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger().addHandler(JsonlLogHandler())
    Path("outputs").mkdir(exist_ok=True)

    merge_skimmer_universe(config)

    # single-instance guard: a second runner on the same outputs/ dir clobbers
    # status/state, races the control queue, and corrupts the audit chain -
    # and a stuck duplicate is what makes status.json flap "stale". Refuse to
    # start if a live runner already holds the lock.
    _lock = SingleInstanceLock(stale_after_sec=max(
        float(config.get("system", {}).get("polling_interval_sec", 5)) * 5,
        30.0))
    held = _lock.acquire()
    if held is not None:
        hb_age = time.time() - float(held.get("heartbeat", 0))
        # Two cases, very different urgency:
        #  * peer HEALTHY (recent heartbeat): this is the benign supervisor/
        #    updater revive race — a redundant spawn during a restart window
        #    hit a still-alive runner and the lock did its job. NO action
        #    needed; this spawn just backs off. (Logging it CRITICAL with
        #    "stop it first" made routine deploy restarts look like a rogue
        #    second bot — 2026-07-18.)
        #  * peer STALE (heartbeat older than the lock's own stale window):
        #    a genuinely wedged duplicate the operator may need to clear.
        if hb_age <= _lock.stale_after:
            log.info("peer runner healthy (pid=%s, heartbeat %.0fs ago) — "
                     "this redundant spawn is backing off, no action needed "
                     "(supervisor/updater revive race, lock working)",
                     held.get("pid"), hb_age)
        else:
            log.critical("another runner holds outputs/ but looks STALE "
                         "(pid=%s, heartbeat %.0fs ago > %.0fs) - refusing to "
                         "start; clear it (stop.bat) or wait for lock expiry.",
                         held.get("pid"), hb_age, _lock.stale_after)
        raise SystemExit(3)

    if args.fresh:
        StateStore(config.get("system", {})
                   .get("state_path", "outputs/state.json")).clear()
        log.info("--fresh: saved state cleared")
    BotRunner(config, start_paused=args.paused,
              resume=not args.fresh, lock=_lock).run()


if __name__ == "__main__":
    main()
