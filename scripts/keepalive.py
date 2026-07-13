"""
scripts/keepalive.py — revive a dead runner (Task Scheduler, ~10 min).

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
import subprocess  # nosec B404 - fixed argv relaunch of our own runner
import sys
import time
from pathlib import Path

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
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    flags = (subprocess.DETACHED_PROCESS
             | subprocess.CREATE_NEW_PROCESS_GROUP)
    subprocess.Popen(  # nosec B603 - fixed argv, repo-local interpreter
        [str(py), "runner.py"], cwd=str(ROOT), creationflags=flags,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL, close_fds=True)
    print(f"RELAUNCHED runner: status stale {status_age:.0f}s, lock "
          f"stale {lock_age:.0f}s (snapshot resume; SingleInstanceLock "
          f"guards against races)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
