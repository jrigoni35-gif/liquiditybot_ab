"""tests/test_remote_control.py — the one-bot git command bus.

The security posture IS the feature, so the pins are mostly negative:
arm_live can never ride this channel (whitelist invariant, sender refusal,
poller rejection), stale/future/malformed commands die at validation, and
an id is forwarded exactly once. The transport (fetch/worktree/push) is
exercised end-to-end against throwaway LOCAL repos — no network, and the
real paper-telemetry branch is never touched.
"""
import json
import subprocess
import time
from pathlib import Path

import pytest

import scripts.remote_control as rc
from core.runtime import VALID_COMMANDS


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True)


@pytest.fixture()
def repos(tmp_path, monkeypatch):
    """A bare 'origin' with a seeded paper-telemetry branch, plus a work
    repo cloned against it (stands in for the PC checkout)."""
    bare = tmp_path / "origin.git"
    _git("init", "--bare", "-b", "main", str(bare), cwd=tmp_path)
    root = tmp_path / "work"
    root.mkdir()
    _git("init", "-b", "main", str(root), cwd=tmp_path)
    _git("config", "user.email", "t@t.t", cwd=root)
    _git("config", "user.name", "t", cwd=root)
    _git("config", "commit.gpgsign", "false", cwd=root)
    (root / "code.txt").write_text("x", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-m", "init", cwd=root)
    _git("remote", "add", "origin", str(bare), cwd=root)
    _git("checkout", "--orphan", "paper-telemetry", cwd=root)
    _git("rm", "-rf", "--cached", ".", cwd=root)
    (root / "README").write_text("telemetry\n", encoding="utf-8")
    (root / "code.txt").unlink()
    _git("add", "README", cwd=root)
    _git("commit", "-m", "seed", cwd=root)
    _git("push", "origin", "paper-telemetry", cwd=root)
    _git("checkout", "main", cwd=root)
    monkeypatch.delenv("LB_NO_REMOTE_CMD", raising=False)
    monkeypatch.delenv("LB_NO_STATUS_PUSH", raising=False)
    return root, bare


def _branch_file(bare: Path, rel: str) -> str | None:
    p = subprocess.run(["git", "show", f"paper-telemetry:{rel}"],
                       cwd=str(bare), capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else None


# ---------------- whitelist invariants (the point of the design) ----------

def test_whitelist_is_subset_of_valid_commands():
    assert rc.REMOTE_SAFE_COMMANDS <= VALID_COMMANDS


def test_arm_live_can_never_ride_the_channel():
    assert "arm_live" not in rc.REMOTE_SAFE_COMMANDS


def test_sim_shocks_are_console_only():
    assert not any(c.startswith("sim_") for c in rc.REMOTE_SAFE_COMMANDS)


def test_safe_direction_commands_are_present():
    # de-risking must always be remotely reachable
    assert {"force_dry", "flatten_all", "pause",
            "disarm_live"} <= rc.REMOTE_SAFE_COMMANDS


def test_sender_refuses_non_whitelisted_before_transport(repos):
    root, _ = repos
    with pytest.raises(ValueError, match="not remotely allowed"):
        rc.send_command("arm_live", root=root)


# ---------------- validation table ----------------------------------------

def _payload(**over):
    p = {"id": "abc", "cmd": "pause", "args": {}, "issued_at": 1000.0}
    p.update(over)
    return p


def test_valid_payload_passes():
    assert rc.validate_command(_payload(), "abc", now=1000.0) is None


@pytest.mark.parametrize("payload,fid", [
    (None, "abc"),                                   # not an object
    (_payload(id="other"), "abc"),                   # id/filename mismatch
    (_payload(cmd="arm_live"), "abc"),               # forbidden command
    (_payload(cmd="sim_price_shock"), "abc"),        # console-only command
    (_payload(issued_at=None), "abc"),               # missing timestamp
    (_payload(issued_at=1000.0 - 1801), "abc"),      # stale
    (_payload(issued_at=1000.0 + 301), "abc"),       # future
    (_payload(args="pause"), "abc"),                 # args not an object
])
def test_invalid_payloads_are_rejected(payload, fid):
    reason = rc.validate_command(payload, fid, now=1000.0)
    assert reason is not None and "RC-011" in reason


# ---------------- end-to-end over a local bare repo ------------------------

def test_command_round_trip_exactly_once(repos):
    root, bare = repos
    cid = rc.send_command("pause", root=root)
    out = rc.poll_once(root=root)
    assert out == "applied=1 rejected=0"
    # forwarded into the runner's local control queue
    cmds = list((root / "outputs" / "control").glob("cmd_*.json"))
    assert len(cmds) == 1
    body = json.loads(cmds[0].read_text(encoding="utf-8"))
    assert body["cmd"] == "pause"
    # ledger remembers the id; a second poll forwards nothing
    ledger = json.loads(
        (root / "outputs" / "remote_consumed.json").read_text("utf-8"))
    assert [e["id"] for e in ledger] == [cid]
    assert rc.poll_once(root=root) in ("queue_empty", "applied=0 rejected=0")
    assert len(list((root / "outputs" / "control").glob("cmd_*.json"))) == 1


def test_stale_command_is_rejected_not_forwarded(repos, monkeypatch):
    root, bare = repos
    cid = rc.send_command("pause", root=root)
    out = rc.poll_once(root=root, now=time.time() + rc.MAX_AGE_SEC + 60)
    assert out == "applied=0 rejected=1"
    assert not list((root / "outputs" / "control").glob("cmd_*.json"))
    ledger = json.loads(
        (root / "outputs" / "remote_consumed.json").read_text("utf-8"))
    assert ledger[0]["id"] == cid and ledger[0]["result"] == "rejected"


def test_kill_switch_disables_polling(repos, monkeypatch):
    root, _ = repos
    rc.send_command("pause", root=root)
    monkeypatch.setenv("LB_NO_REMOTE_CMD", "1")
    assert rc.poll_once(root=root) == "disabled"
    assert not list((root / "outputs" / "control").glob("cmd_*.json"))


def test_status_push_publishes_and_gc_consumed_queue(repos):
    root, bare = repos
    (root / "outputs").mkdir(exist_ok=True)
    (root / "outputs" / "status.json").write_text(
        json.dumps({"equity": 5000.0, "runner_state": "RUNNING",
                    "written_at": time.time()}), encoding="utf-8")
    cid = rc.send_command("snapshot", root=root)
    assert rc.poll_once(root=root) == "applied=1 rejected=0"
    assert rc.push_pc_status(root=root) == "pushed"
    env = json.loads(_branch_file(bare, "control/pc_status.json"))
    assert env["status"]["equity"] == 5000.0
    assert env["remote_commands"][-1]["id"] == cid
    # the consumed queue file was garbage-collected in the same commit
    assert _branch_file(bare, f"control/queue/{cid}.json") is None


def test_status_push_without_status_is_a_noop(repos):
    root, _ = repos
    assert rc.push_pc_status(root=root) == "no_status"


def test_publish_leaves_caller_checkout_untouched(repos):
    root, _ = repos
    rc.send_command("pause", root=root)
    head = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                          cwd=str(root), check=True, capture_output=True,
                          text=True).stdout.strip()
    assert head == "main"
    wl = subprocess.run(["git", "worktree", "list"], cwd=str(root),
                        check=True, capture_output=True, text=True).stdout
    assert wl.count("\n") == 1
