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
        # DETACHED_PROCESS must NEVER ride along: per CreateProcess docs it
        # wins over CREATE_NO_WINDOW, leaving the child console-LESS so any
        # unflagged grandchild pops a VISIBLE console — the exact bug class
        assert "0x00000008" not in src \
            and "subprocess.DETACHED_PROCESS" not in src, (
                f"{name}: DETACHED_PROCESS would defeat CREATE_NO_WINDOW")
        for lineno, block in _call_blocks(src):
            assert "_NOWIN" in block or "creationflags" in block, (
                f"scripts/{name}:{lineno} subprocess call without the "
                f"no-window flag — on Windows this pops a console window "
                f"per call under the headless supervisor")


def test_supervisor_and_keepalive_spawn_windowless():
    sup = (ROOT / "scripts" / "pc_supervisor.py").read_text(encoding="utf-8")
    ka = (ROOT / "scripts" / "keepalive.py").read_text(encoding="utf-8")
    # hidden console (inherited by the whole child tree), NEVER
    # DETACHED_PROCESS (which wins over CREATE_NO_WINDOW and leaves the
    # child console-less -> unflagged grandchildren pop visible consoles)
    assert "0x08000000" in sup
    # the FLAG itself must be gone (comments may explain why it's banned)
    assert "0x00000008" not in sup
    assert "subprocess.DETACHED_PROCESS" not in sup
    assert "CREATE_NO_WINDOW" in ka
    assert "subprocess.DETACHED_PROCESS" not in ka


def test_prompt_sweep_is_one_shot_dead_only():
    """The deployed close-dead-prompts sweep must be stamp-gated to exactly
    one run, FAIL CLOSED when the stamp cannot be written (never an every-
    tick loop against the operator's prompts), target ONLY dead cmd shells,
    fail SAFE on child enumeration errors, close politely before any force,
    scope the force to runner-signature shells, and leave evidence."""
    sup = (ROOT / "scripts" / "pc_supervisor.py").read_text(encoding="utf-8")
    assert "_PROMPT_SWEEP_STAMP" in sup
    assert ".prompt_sweep_done2" in sup
    # fail-closed: the spawn is gated on the stamp PROVABLY existing
    assert "stamped = _PROMPT_SWEEP_STAMP.exists()" in sup
    assert "if stamped:" in sup
    ps1 = (ROOT / "scripts" / "close_prompts.ps1").read_text(encoding="utf-8")
    assert "ParentProcessId" in ps1                      # dead = no children
    assert "-ErrorAction Stop" in ps1 and "catch" in ps1  # fail-safe CIM
    assert "CloseMainWindow" in ps1                      # polite first
    assert ps1.index("CloseMainWindow") < ps1.index("Stop-Process")
    # the force rung is scoped to the runner signature, never arbitrary
    assert "RUNNER_SIG" in ps1 and "runner\\.py" in ps1
    assert "MainWindowTitle" in ps1        # the WT/never-shown discriminator
    assert "prompt_sweep.log" in ps1       # evidence, never a silent no-op
    assert "-Name cmd" in ps1                            # classic cmd only
    # never targets terminal apps (the process name has no space)
    assert "WindowsTerminal" not in ps1
    # PS 5.1 only: no PowerShell-7-only null-coalescing operator
    assert "??" not in ps1


def test_legacy_task_migration_is_one_shot_and_windowless():
    """The runbook's pre-supervisor scheduled tasks (console python.exe
    keepalive / run_checkin.bat under cmd.exe) were the recurring popups.
    The migration must be stamp-gated + fail-closed, match by ACTION
    content (never by task name), re-register — never delete — and the
    replacement actions must run under pythonw / the quiet wrapper."""
    sup = (ROOT / "scripts" / "pc_supervisor.py").read_text(encoding="utf-8")
    assert "_TASK_MIGRATE_STAMP" in sup and ".task_migrate_done" in sup
    assert "stamped = _TASK_MIGRATE_STAMP.exists()" in sup
    assert "migrate_legacy_tasks" in sup
    assert "/Change" in sup and "/Delete" not in sup     # re-register only
    assert "keepalive.py" in sup and "run_checkin.bat" in sup
    assert "pythonw.exe" in sup
    # the quiet checkin wrapper exists and stays windowless itself
    quiet = (ROOT / "scripts" / "run_checkin_quiet.py").read_text(
        encoding="utf-8")
    assert "_NOWIN" in quiet and "0x08000000" in quiet
    assert "checkin_run.log" in quiet      # preserves the .bat's trace
