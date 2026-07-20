"""
scripts/keepalive.py — revive a dead runner (Task Scheduler / cron, ~10 min).

Operator contract: the sentinel file outputs/keepalive.on ARMS this
script. Delete the sentinel before an intentional long stop, or the bot
revives within one scheduler period. All checks are read-only; a
relaunch uses the same detached pattern as manual launches, and the
runner's own SingleInstanceLock makes a double-launch race harmless
(the loser refuses and exits).

Liveness = either signal fresh: status.json written_at, or the runner
lockfile heartbeat (refreshed every cycle). Both stale -> relaunch.
"""
import json
import os
import subprocess  # nosec B404 - fixed argv relaunch of our own runner
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SENTINEL = ROOT / "outputs" / "keepalive.on"
STATUS_STALE_SEC = 900.0     # status normally refreshes every cycle (~5s)
LOCK_STALE_SEC = 60.0        # heartbeat refreshes every cycle too


def _age(path: Path, key: str) -> float:
    try:
        v = json.loads(path.read_text(encoding="utf-8")).get(key, 0)
        return time.time() - float(v or 0)
    except (OSError, ValueError, TypeError):
        return float("inf")


def relaunch_interpreter() -> Path:
    """The repo venv's python for THIS platform (the original hardcoded
    Windows layout broke revival on macOS/Linux), falling back to the
    interpreter running keepalive itself if no venv exists."""
    py = ROOT / (".venv/Scripts/python.exe" if os.name == "nt"
                 else ".venv/bin/python")
    return py if py.exists() else Path(sys.executable)


def main() -> int:
    if not SENTINEL.exists():
        print("keepalive disarmed (outputs/keepalive.on absent)")
        return 0
    status_age = _age(ROOT / "outputs" / "status.json", "written_at")
    lock_age = _age(ROOT / "outputs" / "runner.lock", "heartbeat")
    if status_age < STATUS_STALE_SEC or lock_age < LOCK_STALE_SEC:
        print(f"runner alive (status {status_age:.0f}s, "
              f"lock heartbeat {lock_age:.0f}s)")
        return 0
    py = relaunch_interpreter()
    # detach per-OS: Windows wants its own process group/console flags,
    # POSIX wants a new session so scheduler/terminal signals never reach
    # the revived runner. Same detach contract, both platforms.
    # CREATE_NO_WINDOW (hidden console the whole child tree inherits), NOT
    # DETACHED_PROCESS: per CreateProcess docs the two are mutually exclusive
    # and DETACHED wins, leaving the child console-LESS — any unflagged
    # console-subsystem grandchild would then pop a visible window.
    detach: dict[str, Any] = (
        {"creationflags": (subprocess.CREATE_NO_WINDOW
                           | subprocess.CREATE_NEW_PROCESS_GROUP)}
        if os.name == "nt" else {"start_new_session": True})
    subprocess.Popen(  # nosec B603 - fixed argv, repo-local interpreter
        [str(py), "runner.py"], cwd=str(ROOT),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL, close_fds=True, **detach)
    print(f"RELAUNCHED runner: status stale {status_age:.0f}s, lock "
          f"stale {lock_age:.0f}s (snapshot resume; SingleInstanceLock "
          f"guards against races)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
