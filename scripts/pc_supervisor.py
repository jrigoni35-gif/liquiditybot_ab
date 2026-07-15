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
import os
import subprocess  # nosec B404 - fixed argv, no shell
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
CHECK_SEC = 30.0
STALE_SEC = 120.0          # a heartbeat older than this = process is gone
# test-gated self-update cadence: how often to check origin/main for new code.
# Default daily; LB_NO_AUTO_UPDATE=1 disables it entirely (checked here AND in
# auto_update.py, so either gate turns it fully off).
try:
    UPDATE_SEC = float(os.environ.get("LB_AUTO_UPDATE_SEC", "86400"))
except ValueError:
    UPDATE_SEC = 86400.0
_UPDATE_STAMP = OUT / ".auto_update_stamp"
IS_WIN = os.name == "nt"
PY = sys.executable        # the venv's python (pythonw.exe when run hidden)


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
    # 3) test-gated self-update (opt-in cadence; disabled by LB_NO_AUTO_UPDATE).
    # auto_update.py tests origin/main in an isolated worktree and only fast-
    # forwards if the battery is green, then signals a stop so we relaunch on the
    # new code. Detached: a 20-min battery must never block liveness checks.
    if _auto_update_due():
        log("auto-update check due -> spawning test-gated updater")
        _mark_update_checked()
        _spawn([PY, "scripts/auto_update.py"], own_log=False)


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
