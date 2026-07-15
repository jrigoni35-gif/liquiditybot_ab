"""
scripts/auto_update.py — test-gated self-update for the always-on PC bot.

The operator can't always git-pull the PC by hand (away from home). This pulls
origin/main and redeploys — but ONLY if the INCOMING code passes the full test
battery first, so a bad commit can never reach the live trading bot. Run by
pc_supervisor.py on a slow cadence (default daily), or by hand:
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
import os
import subprocess  # nosec B404 - fixed argv, no shell
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
BRANCH = "main"


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
    tail = (p.stdout or "").strip().splitlines()[-1:] or ["(no output)"]
    log(f"incoming-code battery rc={p.returncode}: {tail[0]}")
    return p.returncode == 0


def _signal_restart() -> None:
    """Graceful stop so the supervisor relaunches the runner on the new code."""
    try:
        sys.path.insert(0, str(ROOT))
        from core.runtime import ControlChannel
        ControlChannel(str(OUT / "control")).send("stop")
        log("sent stop - supervisor will relaunch on the new code")
    except Exception as e:                        # noqa: BLE001
        log(f"restart signal failed ({e}) - new code loads on the next restart")


def update_once() -> str:
    """One update attempt. Returns the outcome string."""
    if os.environ.get("LB_NO_AUTO_UPDATE"):
        return "disabled"
    rc, _ = _git("fetch", "origin", BRANCH, timeout=120)
    if rc != 0:
        log("git fetch failed - skipping (offline?)")
        return "fetch_failed"
    _, local = _git("rev-parse", "HEAD")
    _, remote = _git("rev-parse", f"origin/{BRANCH}")
    _, porcelain = _git("status", "--porcelain")
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
    wt = OUT / f"_update_wt_{os.getpid()}"
    _git("worktree", "remove", "--force", str(wt))     # clean any stale one
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
    raise SystemExit(0 if update_once() in
                     ("updated", "current", "dirty", "disabled") else 1)
