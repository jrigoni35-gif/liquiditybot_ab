"""Stacked-console-window regression guard.

The visible-window cascade on the PC was repeated start.bat launches: each ran
`cmd /k python runner.py`, the SingleInstanceLock refused the duplicate engine,
but `cmd /k` left the empty shell open. The fix: start.bat asks bot_alive.py
first and refuses to open a window when a bot is already up; tidy_windows.*
clears any pile that already accumulated. These tests pin that behavior.
"""
import json
from pathlib import Path

import scripts.bot_alive as ba

ROOT = Path(__file__).resolve().parents[1]


def _write_status(tmp_path, written_at):
    p = tmp_path / "status.json"
    p.write_text(json.dumps({"written_at": written_at}), encoding="utf-8")
    return p


def test_is_alive_true_for_fresh_heartbeat(tmp_path, monkeypatch):
    monkeypatch.setattr(ba, "STATUS", _write_status(tmp_path, 1_000.0))
    assert ba.is_alive(now=1_030.0) is True          # 30s old < 120s


def test_is_alive_false_for_stale_heartbeat(tmp_path, monkeypatch):
    monkeypatch.setattr(ba, "STATUS", _write_status(tmp_path, 1_000.0))
    assert ba.is_alive(now=1_200.0) is False         # 200s old > 120s


def test_is_alive_false_when_status_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(ba, "STATUS", tmp_path / "nope.json")
    assert ba.is_alive(now=1_000.0) is False


def test_is_alive_false_on_garbage_status(tmp_path, monkeypatch):
    p = tmp_path / "status.json"
    p.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(ba, "STATUS", p)
    assert ba.is_alive(now=1_000.0) is False


def test_is_alive_boundary_matches_supervisor_stale_sec():
    # Contract with pc_supervisor.STALE_SEC=120: the launcher and the
    # supervisor must agree on what "alive" means.
    assert ba.STALE_SEC == 120.0


def test_start_bat_refuses_second_window_when_alive():
    txt = (ROOT / "start.bat").read_text(encoding="utf-8")
    # the guard must run bot_alive.py and short-circuit BEFORE the `start` line
    assert "scripts\\bot_alive.py" in txt
    guard = txt.index("bot_alive.py")
    launch = txt.index('start "liquiditybot-runner"')
    assert guard < launch, "alive-check must precede the window launch"
    assert "if not errorlevel 1" in txt          # errorlevel 0 == alive == skip


def test_tidy_windows_scripts_exist_and_are_safe():
    ps1 = (ROOT / "scripts" / "tidy_windows.ps1").read_text(encoding="utf-8")
    bat = (ROOT / "scripts" / "tidy_windows.bat").read_text(encoding="utf-8")
    # ensures the headless supervisor is up before closing anything
    assert "LiquidityBot" in ps1 and "bot_alive.py" in ps1
    assert "CloseMainWindow" in ps1
    # only targets liquiditybot-titled windows, never a blanket python kill
    assert "*liquiditybot*" in ps1
    assert "tidy_windows.ps1" in bat
