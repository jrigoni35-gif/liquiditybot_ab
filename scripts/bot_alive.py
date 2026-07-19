"""Exit 0 if the bot is already running, exit 1 if not.

Liveness is heartbeat-based, identical to pc_supervisor's own check: the runner
rewrites outputs/status.json every cycle, so a 'written_at' fresher than
STALE_SEC means a bot is live (whether it runs hidden under the LiquidityBot
scheduled task or in a visible start.bat window). No psutil, no command-line
scraping.

Used by start.bat to REFUSE opening a second console when a bot is already up —
that refusal is the fix for the stacked-cmd-window cascade (every extra
start.bat used to leave a dead `cmd /k` shell behind). scripts/tidy_windows.ps1
reuses it to confirm the bot survived a window cleanup.
"""
import json
import sys
import time
from pathlib import Path

STALE_SEC = 120.0          # matches pc_supervisor.STALE_SEC
ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "outputs" / "status.json"


def is_alive(now: float | None = None, stale_sec: float = STALE_SEC) -> bool:
    """True when status.json carries a heartbeat newer than stale_sec."""
    ref = time.time() if now is None else now
    try:
        ts = float(json.loads(STATUS.read_text(encoding="utf-8"))
                   .get("written_at", 0.0))
    except (OSError, ValueError, TypeError):
        return False
    return (ref - ts) < stale_sec


if __name__ == "__main__":
    sys.exit(0 if is_alive() else 1)
