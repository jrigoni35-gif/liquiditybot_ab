"""
scripts/auto_update.py — test-gated self-update for the always-on PC bot.

The operator can't always git-pull the PC by hand (away from home). This pulls
origin/main and redeploys — but ONLY if the INCOMING code passes the full test
battery first, so a bad commit can never reach the live trading bot. Run by
pc_supervisor.py every LB_AUTO_UPDATE_SEC (default 15 min — the check is a
bare fetch+compare; the heavy battery only runs when main actually moved, so
a push lands on the PC within minutes), or by hand:
    python scripts/auto_update.py

Safety rules (why this is safe to run unattended against a live paper bot):
  * NEVER updates across local uncommitted changes — that would clobber operator
    config edits (e.g. the debug flag). Dirty tree -> log and skip.
  * Tests the INCOMING code in an ISOLATED git worktree BEFORE fast-forwarding.
    A red battery aborts the update; the bot stays on the known-good code.
  * Fast-forward ONLY (never a merge/rebase that could conflict). After the
    fast-forward it signals a graceful runner stop (ControlChannel), so the
    supervisor relaunches on the new code.
  * Every decision logs one line; any error is caught and the bot is left
    exactly as it was. Disable entirely with LB_NO_AUTO_UPDATE=1.
"""
import json
import os
import subprocess  # nosec B404 - fixed argv, no shell
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.runtime import SingleInstanceLock  # noqa: E402

OUT = ROOT / "outputs"
BRANCH = "main"
# One updater at a time: the supervisor's fast cadence plus a manual run could
# otherwise stack two 20-min batteries and race the fast-forward. Staleness
# must outlive the worst case (1200s battery + worktree/git ops) with margin.
LOCK_STALE_SEC = 2700.0
# Outcomes that exit 0 ("nothing wrong"), vs real failures that exit 1.
OK_OUTCOMES = ("updated", "current", "dirty", "disabled", "busy")


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} auto_update: {msg}"
    print(line, flush=True)
    try:
        OUT.mkdir(exist_ok=True)
        with open(OUT / "auto_update.log", "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


# Windows: children of the WINDOWLESS supervisor spawn otherwise pop a new
# console window per call ("command centers") — for this script that meant a
# git window every poll AND a lingering pytest window per battery run.
_NOWIN = {"creationflags": 0x08000000} if os.name == "nt" else {}


def _git(*args, cwd=None, timeout=120):
    """Run a git command; return (rc, stdout.strip()). Never raises."""
    try:
        p = subprocess.run(["git", *args], cwd=str(cwd or ROOT),  # nosec B603 B607
                           capture_output=True, text=True, timeout=timeout,
                           **_NOWIN)
        return p.returncode, (p.stdout or "").strip()
    except Exception as e:                       # noqa: BLE001
        return 1, f"error: {e}"


def _venv_python() -> str:
    """The repo venv's interpreter (Windows Scripts / POSIX bin), or the
    current one as a fallback."""
    for rel in (".venv/Scripts/python.exe", ".venv/bin/python"):
        p = ROOT / rel
        if p.exists():
            return str(p)
    return sys.executable


def decide(local: str, remote: str, dirty: bool) -> str:
    """Pure decision (unit-testable): 'current' (nothing to do), 'dirty' (local
    edits, skip), or 'test' (new code -> gate on the battery)."""
    if not remote or remote == local:
        return "current"
    if dirty:
        return "dirty"
    return "test"


def battery_passes(worktree: Path) -> bool:
    """Run the test battery against the INCOMING code in an isolated worktree.
    Green is required before the update is allowed to touch the live checkout."""
    py = _venv_python()
    try:
        p = subprocess.run([py, "-m", "pytest", "tests/", "-q",  # nosec B603
                            "-x", "--no-header"],
                           cwd=str(worktree), capture_output=True, text=True,
                           timeout=1200, **_NOWIN)
    except Exception as e:                       # noqa: BLE001
        log(f"battery could not run ({e}) - refusing the update")
        return False
    lines = (p.stdout or "").strip().splitlines()
    tail = lines[-1:] or ["(no output)"]
    log(f"incoming-code battery rc={p.returncode}: {tail[0]}")
    if p.returncode != 0:
        # capture the FAILED lines (pytest -x stops at the first) so the
        # deploy observable can name WHICH test rejected the update off-box
        # — otherwise a Windows-only failure is invisible from the cloud
        # (lived 2026-07-18: the PC rejected every update on a CRLF test
        # and nothing said which). Bounded so the stamp stays small.
        failed = [ln for ln in lines if ln.startswith("FAILED")][:3]
        global _BATTERY_DETAIL
        _BATTERY_DETAIL = " | ".join(failed) or tail[0]
    return p.returncode == 0


# Deploy-restart escalation: a graceful 'stop' asks the runner to exit so the
# supervisor relaunches it on new code. If the runner's command consumption is
# wedged (seen live 2026-07-21: a long-lived runner ignored every 'stop', so the
# repo advanced but the process kept running stale code), force-kill ITS pid
# after a grace window so the deploy actually lands. Disable with
# LB_NO_FORCE_KILL_RESTART=1.
_FORCE_KILL_STUCK = os.environ.get("LB_NO_FORCE_KILL_RESTART") != "1"
_FORCE_KILL_AFTER_SEC = float(os.environ.get("LB_FORCE_KILL_AFTER_SEC", "45"))
_FORCE_KILL_POLL_SEC = 5.0


def _runner_pid():
    """The live runner's pid from its SingleInstanceLock, or None."""
    try:
        d = json.loads((OUT / "runner.lock").read_text(encoding="utf-8"))
        pid = d.get("pid")
        return pid if isinstance(pid, int) else None
    except (OSError, ValueError, TypeError):
        return None


def _should_escalate(orig_pid, cur_pid) -> bool:
    """Force-kill ONLY when the SAME pid still holds the lock after the grace
    window (the soft stop was ignored). A changed or absent pid means the runner
    already exited/relaunched — leave it alone."""
    return orig_pid is not None and cur_pid == orig_pid


def _force_kill(pid) -> None:
    """Kill one pid, cross-platform, fail-safe (never raises into the deploy)."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/PID", str(int(pid))],  # nosec B603 B607
                           timeout=30, capture_output=True, **_NOWIN)
        else:
            import signal as _signal
            os.kill(int(pid), _signal.SIGKILL)
        log(f"force-killed stuck runner pid {pid} - supervisor relaunches on new code")
    except Exception as e:                        # noqa: BLE001 - fail-safe
        log(f"force-kill of pid {pid} failed ({e})")


def _escalate_if_stuck(orig_pid, read_pid, wait_sec, poll_sec, kill_fn,
                       sleep_fn=time.sleep, now_fn=time.time) -> str:
    """Wait out the grace window; force-kill iff the same runner pid survives it.
    Injectable timing/readers so the decision is unit-testable without sleeping.
    Returns 'no_pid' | 'restarted' | 'force_killed'."""
    if orig_pid is None:
        return "no_pid"
    deadline = now_fn() + wait_sec
    while now_fn() < deadline:
        sleep_fn(poll_sec)
        if not _should_escalate(orig_pid, read_pid()):
            return "restarted"
    kill_fn(orig_pid)
    return "force_killed"


def _signal_restart() -> None:
    """Graceful stop so the supervisor relaunches the runner on the new code;
    escalate to a targeted force-kill if the runner ignores the soft stop."""
    orig_pid = _runner_pid()
    try:
        from core.runtime import ControlChannel
        ControlChannel(str(OUT / "control")).send("stop")
        log("sent stop - supervisor will relaunch on the new code")
    except Exception as e:                        # noqa: BLE001
        log(f"restart signal failed ({e}) - new code loads on the next restart")
    if not _FORCE_KILL_STUCK:
        return
    outcome = _escalate_if_stuck(orig_pid, _runner_pid, _FORCE_KILL_AFTER_SEC,
                                 _FORCE_KILL_POLL_SEC, _force_kill)
    if outcome == "no_pid":
        log("no runner.lock pid to watch - relying on the supervisor's "
            "stale-heartbeat relaunch")
    elif outcome == "restarted":
        log("runner exited on the soft stop - clean restart")


_BATTERY_DETAIL = ""            # failing-test detail from the last battery run


def _record_outcome(outcome: str) -> None:
    """Persist the last attempt's outcome + revs to a small JSON stamp the
    status push publishes (outputs/auto_update_state.json). Found live
    2026-07-18: the updater silently failed for 6+ hours (outcome unknown
    — dirty? rejected? ff_failed?) and NOTHING observable off-box said
    which; the PC's deploy state was a blind spot. Fail-safe: never let
    telemetry break the update itself. On a 'rejected' outcome the stamp
    also carries which test(s) failed the battery, so a Windows-only
    failure is diagnosable from the cloud."""
    try:
        _, head = _git("rev-parse", "--short", "HEAD")
        _, remote = _git("rev-parse", "--short", f"origin/{BRANCH}")
        state = {"ts": time.time(), "outcome": outcome,
                 "head": head.strip(), "remote": remote.strip()}
        if outcome == "rejected" and _BATTERY_DETAIL:
            state["battery_detail"] = _BATTERY_DETAIL[:500]
        p = OUT / "auto_update_state.json"
        tmp = p.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(state), encoding="utf-8")
        os.replace(tmp, p)
    except Exception as e:                        # noqa: BLE001
        log(f"outcome stamp failed ({e}) - update itself unaffected")


def _ensure_pushers_current() -> None:
    """Telemetry sidecars only reload code when THEY restart - the update
    restart signal reaches the runner alone, so long-lived pushers kept
    exporting a pre-deploy gauge set forever (lived 2026-07-20: the
    profit-pools row was 'No data' all day while the runner carried the
    values). This process is spawned FRESH every cadence, so it always
    runs current code: when the deployed rev differs from the marker,
    best-effort stop the pusher processes and let the supervisor's
    stale-heartbeat check relaunch them on the new code. The pushers also
    self-exit on source change now; this is the migration path for
    processes started before that guard existed, and the backstop.
    Fail-safe throughout: a failed bounce only means stale gauges."""
    try:
        _, head = _git("rev-parse", "--short", "HEAD")
        marker = OUT / "pushers_code_rev.txt"
        try:
            if marker.read_text(encoding="utf-8").strip() == head.strip():
                return
        except OSError:
            pass                              # no marker yet -> bounce once
        if os.name == "nt":
            ps = ("Get-CimInstance Win32_Process | Where-Object "
                  "{ $_.CommandLine -match "
                  "'gc_pusher\\.py|gc_log_pusher\\.py|gc_trace_pusher\\.py' }"
                  " | ForEach-Object "
                  "{ Stop-Process -Id $_.ProcessId -Force "
                  "-ErrorAction SilentlyContinue }")
            subprocess.run(["powershell", "-NoProfile",  # nosec B603 B607
                            "-Command", ps], timeout=90,
                           capture_output=True, **_NOWIN)
            log(f"pushers bounced for rev {head.strip()} - supervisor "
                f"relaunches them on the deployed code")
        marker.write_text(head.strip() + "\n", encoding="utf-8")
    except Exception as e:                        # noqa: BLE001
        log(f"pusher bounce failed ({e}) - gauges may lag one deploy")


def update_once() -> str:
    """One update attempt. Returns the outcome string."""
    if os.environ.get("LB_NO_AUTO_UPDATE"):
        return "disabled"
    lock = SingleInstanceLock(str(OUT / "auto_update.lock"),
                              stale_after_sec=LOCK_STALE_SEC)
    holder = lock.acquire()
    if holder is not None:
        log(f"another updater already running (pid {holder.get('pid')}) - "
            f"skipping this check")
        return "busy"
    try:
        out = _update_locked()
    finally:
        lock.release()
    _record_outcome(out)
    return out


def _update_locked() -> str:
    """The update body; caller holds the single-updater lock."""
    rc, _ = _git("fetch", "origin", BRANCH, timeout=120)
    if rc != 0:
        log("git fetch failed - skipping (offline?)")
        return "fetch_failed"
    _, local = _git("rev-parse", "HEAD")
    _, remote = _git("rev-parse", f"origin/{BRANCH}")
    # --untracked-files=no: only TRACKED modifications are operator edits a
    # fast-forward could clobber. Untracked files (e.g. a .claude/skills/
    # dir the desktop app drops) blocked updates forever — and git stash
    # can't even clear them, so the operator had no way out (live 2026-07-17).
    _, porcelain = _git("status", "--porcelain", "--untracked-files=no")
    action = decide(local, remote, bool(porcelain.strip()))
    if action == "current":
        log("already up to date")
        return "current"
    if action == "dirty":
        log("local uncommitted changes present - NOT auto-updating (your edits "
            "are safe); pull by hand when ready")
        return "dirty"

    _, behind = _git("rev-list", "--count", f"HEAD..origin/{BRANCH}")
    log(f"{behind} new commit(s) on {BRANCH} - testing the incoming code first")
    # reclaim EVERY stale _update_wt_* (any pid): a crashed updater's full
    # checkout otherwise sat under outputs/ forever — `worktree prune` skips
    # it because the directory exists (audit C-F11). Concurrent updaters are
    # excluded by the single-updater lock, so anything here is dead.
    for stale_wt in OUT.glob("_update_wt_*"):
        _git("worktree", "remove", "--force", str(stale_wt))
    wt = OUT / f"_update_wt_{os.getpid()}"
    rc, err = _git("worktree", "add", "--detach", str(wt), f"origin/{BRANCH}")
    if rc != 0:
        log(f"could not create test worktree ({err}) - skipping")
        return "worktree_failed"
    try:
        ok = battery_passes(wt)
    finally:
        _git("worktree", "remove", "--force", str(wt))
    if not ok:
        log("incoming code FAILED the battery - staying on current code")
        return "rejected"
    rc, err = _git("merge", "--ff-only", f"origin/{BRANCH}")
    if rc != 0:
        log(f"fast-forward failed ({err}) - not updated")
        return "ff_failed"
    log(f"updated {local[:8]} -> {remote[:8]} (battery-verified)")
    _signal_restart()
    return "updated"


if __name__ == "__main__":
    _outcome = update_once()
    # after the update body (including a just-applied fast-forward), make
    # sure the telemetry sidecars run the code that is now deployed
    _ensure_pushers_current()
    raise SystemExit(0 if _outcome in OK_OUTCOMES else 1)
