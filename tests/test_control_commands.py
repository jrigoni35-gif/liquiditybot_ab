"""
Regression for the ControlChannel command vocabulary.

force_dry (the one-way LIVE->DRY seal, hard invariant #2) was handled by
runner.handle_command but was once missing from VALID_COMMANDS - so
ControlChannel.send() raised and a hand-dropped command file was silently
discarded by consume(). The safety path was dead. These tests pin the fix
and add a parity guard so no command a SENDER emits can fall out of the
vocabulary. The command sender is now the git remote-control plane
(scripts/remote_control.py, REMOTE_SAFE_COMMANDS) — the legacy Streamlit UI
that used to carry the buttons is retired.
"""
from core.runtime import VALID_COMMANDS, ControlChannel


def test_force_dry_is_a_valid_command():
    assert "force_dry" in VALID_COMMANDS


def test_force_dry_survives_send_consume_round_trip(tmp_path):
    ch = ControlChannel(str(tmp_path / "control"))
    ch.send("force_dry")
    cmds = ch.consume()
    assert [c["cmd"] for c in cmds] == ["force_dry"]


def test_every_remote_command_is_valid():
    """Every command the remote-control plane can send must be in the runner's
    vocabulary, or ControlChannel.send() raises and consume() drops the file
    (the exact dead-safety-path regression this suite was born for)."""
    from scripts.remote_control import REMOTE_SAFE_COMMANDS
    assert REMOTE_SAFE_COMMANDS, "remote plane sends nothing? update this test"
    unknown = REMOTE_SAFE_COMMANDS - VALID_COMMANDS
    assert not unknown, (
        f"remote plane sends {sorted(unknown)} but VALID_COMMANDS omits them - "
        f"send() will raise and consume() drops the queued file")


def test_arm_live_can_never_be_a_remote_command():
    """Hard invariant #2: the only road to live is config + restart + typed
    ARM LIVE at the PC console. arm_live must never be remotely armable."""
    from scripts.remote_control import REMOTE_SAFE_COMMANDS
    assert "arm_live" not in REMOTE_SAFE_COMMANDS
