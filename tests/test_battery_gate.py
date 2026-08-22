"""The battery's pytest stage gate must actually bite (2026-08-08).

FOUND LIVE: `start /b /wait "" cmd || (...)` NEVER fires the `||` -
start's own successful LAUNCH satisfies the conditional; the awaited
child's exit code lands only in ERRORLEVEL. A red pytest stage
(1 failed, 3444 passed) sailed through to ALL GREEN - the first false
arm this matrix ever produced. Every earlier "failed" battery was
caught by a LATER stage whose engine broke on the same bugs, which is
why the lie survived every prior red run.

Two pins:
  1. The cmd semantics themselves (subprocess, two-sided): `||` misses
     an exit-1 child behind start /wait; `if errorlevel 1` catches it.
     If a future Windows changes this, the pin tells us.
  2. test_windows.bat never combines `start /b /wait` with `||` on one
     line - the construct is banned in the matrix (same spirit as the
     AST append-mode gate: the CLASS is fenced, not the instance).
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

_BAT = Path(__file__).resolve().parents[1] / "test_windows.bat"

# The three cmd-semantics pins below execute `cmd.exe`. Windows is the
# target runtime and they run there; on a Linux analyst box they FAILED
# with FileNotFoundError, which reads identically to the defect they
# guard — a false red that trains the reader to ignore the battery.
# Skipped off-Windows, never skipped ON Windows, so the pin keeps its
# whole force where the battery actually gates. The static pin below
# (test_matrix_splits_timing_family_into_a_serial_pass) reads the .bat as
# text and runs everywhere.
_needs_cmd = pytest.mark.skipif(
    os.name != "nt", reason="pins Windows cmd.exe semantics; cmd.exe absent")


def _run_bat(tmp_path: Path, body: str) -> int:
    """Run the construct from a REAL .bat file: `cmd /c "start ..."`
    inline deadlocks under captured pipes (the quote layers make start
    mis-parse and wait forever - measured 60s TimeoutExpired x3 on the
    first version of these pins), while the identical construct inside
    a .bat file completes instantly. The battery is a .bat, so the
    file form is also the faithful reproduction."""
    bat = tmp_path / "gate_pin.bat"
    bat.write_text("@echo off\r\n" + body + "\r\n", encoding="ascii")
    return subprocess.run(
        ["cmd.exe", "/d", "/c", str(bat)], capture_output=True,
        timeout=60).returncode  # nosec B603 B607 - fixed argv, no shell


@_needs_cmd
def test_start_wait_or_operator_misses_child_failure(tmp_path):
    """The defect, pinned: || after start /b /wait sees the LAUNCH, not
    the child - an exit-1 child yields outer exit 0."""
    rc = _run_bat(tmp_path,
                  f'start /b /wait "" "{sys.executable}" -c '
                  f'"import sys; sys.exit(1)" || exit /b 7')
    assert rc == 0, ("cmd's || now sees the awaited child's code - "
                     "revisit the matrix gates with this new semantics")


@_needs_cmd
def test_if_errorlevel_catches_child_failure(tmp_path):
    """The fix, pinned: if errorlevel 1 reads the awaited child's code."""
    rc = _run_bat(tmp_path,
                  f'start /b /wait "" "{sys.executable}" -c '
                  f'"import sys; sys.exit(1)"\r\n'
                  f'if errorlevel 1 exit /b 7')
    assert rc == 7


@_needs_cmd
def test_if_errorlevel_passes_child_success(tmp_path):
    rc = _run_bat(tmp_path,
                  f'start /b /wait "" "{sys.executable}" -c '
                  f'"import sys; sys.exit(0)"\r\n'
                  f'if errorlevel 1 exit /b 7')
    assert rc == 0


def test_matrix_splits_timing_family_into_a_serial_pass():
    """Owed item 44 (2026-08-08): once the gate above became honest, a
    rotating one-red-per-battery family surfaced - wall-clock-sensitive
    tests failing purely from -n 8 saturation. The matrix must run
    exactly two pytest passes: parallel xdist EXCLUDING @timing, then a
    serial pass of ONLY @timing on the quiet machine - each behind its
    own `if errorlevel 1` gate so neither can lie."""
    lines = _BAT.read_text(encoding="utf-8").splitlines()
    idx = [i for i, ln in enumerate(lines)
           if "-m pytest tests" in ln
           and not ln.strip().upper().startswith("REM")]
    assert len(idx) == 2, (
        "expected exactly two pytest passes (parallel + serial timing), "
        f"found {len(idx)}")
    par, ser = lines[idx[0]], lines[idx[1]]
    assert "-n 8" in par and '-m "not timing"' in par, (
        "parallel pass must keep xdist and exclude the timing family: "
        f"{par.strip()}")
    assert "-m timing" in ser and " -n " not in f"{ser} ", (
        "timing pass must select the family and stay SERIAL (no xdist): "
        f"{ser.strip()}")
    for i in idx:
        nxt = next(ln.strip() for ln in lines[i + 1:] if ln.strip())
        assert nxt.lower().startswith("if errorlevel 1"), (
            f"pytest pass at line {i + 1} is not gated by the honest "
            f"`if errorlevel 1` form; next line: {nxt}")


def test_no_bat_file_pairs_start_wait_with_or_operator():
    """No batch file in the repo may gate a start /wait child with || -
    the ban is class-wide (2026-08-08 sweep: exactly one live instance
    existed, in the matrix; auto_update's deploy gate was verified
    honest - subprocess.run + returncode, no cmd involved)."""
    for bat in sorted(_BAT.parent.glob("*.bat")):
        for i, line in enumerate(
                bat.read_text(encoding="utf-8",
                              errors="replace").splitlines(), 1):
            s = line.strip()
            if s.upper().startswith("REM"):
                continue
            assert not ("start" in s and "/wait" in s and "||" in s), (
                f"{bat.name}:{i} gates a start /wait child with || - "
                f"that gate can never fire; use `if errorlevel 1`")
