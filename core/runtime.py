"""
core/runtime.py

Shared state layer between the engine (main.LiquidityBot), the runner
(runner.py) and the out-of-process observability and control planes -
Grafana Cloud telemetry export (scripts/gc_pusher.py reads these files)
and the git remote-control console (scripts/remote_control.py). None of
them share a process or import each other's live objects - they
communicate through files under outputs/, all writes atomic (tmp +
os.replace), all payloads plain JSON. Consumers can therefore never
block, slow, or crash the trading loop, and the loop never waits on any
reader.

status.json    - full telemetry-facing state, rewritten every cycle
equity.csv     - append-only equity curve (ts, equity, daily_pnl)
events.jsonl   - every log record from every module, structured
                {ts, level, logger, msg}; rotates at 5 MB
control/       - one JSON file per control command; runner consumes,
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

# The command vocabulary BOTH delivery paths enforce: send() raises on
# anything else, and consume() drops (unlinks) anything else. It must
# therefore stay a superset of what runner.BotRunner.handle_command actually
# implements — runner.HANDLED_COMMANDS is the other half of that contract and
# tests/test_audit_runner_state.py asserts the equality in BOTH directions.
# H7: "clear_fault" was implemented in the runner but missing here, so the
# ONLY in-band path out of a latched fault was dead AND silent (send() raised;
# a hand-dropped file was unlinked by consume() with no log, no ack).
VALID_COMMANDS = {
    "start", "pause", "stop", "step", "snapshot", "entries_on",
    "entries_off", "arm_live", "disarm_live", "clear_fault", "force_dry",
    "flatten_all", "budget_reanchor_week",
    "sim_price_shock", "sim_force_fear", "sim_force_regime", "sim_clear",
}
ARM_PHRASE = "ARM LIVE"


def replace_with_retry(src, dst, retries: int = 6) -> None:
    """os.replace with the transient-Windows-PermissionError retry.

    Windows raises PermissionError (WinError 5) when a READER holds the
    destination open; readers hold it for microseconds, so a short backoff
    almost always wins where letting it propagate loses the whole write.
    POSIX rename never hits this. The last attempt re-raises so a genuinely
    stuck destination is never silently swallowed here — the callers decide.

    M1: extracted so `StateStore._seal_and_write` (core/persistence.py) shares
    the EXACT retry that atomic_write_json has had all along. state.json is
    the book of record and was the one publisher without it, so a concurrent
    reader (core/session_digest via scripts/checkin.py hourly, or
    scripts/train_meta.py) could drop the post-fill "never lose an executed
    fill" snapshot — silently, since snapshot() swallows and its caller
    discards the return value."""
    for attempt in range(retries):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == retries - 1:
                raise
            time.sleep(0.02 * (attempt + 1))


def atomic_write_json(path: Path, payload: dict, _retries: int = 6):
    """Publish `payload` as UTF-8 JSON atomically: PID-scoped tmp + fsync +
    os.replace, so a reader can never observe a torn or half-written file.
    Retries transient Windows PermissionError renames; last attempt raises."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # PID-scoped tmp: a fixed "status.json.tmp" is shared, so during the
    # single-instance-lock convergence window (LOST_LIMIT cycles, or a
    # cold-start race) two runners open the SAME tmp -> truncate+interleave,
    # and os.replace can publish a half-written file a reader then fails to
    # parse. A per-writer tmp keeps each publish atomic and un-interleaved
    # (last writer wins the destination, but never a torn file).
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    # W2-20: unlink the tmp on EVERY exit path (json.dump raising mid-write,
    # or the retry loop below exhausting on a persistent PermissionError) -
    # a fixed 476-collision storm precedent already showed orphaned tmp
    # litter is a real failure mode (persistence.py's _seal_and_write uses
    # the same finally-unlink). A successful os.replace already renamed the
    # tmp away, so unlink(missing_ok=True) is a no-op on the happy path.
    try:
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
        replace_with_retry(tmp, path, _retries)
    finally:
        Path(tmp).unlink(missing_ok=True)


def durable_append(path, render, *, header: str = "", newline: str = "",
                   torn_sep: str = "\r\n", fsync: bool = True) -> bool:
    """Append ONE record so a hard kill cannot fuse it with the previous.

    THE DEFECT THIS EXISTS TO PREVENT, observed three times before this
    helper existed (core/fill_ledger.py, ml/registry.py, and the
    2026-08-06 sweep that found the same shape in seven more writers): a
    kill mid-append - auto_update's `taskkill /F` (scripts/auto_update.py),
    or power loss - leaves a final line with no trailing newline. The next
    append concatenates onto that fragment, welding two records into one
    malformed line, and the reader drops BOTH. One kill destroys the torn
    record AND the next good one.

    The append-mode sibling of atomic_write_json above: same durability
    contract, same never-raise discipline, for the file that grows a
    record at a time instead of being republished whole.

    Three guarantees, in the order they matter:

    1. SIZE-0 COUNTS AS NEW. A kill in the create-to-first-flush window
       leaves a zero-length file; appending a data row to it without the
       header makes csv.DictReader silently adopt the first RECORD as the
       column names, and every consumer then misparses the whole file with
       no error at all. `not path.exists()` alone does not catch this.
    2. A TORN TAIL IS ISOLATED, NEVER REPAIRED. Writing `torn_sep` first
       leaves the fragment as its own junk line that CSV/JSONL readers
       skip, and the new record lands intact beside it. Repair would have
       to invent the missing bytes; isolation loses exactly the one record
       the kill already destroyed, and no more.
    3. FSYNC bounds the torn window to the single record being written,
       instead of everything since the last OS flush.

    `render(f)` writes the record to the open handle - `csv.writer(f)
    .writerow(...)` for CSV callers, `f.write(json.dumps(rec) + "\\n")`
    for JSONL. `header` is written only when the file is new/empty, and
    must carry its own terminator. `newline=""` is the csv module's
    required setting; JSONL callers pass newline="\\n".

    Returns True when the record landed, False on OSError. Never raises:
    every call site is bookkeeping on a path where the trade, decision or
    disposition has ALREADY happened, and losing a log row must never
    unwind it (CLAUDE.md invariant 5)."""
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not path.exists() or path.stat().st_size == 0
        torn = False
        if not new_file:
            with open(path, "rb") as rf:
                rf.seek(-1, os.SEEK_END)
                torn = rf.read(1) != b"\n"
        with open(path, "a", newline=newline, encoding="utf-8") as f:
            if torn:
                f.write(torn_sep)          # isolate the torn fragment
            if new_file and header:
                f.write(header)
            render(f)
            f.flush()
            if fsync:
                os.fsync(f.fileno())
        return True
    except OSError:
        log.exception("durable append failed (%s) - record lost, the "
                      "action it describes is unaffected", path)
        return False


def read_json(path: Path):
    """Best-effort UTF-8 JSON read: the parsed payload, or None on any
    OS/parse/decode error (never raises - readers must not wedge on a torn
    file). ValueError, not JSONDecodeError: a non-UTF8 byte in the file
    raises UnicodeDecodeError - a ValueError that is NOT a JSONDecodeError -
    and the one caller that runs OUTSIDE any guarded loop
    (SingleInstanceLock.refresh, once per pc_supervisor cycle) turned that
    single uncaught path into a silent process death under pythonw
    (2026-08-16 incident: nothing on stderr, exit 1, whole job torn down)."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _heartbeat_age(rec: dict) -> float:
    """Seconds since `rec`'s lock heartbeat. A missing/empty/zero field
    coerces to epoch 0, so the age reads as ~the current epoch time (huge,
    always > stale_after); non-numeric garbage returns +inf. Either way
    unprovable liveness reads as STALE - a corrupt lock is then reclaimed
    and rewritten instead of float() raising out of a supervisor/runner
    loop (same never-raise discipline as read_json)."""
    try:
        return time.time() - float(rec.get("heartbeat", 0) or 0)
    except (TypeError, ValueError):
        return float("inf")


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
        """Append one {ts, level, logger, msg[, exc]} JSON line (UTF-8);
        any failure routes to handleError, never to the caller."""
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
    """Last `n` structured event dicts at/above `min_level`, oldest first.
    Reads only the file tail (bounded I/O); malformed lines are skipped and
    any OS error returns [] - a log reader must never raise."""
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
        # Failed heartbeat WRITES, tracked apart from lost_count: a disk error
        # is not a peer claiming the directory, so it must never reach
        # forfeited (which exits the runner). Observable, not fatal.
        self.write_failures = 0

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
                    if _heartbeat_age(cur) < self.stale_after:
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
                # stale-readable or crashed-empty foreign lock: drop it and
                # retry - but re-read IMMEDIATELY first (29e): between the
                # read above and this unlink, the OTHER racer in the same
                # reclaim race may have already unlinked, re-created and
                # WRITTEN the lock. Unlinking blind then destroys that
                # winner's LIVE lock and both racers acquire - the
                # double-drive this class exists to prevent. Any change ->
                # back off and re-evaluate; refresh()'s ownership forfeit
                # remains the backstop for the microsecond residue.
                if read_json(self.path) != cur:
                    continue
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
            if _heartbeat_age(cur) < self.stale_after:
                self.lost_count += 1            # a LIVE peer owns the dir
                return False
        try:
            atomic_write_json(self.path, {"pid": self.pid,
                                          "heartbeat": time.time()})
        except OSError as e:
            # ADVISORY, NEVER FATAL - but never a silent success either. This
            # used to `pass`, reset lost_count and return True, so a heartbeat
            # that never landed was indistinguishable from a healthy one at
            # every reader. The on-disk record then ages out against the 30s
            # stale window, a peer claims the directory, and two runners share
            # one outputs/ tree - interleaving appends into the hash-chained
            # audit - while this process still believes it holds the lock,
            # because refresh() said so.
            #
            # Counted SEPARATELY from lost_count on purpose: `forfeited` means
            # "a LIVE PEER owns this directory, exit", and a disk error is not
            # a peer. Routing write failures into it would let transient I/O
            # terminate the runner, which is worse than the defect above.
            self.write_failures += 1
            log.warning(
                "lock heartbeat write FAILED (%s) - the on-disk record is "
                "not advancing and will age out against the stale window; "
                "%d consecutive failure(s). Not fatal and NOT a forfeit: a "
                "write error is not a peer claiming the directory.",
                e, self.write_failures)
            return False
        self.lost_count = 0
        self.write_failures = 0
        return True

    @property
    def forfeited(self) -> bool:
        """True after LOST_LIMIT consecutive failed refreshes: a live peer
        owns the dir and this runner must exit."""
        return self.lost_count >= self.LOST_LIMIT

    def release(self):
        """Delete the lockfile - but only if this process still owns it
        (never destroys a peer's live lock)."""
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
        """Drop one command file (atomic write) into the queue; returns the
        command id. Raises ValueError on a command not in VALID_COMMANDS."""
        if cmd not in VALID_COMMANDS:
            raise ValueError(f"unknown command {cmd}")
        cid = f"{time.time():.6f}-{uuid.uuid4().hex[:6]}"
        atomic_write_json(self.dir / f"cmd_{cid}.json",
                        {"id": cid, "cmd": cmd, "args": args or {},
                        "sent_at": time.time()})
        return cid

    def consume(self) -> list:
        """Drain the queue in timestamp order: returns valid command dicts,
        deleting every file it touches. Unparseable/unknown files are still
        DROPPED (the queue can never wedge - that property is deliberate), but
        H7: they are no longer dropped SILENTLY. `clear_fault` was implemented
        in the runner and missing from VALID_COMMANDS for its whole life, and
        the only symptom was a command file that vanished with no log, no ack
        and no error - the drift was undetectable in production."""
        cmds = []
        for f in sorted(self.dir.glob("cmd_*.json")):
            payload = read_json(f)
            try:
                f.unlink()
            except OSError:
                pass
            if payload and payload.get("cmd") in VALID_COMMANDS:
                cmds.append(payload)
            else:
                log.warning("control: dropped unknown/unparseable command "
                            "file %s (cmd=%r not in VALID_COMMANDS) - it was "
                            "NOT executed", f.name,
                            (payload or {}).get("cmd")
                            if isinstance(payload, dict) else None)
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
        """True while any injected override still has cycles remaining."""
        return bool(self.price_shock or self.force_fear or self.force_regime)

    def tick(self):
        """Decrement every override's remaining-cycle count by one engine
        cycle, expiring those that reach zero."""
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
        """Status-schema `sim` payload: the currently active overrides."""
        return {"price_shock": self.price_shock,
                "force_fear_cycles": self.force_fear,
                "force_regime": self.force_regime}


# ---------------------------------------------------------------------------
class StatusWriter:
    """Owns the telemetry files: atomic status.json rewrites plus the
    append-only equity.csv curve (throttled to one row / 15s)."""

    def __init__(self, status_path: str = "outputs/status.json",
                equity_path: str = "outputs/equity.csv"):
        self.status_path = Path(status_path)
        self.equity_path = Path(equity_path)
        self._last_equity_ts = 0.0
        self._write_fails = 0        # consecutive status-write losses
        # Header creation is now durable_append's job (it treats a
        # zero-length file as new), so a kill in the create-to-first-flush
        # window can no longer leave a headerless equity.csv that readers
        # parse with the first SAMPLE as their column names.
        self.equity_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, payload: dict, now: float | None = None):
        """Publish the status snapshot atomically (MUTATES payload: adds
        written_at) and append the throttled equity row. A lost write is
        benign - the next cycle rewrites - so failures are counted and
        warned sparsely, never raised."""
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
            # Highest write frequency of any append-only file in the repo
            # (every 15s, ~5,760 rows/day), so it has the widest exposure
            # window to auto_update's taskkill. fsync=False: the payload is
            # a dense redundant time series where one interpolatable sample
            # is not worth an fsync 5,760 times a day - the torn-tail heal
            # and the size-0 header guard are what matter here.
            line = (f"{now:.0f},{payload.get('equity', 0):.2f},"
                    f"{payload.get('daily_pnl', 0):.2f}\n")
            durable_append(self.equity_path, lambda f: f.write(line),
                           header="ts,equity,daily_pnl\n", newline="\n",
                           torn_sep="\n", fsync=False)
