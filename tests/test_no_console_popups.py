"""No-console-popup invariant for the PC-side sidecars.

pc_supervisor spawns its sidecars WINDOWLESS (CREATE_NO_WINDOW). On Windows,
a console-subsystem child (git.exe, python.exe) of a console-LESS parent gets
a brand-new console window allocated per call unless CREATE_NO_WINDOW is
passed — observed live 2026-07-19 as "command centers repeatedly popping up":
remote_control's 120s git poll, corpus_sync/telemetry_backup's hourly git,
auto_update's git poll + lingering pytest battery window. Every subprocess
call in these scripts must therefore carry the no-window flag.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# every PC-side script that shells out (pc_supervisor passes explicit
# creationflags already; keepalive builds its own detach dict)
SIDECARS = ("remote_control.py", "corpus_sync.py", "telemetry_backup.py",
            "auto_update.py")

_CALL = re.compile(r"subprocess\.(run|Popen|check_output|check_call|call)\(")


def _call_blocks(src: str):
    """Yield (lineno, text) for each subprocess call with ~6 lines of its
    argument context (enough to see the flags/kwargs)."""
    lines = src.splitlines()
    for i, ln in enumerate(lines):
        if _CALL.search(ln):
            yield i + 1, "\n".join(lines[i:i + 7])


def test_every_sidecar_subprocess_call_is_windowless():
    for name in SIDECARS:
        src = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "_NOWIN" in src, f"{name}: missing the _NOWIN declaration"
        assert "0x08000000" in src, f"{name}: CREATE_NO_WINDOW flag absent"
        for lineno, block in _call_blocks(src):
            assert "_NOWIN" in block or "creationflags" in block, (
                f"scripts/{name}:{lineno} subprocess call without the "
                f"no-window flag — on Windows this pops a console window "
                f"per call under the headless supervisor")


def test_supervisor_and_keepalive_spawn_windowless():
    sup = (ROOT / "scripts" / "pc_supervisor.py").read_text(encoding="utf-8")
    # DETACHED_PROCESS | CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    assert "0x08000000" in sup
    ka = (ROOT / "scripts" / "keepalive.py").read_text(encoding="utf-8")
    assert "CREATE_NO_WINDOW" in ka
