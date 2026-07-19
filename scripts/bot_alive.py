"""Exit 0 if the bot is already running, exit 1 if not.

The authoritative signal is the runner's SingleInstanceLock heartbeat
(outputs/runner.lock, a JSON {pid, heartbeat}). The lock exists the INSTANT a
runner starts — before status.json is first written — and is refreshed every
cycle, so gating start.bat on it (not on status.json):

  * closes the double-click race — a second start.bat fired in the seconds
    before the first runner writes status.json would otherwise see "not
    running", open a window, and leave a dead `cmd /k` shell (the very
    cascade the guard exists to prevent);
  * matches the runner's OWN staleness window (max(polling*5, 30)s), so the
    guard can't false-positive a runner that crashed 40s ago as "alive" and
    refuse to relaunch it.

Fallback: if the lock file is absent/unreadable, use the status.json heartbeat
(written_at younger than STALE_SEC) so a lockless/legacy run still reads right.

Exit 0 = a bot is up (start.bat then refuses to open another window).
"""
import json
import sys
import time
from pathlib import Path

STALE_SEC = 120.0          # status.json fallback window (== pc_supervisor.STALE_SEC)
LOCK_STALE_FLOOR = 30.0    # == SingleInstanceLock default stale_after_sec
ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "outputs" / "status.json"
LOCK = ROOT / "outputs" / "runner.lock"
CONFIG = ROOT / "config.json"


def _lock_stale_sec() -> float:
    """Mirror runner.py's lock window: max(polling_interval_sec*5, 30). A live
    runner heartbeats every cycle (~polling_interval), so it never approaches
    this; only a crashed one crosses it. Fail-safe to the floor."""
    try:
        poll = float(json.loads(CONFIG.read_text(encoding="utf-8"))
                     .get("system", {}).get("polling_interval_sec", 5.0))
        return max(poll * 5.0, LOCK_STALE_FLOOR)
    except (OSError, ValueError, TypeError, AttributeError):
        return LOCK_STALE_FLOOR


def _fresh(path: Path, key: str, window: float, ref: float):
    """None if the file is absent/unreadable/missing the key; else True when
    the epoch at `key` is within `window` of `ref`. A future-dated stamp
    (clock skew or a mid-write file) counts as fresh, never as stale."""
    try:
        ts = float(json.loads(path.read_text(encoding="utf-8")).get(key))
    except (OSError, ValueError, TypeError):
        return None
    return (ref - ts) < window          # negative age (future) -> fresh


def is_alive(now: float | None = None) -> bool:
    """True when a runner is up. The lock heartbeat is authoritative; status.json
    is consulted only when the lock file is absent."""
    ref = time.time() if now is None else now
    lock = _fresh(LOCK, "heartbeat", _lock_stale_sec(), ref)
    if lock is not None:
        return lock              # lock present -> it alone decides
    return bool(_fresh(STATUS, "written_at", STALE_SEC, ref))


if __name__ == "__main__":
    sys.exit(0 if is_alive() else 1)
