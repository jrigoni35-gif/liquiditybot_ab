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
error logs one line and retries next tick; the bot never depends on this.

Telemetry token: materialised once from the GC_OTLP_TOKEN env var (set it as a
Windows user environment variable) into ~/.liquiditybot/gc-token, matching the
cloud hook — so the pushers find it without a token ever entering git.

Run it directly to test (Ctrl+C to stop); Task Scheduler runs it via
scripts/run_hidden.vbs at logon.
"""
import json
import os
import socket
import subprocess  # nosec B404 - fixed argv, no shell
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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
_CORPUS_SYNC_STAMP = OUT / ".corpus_sync_stamp"
# moomoo OpenD gateway: relaunch throttle. A GUI-login OpenD that never opens
# its port must NOT be relaunched every tick (that stacks login windows), so a
# launch attempt is spaced at least this far apart regardless of outcome.
try:
    OPEND_RELAUNCH_SEC = float(os.environ.get("LB_OPEND_RELAUNCH_SEC", "300"))
except ValueError:
    OPEND_RELAUNCH_SEC = 300.0
_OPEND_STAMP = OUT / ".opend_launch_stamp"
IS_WIN = os.name == "nt"
PY = sys.executable        # the venv's python (pythonw.exe when run hidden)
_SELF = Path(__file__).resolve()
try:
    _SELF_MTIME = _SELF.stat().st_mtime
except OSError:
    _SELF_MTIME = 0.0


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} pc_supervisor: {msg}"
    print(line, flush=True)
    try:
        OUT.mkdir(exist_ok=True)
        with open(OUT / "pc_supervisor.log", "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


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
        return (time.time() - ts) < STALE_SEC
    except (OSError, ValueError, TypeError):
        return False


def _spawn(argv: list, own_log: bool = True) -> None:
    """Launch a detached, WINDOWLESS child that outlives this process. When
    own_log is False the child keeps its own log file, so stdout goes to
    DEVNULL (avoids double-writing every line)."""
    kwargs: dict = {"cwd": str(ROOT)}
    if IS_WIN:
        # DETACHED_PROCESS | CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        kwargs["creationflags"] = 0x00000008 | 0x08000000 | 0x00000200
    else:
        kwargs["start_new_session"] = True          # setsid-equivalent
    out = (open(OUT / (Path(argv[1]).stem + ".log"), "a", encoding="utf-8")
           if own_log else subprocess.DEVNULL)
    subprocess.Popen(argv, stdout=out, stderr=subprocess.STDOUT,  # nosec B603
                     stdin=subprocess.DEVNULL, **kwargs)


def _auto_update_due() -> bool:
    """True when a test-gated self-update check is due (never run, or older than
    UPDATE_SEC). Off entirely when LB_NO_AUTO_UPDATE is set."""
    if os.environ.get("LB_NO_AUTO_UPDATE"):
        return False
    try:
        return (time.time() - _UPDATE_STAMP.stat().st_mtime) >= UPDATE_SEC
    except OSError:
        return True          # no stamp yet -> due (check once on first boot)


def _mark_update_checked() -> None:
    try:
        OUT.mkdir(exist_ok=True)
        _UPDATE_STAMP.touch()
    except OSError:
        pass


def _stamp_due(stamp: Path, period_sec: float) -> bool:
    """True when `stamp` is absent or older than period_sec; touches it on
    True so each caller runs at most once per period (same contract as the
    auto-update stamp, generalized)."""
    try:
        if (time.time() - stamp.stat().st_mtime) < period_sec:
            return False
    except OSError:
        pass                       # no stamp yet -> due
    try:
        OUT.mkdir(exist_ok=True)
        stamp.touch()
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
        return (time.time() - _OPEND_STAMP.stat().st_mtime) >= OPEND_RELAUNCH_SEC
    except OSError:
        return True          # never launched -> due


def _launch_opend(path: str) -> None:
    """Launch OpenD detached, from its OWN directory (it reads OpenD.xml there
    for headless login). GUI-login OpenD without a headless config will open a
    window and not serve the port — that is a moomoo-side setup, not ours."""
    p = Path(path)
    kwargs: dict = {"cwd": str(p.parent)}
    if IS_WIN:
        kwargs["creationflags"] = 0x00000008 | 0x08000000 | 0x00000200
    else:
        kwargs["start_new_session"] = True
    try:
        with open(OUT / "opend.log", "a", encoding="utf-8") as out:
            subprocess.Popen([str(p)], stdout=out,        # nosec B603
                             stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, **kwargs)
    except OSError as e:
        log(f"OpenD launch failed: {e}")


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
    # 1) runner — the bot itself
    if not _fresh(OUT / "status.json", key="written_at"):
        log("runner stale/absent -> relaunching")
        _spawn([PY, "runner.py"])
    # 2) telemetry pushers (optional; only if a token is configured)
    if _telemetry_ready():
        if not _fresh(OUT / "gc_pusher.log"):
            log("metrics pusher stale/absent -> relaunching")
            _spawn([PY, "scripts/gc_pusher.py"])
        if not _fresh(OUT / "gc_log_pusher.log"):
            log("log pusher stale/absent -> relaunching")
            _spawn([PY, "scripts/gc_log_pusher.py"])
        if not _fresh(OUT / "gc_trace_pusher.log"):
            log("trace pusher stale/absent -> relaunching")
            _spawn([PY, "scripts/gc_trace_pusher.py"])
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
            and _stamp_due(_CORPUS_SYNC_STAMP, CORPUS_SYNC_SEC)):
        _spawn([PY, "scripts/corpus_sync.py"], own_log=False)

    # 6) self-restart on source change: the auto-updater bounces the RUNNER,
    # but this process would keep the pre-update supervisor in memory until
    # the next reboot (observed live 2026-07-17: new tick steps sat dormant).
    # When our own file changes on disk, hand over to a fresh copy and exit —
    # children are detached and survive; the brief two-supervisor overlap is
    # harmless (relaunches are heartbeat-gated, the updater holds a lock).
    if _source_changed():
        log("pc_supervisor.py changed on disk -> restarting on the new code")
        _spawn([PY, str(_SELF)])
        raise SystemExit(0)


def _source_changed() -> bool:
    """True when scripts/pc_supervisor.py's mtime moved since import (and
    the file still exists non-empty — a half-written file must not trigger
    a handover to a broken copy)."""
    try:
        st = _SELF.stat()
        return st.st_size > 0 and abs(st.st_mtime - _SELF_MTIME) > 1e-6
    except OSError:
        return False


def main() -> None:
    log(f"start (python={PY}, check={CHECK_SEC:.0f}s, stale={STALE_SEC:.0f}s)")
    _materialise_token()
    if not _telemetry_ready():
        log("no GC_OTLP_URL/GC_INSTANCE_ID/token — running bot only, no push")
    while True:
        try:
            tick()
        except Exception as e:                       # fail-safe: never wedge
            log(f"tick error (continuing): {e}")
        time.sleep(CHECK_SEC)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
