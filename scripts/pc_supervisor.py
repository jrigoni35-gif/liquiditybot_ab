"""
scripts/pc_supervisor.py — always-on supervisor for a self-hosted PC run.

The cloud session-start hook keeps the bot + telemetry alive in the ephemeral
container; this is its PC twin. It runs forever (Task Scheduler keeps IT alive
and restarts it on death — see scripts/install_autostart.bat) and, every
CHECK_SEC, ensures the runner and the two Grafana pushers are alive, relaunching
any that died — HIDDEN (no console windows, the whole point of running headless
at logon). Liveness is heartbeat-based (fresh files), so no psutil dependency
and no fragile Windows command-line scraping:

  * runner    -> outputs/status.json 'written_at' fresher than STALE_SEC
  * pusher    -> outputs/gc_pusher.log mtime fresher than STALE_SEC
  * logpusher -> outputs/gc_log_pusher.log mtime fresher than STALE_SEC

The runner's SingleInstanceLock makes a relaunch safe even if the old one is
merely hung (the duplicate is refused, not doubled). Fail-safe throughout: any
error logs one line WITH ITS TRACEBACK and retries next tick; the bot never
depends on this.

JOB-OBJECT HAZARD (2026-08-16 incident): when Task Scheduler launches this
script, the task wraps it in a job object; children spawned without a
successful CREATE_BREAKAWAY_FROM_JOB inherit it and are KILLED when this
process exits (the scheduler tears the job down). _spawn tries breakaway
first and logs LOUDLY when the job denies it; main() logs the live job/
breakaway status at startup (_job_status). When breakaway is denied the
children's survival depends entirely on this process not dying - hence the
never-die-silently loop (_guarded_iteration) and exit forensics
(_arm_exit_forensics) - and on the external revival layer (the keepalive
scheduled task): verify that task's repetition never expires
(schtasks /query /v; a One-Time trigger with StopAtDurationEnd stops
reviving forever once its duration lapses).

Telemetry token: materialised once from the GC_OTLP_TOKEN env var (set it as a
Windows user environment variable) into ~/.liquiditybot/gc-token, matching the
cloud hook — so the pushers find it without a token ever entering git.

Run it directly to test (Ctrl+C to stop); Task Scheduler runs it directly
via .venv\\Scripts\\pythonw.exe at logon (see scripts/install_autostart.ps1).
"""
import atexit
import json
import os
import socket
import subprocess  # nosec B404 - fixed argv, no shell
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.runtime import SingleInstanceLock, read_json  # noqa: E402

OUT = ROOT / "outputs"
CHECK_SEC = 30.0
STALE_SEC = 120.0          # a heartbeat older than this = process is gone
# test-gated self-update cadence: how often to check origin/main for new code.
# Default 15 min — the check is a bare `git fetch` + rev compare (auto_update
# only runs the heavy battery when main actually MOVED, and its single-updater
# lock refuses overlap), so a push self-deploys within minutes instead of the
# old daily wait. LB_NO_AUTO_UPDATE=1 disables it entirely (checked here AND
# in auto_update.py, so either gate turns it fully off).
try:
    UPDATE_SEC = float(os.environ.get("LB_AUTO_UPDATE_SEC", "900"))
except ValueError:
    UPDATE_SEC = 900.0
_UPDATE_STAMP = OUT / ".auto_update_stamp"
# one-bot remote control (scripts/remote_control.py): poll the durable branch
# for operator commands, and publish the full status.json back, so the bot is
# drivable from anywhere without an open port. Kill switches mirror the
# updater's: LB_NO_REMOTE_CMD / LB_NO_STATUS_PUSH disable each direction.
try:
    REMOTE_CMD_SEC = float(os.environ.get("LB_REMOTE_CMD_POLL_SEC", "120"))
except ValueError:
    REMOTE_CMD_SEC = 120.0
try:
    STATUS_PUSH_SEC = float(os.environ.get("LB_STATUS_PUSH_SEC", "600"))
except ValueError:
    STATUS_PUSH_SEC = 600.0
_REMOTE_CMD_STAMP = OUT / ".remote_cmd_stamp"
_STATUS_PUSH_STAMP = OUT / ".status_push_stamp"
# one-bot corpus sync (scripts/corpus_sync.py): pull the durable branch's
# learning bundles in, so this machine trains on the SAME foundation the
# rest of the fleet contributes to. LB_NO_CORPUS_SYNC=1 disables.
try:
    CORPUS_SYNC_SEC = float(os.environ.get("LB_CORPUS_SYNC_SEC", "3600"))
except ValueError:
    CORPUS_SYNC_SEC = 3600.0
# one-bot corpus EXPORT (scripts/telemetry_backup.py --once): push THIS
# machine's live training corpus to the durable branch under the pc-live
# label. Found live 2026-07-18: the PC's corpus (1177 rows) had NO export
# path at all — only the cloud mirror pushed bundles, so 54% of the
# learning data existed on exactly one disk. LB_NO_TELEM_BACKUP=1 disables.
try:
    TELEM_BACKUP_SEC = float(os.environ.get("LB_TELEM_BACKUP_SEC", "3600"))
except ValueError:
    TELEM_BACKUP_SEC = 3600.0
_TELEM_BACKUP_STAMP = OUT / ".telem_backup_stamp"
_CORPUS_SYNC_STAMP = OUT / ".corpus_sync_stamp"
# rotation-hazard fast path (task-rotation-report.md): ml/history.py's
# _ensure_schema rotates the corpus to a fresh .bak_<ts> the instant it sees
# an old-header production file under new code, leaving the live file near-
# empty until scripts/corpus_sync.py's recover_local_baks() merges the .bak
# back in. Waiting out the up-to-CORPUS_SYNC_SEC cadence for that meant
# everything reading the corpus in between (evidence-gate row floors, a
# scheduled retrain, status.json row counts) saw a near-empty file for as
# long as an hour. HistoryStore._mark_rotated() drops this marker NEXT TO
# the corpus on rotation (ml/history.py owns writing it, has zero knowledge
# of this module); its mere presence here means "run corpus_sync NOW", not
# on the hourly clock. Named distinctly from _CORPUS_SYNC_STAMP (that one is
# a "last ran at" cadence stamp; this one is a "something happened, act on
# it" event marker) - see _corpus_sync_due for the self-clearing contract.
_CORPUS_ROTATION_MARKER = OUT / ".corpus_rotated"
# ONE-SHOT prompt sweep (operator request 2026-07-20): close the DEAD Command
# Prompt windows the pre-fix code left open. Runs once, then the stamp holds
# forever (delete the stamp to run it again). v2 stamp: the v1 sweep could
# silently no-op on Windows-Terminal-default machines; the hardened script
# (runner-signature fallback + evidence log) gets one fresh shot.
_PROMPT_SWEEP_STAMP = OUT / ".prompt_sweep_done2"
# ONE-SHOT legacy scheduled-task migration: the pre-supervisor runbook
# registered 'Revival' (console python.exe keepalive.py, every 10 min) and
# 'Deep audit' (run_checkin.bat under cmd.exe, hourly). Each fire pops a
# visible console — the operator's recurring "command centers". Re-register
# those actions windowless (pythonw / the quiet wrapper); never delete.
_TASK_MIGRATE_STAMP = OUT / ".task_migrate_done"
# moomoo OpenD gateway: relaunch throttle. A GUI-login OpenD that never opens
# its port must NOT be relaunched every tick (that stacks login windows), so a
# launch attempt is spaced at least this far apart regardless of outcome.
try:
    OPEND_RELAUNCH_SEC = float(os.environ.get("LB_OPEND_RELAUNCH_SEC", "300"))
except ValueError:
    OPEND_RELAUNCH_SEC = 300.0
_OPEND_STAMP = OUT / ".opend_launch_stamp"
# Dashboard auto-import (2026-07-30, operator away from the PC): when a
# deploy changes docs/grafana/*.json and a Grafana service-account token
# is available (GRAFANA_SA_TOKEN env, or persisted at
# ~/.liquiditybot/grafana-sa-token — the gc-token pattern), the boards
# import themselves. The stamp stores the imported content FINGERPRINT
# and is written by the import child ONLY on full success
# (grafana_import.py --stamp contract), so failures retry next tick.
# Disable with LB_NO_DASH_IMPORT.
_DASH_IMPORT_STAMP = OUT / ".dash_import_stamp"
_DASH_DIR = Path(__file__).resolve().parents[1] / "docs" / "grafana"
IS_WIN = os.name == "nt"
PY = sys.executable        # the venv's python (pythonw.exe when run hidden)
_SELF = Path(__file__).resolve()
try:
    _SELF_MTIME = _SELF.stat().st_mtime
except OSError:
    _SELF_MTIME = 0.0


# Log destination as a REBINDABLE module attribute (2026-07-31). The
# suite drives this script's functions in-process, and a hardcoded
# `OUT / "pc_supervisor.log"` inside log() meant every such test appended to the
# operator's REAL pc_supervisor.log - the same defect measured across six
# outputs/ files that day. Tests monkeypatch LOG_PATH; production reads
# the default and behaves byte-identically. tests/conftest.py's
# _no_production_outputs_writes fails any test that regresses this.
LOG_PATH = OUT / "pc_supervisor.log"


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} pc_supervisor: {msg}"
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


# W2-13: a backwards clock step (RTC fast at boot, then a time service
# steps it back) makes a heartbeat/stamp mtime read from the FUTURE, so
# `time.time() - mtime` goes negative — comparing only `age < threshold`
# then reads every cadence as fresh/not-due for as long as the clock lags
# the stamp, including blocking a dead runner's relaunch. A small negative
# age (ordinary NTP jitter, a few seconds) is not a clock step and must
# stay fresh/not-due; only a jump beyond this allowance is suspect. ~120s
# comfortably exceeds normal jitter while still catching a real step-back.
CLOCK_SKEW_ALLOWANCE_SEC = 120.0


def _stale_or_due(age: float, threshold: float,
                  skew_allowance: float = CLOCK_SKEW_ALLOWANCE_SEC) -> bool:
    """True when `age` (seconds since a stamp's mtime) means STALE/DUE:
    ordinary staleness (age >= threshold) OR a backwards clock step that
    makes the mtime read from the future (age < -skew_allowance). Age
    inside [-skew_allowance, threshold) is fresh/not-due."""
    return age < -skew_allowance or age >= threshold


def _fresh(path: Path, key: str | None = None) -> bool:
    """True if `path` is a heartbeat fresher than STALE_SEC. When `key` is
    given, read that numeric epoch field from a JSON file; else use mtime."""
    try:
        if key is not None:
            import json
            with open(path, encoding="utf-8") as fh:
                ts = float(json.load(fh).get(key, 0.0))
        else:
            ts = path.stat().st_mtime
        return not _stale_or_due(time.time() - ts, STALE_SEC)
    except (OSError, ValueError, TypeError):
        return False


# Child-log rotation cap/retention. Lifted defaults, overridable via env
# (LB_CHILD_LOG_MAX_MB / LB_CHILD_LOG_KEEP) so no fitted literal hides in a
# decision path: 64MB is sized against the measured growth (runner.log hit
# 153.8MB in ~3 weeks, ~7MB/day, so one generation spans ~9 days) and 2
# archives keep ~3 weeks of forensics - the window every incident
# investigation this month actually needed. Rotation must happen at the
# SPAWN boundary and nowhere else: Windows refuses to rename a file with an
# open handle, and between spawns the dead child's handle is released -
# this is the only moment the rename can succeed.
_CHILD_LOG_MAX_BYTES = int(float(
    os.environ.get("LB_CHILD_LOG_MAX_MB", "64")) * 1024 * 1024)
_CHILD_LOG_KEEP = max(int(os.environ.get("LB_CHILD_LOG_KEEP", "2")), 1)


def _rotate_child_log(path: Path) -> None:
    """Rotate `path` to path.1 (shifting .1->.2 ...) when it exceeds the
    cap. Best-effort by contract: a lingering handle (a child not fully
    dead yet, an operator tail, AV) makes os.replace raise on Windows, and
    the spawn must proceed with append rather than fail - an unrotated log
    is an inconvenience, an unspawned runner is an outage. gc_log_pusher's
    _drain_rotated already handles the rename losslessly on its side."""
    try:
        if not path.exists() or path.stat().st_size < _CHILD_LOG_MAX_BYTES:
            return
        for i in range(_CHILD_LOG_KEEP, 0, -1):
            src = path.with_name(f"{path.name}.{i}")
            if i == _CHILD_LOG_KEEP:
                src.unlink(missing_ok=True)
                continue
            if src.exists():
                os.replace(src, path.with_name(f"{path.name}.{i + 1}"))
        os.replace(path, path.with_name(f"{path.name}.1"))
        log(f"rotated {path.name} ({_CHILD_LOG_MAX_BYTES >> 20}MB cap)")
    except OSError as e:
        log(f"child-log rotation skipped for {path.name} ({e}) - "
            f"appending to the existing file")


def _spawn(argv: list, own_log: bool = True) -> None:
    """Launch a windowless child that outlives this process. When own_log is
    False the child keeps its own log file, so stdout goes to DEVNULL
    (avoids double-writing every line).

    CREATE_NO_WINDOW (0x08000000) | CREATE_NEW_PROCESS_GROUP (0x00000200) —
    deliberately NOT DETACHED_PROCESS: per CreateProcess docs the two are
    mutually exclusive and DETACHED wins, leaving the child with NO console;
    any console-subsystem grandchild spawned without flags would then pop a
    VISIBLE window. CREATE_NO_WINDOW instead gives the child a HIDDEN
    console that every descendant inherits — the whole tree stays silent.

    CREATE_BREAKAWAY_FROM_JOB (0x01000000): Task Scheduler wraps the task's
    process in a JOB OBJECT and every spawned child inherits it, so the task
    instance reads "Running" while ANY runner/pusher lives — IgnoreNew then
    silently DROPS every Start request and RestartOnFailure never fires,
    because the instance never "ends" (observed live 2026-07-21 22:01: dead
    supervisor, living children, and no way to restart it via the task).
    Breaking children out of the job makes the task track the SUPERVISOR
    alone. Fall back to in-job spawn when the job forbids breakaway."""
    kwargs: dict = {"cwd": str(ROOT)}
    # Sibling of LOG_PATH, not of the module-level OUT: a spawned child's
    # stdout log is the same operator artifact as this supervisor's own,
    # and pinning it to OUT meant a test that drove _spawn appended real
    # child output (outputs/telemetry_backup.log) to the production tree
    # while LOG_PATH was already redirected. One knob now moves both.
    child_log = LOG_PATH.parent / (Path(argv[1]).stem + ".log")
    if own_log:
        _rotate_child_log(child_log)
    out = (open(child_log, "a", encoding="utf-8")
           if own_log else subprocess.DEVNULL)
    if not IS_WIN:
        subprocess.Popen(argv, stdout=out, stderr=subprocess.STDOUT,  # nosec B603
                         stdin=subprocess.DEVNULL, start_new_session=True,
                         **kwargs)
        return
    base = 0x08000000 | 0x00000200
    err: OSError | None = None
    for flags in (base | 0x01000000, base):     # breakaway, then in-job
        try:
            subprocess.Popen(argv, stdout=out,               # nosec B603
                             stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL,
                             creationflags=flags, **kwargs)
            if not flags & 0x01000000:
                # LOUD by design (2026-08-16 incident): this fallback was
                # silent, so the forensics could not say whether children
                # sat inside the task's job. They did - when the supervisor
                # exited, the job teardown killed the runner and every
                # pusher within one heartbeat. If this line appears, the
                # children WILL die with this process; only an external
                # revival layer (keepalive task) brings them back.
                log(f"spawn {argv[1]!r}: job denies breakaway ({err}) - "
                    f"child is IN the task job and dies with this process")
            return
        except OSError as e:
            err = e
            continue        # job denies breakaway -> retry inside the job
    log(f"spawn failed for {argv[1]!r} (both flag sets refused: {err})")


def _job_status() -> str:
    """One honest startup line about the Windows JOB OBJECT this process
    sits in - asked of the live kernel, never inferred. The 2026-08-16
    incident hinged on exactly this being unknowable after the fact: the
    supervisor exited, Task Scheduler tore its job down, and the runner +
    every pusher died inside one heartbeat - and no log line ever said the
    children were in the job (the breakaway fallback in _spawn was
    silent). JOB_OBJECT_LIMIT_BREAKAWAY_OK (0x800) governs whether _spawn's
    CREATE_BREAKAWAY_FROM_JOB can succeed; without it every child is
    hostage to this process's exit. Fail-safe: any probe failure returns a
    string saying so - this is forensics, never a gate."""
    if not IS_WIN:
        return "n/a (posix session semantics)"
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        in_job = wintypes.BOOL(0)
        if not k32.IsProcessInJob(k32.GetCurrentProcess(), None,
                                  ctypes.byref(in_job)):
            return "unknown (IsProcessInJob failed)"
        if not in_job.value:
            return "not in a job - children survive this process's exit"

        class _IoCounters(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in (
                "ReadOperationCount", "WriteOperationCount",
                "OtherOperationCount", "ReadTransferCount",
                "WriteTransferCount", "OtherTransferCount")]

        class _BasicLimits(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                        ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t),    # ULONG_PTR
                        ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class _ExtendedLimits(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", _BasicLimits),
                        ("IoInfo", _IoCounters),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        info = _ExtendedLimits()
        ok = k32.QueryInformationJobObject(
            None, 9,               # 9 = JobObjectExtendedLimitInformation,
            ctypes.byref(info),    # NULL handle = the job WE are in
            ctypes.sizeof(info), None)
        if not ok:
            return "IN a job (limit flags unreadable)"
        flags = int(info.BasicLimitInformation.LimitFlags)
        breakaway = bool(flags & 0x00000800)      # BREAKAWAY_OK
        kill_on_close = bool(flags & 0x00002000)  # KILL_ON_JOB_CLOSE
        return (f"IN a job: limits=0x{flags:08x} breakaway_ok={breakaway} "
                f"kill_on_job_close={kill_on_close}"
                + ("" if breakaway else " - children CANNOT break away "
                   "and die when this process exits"))
    except Exception as e:            # noqa: BLE001 - forensics, never a gate
        return f"unknown ({e})"


# boot-grace spawn throttle: a freshly spawned runner takes minutes to boot
# before its heartbeat freshens, and the old per-tick stale check respawned it
# every 30s meanwhile (observed live 2026-07-21 21:58-22:01: 2x runner + 2x
# every pusher from one supervisor). One spawn per child per grace window;
# the heartbeat check still governs WHETHER a spawn is needed at all.
try:
    BOOT_GRACE_SEC = float(os.environ.get("LB_BOOT_GRACE_SEC", "180"))
except ValueError:
    BOOT_GRACE_SEC = 180.0
_last_spawn: dict = {}


def _spawn_gated(key: str, argv: list, own_log: bool = True) -> bool:
    """_spawn, at most once per BOOT_GRACE_SEC per child. True if spawned."""
    now = time.time()
    if now - _last_spawn.get(key, 0.0) < BOOT_GRACE_SEC:
        return False
    _last_spawn[key] = now
    _spawn(argv, own_log)
    return True


def _auto_update_due() -> bool:
    """True when a test-gated self-update check is due (never run, or older than
    UPDATE_SEC). Off entirely when LB_NO_AUTO_UPDATE is set."""
    if os.environ.get("LB_NO_AUTO_UPDATE"):
        return False
    try:
        return _stale_or_due(time.time() - _UPDATE_STAMP.stat().st_mtime,
                             UPDATE_SEC)
    except OSError:
        return True          # no stamp yet -> due (check once on first boot)


def _mark_update_checked() -> None:
    try:
        OUT.mkdir(exist_ok=True)
        _UPDATE_STAMP.touch()
    except OSError:
        pass


def _stamp_due(stamp: Path, period_sec: float) -> bool:
    """True when `stamp` is absent, older than period_sec, or clock-stepped
    into the future; touches it on True so each caller runs at most once
    per period (same contract as the auto-update stamp, generalized)."""
    try:
        if not _stale_or_due(time.time() - stamp.stat().st_mtime, period_sec):
            return False
    except OSError:
        pass                       # no stamp yet -> due
    try:
        OUT.mkdir(exist_ok=True)
        stamp.touch()
    except OSError:
        pass
    return True


def _dash_fingerprint(dash_dir: Path = _DASH_DIR) -> str:
    """Stable content hash of the repo's dashboard JSONs — the
    auto-import change-detection key. Empty string when the directory is
    absent/empty (nothing to import)."""
    import hashlib
    h = hashlib.sha256()
    try:
        files = sorted(dash_dir.glob("*.json"))
    except OSError:
        return ""
    if not files:
        return ""
    for p in files:
        try:
            h.update(p.name.encode("utf-8"))
            h.update(p.read_bytes())
        except OSError:
            return ""          # unreadable mid-deploy: skip this tick
    return h.hexdigest()


def _grafana_token_present() -> bool:
    if os.environ.get("GRAFANA_SA_TOKEN", "").strip():
        return True
    try:
        f = Path.home() / ".liquiditybot" / "grafana-sa-token"
        return f.is_file() and f.stat().st_size > 0
    except OSError:
        return False


_dash_no_token_warned = False


def _dash_import_due(dash_dir: Path = _DASH_DIR,
                     stamp: Path = _DASH_IMPORT_STAMP) -> str:
    """The dashboards' fingerprint when an import should run THIS tick
    (content changed since the last SUCCESSFUL import and a token is
    available), else "". The stamp is written by the import child on
    success, never here — a failed import stays due and retries under
    _spawn_gated's rate limit. A due import with NO token warns once per
    process instead of degrading silently (the boards would drift stale
    on Grafana with nothing in the log saying why)."""
    fp = _dash_fingerprint(dash_dir)
    if not fp:
        return ""
    try:
        if stamp.read_text(encoding="utf-8").strip() == fp:
            return ""
    except OSError:
        pass                   # no stamp yet -> first import is due
    if not _grafana_token_present():
        global _dash_no_token_warned
        if not _dash_no_token_warned:
            _dash_no_token_warned = True
            log("WARN: dashboards changed but no Grafana token found "
                "(GRAFANA_SA_TOKEN or ~/.liquiditybot/grafana-sa-token) - "
                "auto-import skipped; boards will drift until a token is "
                "provided")
        return ""
    return fp


def _corpus_sync_due() -> bool:
    """True when corpus_sync.py should run THIS tick: the normal hourly
    cadence (_stamp_due against _CORPUS_SYNC_STAMP), OR
    ml.history._ensure_schema left a rotation marker behind
    (_CORPUS_ROTATION_MARKER) - a schema-mismatch rotation that would
    otherwise sit near-empty for up to CORPUS_SYNC_SEC before recovery
    (corpus_sync.recover_local_baks) ever runs. See the marker's
    declaration above for the full rollout-hazard writeup.

    Self-clearing + idempotent: a present marker is consumed (unlinked)
    HERE, unconditionally, the instant it's observed - regardless of
    whether the spawn the caller makes afterward actually lands a live
    child. That mirrors every other stamp in this module (a failed spawn
    is invisible to us; the fallback is simply the normal cadence, no
    worse than before this marker existed) and guarantees a stale marker
    can never wedge into a tight loop: nothing re-creates it except a
    genuine NEW rotation. The caller gates this whole call behind
    LB_NO_CORPUS_SYNC (short-circuited, never invoked when the switch is
    set), so the kill switch cannot silently eat a pending marker - it
    simply waits, un-cleared, for the switch to lift.

    A marker hit also re-touches the cadence stamp (when it wasn't already
    due) so a rotation landing seconds before the hourly mark doesn't fire
    the sync twice back-to-back; harmless either way since the merge is
    idempotent, just wasted network. A MISSING marker never suppresses the
    normal cadence - the two conditions are OR'd, not coupled."""
    marker_hit = _CORPUS_ROTATION_MARKER.exists()
    cadence_due = _stamp_due(_CORPUS_SYNC_STAMP, CORPUS_SYNC_SEC)
    if not marker_hit:
        return cadence_due
    try:
        _CORPUS_ROTATION_MARKER.unlink()
    except OSError:
        pass
    if not cadence_due:
        try:
            OUT.mkdir(exist_ok=True)
            _CORPUS_SYNC_STAMP.touch()
        except OSError:
            pass
    return True


def _materialise_token() -> None:
    """Write GC_OTLP_TOKEN (if set) to ~/.liquiditybot/gc-token 0600 and point
    GC_TOKEN_FILE at it, so the pushers authenticate — same as the cloud hook."""
    tok = os.environ.get("GC_OTLP_TOKEN", "")
    if not tok:
        return
    d = Path.home() / ".liquiditybot"
    d.mkdir(exist_ok=True)
    f = d / "gc-token"
    try:
        f.write_text(tok, encoding="utf-8")
        if not IS_WIN:
            os.chmod(f, 0o600)
        os.environ.setdefault("GC_TOKEN_FILE", str(f))
    except OSError as e:
        log(f"token materialise failed: {e}")


def _telemetry_ready() -> bool:
    tf = os.environ.get("GC_TOKEN_FILE") or str(Path.home() / ".liquiditybot"
                                                / "gc-token")
    return (bool(os.environ.get("GC_OTLP_URL"))
            and bool(os.environ.get("GC_INSTANCE_ID"))
            and Path(tf).is_file() and Path(tf).stat().st_size > 0)


def _opend_cfg():
    """(enabled, exe_path, host, port) for the moomoo OpenD gateway, read from
    config.json's moomoo block. The exe path also honours the LB_OPEND_PATH env
    var (takes precedence) so it can be set without editing config."""
    path = os.environ.get("LB_OPEND_PATH", "")
    enabled, host, port = False, "127.0.0.1", 11111
    try:
        c = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        m = c.get("moomoo", {}) or {}
        enabled = bool(m.get("enabled", False))
        path = path or str(m.get("opend_path", "") or "")
        host = str(m.get("opend_host", host))
        port = int(m.get("opend_port", port))
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return enabled, path, host, port


def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _opend_relaunch_due() -> bool:
    try:
        return _stale_or_due(time.time() - _OPEND_STAMP.stat().st_mtime,
                             OPEND_RELAUNCH_SEC)
    except OSError:
        return True          # never launched -> due


def _launch_opend(path: str) -> None:
    """Launch OpenD windowless, from its OWN directory (it reads OpenD.xml
    there for headless login). GUI-login OpenD without a headless config will
    open a window and not serve the port — that is a moomoo-side setup, not
    ours. Same flag rationale as _spawn (no DETACHED_PROCESS)."""
    p = Path(path)
    kwargs: dict = {"cwd": str(p.parent)}
    if IS_WIN:
        kwargs["creationflags"] = 0x08000000 | 0x00000200
    else:
        kwargs["start_new_session"] = True
    try:
        with open(OUT / "opend.log", "a", encoding="utf-8") as out:
            subprocess.Popen([str(p)], stdout=out,        # nosec B603
                             stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, **kwargs)
    except OSError as e:
        log(f"OpenD launch failed: {e}")


def _run_quiet(argv: list, timeout: float = 60.0):
    """Run a short helper (schtasks) with a HIDDEN console; (rc, stdout)."""
    kwargs: dict = {}
    if IS_WIN:
        kwargs["creationflags"] = 0x08000000
    try:
        p = subprocess.run(argv, capture_output=True, text=True,  # nosec B603
                           timeout=timeout, **kwargs)
        return p.returncode, (p.stdout or "")
    except Exception as e:                       # noqa: BLE001
        return 1, f"error: {e}"


def migrate_legacy_tasks() -> str:
    """ONE-SHOT: re-register the runbook's pre-supervisor scheduled tasks so
    they stop popping consoles. 'Revival' ran console python.exe
    keepalive.py every 10 min (a visible flash per fire); 'Deep audit' ran
    run_checkin.bat under cmd.exe (a window for the whole checkin). Matched
    by ACTION CONTENT, never by name; the action is re-pointed at pythonw /
    the quiet wrapper with the SAME script and cadence — behavior preserved,
    window gone. Never deletes a task; any failure logs and moves on."""
    pyw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
    if not (IS_WIN and pyw.exists()):
        return "skipped"
    rc, out = _run_quiet(["schtasks", "/Query", "/FO", "CSV", "/V"])
    if rc != 0:
        log(f"task migration: schtasks query failed ({out[:120]})")
        return "query_failed"
    import csv as _csv
    import io as _io
    changed = 0
    for row in _csv.DictReader(_io.StringIO(out)):
        name = (row.get("TaskName") or "").strip()
        action = (row.get("Task To Run") or "")
        low = action.lower()
        if not name or name.lower() == "taskname":
            continue
        new_tr = None
        if "keepalive.py" in low and "pythonw" not in low:
            new_tr = f'"{pyw}" "{ROOT / "scripts" / "keepalive.py"}"'
        elif "run_checkin.bat" in low:
            # preserve the label argument the .bat received (e.g. "6h")
            label = action.rsplit(" ", 1)[-1].strip('"') \
                if " " in action.strip() else "6h"
            if label.lower().endswith(".bat"):
                label = "6h"
            new_tr = (f'"{pyw}" "{ROOT / "scripts" / "run_checkin_quiet.py"}"'
                      f' {label}')
        if new_tr is None:
            continue
        rc2, out2 = _run_quiet(["schtasks", "/Change", "/TN", name,
                                "/TR", new_tr])
        if rc2 == 0:
            changed += 1
            log(f"task migration: {name!r} re-registered windowless")
        else:
            log(f"task migration: {name!r} change failed ({out2[:120]})")
    return f"migrated={changed}"


def _maybe_launch_opend() -> str:
    """Ensure a LOCAL moomoo OpenD is running (optional). Returns an outcome
    string (also handy for tests). Only a local OpenD can be launched from here;
    a remote one lives on another machine. Throttled (OPEND_RELAUNCH_SEC) so a
    GUI-login OpenD that never opens its port isn't relaunched every tick."""
    en, opend, host, port = _opend_cfg()
    if not (en and opend):
        return "disabled"                    # off, or no path set -> nothing to do
    if host not in ("127.0.0.1", "localhost", "::1"):
        return "remote"                      # can't manage OpenD on another host
    if _port_open(host, port):
        return "up"
    if not _opend_relaunch_due():
        return "throttled"
    _OPEND_STAMP.parent.mkdir(exist_ok=True)
    _OPEND_STAMP.touch()                      # throttle regardless of outcome
    if not Path(opend).exists():
        log(f"OpenD enabled but exe not found at {opend!r} - set "
            f"moomoo.opend_path (or LB_OPEND_PATH)")
        return "missing"
    log(f"OpenD not listening on {host}:{port} -> launching {opend}")
    _launch_opend(opend)
    return "launched"


def tick() -> None:
    # 1) runner — the bot itself (boot-grace gated: one spawn per window,
    # however long the stale heartbeat lingers while the child boots)
    if not _fresh(OUT / "status.json", key="written_at") and \
            _spawn_gated("runner", [PY, "runner.py"]):
        log("runner stale/absent -> relaunching")
    # 2) telemetry pushers (optional; only if a token is configured)
    if _telemetry_ready():
        if not _fresh(OUT / "gc_pusher.log") and \
                _spawn_gated("gc_pusher", [PY, "scripts/gc_pusher.py"]):
            log("metrics pusher stale/absent -> relaunching")
        if not _fresh(OUT / "gc_log_pusher.log") and \
                _spawn_gated("gc_log_pusher",
                             [PY, "scripts/gc_log_pusher.py"]):
            log("log pusher stale/absent -> relaunching")
        if not _fresh(OUT / "gc_trace_pusher.log") and \
                _spawn_gated("gc_trace_pusher",
                             [PY, "scripts/gc_trace_pusher.py"]):
            log("trace pusher stale/absent -> relaunching")
    # 3) moomoo OpenD data gateway (optional): start it with the bot and keep it
    # alive. moomoo is a read-only optional feed — a failure here never affects
    # trading.
    _maybe_launch_opend()

    # 4) test-gated self-update (opt-in cadence; disabled by LB_NO_AUTO_UPDATE).
    # auto_update.py tests origin/main in an isolated worktree and only fast-
    # forwards if the battery is green, then signals a stop so we relaunch on the
    # new code. Detached: a 20-min battery must never block liveness checks.
    if _auto_update_due():
        log("auto-update check due -> spawning test-gated updater")
        _mark_update_checked()
        _spawn([PY, "scripts/auto_update.py"], own_log=False)

    # 5) one-bot remote control: apply queued operator commands from the
    # durable branch, and publish the full status back. Both directions are
    # short-lived detached child processes with their own log
    # (outputs/remote_control.log) and their own fail-safe error handling.
    if (not os.environ.get("LB_NO_REMOTE_CMD")
            and _stamp_due(_REMOTE_CMD_STAMP, REMOTE_CMD_SEC)):
        _spawn([PY, "scripts/remote_control.py", "--poll"], own_log=False)
    if (not os.environ.get("LB_NO_STATUS_PUSH")
            and _stamp_due(_STATUS_PUSH_STAMP, STATUS_PUSH_SEC)):
        _spawn([PY, "scripts/remote_control.py", "--push-status"],
               own_log=False)
    if (not os.environ.get("LB_NO_CORPUS_SYNC")
            and _corpus_sync_due()):
        _spawn([PY, "scripts/corpus_sync.py"], own_log=False)
    # corpus EXPORT: the PC is THE bot, so ITS file is the canonical
    # learning corpus — checkpoint it durably under its own label (the
    # cloud sidecar's mirror bundle must never shadow this one)
    if (not os.environ.get("LB_NO_TELEM_BACKUP")
            and _stamp_due(_TELEM_BACKUP_STAMP, TELEM_BACKUP_SEC)):
        _spawn([PY, "scripts/telemetry_backup.py", "--once",
                "--label", "pc-live"])

    # 5b) ONE-SHOT window sweep: close DEAD Command Prompt windows the
    # pre-popup-fix code left on the desktop (polite first; force + the
    # Windows-Terminal fallback only for runner-signature shells; evidence
    # in outputs/prompt_sweep.log). FAIL CLOSED: the sweep spawns ONLY
    # after the stamp provably exists on disk — an unwritable outputs/
    # (ACL drift, disk full) must skip the sweep entirely, never turn a
    # one-shot into an every-30s loop against the operator's prompts.
    if IS_WIN and not _PROMPT_SWEEP_STAMP.exists():
        try:
            OUT.mkdir(exist_ok=True)
            _PROMPT_SWEEP_STAMP.touch()      # stamp FIRST, spawn only if it
            stamped = _PROMPT_SWEEP_STAMP.exists()   # actually landed
        except OSError as e:
            stamped = False
            log(f"prompt sweep skipped: stamp unwritable ({e})")
        if stamped:
            log("one-shot prompt sweep -> closing dead Command Prompt windows")
            _spawn(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "scripts" / "close_prompts.ps1")],
                   own_log=False)

    # 5c) ONE-SHOT legacy-task migration: re-register the runbook's console
    # scheduled tasks (keepalive / run_checkin.bat) windowless — the source
    # of the every-10-min console flash. Same fail-closed stamp contract.
    if IS_WIN and not _TASK_MIGRATE_STAMP.exists():
        try:
            OUT.mkdir(exist_ok=True)
            _TASK_MIGRATE_STAMP.touch()
            stamped = _TASK_MIGRATE_STAMP.exists()
        except OSError as e:
            stamped = False
            log(f"task migration skipped: stamp unwritable ({e})")
        if stamped:
            log(f"legacy-task migration: {migrate_legacy_tasks()}")

    # 6) self-restart on source change: the auto-updater bounces the RUNNER,
    # but this process would keep the pre-update supervisor in memory until
    # the next reboot (observed live 2026-07-17: new tick steps sat dormant).
    # When our own file changes on disk, hand over to a fresh copy and exit.
    # The lock is RELEASED FIRST so the replacement can acquire it cleanly —
    # the pre-lock handoff spawned a task-UNtracked copy that Task Scheduler
    # could not see, so IgnoreNew/RestartOnFailure/logon each added another
    # (observed live 2026-07-22: TWO full supervisor+runner stacks, the
    # source of the audit trail's concurrent-writer seams).
    if _source_changed():
        log("pc_supervisor.py changed on disk -> restarting on the new code")
        if _LOCK is not None:
            _LOCK.release()
        _spawn([PY, str(_SELF)])
        raise SystemExit(0)

    # 7) dashboard auto-import: deploy-changed docs/grafana/*.json reach
    # Grafana Cloud without operator hands whenever a token is available
    # (see _DASH_IMPORT_STAMP block comment). Cheap per tick (one sha256
    # over four small files); the actual HTTP import is a short-lived
    # detached child rate-limited by _spawn_gated. Deliberately AFTER the
    # step-6 handoff (tests/test_pc_supervisor_lock.py pins the handoff's
    # release-then-spawn as the ONLY actions on a restart tick): a
    # mid-deploy tick restarts onto the new code first and the fresh
    # supervisor imports on its first tick - never boards that are about
    # to change again.
    if not os.environ.get("LB_NO_DASH_IMPORT"):
        _dash_fp = _dash_import_due()
        if _dash_fp and _spawn_gated(
                "dash_import",
                [PY, "scripts/grafana_import.py",
                 "--stamp", str(_DASH_IMPORT_STAMP),
                 "--fingerprint", _dash_fp], own_log=True):
            log("dashboards changed + Grafana token present -> importing")


def _source_changed() -> bool:
    """True when scripts/pc_supervisor.py's mtime moved since import (and
    the file still exists non-empty — a half-written file must not trigger
    a handover to a broken copy)."""
    try:
        st = _SELF.stat()
        return st.st_size > 0 and abs(st.st_mtime - _SELF_MTIME) > 1e-6
    except OSError:
        return False


# single-instance lock: only ONE supervisor may drive an outputs/ dir, no
# matter how it was launched (Task Scheduler, RestartOnFailure, the source-
# change handoff, restart.bat, a manual start). Task Scheduler's IgnoreNew
# only dedups instances IT started — the handoff spawns a detached copy the
# task cannot see, so every OS-level path was adding a second full stack
# (2x supervisor -> 2x runner -> audit writer-seam forks). Same hardened
# heartbeat lock the runner uses; stale_after matches STALE_SEC so a crashed
# supervisor is replaced within one liveness window.
_LOCK: SingleInstanceLock | None = None
LOCK_POLL_SEC = 5.0        # heartbeat-watch cadence while another lock exists


def _acquire_or_wait(lock: SingleInstanceLock,
                     poll_sec: float = 5.0) -> bool:
    """True when WE end up holding the lock; False only against a peer that
    is PROVABLY alive (its heartbeat MOVED while we watched).

    Exit-on-sight refusal had a liveness hole: a force-killed supervisor
    leaves a frozen-but-recent heartbeat, so any relaunch inside the stale
    window (Task Scheduler's 1-min RestartOnFailure, a quick manual start)
    saw a "live" peer, refused with rc 0, and Task Scheduler read the clean
    exit as success — leaving NO supervisor at all until a human noticed
    (observed live 2026-07-21 ~22:02). A dead pid cannot advance its
    heartbeat, so movement — not age — is the only honest liveness signal:
    frozen past the stale window -> take over; advancing -> genuine double
    -> back off."""
    holder = lock.acquire()
    if holder is None:
        return True
    last_hb = float(holder.get("heartbeat", 0) or 0)
    deadline = time.time() + lock.stale_after + 2 * poll_sec
    log(f"supervisor lock held by pid {holder.get('pid')} — watching its "
        f"heartbeat for up to {lock.stale_after + 2 * poll_sec:.0f}s")
    while time.time() < deadline:
        time.sleep(poll_sec)
        cur = read_json(lock.path)
        hb = float(cur.get("heartbeat", 0) or 0) \
            if isinstance(cur, dict) else 0.0
        if hb > last_hb + 1e-6:
            return False                    # heartbeat MOVED: live peer
        if lock.acquire() is None:          # stale/vanished -> reclaimed
            return True
    return lock.acquire() is None           # final verdict at the deadline


def _stagger_stamps() -> None:
    """C-F10: the four git sidecars (remote-cmd poll, status push, corpus
    sync, telemetry backup) are all stamp-gated and all default-due on a
    fresh boot, and their periods share divisors (600 | 3600) — so every
    hour the whole set fires on ONE tick and contends for git/network at
    once. Seed ABSENT stamps with phase offsets (fractions of each period)
    so the cadences interleave; periods are unchanged, so the phase holds
    forever after. Existing stamps are never touched."""
    for stamp, period, frac in (
            (_REMOTE_CMD_STAMP, REMOTE_CMD_SEC, 0.0),      # due immediately
            (_STATUS_PUSH_STAMP, STATUS_PUSH_SEC, 0.5),
            (_CORPUS_SYNC_STAMP, CORPUS_SYNC_SEC, 0.25),
            (_TELEM_BACKUP_STAMP, TELEM_BACKUP_SEC, 0.75)):
        if stamp.exists():
            continue
        try:
            OUT.mkdir(exist_ok=True)
            stamp.touch()
            age = period * (1.0 - frac)      # first due after frac*period
            os.utime(stamp, (time.time() - age, time.time() - age))
        except OSError:
            pass                             # stagger is best-effort


def _guarded_iteration() -> bool:
    """ONE supervisor loop iteration under the never-die-silently contract.

    2026-08-16 incident: pid 15160 (Task Scheduler, pythonw) exited 1 five
    minutes after logon with NOTHING in its own log, and the task's job
    object took the runner and all three pushers down within one heartbeat
    - a gate whose failure killed the thing it guards. The old loop guarded
    tick() but ran `_LOCK.refresh()` OUTSIDE the try, so any raise there
    (e.g. a decode error off a corrupt lock file) was an instant silent
    death: under pythonw an unhandled traceback goes nowhere. Now BOTH are
    guarded, exceptions log their FULL traceback, and the loop continues.
    Returns False only for the one legitimate exit here (lock forfeited to
    a live peer). The source-change handoff's SystemExit propagates
    untouched - tests/test_pc_supervisor_lock.py pins that contract."""
    try:
        tick()
    except SystemExit:
        raise                                    # handoff already released
    except Exception:                            # fail-safe: never wedge
        log(f"tick error (continuing):\n{traceback.format_exc()}")
    try:
        if not _LOCK.refresh() and _LOCK.forfeited:  # type: ignore[union-attr]
            log("lost the supervisor lock to a live peer — exiting")
            return False                         # peer owns outputs/ now
    except Exception:                            # the old silent-death path
        log(f"lock refresh error (continuing):\n{traceback.format_exc()}")
    return True


def main() -> None:
    global _LOCK
    _stagger_stamps()
    _LOCK = SingleInstanceLock(path=str(OUT / "pc_supervisor.lock"),
                               stale_after_sec=STALE_SEC)
    if not _acquire_or_wait(_LOCK, poll_sec=LOCK_POLL_SEC):
        log("another supervisor is live (heartbeat advancing) — "
            "refusing to double, exiting")
        return
    log(f"start (python={PY}, check={CHECK_SEC:.0f}s, stale={STALE_SEC:.0f}s, "
        f"lock pid={os.getpid()})")
    log(f"job status: {_job_status()}")
    _materialise_token()
    if not _telemetry_ready():
        log("no GC_OTLP_URL/GC_INSTANCE_ID/token — running bot only, no push")
    try:
        while True:
            if not _guarded_iteration():
                return
            time.sleep(CHECK_SEC)
    finally:
        _LOCK.release()                              # ownership-aware: never
                                                     # deletes a peer's lock


_EXIT_HOOKS_ARMED = False


def _arm_exit_forensics() -> None:
    """atexit + faulthandler so this process can no longer END without a
    trace. Every Python-level exit (return, sys.exit, unhandled exception)
    now appends a 'process exit' line; faulthandler catches native-level
    deaths (access violations) into pc_supervisor_fault.log. The
    contrapositive is the forensic payoff the 2026-08-16 incident lacked:
    a dead supervisor whose log has NO exit line was killed from OUTSIDE
    python (TerminateProcess / power) - previously indistinguishable from
    a silent crash. The log path is captured at arm time so the atexit
    write lands where THIS process actually logged."""
    global _EXIT_HOOKS_ARMED
    if _EXIT_HOOKS_ARMED:
        return
    _EXIT_HOOKS_ARMED = True
    path = LOG_PATH

    def _log_exit() -> None:
        line = (f"{time.strftime('%Y-%m-%d %H:%M:%S')} pc_supervisor: "
                f"process exit (pid {os.getpid()})")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass
    atexit.register(_log_exit)
    try:
        import faulthandler
        faulthandler.enable(
            open(path.with_name("pc_supervisor_fault.log"),  # noqa: SIM115
                 "a", encoding="utf-8"))   # handle lives for the process
    except Exception as e:                # noqa: BLE001 - forensics only
        log(f"faulthandler not armed ({e}) - native-crash forensics off")


def _main_guarded() -> int:
    """Exit-proof top level (2026-08-16): under pythonw an unhandled
    exception's traceback ceases to exist and the process just vanishes
    with rc 1 - then Task Scheduler tears down the job and the whole stack
    goes dark. Every death path now logs before the process ends. The exit
    code contract is unchanged: unhandled -> 1, Ctrl+C -> 0, the
    source-change handoff -> its own SystemExit code."""
    _arm_exit_forensics()
    try:
        main()
        return 0
    except KeyboardInterrupt:
        return 0
    except SystemExit as e:                      # handoff: reason already logged
        if isinstance(e.code, int):
            return e.code
        return 0 if e.code is None else 1
    except BaseException:                        # noqa: BLE001 - last resort
        log(f"FATAL: unhandled exception — exiting 1:\n"
            f"{traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    sys.exit(_main_guarded())
