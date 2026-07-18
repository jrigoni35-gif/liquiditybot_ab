"""
core/runtime.py

Shared state layer between the engine (main.LiquidityBot), the runner
(runner.py) and the UI (ui/dashboard.py). The three never share a
process or import each other's live objects - they communicate through
files under outputs/, all writes atomic (tmp + os.replace), all
payloads plain JSON. The UI can therefore never block, slow, or crash
the trading loop, and the loop can never freeze the UI.

status.json    - full UI-facing state, rewritten every cycle
equity.csv     - append-only equity curve (ts, equity, daily_pnl)
events.jsonl   - every log record from every module, structured
                {ts, level, logger, msg}; rotates at 5 MB
control/       - one JSON file per UI command; runner consumes,
                deletes, and acks into events.jsonl
state.json     - the pause/resume snapshot (core/persistence.py)

SimOverrides lets the operator inject conditions (price shock, forced
fear, forced regime) - DRY RUN ONLY, enforced by the runner.
"""

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger("liquiditybot.runtime")

VALID_COMMANDS = {
    "start", "pause", "stop", "step", "snapshot", "entries_on",
    "entries_off", "arm_live", "disarm_live", "force_dry", "flatten_all",
    "sim_price_shock", "sim_force_fear", "sim_force_regime", "sim_clear",
}
ARM_PHRASE = "ARM LIVE"


def atomic_write_json(path: Path, payload: dict, _retries: int = 6):
    path.parent.mkdir(parents=True, exist_ok=True)
    # PID-scoped tmp: a fixed "status.json.tmp" is shared, so during the
    # single-instance-lock convergence window (LOST_LIMIT cycles, or a
    # cold-start race) two runners open the SAME tmp -> truncate+interleave,
    # and os.replace can publish a half-written file a reader then fails to
    # parse. A per-writer tmp keeps each publish atomic and un-interleaved
    # (last writer wins the destination, but never a torn file).
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, default=str)
        # fsync the tmp before the rename publishes it: without this a power
        # loss can leave the destination (status.json, or runner.lock) torn or
        # zero-length, and a restart then reads runner.lock as "no owner".
        f.flush()
        os.fsync(f.fileno())
    # Windows: os.replace raises PermissionError (WinError 5) when a READER
    # (the dashboard or a monitor) has the destination open - the file lock is
    # transient (readers hold it for microseconds), so retry with a short
    # backoff instead of letting the whole cycle error out and status.json go
    # stale. POSIX rename never hits this. Last attempt re-raises.
    for attempt in range(_retries):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == _retries - 1:
                raise
            time.sleep(0.02 * (attempt + 1))


def read_json(path: Path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
class JsonlLogHandler(logging.Handler):
    """Structured log capture: every record from every module lands as one
    JSON line the UI can filter by level/logger. Replaces print-style logs
    for machine consumption; the console handler stays for humans."""

    def __init__(self, path: str = "outputs/events.jsonl",
                max_bytes: int = 5_000_000):
        super().__init__()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes

    def _maybe_rotate(self):
        # rotation is check-then-rename and NOT cross-process atomic; if a
        # reader or a second writer races the rename it can raise. Isolate it
        # in its own guard so a rotation race can never lose the LOG LINE the
        # emit() below is about to write (the old inline rename put the whole
        # emit into handleError on any rotation error).
        try:
            if self.path.exists() and self.path.stat().st_size > self.max_bytes:
                self.path.replace(self.path.with_suffix(".jsonl.1"))
        except OSError:
            pass

    def emit(self, record: logging.LogRecord):
        try:
            self._maybe_rotate()
            payload = {
                "ts": round(record.created, 3),
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage()[:800],
            }
            # log.exception() callers rely on exc_info for the actual error;
            # dropping it made lines like "runner cycle error - continuing"
            # undiagnosable after the fact. Keep it compact but present.
            if record.exc_info and record.exc_info[0] is not None:
                import traceback
                payload["exc"] = "".join(traceback.format_exception(
                    *record.exc_info))[-1200:]
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
        except Exception:
            self.handleError(record)


def tail_events(path: str = "outputs/events.jsonl", n: int = 200,
                min_level: str = "INFO") -> list:
    order = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}
    floor = order.get(min_level, 1)
    p = Path(path)
    if not p.exists():
        return []
    out = []
    try:
        with open(p, "rb") as f:
            f.seek(max(f.seek(0, 2) - 400_000, 0))
            lines = f.read().decode(errors="replace").splitlines()
        for line in lines[-4000:]:
            try:
                e = json.loads(line)
                if order.get(e.get("level"), 1) >= floor:
                    out.append(e)
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return out[-n:]


# ---------------------------------------------------------------------------
class SingleInstanceLock:
    """Heartbeat lockfile so only ONE runner ever drives a given outputs/ dir.

    Two runners against the same outputs/ clobber each other's status.json and
    state.json, race the control queue, and interleave the hash-chained audit
    trail — and a stuck/zombie duplicate makes status.json flap "stale". The
    lock stores {pid, heartbeat}; a live runner refreshes the heartbeat every
    cycle, so a second launch sees a fresh heartbeat and refuses. A crashed
    runner's heartbeat goes stale and the next launch takes over — self-healing,
    no OS-specific PID probing (portable to Windows)."""

    LOST_LIMIT = 3      # consecutive lost refreshes before forfeiting

    def __init__(self, path: str = "outputs/runner.lock",
                 stale_after_sec: float = 30.0):
        self.path = Path(path)
        self.pid = os.getpid()
        self.stale_after = stale_after_sec
        self.lost_count = 0

    def acquire(self) -> Optional[dict]:
        """Atomically claim the lock. Returns None on success, or the LIVE
        holder's record if another runner already owns this outputs/ dir.

        The old body read-then-wrote with no atomicity: two runners launched
        together BOTH saw no/stale lock, both wrote their pid, both returned
        None, and both drove cycle_once for up to LOST_LIMIT cycles (double
        control-command execution, audit interleave, live-order dup). An
        exclusive create (O_CREAT|O_EXCL — atomic and portable to Windows) lets
        exactly ONE win the cold-start race; the loser reads the winner's fresh
        record and refuses. A stale/leftover foreign lock is dropped and the
        create retried; the residual live-peer window (create-before-write) is
        still caught by refresh()'s ownership check + forfeit."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _attempt in range(3):
            try:
                fd = os.open(str(self.path),
                             os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                cur = read_json(self.path)
                if isinstance(cur, dict) and cur.get("pid") == self.pid:
                    self.refresh()              # our own lock: reclaim
                    return None
                if isinstance(cur, dict):
                    age = time.time() - float(cur.get("heartbeat", 0) or 0)
                    if age < self.stale_after:
                        return cur              # a live peer owns it
                    # a stale, READABLE foreign lock -> safe to reclaim below
                else:
                    # exists but UNREADABLE/EMPTY: this is the create-before-
                    # write window of the peer that just WON the O_EXCL race (a
                    # genuine mid-create is milliseconds old). The old code
                    # unlinked it here — which destroyed the winner's fresh lock
                    # so BOTH racers returned None (the double-acquire this whole
                    # thing exists to prevent). Back off instead: only an empty
                    # lock that has sat unwritten past a short grace is a
                    # crashed-mid-create leftover worth reclaiming.
                    try:
                        empty_age = time.time() - self.path.stat().st_mtime
                    except OSError:
                        empty_age = self.stale_after + 1.0   # vanished: retry
                    if empty_age < min(self.stale_after, 5.0):
                        return {"pid": "initializing"}       # a peer is mid-claim
                # stale-readable or crashed-empty foreign lock: drop it and retry
                try:
                    self.path.unlink()
                except OSError:
                    pass
                continue
            except OSError:
                # can't create exclusively (fs error, e.g. a Windows scanner
                # holding the file): best-effort claim, but HONOR refresh()'s
                # verdict — the old unconditional `return None` let BOTH
                # racers "acquire" past a live peer (audit C-F14 2026-07-17)
                if self.refresh():
                    return None
                cur = read_json(self.path)
                return cur if isinstance(cur, dict) else {"pid": "contended"}
            else:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump({"pid": self.pid, "heartbeat": time.time()}, f)
                    f.flush()
                    os.fsync(f.fileno())
                self.lost_count = 0
                return None
        # lost the create race repeatedly to a peer that keeps recreating it
        cur = read_json(self.path)
        return cur if isinstance(cur, dict) else {"pid": "contended"}

    def refresh(self) -> bool:
        """Heartbeat, OWNERSHIP-AWARE. The original rewrote {pid, heartbeat}
        unconditionally, so two live runners flip-flopped the file every
        cycle - each believed it held the lock and the duplicate ran
        forever (observed live 2026-07-14: THREE runners, zombies eating
        stop commands and racing snapshots). A fresh FOREIGN record is now
        never overwritten: the loser's refresh fails, and after LOST_LIMIT
        consecutive losses `forfeited` turns True and the runner exits.
        Deterministic winner, still portable (no fcntl on Windows)."""
        cur = read_json(self.path)
        if isinstance(cur, dict) and cur.get("pid") != self.pid:
            age = time.time() - float(cur.get("heartbeat", 0) or 0)
            if age < self.stale_after:
                self.lost_count += 1            # a LIVE peer owns the dir
                return False
        try:
            atomic_write_json(self.path, {"pid": self.pid,
                                          "heartbeat": time.time()})
        except OSError:
            pass                                # lock is advisory; never fatal
        self.lost_count = 0
        return True

    @property
    def forfeited(self) -> bool:
        return self.lost_count >= self.LOST_LIMIT

    def release(self):
        cur = read_json(self.path)
        if isinstance(cur, dict) and cur.get("pid") == self.pid:
            try:
                self.path.unlink()
            except OSError:
                pass


# ---------------------------------------------------------------------------
class ControlChannel:
    """File-based command queue: UI (or shell) drops one JSON file per
    command into outputs/control/; the runner consumes in timestamp order,
    deletes, and acks into the event log. No sockets, no locks, no way to
    wedge the loop."""

    def __init__(self, directory: str = "outputs/control"):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    def send(self, cmd: str, args: dict | None = None) -> str:
        if cmd not in VALID_COMMANDS:
            raise ValueError(f"unknown command {cmd}")
        cid = f"{time.time():.6f}-{uuid.uuid4().hex[:6]}"
        atomic_write_json(self.dir / f"cmd_{cid}.json",
                        {"id": cid, "cmd": cmd, "args": args or {},
                        "sent_at": time.time()})
        return cid

    def consume(self) -> list:
        cmds = []
        for f in sorted(self.dir.glob("cmd_*.json")):
            payload = read_json(f)
            try:
                f.unlink()
            except OSError:
                pass
            if payload and payload.get("cmd") in VALID_COMMANDS:
                cmds.append(payload)
        return cmds


# ---------------------------------------------------------------------------
@dataclass
class SimOverrides:
    """Injected conditions for testing behavior on demand. Dry run only -
    the runner refuses every sim command when config is live."""
    price_shock: dict = field(default_factory=dict)   # asset -> {"pct","cycles"}
    force_fear: int = 0                               # cycles remaining
    force_regime: dict = field(default_factory=dict)  # asset -> {"label","cycles"}

    def active(self) -> bool:
        return bool(self.price_shock or self.force_fear or self.force_regime)

    def tick(self):
        for a in list(self.price_shock):
            self.price_shock[a]["cycles"] -= 1
            if self.price_shock[a]["cycles"] <= 0:
                del self.price_shock[a]
        if self.force_fear > 0:
            self.force_fear -= 1
        for a in list(self.force_regime):
            self.force_regime[a]["cycles"] -= 1
            if self.force_regime[a]["cycles"] <= 0:
                del self.force_regime[a]

    def describe(self) -> dict:
        return {"price_shock": self.price_shock,
                "force_fear_cycles": self.force_fear,
                "force_regime": self.force_regime}


# ---------------------------------------------------------------------------
class StatusWriter:
    def __init__(self, status_path: str = "outputs/status.json",
                equity_path: str = "outputs/equity.csv"):
        self.status_path = Path(status_path)
        self.equity_path = Path(equity_path)
        self._last_equity_ts = 0.0
        self._write_fails = 0        # consecutive status-write losses
        if not self.equity_path.exists():
            self.equity_path.parent.mkdir(parents=True, exist_ok=True)
            self.equity_path.write_text("ts,equity,daily_pnl\n", encoding="utf-8")

    def write(self, payload: dict, now: float | None = None):
        now = now if now is not None else time.time()
        payload["written_at"] = now
        try:
            atomic_write_json(self.status_path, payload)
            if self._write_fails:
                log.info("status writes recovered after %d failed "
                         "attempt(s)", self._write_fails)
                self._write_fails = 0
        except PermissionError:
            # Windows: an external reader/scanner (dashboard, Defender,
            # sync client) can hold status.json past the retry window. A
            # lost status write is benign - the next cycle rewrites - but
            # letting it raise turned each collision into a full
            # cycle-error traceback (476 in one storm) and tripped the
            # check-in's error-volume anomaly. Count, warn sparsely.
            self._write_fails += 1
            if self._write_fails in (1, 10, 100) \
                    or self._write_fails % 1000 == 0:
                log.warning("status write skipped (reader holds the file; "
                            "WinError 5) - %d consecutive failures; next "
                            "cycle rewrites", self._write_fails)
        if now - self._last_equity_ts >= 15.0:
            self._last_equity_ts = now
            try:
                with open(self.equity_path, "a", encoding="utf-8") as f:
                    f.write(f"{now:.0f},{payload.get('equity', 0):.2f},"
                            f"{payload.get('daily_pnl', 0):.2f}\n")
            except OSError:
                pass
