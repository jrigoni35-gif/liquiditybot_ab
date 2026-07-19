"""Stacked-console-window regression guard.

The visible-window cascade on the PC was repeated start.bat launches: each ran
`cmd /k python runner.py`, the SingleInstanceLock refused the duplicate engine,
but `cmd /k` left the empty shell open. The fixes:
  * start.bat asks bot_alive.py first and refuses a window when a bot is up;
  * bot_alive keys on the SingleInstanceLock heartbeat (authoritative, exists
    the instant the runner starts) so the double-click race can't stack a
    window and a crashed runner is never read as "alive";
  * tidy_windows.ps1 closes ONLY dead 'liquiditybot-runner' shells (no python
    child), never the live bot and never an unrelated window.
"""
import json
from pathlib import Path

import scripts.bot_alive as ba
import scripts.pc_supervisor as sup

ROOT = Path(__file__).resolve().parents[1]


def _patch(monkeypatch, tmp_path, lock=None, status=None):
    """Point bot_alive at temp lock/status files; force the lock window to its
    floor (30s) by aiming CONFIG at a nonexistent path."""
    lp, sp = tmp_path / "runner.lock", tmp_path / "status.json"
    if lock is not None:
        lp.write_text(json.dumps(lock), encoding="utf-8")
    if status is not None:
        sp.write_text(json.dumps(status), encoding="utf-8")
    monkeypatch.setattr(ba, "LOCK", lp)
    monkeypatch.setattr(ba, "STATUS", sp)
    monkeypatch.setattr(ba, "CONFIG", tmp_path / "noconfig.json")   # -> 30s floor


# ---- lock is authoritative -------------------------------------------------
def test_alive_when_lock_heartbeat_fresh(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path, lock={"pid": 1, "heartbeat": 1_000.0})
    assert ba.is_alive(now=1_020.0) is True          # 20s < 30s floor


def test_dead_when_lock_stale_even_if_status_fresh(tmp_path, monkeypatch):
    # crashed 40s ago: lock stale (>30s) but status.json still 5s old. The lock
    # must win, else start.bat refuses to relaunch a genuinely-dead bot (M1).
    _patch(monkeypatch, tmp_path,
           lock={"pid": 1, "heartbeat": 1_000.0},
           status={"written_at": 1_035.0})
    assert ba.is_alive(now=1_040.0) is False


def test_future_dated_lock_reads_alive(tmp_path, monkeypatch):
    # clock skew / mid-write: a future heartbeat is fresh, never stale (L1).
    _patch(monkeypatch, tmp_path, lock={"pid": 1, "heartbeat": 1_050.0})
    assert ba.is_alive(now=1_000.0) is True


# ---- status.json fallback (no lock file) -----------------------------------
def test_status_fallback_fresh(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path, status={"written_at": 1_000.0})  # no lock
    assert ba.is_alive(now=1_030.0) is True          # 30s < 120s


def test_status_fallback_stale(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path, status={"written_at": 1_000.0})
    assert ba.is_alive(now=1_200.0) is False         # 200s > 120s


def test_dead_when_nothing_present(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)                     # neither file
    assert ba.is_alive(now=1_000.0) is False


def test_garbage_files_are_not_alive(tmp_path, monkeypatch):
    lp, sp = tmp_path / "runner.lock", tmp_path / "status.json"
    lp.write_text("{broken", encoding="utf-8")
    sp.write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(ba, "LOCK", lp)
    monkeypatch.setattr(ba, "STATUS", sp)
    monkeypatch.setattr(ba, "CONFIG", tmp_path / "noconfig.json")
    assert ba.is_alive(now=1_000.0) is False


def test_stale_window_matches_supervisor():
    # the fallback window must track pc_supervisor's, not a drifting literal
    assert ba.STALE_SEC == sup.STALE_SEC


def test_lock_window_mirrors_runner_formula():
    # floor is the SingleInstanceLock default; the config path scales it
    assert ba._lock_stale_sec() >= ba.LOCK_STALE_FLOOR == 30.0


# ---- launcher scripts pin the hardened contract ----------------------------
def test_start_bat_refuses_second_window_when_alive():
    txt = (ROOT / "start.bat").read_text(encoding="utf-8")
    assert "scripts\\bot_alive.py" in txt
    guard = txt.index("bot_alive.py")
    launch = txt.index('start "liquiditybot-runner"')
    assert guard < launch, "alive-check must precede the window launch"
    assert "if not errorlevel 1" in txt          # errorlevel 0 == alive == skip


def test_tidy_windows_targets_only_dead_runner_shells():
    ps1 = (ROOT / "scripts" / "tidy_windows.ps1").read_text(encoding="utf-8")
    bat = (ROOT / "scripts" / "tidy_windows.bat").read_text(encoding="utf-8")
    # exact runner title, never the folder-name substring that would hit VS Code
    assert "-like '*liquiditybot-runner*'" in ps1
    assert "-like '*liquiditybot*'" not in ps1     # never the folder-name match
    assert "-Name cmd" in ps1                     # restricted to cmd hosts
    assert "$_.Id -ne $self" in ps1               # never its own console
    assert "ParentProcessId" in ps1               # keeps windows with a py child
    assert "taskkill" in ps1                      # tree-kill dead shells only
    # fail SAFE on a CIM enumeration error: never read an error as "no child"
    assert "-ErrorAction Stop" in ps1 and "catch" in ps1
    assert "$queryOk" in ps1
    # the cleaner must NOT silently convert a manual user to headless autostart
    assert "install_autostart.ps1" not in ps1
    assert "tidy_windows.ps1" in bat
