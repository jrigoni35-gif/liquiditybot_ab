"""
Regression for the ControlChannel command vocabulary.

force_dry (the one-way LIVE->DRY seal, hard invariant #2) was handled by
runner.handle_command and wired to a dashboard button, but missing from
VALID_COMMANDS - so ControlChannel.send() raised in the UI and a
hand-dropped command file was silently discarded by consume(). The
safety path was dead. These tests pin the fix and add a parity guard so
no command the dashboard sends can fall out of the vocabulary again.
"""
import re
from pathlib import Path

from core.runtime import VALID_COMMANDS, ControlChannel

REPO = Path(__file__).resolve().parents[1]


def test_force_dry_is_a_valid_command():
    assert "force_dry" in VALID_COMMANDS


def test_force_dry_survives_send_consume_round_trip(tmp_path):
    ch = ControlChannel(str(tmp_path / "control"))
    ch.send("force_dry")
    cmds = ch.consume()
    assert [c["cmd"] for c in cmds] == ["force_dry"]


def test_every_dashboard_command_is_valid():
    src = (REPO / "ui" / "dashboard.py").read_text(encoding="utf-8")
    sent = set(re.findall(r'control\.send\(\s*"([a-z_]+)"', src))
    assert sent, "dashboard no longer sends commands? update this test"
    unknown = sent - VALID_COMMANDS
    assert not unknown, (
        f"dashboard sends {sorted(unknown)} but VALID_COMMANDS omits them - "
        f"send() will raise and consume() drops hand-written files")
