"""
runner.py - the process that drives the engine.

The engine (main.LiquidityBot) is loop-free: it exposes cycle_once().
This runner owns the ONLY loop in the system, and around each cycle it:

  1. consumes control commands from outputs/control/ (dropped by the
     Streamlit UI or by hand: any JSON {"cmd": ...} file works)
  2. runs one engine cycle if state is RUNNING (or a step was requested)
  3. writes the full UI-facing status to outputs/status.json (atomic)
     and appends the equity curve point
  4. snapshots on cadence (the engine also snapshots after every fill)

Commands: start, pause, stop, step, snapshot, entries_on, entries_off,
arm_live (requires confirm phrase), disarm_live, flatten_all,
sim_price_shock / sim_force_fear / sim_force_regime / sim_clear
(sim_* are refused outright when config is live).

Run:  python runner.py [--config config.json] [--fresh] [--paused]
"""

import argparse
import sys
import os
import logging
import time
from pathlib import Path

from core.persistence import StateStore
from core.runtime import (ARM_PHRASE, ControlChannel, JsonlLogHandler,
                          SingleInstanceLock, StatusWriter)
from core.session_digest import write_digest
from main import LiquidityBot, load_config

log = logging.getLogger("liquiditybot.runner")


class BotRunner:
    def __init__(self, config: dict, bot: LiquidityBot | None = None,
                 start_paused: bool = False, resume: bool = True,
                 lock: SingleInstanceLock | None = None):
        self.config = config
        self._lock = lock
        self.bot = bot or LiquidityBot(config, resume=resume)
        if config.get("system", {}).get("record_feeds"):
            from data.replay import FeedRecorder
            rec_dir = config["system"].get("recording_dir",
                                            "outputs/recordings")
            sink = f"{rec_dir}/session_{int(time.time())}.jsonl"
            for name in ("okx", "binanceus", "kraken"):
                setattr(self.bot, name,
                        FeedRecorder(getattr(self.bot, name), name, sink))
            log.warning(f"feed recording ON -> {sink} (replay it with "
                        f"scripts/replay.py)")
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
        self.state = "PAUSED" if start_paused else "RUNNING"
        self._step_requested = False
        self._stop = False
        self.poll_sec = self.bot.poll_sec

    # ------------------------------------------------------------------
    def handle_command(self, c: dict):
        cmd, args = c["cmd"], c.get("args", {})
        bot = self.bot
        note = ""
        if cmd == "start":
            self.state = "RUNNING"
        elif cmd == "pause":
            self.state = "PAUSED"
        elif cmd == "stop":
            self._stop = True
        elif cmd == "step":
            self._step_requested = True
        elif cmd == "snapshot":
            ok = bot.store.snapshot(bot)
            note = f"snapshot {'saved' if ok else 'FAILED'}"
        elif cmd == "entries_on":
            bot.entries_enabled = True
        elif cmd == "entries_off":
            bot.entries_enabled = False
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
        elif cmd == "force_dry":
            # one-way, safe-direction only: LIVE -> DRY. There is no
            # command that sets dry_run False; returning to live requires
            # config dry_run=false + restart + typed ARM phrase.
            if bot.dry_run:
                note = "already dry-run"
            else:
                bot.live_armed = False
                bot.dry_run = True
                bot.orders.dry_run = True     # OrderManager caches the flag
                note = ("FORCED DRY-RUN by operator - live order paths "
                        "sealed (venue dead-man will cancel resting "
                        "orders); live again = config + restart + ARM")
        elif cmd == "flatten_all":
            for pos in bot.state.open_positions():
                bot._submit_exit(pos, 100.0, "operator flatten_all")
            note = f"flatten requested for {bot.state.open_position_count()} positions"
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
    def build_status(self, now: float) -> dict:
        bot = self.bot
        marks = bot.marks
        positions = []
        for p in bot.state.open_positions():
            mark = marks.get(p.symbol) or p.entry_price
            positions.append({
                "id": p.position_id[:8], "symbol": p.symbol,
                "direction": p.direction, "size": round(p.size, 8),
                "entry": round(p.entry_price, 2), "mark": round(mark, 2),
                "upnl_pct": round(p.unrealized_pnl_pct(mark), 3),
                "upnl_usd": round((mark - p.entry_price) * p.size *
                                  (1 if p.direction == "long" else -1), 2),
                "stop": round(p.stop_price, 2) if p.stop_price else None,
                "trail": round(p.trailing_stop_price, 2)
                if p.trailing_stop_price else None,
                "tiers_fired": p.tier_closed,
                "age_h": round((now - p.opened_at.timestamp()) / 3600.0, 1),
                "p_win": round(p.confidence, 2), "hedge": p.is_hedge,
                "fees_usd": round(p.fees_paid_usd, 2),
            })
        orders = [{
            "id": o.order_id, "symbol": o.symbol, "side": o.side,
            "purpose": o.purpose, "price": round(o.price, 2),
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
            "ts": now, "cycle": bot._cycle, "runner_state": self.state,
            "mode": "DRY_RUN" if bot.dry_run else
                    ("LIVE_ARMED" if bot.live_armed else "LIVE_DISARMED"),
            "entries_enabled": bot.entries_enabled, "halted": bot._halted,
            "equity": round(equity, 2),
            "cash": round(bot.state.cash_balance, 2),
            "savings": round(bot.state.savings_balance, 2),
            "daily_pnl": round(bot.state.daily_realized_pnl, 2),
            "realized_total": round(bot.state.realized_pnl_total, 2),
            "fees_total": round(bot.state.fees_paid_total, 2),
            "drawdown_pct": round(bot.state.drawdown_pct(), 2),
            "latency_ms": round(bot.orders.latency_ms, 1),
            "positions": positions, "open_orders": orders,
            "signals": getattr(bot, "last_signals", {}),
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
            "moomoo": {"risk_z": round(risk.risk_z, 2),
                       "basket_ret_pct": risk.basket_ret_pct,
                       "per_ticker": risk.per_ticker,
                       "available": risk.available},
            "watchdog": bot.watchdog.status(),
            "equity_drift_pct": round(bot._equity_drift_pct, 3),
            "monitor": bot.monitor.status(),
            "ml": {"trained": bot.meta.trained,
                   "drift_share": bot.monitor.drift_share,
                   "drifting": bot.monitor.drifting[:5],
                   "model_kind": getattr(bot.meta.model, "kind", None),
                   "history_rows": bot.history.row_count(),
                   "pending_labels": len(bot.history._pending),
                   "open_candidates": len(bot.candidates._cands),
                   "retrain_flag": bot.monitor.flag_path.exists(),
                   "gate_stats": bot.gate_stats.summary()},
            "thales": bot.thales.status(now) if hasattr(bot, "thales") else {},
            "sim": bot.sim.describe(),
        }

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
                    self._lock.refresh()
                try:
                    for c in self.control.consume():
                        self.handle_command(c)
                    if self._stop:
                        break
                    if self.state == "RUNNING" or self._step_requested:
                        stepped = self._step_requested
                        self._step_requested = False
                        bot.cycle_once(now)
                        if stepped:
                            log.info(f"stepped one cycle -> {bot._cycle}")
                    if now - bot._last_snapshot >= bot.snapshot_sec:
                        bot.store.snapshot(bot)
                        bot._last_snapshot = now
                    snap = self.build_status(now)
                    self._last_status = snap
                    self.status.write(snap, now)
                except KeyboardInterrupt:
                    log.info("shutdown requested")
                    break
                except Exception:
                    log.exception("runner cycle error - continuing")
                elapsed = time.time() - now
                time.sleep(max(self.poll_sec - elapsed, 0.25))
        finally:
            bot.moomoo.close()
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
            # leave a reconciled, machine-readable digest of the run so the
            # next session (operator or agent) can pick up from an accurate
            # summary instead of cross-joining six raw streams. Read-only and
            # best-effort: a digest failure must never mar a clean shutdown.
            try:
                d = write_digest("outputs", self.config)
                log.info(f"session digest: {d['verdict']} -> "
                         f"outputs/session_digest.md")
            except Exception:
                log.debug("session digest write failed during shutdown")
            if self._lock is not None:
                self._lock.release()              # free the lock for a restart


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

    # single-instance guard: a second runner on the same outputs/ dir clobbers
    # status/state, races the control queue, and corrupts the audit chain -
    # and a stuck duplicate is what makes status.json flap "stale". Refuse to
    # start if a live runner already holds the lock.
    _lock = SingleInstanceLock(stale_after_sec=max(
        float(config.get("system", {}).get("polling_interval_sec", 5)) * 5,
        30.0))
    held = _lock.acquire()
    if held is not None:
        log.critical("another runner is already driving outputs/ (pid=%s, "
                     "heartbeat %.0fs ago) - refusing to start a duplicate. "
                     "Stop it first (stop.bat) or wait for its lock to expire.",
                     held.get("pid"), time.time() - float(held.get("heartbeat", 0)))
        raise SystemExit(3)

    if args.fresh:
        StateStore(config.get("system", {})
                   .get("state_path", "outputs/state.json")).clear()
        log.info("--fresh: saved state cleared")
    BotRunner(config, start_paused=args.paused,
              resume=not args.fresh, lock=_lock).run()


if __name__ == "__main__":
    main()
