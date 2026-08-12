"""Windowless replacement for scripts/run_checkin.bat.

The legacy Task Scheduler 'Deep audit' entry ran run_checkin.bat, and a
scheduled .bat executes under a visible cmd.exe console for the whole
checkin. This wrapper replicates the .bat exactly (label argument, append
console output to outputs/checkin/checkin_run.log, exit-code trace) but is
registered under pythonw.exe, so no window ever appears. pc_supervisor's
one-shot legacy-task migration re-points the scheduled action here.
"""
import os
import subprocess  # nosec B404 - fixed argv, no shell
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "outputs" / "checkin"
LOG = LOG_DIR / "checkin_run.log"
# CREATE_NO_WINDOW as a plain int (0 is the POSIX no-op) passed as
# creationflags= — a **dict unpack untyped the subprocess.run call.
_NOWIN = 0x08000000 if os.name == "nt" else 0


def main() -> int:
    label = sys.argv[1] if len(sys.argv) > 1 else ""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        if not label:
            fh.write("run_checkin_quiet: missing label argument\n")
            return 1
        fh.write(f"\n==== {time.strftime('%Y-%m-%d %H:%M:%S')} : checkin "
                 f"label={label} (quiet) ====\n")
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    argv = [str(py) if py.exists() else sys.executable,
            str(ROOT / "scripts" / "checkin.py"), "--label", label]
    env = dict(os.environ, PYTHONUTF8="1")
    with open(LOG, "a", encoding="utf-8") as fh:
        p = subprocess.run(argv, cwd=str(ROOT), stdout=fh,  # nosec B603
                           stderr=subprocess.STDOUT, env=env,
                           creationflags=_NOWIN)
        fh.write(f"exit code {p.returncode}\n")
    return p.returncode


if __name__ == "__main__":
    sys.exit(main())
