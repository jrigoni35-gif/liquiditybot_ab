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
arm_live (requires confirm phrase), disarm_live, clear_fault, force_dry
(one-way LIVE->DRY), flatten_all,
sim_price_shock / sim_force_fear / sim_force_regime / sim_clear
(sim_* are refused outright when config is live).

Run:  python runner.py [--config config.json] [--fresh] [--paused]
"""

import argparse
import sys
import os
import logging
import math
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from core import code_stats
from core.audit import get_audit
from core.codes import Code
from core.goals import goal_progress
from core.persistence import StateStore
from core.precision import round_price
from core.runtime import (ARM_PHRASE, VALID_COMMANDS, ControlChannel,
                          JsonlLogHandler, SingleInstanceLock, StatusWriter)
from core.session_digest import write_digest
from main import LiquidityBot, load_config

log = logging.getLogger("liquiditybot.runner")

# Wall clock at process start. Import happens before anything else this
# process does, so it is the earliest honest "this runner exists" stamp -
# H6 uses it to keep a control command that was SENT while this process was
# booting instead of purging it with the previous life's leftovers.
_PROC_START = time.time()

# H4: durable one-way LIVE->DRY seal. force_dry flips the RUNTIME flags, and
# the snapshot records the runtime flag - so without a durable marker the
# prescribed live restart hits restore()'s paper/live mismatch guard and
# starts FLAT while the venue still holds the book (or, worse, adopts
# force_dry-era PAPER positions into a live engine). The sentinel makes boot
# reproduce the operator's decision instead of silently reverting it, exactly
# like outputs/paused.on and outputs/entries_off.on (audit F2 2026-07-17).
# Cleared ONLY by --fresh or by deleting the file.
FORCE_DRY_SENTINEL = Path("outputs") / "force_dry.on"

# H7: the vocabulary BotRunner.handle_command actually implements, declared
# beside it rather than derived from it, so tests/test_audit_runner_state.py
# can compare BOTH directions against core.runtime.VALID_COMMANDS:
#   * handled but not valid -> ControlChannel.send() raises and consume()
#     unlinks the file; the command is dead and silently so (clear_fault
#     lived in that state for its whole life);
#   * valid but not handled -> the runner acks "ok" and does nothing.
# A source-parse test pins this set against the dispatcher's own branches so
# the constant itself cannot drift.
HANDLED_COMMANDS = frozenset({
    "start", "pause", "stop", "step", "snapshot", "entries_on",
    "entries_off", "arm_live", "disarm_live", "clear_fault", "force_dry",
    "flatten_all", "budget_reanchor_week",
    "sim_price_shock", "sim_force_fear", "sim_force_regime", "sim_clear",
})

# Fault key latched when a live peer wins the instance lock (C1). Not a
# reason code: FaultManager.latch() already writes FT-010 to the audit chain
# and fires the operator alert; this is the table key clear_fault names.
LOCK_LOST_FAULT = "lock_lost"


def command_vocabulary_drift() -> tuple:
    """H7 parity guard, BOTH directions: (handled-but-not-valid,
    valid-but-not-handled). The pre-existing guard only checked
    REMOTE_SAFE_COMMANDS ⊆ VALID_COMMANDS and never looked at the dispatcher's
    own vocabulary, which is exactly how clear_fault stayed dead. Called from
    BotRunner.__init__ (so a live process says so out loud) and asserted empty
    in tests/test_audit_runner_state.py (so CI stops it landing at all)."""
    return (HANDLED_COMMANDS - VALID_COMMANDS,
            frozenset(VALID_COMMANDS) - HANDLED_COMMANDS)


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
        # C1: the lock heartbeat runs on its OWN daemon thread, started before
        # the (unbounded) engine construction below and refreshing every
        # polling interval. See _heartbeat_loop for why this must not live on
        # the cycle thread. No new tunable: the cadence IS the existing
        # system.polling_interval_sec the loop already runs at.
        _sys_cfg = (config or {}).get("system", {}) or {}
        try:
            _poll = float(_sys_cfg.get("polling_interval_sec", 5.0))
        except (TypeError, ValueError):
            _poll = 5.0
        # floor is a busy-spin guard, not a decision knob: harnesses run the
        # loop at poll_sec=0 and a 0-second wait would pin a core rewriting
        # the lockfile.
        self._hb_sec = max(_poll, 0.05)
        # C1b: C1's thread refreshes on a cadence the cycle body cannot stall,
        # which proves this PROCESS is alive. That is not the same claim as
        # "the loop is alive", and the gap between them matters: a cycle_once
        # that HANGS (rather than raises) leaves a live process driving
        # nothing, and an unconditional heartbeat would hold the lock forever
        # so no healthy runner could ever replace it. The wedge guard does not
        # cover that - it is scoped to a cycle that RAISES every iteration -
        # so before C1 the stale lock WAS the only recovery path for a hang,
        # and C1 removed it while fixing the false-takeover direction.
        # The bound restores it: refresh while the loop is MOVING (however
        # slowly), stop once it has demonstrably stopped. 300s is ~3.4x the
        # worst stall ever measured here (88.1s, outputs/runner.log) and 10x
        # the lock's 30s stale window - comfortably above any legitimate
        # cycle, far below "an operator would not notice". Derived from
        # measurement, not tuned.
        try:
            self._hb_max_stall = float(
                _sys_cfg.get("lock_progress_max_stall_sec", 300.0))
        except (TypeError, ValueError):
            self._hb_max_stall = 300.0
        # None = the loop has not run yet. The heartbeat thread starts BEFORE
        # the unbounded LiquidityBot construction below, so during startup
        # there is no progress to measure and refresh must be unconditional -
        # gating on progress alone here would re-open the exact window C1
        # closed.
        self._last_progress_ts: Optional[float] = None
        # ...but "unconditional" must still be BOUNDED (2026-08-05): a boot
        # that never finishes would otherwise hold the lock forever and
        # deadlock every replacement spawn. Startup gets its own grace,
        # measured from process start, defaulting to twice the running
        # stall bound - a normal engine build takes tens of seconds, so
        # this only ever fires on a genuine hang.
        self._proc_start_ts: float = time.time()
        try:
            self._hb_boot_grace = float(
                _sys_cfg.get("lock_boot_max_stall_sec",
                             self._hb_max_stall * 2.0))
        except (TypeError, ValueError):
            self._hb_boot_grace = self._hb_max_stall * 2.0
        self._hb_stall_logged = False
        self._hb_stop = threading.Event()
        self._hb_thread: Optional[threading.Thread] = None
        self._lock_lost_latched = False
        if self._lock is not None:
            self._hb_thread = threading.Thread(
                target=self._heartbeat_loop, name="lock-heartbeat",
                daemon=True)
            self._hb_thread.start()
        self.bot = bot or LiquidityBot(config, resume=resume)
        # C1: we PROVABLY own the lock (main() exits 3 otherwise), so a
        # lock_lost fault re-latched from a previous life's snapshot names a
        # peer that no longer exists. Leaving it would boot HALTED - new risk
        # refused forever - on evidence this very acquire() disproves.
        if self._lock is not None:
            _fm = getattr(self.bot, "fault", None)
            if _fm is not None and LOCK_LOST_FAULT in \
                    (_fm.status().get("faults") or {}):
                _fm.clear_fault(LOCK_LOST_FAULT, operator="boot-lock-acquired")
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
        #
        # H6: the purge was UNCONDITIONAL, and engine construction above takes
        # tens of seconds (feeds, corpus, model load). The remote plane is
        # at-most-once - it appends the id to remote_consumed.json and
        # publishes result:"applied" BEFORE forwarding, and never retries - so
        # anything it forwarded during THIS process's boot window was
        # acknowledged to the operator and then deleted here unread. A
        # swallowed flatten_all/stop tells the operator the book is flat when
        # it is not. ControlChannel.send stamps sent_at (until now a dead
        # field: one writer, zero readers), so keep what was sent after this
        # process started and drop only what predates it. Unstamped files
        # (hand-dropped JSON) keep the old conservative treatment.
        self._boot_commands: list = []
        stale = []
        for _c in self.control.consume():
            try:
                _sent = float(_c.get("sent_at", 0) or 0)
            except (TypeError, ValueError):
                _sent = 0.0
            (self._boot_commands if _sent >= _PROC_START else stale).append(_c)
        if stale:
            log.warning("discarded %d stale control command(s) queued before "
                        "startup: %s", len(stale),
                        [c.get("cmd") for c in stale])
        if self._boot_commands:
            log.warning("retained %d control command(s) sent during startup "
                        "(after this process began): %s - they run on the "
                        "first loop iteration", len(self._boot_commands),
                        [c.get("cmd") for c in self._boot_commands])
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
        # H4: written by force_dry, read by main() BEFORE the engine is
        # constructed (see FORCE_DRY_SENTINEL).
        self._force_dry_sentinel = FORCE_DRY_SENTINEL
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
        # H5: an emergency flatten is a LATCH re-driven every tick, not the
        # single unretried attempt it used to be. See _drive_flatten.
        self._flatten_latched = False
        self._flatten_since = 0.0
        self._flatten_alerted = False
        # H7: say it out loud in the live process too, not only in CI - a
        # dropped command is otherwise invisible at every layer.
        _dead, _deaf = command_vocabulary_drift()
        if _dead:
            log.critical("control vocabulary drift: %s are handled but not in "
                         "VALID_COMMANDS - send() raises and consume() DELETES "
                         "them unread", sorted(_dead))
        if _deaf:
            log.critical("control vocabulary drift: %s are accepted but have "
                         "no handler - they ack 'ok' and do nothing",
                         sorted(_deaf))

    # ------------------------------------------------------------------
    def _heartbeat_loop(self) -> None:
        """C1: refresh the single-instance lock from a DEDICATED daemon
        thread, never from the cycle thread.

        The heartbeat used to be written once per loop iteration, so the
        effective interval was the whole iteration - and cycle_once has no
        time bound. Measured stalls in outputs/runner.log: 88.1s, 55.5s,
        50.2s, 48.4s, 47.8s, every one of them past the lock's 30s stale
        window. A LIVE runner therefore read as crashed, a second runner
        reclaimed the lock and restored the same state.json, and the loser
        kept placing orders for LOST_LIMIT more cycles - the dual-writer seam
        behind both audit-chain forks in outputs/ (RT-010,
        audit.jsonl.forked_20260713_054924).

        scripts/pc_supervisor._acquire_or_wait documents the principle this
        rests on: a dead pid cannot advance its heartbeat, so MOVEMENT - not
        age - is the only honest liveness signal. Movement is only honest if
        the trading work cannot block it, which is precisely what this thread
        buys. The loop keeps the VERDICT (self._lock.forfeited /
        lost_count); this thread only supplies the evidence.

        Never raises: the lock is advisory, and a refresh that raises must not
        kill the heartbeat for the rest of the session."""
        assert self._lock is not None      # only started when a lock exists
        while not self._hb_stop.wait(self._hb_sec):
            try:
                if not self._hb_should_refresh(time.time()):
                    if not self._hb_stall_logged:
                        self._hb_stall_logged = True
                        log.critical(
                            "loop has not advanced in >%.0fs - WITHHOLDING the "
                            "lock heartbeat so a healthy runner can take this "
                            "outputs/ dir over. This process is alive but not "
                            "trading; investigate the hang.",
                            self._hb_max_stall)
                    continue
                if self._hb_stall_logged:
                    self._hb_stall_logged = False
                    log.warning("loop advanced again - resuming the lock "
                                "heartbeat")
                self._lock.refresh()
            except Exception:
                log.exception("lock heartbeat refresh raised - retrying at "
                              "the next interval")

    def _hb_should_refresh(self, now: float) -> bool:
        """Is the LOOP alive, not merely this process?

        `_last_progress_ts is None` means the loop has not started yet
        (__init__ starts this thread before the unbounded engine build), and
        startup must refresh unconditionally - that window is what C1 exists
        to cover. Once the loop has stamped once, a gap beyond
        system.lock_progress_max_stall_sec is a hang rather than a slow
        cycle, and the honest signal is to stop claiming the lock.

        Pure and side-effect free so the decision is testable without
        threads or timing."""
        last = self._last_progress_ts
        if last is None:
            # BOUNDED startup grace (round-2 fix 2026-08-05). This returned
            # True unconditionally, so a boot that HANGS - engine
            # construction does network I/O: feeds, corpus, model load -
            # refreshed the lock forever while writing no status.json. The
            # supervisor then saw stale status, spawned a replacement, and
            # that replacement read a FRESH foreign heartbeat and exited 3,
            # permanently: no trading and no self-heal until a human
            # intervened. The stall bound that covers the running loop now
            # covers the boot too, measured from process start, so a hung
            # constructor eventually stops claiming the lock and the next
            # spawn can take over. The bound is generous relative to a
            # normal build, so an ordinary slow start is unaffected.
            started = getattr(self, "_proc_start_ts", None)
            if started is None:
                return True
            return (now - started) <= self._hb_boot_grace
        return (now - last) <= self._hb_max_stall

    def _stop_heartbeat(self) -> None:
        """Halt the heartbeat thread and wait for it to leave refresh().
        MUST run before _lock.release(), or a refresh landing after the
        unlink recreates the lockfile this process no longer owns."""
        self._hb_stop.set()
        t = self._hb_thread
        if t is not None and t.is_alive():
            t.join(timeout=max(self._hb_sec * 2.0, 1.0))

    def _note_lock_lost(self) -> None:
        """C1: the FIRST lost heartbeat already proves a live peer owns this
        outputs/ dir. Refuse NEW risk immediately instead of trading through
        the LOST_LIMIT-heartbeat convergence window - during overlap both
        processes submit full-size exits off their own per-process
        open_orders() view (double close, reversal into a leveraged short)
        and both interleave the hash-chained audit trail.

        Exits are NEVER gated by this (invariant #5): a CRITICAL fault sets
        op-state HALTED, which refuses new risk and leaves allow_exits() True.
        Latched once per contention episode; a recovered lock (lost_count back
        to 0) re-arms so a later episode alerts again. Recovery is the
        operator's `clear_fault lock_lost` - which H7 made reachable - or a
        restart, where __init__ drops it because acquire() succeeded."""
        fm = getattr(self.bot, "fault", None)
        if fm is None:
            log.critical("instance lock lost to a live peer and there is no "
                         "fault authority to refuse new risk - stop one of "
                         "the runners NOW")
            return
        try:
            from core.fault import Severity
            fm.latch(LOCK_LOST_FAULT, Severity.CRITICAL,
                     f"a live peer holds outputs/runner.lock "
                     f"(lost_count={getattr(self._lock, 'lost_count', '?')}) "
                     f"- refusing NEW risk while two runners contend for one "
                     f"book; exits still run")
        except Exception:
            log.exception("lock_lost fault-latch failed - new risk is NOT "
                          "sealed; stop one of the runners manually")

    # ------------------------------------------------------------------
    def _cfg_dry_run(self) -> bool:
        """The CONFIGURED mode for this session. force_dry never touches it -
        that is the whole point (M3). getattr-guarded because several suites
        drive handle_command off a BotRunner.__new__ double that has no
        config; an absent config resolves to the SAFE default (dry)."""
        cfg = getattr(self, "config", None) or {}
        return bool((cfg.get("system") or {}).get("dry_run", True))

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
                if key == LOCK_LOST_FAULT:
                    # C1: re-arm so a LATER contention episode latches (and
                    # alerts) again instead of being swallowed by this one.
                    self._lock_lost_latched = False
                note = (f"fault {key} cleared -> op-state {fm.status()['state']}"
                        if cleared else f"no such fault {key!r}")
        elif cmd == "budget_reanchor_week":
            # operator override for BUG-ATTRIBUTABLE weekly loss-budget
            # consumption (first use 2026-08-08: the ADA hedge-churn
            # class, fixed in 5c111962/cf454d5e, had spent 109% of the
            # week and taper_mult=0.0 blocked all entries; without the
            # bug the week was net positive). The budget measures from
            # persisted EQUITY ANCHORS, so no restart clears it - this
            # verb re-anchors the week at current equity, touching no
            # ledger, pool or learning data. Reason REQUIRED (audited,
            # RP-042); deliberately absent from rest_server's
            # ALLOWED_CONTROL - risk-loosening verbs stay off the
            # browser-reachable surface, same posture as arm_live.
            rp = getattr(bot, "risk_protocols", None)
            reason = str(args.get("reason", "")).strip()
            if rp is None:
                note = "no risk protocol stack"
            elif not reason:
                note = ("REFUSED: give args.reason - this is an audited "
                        "operator override")
            else:
                eq = bot.state.total_equity(bot.marks)
                if rp.reanchor_week(eq, now=now):
                    note = (f"weekly loss budget re-anchored at "
                            f"${eq:,.2f}: {reason}")
                    get_audit().log("runner", Code.RP_BUDGET_REANCHORED,
                                    note, {"equity": round(eq, 2),
                                           "reason": reason})
                else:
                    note = "REFUSED: no finite positive equity to anchor"
        elif cmd == "force_dry":
            note = self._cmd_force_dry(bot)
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
            # H5: LATCH the flatten. A single unretried attempt was the whole
            # defect - on the 25s order timeout _poll_live cancels and emits a
            # zero-fill final event _handle_fill has no branch for, so nothing
            # ever re-submitted and the ack still claimed success.
            self._latch_flatten(now)
            note = f"flatten submitted for {submitted} position(s); LATCHED"
            if self.state == "PAUSED":
                # W2-6: orders.poll/refresh_deadman still run every tick while
                # paused (see _run_paused_order_maintenance) so these exits
                # are not left resting unmanaged until the venue's dead-man
                # cancels them with no local reconciliation.
                note += "; exits will be managed while paused"
                note += self._paused_mark_staleness_note(now)
            if failed:
                note += f"; {failed} FAILED to submit - see log, retry"
        elif cmd.startswith("sim_"):
            # M3: BOTH the configured mode and the runtime flag must be dry.
            # The old gate read only the mutable bot.dry_run, so force_dry
            # (LIVE->DRY) silently unlocked simulated price shocks on a
            # live-CONFIG bot - and status.json then reported "DRY_RUN", the
            # exact signal an operator reads as safe. _apply_sim multiplies
            # REAL marks in place, driving stops/tiers straight into
            # _submit_exit. runner.py's module docstring and
            # core/runtime.SimOverrides both already promised the config gate.
            if not (self._cfg_dry_run() and bot.dry_run):
                note = ("REFUSED: simulations are dry-run only "
                        "(configured mode AND runtime flag must both be dry)")
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
    def _cmd_force_dry(self, bot) -> str:
        """One-way, safe-direction only: LIVE -> DRY. There is no command that
        sets dry_run False; returning to live requires config dry_run=false +
        restart + the typed ARM phrase (hard invariant #1).

        C2 (runner side): force_dry used to cancel resting orders, flip the
        flags, and leave the runner RUNNING. Every subsequent exit for a
        LIVE-born position then routed through OrderManager's dry branch, got
        a DRY- txid, and _sim_cross fabricated a fill against the still-live
        Kraken book - with `venue calls: []`. main._handle_fill has no dry/live
        provenance (Position carries no such field), so it decremented size,
        booked paper PnL and finalized a position the venue still holds. A real
        book was paper-closed and status reported a falling position count.
        The flag flip itself is correct and invariant-mandated, so it is
        UNCHANGED; what stops the fabrication is PAUSING - cycle_once is the
        only caller of the stop/tier evaluation that reaches _submit_exit.
        The engine-side provenance work is tracked separately.

        H4: write the durable outputs/force_dry.on sentinel. snapshot()
        persists the RUNTIME dry_run flag and force_dry is its only runtime
        writer, so without the sentinel the very next 30s cadence snapshot
        wrote dry_run:true alongside a still-real book; the prescribed live
        restart then hit restore()'s paper/live mismatch guard, logged
        "refusing to mix paper and live state", and booted flat with the full
        starting capital while Kraken held the coins. One poisoned generation
        is fatal (a readable-but-mismatched primary short-circuits before
        _pick_snapshot consults .bak). main() reads the sentinel BEFORE the
        engine exists and forces dry_run=True, so the snapshot's flag matches
        and the book survives."""
        if bot.dry_run:
            return "already dry-run"
        # W2-5: cancel every still-resting LIVE venue order BEFORE flipping
        # the flags. Flipping first left any resting order routed through
        # _poll_dry from the NEXT poll onward, which SIMULATES a fill on an
        # order genuinely resting on Kraken - in the 0..deadman_sec window
        # before the venue dead-man cancels it, a real fill could land with no
        # local record (and with deadman_timeout_sec=0 it rests unmanaged
        # forever). cancel_order() is called while bot.orders.dry_run is STILL
        # False so it takes the live path (venue CancelOrder + final-fill
        # reconciliation query) rather than the dry-run no-op.
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
        # getattr-guarded like every other stub-tolerant path here: a
        # BotRunner.__new__ double (test harnesses) has no sentinel path, and
        # writing a repo-relative outputs/force_dry.on from a unit test would
        # leak a durable risk-off into the operator's real checkout.
        _fd = getattr(self, "_force_dry_sentinel", None)
        if _fd is not None:
            self._set_sentinel(_fd)
        else:
            log.warning("force_dry: no sentinel path on this runner - the "
                        "one-way seal will NOT survive a restart")
        note = (f"FORCED DRY-RUN by operator - {cancelled} resting "
                f"live order(s) cancelled, live order paths sealed; "
                f"outputs/force_dry.on written so a restart under the "
                f"unchanged live config restores this book instead of "
                f"discarding it; live again = delete that sentinel + "
                f"config + restart + ARM")
        # C2: read the book AFTER the seal is committed - the flip is an
        # invariant and must never depend on this succeeding. `state` is
        # getattr-guarded for the minimal SimpleNamespace doubles several
        # suites drive handle_command with (a real LiquidityBot always builds
        # PortfolioState in __init__, so the None branch is unreachable in
        # production); a state that RAISES is treated as a non-empty book,
        # because "cannot prove the book is empty" must fail toward pausing.
        stranded, unknown = [], False
        _state = getattr(bot, "state", None)
        if _state is not None:
            try:
                stranded = list(_state.open_positions())
            except Exception:
                unknown = True
                log.exception("force_dry: open_positions() raised - treating "
                              "the book as NON-empty and pausing")
        if not stranded and not unknown:
            return note
        # A REAL book is now behind a paper engine. Pause (that is what stops
        # cycle_once - the only caller that reaches _submit_exit - from
        # fabricating fills against the still-live Kraken book), make the
        # pause durable so a supervisor/updater relaunch cannot silently
        # revert it, and name the stranded positions.
        self.state = "PAUSED"
        _ps = getattr(self, "_paused_sentinel", None)   # see the note above:
        if _ps is not None:                             # never leak into the
            self._set_sentinel(_ps)                     # operator's checkout
        detail = ", ".join(f"{p.symbol} {p.position_id[:8]} "
                           f"{p.direction} {p.size:.8g}" for p in stranded) \
            or "position count UNKNOWN (open_positions() raised)"
        msg = (f"force_dry with {len(stranded) or 'an unknown number of'} "
               f"OPEN LIVE POSITION(S): {detail}. The runner is now PAUSED so "
               f"the paper engine cannot fabricate exits against the real "
               f"Kraken book. These positions are REAL and are NOT being "
               f"stop-managed while paused - flatten them from the venue, or "
               f"delete outputs/force_dry.on + outputs/paused.on and restart "
               f"live.")
        try:
            bot.alerts.fire("force_dry_with_open_positions", msg,
                            level="CRITICAL")
        except Exception:
            log.exception("force_dry alert failed - the pause still stands")
        log.critical("force_dry: %s", msg)
        return (f"{note}; PAUSED with {len(stranded)} OPEN LIVE position(s) "
                f"({detail}) - they are REAL, not paper")

    # ------------------------------------------------------------------
    def _latch_flatten(self, now: Optional[float]) -> None:
        """H5: arm the emergency-flatten latch (idempotent re-arm resets the
        escalation clock so a second operator flatten is not judged against
        the first one's deadline)."""
        self._flatten_latched = True
        self._flatten_since = now if now is not None else time.time()
        self._flatten_alerted = False

    def _flatten_deadline_sec(self) -> float:
        """How long the exit-escalation ladder needs to run itself out, from
        the engine's OWN configured values - no new tunable. Each attempt
        rests for order_timeout_sec; the ladder reaches its MARKET rung after
        esc_market_after attempts, so a flatten still open one timeout past
        that is not going to resolve itself."""
        bot = self.bot
        timeout = float(getattr(getattr(bot, "orders", None),
                                "timeout_sec", 25.0) or 25.0)
        rungs = int(getattr(bot, "esc_market_after", 3) or 3)
        return timeout * (rungs + 2)

    def _drive_flatten(self, now: float) -> None:
        """H5: re-drive the latched flatten every tick until the book is flat.

        flatten_all used to be ONE _submit_exit per position with no latch -
        contrast the catastrophe hard stop, which sets bot._halted and
        re-flattens every cycle. On the 25s order timeout _poll_live cancels
        and emits a zero-fill final FillEvent that _handle_fill has no branch
        for, so nothing re-submitted: the ack said "flatten submitted", the
        positions stayed open, and no alert ever fired.

        Re-driving is nearly free: _submit_exit's own one-live-exit-per-
        position dedup returns early while an exit rests, so this only bites
        when an attempt has expired - and then the existing escalation ladder
        (widening slip cap, MARKET on the final rung) advances exactly as
        designed. Runs in BOTH runner states, because invariant #5 is that a
        pause blocks new risk and never an escape.

        Isolated per position, like flatten_all itself."""
        if not self._flatten_latched:
            return
        bot = self.bot
        try:
            positions = list(bot.state.open_positions())
        except Exception:
            log.exception("flatten latch: open_positions() raised - "
                          "retrying next tick")
            return
        if not positions:
            self._flatten_latched = False
            self._flatten_alerted = False
            log.warning("flatten latch cleared: book is flat")
            return
        if self.state == "PAUSED":
            # H5: fast_cycle is the ONLY writer of bot.marks / bot.kraken_books
            # and it does not run while paused, so every replacement exit would
            # be priced off the touch frozen at pause time - and it would pass
            # the firewall collar, because the collar centers on that same
            # frozen mid (verified: a 35-minute-stale book produced a sell limit
            # at 1990 into a 1720 market). Refresh first so the ladder advances
            # against real prices.
            self._refresh_marks_for_flatten(now, positions)
        for pos in positions:
            try:
                bot._submit_exit(pos, 100.0, "operator flatten_all (latched)",
                                 now=now)
            except Exception:
                log.exception("[%s] latched flatten re-submit raised - "
                              "continuing with the rest", pos.symbol)
        elapsed = now - self._flatten_since
        if not self._flatten_alerted and elapsed > self._flatten_deadline_sec():
            self._flatten_alerted = True
            msg = (f"emergency flatten still open after {elapsed:.0f}s: "
                   f"{len(positions)} position(s) "
                   f"({', '.join(p.symbol for p in positions)}) survived the "
                   f"full exit-escalation ladder including its MARKET rung. "
                   f"The latch keeps retrying every tick - intervene at the "
                   f"venue.")
            try:
                bot.alerts.fire("flatten_all_unresolved", msg, level="CRITICAL")
            except Exception:
                log.exception("flatten escalation alert failed - latch stands")
            log.critical("flatten latch: %s", msg)

    def _refresh_marks_for_flatten(self, now: float, positions: list) -> None:
        """H5: read-only mark/book refresh for the assets a latched flatten
        still holds, used ONLY while PAUSED (fast_cycle already does this when
        RUNNING). Ticker + Depth + the engine's own tick quarantine and
        nothing else: no signal, no sizing, no entry path runs here, so it
        cannot create new risk - it only lets the existing exit ladder price
        against the live market instead of a frozen one.

        Deliberately duplicates the READ slice of main.fast_cycle: the engine
        exposes no narrower refresh entry point, and runner.py must not grow
        engine decision logic to get one. Fully isolated - on any feed fault
        the marks stay exactly as stale as they already were, which is the
        pre-existing behaviour."""
        bot = self.bot
        pair_of = getattr(bot, "_pair_of", None) or {}
        kraken = getattr(bot, "kraken", None)
        asset_of = getattr(bot, "_asset_of", None)
        if not pair_of or kraken is None or not callable(asset_of):
            return
        assets = set()
        for p in positions:
            try:
                assets.add(asset_of(p.symbol))
            except Exception:
                log.debug("paused flatten: no asset mapping for %r - its "
                          "exit still re-submits off the existing marks",
                          getattr(p, "symbol", "?"), exc_info=True)
        pairs = [pair_of[a] for a in sorted(assets) if a in pair_of]
        if not pairs:
            return
        try:
            ticks = kraken.get_tickers(pairs) or {}
        except Exception:
            log.exception("paused flatten: ticker refresh failed - exits "
                          "will price off the last known marks")
            ticks = {}
        for asset in sorted(assets):
            pair = pair_of.get(asset)
            if pair is None:
                continue
            try:
                symbol = bot.symbol_map.get(asset)
                px = ticks.get(pair)
                if px and symbol:
                    mark, stop_ok = bot.watchdog.filter_mark(asset, px)
                    bot.marks[symbol] = mark
                    bot._mark_ts[symbol] = now
                    bot._stop_ok[asset] = stop_ok
                book = kraken.get_order_book(pair)
                if book:
                    bot.kraken_books[asset] = book
                    # 42a: DATA-time stamp, same convention as fast_cycle
                    bot.book_ts[asset] = float(book.get("recv_ts") or now)
            except Exception:
                log.exception("paused flatten: refresh failed for %s - "
                              "continuing with the rest", asset)

    def _paused_mark_staleness_note(self, now: Optional[float]) -> str:
        """H5: the PAUSED flatten ack used to claim "exits will be managed"
        unconditionally. When the marks/books behind those exits are older
        than the engine's own mark_stale_sec, say so in the ack instead of
        letting the operator read success into a limit priced off a frozen
        touch."""
        bot = self.bot
        ts = getattr(bot, "_mark_ts", None)
        if not ts:
            return ""
        ref = now if now is not None else time.time()
        try:
            age = max(ref - float(v) for v in ts.values())
            limit = float(getattr(bot, "_mark_stale_sec", 20.0))
        except (TypeError, ValueError):
            return ""
        if age <= limit:
            return ""
        return (f"; WARNING marks are {age:.0f}s old (> {limit:.0f}s) - the "
                f"latch refreshes them before each retry, but the FIRST "
                f"attempt above was priced off frozen data")

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
                # The drawdown ITSELF, not just its derived throttle. It was
                # computed here and discarded, so the only drawdown an
                # operator could see was second-hand through the multiplier -
                # and a throttle of 1.0 reads identically whether drawdown is
                # zero or the hard stop is misconfigured. Exported with its
                # cap so a gauge has a scale.
                "drawdown_mtm_pct": round(float(dd), 4),
                "hard_stop_dd_pct": round(float(sizer.hard_stop_dd_pct), 4),
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
        # month tracks the EFFECTIVE goal (base x RP-072 ladder), and the
        # mult is exported so a board can show how many rungs have been
        # climbed rather than a target that silently moved
        mult = float(getattr(bot.state, "goal_ladder_mult", 1.0))
        return {
            "week": goal_progress("week", bot.state.weekly_realized_pnl,
                                  cm.get("weekly_profit_goal_usd", 0) or 0),
            "month": goal_progress("month", bot.state.monthly_realized_pnl,
                                   (cm.get("monthly_profit_goal_usd", 0) or 0)
                                   * mult),
            "ladder_mult": round(mult, 4),
        }

    def _note_cycle_duration(self, elapsed: float) -> None:
        """Record the iteration's true wall duration (latency audit
        2026-08-07): `elapsed` was computed every loop and used only to
        size the sleep - the documented 88.1s stall left no trace in any
        exported number. last + max, exported by build_status and pushed
        to Grafana, so a stalling cycle is finally a visible event."""
        self._cycle_dur_last = elapsed
        self._cycle_dur_max = max(getattr(self, "_cycle_dur_max", 0.0),
                                  elapsed)

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
        # TANGIBLE-VALUE GRADIENT (regime/haven.py, 2026-08-05): where
        # capital sits on the PAXG > BTC > ETH > alts ladder, read from the
        # engine's OWN venue-grounded 5m bars - no new feed, no new
        # dependency. Report-only by construction (the module cannot reach
        # the trading path; tests/test_haven_gradient.py pins that), so a
        # failure here must never cost a status write.
        try:
            from regime import haven
            _closes = {a: [c["close"] for c in (cs or [])]
                       for a, (_ts, cs) in getattr(bot, "_kr_candles",
                                                   {}).items()}
            haven_state = haven.evaluate(_closes).to_dict()
        except Exception:                       # noqa: BLE001
            haven_state = {"state": "unknown",
                           "detail": "haven read failed"}
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
            # HONEST ALL-TIME P&L (2026-08-09). `realized_total` is net of
            # the CLOSING fee leg only: opening-leg fees (entry + hedge) are
            # debited straight to cash by record_entry_fee and were netted
            # into no P&L figure at all, so the bot reported -208.31 against
            # a true all-time change of -383.26 - 49% of lifetime fees were
            # invisible to every number an operator could read. These four
            # keys close the identity so it can be audited from status.json
            # alone:
            #   net_pnl_all_time = equity - starting_capital
            #   realized_net_all_in = realized_total - entry_fees_total
            # net_pnl_all_time comes from the STATE METHOD rather than being
            # recomputed here: one quantity, one derivation (the drift class
            # that caused this session's corpus incident).
            "starting_capital": round(bot.state.starting_capital, 2),
            "entry_fees_total": round(bot.state.entry_fees_total, 2),
            "realized_net_all_in": round(bot.state.realized_net_all_in(), 2),
            "net_pnl_all_time": round(
                bot.state.net_pnl_all_time(bot.marks), 2),
            "drawdown_pct": round(bot.state.drawdown_pct(), 2),
            "latency_ms": round(bot.orders.latency_ms, 1),
            "feed_latency_ms": round(getattr(bot.kraken, "latency_ms", 0.0), 1),
            # truthful mark freshness: feed_latency_ms only updates on a
            # SUCCESSFUL Kraken call, so a Ticker outage freezes prices AND
            # freezes the latency gauge - stale marks read as live everywhere.
            # marks_age_sec = WALL-clock age of the OLDEST live mark from the
            # engine's telemetry-only wall stamps (latency audit 2026-08-07:
            # the old form compared the loop-frozen `now` against stamps set
            # to that same `now` - arithmetically 0.0 forever).
            "marks_age_sec": _marks_age_sec(bot, time.time()),
            # true iteration durations (see _note_cycle_duration): the only
            # place an 88s stall becomes a number an operator can see.
            "cycle_duration_sec": round(
                getattr(self, "_cycle_dur_last", 0.0), 2),
            "cycle_duration_max_sec": round(
                getattr(self, "_cycle_dur_max", 0.0), 2),
            "positions": positions, "open_orders": orders,
            # shallow-copy: the REST/gRPC provider returns _last_status from an
            # API thread while the engine thread mutates bot.last_signals in
            # slow_cycle - a live reference risks a torn read / "dict changed
            # size". Copied like manip_suspect below. The file path is already
            # safe (serialized in-thread), this covers the API path.
            "signals": dict(getattr(bot, "last_signals", {})),
            "exec_algos": bot.algo.status() if hasattr(bot, "algo") else {},
            "regimes": regimes,
            # cross-asset turbulence WITH its provenance (2026-08-22
            # verification, D7: `grep -rn "turbulence" core/ api/` returned
            # nothing - the scalar that can set macro=crisis on every asset
            # at once reached no operator surface at all). stale/hold_reason
            # say whether this reading was recomputed or held (CR-010), and
            # computed_at/sample_count say when and on how many returns, so
            # a frozen crisis value is finally distinguishable from a live
            # one. Report-only: nothing reads these keys back.
            "correlation": {
                "turbulence": round(_cst.turbulence, 3),
                "turbulence_pct": round(_cst.turbulence_pct, 2),
                "computed_at": round(float(_cst.computed_at), 3),
                "sample_count": int(_cst.sample_count),
                "stale": bool(_cst.stale),
                "hold_reason": str(_cst.hold_reason),
            } if (_cst := getattr(getattr(bot, "corr", None), "state", None)
                  ) is not None else {},
            "haven": haven_state,
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
                       # 41a/41b: closed-market freeze state - the quote is
                       # real but static and z-window appends are suspended;
                       # getattr-guarded for pre-41a snapshots in doubles
                       "quotes_frozen": bool(getattr(risk, "quotes_frozen",
                                                     False)),
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
                # C1b: the ONE thing the loop still owes the heartbeat - proof
                # it is moving. Stamped at the TOP, so it records "the previous
                # iteration finished"; a cycle_once that hangs leaves this
                # frozen and the heartbeat thread stops claiming the lock once
                # the gap passes lock_progress_max_stall_sec. A plain
                # assignment is deliberate: float store/load is atomic under
                # the GIL, so the reader needs no lock, and taking one here
                # would put cycle-body contention back on the heartbeat path -
                # the exact coupling C1 removed.
                self._last_progress_ts = now
                # C1: the heartbeat is written by the daemon thread started in
                # __init__, at a fixed cadence the cycle body cannot stall.
                # The loop only READS the verdict. Writing it here made the
                # effective heartbeat interval equal to a whole iteration -
                # and cycle_once has no time bound, so a live runner regularly
                # read as crashed inside the 30s stale window.
                if self._lock is not None:
                    if self._lock.lost_count == 0:
                        self._lock_lost_latched = False
                    elif not self._lock_lost_latched:
                        # do not wait for LOST_LIMIT: one lost heartbeat is
                        # already proof of a live peer. Seal NEW risk now;
                        # exits keep running (invariant #5).
                        self._lock_lost_latched = True
                        self._note_lock_lost()
                    if self._lock.forfeited:
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
                    # H6: _boot_commands are the ones that arrived DURING this
                    # process's startup (remote plane already ledgered them
                    # "applied"); they run once, ahead of this tick's queue.
                    pending = self._boot_commands + self.control.consume()
                    self._boot_commands = []
                    for c in pending:
                        try:
                            self.handle_command(c, now)
                        except Exception:
                            log.exception("control command %r failed - "
                                          "continuing with the rest",
                                          (c or {}).get("cmd", c)
                                          if isinstance(c, dict) else c)
                    if self._stop:
                        break
                    # H5: a latched emergency flatten is re-driven every tick,
                    # in BOTH states, until the book is flat. Isolated - it
                    # must never feed the wedge counter or skip the cycle.
                    try:
                        self._drive_flatten(now)
                    except Exception:
                        log.exception("flatten latch drive raised - latch "
                                      "stands, retrying next tick")
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
                self._note_cycle_duration(elapsed)
                time.sleep(max(self.poll_sec - elapsed, 0.25))
        finally:
            # C1: stop the heartbeat FIRST. A refresh landing after
            # _lock.release() below would recreate a lockfile this process no
            # longer owns, and a refresh racing the forfeit exit would keep
            # contending with the peer we just conceded to.
            self._stop_heartbeat()
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


def apply_force_dry_sentinel(config: dict, fresh: bool = False,
                             sentinel: Path | None = None) -> bool:
    """H4: reproduce a previous session's force_dry at boot, BEFORE the engine
    reads system.dry_run.

    force_dry is the only runtime writer of bot.dry_run, and snapshot()
    persists that runtime flag. So the moment an operator force_dry'd a live
    session, the next 30s cadence snapshot wrote dry_run:true onto a state
    file that still described a REAL book - and the very next routine restart
    (auto-updater, keepalive, supervisor) hit restore()'s paper/live mismatch
    guard under the unchanged live config, logged "refusing to mix paper and
    live state; starting fresh", and booted with 0 positions and the full
    starting capital while Kraken still held the coins. Flipping the config to
    dry_run:true instead PASSED the guard and restored a genuinely live book
    into a paper engine - there was no config choice that recovered correctly.

    Forcing dry_run True here is the SAFE direction and the only direction
    this function moves (hard invariant #1): it can never set dry_run False.
    Returns True when the sentinel applied. --fresh clears it, because --fresh
    discards the very state the sentinel exists to keep loadable."""
    path = sentinel if sentinel is not None else FORCE_DRY_SENTINEL
    if fresh:
        if path.exists():
            try:
                path.unlink()
                log.warning("--fresh: cleared %s - this boot honours the "
                            "configured mode again", path)
            except OSError:
                log.warning("--fresh: could not clear %s - boot stays DRY", path)
        return False
    if not path.exists():
        return False
    sys_cfg = config.setdefault("system", {})
    was_live = not bool(sys_cfg.get("dry_run", True))
    sys_cfg["dry_run"] = True
    if was_live:
        log.critical(
            "%s present: a previous session was FORCED to dry-run while the "
            "config still says dry_run:false. Booting DRY so the saved "
            "snapshot loads instead of being discarded as paper/live "
            "mismatch. Delete the sentinel (or run --fresh) to go live.",
            path)
    else:
        log.warning("%s present: config is already dry_run - sentinel is a "
                    "no-op this boot", path)
    return True


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
    apply_force_dry_sentinel(config, fresh=args.fresh)

    # single-instance guard: a second runner on the same outputs/ dir clobbers
    # status/state, races the control queue, and corrupts the audit chain -
    # and a stuck duplicate is what makes status.json flap "stale". Refuse to
    # start if a live runner already holds the lock.
    _lock = SingleInstanceLock(stale_after_sec=max(
        float(config.get("system", {}).get("polling_interval_sec", 5)) * 5,
        30.0))
    held = _lock.acquire()
    if held is not None:
        # SENTINEL SHAPES FIRST. core/runtime.py returns {"pid":"initializing"}
        # and {"pid":"contended"} with NO heartbeat key at all. A bare
        # float(held.get("heartbeat", 0)) then makes hb_age ~1.79e9 s, which
        # exceeds every stale window — so the benign branch below was
        # UNREACHABLE for those shapes and a perfectly healthy peer was paged
        # CRITICAL telling the operator to "clear it (stop.bat)". Treat a
        # sentinel as the benign case: it means the peer is mid-handshake, not
        # wedged. The lock's other readers already guard this
        # (core/runtime.py:314, :380); this was the sole unguarded read.
        _hb_raw = held.get("heartbeat")
        _pid_raw = str(held.get("pid", ""))
        if _hb_raw is None or not _pid_raw.isdigit():
            log.info("outputs/ lock held by a transient peer (pid=%s, no "
                     "heartbeat yet) - this redundant spawn is backing off, "
                     "no action needed", _pid_raw or "?")
            raise SystemExit(3)
        hb_age = time.time() - float(_hb_raw)
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


def _marks_age_sec(bot, wall_now: float) -> float:
    """WALL-clock age of the oldest live mark, from the engine's
    telemetry-only `_mark_wall_ts` stamps (latency audit 2026-08-07).

    Module-level and pure-ish on purpose: build_status calls it with a
    fresh time.time(), tests call it with a stub - no BotRunner needed.
    An unstamped symbol (first cycle after boot) defaults to wall_now,
    reading age 0 rather than a since-epoch number, matching the old
    gauge's benign cold start. Decision paths never read wall stamps;
    replay determinism is untouched."""
    wall = getattr(bot, "_mark_wall_ts", {}) or {}
    return round(max((wall_now - wall.get(s, wall_now)
                      for s in bot.marks), default=0.0), 1)


if __name__ == "__main__":
    main()
