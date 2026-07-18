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


def _git(*args, cwd=None, timeout=120):
    """Run a git command; return (rc, stdout.strip()). Never raises."""
    try:
        p = subprocess.run(["git", *args], cwd=str(cwd or ROOT),  # nosec B603 B607
                           capture_output=True, text=True, timeout=timeout)
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
                           timeout=1200)
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


def _signal_restart() -> None:
    """Graceful stop so the supervisor relaunches the runner on the new code."""
    try:
        from core.runtime import ControlChannel
        ControlChannel(str(OUT / "control")).send("stop")
        log("sent stop - supervisor will relaunch on the new code")
    except Exception as e:                        # noqa: BLE001
        log(f"restart signal failed ({e}) - new code loads on the next restart")


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
    raise SystemExit(0 if update_once() in OK_OUTCOMES else 1)
